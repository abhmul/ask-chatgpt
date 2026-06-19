"""Offline transcript persistence for ask-chatgpt."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
import warnings
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from ask_chatgpt.errors import ConversationNotFoundError, StoreError, StoreWarning
from ask_chatgpt.identity import ConversationRef, conversation_url, parse_conversation_address
from ask_chatgpt.models import AttachmentRef, CitationRef, ModelRef, Transcript, TurnRecord

try:  # pragma: no cover - Linux in CI; fallback is for portability only.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ConversationPaths:
    root: Path
    transcript_jsonl: Path
    raw_mapping_json: Path
    attachments_dir: Path
    gitignore: Path


class Store:
    def __init__(
        self,
        data_dir: str | Path | None = None,
        *,
        env: Mapping[str, str] = os.environ,
    ) -> None:
        self._explicit_data_dir = Path(data_dir).expanduser() if data_dir is not None else None
        self._env = dict(env)

    def resolve_data_dir(self) -> Path:
        if self._explicit_data_dir is not None:
            return self._explicit_data_dir
        env_dir = self._env.get("ASK_CHATGPT_DATA_DIR")
        if env_dir:
            return Path(env_dir).expanduser()
        cwd = Path.cwd().resolve()
        for candidate in (cwd, *cwd.parents):
            if (candidate / "pyproject.toml").is_file():
                return candidate / "cache"
        return cwd / "cache"

    def resolve_conversation(self, address: str | ConversationRef) -> ConversationRef:
        if isinstance(address, ConversationRef):
            return address
        raw = address.strip()
        if not raw:
            raise ConversationNotFoundError("empty conversation alias")
        if "://" in raw:
            parsed_url = parse_conversation_address(raw)
            if parsed_url is None:
                raise ConversationNotFoundError("conversation URL is not supported")
            return parsed_url
        index = self._read_index_lenient()
        target = _lookup_index_target(index, raw)
        if target is not None:
            return _conversation_ref_from_index(index, target)
        parsed_id = parse_conversation_address(raw)
        if parsed_id is not None and _looks_like_bare_conversation_id(raw):
            return parsed_id
        raise ConversationNotFoundError("conversation alias not found")

    def ensure_conversation(self, ref: ConversationRef) -> ConversationPaths:
        if ref.conversation_id is None:
            raise StoreError("cannot persist a draft conversation without a conversation_id")
        conversation_id = _validate_conversation_id(ref.conversation_id)
        root = self.resolve_data_dir() / "conversations" / conversation_id
        transcript = root / "transcript.jsonl"
        raw_mapping = root / "raw-mapping.json"
        attachments = root / "attachments"
        gitignore = root / ".gitignore"
        try:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            attachments.mkdir(exist_ok=True, mode=0o700)
            transcript.touch(exist_ok=True)
            if gitignore.exists():
                text = gitignore.read_text(encoding="utf-8")
                if "attachments/" not in text.splitlines():
                    with gitignore.open("a", encoding="utf-8") as handle:
                        if text and not text.endswith("\n"):
                            handle.write("\n")
                        handle.write("attachments/\n")
            else:
                gitignore.write_text("attachments/\n", encoding="utf-8")
        except OSError as exc:  # pragma: no cover - exercised by public StoreError boundary
            raise StoreError("failed to ensure conversation layout") from exc
        return ConversationPaths(root, transcript, raw_mapping, attachments, gitignore)

    def put_conversation_ref(self, ref: ConversationRef) -> None:
        if ref.conversation_id is None:
            raise StoreError("cannot index a draft conversation without a conversation_id")
        conversation_id = _validate_conversation_id(ref.conversation_id)
        self.resolve_data_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
        index = self._read_index_lenient()
        conversations = index.setdefault("conversations", {})
        if not isinstance(conversations, dict):
            conversations = {}
            index["conversations"] = conversations
        prior = conversations.get(conversation_id)
        entry = dict(prior) if isinstance(prior, dict) else {}
        entry.update(
            {
                "conversation_id": conversation_id,
                "url": conversation_url(ref),
                "project_id": ref.project_id,
                "title": ref.title,
                "model": {"slug": ref.default_model_slug, "display": None},
                "current_node": ref.current_node,
                "last_updated": _datetime_to_rfc3339(ref.updated_at),
            }
        )
        conversations[conversation_id] = entry
        self._write_index_atomic(index)

    def begin_send(
        self,
        ref: ConversationRef,
        prompt: str,
        *,
        model: ModelRef | None,
        active_tools: Iterable[str],
    ) -> TurnRecord:
        if ref.conversation_id is None:
            raise StoreError("cannot begin send for a draft conversation without a conversation_id")
        self.ensure_conversation(ref)
        self.put_conversation_ref(ref)
        client_send_id = uuid.uuid4().hex
        stub = TurnRecord(
            conversation_id=ref.conversation_id,
            conversation_url=conversation_url(ref),
            project_id=ref.project_id,
            message_id=f"local:{client_send_id}",
            parent_id=None,
            turn_index=None,
            role="user",
            content_markdown=prompt,
            model=model,
            active_tools=tuple(active_tools),
            kind="normal",
            created_at=None,
            attachments=(),
            citations=(),
            status="partial",
            partial=True,
            user_message_id=None,
            turn_exchange_id=None,
            client_send_id=client_send_id,
            supersedes_message_id=None,
            capture_source="backend_api",
            fidelity="canonical",
            error=None,
        )
        self.upsert_turn(stub)
        return stub

    def commit_send(self, client_send_id: str, canonical_user: TurnRecord) -> None:
        if not client_send_id:
            raise StoreError("client_send_id must be non-empty")
        if canonical_user.role != "user" or canonical_user.message_id.startswith("local:"):
            raise StoreError("canonical committed send must be a backend user record")
        record = replace(
            canonical_user,
            client_send_id=client_send_id,
            supersedes_message_id=f"local:{client_send_id}",
        )
        self.upsert_turn(record)

    def write_raw_mapping_atomic(self, conversation_id: str, raw_tmp: Path) -> Path:
        ref = _conversation_ref_from_id(conversation_id)
        paths = self.ensure_conversation(ref)
        try:
            candidate = json.loads(Path(raw_tmp).read_text(encoding="utf-8"))
            raw = _validated_backend_raw(candidate)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise StoreError("invalid raw mapping candidate") from exc
        payload = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tmp = paths.root / f".{paths.raw_mapping_json.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        try:
            with tmp.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, paths.raw_mapping_json)
            _fsync_dir(paths.root)
        except OSError as exc:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise StoreError("failed to atomically write raw mapping") from exc
        return paths.raw_mapping_json

    def upsert_turn(self, record: TurnRecord) -> None:
        self.upsert_many([record])

    def upsert_many(self, records: Iterable[TurnRecord]) -> None:
        pending = list(records)
        if not pending:
            return
        by_conversation: dict[str, list[TurnRecord]] = {}
        for record in pending:
            by_conversation.setdefault(record.conversation_id, []).append(record)
        for conversation_id, group in by_conversation.items():
            first = group[0]
            ref = ConversationRef(
                conversation_id=conversation_id,
                url=first.conversation_url,
                project_id=first.project_id,
            )
            paths = self.ensure_conversation(ref)
            payload = b"".join(_turn_to_jsonl(record) for record in group)
            try:
                with self._conversation_lock(conversation_id):
                    with paths.transcript_jsonl.open("ab") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
            except OSError as exc:
                raise StoreError("failed to append transcript records") from exc

    def load_transcript(
        self,
        address: str | ConversationRef,
        *,
        include_pending: bool = False,
    ) -> Transcript:
        ref = self.resolve_conversation(address)
        paths = self.ensure_conversation(ref)
        records: list[TurnRecord] = []
        try:
            raw = paths.transcript_jsonl.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise StoreError("failed to read transcript") from exc
        lines = text.splitlines()
        invalid: list[tuple[int, BaseException]] = []
        for index, line in enumerate(lines):
            if not line:
                continue
            try:
                records.append(_turn_from_json_obj(json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                invalid.append((index, exc))
        if invalid:
            final_line_is_torn = bool(lines) and not text.endswith("\n")
            if len(invalid) == 1 and invalid[0][0] == len(lines) - 1 and final_line_is_torn:
                warnings.warn(
                    StoreWarning("ignored one torn trailing transcript line"),
                    stacklevel=2,
                )
            else:
                raise StoreError("failed to parse transcript") from invalid[0][1]
        last_by_message_id: dict[str, TurnRecord] = {}
        for record in records:
            last_by_message_id[record.message_id] = record
        visible = _visible_records(last_by_message_id.values(), include_pending=include_pending)
        return Transcript(
            conversation=ref,
            turns=tuple(visible),
            raw_mapping_path=paths.raw_mapping_json if paths.raw_mapping_json.exists() else None,
            transcript_path=paths.transcript_jsonl,
        )

    def render_markdown(self, transcript: Transcript) -> str:
        visible = _visible_records(transcript.turns, include_pending=False)
        sections = []
        for record in visible:
            heading = "User" if record.role == "user" else "Assistant"
            sections.append(f"## {heading}\n\n{record.content_markdown}")
        if not sections:
            return ""
        rendered = "\n\n".join(sections)
        return rendered.rstrip("\n") + "\n"

    def record_partial(
        self,
        ref: ConversationRef,
        *,
        client_send_id: str | None,
        partial_markdown: str,
        error: BaseException,
        capture_source: str = "dom_text",
        fidelity: str = "lossy_dom_text",
        message_id: str | None = None,
        user_message_id: str | None = None,
    ) -> TurnRecord:
        if ref.conversation_id is None:
            raise StoreError("cannot record partial for a draft conversation without a conversation_id")
        existing = self.load_transcript(ref, include_pending=True).turns
        numeric_indexes = [record.turn_index for record in existing if record.turn_index is not None]
        turn_index = (max(numeric_indexes) + 1) if numeric_indexes else 0
        record = TurnRecord(
            conversation_id=ref.conversation_id,
            conversation_url=conversation_url(ref),
            project_id=ref.project_id,
            message_id=message_id or f"partial:{uuid.uuid4().hex}",
            parent_id=None,
            turn_index=turn_index,
            role="assistant",
            content_markdown=partial_markdown,
            model=None,
            active_tools=(),
            kind="normal",
            created_at=None,
            attachments=(),
            citations=(),
            status="partial" if partial_markdown else "error",
            partial=True,
            user_message_id=user_message_id,
            turn_exchange_id=None,
            client_send_id=client_send_id,
            supersedes_message_id=None,
            capture_source=capture_source,  # type: ignore[arg-type]
            fidelity=fidelity,  # type: ignore[arg-type]
            error={"type": type(error).__name__, "message": _redact_error_text(str(error))},
        )
        self.upsert_turn(record)
        return record

    def attachment_path(self, conversation_id: str, ref: AttachmentRef) -> Path:
        paths = self.ensure_conversation(_conversation_ref_from_id(conversation_id))
        safe_name = _safe_attachment_filename(ref.filename)
        stable_key = "|".join(
            [ref.source_kind, ref.source_ref or "", ref.raw_path, ref.sha256 or ""]
        )
        prefix = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]
        candidate = paths.attachments_dir / f"{prefix}__{safe_name}"
        try:
            candidate.resolve().relative_to(paths.attachments_dir.resolve())
        except ValueError as exc:
            raise StoreError("attachment path escaped conversation attachments directory") from exc
        return candidate

    def atomic_write_payload(self, out: str | Path, content: str | bytes) -> Path:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = _payload_bytes(content)
        tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        try:
            with tmp.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            _fsync_dir(path.parent)
        except OSError as exc:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise StoreError("failed to atomically write payload") from exc
        return path

    def emit_payload(
        self,
        content: str | bytes,
        *,
        out: str | Path | None = None,
        stdout: Any | None = None,
    ) -> Path | None:
        _emit_stdout(content, sys.stdout if stdout is None else stdout)
        if out is None:
            return None
        return self.atomic_write_payload(out, content)

    @contextmanager
    def _conversation_lock(self, conversation_id: str):
        lock_dir = self.resolve_data_dir() / "conversations" / conversation_id
        lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = lock_dir / ".transcript.lock"
        with lock_path.open("a+b") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @property
    def _index_path(self) -> Path:
        return self.resolve_data_dir() / "index.json"

    def _read_index_lenient(self) -> dict[str, Any]:
        path = self._index_path
        if not path.exists():
            return _default_index()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _default_index()
        if not isinstance(loaded, dict):
            return _default_index()
        index = _default_index()
        for key in ("aliases", "sessions", "conversations"):
            value = loaded.get(key)
            if isinstance(value, dict):
                index[key] = value
        index["schema_version"] = 1
        return index

    def _write_index_atomic(self, index: Mapping[str, Any]) -> None:
        path = self._index_path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        payload = json.dumps(index, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            with tmp.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            _fsync_dir(path.parent)
        except OSError as exc:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise StoreError("failed to atomically write index") from exc


_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_SENSITIVE_TEXT_PARTS = (
    "authorization",
    "bearer",
    "cookie",
    "oai-",
    "password",
    "prompt",
    "secret",
    "token",
    "canary",
)


def _redact_error_text(text: str) -> str:
    lowered = text.lower()
    if any(part in lowered for part in _SENSITIVE_TEXT_PARTS):
        return "<redacted>"
    return text


def _safe_attachment_filename(filename: str | None) -> str:
    if not filename:
        return "attachment"
    raw = filename.strip()
    parts = [part for chunk in raw.split("/") for part in chunk.split("\\")]
    if (
        Path(raw).is_absolute()
        or raw.startswith("\\")
        or re.match(r"^[A-Za-z]:", raw) is not None
        or any(part in {"..", ""} for part in parts)
    ):
        raise StoreError("unsafe attachment filename")
    safe = _SAFE_FILENAME_CHARS.sub("_", "_".join(parts)).strip("._")
    return safe or "attachment"


def _payload_bytes(content: str | bytes) -> bytes:
    return content if isinstance(content, bytes) else content.encode("utf-8")


def _emit_stdout(content: str | bytes, stdout: Any) -> None:
    if isinstance(content, bytes):
        binary = getattr(stdout, "buffer", None)
        if binary is not None:
            binary.write(content)
            binary.flush()
            return
        stdout.write(content)
        stdout.flush()
        return
    stdout.write(content)
    stdout.flush()


def emit_payload(
    content: str | bytes,
    *,
    out: str | Path | None = None,
    stdout: Any | None = None,
) -> Path | None:
    return Store().emit_payload(content, out=out, stdout=stdout)


def _looks_like_bare_conversation_id(value: str) -> bool:
    return any(character.isdigit() for character in value) or len(value) >= 16


def _lookup_index_target(index: Mapping[str, Any], value: str) -> str | None:
    for key in ("aliases", "sessions"):
        mapping = index.get(key)
        if isinstance(mapping, Mapping):
            target = mapping.get(value)
            if isinstance(target, str) and target:
                return target
    return None


def _conversation_ref_from_index(index: Mapping[str, Any], target: str) -> ConversationRef:
    conversations = index.get("conversations")
    entry = conversations.get(target) if isinstance(conversations, Mapping) else None
    if isinstance(entry, Mapping):
        conversation_id = entry.get("conversation_id") or target
        url = entry.get("url")
        if not isinstance(conversation_id, str) or not isinstance(url, str):
            return _conversation_ref_from_id(target)
        model = entry.get("model")
        default_model_slug = model.get("slug") if isinstance(model, Mapping) else None
        if not isinstance(default_model_slug, str):
            default_model_slug = None
        return ConversationRef(
            conversation_id=conversation_id,
            url=url,
            project_id=entry.get("project_id") if isinstance(entry.get("project_id"), str) else None,
            title=entry.get("title") if isinstance(entry.get("title"), str) else None,
            current_node=entry.get("current_node") if isinstance(entry.get("current_node"), str) else None,
            default_model_slug=default_model_slug,
        )
    parsed = parse_conversation_address(target)
    if parsed is not None:
        return parsed
    raise ConversationNotFoundError("conversation alias target not found")


def _validate_conversation_id(conversation_id: str) -> str:
    parsed = parse_conversation_address(conversation_id)
    if parsed is None or parsed.conversation_id != conversation_id:
        raise StoreError("invalid conversation_id")
    return conversation_id


def _conversation_ref_from_id(conversation_id: str) -> ConversationRef:
    return parse_conversation_address(_validate_conversation_id(conversation_id))  # type: ignore[return-value]


def _validated_backend_raw(candidate: Any) -> dict[str, Any]:
    raw = _unwrap_backend_raw(candidate)
    mapping = raw.get("mapping")
    current_node = raw.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(current_node, str) or not current_node:
        raise ValueError("raw mapping candidate requires top-level mapping and current_node")
    return _drop_sensitive_raw_keys(raw)


def _unwrap_backend_raw(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("raw mapping candidate must be a JSON object")
    if "mapping" in candidate and "current_node" in candidate:
        return candidate
    for key in ("body", "json", "data", "response"):
        nested = candidate.get(key)
        if isinstance(nested, dict) and "mapping" in nested and "current_node" in nested:
            return nested
    raise ValueError("raw mapping candidate requires top-level mapping and current_node")


def _drop_sensitive_raw_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _drop_sensitive_raw_keys(nested)
            for key, nested in value.items()
            if not _is_sensitive_raw_key(str(key))
        }
    if isinstance(value, list):
        return [_drop_sensitive_raw_keys(item) for item in value]
    return value


def _is_sensitive_raw_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in {"authorization", "cookie", "headers", "request_headers"} or lowered.startswith("oai-")


def _is_pending_local_stub(record: TurnRecord) -> bool:
    return record.message_id.startswith("local:") and record.turn_index is None


def _visible_records(records: Iterable[TurnRecord], *, include_pending: bool) -> list[TurnRecord]:
    materialized = list(records)
    if not include_pending:
        superseded_ids = {
            record.supersedes_message_id
            for record in materialized
            if record.supersedes_message_id is not None
        }
        materialized = [
            record
            for record in materialized
            if not _is_pending_local_stub(record) and record.message_id not in superseded_ids
        ]
    materialized.sort(key=_turn_sort_key)
    return materialized


def _turn_sort_key(record: TurnRecord) -> tuple[bool, int | None, str, str]:
    created_at = "" if record.created_at is None else record.created_at.isoformat()
    return (record.turn_index is None, record.turn_index, created_at, record.message_id)


def _turn_to_jsonl(record: TurnRecord) -> bytes:
    return (
        json.dumps(_turn_to_json_obj(record), ensure_ascii=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _turn_to_json_obj(record: TurnRecord) -> dict[str, Any]:
    return {field.name: _json_clean(getattr(record, field.name)) for field in fields(TurnRecord)}


def _json_clean(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ModelRef):
        return {"slug": value.slug, "display": value.display}
    if isinstance(value, AttachmentRef):
        return {
            "source_kind": value.source_kind,
            "source_ref": value.source_ref,
            "raw_path": value.raw_path,
            "filename": value.filename,
            "mime": value.mime,
            "bytes": value.bytes,
            "sha256": value.sha256,
            "local_path": value.local_path,
            "download_state": value.download_state,
            "metadata": _json_clean(value.metadata),
        }
    if isinstance(value, CitationRef):
        return {
            "title": value.title,
            "url": value.url,
            "source": value.source,
            "citation_type": value.citation_type,
            "start_ix": value.start_ix,
            "end_ix": value.end_ix,
            "citation_format_type": value.citation_format_type,
            "raw_path": value.raw_path,
            "metadata": _json_clean(value.metadata),
        }
    if isinstance(value, Mapping):
        return {str(key): _json_clean(nested) for key, nested in value.items()}
    if isinstance(value, tuple | list):
        return [_json_clean(item) for item in value]
    return value


def _turn_from_json_obj(data: Mapping[str, Any]) -> TurnRecord:
    model_data = data.get("model")
    model = None if model_data is None else ModelRef(**model_data)
    return TurnRecord(
        conversation_id=data["conversation_id"],
        conversation_url=data["conversation_url"],
        project_id=data["project_id"],
        message_id=data["message_id"],
        parent_id=data["parent_id"],
        turn_index=data["turn_index"],
        role=data["role"],
        content_markdown=data["content_markdown"],
        model=model,
        active_tools=tuple(data["active_tools"]),
        kind=data["kind"],
        created_at=_datetime_from_rfc3339(data["created_at"]),
        attachments=tuple(AttachmentRef(**item) for item in data["attachments"]),
        citations=tuple(CitationRef(**item) for item in data["citations"]),
        status=data["status"],
        partial=data["partial"],
        user_message_id=data["user_message_id"],
        turn_exchange_id=data["turn_exchange_id"],
        client_send_id=data["client_send_id"],
        supersedes_message_id=data["supersedes_message_id"],
        capture_source=data["capture_source"],
        fidelity=data["fidelity"],
        error=data["error"],
    )


def _datetime_from_rfc3339(value: str | None) -> datetime | None:
    if value is None:
        return None
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


def _default_index() -> dict[str, Any]:
    return {"schema_version": 1, "aliases": {}, "sessions": {}, "conversations": {}}


def _datetime_to_rfc3339(value: object) -> str | None:
    if value is None:
        return None
    return value.isoformat()  # type: ignore[attr-defined]


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = ["ConversationPaths", "Store", "emit_payload"]
