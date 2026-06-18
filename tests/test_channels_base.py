from __future__ import annotations

import inspect
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from ask_chatgpt import Session
from ask_chatgpt.channels.base import (
    BrowserChannel,
    FetchResult,
    RequestSnapshot,
    TabLease,
    TurnDom,
    TurnDomSnapshot,
)
from ask_chatgpt.models import PreflightResult


class DummyChannel:
    def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult:
        return PreflightResult(True, "mock", None, None, False)

    def attach(self) -> None: ...
    def detach(self) -> None: ...
    def open_tab(self, url: str) -> TabLease:
        return TabLease(tab_id="tab-1", url=url, channel=self)

    def close_tab(self, tab: TabLease) -> None: ...
    def reload(self, tab: TabLease) -> None: ...
    def wait_for_load_state(self, tab: TabLease, *, timeout_s: float) -> None: ...
    def evaluate(self, tab: TabLease, js: str, *, arg: Any = None, timeout_s: float | None = None) -> Any:
        return arg

    def wait_for_selector(self, tab: TabLease, selector: str, *, state: str = "visible", timeout_s: float) -> None: ...
    def fill(self, tab: TabLease, selector: str, text: str) -> None: ...
    def insert_text(self, tab: TabLease, selector: str, text: str) -> None: ...
    def click(self, tab: TabLease, selector: str) -> None: ...
    def hover(self, tab: TabLease, selector: str) -> None: ...
    def press(self, tab: TabLease, selector: str, key: str) -> None: ...
    def query_turns(self, tab: TabLease, selectors: dict[str, str]) -> TurnDomSnapshot:
        return TurnDomSnapshot(
            users=(TurnDom("u1", "user", "hello"),),
            assistants=(TurnDom("a1", "assistant", "hi"),),
            stop_visible=False,
            composer_visible=True,
            model_labels=("GPT-4o",),
        )

    def wait_for_request(self, tab: TabLease, predicate: Any, *, timeout_s: float) -> RequestSnapshot:
        return RequestSnapshot("https://chatgpt.com/backend-api/conversation/chat_123", "GET", {})

    def fetch_in_page(self, tab: TabLease, url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: bytes | str | None = None, stream_to: Path | None = None, timeout_s: float | None = None) -> FetchResult:
        return FetchResult(200, {"content-type": "application/json"}, None, b"{}")

    def read_clipboard(self, tab: TabLease) -> str:
        return ""

    def upload_files(self, tab: TabLease, selector: str, paths: list[Path]) -> None: ...


def test_channel_dataclasses_preserve_browser_seam_values() -> None:
    channel: BrowserChannel = DummyChannel()
    tab = channel.open_tab("https://chatgpt.com/c/chat_123")
    snapshot = channel.query_turns(tab, selectors={})  # type: ignore[arg-type]
    request = channel.wait_for_request(tab, lambda req: True, timeout_s=1.0)
    result = channel.fetch_in_page(tab, request.url)

    assert tab == TabLease("tab-1", "https://chatgpt.com/c/chat_123", channel)
    assert snapshot.users == (TurnDom("u1", "user", "hello"),)
    assert snapshot.assistants[0].role == "assistant"
    assert request.method == "GET"
    assert result.status == 200
    assert result.body_bytes == b"{}"

    with pytest.raises(FrozenInstanceError):
        tab.url = "https://evil.example"  # type: ignore[misc]


def test_browser_channel_protocol_exposes_required_methods() -> None:
    method_names = {
        name for name, value in inspect.getmembers(BrowserChannel) if inspect.isfunction(value)
    }

    assert {
        "preflight",
        "attach",
        "detach",
        "open_tab",
        "close_tab",
        "reload",
        "wait_for_load_state",
        "evaluate",
        "wait_for_selector",
        "fill",
        "insert_text",
        "click",
        "hover",
        "press",
        "query_turns",
        "wait_for_request",
        "fetch_in_page",
        "read_clipboard",
        "upload_files",
    } <= method_names


def test_importing_public_api_and_session_stub_is_offline_and_not_implemented() -> None:
    session = Session(channel="mock")

    assert not any(name == "playwright" or name.startswith("playwright.") for name in sys.modules)
    with pytest.raises(NotImplementedError):
        session.ask(None, "hello")
