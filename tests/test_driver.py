import json
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect

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

    def goto(self, url: str, **_kwargs):
        self.goto_calls.append(url)
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
