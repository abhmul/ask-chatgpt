"""Stateless conversation identity parsing and canonical URL helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

_CHATGPT_HOST = "chatgpt.com"
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class ConversationRef:
    conversation_id: str | None
    url: str
    project_id: str | None = None
    title: str | None = None
    current_node: str | None = None
    default_model_slug: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_draft: bool = False


def _is_safe_token(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and bool(_SAFE_TOKEN_RE.fullmatch(value))


def _project_id_from_segment(segment: str) -> str | None:
    if not segment.startswith("g-p-"):
        return None
    project_id = segment[len("g-p-") :]
    return project_id if _is_safe_token(project_id) else None


def _split_canonical_path(path: str) -> list[str] | None:
    parts = [part for part in path.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    if any("%" in part for part in parts):
        # Conversation/project ids are plain safe tokens; encoded traversal or
        # encoded separators fail closed rather than being interpreted later.
        return None
    return parts


def _split_chatgpt_url(value: str) -> list[str] | None:
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if host != _CHATGPT_HOST:
        return None
    return _split_canonical_path(parsed.path)


def parse_conversation_address(value: str) -> ConversationRef | None:
    """Parse a bare id or supported chatgpt.com conversation URL safely."""

    raw = value.strip()
    if not raw:
        return None

    if "://" not in raw:
        if "/" in raw or "?" in raw or "#" in raw or not _is_safe_token(raw):
            return None
        return ConversationRef(conversation_id=raw, url=f"https://chatgpt.com/c/{raw}")

    parts = _split_chatgpt_url(raw)
    if parts is None:
        return None

    if len(parts) == 2 and parts[0] == "c" and _is_safe_token(parts[1]):
        conversation_id = parts[1]
        return ConversationRef(
            conversation_id=conversation_id,
            url=f"https://chatgpt.com/c/{conversation_id}",
        )

    if len(parts) == 4 and parts[0] == "g" and parts[2] == "c":
        project_id = _project_id_from_segment(parts[1])
        conversation_id = parts[3]
        if project_id is None or not _is_safe_token(conversation_id):
            return None
        return ConversationRef(
            conversation_id=conversation_id,
            url=f"https://chatgpt.com/g/g-p-{project_id}/c/{conversation_id}",
            project_id=project_id,
        )

    return None


def parse_project_address(value: str) -> str | None:
    """Parse a project URL or token and return the bare project id."""

    raw = value.strip()
    if not raw:
        return None

    if "://" not in raw:
        project_id = raw.removeprefix("g-p-")
        return project_id if _is_safe_token(project_id) else None

    parts = _split_chatgpt_url(raw)
    if parts is None or len(parts) < 2 or parts[0] != "g":
        return None
    return _project_id_from_segment(parts[1])


def conversation_url(ref: ConversationRef) -> str:
    """Return the canonical web URL for a conversation reference."""

    if ref.conversation_id is None:
        return ref.url
    conversation_id = normalize_conversation_id(ref.conversation_id)
    if ref.project_id:
        project_id = parse_project_address(ref.project_id)
        if project_id is None:
            raise ValueError(f"invalid project id: {ref.project_id!r}")
        return f"https://chatgpt.com/g/g-p-{project_id}/c/{conversation_id}"
    return f"https://chatgpt.com/c/{conversation_id}"


def backend_conversation_url(conversation_id: str) -> str:
    """Return the canonical backend conversation endpoint for a chat id."""

    return f"https://chatgpt.com/backend-api/conversation/{normalize_conversation_id(conversation_id)}"


def normalize_conversation_id(value: str) -> str:
    """Extract and validate the canonical conversation id or raise ValueError."""

    ref = parse_conversation_address(value)
    if ref is None or ref.conversation_id is None:
        raise ValueError(f"invalid conversation address: {value!r}")
    return ref.conversation_id


def resolve_conv_or_alias(value: str | ConversationRef, store: object) -> ConversationRef:
    """E2 stub: alias resolution requires the Store/index.json layer."""

    raise NotImplementedError("resolve_conv_or_alias: implemented in M4-E2 store")


__all__ = [
    "ConversationRef",
    "backend_conversation_url",
    "conversation_url",
    "normalize_conversation_id",
    "parse_conversation_address",
    "parse_project_address",
    "resolve_conv_or_alias",
]
