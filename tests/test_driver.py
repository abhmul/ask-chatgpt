import json
from pathlib import Path
import time

import pytest
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, expect

from ask_chatgpt.driver import BrowserSession, REAL_BASE_URL
from ask_chatgpt.errors import (
    LoginRequiredError,
    ModelUnavailableError,
    RateLimitedError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
)
from ask_chatgpt.selector_map import SelectorMap, load_selector_map


EMPTY_REAL_SELECTOR_MAPS_DIR = Path(__file__).parent / "fixtures" / "selector_maps" / "empty"


class _FakeLocator:
    def __init__(self, *, count: int = 1, attributes: dict[str, str | None] | None = None) -> None:
        self._count = count
        self._attributes = {} if attributes is None else attributes
        self.click_count = 0

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        return self

    def click(self, **_kwargs) -> None:
        self.click_count += 1

    def get_attribute(self, attr: str) -> str | None:
        return self._attributes.get(attr)


class _FakePage:
    def __init__(self, *, url: str, locators: dict[str, _FakeLocator]) -> None:
        self.url = url
        self._locators = locators
        self.wait_count = 0

    def locator(self, selector: str) -> _FakeLocator:
        return self._locators[selector]

    def wait_for_load_state(self, *_args, **_kwargs) -> None:
        self.wait_count += 1


class _CallbackLocator:
    def __init__(
        self,
        *,
        count_fn=None,
        attributes: dict[str, str | None] | None = None,
        on_click=None,
        on_fill=None,
    ) -> None:
        self._count_fn = count_fn or (lambda: 1)
        self._attributes = {} if attributes is None else attributes
        self._on_click = on_click
        self._on_fill = on_fill
        self.click_count = 0
        self.filled_texts: list[str] = []

    def count(self) -> int:
        return int(self._count_fn())

    @property
    def first(self):
        return self

    def click(self, **_kwargs) -> None:
        self.click_count += 1
        if self._on_click is not None:
            self._on_click()

    def fill(self, text: str, **_kwargs) -> None:
        self.filled_texts.append(text)
        if self._on_fill is not None:
            self._on_fill(text)

    def get_attribute(self, attr: str) -> str | None:
        return self._attributes.get(attr)


class _DelayedReadyPage:
    def __init__(self, *, url: str = "https://chatgpt.com/", ref: str = "") -> None:
        self.url = url
        self.ref = ref
        self.ready_attached = False
        self.new_chat_click_count = 0
        self.wait_for_selector_calls: list[tuple[str, dict]] = []
        self.load_wait_count = 0
        self.goto_calls: list[str] = []
        self.goto_call_kwargs: list[dict] = []

    def goto(self, url: str, **_kwargs):
        self.goto_calls.append(url)
        self.goto_call_kwargs.append(dict(_kwargs))
        self.url = url
        self.ref = url.rstrip("/").rsplit("/", 1)[-1]
        self.ready_attached = False
        return None

    def locator(self, selector: str):
        if selector == "#ready":
            return _CallbackLocator(
                count_fn=lambda: self.ready_attached,
                attributes={"data-conversation-ref": self.ref},
            )
        if selector == "#composer":
            return _CallbackLocator(count_fn=lambda: self.ready_attached)
        if selector == "#new-chat":
            return _CallbackLocator(on_click=self._click_new_chat)
        if selector in {"#not-found", "#login"}:
            return _CallbackLocator(count_fn=lambda: 0)
        raise KeyError(selector)

    def wait_for_selector(self, selector: str, **kwargs) -> None:
        self.wait_for_selector_calls.append((selector, dict(kwargs)))
        assert selector == "#ready"
        assert kwargs.get("state") == "attached"
        self.ready_attached = True

    def wait_for_load_state(self, *_args, **_kwargs) -> None:
        self.load_wait_count += 1

    def title(self) -> str:
        return "ChatGPT"

    def _click_new_chat(self) -> None:
        self.new_chat_click_count += 1
        self.ref = "new-delayed-ref"
        self.url = "https://chatgpt.com/c/new-delayed-ref"
        self.ready_attached = False


class _NeverReadyPage(_DelayedReadyPage):
    def wait_for_selector(self, selector: str, **kwargs) -> None:
        self.wait_for_selector_calls.append((selector, dict(kwargs)))
        raise PlaywrightTimeoutError("ready_root did not attach")


class _SendButtonAfterFillPage:
    def __init__(self) -> None:
        self.url = "https://chatgpt.com/"
        self.composer_filled = False
        self.filled_texts: list[str] = []
        self.send_click_count = 0
        self.wait_for_selector_calls: list[tuple[str, dict, bool]] = []
        self.load_wait_count = 0

    def locator(self, selector: str):
        if selector == "#composer":
            return _CallbackLocator(on_fill=self._fill_composer)
        if selector == "#send":
            return _CallbackLocator(count_fn=lambda: self.composer_filled, on_click=self._click_send)
        raise KeyError(selector)

    def wait_for_selector(self, selector: str, **kwargs) -> None:
        self.wait_for_selector_calls.append((selector, dict(kwargs), self.composer_filled))
        if selector == "#send" and self.composer_filled:
            return
        raise PlaywrightTimeoutError("send button did not attach")

    def wait_for_load_state(self, *_args, **_kwargs) -> None:
        self.load_wait_count += 1

    def _fill_composer(self, text: str) -> None:
        self.filled_texts.append(text)
        self.composer_filled = True

    def _click_send(self) -> None:
        self.send_click_count += 1


class _RealSendMechanicsLocator:
    def __init__(self, page: "_RealSendMechanicsPage", name: str, *, count: int = 1) -> None:
        self._page = page
        self._name = name
        self._count = count

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        return self

    def click(self, **_kwargs) -> None:
        self._page.events.append(("click", self._name))
        if self._name == "send":
            self._page.send_click_count += 1

    def fill(self, text: str, **_kwargs) -> None:
        self._page.events.append(("fill", text))
        if self._page.fill_raises:
            raise PlaywrightError("contenteditable fill failed")
        self._page.filled_texts.append(text)

    def get_attribute(self, _attr: str) -> str | None:
        return None


class _RecordingKeyboard:
    def __init__(self, page: "_RealSendMechanicsPage") -> None:
        self._page = page

    def press(self, key: str) -> None:
        self._page.events.append(("press", key))

    def insert_text(self, text: str) -> None:
        self._page.events.append(("insert_text", text))
        if self._page.insert_raises:
            raise PlaywrightError("insert_text failed")


class _RealSendMechanicsPage:
    def __init__(self, *, send_button_present: bool, fill_raises: bool = False, insert_raises: bool = False) -> None:
        self.url = "https://chatgpt.com/"
        self.send_button_present = send_button_present
        self.fill_raises = fill_raises
        self.insert_raises = insert_raises
        self.keyboard = _RecordingKeyboard(self)
        self.events: list[tuple] = []
        self.filled_texts: list[str] = []
        self.send_click_count = 0
        self.wait_for_selector_calls: list[tuple[str, dict]] = []

    def locator(self, selector: str):
        if selector == "#composer":
            return _RealSendMechanicsLocator(self, "composer")
        if selector == "#send":
            return _RealSendMechanicsLocator(self, "send", count=1 if self.send_button_present else 0)
        if selector in {"#not-found", "#login", "#rate-limit"}:
            return _RealSendMechanicsLocator(self, selector, count=0)
        raise KeyError(selector)

    def wait_for_selector(self, selector: str, **kwargs) -> None:
        self.wait_for_selector_calls.append((selector, dict(kwargs)))
        if selector == "#send" and self.send_button_present:
            return
        raise PlaywrightTimeoutError("send button absent")

    def wait_for_load_state(self, *_args, **_kwargs) -> None:
        self.events.append(("wait_for_load_state",))


class _CompletionLocator:
    def __init__(
        self,
        *,
        count: int = 0,
        count_fn=None,
        items: list["_CompletionLocator"] | None = None,
        children: dict[str, "_CompletionLocator"] | None = None,
        text_values: list[str] | None = None,
    ) -> None:
        self._count = count
        self._count_fn = count_fn
        self._items = [] if items is None else items
        self._children = {} if children is None else children
        self._text_values = text_values
        self._text_index = 0

    def count(self) -> int:
        if self._count_fn is not None:
            return int(self._count_fn())
        return self._count

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def nth(self, index: int):
        return self._items[index]

    def locator(self, selector: str):
        return self._children.get(selector, _CompletionLocator(count=0))

    def inner_text(self, **_kwargs) -> str:
        if not self._text_values:
            return ""
        index = min(self._text_index, len(self._text_values) - 1)
        self._text_index += 1
        return self._text_values[index]


class _CountSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = values
        self._index = 0

    def __call__(self) -> int:
        index = min(self._index, len(self._values) - 1)
        self._index += 1
        return self._values[index]


class _CompletionPollingPage:
    def __init__(self, *, text_values: list[str], streaming_counts: list[int], completion_count: int = 0) -> None:
        self.url = "https://chatgpt.com/c/unit"
        self.wait_timeouts: list[int] = []
        self.latest_assistant = _CompletionLocator(
            count=1,
            children={
                "#complete": _CompletionLocator(count=completion_count),
                "#streaming": _CompletionLocator(count=0),
            },
        )
        self._locators = {
            "#not-found": _CompletionLocator(count=0),
            "#login": _CompletionLocator(count=0),
            "#rate-limit": _CompletionLocator(count=0),
            "#assistant": _CompletionLocator(count=1, items=[self.latest_assistant]),
            "#body": _CompletionLocator(count=1, text_values=text_values),
            "#complete": _CompletionLocator(count=completion_count),
            "#streaming": _CompletionLocator(count_fn=_CountSequence(streaming_counts)),
        }

    def locator(self, selector: str):
        try:
            return self._locators[selector]
        except KeyError as exc:
            raise AssertionError(f"unexpected selector: {selector}") from exc

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_timeouts.append(timeout_ms)
        time.sleep(timeout_ms / 1000)


def _real_unit_session(page) -> BrowserSession:
    session = BrowserSession(channel="real", base_url=REAL_BASE_URL)
    session.selectors = SelectorMap(
        channel="unit",
        selectors={
            "ready_root": "#ready",
            "composer": "#composer",
            "new_chat_button": "#new-chat",
            "conversation_not_found": "#not-found",
            "login_wall": "#login",
        },
        attributes={"conversation_ref": "data-conversation-ref"},
    )
    session.page = page
    return session


def _real_send_mechanics_session(page: _RealSendMechanicsPage) -> BrowserSession:
    session = BrowserSession(channel="real", base_url=REAL_BASE_URL)
    session.selectors = SelectorMap(
        channel="unit",
        selectors={
            "composer": "#composer",
            "send_button": "#send",
            "conversation_not_found": "#not-found",
            "login_wall": "#login",
            "rate_limit_marker": "#rate-limit",
        },
        attributes={},
    )
    session.page = page
    return session


def _real_completion_session(page: _CompletionPollingPage) -> BrowserSession:
    session = BrowserSession(channel="real", base_url=REAL_BASE_URL)
    session.selectors = SelectorMap(
        channel="unit",
        selectors={
            "conversation_not_found": "#not-found",
            "login_wall": "#login",
            "rate_limit_marker": "#rate-limit",
            "truncation_marker": "",
            "assistant_message": "#assistant",
            "message_body": "#body",
            "completion_marker": "#complete",
            "streaming_marker": "#streaming",
        },
        attributes={},
    )
    session.page = page
    return session


class _ScriptedClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance_ms(self, timeout_ms: int) -> None:
        self.now += timeout_ms / 1000


class _ScriptedCompletionPage:
    def __init__(self, clock: _ScriptedClock) -> None:
        self.url = "https://chatgpt.com/c/unit-scripted"
        self.clock = clock
        self.wait_timeouts: list[int] = []

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_timeouts.append(timeout_ms)
        self.clock.advance_ms(timeout_ms)


class _ScriptedCountLocator:
    def __init__(self, count_fn) -> None:
        self._count_fn = count_fn

    def count(self) -> int:
        return int(self._count_fn())


class _ScriptedTurnLocator:
    def __init__(self, state: "_MicroPauseCompletionState") -> None:
        self._state = state

    def locator(self, selector: str):
        return _ScriptedCountLocator(lambda: self._state.selector_count(selector))

    def inner_text(self, **_kwargs) -> str:
        return self._state.text()


class _MicroPauseCompletionState:
    sentinel = "__TURN_COMPLETE_M008A_MICRO_PAUSE__"

    def __init__(self, clock: _ScriptedClock) -> None:
        self.clock = clock
        self.complete_text = "\n".join(
            [f"M008A-LINE-{index:03d} deterministic long completion payload keeps growing" for index in range(180)]
            + [self.sentinel]
        )
        self.pause_text = "\n".join(self.complete_text.splitlines()[:80])
        self.turn = _ScriptedTurnLocator(self)

    def text(self) -> str:
        now = self.clock.now
        if now < 0.1:
            return "\n".join(self.complete_text.splitlines()[:10])
        if now < 2.5:
            return self.pause_text
        if now < 2.6:
            return "\n".join(self.complete_text.splitlines()[:120])
        if now < 2.8:
            return "\n".join(self.complete_text.splitlines()[:150])
        return self.complete_text

    def streaming_visible(self) -> bool:
        now = self.clock.now
        return now < 0.2 or 2.5 <= now < 2.8

    def completion_marker_visible(self) -> bool:
        return self.clock.now >= 2.8

    def completion_affordance_visible(self) -> bool:
        return False

    def selector_count(self, selector: str) -> int:
        if selector == "#complete":
            return int(self.completion_marker_visible())
        if selector == "#streaming":
            return int(self.streaming_visible())
        if selector == "#affordance":
            return int(self.completion_affordance_visible())
        return 0

    def present(self, key: str) -> bool:
        if key == "truncation_marker":
            return False
        if key == "streaming_marker":
            return self.streaming_visible()
        if key == "completion_marker":
            return self.completion_marker_visible()
        if key == "completion_affordance":
            return self.completion_affordance_visible()
        if key in {"conversation_not_found", "login_wall", "rate_limit_marker"}:
            return False
        raise AssertionError(f"unexpected present key: {key}")


class _StableMarkerCompletionState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M008B_MARKER__"

    def text(self) -> str:
        return self.complete_text

    def streaming_visible(self) -> bool:
        return self.clock.now < 0.2

    def completion_marker_visible(self) -> bool:
        return self.clock.now >= 0.2


class _PrematureGlobalMarkerState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M008B_PREMATURE_GLOBAL__"

    def text(self) -> str:
        now = self.clock.now
        if now < 0.4:
            return self.complete_text[:4]
        if now < 0.8:
            return "\n".join(self.complete_text.splitlines()[:30])
        if now < 1.2:
            return "\n".join(self.complete_text.splitlines()[:90])
        return self.complete_text

    def streaming_visible(self) -> bool:
        now = self.clock.now
        return 0.4 <= now < 1.2

    def completion_marker_visible(self) -> bool:
        return True

    def latest_completion_marker_visible(self) -> bool:
        return self.clock.now >= 1.2

    def selector_count(self, selector: str) -> int:
        if selector == "#complete":
            return int(self.latest_completion_marker_visible())
        return super().selector_count(selector)


class _GlobalOnlyMarkerCompletionState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M008B_GLOBAL_ONLY_MARKER__"

    def selector_count(self, selector: str) -> int:
        if selector == "#complete":
            return 0
        return super().selector_count(selector)


class _NeverSawStreamingCompleteState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M009_NEVER_SAW_STREAMING__"

    def text(self) -> str:
        return self.complete_text  # stable, non-empty from t=0

    def streaming_visible(self) -> bool:
        return False  # the stop control was never caught by any poll

    def completion_marker_visible(self) -> bool:
        return True  # copy-turn marker present: the turn is already complete


class _ShortReplyNeverStreamedState(_NeverSawStreamingCompleteState):
    sentinel = "PING"

    def text(self) -> str:
        return "PING"  # one-word reply, stable, non-empty


class _ImmediateAffordanceCompletionState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M008A_AFFORDANCE__"

    def text(self) -> str:
        return self.complete_text

    def streaming_visible(self) -> bool:
        return self.clock.now < 0.2

    def completion_marker_visible(self) -> bool:
        return False

    def completion_affordance_visible(self) -> bool:
        return self.clock.now >= 0.2


class _GrowingUntilCompletionState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M008A_PROGRESS__"

    def text(self) -> str:
        index = min(int(self.clock.now * 10) + 1, 12)
        if index >= 12:
            return self.complete_text
        return "\n".join(self.complete_text.splitlines()[: index * 15])

    def streaming_visible(self) -> bool:
        return self.clock.now < 1.2

    def completion_marker_visible(self) -> bool:
        return self.clock.now >= 1.2


class _NeverCompletesGrowingState(_MicroPauseCompletionState):
    sentinel = "__TURN_INCOMPLETE_M008B_UNBOUNDED__"

    def text(self) -> str:
        return f"partial response keeps growing at t={self.clock.now:.1f}s"

    def streaming_visible(self) -> bool:
        return True

    def completion_marker_visible(self) -> bool:
        return False

    def completion_affordance_visible(self) -> bool:
        return False


class _CeilingSafetyValvePage(_ScriptedCompletionPage):
    def __init__(self, clock: _ScriptedClock, *, max_waits: int = 100) -> None:
        super().__init__(clock)
        self.max_waits = max_waits

    def wait_for_timeout(self, timeout_ms: int) -> None:
        if len(self.wait_timeouts) >= self.max_waits:
            raise RuntimeError("unbounded: no ceiling")
        super().wait_for_timeout(timeout_ms)


def _scripted_real_completion_session(
    monkeypatch,
    state: _MicroPauseCompletionState,
    page: _ScriptedCompletionPage,
    *,
    include_completion_affordance: bool = False,
) -> BrowserSession:
    session = BrowserSession(channel="cdp", base_url=REAL_BASE_URL)
    selectors = {
        "completion_marker": "#complete",
        "streaming_marker": "#streaming",
    }
    if include_completion_affordance:
        selectors["completion_affordance"] = "#affordance"
    session.selectors = SelectorMap(channel="unit", selectors=selectors, attributes={})
    session.page = page
    monkeypatch.setattr("ask_chatgpt.driver.time.monotonic", page.clock.monotonic)
    monkeypatch.setattr(session, "_require_page", lambda: page)
    monkeypatch.setattr(session, "_present", state.present)
    monkeypatch.setattr(session, "_latest_assistant_turn", lambda: state.turn)
    monkeypatch.setattr(session, "_latest_assistant_body_text", lambda _latest: state.text())
    monkeypatch.setattr(
        session,
        "_optional_selector",
        lambda key: None if key == "truncation_marker" else session.selectors.selectors.get(key),
    )
    monkeypatch.setattr(session, "_raise_open_failures", lambda: None)
    monkeypatch.setattr(session, "_rate_limit_visible", lambda: False)
    return session


def test_driver_happy_path_returns_latest_completed_turn(mock_chatgpt):
    answer = "Driver happy path answer 8b85df"
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(answer)

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        conversation_ref = session.open_or_create_conversation(None)
        assert conversation_ref.startswith("conv-")

        session.select_model({"model": "mock-default"})
        session.send_prompt("hello driver")
        latest = session.wait_for_completion(timeout_s=3)

        expect(latest.locator(session.selectors.selector("message_body"))).to_have_text(answer, timeout=1000)
        assert mock_chatgpt.inspect()["last_prompt"] == "hello driver"
        assert session.page.url.startswith(mock_chatgpt.base_url + "/c/")


def test_driver_streaming_completion_reload_polls_until_complete(mock_chatgpt):
    answer = "Driver streamed answer 42c80b"
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(answer, streaming=True, stream_reads=2)

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        session.send_prompt("stream this")
        latest = session.wait_for_completion(timeout_s=5)

        expect(latest.locator(session.selectors.selector("message_body"))).to_have_text(answer, timeout=1000)
        assert mock_chatgpt.inspect()["conversations"][session.active_conversation_ref]["turns"][-1]["complete"] is True


def test_conversation_ref_from_url_derives_c_path_and_decodes():
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")

    assert session._conversation_ref_from_url("https://chatgpt.com/c/abc123") == "abc123"
    assert session._conversation_ref_from_url("https://chatgpt.com/") is None
    assert session._conversation_ref_from_url("http://127.0.0.1:9999/c/loop-ref") == "loop-ref"
    assert session._conversation_ref_from_url("https://chatgpt.com/c/abc%2Fdef%20x") == "abc/def x"


def test_read_active_conversation_ref_prefers_dom_attribute_over_url():
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    session.selectors = SelectorMap(
        channel="unit",
        selectors={"ready_root": "#ready"},
        attributes={"conversation_ref": "data-conversation-ref"},
    )
    session.page = _FakePage(
        url="https://chatgpt.com/c/url-ref",
        locators={"#ready": _FakeLocator(attributes={"data-conversation-ref": "dom-ref"})},
    )

    assert session._read_active_conversation_ref() == "dom-ref"


def test_read_active_conversation_ref_falls_back_to_url_when_attribute_unavailable():
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    session.selectors = SelectorMap(
        channel="unit",
        selectors={"ready_root": "#ready"},
        attributes={"conversation_ref": ""},
    )
    session.page = _FakePage(
        url="https://chatgpt.com/c/url-ref-123",
        locators={"#ready": _FakeLocator(attributes={})},
    )

    assert session._read_active_conversation_ref() == "url-ref-123"


def test_refresh_active_conversation_ref_updates_from_settled_url_after_empty_start():
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    session.selectors = SelectorMap(
        channel="unit",
        selectors={"ready_root": "#ready"},
        attributes={"conversation_ref": "data-conversation-ref"},
    )
    page = _FakePage(
        url="https://chatgpt.com/",
        locators={"#ready": _FakeLocator(attributes={})},
    )
    session.page = page
    session._active_conversation_ref = ""

    assert session.active_conversation_ref == ""

    page.url = "https://chatgpt.com/c/settled-ref"

    assert session.refresh_active_conversation_ref() == "settled-ref"
    assert session.active_conversation_ref == "settled-ref"


def test_refresh_active_conversation_ref_fail_closed_when_url_never_settles():
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    session.selectors = SelectorMap(
        channel="unit",
        selectors={"ready_root": "#ready"},
        attributes={"conversation_ref": "data-conversation-ref"},
    )
    session.page = _FakePage(
        url="https://chatgpt.com/",
        locators={"#ready": _FakeLocator(attributes={})},
    )
    session._active_conversation_ref = ""

    assert session.refresh_active_conversation_ref() is None
    assert session.active_conversation_ref == ""


def test_open_or_create_new_conversation_tolerates_no_ref_until_after_send():
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    new_chat = _FakeLocator()
    session.selectors = SelectorMap(
        channel="unit",
        selectors={
            "ready_root": "#ready",
            "composer": "#composer",
            "new_chat_button": "#new-chat",
            "conversation_not_found": "#not-found",
            "login_wall": "#login",
        },
        attributes={"conversation_ref": ""},
    )
    session.page = _FakePage(
        url="https://chatgpt.com/",
        locators={
            "#ready": _FakeLocator(),
            "#composer": _FakeLocator(),
            "#new-chat": new_chat,
            "#not-found": _FakeLocator(count=0),
            "#login": _FakeLocator(count=0),
        },
    )

    assert session.open_or_create_conversation(None) == ""
    assert session.active_conversation_ref == ""
    assert new_chat.click_count == 1


def test_open_existing_conversation_waits_for_delayed_real_ready_root_before_requiring_it():
    page = _DelayedReadyPage()
    session = _real_unit_session(page)

    assert session.open_or_create_conversation("existing-delayed-ref") == "existing-delayed-ref"

    assert page.goto_calls == ["https://chatgpt.com/c/existing-delayed-ref"]
    assert page.goto_call_kwargs == [{"wait_until": "load", "timeout": 60_000}]
    assert page.wait_for_selector_calls == [
        ("#ready", {"timeout": 30_000, "state": "attached"}),
    ]


def test_open_new_conversation_waits_for_initial_and_post_click_real_ready_root():
    page = _DelayedReadyPage()
    session = _real_unit_session(page)

    assert session.open_or_create_conversation(None) == "new-delayed-ref"

    assert page.new_chat_click_count == 1
    assert page.load_wait_count == 1
    assert page.wait_for_selector_calls == [
        ("#ready", {"timeout": 30_000, "state": "attached"}),
        ("#ready", {"timeout": 30_000, "state": "attached"}),
    ]


def test_wait_for_ready_root_timeout_reports_title_and_url_path_shape_only():
    page = _NeverReadyPage(url="https://chatgpt.com/c/secret-conversation-ref?token=SECRET")
    session = _real_unit_session(page)

    with pytest.raises(SelectorUnavailableError) as excinfo:
        session._wait_for_ready_root(timeout_ms=17)

    message = str(excinfo.value)
    assert "app did not become ready" in message
    assert "title='ChatGPT'" in message
    assert "path_shape='/c/<segment>'" in message
    assert "secret-conversation-ref" not in message
    assert "token=SECRET" not in message
    assert page.wait_for_selector_calls == [("#ready", {"timeout": 17, "state": "attached"})]


def test_send_prompt_fills_composer_before_waiting_for_send_button_after_fill():
    page = _SendButtonAfterFillPage()
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    session.selectors = SelectorMap(
        channel="unit",
        selectors={"composer": "#composer", "send_button": "#send"},
        attributes={},
    )
    session.page = page

    session.send_prompt("hello after fill")

    assert page.filled_texts == ["hello after fill"]
    assert page.wait_for_selector_calls == [("#send", {"timeout": 5_000, "state": "attached"}, True)]
    assert page.send_click_count == 1
    assert page.load_wait_count == 1


def test_real_send_prompt_focuses_before_fill_and_enters_when_send_button_absent():
    page = _RealSendMechanicsPage(send_button_present=False)
    session = _real_send_mechanics_session(page)

    session.send_prompt("hello real")

    assert page.events[:2] == [("click", "composer"), ("fill", "hello real")]
    assert ("press", "Enter") in page.events
    assert ("click", "send") not in page.events
    assert page.send_click_count == 0


def test_real_send_prompt_clicks_send_button_when_it_is_present():
    page = _RealSendMechanicsPage(send_button_present=True)
    session = _real_send_mechanics_session(page)

    session.send_prompt("hello click")

    assert page.events[:2] == [("click", "composer"), ("fill", "hello click")]
    assert ("click", "send") in page.events
    assert ("press", "Enter") not in page.events
    assert page.send_click_count == 1


def test_real_send_prompt_uses_keyboard_insert_text_when_contenteditable_fill_fails():
    page = _RealSendMechanicsPage(send_button_present=False, fill_raises=True)
    session = _real_send_mechanics_session(page)

    session.send_prompt("fallback text")

    assert page.events[:4] == [
        ("click", "composer"),
        ("fill", "fallback text"),
        ("press", "Control+A"),
        ("insert_text", "fallback text"),
    ]
    assert ("press", "Enter") in page.events


def test_real_send_prompt_maps_hard_fill_and_insert_failure_to_selector_error():
    page = _RealSendMechanicsPage(send_button_present=False, fill_raises=True, insert_raises=True)
    session = _real_send_mechanics_session(page)

    with pytest.raises(SelectorUnavailableError, match="selector 'composer' unavailable"):
        session.send_prompt("no fill")

    assert ("press", "Enter") not in page.events


def test_real_wait_for_completion_returns_after_completion_marker_visible(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _StableMarkerCompletionState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=5.0)

    assert latest is state.turn
    assert state.sentinel in latest.inner_text()
    assert clock.now >= 3.0
    assert page.wait_timeouts


def test_real_wait_for_completion_returns_when_never_saw_streaming_marker_and_text_stable(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _NeverSawStreamingCompleteState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)

    assert latest is state.turn
    assert state.sentinel in latest.inner_text()
    assert clock.now >= 3.0   # waited the stability window
    assert clock.now < 30.0   # did NOT run to the truncation deadline


def test_real_wait_for_completion_returns_short_reply_that_never_streamed(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _ShortReplyNeverStreamedState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)

    assert latest.inner_text() == "PING"
    assert clock.now < 30.0


def test_real_wait_for_completion_times_out_when_stop_gone_and_body_stable_without_completion_evidence(monkeypatch):
    monkeypatch.setattr("ask_chatgpt.driver._POLL_INTERVAL_S", 0.005)
    page = _CompletionPollingPage(
        text_values=["stable but unfinished", "stable but unfinished", "stable but unfinished"],
        streaming_counts=[1, 0, 0, 0],
        completion_count=0,
    )
    session = _real_completion_session(page)

    with pytest.raises(ResponseTruncatedError, match="completion marker did not appear before timeout"):
        session.wait_for_completion(timeout_s=0.03)


def test_real_wait_for_completion_does_not_return_midstream_micro_pause_without_completion_evidence(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _MicroPauseCompletionState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=5.0)
    returned_text = latest.inner_text()

    assert state.sentinel in returned_text, (
        f"returned clipped text at t={clock.now:.1f}s length={len(returned_text)} tail={returned_text[-160:]!r}"
    )
    assert returned_text == state.complete_text
    assert len(returned_text) >= 4096
    assert returned_text.count("\n") >= 150


def test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _PrematureGlobalMarkerState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)
    returned_text = latest.inner_text()

    assert returned_text == state.complete_text, (
        f"returned premature partial at t={clock.now:.1f}s length={len(returned_text)} text={returned_text!r}"
    )
    assert state.sentinel in returned_text


def test_real_wait_for_completion_completes_when_marker_is_global_only_not_in_turn(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _GlobalOnlyMarkerCompletionState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)
    returned_text = latest.inner_text()

    assert state.selector_count("#complete") == 0
    assert returned_text == state.complete_text
    assert state.sentinel in returned_text


def test_real_wait_for_completion_honors_optional_completion_affordance_when_marker_absent(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _ImmediateAffordanceCompletionState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page, include_completion_affordance=True)

    latest = session.wait_for_completion(timeout_s=5.0)

    assert latest is state.turn
    assert state.sentinel in latest.inner_text()
    assert clock.now >= 3.0
    assert page.wait_timeouts


def test_real_wait_for_completion_extends_deadline_while_body_text_grows(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _GrowingUntilCompletionState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=3.5, max_total_wait_s=6.0)
    returned_text = latest.inner_text()

    assert returned_text == state.complete_text
    assert state.sentinel in returned_text
    assert clock.now >= 4.2
    assert clock.now < 6.0


@pytest.mark.parametrize("ceiling_s", [5.0])
def test_real_wait_for_completion_caps_progress_extensions_at_absolute_ceiling(monkeypatch, ceiling_s):
    monkeypatch.setattr("ask_chatgpt.driver._POLL_INTERVAL_S", 0.5)
    clock = _ScriptedClock()
    page = _CeilingSafetyValvePage(clock)
    state = _NeverCompletesGrowingState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    with pytest.raises(ResponseTruncatedError, match="completion marker did not appear before timeout"):
        try:
            session.wait_for_completion(timeout_s=2.0, max_total_wait_s=ceiling_s)
        except TypeError as exc:
            if "max_total_wait_s" not in str(exc):
                raise
            session.wait_for_completion(timeout_s=2.0)

    assert ceiling_s <= clock.now <= ceiling_s + 0.5


def test_real_wait_for_completion_times_out_when_body_text_never_stabilizes(monkeypatch):
    monkeypatch.setattr("ask_chatgpt.driver._POLL_INTERVAL_S", 0.005)
    changing_text = [f"partial {index}" for index in range(100)]
    page = _CompletionPollingPage(
        text_values=changing_text,
        streaming_counts=[1] + [0] * 200,
        completion_count=1,
    )
    session = _real_completion_session(page)

    with pytest.raises(ResponseTruncatedError, match="completion marker did not appear before timeout"):
        session.wait_for_completion(timeout_s=0.05)


def test_selector_map_missing_and_empty_keys_fail_closed(tmp_path):
    maps_dir = tmp_path
    (maps_dir / "bad.json").write_text(
        json.dumps(
            {
                "channel": "bad",
                "version": 1,
                "selectors": {"composer": ""},
                "attributes": {"conversation_ref": ""},
            }
        ),
        encoding="utf-8",
    )

    selector_map = load_selector_map("bad", maps_dir=maps_dir)

    with pytest.raises(SelectorUnavailableError, match="selector 'composer' unavailable for channel 'bad'"):
        selector_map.selector("composer")
    with pytest.raises(SelectorUnavailableError, match="selector 'missing' unavailable for channel 'bad'"):
        selector_map.selector("missing")
    with pytest.raises(SelectorUnavailableError, match="attribute 'conversation_ref' unavailable for channel 'bad'"):
        selector_map.attribute("conversation_ref")
    with pytest.raises(SelectorUnavailableError, match="attribute 'missing' unavailable for channel 'bad'"):
        selector_map.attribute("missing")


def test_selector_unavailable_fixture_mode_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="selector_unavailable")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(SelectorUnavailableError):
            session.open_or_create_conversation(None)


def test_login_required_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="login_required")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(LoginRequiredError):
            session.open_or_create_conversation(None)


def test_session_not_found_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="session_not_found")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(SessionNotFoundError):
            session.open_or_create_conversation("missing-driver-session")


def test_model_unavailable_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(
        "unused", failure_mode="model_unavailable", unavailable_model="mock-reasoning"
    )

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        with pytest.raises(ModelUnavailableError):
            session.select_model({"model": "mock-reasoning"})


def test_response_truncated_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("partial truncated answer", failure_mode="response_truncated")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        session.send_prompt("truncate this")
        with pytest.raises(ResponseTruncatedError):
            session.wait_for_completion(timeout_s=1)


def test_rate_limited_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="rate_limited")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        with pytest.raises(RateLimitedError):
            session.send_prompt("rate limit this")


def test_tests_use_loopback_only_while_real_constant_exists(mock_chatgpt):
    assert REAL_BASE_URL == "https://chatgpt.com"

    mock_chatgpt.reset()
    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        assert session.page.url.startswith(mock_chatgpt.base_url)
        assert "chatgpt.com" not in session.page.url


def test_empty_real_selector_map_fixture_fails_closed():
    fixture_path = EMPTY_REAL_SELECTOR_MAPS_DIR / "real.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert payload["channel"] == "real"
    assert payload["selectors"]
    assert payload["attributes"]
    assert all(value == "" for value in payload["selectors"].values())
    assert all(value == "" for value in payload["attributes"].values())

    selector_map = load_selector_map("real", maps_dir=EMPTY_REAL_SELECTOR_MAPS_DIR)
    first_selector_key = next(iter(payload["selectors"]))
    with pytest.raises(SelectorUnavailableError):
        selector_map.selector(first_selector_key)
    with pytest.raises(SelectorUnavailableError):
        selector_map.attribute("conversation_ref")
