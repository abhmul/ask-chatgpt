"""Completion detection over the offline BrowserChannel seam."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ask_chatgpt.capture import acquire_backend_headers
from ask_chatgpt.channels.base import TabLease, TurnDom, WebSocketIdleObserver
from ask_chatgpt.errors import (
    BackendAuthUnavailableError,
    BackendCaptureShapeError,
    CompletionTimeoutError,
    HumanActionNeededError,
    MaxTotalWaitExceededError,
)
from ask_chatgpt.governor import DEFAULT_TOKEN_WEIGHTS, Governor, raise_for_rate_limit
from ask_chatgpt.identity import ConversationRef, conversation_url
from ask_chatgpt.models import SelectorMap, TurnRecord
from ask_chatgpt.send import TurnBaseline


DEFAULT_WEBSOCKET_IDLE_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class CompletionState:
    complete: bool
    assistant_message_id: str | None
    async_status: str | None
    node_status: str | None
    activity_token: str
    partial_markdown: str
    source: Literal["backend", "dom", "ws_idle"]
    last_progress_monotonic: float


def poll_backend_completion(
    tab: TabLease,
    conv: ConversationRef,
    baseline: TurnBaseline,
    *,
    prefer_lightweight: bool = False,
    governor: Governor | None = None,
) -> CompletionState:
    conversation_id = _require_conversation_id(conv)
    headers = acquire_backend_headers(tab, conv)
    path = f"/backend-api/conversation/{conversation_id}/stream_status" if prefer_lightweight else f"/backend-api/conversation/{conversation_id}"
    if governor is not None:
        governor.acquire(DEFAULT_TOKEN_WEIGHTS["backend_fetch"], action="backend_fetch", path_kind="completion")
    result = tab.channel.fetch_in_page(
        tab,
        path,
        method="GET",
        headers={"accept": "application/json", **headers.for_single_fetch()},
        timeout_s=None,
    )
    raise_for_rate_limit(result)
    if result.status != 200:
        raise BackendCaptureShapeError(
            "backend completion check did not return JSON success",
            details={"status": result.status},
        )
    raw = _decode_json_body(result.body_bytes)
    if not isinstance(raw, Mapping):
        raise BackendCaptureShapeError("backend completion body must be an object")
    return _completion_state_from_backend(tab, raw, baseline)


def poll_dom_progress(
    tab: TabLease, selectors: SelectorMap, baseline: TurnBaseline
) -> CompletionState:
    snapshot = tab.channel.query_turns(tab, selectors)
    latest = snapshot.assistants[-1] if snapshot.assistants else None
    is_new = latest is not None and latest.message_id != baseline.latest_assistant_id
    text = latest.text if latest is not None and is_new else ""
    assistant_id = latest.message_id if latest is not None else None
    node_status = "stop_visible" if snapshot.stop_visible else "stop_absent"
    token = _activity_token(
        {
            "source": "dom",
            "assistant_id": assistant_id,
            "is_new": is_new,
            "text_hash": _hash_text(text),
            "text_len": len(text),
            "stop_visible": snapshot.stop_visible,
            "assistant_count": len(snapshot.assistants),
        }
    )
    return CompletionState(
        complete=False,
        assistant_message_id=assistant_id if is_new else None,
        async_status=None,
        node_status=node_status,
        activity_token=token,
        partial_markdown=text,
        source="dom",
        last_progress_monotonic=_monotonic(tab),
    )


def poll_dom_completion(
    tab: TabLease,
    selectors: SelectorMap,
    baseline: TurnBaseline,
    *,
    stable_window_s: float,
) -> CompletionState:
    first = poll_dom_progress(tab, selectors, baseline)
    if not _dom_state_can_complete(first):
        return first
    _sleep(tab, stable_window_s)
    second = poll_dom_progress(tab, selectors, baseline)
    if (
        _dom_state_can_complete(second)
        and second.assistant_message_id == first.assistant_message_id
        and _text_stability_key(second) == _text_stability_key(first)
    ):
        return CompletionState(
            complete=True,
            assistant_message_id=second.assistant_message_id,
            async_status=None,
            node_status=second.node_status,
            activity_token=second.activity_token,
            partial_markdown=second.partial_markdown,
            source="dom",
            last_progress_monotonic=_monotonic(tab),
        )
    return second


def wait_for_completion(
    tab: TabLease,
    conv: ConversationRef,
    selectors: SelectorMap,
    baseline: TurnBaseline,
    *,
    activity_timeout_s: float,
    max_total_wait_s: float | None,
    progress_poll_interval_s: float = 2.0,
    backend_check_interval_s: float | None = None,
    websocket_idle_timeout_s: float = DEFAULT_WEBSOCKET_IDLE_TIMEOUT_S,
    websocket_idle_observer: WebSocketIdleObserver | None = None,
    governor: Governor | None = None,
) -> CompletionState:
    start = _monotonic(tab)
    last_progress = start
    backend_rescue_at = start + float(backend_check_interval_s) if backend_check_interval_s is not None else None
    backend_rescue_done = backend_check_interval_s is None
    seen_tokens: dict[str, str] = {}
    latest_backend_partial: CompletionState | None = None
    latest_dom_partial: CompletionState | None = None
    dom_stable_key: tuple[str | None, str, int] | None = None
    dom_stable_since: float | None = None
    stable_window_s = progress_poll_interval_s

    while True:
        now = _monotonic(tab)
        if max_total_wait_s is not None and now - start >= max_total_wait_s:
            error = MaxTotalWaitExceededError(
                "caller max_total_wait_s elapsed before completion",
                details={"elapsed_s": now - start, "max_total_wait_s": max_total_wait_s},
            )
            _attach_partials(error, latest_backend_partial, latest_dom_partial)
            raise error

        if not backend_rescue_done and backend_rescue_at is not None and now >= backend_rescue_at - 1e-9:
            backend_rescue_done = True
            try:
                backend_state = poll_backend_completion(tab, conv, baseline, governor=governor)
            except (BackendAuthUnavailableError, BackendCaptureShapeError):
                backend_state = None
            if backend_state is not None:
                if backend_state.partial_markdown:
                    latest_backend_partial = backend_state
                if _remember_progress(seen_tokens, "backend", backend_state.activity_token):
                    last_progress = now
                if backend_state.complete:
                    return backend_state

        dom_state = poll_dom_progress(tab, selectors, baseline)
        if dom_state.partial_markdown:
            latest_dom_partial = dom_state
        if _remember_progress(seen_tokens, "dom", dom_state.activity_token):
            last_progress = now

        dom_stable_ready = False
        if _dom_state_can_complete(dom_state):
            key = _text_stability_key(dom_state)
            if key != dom_stable_key:
                dom_stable_key = key
                dom_stable_since = now
            elif dom_stable_since is not None and now - dom_stable_since >= stable_window_s:
                dom_stable_ready = True
        else:
            dom_stable_key = None
            dom_stable_since = None

        ws_idle_ready = False
        if websocket_idle_observer is not None:
            ws_snapshot = websocket_idle_observer.snapshot(
                now_s=now,
                idle_after_s=websocket_idle_timeout_s,
            )
            ws_token = _activity_token(
                {
                    "source": "ws_idle",
                    "armed_monotonic_s": ws_snapshot.armed_monotonic_s,
                    "last_frame_monotonic_s": ws_snapshot.last_frame_monotonic_s,
                    "frame_count": ws_snapshot.frame_count,
                    "sent_count": ws_snapshot.sent_count,
                    "received_count": ws_snapshot.received_count,
                }
            )
            if _remember_progress(seen_tokens, "ws_idle", ws_token):
                last_progress = now
            ws_idle_ready = ws_snapshot.idle

        if dom_stable_ready and (websocket_idle_observer is None or ws_idle_ready):
            return CompletionState(
                complete=True,
                assistant_message_id=dom_state.assistant_message_id,
                async_status=None,
                node_status=dom_state.node_status,
                activity_token=dom_state.activity_token,
                partial_markdown=dom_state.partial_markdown,
                source="dom" if websocket_idle_observer is None else "ws_idle",
                last_progress_monotonic=now,
            )

        now = _monotonic(tab)
        if now - last_progress >= activity_timeout_s:
            error = CompletionTimeoutError(
                "no completion progress observed within activity_timeout_s",
                details={"elapsed_since_progress_s": now - last_progress, "activity_timeout_s": activity_timeout_s},
            )
            _attach_partials(error, latest_backend_partial, latest_dom_partial)
            raise error
        _sleep(tab, progress_poll_interval_s)


def salvage_partial(
    tab: TabLease,
    conv: ConversationRef,
    baseline: TurnBaseline,
    *,
    backend_partial: CompletionState | None,
    allow_clipboard: bool = False,
) -> TurnRecord | None:
    if (
        backend_partial is not None
        and backend_partial.assistant_message_id is not None
        and backend_partial.assistant_message_id != baseline.latest_assistant_id
        and backend_partial.partial_markdown
    ):
        return _partial_record(
            conv,
            message_id=backend_partial.assistant_message_id,
            text=backend_partial.partial_markdown,
            source="backend_api",
            fidelity="canonical",
        )

    clipboard_error: HumanActionNeededError | None = None
    if allow_clipboard:
        try:
            copied = tab.channel.read_clipboard(tab)
        except HumanActionNeededError as exc:
            copied = ""
            clipboard_error = exc
        if copied:
            return _partial_record(
                conv,
                message_id="partial:copy-button",
                text=copied,
                source="copy_button",
                fidelity="ui_copy",
            )

    snapshot = tab.channel.query_turns(tab, {  # type: ignore[arg-type]
        "composer": "#prompt-textarea",
        "tools_button": "",
        "message_turn": "",
        "user_turn": "",
        "assistant_turn": "",
        "copy_button": "",
        "stop_button": "",
        "send_button_unverified_no_input": "",
        "file_input": "",
        "attachment_chip": "",
        "active_tool_chip": "",
        "radix_portal": "",
        "model_picker_trigger_candidates": "",
    })
    latest = snapshot.assistants[-1] if snapshot.assistants else None
    if latest is not None and latest.message_id != baseline.latest_assistant_id and latest.text:
        return _partial_record(
            conv,
            message_id=latest.message_id,
            text=latest.text,
            source="dom_text",
            fidelity="lossy_dom_text",
        )
    if clipboard_error is not None:
        raise HumanActionNeededError(
            "clipboard fallback requires explicit permission",
            details={"reason": "clipboard_permission"},
        ) from clipboard_error
    raise HumanActionNeededError(
        "partial salvage requires backend or DOM content",
        details={"reason": "no_salvageable_partial"},
    )


def _completion_state_from_backend(
    tab: TabLease, raw: Mapping[str, Any], baseline: TurnBaseline
) -> CompletionState:
    branch = _current_branch_messages(raw)
    latest_assistant = _latest_assistant(branch)
    assistant_id = latest_assistant[0] if latest_assistant else None
    text = latest_assistant[1] if latest_assistant else ""
    message = latest_assistant[2] if latest_assistant else {}
    metadata = message.get("metadata") if isinstance(message, Mapping) else None
    metadata = metadata if isinstance(metadata, Mapping) else {}
    async_status = _optional_str(raw.get("async_status"))
    node_status = _optional_str(message.get("status")) if isinstance(message, Mapping) else None
    active = _has_active_backend_status(async_status, node_status, metadata)
    is_new = assistant_id is not None and assistant_id != baseline.latest_assistant_id
    explicit_empty_complete = bool(metadata.get("is_complete")) and not active
    complete = bool(is_new and (text or explicit_empty_complete) and not active)
    token = _activity_token(
        {
            "source": "backend",
            "assistant_id": assistant_id,
            "is_new": is_new,
            "text_hash": _hash_text(text),
            "text_len": len(text),
            "async_status": async_status,
            "node_status": node_status,
            "update_time": raw.get("update_time"),
            "current_node": raw.get("current_node"),
            "is_complete": metadata.get("is_complete"),
            "is_finalizing": metadata.get("is_finalizing"),
            "pro_progress": metadata.get("pro_progress"),
            "async_source": metadata.get("async_source"),
        }
    )
    return CompletionState(
        complete=complete,
        assistant_message_id=assistant_id if is_new else None,
        async_status=async_status,
        node_status=node_status,
        activity_token=token,
        partial_markdown=text if is_new else "",
        source="backend",
        last_progress_monotonic=_monotonic(tab),
    )


def _current_branch_messages(raw: Mapping[str, Any]) -> list[tuple[str, str, Mapping[str, Any]]]:
    mapping = raw.get("mapping")
    current = raw.get("current_node")
    if not isinstance(mapping, Mapping) or not isinstance(current, str) or not current:
        raise BackendCaptureShapeError("backend completion shape requires mapping and current_node")
    node_id: str | None = current
    branch: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    while node_id:
        if node_id in seen:
            raise BackendCaptureShapeError("cycle in backend completion branch")
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, Mapping):
            raise BackendCaptureShapeError("backend completion branch references a missing node")
        branch.append(node)
        parent = node.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise BackendCaptureShapeError("backend completion parent must be string or null")
        node_id = parent
    visible: list[tuple[str, str, Mapping[str, Any]]] = []
    for node in reversed(branch):
        message = node.get("message")
        if not isinstance(message, Mapping):
            continue
        role = _message_role(message)
        if role not in {"user", "assistant"}:
            continue
        content = message.get("content")
        if not isinstance(content, Mapping) or content.get("content_type") != "text":
            continue
        parts = content.get("parts")
        if not isinstance(parts, list) or not all(isinstance(part, str) for part in parts):
            raise BackendCaptureShapeError("backend completion text parts must be strings")
        message_id = _optional_str(message.get("id")) or _optional_str(node.get("id"))
        if message_id is None:
            raise BackendCaptureShapeError("backend completion visible message requires an id")
        visible.append((message_id, "".join(parts), message))
    return visible


def _latest_assistant(
    branch: Sequence[tuple[str, str, Mapping[str, Any]]]
) -> tuple[str, str, Mapping[str, Any]] | None:
    for message_id, text, message in reversed(branch):
        if _message_role(message) == "assistant":
            return (message_id, text, message)
    return None


def _message_role(message: Mapping[str, Any]) -> str | None:
    author = message.get("author")
    role = author.get("role") if isinstance(author, Mapping) else None
    return role if isinstance(role, str) else None


def _has_active_backend_status(
    async_status: str | None, node_status: str | None, metadata: Mapping[str, Any]
) -> bool:
    inactive = {None, "", "complete", "completed", "done", "success", "finished", "finished_successfully"}
    values = [async_status, node_status, _optional_str(metadata.get("async_source"))]
    if any((value.lower() if isinstance(value, str) else value) not in inactive for value in values):
        return True
    if metadata.get("is_complete") is False:
        return True
    if metadata.get("is_finalizing") is True:
        return True
    pro_progress = metadata.get("pro_progress")
    statuses_known_complete = all((value.lower() if isinstance(value, str) else value) in inactive - {""} for value in (async_status, node_status) if value is not None)
    if pro_progress and not statuses_known_complete:
        return True
    return False


def _dom_state_can_complete(state: CompletionState) -> bool:
    return (
        state.assistant_message_id is not None
        and state.node_status == "stop_absent"
        and bool(state.partial_markdown)
    )


def _text_stability_key(state: CompletionState) -> tuple[str | None, str, int]:
    return (state.assistant_message_id, _hash_text(state.partial_markdown), len(state.partial_markdown))


def _partial_record(
    conv: ConversationRef,
    *,
    message_id: str,
    text: str,
    source: Literal["backend_api", "copy_button", "dom_text"],
    fidelity: Literal["canonical", "ui_copy", "lossy_dom_text"],
) -> TurnRecord:
    conversation_id = _require_conversation_id(conv)
    return TurnRecord(
        conversation_id=conversation_id,
        conversation_url=conversation_url(conv),
        project_id=conv.project_id,
        message_id=message_id if message_id else "partial:unknown",
        parent_id=None,
        turn_index=0,
        role="assistant",
        content_markdown=text,
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="partial" if text else "error",
        partial=True,
        capture_source=source,
        fidelity=fidelity,
        error=None,
    )


def _decode_json_body(body_bytes: bytes | None) -> Any:
    if body_bytes is None:
        raise BackendCaptureShapeError("backend completion body was not buffered")
    try:
        return json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendCaptureShapeError("backend completion body was not valid JSON") from exc


def _remember_progress(tokens: dict[str, str], key: str, token: str) -> bool:
    if tokens.get(key) == token:
        return False
    tokens[key] = token
    return True


def _attach_partials(
    error: BaseException,
    backend_partial: CompletionState | None,
    dom_partial: CompletionState | None,
) -> None:
    setattr(error, "backend_partial", backend_partial)
    setattr(error, "dom_partial", dom_partial)


def _activity_token(parts: Mapping[str, Any]) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _require_conversation_id(conv: ConversationRef) -> str:
    if conv.conversation_id is None:
        raise ValueError("completion requires a persisted conversation id")
    return conv.conversation_id


def _monotonic(tab: TabLease) -> float:
    monotonic = getattr(tab.channel, "monotonic", None)
    if callable(monotonic):
        return float(monotonic())
    return 0.0


def _sleep(tab: TabLease, seconds: float) -> None:
    sleeper = getattr(tab.channel, "sleep", None)
    if callable(sleeper):
        sleeper(max(0.0, float(seconds)))


__all__ = [
    "DEFAULT_WEBSOCKET_IDLE_TIMEOUT_S",
    "CompletionState",
    "poll_backend_completion",
    "poll_dom_completion",
    "poll_dom_progress",
    "salvage_partial",
    "wait_for_completion",
]
