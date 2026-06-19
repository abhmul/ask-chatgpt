"""Deterministic offline ``BrowserChannel`` implementation for M4 tests.

This module is intentionally browser-free: it does not import Playwright, open a
browser, use CDP, or perform network I/O. It only returns scripted data from a
plain ``MockScenario`` object.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from ask_chatgpt.allowlist import Allowlist
from ask_chatgpt.channels.base import (
    FetchResult,
    RequestSnapshot,
    TabLease,
    TurnDomSnapshot,
)
from ask_chatgpt.errors import HumanActionNeededError, SelectorNotFoundError
from ask_chatgpt.models import JsonValue, PreflightResult, SelectorMap

REQUIRED_BACKEND_HEADERS: tuple[str, ...] = (
    "authorization",
    "oai-client-build-number",
    "oai-client-version",
    "oai-device-id",
    "oai-language",
    "oai-session-id",
    "x-openai-target-path",
    "x-openai-target-route",
)

HEADER_CANARIES: dict[str, str] = {
    "authorization": "Bearer MOCK_HEADER_CANARY_AUTHORIZATION_DO_NOT_PERSIST_000",
    "oai-client-build-number": "MOCK_HEADER_CANARY_BUILD_DO_NOT_PERSIST_001",
    "oai-client-version": "MOCK_HEADER_CANARY_VERSION_DO_NOT_PERSIST_002",
    "oai-device-id": "MOCK_HEADER_CANARY_DEVICE_DO_NOT_PERSIST_003",
    "oai-language": "MOCK_HEADER_CANARY_LANGUAGE_DO_NOT_PERSIST_004",
    "oai-session-id": "MOCK_HEADER_CANARY_SESSION_DO_NOT_PERSIST_005",
    "x-openai-target-path": "MOCK_HEADER_CANARY_TARGET_PATH_DO_NOT_PERSIST_006",
    "x-openai-target-route": "MOCK_HEADER_CANARY_TARGET_ROUTE_DO_NOT_PERSIST_007",
}


def _empty_turn_snapshot() -> TurnDomSnapshot:
    return TurnDomSnapshot(
        users=(),
        assistants=(),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )


@dataclass(frozen=True)
class MockCall:
    """A redacted record of one channel method call."""

    method: str
    tab_id: str | None = None
    details: Mapping[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class MockBackendResponse:
    status: int
    body: JsonValue | bytes | str
    headers: Mapping[str, str] = field(
        default_factory=lambda: {"content-type": "application/json"}
    )

    def body_as_bytes(self) -> bytes:
        if isinstance(self.body, bytes):
            return self.body
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return json.dumps(self.body, ensure_ascii=False, sort_keys=True).encode("utf-8")


@dataclass(frozen=True)
class TimedTurnSnapshot:
    at_s: float
    snapshot: TurnDomSnapshot


@dataclass(frozen=True)
class TimedBackendResponse:
    at_s: float
    response: MockBackendResponse


@dataclass(frozen=True)
class TimedSelectorPresence:
    at_s: float
    present: bool


@dataclass(frozen=True)
class MockScenario:
    """Plain-data script consumed by ``MockChannel``."""

    name: str = "default"
    backend_conversations: Mapping[str, JsonValue] = field(default_factory=dict)
    backend_responses: Mapping[str, MockBackendResponse] = field(default_factory=dict)
    file_downloads: Mapping[str, MockBackendResponse] = field(default_factory=dict)
    download_responses: Mapping[str, MockBackendResponse] = field(default_factory=dict)
    backend_timeline: tuple[TimedBackendResponse, ...] = ()
    turn_timeline: tuple[TimedTurnSnapshot, ...] = ()
    request_snapshots: tuple[RequestSnapshot, ...] = ()
    selector_presence: Mapping[str, bool] = field(default_factory=dict)
    selector_timeline: Mapping[str, tuple[TimedSelectorPresence, ...]] = field(default_factory=dict)
    evaluations: Mapping[str, JsonValue] = field(default_factory=dict)
    clipboard_permission: Literal["prompt", "granted", "denied"] = "prompt"
    clipboard_text: str | None = None
    login_wall: bool = False
    challenge: bool = False
    header_canaries: Mapping[str, str] = field(
        default_factory=lambda: dict(HEADER_CANARIES)
    )
    one_use_headers: bool = False
    status_fixture: Mapping[str, JsonValue] | None = None
    fill_behavior: Literal["normal", "ignored", "truncated"] = "normal"
    fill_truncate_to: int | None = None
    disabled_click_selectors: tuple[str, ...] = ()
    disallow_global_enter: bool = False
    private_page_canary: str = "MOCK_PRIVATE_PAGE_CANARY_DO_NOT_LEAK"


class ScriptedClock:
    """Small fake monotonic clock/sleeper for offline timeout tests."""

    def __init__(self, start_s: float = 0.0) -> None:
        self._now_s = float(start_s)
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self._now_s

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(float(seconds))
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot move the scripted clock backwards")
        self._now_s += float(seconds)


class _ForbiddenBrowserProxy:
    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attr: str) -> object:
        raise AttributeError(f"MockChannel exposes no {self._name}.{attr} browser internals")


class _MockContext:
    def __init__(self, private_page_canary: str) -> None:
        self._private_page_canary = private_page_canary

    @property
    def pages(self) -> object:
        _ = self._private_page_canary
        raise RuntimeError("MockChannel forbids context.pages enumeration")

    def __iter__(self) -> object:
        raise RuntimeError("MockChannel forbids browser-context enumeration")

    def __getattr__(self, attr: str) -> object:
        raise AttributeError(f"MockChannel exposes no context.{attr} browser internals")


class MockChannel:
    """Scripted offline implementation of the ``BrowserChannel`` Protocol."""

    def __init__(
        self,
        scenario: MockScenario | None = None,
        *,
        monotonic: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        allowlist: Allowlist | None = None,
    ) -> None:
        self.scenario = scenario or MockScenario()
        self._monotonic = monotonic or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._allowlist = allowlist or Allowlist()
        self.context = _MockContext(self.scenario.private_page_canary)
        self.browser = _ForbiddenBrowserProxy("browser")
        self.page = _ForbiddenBrowserProxy("page")
        self.calls: list[MockCall] = []
        self.counters: Counter[str] = Counter()
        self._attached = False
        self._next_tab_index = 1
        self._tabs: dict[str, str] = {}
        self._composer_text: dict[str, str] = {}
        self._request_index = 0
        self._used_header_fingerprints: set[str] = set()

    @property
    def call_order(self) -> tuple[str, ...]:
        return tuple(call.method for call in self.calls)

    @property
    def method_counts(self) -> Mapping[str, int]:
        return dict(self.counters)

    def monotonic(self) -> float:
        return self._monotonic()

    def sleep(self, seconds: float) -> None:
        self._sleeper(seconds)

    def composer_text(self, tab: TabLease) -> str:
        self._validate_tab(tab)
        return self._composer_text.get(tab.tab_id, "")

    def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult:
        self._record("preflight", timeout_s=timeout_s)
        if self.scenario.login_wall or self.scenario.challenge:
            return PreflightResult(
                ok=False,
                cdp_endpoint="mock",
                browser=None,
                protocol_version=None,
                websocket_url_present=False,
                error_code="HUMAN-ACTION-NEEDED",
                error="login_or_challenge",
            )
        return PreflightResult(
            ok=True,
            cdp_endpoint="mock",
            browser="MockChannel",
            protocol_version=None,
            websocket_url_present=False,
        )

    def attach(self) -> None:
        self._attached = True
        self._record("attach")

    def detach(self) -> None:
        self._attached = False
        self._record("detach")

    def open_tab(self, url: str) -> TabLease:
        self._require_allowed_navigation(url)
        self._raise_if_human_blocked()
        tab_id = f"mock-tab-{self._next_tab_index}"
        self._next_tab_index += 1
        self._tabs[tab_id] = url
        self._composer_text[tab_id] = ""
        tab = TabLease(tab_id=tab_id, url=url, channel=self)
        self._record("open_tab", tab=tab, url=self._safe_url(url))
        return tab

    def close_tab(self, tab: TabLease) -> None:
        self._validate_tab(tab)
        self._tabs.pop(tab.tab_id, None)
        self._composer_text.pop(tab.tab_id, None)
        self._record("close_tab", tab=tab)

    def reload(self, tab: TabLease) -> None:
        self._validate_tab(tab)
        self._raise_if_human_blocked()
        self._record("reload", tab=tab)

    def wait_for_load_state(self, tab: TabLease, *, timeout_s: float) -> None:
        self._validate_tab(tab)
        self._record("wait_for_load_state", tab=tab, timeout_s=timeout_s)

    def evaluate(
        self,
        tab: TabLease,
        js: str,
        *,
        arg: JsonValue | None = None,
        timeout_s: float | None = None,
    ) -> JsonValue:
        self._validate_tab(tab)
        self._record(
            "evaluate",
            tab=tab,
            js_hash=self._hash_text(js),
            has_arg=arg is not None,
            timeout_s=timeout_s,
        )
        if js == "ask_chatgpt_send_read_composer_text":
            return self._composer_text.get(tab.tab_id, "")
        if js in self.scenario.evaluations:
            return self.scenario.evaluations[js]
        return arg

    def wait_for_selector(
        self,
        tab: TabLease,
        selector: str,
        *,
        state: Literal["attached", "visible"] = "visible",
        timeout_s: float,
    ) -> None:
        self._validate_tab(tab)
        self._record(
            "wait_for_selector",
            tab=tab,
            selector=selector,
            state=state,
            timeout_s=timeout_s,
        )
        if not self._selector_present(selector):
            raise SelectorNotFoundError(
                "mock selector is not present",
                details={"selector": selector, "state": state},
            )

    def fill(self, tab: TabLease, selector: str, text: str) -> None:
        self._validate_tab(tab)
        self._record("fill", tab=tab, selector=selector, text_len=len(text))
        self._apply_fill(tab, text, append=False)

    def insert_text(self, tab: TabLease, selector: str, text: str) -> None:
        self._validate_tab(tab)
        self._record("insert_text", tab=tab, selector=selector, text_len=len(text))
        self._apply_fill(tab, text, append=True)

    def click(self, tab: TabLease, selector: str) -> None:
        self._validate_tab(tab)
        self._record("click", tab=tab, selector=selector)
        if selector in self.scenario.disabled_click_selectors:
            raise RuntimeError(f"mock selector is disabled: {selector}")

    def hover(self, tab: TabLease, selector: str) -> None:
        self._validate_tab(tab)
        self._record("hover", tab=tab, selector=selector)

    def press(self, tab: TabLease, selector: str, key: str) -> None:
        self._validate_tab(tab)
        self._record("press", tab=tab, selector=selector, key=key)
        if self.scenario.disallow_global_enter and key == "Enter" and selector in {"body", "html", "document"}:
            raise RuntimeError("mock forbids global Enter submission")

    def query_turns(self, tab: TabLease, selectors: SelectorMap) -> TurnDomSnapshot:
        self._validate_tab(tab)
        self._record("query_turns", tab=tab, selector_keys=tuple(sorted(selectors.keys())))
        self.counters["dom_polls"] += 1
        return self._current_turn_snapshot()

    def wait_for_request(
        self,
        tab: TabLease,
        predicate: Callable[[RequestSnapshot], bool],
        *,
        timeout_s: float,
    ) -> RequestSnapshot:
        self._validate_tab(tab)
        self._record("wait_for_request", tab=tab, timeout_s=timeout_s)
        self.counters["header_acquisitions"] += 1
        for index in range(self._request_index, len(self.scenario.request_snapshots)):
            request = self.scenario.request_snapshots[index]
            if predicate(request):
                self._request_index = index + 1
                return request
        raise TimeoutError("mock wait_for_request predicate did not match")

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
        self._validate_tab(tab)
        self._require_allowed_fetch(url)
        response = self._scripted_fetch_response(url, headers or {})
        self._record(
            "fetch_in_page",
            tab=tab,
            url=self._safe_url(url),
            http_method=method,
            header_names=tuple(sorted(self._lower_headers(headers or {}).keys())),
            has_body=body is not None,
            streamed=stream_to is not None,
            timeout_s=timeout_s,
        )
        self._count_backend_fetch_kind(url)
        body_bytes = response.body_as_bytes()
        if stream_to is not None:
            stream_to.parent.mkdir(parents=True, exist_ok=True)
            stream_to.write_bytes(body_bytes)
            return FetchResult(response.status, dict(response.headers), stream_to, None)
        return FetchResult(response.status, dict(response.headers), None, body_bytes)

    def read_clipboard(self, tab: TabLease) -> str:
        self._validate_tab(tab)
        self._record("read_clipboard", tab=tab)
        if self.scenario.clipboard_permission != "granted" or self.scenario.clipboard_text is None:
            raise HumanActionNeededError(
                "clipboard read blocked by mock permission state",
                details={"reason": "clipboard_permission", "permission": self.scenario.clipboard_permission},
            )
        return self.scenario.clipboard_text

    def upload_files(self, tab: TabLease, selector: str, paths: Sequence[Path]) -> None:
        self._validate_tab(tab)
        self._record("upload_files", tab=tab, selector=selector, file_count=len(paths))

    def _record(self, method: str, tab: TabLease | None = None, **details: Any) -> None:
        self.counters[method] += 1
        sanitized = {key: self._json_safe(value) for key, value in details.items()}
        self.calls.append(MockCall(method=method, tab_id=tab.tab_id if tab else None, details=sanitized))

    def _validate_tab(self, tab: TabLease) -> None:
        if tab.channel is not self:
            raise ValueError("tab lease belongs to a different channel")
        if tab.tab_id not in self._tabs:
            raise ValueError(f"unknown or closed mock tab: {tab.tab_id}")

    def _require_allowed_navigation(self, url: str) -> None:
        self._allowlist.require_allowed_url(url)

    def _require_allowed_fetch(self, url: str) -> None:
        if url.startswith("/") and not url.startswith("//"):
            return
        self._allowlist.require_allowed_url(url)

    def _raise_if_human_blocked(self) -> None:
        if self.scenario.login_wall or self.scenario.challenge:
            raise HumanActionNeededError(
                "mock scenario is blocked by login or challenge",
                details={"login_wall": self.scenario.login_wall, "challenge": self.scenario.challenge},
            )

    def _safe_url(self, url: str) -> str:
        if url.startswith("/") and not url.startswith("//"):
            return url
        return self._allowlist.sanitize_for_log(url)

    def _selector_present(self, selector: str) -> bool:
        if selector in self.scenario.selector_timeline:
            return bool(self._select_timed(self.scenario.selector_timeline[selector]).present)
        return self.scenario.selector_presence.get(selector, True)

    def _apply_fill(self, tab: TabLease, text: str, *, append: bool) -> None:
        if self.scenario.fill_behavior == "ignored":
            return
        incoming = text
        if self.scenario.fill_behavior == "truncated":
            limit = self.scenario.fill_truncate_to if self.scenario.fill_truncate_to is not None else max(0, len(text) - 1)
            incoming = text[:limit]
        current = self._composer_text.get(tab.tab_id, "") if append else ""
        self._composer_text[tab.tab_id] = f"{current}{incoming}"

    def _current_turn_snapshot(self) -> TurnDomSnapshot:
        if not self.scenario.turn_timeline:
            return _empty_turn_snapshot()
        return self._select_timed(self.scenario.turn_timeline).snapshot

    def _scripted_fetch_response(
        self, url: str, headers: Mapping[str, str]
    ) -> MockBackendResponse:
        if url in self.scenario.download_responses:
            return self.scenario.download_responses[url]
        file_id = self._backend_file_download_id(url)
        if file_id is not None:
            lower_headers = self._lower_headers(headers)
            missing = set(REQUIRED_BACKEND_HEADERS) - set(lower_headers)
            if missing:
                return MockBackendResponse(
                    404,
                    {
                        "detail": "required backend authorization/OAI headers were not present",
                        "missing_headers": sorted(missing),
                    },
                )
            self._check_one_use_headers(lower_headers)
            if file_id in self.scenario.file_downloads:
                return self.scenario.file_downloads[file_id]
            if url in self.scenario.backend_responses:
                return self.scenario.backend_responses[url]
            return MockBackendResponse(404, {"detail": "file fixture not found"})
        conversation_id = self._backend_conversation_id(url)
        if conversation_id is None:
            if url in self.scenario.backend_responses:
                return self.scenario.backend_responses[url]
            return MockBackendResponse(404, {"detail": "mock route not found"})
        lower_headers = self._lower_headers(headers)
        if not set(REQUIRED_BACKEND_HEADERS).issubset(lower_headers):
            return MockBackendResponse(
                404,
                {
                    "detail": "required backend authorization/OAI headers were not present",
                    "missing_headers": sorted(set(REQUIRED_BACKEND_HEADERS) - set(lower_headers)),
                },
            )
        self._check_one_use_headers(lower_headers)
        if url in self.scenario.backend_responses:
            return self.scenario.backend_responses[url]
        if self.scenario.backend_timeline:
            return self._select_timed(self.scenario.backend_timeline).response
        if conversation_id not in self.scenario.backend_conversations:
            return MockBackendResponse(404, {"detail": "conversation fixture not found"})
        return MockBackendResponse(200, self.scenario.backend_conversations[conversation_id])

    def _check_one_use_headers(self, lower_headers: Mapping[str, str]) -> None:
        if not self.scenario.one_use_headers:
            return
        fingerprint_payload = json.dumps(
            {name: lower_headers.get(name, "") for name in REQUIRED_BACKEND_HEADERS},
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
        if fingerprint in self._used_header_fingerprints:
            raise RuntimeError("mock one-use backend header canaries were reused")
        self._used_header_fingerprints.add(fingerprint)

    def _count_backend_fetch_kind(self, url: str) -> None:
        path = urlsplit(url).path
        self.counters["backend_fetches"] += 1
        if path.endswith("/stream_status"):
            self.counters["backend_checks"] += 1
        elif self._backend_file_download_id(url) is not None:
            self.counters["attachment_descriptor_fetches"] += 1
        elif url in self.scenario.download_responses:
            self.counters["attachment_byte_fetches"] += 1
        elif self._backend_conversation_id(url) is not None:
            self.counters["full_raw_fetches"] += 1

    def _backend_conversation_id(self, url: str) -> str | None:
        path = urlsplit(url).path
        marker = "/backend-api/conversation/"
        if marker not in path:
            return None
        suffix = path.split(marker, 1)[1]
        conversation_id = suffix.split("/", 1)[0]
        return conversation_id or None

    def _backend_file_download_id(self, url: str) -> str | None:
        path = urlsplit(url).path
        marker = "/backend-api/files/"
        suffix_marker = "/download"
        if marker not in path or not path.endswith(suffix_marker):
            return None
        suffix = path.split(marker, 1)[1]
        encoded_file_id = suffix[: -len(suffix_marker)]
        return unquote(encoded_file_id) if encoded_file_id else None

    def _select_timed(self, steps: Sequence[Any]) -> Any:
        now = self.monotonic()
        selected = steps[0]
        for step in sorted(steps, key=lambda item: item.at_s):
            if step.at_s <= now:
                selected = step
            else:
                break
        return selected

    @staticmethod
    def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_safe(value: Any) -> JsonValue:
        if value is None or isinstance(value, bool | int | float | str):
            return value
        if isinstance(value, tuple | list):
            return [MockChannel._json_safe(item) for item in value]
        if isinstance(value, Mapping):
            return {str(key): MockChannel._json_safe(item) for key, item in value.items()}
        if isinstance(value, Path):
            return str(value)
        return repr(value)


__all__ = [
    "HEADER_CANARIES",
    "MockBackendResponse",
    "MockCall",
    "MockChannel",
    "MockScenario",
    "REQUIRED_BACKEND_HEADERS",
    "ScriptedClock",
    "TimedBackendResponse",
    "TimedSelectorPresence",
    "TimedTurnSnapshot",
]
