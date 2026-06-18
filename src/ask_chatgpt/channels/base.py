"""Browser channel protocol seam for offline-first testing."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from ask_chatgpt.models import JsonValue, PreflightResult, SelectorMap


@dataclass(frozen=True)
class TabLease:
    tab_id: str
    url: str
    channel: BrowserChannel


@dataclass(frozen=True)
class TurnDom:
    message_id: str
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class TurnDomSnapshot:
    users: tuple[TurnDom, ...]
    assistants: tuple[TurnDom, ...]
    stop_visible: bool
    composer_visible: bool
    model_labels: tuple[str, ...]


@dataclass(frozen=True)
class RequestSnapshot:
    url: str
    method: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class FetchResult:
    status: int
    headers: Mapping[str, str]
    body_path: Path | None
    body_bytes: bytes | None


class BrowserChannel(Protocol):
    def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult: ...
    def attach(self) -> None: ...
    def detach(self) -> None: ...
    def open_tab(self, url: str) -> TabLease: ...
    def close_tab(self, tab: TabLease) -> None: ...
    def reload(self, tab: TabLease) -> None: ...
    def wait_for_load_state(self, tab: TabLease, *, timeout_s: float) -> None: ...
    def evaluate(
        self,
        tab: TabLease,
        js: str,
        *,
        arg: JsonValue | None = None,
        timeout_s: float | None = None,
    ) -> JsonValue: ...
    def wait_for_selector(
        self,
        tab: TabLease,
        selector: str,
        *,
        state: Literal["attached", "visible"] = "visible",
        timeout_s: float,
    ) -> None: ...
    def fill(self, tab: TabLease, selector: str, text: str) -> None: ...
    def insert_text(self, tab: TabLease, selector: str, text: str) -> None: ...
    def click(self, tab: TabLease, selector: str) -> None: ...
    def hover(self, tab: TabLease, selector: str) -> None: ...
    def press(self, tab: TabLease, selector: str, key: str) -> None: ...
    def query_turns(self, tab: TabLease, selectors: SelectorMap) -> TurnDomSnapshot: ...
    def wait_for_request(
        self,
        tab: TabLease,
        predicate: Callable[[RequestSnapshot], bool],
        *,
        timeout_s: float,
    ) -> RequestSnapshot: ...
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
    ) -> FetchResult: ...
    def read_clipboard(self, tab: TabLease) -> str: ...
    def upload_files(self, tab: TabLease, selector: str, paths: Sequence[Path]) -> None: ...


__all__ = [
    "BrowserChannel",
    "FetchResult",
    "RequestSnapshot",
    "TabLease",
    "TurnDom",
    "TurnDomSnapshot",
]
