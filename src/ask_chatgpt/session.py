"""Minimal public Session facade for the M4 offline-core spine."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Literal

from ask_chatgpt.capture import SendContext, capture_conversation
from ask_chatgpt.channels.base import BrowserChannel, TabLease
from ask_chatgpt.completion import salvage_partial, wait_for_completion
from ask_chatgpt.errors import (
    AskChatGPTError,
    CompletionTimeoutError,
    InternalError,
    MaxTotalWaitExceededError,
)
from ask_chatgpt.identity import ConversationRef, conversation_url
from ask_chatgpt.menus import assert_reflected_model, assert_reflected_tools
from ask_chatgpt.models import (
    AttachmentSpec,
    ModelRef,
    SendTimeouts,
    StatusReport,
    Transcript,
    TurnRecord,
)
from ask_chatgpt.selectors import load_selector_map
from ask_chatgpt.send import (
    SubmittedTurn,
    fill_composer,
    read_turn_baseline,
    submit_composer,
    upload_attachments,
    verify_prompt_submitted,
    wait_for_composer,
    wait_for_idle_and_reload_if_needed,
)
from ask_chatgpt.store import Store


class Session:
    def __init__(
        self,
        *,
        cdp_endpoint: str = "http://127.0.0.1:9222",
        data_dir: str | Path | None = None,
        channel: Literal["mock", "cdp"] | BrowserChannel = "cdp",
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
        self.store = Store(data_dir=self.data_dir)
        self._channel_arg = channel
        self._browser_channel: BrowserChannel | None = channel if not isinstance(channel, str) else None
        self.selector_map = load_selector_map(selector_map or "real", strict=strict_selectors)
        self.max_active_tab_ops = max_active_tab_ops
        self.max_tabs = max_tabs
        self.activity_timeout_s = activity_timeout_s
        self.max_total_wait_s = max_total_wait_s
        self.send_verify_timeout_s = send_verify_timeout_s
        self.composer_wait_timeout_s = composer_wait_timeout_s
        self.progress_poll_interval_s = progress_poll_interval_s
        self.backend_check_interval_s = backend_check_interval_s
        self.strict_selectors = strict_selectors
        self._attached = False

    def _not_implemented(self, method: str) -> None:
        raise NotImplementedError(f"Session.{method}: implemented in later M4 steps")

    def _channel(self) -> BrowserChannel:
        if self._browser_channel is not None:
            return self._browser_channel
        if self._channel_arg == "mock":
            from ask_chatgpt.channels.mock import MockChannel

            self._browser_channel = MockChannel()
            return self._browser_channel
        raise NotImplementedError("Session CDP channel is deferred beyond M4 offline core")

    def attach(self) -> "Session":
        if not self._attached:
            self._channel().attach()
            self._attached = True
        return self

    def detach(self, *, close_managed_tabs: bool = True) -> None:
        del close_managed_tabs
        if self._attached:
            self._channel().detach()
            self._attached = False

    def __enter__(self) -> "Session":
        return self.attach()

    def __exit__(
        self, exc_type: object, exc: BaseException | None, tb: object
    ) -> None:
        self.detach()

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
        if conv_or_url is None:
            raise NotImplementedError("draft conversation sends are deferred beyond M4")
        ref = self.store.resolve_conversation(conv_or_url) if not isinstance(conv_or_url, ConversationRef) else conv_or_url
        self.store.put_conversation_ref(ref)
        channel = self._channel()
        self.attach()
        tab = channel.open_tab(conversation_url(ref))
        stub: TurnRecord | None = None
        submitted: SubmittedTurn | None = None
        model_ref = ModelRef(None, model) if model is not None else None
        active_tools = tuple(tools)
        try:
            wait_for_idle_and_reload_if_needed(tab, self.selector_map, timeout_s=self.composer_wait_timeout_s)
            if model is not None:
                assert_reflected_model(tab, self.selector_map, model)
            if active_tools:
                assert_reflected_tools(tab, self.selector_map, active_tools)
            baseline = read_turn_baseline(tab, self.selector_map)
            stub = self.store.begin_send(ref, prompt, model=model_ref, active_tools=active_tools)
            wait_for_composer(tab, self.selector_map, timeout_s=self.composer_wait_timeout_s)
            upload_attachments(tab, self.selector_map, _attachment_specs(attach))
            fill_composer(tab, self.selector_map, prompt)
            submit_composer(tab, self.selector_map)
            submitted = verify_prompt_submitted(
                tab,
                self.selector_map,
                baseline,
                prompt,
                timeout_s=self.send_verify_timeout_s,
            )
            canonical_user = _canonical_user_record(ref, submitted, stub, model_ref, active_tools)
            self.store.commit_send(stub.client_send_id or "", canonical_user)
            try:
                completion_state = wait_for_completion(
                    tab,
                    ref,
                    self.selector_map,
                    baseline,
                    activity_timeout_s=timeout if timeout is not None else self.activity_timeout_s,
                    max_total_wait_s=max_total_wait if max_total_wait is not None else self.max_total_wait_s,
                    progress_poll_interval_s=self.progress_poll_interval_s,
                    backend_check_interval_s=self.backend_check_interval_s,
                )
                capture = capture_conversation(
                    tab,
                    ref,
                    self.store,
                    send_context=SendContext(
                        client_send_id=stub.client_send_id,
                        user_message_id=submitted.user_message_id,
                        model=model_ref,
                        active_tools=active_tools,
                    ),
                )
                answer = _select_new_assistant(capture.transcript.turns, completion_state.assistant_message_id, baseline)
            except (CompletionTimeoutError, MaxTotalWaitExceededError, AskChatGPTError) as exc:
                self._record_partial_if_available(tab, ref, baseline, stub, submitted, exc)
                raise
            if out is not None:
                self.store.emit_payload(answer.content_markdown + "\n", out=out, stdout=_NullStdout())
            return answer
        finally:
            channel.close_tab(tab)

    def scrape(
        self,
        conv_or_url: str | ConversationRef,
        *,
        with_attachments: bool = False,
        out: str | Path | None = None,
    ) -> Transcript:
        ref = self.store.resolve_conversation(conv_or_url) if not isinstance(conv_or_url, ConversationRef) else conv_or_url
        self.store.put_conversation_ref(ref)
        channel = self._channel()
        self.attach()
        tab = channel.open_tab(conversation_url(ref))
        try:
            captured = capture_conversation(tab, ref, self.store, with_attachments=with_attachments)
            transcript = self.store.load_transcript(ref)
            if out is not None:
                self.store.emit_payload(self.store.render_markdown(transcript), out=out, stdout=_NullStdout())
            return transcript if transcript.turns else captured.transcript
        finally:
            channel.close_tab(tab)

    def history(self, conv_or_url: str | ConversationRef) -> Transcript:
        return self.store.load_transcript(conv_or_url)

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
        yield from ()

    def status(
        self,
        conv_or_url: str | ConversationRef | None = None,
        *,
        probe_browser: bool = True,
    ) -> StatusReport:
        self._not_implemented("status")

    def _record_partial_if_available(
        self,
        tab: TabLease,
        ref: ConversationRef,
        baseline: object,
        stub: TurnRecord | None,
        submitted: SubmittedTurn | None,
        error: BaseException,
    ) -> None:
        if stub is None:
            return
        backend_partial = getattr(error, "backend_partial", None)
        try:
            partial = salvage_partial(tab, ref, baseline, backend_partial=backend_partial)  # type: ignore[arg-type]
        except AskChatGPTError:
            return
        if partial is None:
            return
        self.store.record_partial(
            ref,
            client_send_id=stub.client_send_id,
            partial_markdown=partial.content_markdown,
            error=error,
            capture_source=partial.capture_source,
            fidelity=partial.fidelity,
            message_id=partial.message_id,
            user_message_id=submitted.user_message_id if submitted is not None else None,
        )


def _attachment_specs(items: Sequence[str | Path | AttachmentSpec]) -> tuple[AttachmentSpec, ...]:
    specs: list[AttachmentSpec] = []
    for item in items:
        if isinstance(item, AttachmentSpec):
            specs.append(item)
        else:
            specs.append(AttachmentSpec(Path(item)))
    return tuple(specs)


def _canonical_user_record(
    ref: ConversationRef,
    submitted: SubmittedTurn,
    stub: TurnRecord,
    model: ModelRef | None,
    active_tools: tuple[str, ...],
) -> TurnRecord:
    if ref.conversation_id is None:
        raise InternalError("cannot construct canonical user for draft conversation")
    return TurnRecord(
        conversation_id=ref.conversation_id,
        conversation_url=conversation_url(ref),
        project_id=ref.project_id,
        message_id=submitted.user_message_id,
        parent_id=submitted.baseline.latest_assistant_id,
        turn_index=submitted.baseline.user_count + submitted.baseline.assistant_count,
        role="user",
        content_markdown=submitted.normalized_prompt,
        model=model,
        active_tools=active_tools,
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        user_message_id=None,
        client_send_id=stub.client_send_id,
        supersedes_message_id=stub.message_id,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def _select_new_assistant(
    records: Sequence[TurnRecord], assistant_message_id: str | None, baseline: object
) -> TurnRecord:
    baseline_id = getattr(baseline, "latest_assistant_id", None)
    assistants = [record for record in records if record.role == "assistant" and record.message_id != baseline_id]
    if assistant_message_id is not None:
        for record in assistants:
            if record.message_id == assistant_message_id:
                return record
    if assistants:
        return assistants[-1]
    raise InternalError("backend capture did not contain a new assistant turn")


class _NullStdout:
    def write(self, value: object) -> None:
        del value

    def flush(self) -> None:
        pass


__all__ = ["Session"]
