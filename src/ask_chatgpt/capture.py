"""Offline-testable backend capture parser and linearizer."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from ask_chatgpt.channels.base import FetchResult, RequestSnapshot, TabLease
from ask_chatgpt.errors import (
    BackendAuthUnavailableError,
    BackendCaptureShapeError,
    CaptureFailedClosedError,
    HumanActionNeededError,
    StoreError,
)
from ask_chatgpt.identity import ConversationRef, backend_conversation_url, conversation_url
from ask_chatgpt.models import (
    AttachmentRef,
    CaptureFidelity,
    CaptureSource,
    CitationRef,
    JsonValue,
    ModelRef,
    Transcript,
    TurnRecord,
)
from ask_chatgpt.store import Store

REQUIRED_CAPTURE_HEADERS: tuple[str, ...] = (
    "authorization",
    "oai-client-build-number",
    "oai-client-version",
    "oai-device-id",
    "oai-language",
    "oai-session-id",
    "x-openai-target-path",
    "x-openai-target-route",
)

_KATEX_EVAL_KEY = "ask_chatgpt_capture_katex_annotations"
_DOM_TEXT_EVAL_KEY = "ask_chatgpt_capture_dom_text"


@dataclass(frozen=True, repr=False)
class HeaderBundle:
    conversation_id: str
    source: Literal["web_app_request"]
    acquired_at_monotonic: float
    _headers: Mapping[str, str]
    _used: bool = field(default=False, init=False, repr=False, compare=False)

    def for_single_fetch(self) -> Mapping[str, str]:
        if self._used:
            raise BackendAuthUnavailableError(
                "backend headers already consumed",
                details={"conversation_id": self.conversation_id, "header_names": tuple(sorted(self._headers))},
            )
        object.__setattr__(self, "_used", True)
        return dict(self._headers)

    def redacted(self) -> Mapping[str, JsonValue]:
        return {
            "conversation_id": self.conversation_id,
            "source": self.source,
            "acquired_at_monotonic": self.acquired_at_monotonic,
            "header_names": list(sorted(self._headers)),
        }


@dataclass(frozen=True)
class CaptureResult:
    transcript: Transcript
    async_status: str | None
    raw_top_level_keys: tuple[str, ...]
    source: CaptureSource
    fidelity: CaptureFidelity


@dataclass(frozen=True)
class BackendFetchMeta:
    raw_tmp: Path
    status: int
    content_type: str | None
    bytes_written: int
    elapsed_s: float | None


@dataclass(frozen=True)
class BackendTopLevel:
    raw_path: Path
    conversation_id: str
    current_node: str
    async_status: str | None
    update_time: str | int | float | None
    default_model_slug: str | None
    top_level_keys: tuple[str, ...]
    mapping_node_count: int


@dataclass(frozen=True)
class SendContext:
    client_send_id: str | None
    user_message_id: str | None
    model: ModelRef | None
    active_tools: tuple[str, ...]


@dataclass(frozen=True)
class _GroupFacts:
    visible_user: bool = False
    visible_final_assistant: bool = False
    hidden_internal: bool = False
    citation_or_search_metadata: bool = False
    attachments: tuple[AttachmentRef, ...] = ()
    citations: tuple[CitationRef, ...] = ()

    def add(self, **updates: Any) -> "_GroupFacts":
        values = {
            "visible_user": self.visible_user,
            "visible_final_assistant": self.visible_final_assistant,
            "hidden_internal": self.hidden_internal,
            "citation_or_search_metadata": self.citation_or_search_metadata,
            "attachments": self.attachments,
            "citations": self.citations,
        }
        values.update(updates)
        return _GroupFacts(**values)


def acquire_backend_headers(tab: TabLease, conv: ConversationRef, *, timeout_s: float = 30.0) -> HeaderBundle:
    conversation_id = _require_conversation_id(conv)
    target_path = urlsplit(backend_conversation_url(conversation_id)).path

    def matches(request: RequestSnapshot) -> bool:
        path = urlsplit(request.url).path if not request.url.startswith("/") else request.url
        return request.method.upper() == "GET" and path == target_path

    try:
        snapshot = tab.channel.wait_for_request(tab, matches, timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001 - public error boundary must redact details.
        raise BackendAuthUnavailableError(
            "required backend request headers were not observed",
            details={"conversation_id": conversation_id, "required_headers": REQUIRED_CAPTURE_HEADERS},
        ) from exc
    headers = _lower_headers(snapshot.headers)
    missing = tuple(name for name in REQUIRED_CAPTURE_HEADERS if name not in headers)
    if missing:
        raise BackendAuthUnavailableError(
            "required backend request headers were missing",
            details={"conversation_id": conversation_id, "missing_headers": missing},
        )
    required = {name: headers[name] for name in REQUIRED_CAPTURE_HEADERS}
    return HeaderBundle(
        conversation_id=conversation_id,
        source="web_app_request",
        acquired_at_monotonic=_channel_monotonic(tab),
        _headers=required,
    )


def stream_backend_conversation(tab: TabLease, conv: ConversationRef, headers: HeaderBundle, *, raw_tmp: Path) -> BackendFetchMeta:
    conversation_id = _require_conversation_id(conv)
    started = _channel_monotonic(tab)
    fetch_headers = {"accept": "application/json", **headers.for_single_fetch()}
    result = tab.channel.fetch_in_page(
        tab,
        f"/backend-api/conversation/{conversation_id}",
        method="GET",
        headers=fetch_headers,
        stream_to=raw_tmp,
        timeout_s=None,
    )
    elapsed = _channel_monotonic(tab) - started
    content_type = _content_type(result)
    bytes_written = _fetch_bytes_written(result, raw_tmp)
    return BackendFetchMeta(raw_tmp=raw_tmp, status=result.status, content_type=content_type, bytes_written=bytes_written, elapsed_s=elapsed)


def validate_backend_shape(raw_path: Path, expected_conversation_id: str) -> BackendTopLevel:
    raw = _load_backend_raw(raw_path)
    conversation_id = raw.get("conversation_id")
    if conversation_id != expected_conversation_id:
        raise BackendCaptureShapeError(
            "backend conversation_id mismatch",
            details={"expected_conversation_id": expected_conversation_id, "actual_present": isinstance(conversation_id, str)},
        )
    mapping = raw.get("mapping")
    if not isinstance(mapping, dict):
        raise BackendCaptureShapeError("backend raw mapping must be an object")
    current_node = raw.get("current_node")
    if not isinstance(current_node, str) or not current_node:
        raise BackendCaptureShapeError("backend current_node must be a non-empty string")
    if current_node not in mapping:
        raise BackendCaptureShapeError("backend current_node is not present in mapping", details={"current_node": current_node})
    async_status = raw.get("async_status")
    if async_status is not None and not isinstance(async_status, str):
        async_status = None
    update_time = raw.get("update_time")
    if not isinstance(update_time, str | int | float) and update_time is not None:
        update_time = None
    default_model_slug = raw.get("default_model_slug")
    if not isinstance(default_model_slug, str):
        default_model_slug = None
    return BackendTopLevel(
        raw_path=Path(raw_path),
        conversation_id=conversation_id,
        current_node=current_node,
        async_status=async_status,
        update_time=update_time,
        default_model_slug=default_model_slug,
        top_level_keys=tuple(raw.keys()),
        mapping_node_count=len(mapping),
    )


def iter_current_branch_records(raw_path: Path, conv: ConversationRef, *, send_context: SendContext | None = None) -> Iterator[TurnRecord]:
    conversation_id = _require_conversation_id(conv)
    top = validate_backend_shape(raw_path, conversation_id)
    raw = _load_backend_raw(raw_path)
    branch_ids = _iter_current_branch_node_ids(raw)
    mapping = raw["mapping"]
    group_facts = _collect_group_facts(mapping, branch_ids)
    default_model = ModelRef(top.default_model_slug, send_context.model.display if send_context and send_context.model else None) if top.default_model_slug else (send_context.model if send_context else None)
    turn_index = 0
    last_visible_user_id: str | None = None
    for node_id in branch_ids:
        node = mapping[node_id]
        message = node.get("message") if isinstance(node, Mapping) else None
        if not isinstance(message, Mapping) or not _is_visible_text_message(message):
            continue
        content_markdown = _extract_visible_parts(message, node_id)
        role = _message_role(message)
        if role not in {"user", "assistant"}:
            continue
        metadata = _message_metadata(message)
        exchange_id = _optional_str(metadata.get("turn_exchange_id"))
        message_id = _message_id(message, node_id)
        model = _model_for_message(metadata, default_model)
        own_attachments = tuple(_attachments_for_message(node_id, message, visible=True))
        own_citations = tuple(_citations_for_message(node_id, message, visible=True))
        attachments = own_attachments
        citations = own_citations
        active_tools = tuple(send_context.active_tools) if send_context else ()
        kind = "normal"
        user_message_id = None
        supersedes_message_id = None
        if role == "user":
            last_visible_user_id = message_id
            if send_context and send_context.client_send_id and message_id == send_context.user_message_id:
                supersedes_message_id = f"local:{send_context.client_send_id}"
        elif role == "assistant":
            user_message_id = send_context.user_message_id if send_context and send_context.user_message_id else last_visible_user_id
            if exchange_id is not None:
                facts = group_facts.get(exchange_id)
                if facts is not None:
                    attachments = _dedupe_attachments((*own_attachments, *facts.attachments))
                    citations = _dedupe_citations((*own_citations, *facts.citations))
                    if _is_deep_research_exchange(facts):
                        kind = "deep_research"
                        active_tools = _append_unique(active_tools, "deep_research")
        yield TurnRecord(
            conversation_id=conversation_id,
            conversation_url=conversation_url(conv),
            project_id=conv.project_id,
            message_id=message_id,
            parent_id=_parent_id(node),
            turn_index=turn_index,
            role=role,
            content_markdown=content_markdown,
            model=model,
            active_tools=active_tools,
            kind=kind,
            created_at=_created_at(message),
            attachments=attachments,
            citations=citations,
            status="complete",
            partial=False,
            user_message_id=user_message_id,
            turn_exchange_id=exchange_id,
            client_send_id=send_context.client_send_id if send_context else None,
            supersedes_message_id=supersedes_message_id,
            capture_source="backend_api",
            fidelity="canonical",
            error=None,
        )
        turn_index += 1


def capture_conversation(tab: TabLease, conv: ConversationRef, store: Store, *, with_attachments: bool = False, send_context: SendContext | None = None) -> CaptureResult:
    del with_attachments
    conversation_id = _require_conversation_id(conv)
    tmp_dir = store.ensure_conversation(conv).root
    raw_tmp = tmp_dir / f"raw-mapping.json.tmp.{os.getpid()}.{id(tab)}"
    try:
        headers = acquire_backend_headers(tab, conv)
        meta = stream_backend_conversation(tab, conv, headers, raw_tmp=raw_tmp)
        _validate_fetch_meta(meta)
        top = validate_backend_shape(raw_tmp, conversation_id)
        records = tuple(iter_current_branch_records(raw_tmp, conv, send_context=send_context))
        raw_path = store.write_raw_mapping_atomic(conversation_id, raw_tmp)
        store.upsert_many(records)
        transcript_path = store.ensure_conversation(conv).transcript_jsonl
        transcript = Transcript(conv, records, raw_path, transcript_path)
        return CaptureResult(transcript=transcript, async_status=top.async_status, raw_top_level_keys=top.top_level_keys, source="backend_api", fidelity="canonical")
    except (BackendAuthUnavailableError, BackendCaptureShapeError, StoreError) as exc:
        _unlink_if_exists(raw_tmp)
        return fallback_capture_ui(tab, conv, store, reason=exc.code if hasattr(exc, "code") else type(exc).__name__)
    except Exception:
        _unlink_if_exists(raw_tmp)
        raise
    finally:
        if raw_tmp.exists():
            _unlink_if_exists(raw_tmp)


def fallback_capture_ui(tab: TabLease, conv: ConversationRef, store: Store, *, reason: str, allow_clipboard: bool = False) -> CaptureResult:
    if not allow_clipboard:
        raise HumanActionNeededError(
            "clipboard fallback requires explicit permission",
            details={"reason": "clipboard_permission", "backend_reason": reason},
        )
    try:
        copied = tab.channel.read_clipboard(tab)
    except HumanActionNeededError:
        copied = ""
    if copied:
        return _persist_fallback_record(tab, conv, store, copied, source="copy_button", fidelity="ui_copy", status="complete", partial=False, reason=reason)
    katex = tab.channel.evaluate(tab, _KATEX_EVAL_KEY, timeout_s=5.0)
    if isinstance(katex, list) and all(isinstance(item, str) for item in katex) and katex:
        return _persist_fallback_record(tab, conv, store, "".join(katex), source="katex_annotation", fidelity="math_annotation_reconstructed", status="partial", partial=True, reason=reason)
    dom_text = tab.channel.evaluate(tab, _DOM_TEXT_EVAL_KEY, timeout_s=5.0)
    if isinstance(dom_text, str) and dom_text:
        return _persist_fallback_record(tab, conv, store, dom_text, source="dom_text", fidelity="lossy_dom_text", status="partial", partial=True, reason=reason)
    raise CaptureFailedClosedError("backend capture failed and no fallback succeeded", details={"reason": reason})


def _persist_fallback_record(tab: TabLease, conv: ConversationRef, store: Store, text: str, *, source: CaptureSource, fidelity: CaptureFidelity, status: Literal["complete", "partial"], partial: bool, reason: str) -> CaptureResult:
    del tab
    conversation_id = _require_conversation_id(conv)
    existing = store.load_transcript(conv, include_pending=True).turns
    indexes = [turn.turn_index for turn in existing if turn.turn_index is not None]
    turn_index = max(indexes) + 1 if indexes else 0
    record = TurnRecord(
        conversation_id=conversation_id,
        conversation_url=conversation_url(conv),
        project_id=conv.project_id,
        message_id=f"fallback:{source}:{turn_index}",
        parent_id=None,
        turn_index=turn_index,
        role="assistant",
        content_markdown=text,
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status=status,
        partial=partial,
        capture_source=source,
        fidelity=fidelity,
        error={"reason": reason} if partial else None,
    )
    store.upsert_turn(record)
    transcript = Transcript(conv, (record,), None, store.ensure_conversation(conv).transcript_jsonl)
    return CaptureResult(transcript=transcript, async_status=None, raw_top_level_keys=(), source=source, fidelity=fidelity)


def _iter_current_branch_node_ids(raw: Mapping[str, Any]) -> list[str]:
    mapping = raw["mapping"]
    node_id = raw.get("current_node")
    branch: list[str] = []
    seen: set[str] = set()
    while node_id:
        if not isinstance(node_id, str):
            raise BackendCaptureShapeError("backend parent chain contains a non-string node id")
        if node_id in seen:
            raise BackendCaptureShapeError("cycle in backend mapping parent chain", details={"node_id": node_id})
        seen.add(node_id)
        node = mapping.get(node_id) if isinstance(mapping, Mapping) else None
        if not isinstance(node, Mapping):
            raise BackendCaptureShapeError("backend parent chain references a missing node", details={"node_id": node_id})
        branch.append(node_id)
        parent = node.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise BackendCaptureShapeError("backend node parent must be a string or null", details={"node_id": node_id})
        node_id = parent
    return list(reversed(branch))


def _collect_group_facts(mapping: Mapping[str, Any], branch_ids: list[str]) -> dict[str, _GroupFacts]:
    facts: dict[str, _GroupFacts] = {}
    for node_id in branch_ids:
        node = mapping[node_id]
        message = node.get("message") if isinstance(node, Mapping) else None
        if not isinstance(message, Mapping):
            continue
        metadata = _message_metadata(message)
        exchange_id = _optional_str(metadata.get("turn_exchange_id"))
        if exchange_id is None:
            continue
        current = facts.get(exchange_id, _GroupFacts())
        visible = _is_visible_text_message(message)
        role = _message_role(message)
        hidden_internal = current.hidden_internal or (not visible and _is_hidden_internal(message))
        citation_or_search = current.citation_or_search_metadata or _has_citation_or_search_metadata(message)
        attachments = (*current.attachments, *_attachments_for_message(node_id, message, visible=visible)) if not (visible and role == "user") else current.attachments
        citations = (*current.citations, *_citations_for_message(node_id, message, visible=visible))
        facts[exchange_id] = current.add(
            visible_user=current.visible_user or (visible and role == "user"),
            visible_final_assistant=current.visible_final_assistant or (visible and role == "assistant"),
            hidden_internal=hidden_internal,
            citation_or_search_metadata=citation_or_search,
            attachments=_dedupe_attachments(attachments),
            citations=_dedupe_citations(citations),
        )
    return facts


def _attachments_for_message(node_id: str, message: Mapping[str, Any], *, visible: bool) -> Iterator[AttachmentRef]:
    del visible
    metadata = _message_metadata(message)
    for index, item in enumerate(_list(metadata.get("attachments"))):
        if not isinstance(item, Mapping):
            continue
        yield AttachmentRef(
            source_kind="user_upload",
            source_ref=_optional_str(item.get("id")),
            raw_path=f"/mapping/{node_id}/message/metadata/attachments/{index}",
            filename=_optional_str(item.get("name")),
            mime=_optional_str(item.get("mime_type")) or _optional_str(item.get("mime")),
            bytes=_optional_int(item.get("size")),
            sha256=None,
            local_path=None,
            download_state="pending",
            metadata=_sanitize_metadata({key: value for key, value in item.items() if key not in {"id", "name", "size", "mime", "mime_type"}}),
        )
    for index, item in enumerate(_list(metadata.get("content_references"))):
        if not isinstance(item, Mapping) or item.get("type") != "file":
            continue
        yield AttachmentRef(
            source_kind="file_reference",
            source_ref=_optional_str(item.get("id")),
            raw_path=f"/mapping/{node_id}/message/metadata/content_references/{index}",
            filename=_optional_str(item.get("name")),
            mime=_optional_str(item.get("mime_type")) or _optional_str(item.get("mime")),
            bytes=_optional_int(item.get("size")),
            sha256=None,
            local_path=None,
            download_state="pending",
            metadata=_sanitize_metadata({key: value for key, value in item.items() if key not in {"type", "id", "name", "size", "mime", "mime_type"}}),
        )
    content = message.get("content")
    if isinstance(content, Mapping):
        for index, asset in enumerate(_list(content.get("assets"))):
            if not isinstance(asset, Mapping):
                continue
            yield AttachmentRef(
                source_kind="generated_asset",
                source_ref=_optional_str(asset.get("asset_pointer")),
                raw_path=f"/mapping/{node_id}/message/content/assets/{index}",
                filename=_optional_str(asset.get("filename")) or _optional_str(asset.get("name")),
                mime=_optional_str(asset.get("content_type")) or _optional_str(asset.get("mime")),
                bytes=_optional_int(asset.get("size_bytes")) or _optional_int(asset.get("size")),
                sha256=None,
                local_path=None,
                download_state="pending",
                metadata=_sanitize_metadata({key: value for key, value in asset.items() if key not in {"asset_pointer", "filename", "name", "content_type", "mime", "size", "size_bytes"}}),
            )
    aggregate = metadata.get("aggregate_result")
    if isinstance(aggregate, Mapping):
        run_id = _optional_str(aggregate.get("run_id"))
        yield AttachmentRef(
            source_kind="code_execution_output",
            source_ref=run_id,
            raw_path=f"/mapping/{node_id}/message/metadata/aggregate_result",
            filename=f"run_{run_id}_aggregate.json" if run_id else None,
            mime="application/json",
            bytes=None,
            sha256=None,
            local_path=None,
            download_state="pending",
            metadata=_sanitize_metadata({key: value for key, value in aggregate.items() if key != "run_id"}),
        )


def _citations_for_message(node_id: str, message: Mapping[str, Any], *, visible: bool) -> Iterator[CitationRef]:
    del visible
    metadata = _message_metadata(message)
    for index, item in enumerate(_list(metadata.get("citations"))):
        if not isinstance(item, Mapping):
            continue
        nested = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        yield CitationRef(
            title=_optional_str(item.get("title")) or _optional_str(nested.get("title")) if isinstance(nested, Mapping) else _optional_str(item.get("title")),
            url=_optional_str(item.get("url")) or _optional_str(nested.get("url")) if isinstance(nested, Mapping) else _optional_str(item.get("url")),
            source="citations",
            citation_type=_optional_str(item.get("type")) or _optional_str(nested.get("type")) if isinstance(nested, Mapping) else _optional_str(item.get("type")),
            start_ix=_optional_int(item.get("start_ix")),
            end_ix=_optional_int(item.get("end_ix")),
            citation_format_type=_optional_str(item.get("citation_format_type")),
            raw_path=f"/mapping/{node_id}/message/metadata/citations/{index}",
            metadata=_sanitize_metadata(item),
        )
    for index, item in enumerate(_list(metadata.get("content_references"))):
        if not isinstance(item, Mapping):
            continue
        ref_type = item.get("type")
        if ref_type == "file":
            continue
        if ref_type == "grouped_webpages":
            entries = _list(item.get("items")) or [item]
        elif ref_type == "sources_footnote":
            entries = _list(item.get("sources")) or [item]
        else:
            continue
        for entry_index, entry in enumerate(entries):
            entry_map = entry if isinstance(entry, Mapping) else item
            yield CitationRef(
                title=_optional_str(entry_map.get("title")) or _optional_str(item.get("title")),
                url=_optional_str(entry_map.get("url")) or _optional_str(item.get("url")),
                source="content_references",
                citation_type=_optional_str(ref_type),
                start_ix=_optional_int(item.get("start_ix")),
                end_ix=_optional_int(item.get("end_ix")),
                citation_format_type=_optional_str(item.get("citation_format_type")),
                raw_path=f"/mapping/{node_id}/message/metadata/content_references/{index}/{entry_index}",
                metadata=_sanitize_metadata(item),
            )
    for index, item in enumerate(_list(metadata.get("search_result_groups"))):
        if not isinstance(item, Mapping):
            continue
        yield CitationRef(
            title=_optional_str(item.get("title")),
            url=_optional_str(item.get("url")),
            source="search_result_groups",
            citation_type=_optional_str(item.get("type")) or "search_result_group",
            start_ix=_optional_int(item.get("start_ix")),
            end_ix=_optional_int(item.get("end_ix")),
            citation_format_type=_optional_str(item.get("citation_format_type")),
            raw_path=f"/mapping/{node_id}/message/metadata/search_result_groups/{index}",
            metadata=_sanitize_metadata(item),
        )


def _extract_visible_parts(message: Mapping[str, Any], node_id: str) -> str:
    content = message.get("content")
    if not isinstance(content, Mapping):
        raise BackendCaptureShapeError("visible message content must be an object", details={"node_id": node_id})
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise BackendCaptureShapeError("visible content.parts must be a list", details={"node_id": node_id})
    if not all(isinstance(part, str) for part in parts):
        raise BackendCaptureShapeError("visible content.parts must contain only strings", details={"node_id": node_id})
    return "".join(parts)


def _is_visible_text_message(message: Mapping[str, Any]) -> bool:
    role = _message_role(message)
    content = message.get("content")
    content_type = content.get("content_type") if isinstance(content, Mapping) else None
    return role in {"user", "assistant"} and content_type == "text"


def _is_hidden_internal(message: Mapping[str, Any]) -> bool:
    role = _message_role(message)
    content = message.get("content")
    content_type = content.get("content_type") if isinstance(content, Mapping) else None
    return role == "tool" or (role == "assistant" and content_type in {"code", "thoughts", "reasoning_recap", "model_editable_context"})


def _is_deep_research_exchange(facts: _GroupFacts) -> bool:
    return facts.visible_user and facts.visible_final_assistant and facts.hidden_internal and facts.citation_or_search_metadata


def _has_citation_or_search_metadata(message: Mapping[str, Any]) -> bool:
    metadata = _message_metadata(message)
    if _list(metadata.get("citations")):
        return True
    if _list(metadata.get("search_result_groups")):
        return True
    for item in _list(metadata.get("content_references")):
        if isinstance(item, Mapping) and item.get("type") in {"grouped_webpages", "sources_footnote"}:
            return True
    return False


def _message_role(message: Mapping[str, Any]) -> str | None:
    author = message.get("author")
    role = author.get("role") if isinstance(author, Mapping) else None
    return role if isinstance(role, str) else None


def _message_metadata(message: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _model_for_message(metadata: Mapping[str, Any], default_model: ModelRef | None) -> ModelRef | None:
    slug = _optional_str(metadata.get("model_slug"))
    if slug is None:
        return default_model
    return ModelRef(slug, default_model.display if default_model is not None else None)


def _message_id(message: Mapping[str, Any], node_id: str) -> str:
    message_id = message.get("id")
    return message_id if isinstance(message_id, str) and message_id else node_id


def _parent_id(node: Mapping[str, Any]) -> str | None:
    parent = node.get("parent")
    return parent if isinstance(parent, str) else None


def _created_at(message: Mapping[str, Any]) -> datetime | None:
    raw = message.get("create_time")
    if isinstance(raw, int | float):
        return datetime.fromtimestamp(raw, tz=UTC)
    if isinstance(raw, str) and raw:
        value = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _load_backend_raw(raw_path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackendCaptureShapeError("backend raw JSON could not be parsed") from exc
    if not isinstance(raw, dict):
        raise BackendCaptureShapeError("backend raw JSON must be an object")
    return raw


def _validate_fetch_meta(meta: BackendFetchMeta) -> None:
    if meta.status < 200 or meta.status >= 300:
        raise BackendCaptureShapeError("backend fetch returned non-2xx status", details={"status": meta.status, "content_type": meta.content_type})
    if meta.content_type is None or "application/json" not in meta.content_type.lower():
        raise BackendCaptureShapeError("backend fetch did not return JSON", details={"status": meta.status, "content_type": meta.content_type})


def _content_type(result: FetchResult) -> str | None:
    for key, value in result.headers.items():
        if str(key).lower() == "content-type":
            return str(value)
    return None


def _fetch_bytes_written(result: FetchResult, raw_tmp: Path) -> int:
    if result.body_path is not None and raw_tmp.exists():
        return raw_tmp.stat().st_size
    return len(result.body_bytes or b"")


def _channel_monotonic(tab: TabLease) -> float:
    monotonic = getattr(tab.channel, "monotonic", None)
    if callable(monotonic):
        return float(monotonic())
    return time.monotonic()


def _require_conversation_id(conv: ConversationRef) -> str:
    if conv.conversation_id is None:
        raise BackendCaptureShapeError("capture requires a persisted conversation id")
    return conv.conversation_id


def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _append_unique(values: tuple[str, ...], item: str) -> tuple[str, ...]:
    return values if item in values else (*values, item)


def _dedupe_attachments(items: tuple[AttachmentRef, ...]) -> tuple[AttachmentRef, ...]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[AttachmentRef] = []
    for item in items:
        key = (item.source_kind, item.source_ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return tuple(deduped)


def _dedupe_citations(items: tuple[CitationRef, ...]) -> tuple[CitationRef, ...]:
    seen: set[tuple[str | None, str | None, str, str]] = set()
    deduped: list[CitationRef] = []
    for item in items:
        key = (item.url, item.title, item.source, item.raw_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return tuple(deduped)


def _sanitize_metadata(value: Any) -> JsonValue:
    if isinstance(value, Mapping):
        sanitized: dict[str, JsonValue] = {}
        for key, nested in value.items():
            text_key = str(key)
            lowered = text_key.lower()
            if lowered in {"authorization", "cookie", "headers", "request_headers"} or lowered.startswith("oai-"):
                continue
            sanitized[text_key] = _sanitize_metadata(nested)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return repr(value)


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


__all__ = [
    "BackendFetchMeta",
    "BackendTopLevel",
    "CaptureResult",
    "HeaderBundle",
    "REQUIRED_CAPTURE_HEADERS",
    "SendContext",
    "acquire_backend_headers",
    "capture_conversation",
    "fallback_capture_ui",
    "iter_current_branch_records",
    "stream_backend_conversation",
    "validate_backend_shape",
]
