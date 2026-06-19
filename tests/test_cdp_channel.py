from __future__ import annotations

import base64
import importlib
import sys
from urllib.error import HTTPError

import pytest

from ask_chatgpt import Session
from ask_chatgpt.channels.base import TabLease
from ask_chatgpt.errors import DomainNotAllowedError


class FakeRequest:
    def __init__(self, url: str, method: str = "GET", headers: dict[str, str] | None = None, request_id: str | None = None) -> None:
        self.url = url
        self.method = method
        self.request_id = request_id
        self._headers = headers or {}
        self.all_headers_calls = 0

    def all_headers(self) -> dict[str, str]:
        self.all_headers_calls += 1
        return dict(self._headers)


class FakeBindingHandle:
    def __init__(self, page: "FakePage", name: str) -> None:
        self.page = page
        self.name = name
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        self.page.closed_bindings.append(self.name)


class FakePage:
    def __init__(self, name: str = "page") -> None:
        self.name = name
        self.listeners: list[tuple[str, object]] = []
        self.removed_listeners: list[tuple[str, object]] = []
        self.goto_calls: list[tuple[str, dict[str, object]]] = []
        self.reload_calls: list[dict[str, object]] = []
        self.load_state_calls: list[tuple[str, dict[str, object]]] = []
        self.selector_calls: list[tuple[str, dict[str, object]]] = []
        self.hover_calls: list[str] = []
        self.press_calls: list[tuple[str, str]] = []
        self.set_input_files_calls: list[tuple[str, list[str]]] = []
        self.close_calls: list[dict[str, object]] = []
        self.order: list[str] = []
        self.bindings: dict[str, object] = {}
        self.closed_bindings: list[str] = []
        self.evaluate_calls: list[tuple[str, object | None]] = []
        self.composer_text = "fake composer text"
        self.next_click_result: dict[str, object] = {"ok": True}
        self.next_stream_chunks: list[bytes] = [b'{"ok":true}']
        self.next_stream_meta: dict[str, object] = {"status": 200, "headers": {"content-type": "application/json", "set-cookie": "CANARY_SECRET"}}
        self.next_small_result: dict[str, object] = {
            "status": 201,
            "headers": {"content-type": "text/plain", "set-cookie": "CANARY_SECRET"},
            "bodyB64": base64.b64encode(b"small body").decode("ascii"),
        }

    def on(self, event: str, handler: object) -> None:
        self.listeners.append((event, handler))
        self.order.append(f"page.on:{event}")

    def remove_listener(self, event: str, handler: object) -> None:
        self.removed_listeners.append((event, handler))
        self.order.append(f"page.remove_listener:{event}")

    def goto(self, url: str, **kwargs: object) -> None:
        self.goto_calls.append((url, dict(kwargs)))
        self.order.append("page.goto")

    def reload(self, **kwargs: object) -> None:
        self.reload_calls.append(dict(kwargs))
        self.order.append("page.reload")

    def wait_for_load_state(self, state: str, **kwargs: object) -> None:
        self.load_state_calls.append((state, dict(kwargs)))
        self.order.append("page.wait_for_load_state")

    def wait_for_selector(self, selector: str, **kwargs: object) -> None:
        self.selector_calls.append((selector, dict(kwargs)))
        self.order.append("page.wait_for_selector")

    def close(self, **kwargs: object) -> None:
        self.close_calls.append(dict(kwargs))
        self.order.append("page.close")

    def hover(self, selector: str) -> None:
        self.hover_calls.append(selector)
        self.order.append("page.hover")

    def press(self, selector: str, key: str) -> None:
        self.press_calls.append((selector, key))
        self.order.append("page.press")

    def set_input_files(self, selector: str, paths: list[str]) -> None:
        self.set_input_files_calls.append((selector, list(paths)))
        self.order.append("page.set_input_files")

    def expose_binding(self, name: str, callback: object) -> FakeBindingHandle:
        self.bindings[name] = callback
        self.order.append(f"page.expose_binding:{name}")
        return FakeBindingHandle(self, name)

    def wait_for_timeout(self, timeout: float) -> None:
        self.order.append(f"page.wait_for_timeout:{timeout}")

    def evaluate(self, expression: str, arg: object | None = None) -> object:
        self.evaluate_calls.append((expression, arg))
        self.order.append("page.evaluate")
        if "annotation[encoding" in expression:
            return ["\\frac{x}{y}"]
        if "data-message-author-role" in expression:
            return "visible assistant text"
        if isinstance(arg, dict) and "assistant_turn" in arg:
            return {
                "users": [{"message_id": "u1", "text": "hello"}],
                "assistants": [{"message_id": "a1", "text": "hi"}],
                "stop_visible": True,
                "composer_visible": False,
                "model_labels": ["GPT-4o"],
            }
        if expression == "arg => arg":
            return arg
        if "document.querySelector(a.selector)" in expression and "innerText || c.textContent || c.value" in expression:
            return self.composer_text
        if "querySelectorAll(a.selector)" in expression and "getBoundingClientRect" in expression and ".click()" in expression:
            return dict(self.next_click_result)
        if isinstance(arg, dict) and "bindingName" in arg:
            callback = self.bindings[str(arg["bindingName"])]
            seq = 0
            for chunk in self.next_stream_chunks:
                callback(  # type: ignore[misc]
                    {"page": self},
                    {
                        "kind": "chunk",
                        "streamId": arg["streamId"],
                        "seq": seq,
                        "dataB64": base64.b64encode(chunk).decode("ascii"),
                    },
                )
                seq += 1
            callback({"page": self}, {"kind": "done", "streamId": arg["streamId"], "seq": seq})  # type: ignore[misc]
            return self.next_stream_meta
        return self.next_small_result


class FakeCdpSession:
    def __init__(self) -> None:
        self.listeners: list[tuple[str, object]] = []
        self.send_calls: list[tuple[str, object | None]] = []
        self.detach_calls = 0
        self.order: list[str] = []

    def on(self, event: str, handler: object) -> None:
        self.listeners.append((event, handler))
        self.order.append(f"cdp.on:{event}")

    def send(self, method: str, params: object | None = None) -> dict[str, object]:
        self.send_calls.append((method, params))
        self.order.append(f"cdp.send:{method}")
        return {}

    def detach(self) -> None:
        self.detach_calls += 1
        self.order.append("cdp.detach")


class FakeContext:
    def __init__(self) -> None:
        self.pages_created: list[FakePage] = []
        self.cdp_sessions: list[FakeCdpSession] = []
        self.context_on_calls: list[tuple[str, object]] = []

    @property
    def pages(self) -> object:
        raise AssertionError("context.pages must not be touched")

    def on(self, event: str, handler: object) -> None:
        self.context_on_calls.append((event, handler))
        raise AssertionError("context.on must not be used")

    def new_page(self) -> FakePage:
        page = FakePage(f"page-{len(self.pages_created) + 1}")
        self.pages_created.append(page)
        return page

    def new_cdp_session(self, page: FakePage) -> FakeCdpSession:
        assert page in self.pages_created
        session = FakeCdpSession()
        self.cdp_sessions.append(session)
        return session


class FakeBrowser:
    def __init__(self, context: FakeContext) -> None:
        self._contexts = [context]
        self.close_calls = 0

    @property
    def contexts(self) -> list[FakeContext]:
        return self._contexts

    def close(self) -> None:
        self.close_calls += 1


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.connect_calls: list[tuple[str, dict[str, object]]] = []

    def connect_over_cdp(self, endpoint_url: str, **kwargs: object) -> FakeBrowser:
        self.connect_calls.append((endpoint_url, dict(kwargs)))
        return self.browser

    def launch(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("chromium.launch must not be used")


class FakePlaywright:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


def _assert_playwright_not_imported() -> None:
    assert not any(name == "playwright" or name.startswith("playwright.") for name in sys.modules)


def test_cdp_channel_import_and_construction_are_playwright_lazy(tmp_path) -> None:
    for name in list(sys.modules):
        if name == "playwright" or name.startswith("playwright.") or name == "ask_chatgpt.channels.cdp":
            sys.modules.pop(name, None)

    import ask_chatgpt  # noqa: F401
    _assert_playwright_not_imported()

    module = importlib.import_module("ask_chatgpt.channels.cdp")
    _assert_playwright_not_imported()

    module.CdpChannel()
    _assert_playwright_not_imported()

    session = Session(channel="cdp", data_dir=tmp_path)
    report = session.status(probe_browser=False)

    assert report.cdp is None
    _assert_playwright_not_imported()


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (HTTPError("http://127.0.0.1:9222/json/version", 503, "secret outage", {}, None), "http_error"),
        (TimeoutError("CANARY_SECRET timeout"), "timeout"),
        (ConnectionRefusedError("CANARY_SECRET refused"), "connection_refused"),
        (ValueError("CANARY_SECRET invalid json"), "invalid_json"),
    ],
)
def test_preflight_maps_http_failures_to_redacted_cdp_unreachable(exc, expected_error) -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    def fail(_url: str, _timeout_s: float):
        raise exc

    result = CdpChannel(http_get_json=fail).preflight(timeout_s=1.25)

    assert result.ok is False
    assert result.cdp_endpoint == "http://127.0.0.1:9222"
    assert result.error_code == "CDP_UNREACHABLE"
    assert result.error == expected_error
    assert "CANARY_SECRET" not in repr(result)


def test_preflight_maps_version_json_without_leaking_websocket_url() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    calls: list[tuple[str, float]] = []

    def get_json(url: str, timeout_s: float):
        calls.append((url, timeout_s))
        return {
            "Browser": "Chrome/142.0",
            "Protocol-Version": "1.3",
            "webSocketDebuggerUrl": "ws://CANARY_SECRET/socket",
        }

    result = CdpChannel(cdp_endpoint="http://127.0.0.1:9222/", http_get_json=get_json).preflight(timeout_s=2.5)

    assert calls == [("http://127.0.0.1:9222/json/version", 2.5)]
    assert result.ok is True
    assert result.browser == "Chrome/142.0"
    assert result.protocol_version == "1.3"
    assert result.websocket_url_present is True
    assert "CANARY_SECRET" not in repr(result)


def test_preflight_missing_websocket_is_cdp_unreachable() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    result = CdpChannel(http_get_json=lambda _url, _timeout_s: {"Browser": "Chrome/142.0"}).preflight()

    assert result.ok is False
    assert result.browser == "Chrome/142.0"
    assert result.websocket_url_present is False
    assert result.error_code == "CDP_UNREACHABLE"
    assert result.error == "websocket_url_missing"


def test_open_tab_and_fetch_reject_disallowed_urls_before_playwright_factory() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    def forbidden_factory():
        raise AssertionError("playwright factory must not be touched for disallowed URLs")

    channel = CdpChannel(playwright_factory=forbidden_factory)
    tab = TabLease("missing-tab", "https://chatgpt.com/c/conv_allowed", channel)

    for bad_url in ("https://evil.example/c/private-canary", "//evil.example/path", "javascript:alert(1)"):
        with pytest.raises(DomainNotAllowedError):
            channel.open_tab(bad_url)
        with pytest.raises(DomainNotAllowedError):
            channel.fetch_in_page(tab, bad_url)


def test_attach_open_close_detach_own_pages_without_context_page_enumeration() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)

    channel.attach()
    tab1 = channel.open_tab("https://chatgpt.com/c/conv_1")
    tab2 = channel.open_tab("https://chatgpt.com/c/conv_2")
    channel.close_tab(tab1)
    channel.detach()

    assert playwright.chromium.connect_calls == [("http://127.0.0.1:9222", {"timeout": 5000})]
    assert tab1.channel is channel
    assert tab2.channel is channel
    assert len(context.pages_created) == 2
    assert len(context.cdp_sessions) == 2
    assert context.context_on_calls == []
    assert context.pages_created[0].goto_calls == [("https://chatgpt.com/c/conv_1", {"wait_until": "domcontentloaded", "timeout": 30000})]
    assert [event for event, _handler in context.pages_created[0].listeners] == ["request", "requestfinished"]
    assert [event for event, _handler in context.cdp_sessions[0].listeners] == [
        "Network.requestWillBeSent",
        "Network.requestWillBeSentExtraInfo",
    ]
    assert context.cdp_sessions[0].send_calls == [("Network.enable", None)]
    assert context.pages_created[0].order.index("page.on:request") < context.pages_created[0].order.index("page.goto")
    assert context.pages_created[0].close_calls == [{"run_before_unload": False}]
    assert context.cdp_sessions[0].detach_calls == 1
    assert context.pages_created[1].close_calls == [{"run_before_unload": False}]
    assert context.cdp_sessions[1].detach_calls == 1
    assert browser.close_calls == 1
    assert playwright.stop_calls == 1


def test_consume_stream_event_reassembles_bytes_and_rejects_bad_events() -> None:
    from ask_chatgpt.channels.cdp import StreamState, consume_stream_event

    first = "π".encode("utf-8")[:1]
    second = "π".encode("utf-8")[1:] + b" done"
    written = bytearray()
    state = StreamState(stream_id="stream-1")

    consume_stream_event(
        state,
        {"kind": "chunk", "streamId": "stream-1", "seq": 0, "dataB64": base64.b64encode(first).decode("ascii")},
        written.extend,
    )
    consume_stream_event(
        state,
        {"kind": "chunk", "streamId": "stream-1", "seq": 1, "dataB64": base64.b64encode(second).decode("ascii")},
        written.extend,
    )
    consume_stream_event(state, {"kind": "done", "streamId": "stream-1", "seq": 2}, written.extend)

    assert bytes(written).decode("utf-8") == "π done"
    assert state.bytes_written == len(written)
    assert state.done is True

    bad_cases = [
        ("expected", {"kind": "chunk", "streamId": "other", "seq": 0, "dataB64": ""}, "streamId"),
        ("stream-2", {"kind": "chunk", "streamId": "stream-2", "seq": 1, "dataB64": ""}, "seq"),
        ("stream-3", {"kind": "chunk", "streamId": "stream-3", "seq": 0, "dataB64": "not-base64-@@"}, "base64"),
    ]
    for state_id, event, match in bad_cases:
        with pytest.raises(ValueError, match=match):
            consume_stream_event(StreamState(stream_id=state_id), event, bytearray().extend)

    duplicate = StreamState(stream_id="stream-4")
    consume_stream_event(duplicate, {"kind": "done", "streamId": "stream-4", "seq": 0}, bytearray().extend)
    with pytest.raises(ValueError, match="done"):
        consume_stream_event(duplicate, {"kind": "done", "streamId": "stream-4", "seq": 1}, bytearray().extend)


def test_fetch_in_page_returns_protocol_shapes_and_filters_sensitive_response_headers(tmp_path) -> None:
    from ask_chatgpt.channels.base import FetchResult
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_fetch")
    page = context.pages_created[0]

    raw_path = tmp_path / "raw-mapping.json.tmp"
    streamed = channel.fetch_in_page(
        tab,
        "/backend-api/conversation/conv_fetch",
        headers={"authorization": "CANARY_SECRET", "oai-client-version": "CANARY_SECRET"},
        stream_to=raw_path,
    )
    small = channel.fetch_in_page(
        tab,
        "/backend-api/conversation/conv_fetch",
        headers={"authorization": "CANARY_SECRET"},
    )

    assert isinstance(streamed, FetchResult)
    assert streamed.status == 200
    assert streamed.body_path == raw_path
    assert streamed.body_bytes is None
    assert raw_path.read_bytes() == b'{"ok":true}'
    assert streamed.headers == {"content-type": "application/json"}
    assert page.closed_bindings
    assert isinstance(small, FetchResult)
    assert small.status == 201
    assert small.body_path is None
    assert small.body_bytes == b"small body"
    assert small.headers == {"content-type": "text/plain"}
    assert "CANARY_SECRET" not in repr(streamed)
    assert "CANARY_SECRET" not in repr(small)


def test_fetch_in_page_sanitizes_page_evaluate_exceptions() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_fetch")
    page = context.pages_created[0]

    def fail(_expression: str, _arg: object | None = None) -> object:
        raise RuntimeError("CANARY_SECRET from fake evaluate args")

    page.evaluate = fail  # type: ignore[method-assign]

    with pytest.raises(RuntimeError) as exc_info:
        channel.fetch_in_page(tab, "/backend-api/conversation/conv_fetch", headers={"authorization": "CANARY_SECRET"})

    assert "CANARY_SECRET" not in str(exc_info.value)
    assert "CANARY_SECRET" not in repr(exc_info.value)


def test_wait_for_request_uses_cheap_predicate_projects_headers_and_cdp_fallback() -> None:
    from ask_chatgpt.capture import REQUIRED_CAPTURE_HEADERS
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_headers")
    page = context.pages_created[0]
    cdp = context.cdp_sessions[0]
    page_request_handler = next(handler for event, handler in page.listeners if event == "request")
    cdp_extra_handler = next(handler for event, handler in cdp.listeners if event == "Network.requestWillBeSentExtraInfo")
    cdp_request_handler = next(handler for event, handler in cdp.listeners if event == "Network.requestWillBeSent")
    target_url = "https://chatgpt.com/backend-api/conversation/conv_headers"

    required = {name: f"CANARY_SECRET_{name}" for name in REQUIRED_CAPTURE_HEADERS}
    request = FakeRequest(target_url, "GET", {**required, "cookie": "CANARY_SECRET_COOKIE"}, request_id="req-primary")
    seen_snapshots = []
    page_request_handler(request)  # type: ignore[misc]
    snapshot = channel.wait_for_request(tab, lambda snap: seen_snapshots.append(snap) or True, timeout_s=0.0)

    assert seen_snapshots[0].headers == {}
    assert request.all_headers_calls == 1
    assert set(snapshot.headers) == set(REQUIRED_CAPTURE_HEADERS)
    assert "cookie" not in snapshot.headers
    assert snapshot.headers["authorization"] == "CANARY_SECRET_authorization"
    assert "CANARY_SECRET" not in repr(snapshot)

    cdp_extra_handler({"requestId": "req-cdp", "headers": required})  # type: ignore[misc]
    cdp_request_handler({"requestId": "req-cdp", "request": {"url": target_url, "method": "GET"}})  # type: ignore[misc]
    cdp_only = FakeRequest(target_url, "GET", {}, request_id="req-cdp")
    page_request_handler(cdp_only)  # type: ignore[misc]
    cdp_snapshot = channel.wait_for_request(tab, lambda snap: snap.url == target_url, timeout_s=0.0)

    assert cdp_only.all_headers_calls == 1
    assert set(cdp_snapshot.headers) == set(REQUIRED_CAPTURE_HEADERS)
    assert cdp_snapshot.headers["oai-session-id"] == "CANARY_SECRET_oai-session-id"
    assert "CANARY_SECRET" not in repr(cdp_snapshot)

    deficient = FakeRequest(target_url, "GET", {"authorization": "CANARY_SECRET_last"}, request_id="req-deficient")
    page_request_handler(deficient)  # type: ignore[misc]
    deficient_snapshot = channel.wait_for_request(tab, lambda snap: snap.url == target_url, timeout_s=0.0)

    assert dict(deficient_snapshot.headers) == {"authorization": "CANARY_SECRET_last"}
    assert "CANARY_SECRET" not in repr(deficient_snapshot)


def test_cdp_fill_uses_exec_command_with_text_arg_and_readback_js() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_actions")
    page = context.pages_created[0]
    text = "INLINE_GUARD_text_arg_only"

    channel.fill(tab, "#prompt-textarea", text)
    readback = channel.evaluate(tab, "ask_chatgpt_send_read_composer_text", arg={"selector": "#prompt-textarea"})

    fill_js, fill_arg = page.evaluate_calls[-2]
    read_js, read_arg = page.evaluate_calls[-1]
    assert "execCommand('selectAll')" in fill_js
    assert "execCommand('delete')" in fill_js
    assert "execCommand('insertText'" in fill_js
    assert "new InputEvent('input'" in fill_js
    assert fill_arg == {"selector": "#prompt-textarea", "text": text}
    assert text not in fill_js
    assert "document.querySelector(a.selector)" in read_js
    assert "innerText || c.textContent || c.value" in read_js
    assert read_arg == {"selector": "#prompt-textarea"}
    assert readback == "fake composer text"


def test_cdp_insert_hover_press_and_upload_delegate_to_owned_page(tmp_path) -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_actions")
    page = context.pages_created[0]

    channel.insert_text(tab, "#prompt-textarea", "append me")
    channel.hover(tab, "button.menu")
    channel.press(tab, "#prompt-textarea", "Enter")
    channel.upload_files(tab, "input[type=file]", [tmp_path / "a.txt", tmp_path / "b.txt"])

    insert_js, insert_arg = page.evaluate_calls[-1]
    assert "execCommand('insertText'" in insert_js
    assert "execCommand('selectAll')" not in insert_js
    assert "execCommand('delete')" not in insert_js
    assert insert_arg == {"selector": "#prompt-textarea", "text": "append me"}
    assert page.hover_calls == ["button.menu"]
    assert page.press_calls == [("#prompt-textarea", "Enter")]
    assert page.set_input_files_calls == [
        ("input[type=file]", [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")])
    ]


def test_cdp_click_filters_visible_enabled_and_reports_missing_selector() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel
    from ask_chatgpt.errors import SelectorNotFoundError

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_actions")
    page = context.pages_created[0]
    selector = 'button[data-testid="send-button"], #composer-submit-button'

    channel.click(tab, selector)

    click_js, click_arg = page.evaluate_calls[-1]
    assert "querySelectorAll(a.selector)" in click_js
    assert "getComputedStyle" in click_js
    assert "getBoundingClientRect" in click_js
    assert "aria-disabled" in click_js
    assert "hasAttribute('disabled')" in click_js
    assert ".click()" in click_js
    assert click_arg == {"selector": selector}

    page.next_click_result = {"ok": False, "reason": "no enabled send button"}
    with pytest.raises(SelectorNotFoundError) as exc_info:
        channel.click(tab, selector)
    assert exc_info.value.details["selector"] == selector


def test_cdp_open_radix_trigger_dispatches_pointer_sequence_through_evaluate_key() -> None:
    # Falsifiability: removing the CDP dispatch branch or pointer sequence makes the evaluated JS/token assertions fail.
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_actions")
    page = context.pages_created[0]
    selector = 'form button[aria-haspopup="menu"]:not([data-testid])'

    result = channel.evaluate(tab, "ask_chatgpt_open_radix_trigger", arg={"selector": selector}, timeout_s=5.0)

    open_js, open_arg = page.evaluate_calls[-1]
    assert result == {"ok": True}
    assert "querySelectorAll(a.selector)" in open_js
    assert "scrollIntoView({block: 'center', inline: 'center'})" in open_js
    assert "new PointerEvent('pointerdown'" in open_js
    assert "new MouseEvent('mousedown'" in open_js
    assert "new PointerEvent('pointerup'" in open_js
    assert "new MouseEvent('mouseup'" in open_js
    assert "target.click();" in open_js
    assert open_arg == {"selector": selector}


def test_cdp_menu_select_label_dispatches_pointer_events_before_click() -> None:
    # Falsifiability: reverting JS_MENU_CLICK_LABEL to a bare target.click() removes these pointer-event tokens.
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_actions")
    page = context.pages_created[0]

    channel.evaluate(
        tab,
        "ask_chatgpt_menu_click_label",
        arg={"label": "High", "role": "menuitemradio", "path": [], "action": "select"},
        timeout_s=5.0,
    )

    menu_js, _menu_arg = page.evaluate_calls[-1]
    assert "if (a.action === 'select')" in menu_js
    assert "dispatchPointerActivation(target);" in menu_js
    assert "new PointerEvent('pointerdown'" in menu_js
    assert "new MouseEvent('mousedown'" in menu_js
    assert "new PointerEvent('pointerup'" in menu_js
    assert "new MouseEvent('mouseup'" in menu_js
    assert "target.click();" in menu_js


def test_cdp_action_methods_validate_own_open_tab_before_touching_page() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_actions")
    channel.close_tab(tab)
    foreign = TabLease("foreign-tab", "https://chatgpt.com/c/foreign", CdpChannel())

    actions = [
        lambda bad: channel.fill(bad, "#prompt-textarea", "text"),
        lambda bad: channel.insert_text(bad, "#prompt-textarea", "text"),
        lambda bad: channel.click(bad, "button"),
        lambda bad: channel.hover(bad, "button"),
        lambda bad: channel.press(bad, "#prompt-textarea", "Enter"),
        lambda bad: channel.upload_files(bad, "input[type=file]", []),
    ]
    for action in actions:
        with pytest.raises(ValueError, match="different channel"):
            action(foreign)
        with pytest.raises(ValueError, match="unknown or closed CDP tab"):
            action(tab)


def test_cdp_read_clipboard_still_requires_human_permission() -> None:
    from ask_chatgpt.channels.cdp import CdpChannel
    from ask_chatgpt.errors import HumanActionNeededError

    channel = CdpChannel()
    tab = TabLease("missing-tab", "https://chatgpt.com/", channel)

    with pytest.raises(HumanActionNeededError) as exc_info:
        channel.read_clipboard(tab)
    assert exc_info.value.details["reason"] == "clipboard_permission"


def test_dom_read_methods_delegate_to_owned_page_and_return_protocol_dataclasses() -> None:
    from ask_chatgpt.channels.base import TurnDom, TurnDomSnapshot
    from ask_chatgpt.channels.cdp import CdpChannel

    context = FakeContext()
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    channel = CdpChannel(playwright_factory=lambda: playwright)
    channel.attach()
    tab = channel.open_tab("https://chatgpt.com/c/conv_dom")
    page = context.pages_created[0]

    channel.reload(tab)
    channel.wait_for_load_state(tab, timeout_s=1.5)
    channel.wait_for_selector(tab, "main", state="attached", timeout_s=2.0)
    katex = channel.evaluate(tab, "ask_chatgpt_capture_katex_annotations", timeout_s=5.0)
    dom_text = channel.evaluate(tab, "ask_chatgpt_capture_dom_text", timeout_s=5.0)
    generic = channel.evaluate(tab, "arg => arg", arg={"ok": True}, timeout_s=1.0)
    turns = channel.query_turns(
        tab,
        {
            "composer": "textarea",
            "tools_button": "button",
            "message_turn": "article",
            "user_turn": "[data-message-author-role='user']",
            "assistant_turn": "[data-message-author-role='assistant']",
            "copy_button": "button.copy",
            "stop_button": "button.stop",
            "send_button_unverified_no_input": "button.send",
            "radix_portal": "[data-radix-portal]",
            "model_picker_trigger_candidates": "button.model",
        },
    )

    assert page.reload_calls == [{"wait_until": "domcontentloaded"}]
    assert page.load_state_calls == [("domcontentloaded", {"timeout": 1500})]
    assert page.selector_calls == [("main", {"state": "attached", "timeout": 2000})]
    assert katex == ["\\frac{x}{y}"]
    assert dom_text == "visible assistant text"
    assert generic == {"ok": True}
    assert turns == TurnDomSnapshot(
        users=(TurnDom("u1", "user", "hello"),),
        assistants=(TurnDom("a1", "assistant", "hi"),),
        stop_visible=True,
        composer_visible=False,
        model_labels=("GPT-4o",),
    )


def test_catalogue_completion_status_vocab_redacts_progress_payloads(tmp_path) -> None:
    from ask_chatgpt.capture import catalogue_completion_status_vocab

    raw_path = tmp_path / "raw-mapping.json"
    raw_path.write_text(
        """
        {
          "async_status": "complete",
          "mapping": {
            "n1": {
              "status": "node_done",
              "message": {
                "status": "finished_successfully",
                "metadata": {
                  "is_complete": true,
                  "is_finalizing": false,
                  "pro_progress": {"phase": "thinking", "secret": "CANARY_SECRET_OBJECT"}
                }
              }
            },
            "n2": {
              "status": "node_done",
              "message": {
                "status": "in_progress",
                "metadata": {
                  "is_complete": false,
                  "is_finalizing": true,
                  "pro_progress": "CANARY_SECRET free text progress"
                }
              }
            },
            "n3": {
              "status": "node_waiting",
              "message": {"status": "queued", "metadata": {"pro_progress": "searching"}}
            }
          }
        }
        """,
        encoding="utf-8",
    )

    summary = catalogue_completion_status_vocab(raw_path)

    assert summary["async_status"] == {"complete": 1}
    assert summary["node.status"] == {"node_done": 2, "node_waiting": 1}
    assert summary["message.status"] == {"finished_successfully": 1, "in_progress": 1, "queued": 1}
    assert summary["metadata.is_complete"] == {"false": 1, "true": 1}
    assert summary["metadata.is_finalizing"] == {"false": 1, "true": 1}
    assert summary["metadata.pro_progress"]["searching"] == 1
    assert any(key.startswith("object:keys=phase,secret:len=2:sha256=") for key in summary["metadata.pro_progress"])
    assert any(key.startswith("str:len=32:sha256=") for key in summary["metadata.pro_progress"])
    assert "CANARY_SECRET" not in repr(summary)


def test_m5_capture_measure_script_imports_without_running_cdp() -> None:
    import importlib.util

    script = "scripts/m5_capture_measure.py"
    spec = importlib.util.spec_from_file_location("m5_capture_measure", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.main)
