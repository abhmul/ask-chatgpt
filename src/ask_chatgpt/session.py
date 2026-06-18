"""Minimal public Session facade for the offline-core scaffold."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Literal

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import AttachmentSpec, StatusReport, Transcript, TurnRecord


class Session:
    def __init__(
        self,
        *,
        cdp_endpoint: str = "http://127.0.0.1:9222",
        data_dir: str | Path | None = None,
        channel: Literal["mock", "cdp"] = "cdp",
        selector_map: str | Path | Mapping[str, str] | None = None,
        max_active_tab_ops: int = 3,
        max_tabs: int = 3,
        activity_timeout_s: float = 600.0,
        max_total_wait_s: float | None = None,
        send_verify_timeout_s: float = 30.0,
        composer_wait_timeout_s: float = 20.0,
        progress_poll_interval_s: float = 2.0,
        backend_check_interval_s: float | None = None,
        strict_selectors: bool = True,
    ) -> None:
        self.cdp_endpoint = cdp_endpoint
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self.channel = channel
        self.selector_map = selector_map
        self.max_active_tab_ops = max_active_tab_ops
        self.max_tabs = max_tabs
        self.activity_timeout_s = activity_timeout_s
        self.max_total_wait_s = max_total_wait_s
        self.send_verify_timeout_s = send_verify_timeout_s
        self.composer_wait_timeout_s = composer_wait_timeout_s
        self.progress_poll_interval_s = progress_poll_interval_s
        self.backend_check_interval_s = backend_check_interval_s
        self.strict_selectors = strict_selectors

    def _not_implemented(self, method: str) -> None:
        raise NotImplementedError(f"Session.{method}: implemented in later M4 steps")

    def attach(self) -> "Session":
        self._not_implemented("attach")

    def detach(self, *, close_managed_tabs: bool = True) -> None:
        self._not_implemented("detach")

    def __enter__(self) -> "Session":
        self._not_implemented("__enter__")

    def __exit__(
        self, exc_type: object, exc: BaseException | None, tb: object
    ) -> None:
        self._not_implemented("__exit__")

    def create(self, project: str | None = None) -> ConversationRef:
        self._not_implemented("create")

    def ask(
        self,
        conv_or_url: str | ConversationRef | None,
        prompt: str,
        *,
        model: str | None = None,
        tools: Sequence[str] = (),
        attach: Sequence[str | Path | AttachmentSpec] = (),
        timeout: float | None = None,
        max_total_wait: float | None = None,
        out: str | Path | None = None,
    ) -> TurnRecord:
        self._not_implemented("ask")

    def scrape(
        self,
        conv_or_url: str | ConversationRef,
        *,
        with_attachments: bool = False,
        out: str | Path | None = None,
    ) -> Transcript:
        self._not_implemented("scrape")

    def history(self, conv_or_url: str | ConversationRef) -> Transcript:
        self._not_implemented("history")

    def fetch(self, conv_or_url: str | ConversationRef, attachment_ref: str) -> Path:
        self._not_implemented("fetch")

    def loop(
        self,
        conv_or_url: str | ConversationRef,
        *,
        message: str = "keep pushing!!",
        model: str | None = None,
        tools: Sequence[str] = (),
        attach: Sequence[str | Path | AttachmentSpec] = (),
        timeout: float | None = None,
        max_total_wait: float | None = None,
        max_iterations: int | None = None,
        out_dir: str | Path | None = None,
    ) -> Iterator[TurnRecord]:
        self._not_implemented("loop")

    def status(
        self,
        conv_or_url: str | ConversationRef | None = None,
        *,
        probe_browser: bool = True,
    ) -> StatusReport:
        self._not_implemented("status")


__all__ = ["Session"]
