"""Minimal public Session facade for the M4 offline-core spine."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ask_chatgpt.capture import SendContext, capture_conversation
from ask_chatgpt.channels.base import BrowserChannel, TabLease
from ask_chatgpt.completion import salvage_partial, wait_for_completion
from ask_chatgpt.errors import (
    AskChatGPTError,
    AttachmentFetchError,
    AttachmentNotFoundError,
    CompletionTimeoutError,
    HumanActionNeededError,
    InternalError,
    MaxTotalWaitExceededError,
    StoreError,
    TabPoolExhaustedError,
)
from ask_chatgpt.identity import ConversationRef, conversation_url, parse_project_address
from ask_chatgpt.menus import assert_reflected_model, assert_reflected_tools
from ask_chatgpt.models import (
    AttachmentSpec,
    JsonValue,
    ModelRef,
    PreflightResult,
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


@dataclass
class _ManagedTab:
    tab: TabLease
    url: str
    leased: bool = False
    last_used: int = 0


class TabPool:
    """M4 minimal own-tab pool stub.

    The pool records only tabs it opened through the channel. It never enumerates
    browser/context pages, never closes foreign tabs, and implements only the
    small lease/release/close-all behavior needed by the offline core.
    """

    def __init__(self, session: "Session", *, max_tabs: int = 3) -> None:
        self._session = session
        self.max_tabs = max(1, int(max_tabs))
        self._entries: list[_ManagedTab] = []
        self._tick = 0

    def acquire(self, ref: ConversationRef) -> TabLease:
        url = conversation_url(ref)
        self._session.attach()
        for entry in self._entries:
            if entry.url == url and not entry.leased:
                entry.leased = True
                self._tick += 1
                entry.last_used = self._tick
                return entry.tab
        if len(self._entries) >= self.max_tabs:
            self._evict_one_unleased()
        channel = self._session._channel()
        tab = channel.open_tab(url)
        self._tick += 1
        self._entries.append(_ManagedTab(tab=tab, url=url, leased=True, last_used=self._tick))
        return tab

    def release(self, tab: TabLease) -> None:
        for entry in self._entries:
            if entry.tab is tab:
                entry.leased = False
                self._tick += 1
                entry.last_used = self._tick
                return
        raise TabPoolExhaustedError("attempted to release an unmanaged tab lease")

    def close_all(self) -> None:
        entries = list(self._entries)
        self._entries.clear()
        for entry in entries:
            try:
                entry.tab.channel.close_tab(entry.tab)
            except Exception:
                # M4 detach is best-effort for managed tabs and must still
                # disconnect the client transport.
                continue

    def snapshot(self) -> Mapping[str, JsonValue]:
        return {
            "max_tabs": self.max_tabs,
            "managed_tabs": len(self._entries),
            "leased_tabs": sum(1 for entry in self._entries if entry.leased),
        }

    def _evict_one_unleased(self) -> None:
        candidates = [entry for entry in self._entries if not entry.leased]
        if not candidates:
            raise TabPoolExhaustedError("all managed tabs are currently leased")
        victim = min(candidates, key=lambda entry: entry.last_used)
        self._entries.remove(victim)
        victim.tab.channel.close_tab(victim.tab)


class AdaptiveSendBudget:
    """M4 minimal send-budget stub with no hard message cap."""

    def __init__(self) -> None:
        self.successful_submissions = 0
        self.active_submission = False

    @contextmanager
    def submission(self) -> Iterator[None]:
        if self.active_submission:
            raise PromptBudgetBusyError("another prompt submission is active")
        self.active_submission = True
        try:
            yield
            self.successful_submissions += 1
        finally:
            self.active_submission = False

    def snapshot(self) -> Mapping[str, JsonValue]:
        return {
            "successful_submissions": self.successful_submissions,
            "active_submission": self.active_submission,
            "hard_message_cap": None,
        }


class PromptBudgetBusyError(AskChatGPTError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TAB_POOL_EXHAUSTED",
            62,
            True,
            "wait_or_reduce_concurrency",
            message,
            {},
        )


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
        self.tab_pool = TabPool(self, max_tabs=max_tabs)
        self.send_budget = AdaptiveSendBudget()
        self._attached = False

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
        if close_managed_tabs:
            self.tab_pool.close_all()
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
        project_id = parse_project_address(project) if project else None
        if project is not None and project_id is None:
            raise StoreError("invalid project id for draft create")
        url = f"https://chatgpt.com/g/g-p-{project_id}" if project_id else "https://chatgpt.com/"
        return ConversationRef(
            conversation_id=None,
            url=url,
            project_id=project_id,
            is_draft=True,
        )

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
        tab = self.tab_pool.acquire(ref)
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
            with self.send_budget.submission():
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
                partial = self._record_partial_if_available(tab, ref, baseline, stub, submitted, exc)
                if partial is not None:
                    setattr(exc, "partial", partial)
                    setattr(exc, "partial_markdown", partial.content_markdown)
                raise
            if out is not None:
                self.store.emit_payload(_ask_payload(answer.content_markdown), out=out, stdout=_NullStdout())
            return answer
        finally:
            self.tab_pool.release(tab)

    def scrape(
        self,
        conv_or_url: str | ConversationRef,
        *,
        with_attachments: bool = False,
        out: str | Path | None = None,
    ) -> Transcript:
        ref = self.store.resolve_conversation(conv_or_url) if not isinstance(conv_or_url, ConversationRef) else conv_or_url
        self.store.put_conversation_ref(ref)
        tab = self.tab_pool.acquire(ref)
        try:
            captured = capture_conversation(tab, ref, self.store, with_attachments=with_attachments)
            transcript = self.store.load_transcript(ref)
            if out is not None:
                self.store.emit_payload(self.store.render_markdown(transcript), out=out, stdout=_NullStdout())
            return transcript if transcript.turns else captured.transcript
        finally:
            self.tab_pool.release(tab)

    def history(self, conv_or_url: str | ConversationRef) -> Transcript:
        return self.store.load_transcript(conv_or_url)

    def fetch(self, conv_or_url: str | ConversationRef, attachment_ref: str) -> Path:
        transcript = self.store.load_transcript(conv_or_url)
        if transcript.conversation.conversation_id is None:
            raise AttachmentNotFoundError("attachment lookup requires a persisted conversation")
        paths = self.store.ensure_conversation(transcript.conversation)
        for turn in transcript.turns:
            for attachment in turn.attachments:
                if attachment_ref not in {
                    attachment.source_ref,
                    attachment.filename,
                    attachment.local_path,
                    attachment.raw_path,
                }:
                    continue
                if not attachment.local_path:
                    raise AttachmentFetchError("attachment is known but not cached locally")
                candidate = (paths.root / attachment.local_path).resolve()
                try:
                    candidate.relative_to(paths.root.resolve())
                except ValueError as exc:
                    raise AttachmentFetchError("cached attachment path escaped conversation directory") from exc
                if not candidate.exists():
                    raise AttachmentFetchError("cached attachment file is missing")
                return candidate
        raise AttachmentNotFoundError("attachment ref not found in local transcript")

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
        del model, tools, attach, timeout, max_total_wait, out_dir
        if isinstance(self._channel_arg, str) and self._channel_arg != "mock":
            raise HumanActionNeededError("M4 loop stub is mock-only; real browser loop is deferred")
        iterations = 1 if max_iterations is None else int(max_iterations)
        if iterations < 0:
            raise ValueError("max_iterations must be non-negative")
        ref = self.store.resolve_conversation(conv_or_url) if not isinstance(conv_or_url, ConversationRef) else conv_or_url
        if ref.conversation_id is None:
            raise StoreError("loop requires a persisted conversation id")
        for index in range(iterations):
            yield TurnRecord(
                conversation_id=ref.conversation_id,
                conversation_url=conversation_url(ref),
                project_id=ref.project_id,
                message_id=f"mock-loop:{index + 1}",
                parent_id=None,
                turn_index=index,
                role="assistant",
                content_markdown=f"{message} (mock loop iteration {index + 1})",
                model=None,
                active_tools=(),
                kind="normal",
                created_at=None,
                attachments=(),
                citations=(),
                status="complete",
                partial=False,
                capture_source="dom_text",
                fidelity="lossy_dom_text",
                error=None,
            )

    def status(
        self,
        conv_or_url: str | ConversationRef | None = None,
        *,
        probe_browser: bool = True,
    ) -> StatusReport:
        cdp: PreflightResult | None = None
        signed_in: bool | None = None
        login_or_challenge: bool | None = None
        blocking_code: str | None = None
        details: dict[str, JsonValue] = {
            "selectors": {
                key: {"selector": value, "present": None}
                for key, value in self.selector_map.items()
            },
            "tab_pool": dict(self.tab_pool.snapshot()),
            "send_budget": dict(self.send_budget.snapshot()),
        }

        if probe_browser:
            try:
                cdp = self._channel().preflight()
            except NotImplementedError:
                cdp = PreflightResult(
                    ok=False,
                    cdp_endpoint=self.cdp_endpoint,
                    browser=None,
                    protocol_version=None,
                    websocket_url_present=False,
                    error_code="CDP_UNREACHABLE",
                    error="CDP channel is deferred beyond M4 offline core",
                )
            if cdp.ok:
                signed_in = True
                login_or_challenge = False
            else:
                blocking_code = cdp.error_code or "CDP_UNREACHABLE"
                login_or_challenge = blocking_code == "HUMAN-ACTION-NEEDED"

        conversations = _conversation_count(self.store)
        if conv_or_url is not None:
            try:
                transcript = self.store.load_transcript(conv_or_url)
                details["conversation"] = {
                    "conversation_id": transcript.conversation.conversation_id,
                    "conversation_url": transcript.conversation.url,
                    "turns": len(transcript.turns),
                    "transcript_path": str(transcript.transcript_path) if transcript.transcript_path else None,
                    "raw_mapping_path": str(transcript.raw_mapping_path) if transcript.raw_mapping_path else None,
                }
            except AskChatGPTError as exc:
                blocking_code = blocking_code or exc.code
                details["last_error"] = _error_summary(exc)

        return StatusReport(
            ok=blocking_code is None,
            cdp=cdp,
            signed_in=signed_in,
            login_or_challenge=login_or_challenge,
            selector_valid=True,
            conversations=conversations,
            blocking_code=blocking_code,
            details=_redact_json(details),
        )

    def _record_partial_if_available(
        self,
        tab: TabLease,
        ref: ConversationRef,
        baseline: object,
        stub: TurnRecord | None,
        submitted: SubmittedTurn | None,
        error: BaseException,
    ) -> TurnRecord | None:
        if stub is None:
            return None
        backend_partial = getattr(error, "backend_partial", None)
        try:
            partial = salvage_partial(tab, ref, baseline, backend_partial=backend_partial)  # type: ignore[arg-type]
        except AskChatGPTError:
            return None
        if partial is None:
            return None
        return self.store.record_partial(
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


def _ask_payload(content: str) -> str:
    return content.rstrip("\n") + "\n"


def _conversation_count(store: Store) -> int:
    root = store.resolve_data_dir() / "conversations"
    if not root.exists():
        return 0
    return sum(1 for path in root.iterdir() if path.is_dir())


def _error_summary(exc: AskChatGPTError) -> Mapping[str, JsonValue]:
    return {
        "code": exc.code,
        "message": _redact_text(exc.message),
        "exit_code": exc.exit_code,
    }


_SENSITIVE_TEXT = (
    "authorization",
    "bearer",
    "cookie",
    "header",
    "oai-",
    "password",
    "prompt",
    "secret",
    "token",
    "canary",
)


def _redact_text(text: str) -> str:
    lowered = text.lower()
    return "<redacted>" if any(part in lowered for part in _SENSITIVE_TEXT) else text


def _redact_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, JsonValue] = {}
        for key, nested in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in _SENSITIVE_TEXT):
                out[key_text] = "<redacted>"
            else:
                out[key_text] = _redact_json(nested)
        return out
    if isinstance(value, tuple | list):
        return [_redact_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return repr(value)


class _NullStdout:
    def write(self, value: object) -> None:
        del value

    def flush(self) -> None:
        pass


__all__ = ["AdaptiveSendBudget", "Session", "TabPool"]
