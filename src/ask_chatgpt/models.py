"""Canonical public data model for the offline-core rewrite."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict

from ask_chatgpt.identity import ConversationRef

JsonValue: TypeAlias = (
    type(None)
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)
TurnStatus: TypeAlias = Literal["complete", "partial", "error"]
TurnRole: TypeAlias = Literal["user", "assistant"]
CaptureSource: TypeAlias = Literal[
    "backend_api", "copy_button", "katex_annotation", "dom_text"
]
CaptureFidelity: TypeAlias = Literal[
    "canonical", "ui_copy", "math_annotation_reconstructed", "lossy_dom_text"
]
AttachmentSourceKind: TypeAlias = Literal[
    "user_upload",
    "file_reference",
    "generated_asset",
    "code_execution_output",
    "unknown",
]
AttachmentDownloadState: TypeAlias = Literal[
    "pending", "downloaded", "not_downloadable", "unsupported", "error"
]
CitationSource: TypeAlias = Literal[
    "citations", "content_references", "search_result_groups", "unknown"
]

_TURN_STATUSES = {"complete", "partial", "error"}
_TURN_ROLES = {"user", "assistant"}
_CAPTURE_SOURCES = {"backend_api", "copy_button", "katex_annotation", "dom_text"}
_CAPTURE_FIDELITIES = {
    "canonical",
    "ui_copy",
    "math_annotation_reconstructed",
    "lossy_dom_text",
}
_ATTACHMENT_SOURCE_KINDS = {
    "user_upload",
    "file_reference",
    "generated_asset",
    "code_execution_output",
    "unknown",
}
_ATTACHMENT_DOWNLOAD_STATES = {
    "pending",
    "downloaded",
    "not_downloadable",
    "unsupported",
    "error",
}
_CITATION_SOURCES = {
    "citations",
    "content_references",
    "search_result_groups",
    "unknown",
}


@dataclass(frozen=True)
class ModelRef:
    slug: str | None
    display: str | None


@dataclass(frozen=True)
class AttachmentRef:
    source_kind: AttachmentSourceKind
    source_ref: str | None
    raw_path: str
    filename: str | None
    mime: str | None
    bytes: int | None
    sha256: str | None
    local_path: str | None
    download_state: AttachmentDownloadState
    metadata: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        if self.source_kind not in _ATTACHMENT_SOURCE_KINDS:
            raise ValueError(f"invalid attachment source_kind: {self.source_kind!r}")
        if self.download_state not in _ATTACHMENT_DOWNLOAD_STATES:
            raise ValueError(f"invalid attachment download_state: {self.download_state!r}")
        if not self.raw_path:
            raise ValueError("attachment raw_path must be non-empty")


@dataclass(frozen=True)
class CitationRef:
    title: str | None
    url: str | None
    source: CitationSource
    citation_type: str | None
    start_ix: int | None
    end_ix: int | None
    citation_format_type: str | None
    raw_path: str
    metadata: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        if self.source not in _CITATION_SOURCES:
            raise ValueError(f"invalid citation source: {self.source!r}")
        if not self.raw_path:
            raise ValueError("citation raw_path must be non-empty")


@dataclass(frozen=True)
class TurnRecord:
    conversation_id: str
    conversation_url: str
    project_id: str | None
    message_id: str
    parent_id: str | None
    turn_index: int | None
    role: TurnRole
    content_markdown: str
    model: ModelRef | None
    active_tools: tuple[str, ...]
    kind: str
    created_at: datetime | None
    attachments: tuple[AttachmentRef, ...]
    citations: tuple[CitationRef, ...]
    status: TurnStatus
    partial: bool
    user_message_id: str | None = None
    turn_exchange_id: str | None = None
    client_send_id: str | None = None
    supersedes_message_id: str | None = None
    capture_source: CaptureSource = "backend_api"
    fidelity: CaptureFidelity = "canonical"
    error: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "active_tools", tuple(self.active_tools))
        object.__setattr__(self, "attachments", tuple(self.attachments))
        object.__setattr__(self, "citations", tuple(self.citations))

        if self.status not in _TURN_STATUSES:
            raise ValueError(f"invalid turn status: {self.status!r}")
        if not isinstance(self.partial, bool):
            raise ValueError("partial must be a bool")
        if self.role not in _TURN_ROLES:
            raise ValueError(f"invalid turn role: {self.role!r}")
        if self.capture_source not in _CAPTURE_SOURCES:
            raise ValueError(f"invalid capture_source: {self.capture_source!r}")
        if self.fidelity not in _CAPTURE_FIDELITIES:
            raise ValueError(f"invalid fidelity: {self.fidelity!r}")
        if self.partial is not (self.status != "complete"):
            raise ValueError('partial must be False iff status == "complete"')
        if not self.message_id:
            raise ValueError("message_id must be non-empty")
        if self.turn_index is not None and self.turn_index < 0:
            raise ValueError("turn_index must be non-negative or None")
        if self.message_id.startswith("local:"):
            self._validate_pending_local_stub()
        else:
            self._validate_backend_identity_shape()

    def _validate_pending_local_stub(self) -> None:
        if not self.client_send_id:
            raise ValueError("local pending message_id requires client_send_id")
        if self.message_id != f"local:{self.client_send_id}":
            raise ValueError("local pending message_id must match client_send_id")
        if self.role != "user":
            raise ValueError("local pending stub must be a user turn")
        if self.turn_index is not None:
            raise ValueError("local pending stub must have turn_index=None")
        if self.created_at is not None:
            raise ValueError("local pending stub must have created_at=None")
        if self.status != "partial" or self.partial is not True:
            raise ValueError("local pending stub must be status='partial' and partial=True")

    def _validate_backend_identity_shape(self) -> None:
        if self.turn_index is None:
            raise ValueError("turn_index=None is reserved for local pending stubs")


@dataclass(frozen=True)
class Transcript:
    conversation: ConversationRef
    turns: tuple[TurnRecord, ...]
    raw_mapping_path: Path | None
    transcript_path: Path | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "turns", tuple(self.turns))


class SelectorMap(TypedDict):
    composer: str
    tools_button: str
    message_turn: str
    user_turn: str
    assistant_turn: str
    copy_button: str
    stop_button: str
    send_button_unverified_no_input: str
    radix_portal: str
    model_picker_trigger_candidates: str


@dataclass(frozen=True)
class SendTimeouts:
    idle_wait_s: float
    composer_wait_s: float
    submit_verify_s: float
    attachment_upload_s: float


@dataclass(frozen=True)
class AttachmentSpec:
    path: Path
    display_name: str | None = None
    mime: str | None = None


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    cdp_endpoint: str
    browser: str | None
    protocol_version: str | None
    websocket_url_present: bool
    error_code: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class StatusReport:
    ok: bool
    cdp: PreflightResult | None
    signed_in: bool | None
    login_or_challenge: bool | None
    selector_valid: bool
    conversations: int | None
    blocking_code: str | None
    details: Mapping[str, JsonValue]


__all__ = [
    "AttachmentRef",
    "AttachmentSpec",
    "CaptureFidelity",
    "CaptureSource",
    "CitationRef",
    "JsonValue",
    "ModelRef",
    "PreflightResult",
    "SelectorMap",
    "SendTimeouts",
    "StatusReport",
    "Transcript",
    "TurnRecord",
    "TurnRole",
    "TurnStatus",
]
