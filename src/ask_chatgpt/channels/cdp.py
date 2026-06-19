"""Playwright-over-CDP browser channel adapter.

The module is import-safe for offline tests: Playwright is imported only inside
the production attach path.
"""

from __future__ import annotations

import base64
import binascii
import json
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen

from ask_chatgpt.allowlist import Allowlist
from ask_chatgpt.capture import REQUIRED_CAPTURE_HEADERS
from ask_chatgpt.channels.base import FetchResult, RequestSnapshot, TabLease, TurnDom, TurnDomSnapshot
from ask_chatgpt.errors import HumanActionNeededError, SelectorNotFoundError
from ask_chatgpt.models import JsonValue, PreflightResult, SelectorMap


def _urllib_get_json(url: str, timeout_s: float) -> Mapping[str, Any]:
    with urlopen(url, timeout=timeout_s) as response:  # noqa: S310 - caller controls CDP endpoint; preflight only.
        payload = response.read()
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("CDP version response was not an object")
    return data


def _cdp_unreachable(endpoint: str, reason: str) -> PreflightResult:
    return PreflightResult(
        ok=False,
        cdp_endpoint=endpoint,
        browser=None,
        protocol_version=None,
        websocket_url_present=False,
        error_code="CDP_UNREACHABLE",
        error=reason,
    )


JS_STREAM_FETCH = """
async ({bindingName, streamId, url, method, headers, bodyText, bodyB64, chunkBytes, timeoutMs}) => {
  function bytesToBase64(bytes) {
    let binary = "";
    const step = 0x8000;
    for (let i = 0; i < bytes.length; i += step) {
      binary += String.fromCharCode(...bytes.subarray(i, i + step));
    }
    return btoa(binary);
  }
  const controller = new AbortController();
  const timer = timeoutMs == null ? null : setTimeout(() => controller.abort(), timeoutMs);
  try {
    const init = {method, headers, credentials: "include", cache: "no-store", signal: controller.signal};
    if (bodyText != null) init.body = bodyText;
    if (bodyB64 != null) init.body = Uint8Array.from(atob(bodyB64), c => c.charCodeAt(0));
    const response = await fetch(url, init);
    if (!response.body) throw new Error("response.body stream unavailable");
    const reader = response.body.getReader();
    let seq = 0;
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      for (let off = 0; off < value.length; off += chunkBytes) {
        const part = value.subarray(off, off + chunkBytes);
        await window[bindingName]({kind: "chunk", streamId, seq: seq++, dataB64: bytesToBase64(part)});
      }
    }
    await window[bindingName]({kind: "done", streamId, seq});
    return {status: response.status, headers: Object.fromEntries(response.headers.entries())};
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}
"""

JS_SMALL_FETCH = """
async ({url, method, headers, bodyText, bodyB64, timeoutMs}) => {
  function bytesToBase64(bytes) {
    let binary = "";
    const step = 0x8000;
    for (let i = 0; i < bytes.length; i += step) {
      binary += String.fromCharCode(...bytes.subarray(i, i + step));
    }
    return btoa(binary);
  }
  const controller = new AbortController();
  const timer = timeoutMs == null ? null : setTimeout(() => controller.abort(), timeoutMs);
  try {
    const init = {method, headers, credentials: "include", cache: "no-store", signal: controller.signal};
    if (bodyText != null) init.body = bodyText;
    if (bodyB64 != null) init.body = Uint8Array.from(atob(bodyB64), c => c.charCodeAt(0));
    const response = await fetch(url, init);
    const buffer = await response.arrayBuffer();
    return {status: response.status, headers: Object.fromEntries(response.headers.entries()), bodyB64: bytesToBase64(new Uint8Array(buffer))};
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}
"""

JS_KATEX_ANNOTATIONS = """() => Array.from(document.querySelectorAll('annotation[encoding="application/x-tex"]')).map(n => n.textContent || '')"""

JS_DOM_TEXT = """() => Array.from(document.querySelectorAll('[data-message-author-role="assistant"]')).map(n => n.innerText || n.textContent || '').join('\n\n')"""

JS_QUERY_TURNS = """
(selectors) => {
  function items(selector, role) {
    if (!selector) return [];
    return Array.from(document.querySelectorAll(selector)).map((node, index) => ({
      message_id: node.getAttribute('data-message-id') || node.id || `${role}:${index}`,
      text: node.innerText || node.textContent || ''
    }));
  }
  function visible(selector) {
    if (!selector) return false;
    const node = document.querySelector(selector);
    if (!node) return false;
    const style = window.getComputedStyle(node);
    return style && style.display !== 'none' && style.visibility !== 'hidden';
  }
  const labels = selectors.model_picker_trigger_candidates ?
    Array.from(document.querySelectorAll(selectors.model_picker_trigger_candidates)).map(n => (n.innerText || n.textContent || '').trim()).filter(Boolean) : [];
  return {
    users: items(selectors.user_turn, 'user'),
    assistants: items(selectors.assistant_turn, 'assistant'),
    stop_visible: visible(selectors.stop_button),
    composer_visible: visible(selectors.composer),
    model_labels: labels
  };
}
"""

JS_READ_COMPOSER_TEXT = """
(a) => {
  const c = document.querySelector(a.selector);
  return c ? (c.innerText || c.textContent || c.value || '') : '';
}
"""

JS_CURRENT_URL = """() => window.location.href"""

JS_MENU_ENUMERATE = r"""
(a) => {
  const portal = document.querySelector(a.portal_selector || '[data-radix-popper-content-wrapper]');
  if (!portal) return [];
  const norm = value => (value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const disabled = el => Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  return Array.from(portal.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'))
    .filter(visible)
    .map(el => {
      const ariaChecked = el.getAttribute('aria-checked');
      return {
        label: norm(el.innerText || el.textContent || el.getAttribute('aria-label') || ''),
        role: el.getAttribute('role'),
        checked: ariaChecked === 'true' ? true : (ariaChecked === 'false' ? false : null),
        disabled: disabled(el),
        path: []
      };
    })
    .filter(item => item.label);
}
"""

JS_MENU_CLICK_LABEL = r"""
(a) => {
  const portal = document.querySelector('[data-radix-popper-content-wrapper]');
  if (!portal) return {ok: false, reason: 'portal_absent'};
  const norm = value => (value || '').replace(/\s+/g, ' ').trim();
  const requested = norm(a.label);
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const enabled = el => !(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const matches = Array.from(portal.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'))
    .filter(el => visible(el) && enabled(el))
    .filter(el => norm(el.innerText || el.textContent || el.getAttribute('aria-label') || '') === requested)
    .filter(el => !a.role || el.getAttribute('role') === a.role);
  if (matches.length !== 1) return {ok: false, reason: 'match_count', count: matches.length};
  const target = matches[0];
  if (a.action === 'open_submenu') {
    target.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, cancelable: true, view: window}));
    target.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true, cancelable: true, view: window}));
    target.focus();
  }
  target.click();
  return {ok: true};
}
"""

JS_FILL_COMPOSER = """
(a) => {
  const c = document.querySelector(a.selector);
  if (!c) return {ok: false, reason: 'selector_not_found'};
  c.scrollIntoView({block: 'center'});
  c.focus();
  document.execCommand('selectAll');
  document.execCommand('delete');
  document.execCommand('insertText', false, a.text);
  c.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: a.text}));
  return {ok: true};
}
"""

JS_INSERT_TEXT = """
(a) => {
  const c = document.querySelector(a.selector);
  if (!c) return {ok: false, reason: 'selector_not_found'};
  c.scrollIntoView({block: 'center'});
  c.focus();
  document.execCommand('insertText', false, a.text);
  c.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: a.text}));
  return {ok: true};
}
"""

JS_CLICK_VISIBLE_ENABLED = """
(a) => {
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const enabled = el => !(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const matches = Array.from(document.querySelectorAll(a.selector));
  const target = matches.filter(visible).find(enabled);
  if (!target) return {ok: false, reason: 'no_visible_enabled_match', count: matches.length};
  target.click();
  return {ok: true};
}
"""


def _absolute_fetch_url(tab_url: str, url: str) -> str:
    raw = str(url).strip()
    parsed = urlsplit(raw)
    if parsed.scheme:
        return raw
    if raw.startswith("//"):
        return raw
    if raw.startswith("/"):
        return urljoin(tab_url, raw)
    return urljoin(tab_url, raw)


def _fetch_eval_arg(
    *,
    url: str,
    method: str,
    headers: Mapping[str, str] | None,
    body: bytes | str | None,
    timeout_s: float | None,
    binding_name: str | None = None,
    stream_id: str | None = None,
) -> dict[str, Any]:
    arg: dict[str, Any] = {
        "url": url,
        "method": method,
        "headers": dict(headers or {}),
        "bodyText": body if isinstance(body, str) else None,
        "bodyB64": base64.b64encode(body).decode("ascii") if isinstance(body, bytes) else None,
        "timeoutMs": None if timeout_s is None else int(float(timeout_s) * 1000),
    }
    if binding_name is not None:
        arg.update({"bindingName": binding_name, "streamId": stream_id, "chunkBytes": 128 * 1024})
    return arg


def _safe_response_headers(headers: object) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        return {}
    out: dict[str, str] = {}
    for key, value in headers.items():
        name = str(key).lower()
        if name in {"authorization", "cookie", "set-cookie"} or name.startswith("oai-"):
            continue
        out[name] = str(value)
    return out


def _meta_status(meta: object) -> int:
    if not isinstance(meta, Mapping):
        raise ValueError("fetch result metadata was not an object")
    status = meta.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        raise ValueError("fetch result status was not an integer")
    return status


def _meta_headers(meta: object) -> dict[str, str]:
    if not isinstance(meta, Mapping):
        raise ValueError("fetch result metadata was not an object")
    return _safe_response_headers(meta.get("headers"))


def _meta_body_bytes(meta: object) -> bytes:
    if not isinstance(meta, Mapping):
        raise ValueError("fetch result metadata was not an object")
    body_b64 = meta.get("bodyB64")
    if not isinstance(body_b64, str):
        raise ValueError("fetch result body was missing")
    return decode_stream_chunk_base64(body_b64)


def _project_required_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    required = set(REQUIRED_CAPTURE_HEADERS)
    out: dict[str, str] = {}
    for key, value in headers.items():
        name = str(key).lower()
        if name in required:
            out[name] = str(value)
    return out


def _request_attr(request: Any, name: str) -> str:
    value = getattr(request, name, "")
    if callable(value):
        value = value()
    return value if isinstance(value, str) else ""


def _request_id(request: Any) -> str | None:
    for attr in ("request_id", "requestId", "_request_id"):
        value = getattr(request, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _string_tuple(items: object) -> tuple[str, ...]:
    if not isinstance(items, list | tuple):
        return ()
    return tuple(item for item in items if isinstance(item, str))


def _turns_from_raw(items: object, role: Literal["user", "assistant"]) -> list[TurnDom]:
    if not isinstance(items, list):
        return []
    turns: list[TurnDom] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        message_id = item.get("message_id")
        text = item.get("text")
        turns.append(
            TurnDom(
                str(message_id) if isinstance(message_id, str) and message_id else f"{role}:{index}",
                role,
                text if isinstance(text, str) else "",
            )
        )
    return turns


@dataclass
class StreamState:
    stream_id: str
    next_seq: int = 0
    bytes_written: int = 0
    done: bool = False


class _RedactedHeaders(dict[str, str]):
    def __repr__(self) -> str:
        return "{" + ", ".join(f"{key!r}: '<redacted>'" for key in sorted(self)) + "}"

    __str__ = __repr__


@dataclass
class _ObservedRequest:
    url: str
    method: str
    request: Any
    request_id: str | None


@dataclass
class _CdpRequestInfo:
    url: str | None = None
    method: str | None = None
    headers: dict[str, str] | None = None


def decode_stream_chunk_base64(chunk: str) -> bytes:
    try:
        return base64.b64decode(chunk.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError("invalid base64 stream chunk") from exc


def append_decoded_stream_chunk(sink: Any, chunk: str) -> int:
    data = decode_stream_chunk_base64(chunk)
    sink.write(data)
    return len(data)


def consume_stream_event(state: StreamState, event: Mapping[str, Any], write_bytes: Callable[[bytes], object]) -> None:
    if event.get("streamId") != state.stream_id:
        raise ValueError("streamId mismatch")
    if state.done:
        raise ValueError("stream already done")
    seq = event.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq != state.next_seq:
        raise ValueError("stream seq out of order")
    kind = event.get("kind")
    if kind == "chunk":
        chunk = event.get("dataB64")
        if not isinstance(chunk, str):
            raise ValueError("stream chunk dataB64 missing")
        data = decode_stream_chunk_base64(chunk)
        write_bytes(data)
        state.bytes_written += len(data)
        state.next_seq += 1
        return
    if kind == "done":
        state.done = True
        state.next_seq += 1
        return
    raise ValueError("unknown stream event kind")


@dataclass
class _TabState:
    page: Any
    url: str
    cdp_session: Any | None
    page_listeners: tuple[tuple[str, Callable[..., None]], ...]


class CdpChannel:
    def __init__(
        self,
        *,
        cdp_endpoint: str = "http://127.0.0.1:9222",
        allowlist: Allowlist | None = None,
        http_get_json: Callable[[str, float], Mapping[str, Any]] | None = None,
        playwright_factory: Callable[[], Any] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._clock = monotonic or time.monotonic
        self._sleeper = sleeper or time.sleep
        self.cdp_endpoint = cdp_endpoint.rstrip("/")
        self._allowlist = allowlist or Allowlist()
        self._http_get_json = http_get_json or _urllib_get_json
        self._playwright_factory = playwright_factory
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._next_tab_index = 1
        self._pages: dict[str, Any] = {}
        self._tab_urls: dict[str, str] = {}
        self._tab_states: dict[str, _TabState] = {}
        self._request_buffers: dict[str, list[_ObservedRequest]] = {}
        self._request_cursors: dict[str, int] = {}
        self._cdp_requests: dict[str, dict[str, _CdpRequestInfo]] = {}

    def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult:
        url = f"{self.cdp_endpoint}/json/version"
        try:
            info = self._http_get_json(url, float(timeout_s))
        except HTTPError:
            return _cdp_unreachable(self.cdp_endpoint, "http_error")
        except TimeoutError:
            return _cdp_unreachable(self.cdp_endpoint, "timeout")
        except ConnectionRefusedError:
            return _cdp_unreachable(self.cdp_endpoint, "connection_refused")
        except (URLError, OSError):
            return _cdp_unreachable(self.cdp_endpoint, "connection_refused")
        except (json.JSONDecodeError, ValueError, TypeError):
            return _cdp_unreachable(self.cdp_endpoint, "invalid_json")
        if not isinstance(info, Mapping):
            return _cdp_unreachable(self.cdp_endpoint, "invalid_json")
        browser = info.get("Browser") if isinstance(info.get("Browser"), str) else None
        protocol_version = info.get("Protocol-Version") if isinstance(info.get("Protocol-Version"), str) else None
        websocket_url_present = isinstance(info.get("webSocketDebuggerUrl"), str) and bool(info.get("webSocketDebuggerUrl"))
        if not websocket_url_present:
            return PreflightResult(
                ok=False,
                cdp_endpoint=self.cdp_endpoint,
                browser=browser,
                protocol_version=protocol_version,
                websocket_url_present=False,
                error_code="CDP_UNREACHABLE",
                error="websocket_url_missing",
            )
        return PreflightResult(
            ok=True,
            cdp_endpoint=self.cdp_endpoint,
            browser=browser,
            protocol_version=protocol_version,
            websocket_url_present=True,
        )

    def monotonic(self) -> float:
        return float(self._clock())

    def sleep(self, seconds: float) -> None:
        self._sleeper(seconds)

    def attach(self) -> None:
        if self._context is not None:
            return
        playwright = self._start_playwright()
        browser = playwright.chromium.connect_over_cdp(self.cdp_endpoint, timeout=5000)
        contexts = browser.contexts
        if not contexts:
            try:
                browser.close()
            finally:
                playwright.stop()
            raise RuntimeError("CDP browser has no contexts")
        self._playwright = playwright
        self._browser = browser
        self._context = contexts[0]

    def detach(self) -> None:
        for tab_id in list(self._tab_states):
            state = self._tab_states.get(tab_id)
            if state is None:
                continue
            tab = TabLease(tab_id=tab_id, url=state.url, channel=self)
            try:
                self.close_tab(tab)
            except Exception:
                self._drop_tab_state(tab_id)
        browser = self._browser
        playwright = self._playwright
        self._context = None
        self._browser = None
        self._playwright = None
        if browser is not None:
            try:
                browser.close()
            finally:
                if playwright is not None:
                    playwright.stop()
        elif playwright is not None:
            playwright.stop()

    def open_tab(self, url: str) -> TabLease:
        self._allowlist.require_allowed_url(url)
        if self._context is None:
            raise RuntimeError("CDP channel is not attached")
        page = self._context.new_page()
        tab_id = f"cdp-tab-{self._next_tab_index}"
        self._next_tab_index += 1
        self._pages[tab_id] = page
        self._tab_urls[tab_id] = url
        self._request_buffers[tab_id] = []
        self._request_cursors[tab_id] = 0
        self._cdp_requests[tab_id] = {}
        page_listeners = self._install_page_observers(tab_id, page)
        cdp_session = self._install_cdp_observers(tab_id, page)
        self._tab_states[tab_id] = _TabState(page=page, url=url, cdp_session=cdp_session, page_listeners=page_listeners)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return TabLease(tab_id=tab_id, url=url, channel=self)

    def close_tab(self, tab: TabLease) -> None:
        state = self._validate_tab_state(tab)
        if state.cdp_session is not None:
            try:
                state.cdp_session.detach()
            except Exception:
                pass
        for event, handler in state.page_listeners:
            remove_listener = getattr(state.page, "remove_listener", None)
            if callable(remove_listener):
                try:
                    remove_listener(event, handler)
                except Exception:
                    pass
        try:
            state.page.close(run_before_unload=False)
        finally:
            self._drop_tab_state(tab.tab_id)

    def reload(self, tab: TabLease) -> None:
        state = self._validate_tab_state(tab)
        state.page.reload(wait_until="domcontentloaded")

    def wait_for_load_state(self, tab: TabLease, *, timeout_s: float) -> None:
        state = self._validate_tab_state(tab)
        state.page.wait_for_load_state("domcontentloaded", timeout=int(float(timeout_s) * 1000))

    def evaluate(
        self,
        tab: TabLease,
        js: str,
        *,
        arg: JsonValue | None = None,
        timeout_s: float | None = None,
    ) -> JsonValue:
        del timeout_s
        state = self._validate_tab_state(tab)
        if js == "ask_chatgpt_capture_katex_annotations":
            return state.page.evaluate(JS_KATEX_ANNOTATIONS)
        if js == "ask_chatgpt_capture_dom_text":
            return state.page.evaluate(JS_DOM_TEXT)
        if js == "ask_chatgpt_send_read_composer_text":
            return state.page.evaluate(JS_READ_COMPOSER_TEXT, arg)
        if js == "ask_chatgpt_menu_enumerate":
            return state.page.evaluate(JS_MENU_ENUMERATE, arg)
        if js == "ask_chatgpt_menu_click_label":
            return state.page.evaluate(JS_MENU_CLICK_LABEL, arg)
        if js == "ask_chatgpt_current_url":
            return state.page.evaluate(JS_CURRENT_URL)
        return state.page.evaluate(js, arg)

    def wait_for_selector(
        self,
        tab: TabLease,
        selector: str,
        *,
        state: Literal["attached", "visible"] = "visible",
        timeout_s: float,
    ) -> None:
        tab_state = self._validate_tab_state(tab)
        tab_state.page.wait_for_selector(selector, state=state, timeout=int(float(timeout_s) * 1000))

    def fill(self, tab: TabLease, selector: str, text: str) -> None:
        state = self._validate_tab_state(tab)
        state.page.evaluate(JS_FILL_COMPOSER, {"selector": selector, "text": text})

    def insert_text(self, tab: TabLease, selector: str, text: str) -> None:
        state = self._validate_tab_state(tab)
        state.page.evaluate(JS_INSERT_TEXT, {"selector": selector, "text": text})

    def click(self, tab: TabLease, selector: str) -> None:
        state = self._validate_tab_state(tab)
        result = state.page.evaluate(JS_CLICK_VISIBLE_ENABLED, {"selector": selector})
        if not isinstance(result, Mapping) or result.get("ok") is not True:
            raise SelectorNotFoundError("selector had no visible enabled match", details={"selector": selector})

    def hover(self, tab: TabLease, selector: str) -> None:
        state = self._validate_tab_state(tab)
        state.page.hover(selector)

    def press(self, tab: TabLease, selector: str, key: str) -> None:
        state = self._validate_tab_state(tab)
        state.page.press(selector, key)

    def query_turns(self, tab: TabLease, selectors: SelectorMap) -> TurnDomSnapshot:
        state = self._validate_tab_state(tab)
        raw = state.page.evaluate(JS_QUERY_TURNS, dict(selectors))
        if not isinstance(raw, Mapping):
            raw = {}
        return TurnDomSnapshot(
            users=tuple(_turns_from_raw(raw.get("users"), "user")),
            assistants=tuple(_turns_from_raw(raw.get("assistants"), "assistant")),
            stop_visible=bool(raw.get("stop_visible")),
            composer_visible=bool(raw.get("composer_visible")),
            model_labels=_string_tuple(raw.get("model_labels")),
        )

    def wait_for_request(
        self,
        tab: TabLease,
        predicate: Callable[[RequestSnapshot], bool],
        *,
        timeout_s: float,
    ) -> RequestSnapshot:
        state = self._validate_tab_state(tab)
        deadline = self._clock() + max(0.0, float(timeout_s))
        best: RequestSnapshot | None = None
        while True:
            buffer = self._request_buffers.get(tab.tab_id, [])
            index = self._request_cursors.get(tab.tab_id, 0)
            while index < len(buffer):
                observed = buffer[index]
                index += 1
                self._request_cursors[tab.tab_id] = index
                cheap = RequestSnapshot(observed.url, observed.method, _RedactedHeaders())
                if not predicate(cheap):
                    continue
                selected = self._headers_for_observed_request(tab.tab_id, observed)
                snapshot = RequestSnapshot(observed.url, observed.method, _RedactedHeaders(selected))
                missing = set(REQUIRED_CAPTURE_HEADERS) - set(snapshot.headers)
                if not missing:
                    return snapshot
                best = snapshot
                while self._clock() < deadline:
                    selected = self._headers_for_observed_request(tab.tab_id, observed, base=selected)
                    snapshot = RequestSnapshot(observed.url, observed.method, _RedactedHeaders(selected))
                    missing = set(REQUIRED_CAPTURE_HEADERS) - set(snapshot.headers)
                    if not missing:
                        return snapshot
                    best = snapshot
                    self._pump_page_events(state.page, deadline)
                return best
            if self._clock() >= deadline:
                if best is not None:
                    return best
                raise TimeoutError("CDP request predicate did not match")
            self._pump_page_events(state.page, deadline)

    def fetch_in_page(
        self,
        tab: TabLease,
        url: str,
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        body: bytes | str | None = None,
        stream_to: Path | None = None,
        timeout_s: float | None = None,
    ) -> FetchResult:
        absolute = _absolute_fetch_url(tab.url, url)
        self._allowlist.require_allowed_url(absolute)
        state = self._validate_tab_state(tab)
        page = state.page
        if stream_to is not None:
            stream_to.parent.mkdir(parents=True, exist_ok=True)
            stream_id = uuid.uuid4().hex
            binding_name = f"__ask_chatgpt_stream_{stream_id}"
            stream_state = StreamState(stream_id=stream_id)
            binding = None
            with stream_to.open("xb") as out:
                def sink(source: Mapping[str, Any], event: Mapping[str, Any]) -> None:
                    if not isinstance(source, Mapping) or source.get("page") is not page:
                        raise RuntimeError("stream binding called from unexpected page")
                    consume_stream_event(stream_state, event, out.write)

                binding = page.expose_binding(binding_name, sink)
                try:
                    eval_arg = _fetch_eval_arg(
                        url=url,
                        method=method,
                        headers=headers,
                        body=body,
                        timeout_s=timeout_s,
                        binding_name=binding_name,
                        stream_id=stream_id,
                    )
                    try:
                        meta = page.evaluate(JS_STREAM_FETCH, eval_arg)
                    except Exception:
                        raise RuntimeError("CDP in-page stream fetch failed") from None
                finally:
                    close_binding = getattr(binding, "close", None)
                    if callable(close_binding):
                        close_binding()
                    if "eval_arg" in locals():
                        del eval_arg
                out.flush()
            if not stream_state.done:
                raise ValueError("backend stream ended without done marker")
            return FetchResult(_meta_status(meta), _meta_headers(meta), stream_to, None)
        eval_arg = _fetch_eval_arg(url=url, method=method, headers=headers, body=body, timeout_s=timeout_s)
        try:
            try:
                meta = page.evaluate(JS_SMALL_FETCH, eval_arg)
            except Exception:
                raise RuntimeError("CDP in-page fetch failed") from None
        finally:
            del eval_arg
        return FetchResult(_meta_status(meta), _meta_headers(meta), None, _meta_body_bytes(meta))

    def read_clipboard(self, tab: TabLease) -> str:
        del tab
        raise HumanActionNeededError(
            "CDP clipboard read requires human permission",
            details={"reason": "clipboard_permission"},
        )

    def upload_files(self, tab: TabLease, selector: str, paths: Sequence[Path]) -> None:
        state = self._validate_tab_state(tab)
        state.page.set_input_files(selector, [str(path) for path in paths])

    def _start_playwright(self) -> Any:
        if self._playwright_factory is not None:
            return self._playwright_factory()
        from playwright.sync_api import sync_playwright

        return sync_playwright().start()

    def _install_page_observers(self, tab_id: str, page: Any) -> tuple[tuple[str, Callable[..., None]], ...]:
        def on_request(request: Any) -> None:
            self._record_page_request(tab_id, request)

        def on_request_finished(request: Any) -> None:
            self._record_page_request_finished(tab_id, request)

        page.on("request", on_request)
        page.on("requestfinished", on_request_finished)
        return (("request", on_request), ("requestfinished", on_request_finished))

    def _install_cdp_observers(self, tab_id: str, page: Any) -> Any | None:
        if self._context is None:
            return None
        cdp_session = self._context.new_cdp_session(page)

        def on_request_will_be_sent(event: Mapping[str, Any]) -> None:
            self._record_cdp_request(tab_id, event)

        def on_request_extra_info(event: Mapping[str, Any]) -> None:
            self._record_cdp_extra_info(tab_id, event)

        cdp_session.on("Network.requestWillBeSent", on_request_will_be_sent)
        cdp_session.on("Network.requestWillBeSentExtraInfo", on_request_extra_info)
        cdp_session.send("Network.enable")
        return cdp_session

    def _record_page_request(self, tab_id: str, request: Any) -> None:
        if tab_id not in self._request_buffers:
            return
        self._request_buffers[tab_id].append(
            _ObservedRequest(
                url=_request_attr(request, "url"),
                method=_request_attr(request, "method").upper(),
                request=request,
                request_id=_request_id(request),
            )
        )

    def _record_page_request_finished(self, tab_id: str, request: Any) -> None:
        del tab_id, request

    def _record_cdp_request(self, tab_id: str, event: Mapping[str, Any]) -> None:
        request_id = event.get("requestId")
        request = event.get("request")
        if not isinstance(request_id, str) or not isinstance(request, Mapping):
            return
        info = self._cdp_requests.setdefault(tab_id, {}).setdefault(request_id, _CdpRequestInfo())
        url = request.get("url")
        method = request.get("method")
        if isinstance(url, str):
            info.url = url
        if isinstance(method, str):
            info.method = method.upper()

    def _record_cdp_extra_info(self, tab_id: str, event: Mapping[str, Any]) -> None:
        request_id = event.get("requestId")
        headers = event.get("headers")
        if not isinstance(request_id, str) or not isinstance(headers, Mapping):
            return
        info = self._cdp_requests.setdefault(tab_id, {}).setdefault(request_id, _CdpRequestInfo())
        info.headers = _project_required_headers(headers)

    def _headers_for_observed_request(
        self,
        tab_id: str,
        observed: _ObservedRequest,
        *,
        base: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        selected = dict(base or {})
        if base is None:
            all_headers = getattr(observed.request, "all_headers", None)
            if callable(all_headers):
                try:
                    raw = all_headers()
                except Exception:
                    raw = {}
                if isinstance(raw, Mapping):
                    selected.update(_project_required_headers(raw))
                del raw
        selected.update(self._cdp_headers_for_observation(tab_id, observed))
        return selected

    def _cdp_headers_for_observation(self, tab_id: str, observed: _ObservedRequest) -> dict[str, str]:
        cdp_by_id = self._cdp_requests.get(tab_id, {})
        if observed.request_id and observed.request_id in cdp_by_id:
            return dict(cdp_by_id[observed.request_id].headers or {})
        return {}

    def _pump_page_events(self, page: Any, deadline: float) -> None:
        remaining = max(0.0, deadline - self._clock())
        wait_ms = min(50.0, remaining * 1000.0)
        wait_for_timeout = getattr(page, "wait_for_timeout", None)
        if callable(wait_for_timeout):
            wait_for_timeout(wait_ms)
        elif remaining > 0:
            self._sleeper(min(0.05, remaining))

    def _validate_tab_state(self, tab: TabLease) -> _TabState:
        if tab.channel is not self:
            raise ValueError("tab lease belongs to a different channel")
        state = self._tab_states.get(tab.tab_id)
        if state is None:
            raise ValueError(f"unknown or closed CDP tab: {tab.tab_id}")
        return state

    def _drop_tab_state(self, tab_id: str) -> None:
        self._pages.pop(tab_id, None)
        self._tab_urls.pop(tab_id, None)
        self._request_buffers.pop(tab_id, None)
        self._request_cursors.pop(tab_id, None)
        self._cdp_requests.pop(tab_id, None)
        self._tab_states.pop(tab_id, None)


__all__ = [
    "CdpChannel",
    "StreamState",
    "append_decoded_stream_chunk",
    "consume_stream_event",
    "decode_stream_chunk_base64",
]
