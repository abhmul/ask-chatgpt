"""Stdlib loopback mock ChatGPT web UI for tests."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from hashlib import sha256
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import re
import threading
import time
from typing import Any
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen


LOOPBACK_HOST = "127.0.0.1"
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_FAILURE_MODES = frozenset(
    {
        "login_required",
        "session_not_found",
        "model_unavailable",
        "response_truncated",
        "rate_limited",
        "selector_unavailable",
        "download_unsupported",
        "upload_unsupported",
    }
)
_COPY_MODES = frozenset({"ok", "missing", "wrong", "stale", "truncated"})
_DOWNLOAD_MODES = frozenset({"ok", "missing", "delayed", "wrong_older", "corrupt", "truncated", "collision", "unsupported", "opaque"})
_FENCED_MODES = frozenset({"ok", "canonical", "missing_end", "bad_hash", "changed_and_unchanged", "oversized"})
_LAYOUT_VARIANTS = frozenset({"stable", "virtualized"})
_UPLOAD_MODES = frozenset({"ok", "unsupported", "reject_size_type", "corrupt"})
_RECALL_MODES = frozenset({"planted_token"})
_RECALL_NO_TOKEN_SENTINEL = "NO_TOKEN_RECALLED"
_DEFAULT_STREAM_READS = 2
_DEFAULT_PATCH_FILES = {
    "src/mock_changed.txt": "synthetic changed file from mock ChatGPT fixture\n",
    "tests/fixtures/expected-output.txt": "deterministic patch bundle payload\n",
}
_DEFAULT_UNCHANGED_FILES = {
    "docs/unchanged-note.txt": "synthetic unchanged file listed for validator coverage\n",
}
_OVERSIZED_THRESHOLD_BYTES = 64
_FIXED_ZIP_DATE_TIME = (2024, 1, 1, 0, 0, 0)


def _bundle_file_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8")


def _validated_bundle_path(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or normalized.startswith("/") or ".." in parts:
        raise ValueError(f"unsafe bundle path: {path!r}")
    return "/".join(parts)


def _as_path_tuple(value: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=_FIXED_ZIP_DATE_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    return info


def build_mock_patch_zip(
    changed_files: dict[str, str | bytes] | None = None,
    *,
    unchanged_files: dict[str, str | bytes] | None = None,
    deleted_files: list[str] | tuple[str, ...] | str | None = None,
    operations: dict[str, str] | None = None,
    embed_manifest: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    """Build a deterministic synthetic patch zip and its manifest."""
    raw_changed = _DEFAULT_PATCH_FILES if changed_files is None else changed_files
    raw_unchanged = {} if unchanged_files is None else unchanged_files
    raw_deleted = _as_path_tuple(deleted_files)
    raw_operations = {} if operations is None else operations
    changed = [(_validated_bundle_path(path), _bundle_file_bytes(data)) for path, data in raw_changed.items()]
    unchanged = [(_validated_bundle_path(path), _bundle_file_bytes(data)) for path, data in raw_unchanged.items()]
    deleted = [_validated_bundle_path(path) for path in raw_deleted]
    changed.sort(key=lambda item: item[0])
    unchanged.sort(key=lambda item: item[0])
    deleted.sort()
    files: list[dict[str, Any]] = []
    for path, data in changed:
        entry: dict[str, Any] = {"path": path, "size": len(data), "sha256": sha256(data).hexdigest(), "status": "changed"}
        operation = raw_operations.get(path)
        if operation is not None:
            entry["operation"] = str(operation)
        files.append(entry)
    for path, data in unchanged:
        files.append({"path": path, "size": len(data), "sha256": sha256(data).hexdigest(), "status": "unchanged"})
    for path in deleted:
        files.append({"path": path, "size": 0, "sha256": None, "status": "deleted", "operation": "deleted"})
    manifest: dict[str, Any] = {
        "version": 1,
        "files": files,
        "total_byte_count": sum(item["size"] for item in files),
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        if embed_manifest:
            archive.writestr(_zip_info("manifest.json"), manifest_bytes)
        for path, data in changed:
            archive.writestr(_zip_info(path), data)
    return buffer.getvalue(), manifest


def build_mock_fenced_patch_bundle(
    mode: str = "ok",
    *,
    changed_files: dict[str, str | bytes] | None = None,
    deleted_files: list[str] | tuple[str, ...] | str | None = None,
    operations: dict[str, str] | None = None,
) -> tuple[str, bytes, dict[str, Any]]:
    """Build the fenced base64url patch-bundle payload used by the fixture."""
    fenced_mode = _validated_fenced_mode(mode)
    deleted_paths = _as_path_tuple(deleted_files)
    unchanged_files = _DEFAULT_UNCHANGED_FILES if fenced_mode == "changed_and_unchanged" else None
    embed_manifest = bool(deleted_paths) or fenced_mode == "changed_and_unchanged"
    zip_bytes, zip_manifest = build_mock_patch_zip(
        changed_files=changed_files,
        unchanged_files=unchanged_files,
        deleted_files=deleted_paths,
        operations=operations,
        embed_manifest=embed_manifest,
    )
    actual_zip_sha = sha256(zip_bytes).hexdigest()
    display_sha = "0" * 64 if fenced_mode == "bad_hash" else actual_zip_sha
    manifest = dict(zip_manifest)
    manifest["zip_byte_count"] = len(zip_bytes)
    manifest["zip_sha256"] = display_sha
    if fenced_mode == "oversized":
        manifest["oversized"] = True
        manifest["oversized_threshold_bytes"] = _OVERSIZED_THRESHOLD_BYTES
    encoded = base64.urlsafe_b64encode(zip_bytes).decode("ascii").rstrip("=")
    lines = [
        "BEGIN_PATCH_BUNDLE",
        f"ZIP_BYTE_COUNT {len(zip_bytes)}",
        f"ZIP_SHA256 {display_sha}",
        f"BASE64URL {encoded}",
    ]
    if fenced_mode != "missing_end":
        lines.append("END_PATCH_BUNDLE")
    return "\n".join(lines), zip_bytes, manifest


@dataclass(slots=True)
class Artifact:
    artifact_id: str
    filename: str
    body: bytes = field(repr=False)
    manifest: dict[str, Any]
    source_turn_id: str
    mode: str

    def as_json(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "byte_count": len(self.body),
            "sha256": sha256(self.body).hexdigest(),
            "manifest": self.manifest,
            "source_turn_id": self.source_turn_id,
            "mode": self.mode,
        }


@dataclass(slots=True)
class Turn:
    role: str
    text: str
    turn_id: str
    complete: bool = True
    streaming: bool = False
    truncated: bool = False
    stream_reads_remaining: int = 0
    download_mode: str | None = None
    download_artifact_ids: list[str] = field(default_factory=list)
    download_delay_reads_remaining: int = 0

    def as_json(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "turn_id": self.turn_id,
            "complete": self.complete,
            "streaming": self.streaming,
            "truncated": self.truncated,
            "stream_reads_remaining": self.stream_reads_remaining,
            "download_mode": self.download_mode,
            "download_artifact_ids": list(self.download_artifact_ids),
            "download_delay_reads_remaining": self.download_delay_reads_remaining,
        }


@dataclass(slots=True)
class Conversation:
    conversation_ref: str
    title: str
    turns: list[Turn] = field(default_factory=list)
    layout_variant: str = "stable"
    copy_mode: str = "ok"

    def as_json(self) -> dict[str, Any]:
        return {
            "conversation_ref": self.conversation_ref,
            "title": self.title,
            "turns": [turn.as_json() for turn in self.turns],
            "layout_variant": self.layout_variant,
            "copy_mode": self.copy_mode,
        }


@dataclass(slots=True)
class NextScript:
    text: str
    conversation_ref: str | None = None
    streaming: bool = False
    complete: bool = True
    stream_reads: int = _DEFAULT_STREAM_READS
    failure_mode: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "conversation_ref": self.conversation_ref,
            "streaming": self.streaming,
            "complete": self.complete,
            "stream_reads": self.stream_reads,
            "failure_mode": self.failure_mode,
            "extra": dict(self.extra),
        }


class MockChatGPTState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conversations: dict[str, Conversation] = {}
        self._artifacts: dict[str, Artifact] = {}
        self._conversation_counter = 0
        self._turn_counter = 0
        self._artifact_counter = 0
        self._selected_ref: str | None = None
        self._last_prompt: str | None = None
        self._next_script: NextScript | None = None
        self._failure_mode: str | None = None
        self._unavailable_model = "mock-reasoning"
        self._upload_mode = "ok"
        self._uploads: list[dict[str, Any]] = []

    def reset(self) -> None:
        with self._lock:
            self._conversations.clear()
            self._artifacts.clear()
            self._conversation_counter = 0
            self._turn_counter = 0
            self._artifact_counter = 0
            self._selected_ref = None
            self._last_prompt = None
            self._next_script = None
            self._failure_mode = None
            self._unavailable_model = "mock-reasoning"
            self._upload_mode = "ok"
            self._uploads.clear()

    def snapshot(self, *, advance_stream_ref: str | None = None) -> dict[str, Any]:
        with self._lock:
            if advance_stream_ref is not None:
                conversation = self._conversations.get(advance_stream_ref)
                if conversation is not None:
                    self._advance_streaming_turns(conversation)
            return {
                "conversations": {
                    ref: conversation.as_json()
                    for ref, conversation in self._conversations.items()
                },
                "conversation_refs": list(self._conversations),
                "selected_conversation_ref": self._selected_ref,
                "last_prompt": self._last_prompt,
                "next_script": self._next_script.as_json() if self._next_script else None,
                "failure_mode": self._failure_mode,
                "unavailable_model": self._unavailable_model,
                "artifacts": {artifact_id: artifact.as_json() for artifact_id, artifact in self._artifacts.items()},
                "upload_mode": self._upload_mode,
                "uploads": [dict(upload) for upload in self._uploads],
                "last_upload": dict(self._uploads[-1]) if self._uploads else None,
            }

    def create_conversation(self, conversation_ref: str | None = None) -> str:
        with self._lock:
            if conversation_ref is None:
                while True:
                    self._conversation_counter += 1
                    candidate = f"conv-{self._conversation_counter}"
                    if candidate not in self._conversations:
                        conversation_ref = candidate
                        break
            conversation_ref = self._validate_ref(conversation_ref)
            if conversation_ref not in self._conversations:
                title = f"Mock conversation {conversation_ref}"
                self._conversations[conversation_ref] = Conversation(conversation_ref, title)
            self._selected_ref = conversation_ref
            return conversation_ref

    def select_or_create(self, conversation_ref: str) -> str:
        return self.create_conversation(conversation_ref)

    def apply_script(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a /__script__ payload.

        Text-only payloads preserve the T3 behavior: they script the next send.
        Payloads with turns seed a full conversation immediately for reader tests.
        Mode-only payloads set page/failure state.
        """
        with self._lock:
            mode = _optional_str(payload.get("failure_mode") or payload.get("failure") or payload.get("mode"))
            upload_mode = _optional_str(payload.get("upload_mode"))
            if upload_mode is not None:
                self._upload_mode = _validated_upload_mode(upload_mode)
            if mode is not None:
                self._set_failure_mode_unlocked(mode, payload)

            result: dict[str, Any] = {"failure_mode": self._failure_mode, "upload_mode": self._upload_mode}
            if "turns" in payload:
                result["seeded_conversation_ref"] = self._seed_conversation_unlocked(payload)
                return result
            if mode == "response_truncated" and "text" in payload and payload.get("conversation_ref") not in (None, ""):
                result["seeded_conversation_ref"] = self._seed_response_truncated_unlocked(payload)
                return result
            if "text" in payload:
                script = self._next_script_from_payload(payload)
                self._next_script = script
                result["next_script"] = script.as_json()
                return result
            if mode is not None or upload_mode is not None:
                result["next_script"] = None
                return result
            raise ValueError("text is required")

    def set_next_script(self, payload: dict[str, Any]) -> NextScript:
        result = self.apply_script(payload)
        script = result.get("next_script")
        if not isinstance(script, dict) or self._next_script is None:
            raise ValueError("text is required")
        return self._next_script

    def append_exchange(self, prompt: str, conversation_ref: str | None) -> str:
        prompt = str(prompt)
        with self._lock:
            if conversation_ref in (None, ""):
                conversation_ref = self.create_conversation()
            else:
                conversation_ref = self._validate_ref(conversation_ref)
                if conversation_ref not in self._conversations:
                    self._conversations[conversation_ref] = Conversation(
                        conversation_ref, f"Mock conversation {conversation_ref}"
                    )
                self._selected_ref = conversation_ref

            conversation = self._conversations[conversation_ref]
            self._last_prompt = prompt
            conversation.turns.append(Turn("user", prompt, self._next_turn_id()))

            script = self._script_for(conversation_ref)
            if script is None:
                assistant_turn = Turn(
                    "assistant",
                    f"[mock] you said: {prompt}",
                    self._next_turn_id(),
                    complete=True,
                    streaming=False,
                )
            else:
                self._next_script = None
                streaming = script.streaming
                truncated = script.failure_mode == "response_truncated" or _as_bool(
                    script.extra.get("truncated", script.extra.get("response_truncated")), default=False
                )
                complete = script.complete
                stream_reads_remaining = 0
                if streaming:
                    complete = False
                    stream_reads_remaining = max(0, script.stream_reads)
                if truncated:
                    streaming = False
                    complete = False
                    stream_reads_remaining = 0
                if "layout_variant" in script.extra or "dom_variant" in script.extra:
                    conversation.layout_variant = _validated_layout_variant(
                        script.extra.get("layout_variant", script.extra.get("dom_variant"))
                    )
                if "copy_mode" in script.extra:
                    conversation.copy_mode = _validated_copy_mode(script.extra.get("copy_mode"))
                assistant_text = _recall_text_from_history(script.extra, conversation.turns[:-1])
                if assistant_text is None:
                    assistant_text = script.text
                if "fenced_mode" in script.extra:
                    assistant_text = _text_with_fenced_bundle(assistant_text, script.extra.get("fenced_mode"), script.extra)
                assistant_turn = Turn(
                    "assistant",
                    assistant_text,
                    self._next_turn_id(),
                    complete=complete,
                    streaming=streaming,
                    truncated=truncated,
                    stream_reads_remaining=stream_reads_remaining,
                )
                if "download_mode" in script.extra:
                    self._attach_download_artifacts_unlocked(conversation, assistant_turn, script.extra.get("download_mode"), script.extra)

            conversation.turns.append(assistant_turn)
            return conversation_ref

    def _next_script_from_payload(self, payload: dict[str, Any]) -> NextScript:
        if "text" not in payload:
            raise ValueError("text is required")
        raw_ref = payload.get("conversation_ref")
        conversation_ref = None if raw_ref in (None, "") else self._validate_ref(str(raw_ref))
        core_keys = {
            "text",
            "conversation_ref",
            "streaming",
            "complete",
            "stream_reads",
            "failure_mode",
            "failure",
            "mode",
        }
        return NextScript(
            text=str(payload["text"]),
            conversation_ref=conversation_ref,
            streaming=_as_bool(payload.get("streaming"), default=False),
            complete=_as_bool(payload.get("complete"), default=True),
            stream_reads=_as_int(payload.get("stream_reads"), default=_DEFAULT_STREAM_READS),
            failure_mode=_optional_str(payload.get("failure_mode") or payload.get("failure") or payload.get("mode")),
            extra={key: value for key, value in payload.items() if key not in core_keys},
        )

    def _seed_conversation_unlocked(self, payload: dict[str, Any]) -> str:
        turns = payload.get("turns")
        if not isinstance(turns, list):
            raise ValueError("turns must be a list")
        conversation_ref = self._conversation_ref_from_payload_unlocked(payload)
        conversation = self._conversations[conversation_ref]
        conversation.layout_variant = _validated_layout_variant(payload.get("layout_variant", payload.get("dom_variant")))
        conversation.copy_mode = _validated_copy_mode(payload.get("copy_mode"))
        default_stream_reads = _as_int(payload.get("stream_reads"), default=_DEFAULT_STREAM_READS)
        assistant_indices = [
            index
            for index, turn_payload in enumerate(turns)
            if isinstance(turn_payload, dict) and str(turn_payload.get("role") or "assistant") == "assistant"
        ]
        latest_assistant_index = assistant_indices[-1] if assistant_indices else None
        conversation.turns = []
        for index, turn_payload in enumerate(turns):
            turn = self._turn_from_payload_unlocked(turn_payload, default_stream_reads=default_stream_reads)
            if turn.role == "assistant" and isinstance(turn_payload, dict):
                fenced_mode = turn_payload.get("fenced_mode") if "fenced_mode" in turn_payload else None
                if fenced_mode is None and index == latest_assistant_index and "fenced_mode" in payload:
                    fenced_mode = payload.get("fenced_mode")
                if fenced_mode is not None:
                    fenced_extra = turn_payload if "fenced_mode" in turn_payload else payload
                    turn.text = _text_with_fenced_bundle(turn.text, fenced_mode, fenced_extra)
                download_mode = turn_payload.get("download_mode") if "download_mode" in turn_payload else None
                if download_mode is None and index == latest_assistant_index and "download_mode" in payload:
                    download_mode = payload.get("download_mode")
                    download_extra = payload
                else:
                    download_extra = turn_payload
                if download_mode is not None:
                    self._attach_download_artifacts_unlocked(conversation, turn, download_mode, download_extra)
            conversation.turns.append(turn)
        return conversation_ref

    def _seed_response_truncated_unlocked(self, payload: dict[str, Any]) -> str:
        conversation_ref = self._conversation_ref_from_payload_unlocked(payload)
        conversation = self._conversations[conversation_ref]
        conversation.layout_variant = _validated_layout_variant(payload.get("layout_variant", payload.get("dom_variant")))
        conversation.copy_mode = _validated_copy_mode(payload.get("copy_mode"))
        conversation.turns = [
            Turn(
                "assistant",
                str(payload.get("text") or ""),
                self._next_turn_id(),
                complete=False,
                streaming=False,
                truncated=True,
            )
        ]
        return conversation_ref

    def _conversation_ref_from_payload_unlocked(self, payload: dict[str, Any]) -> str:
        raw_ref = payload.get("conversation_ref")
        conversation_ref = self.create_conversation(None if raw_ref in (None, "") else str(raw_ref))
        self._selected_ref = conversation_ref
        return conversation_ref

    def _turn_from_payload_unlocked(self, payload: Any, *, default_stream_reads: int) -> Turn:
        if not isinstance(payload, dict):
            raise ValueError("each turn must be an object")
        role = str(payload.get("role") or "assistant")
        if role not in {"user", "assistant"}:
            raise ValueError(f"unsupported turn role: {role!r}")
        streaming = _as_bool(payload.get("streaming"), default=False)
        truncated = _as_bool(payload.get("truncated", payload.get("response_truncated")), default=False)
        complete = _as_bool(payload.get("complete"), default=not streaming)
        stream_reads = _as_int(
            payload.get("stream_reads", payload.get("stream_reads_remaining")),
            default=default_stream_reads,
        )
        stream_reads_remaining = 0
        if streaming:
            complete = False
            stream_reads_remaining = max(0, stream_reads)
        if truncated:
            streaming = False
            complete = False
            stream_reads_remaining = 0
        turn_id = str(payload.get("turn_id") or self._next_turn_id())
        return Turn(
            role,
            str(payload.get("text") or ""),
            turn_id,
            complete=complete,
            streaming=streaming,
            truncated=truncated,
            stream_reads_remaining=stream_reads_remaining,
        )

    def _attach_download_artifacts_unlocked(
        self,
        conversation: Conversation,
        turn: Turn,
        mode_value: Any,
        extra: dict[str, Any] | None = None,
    ) -> None:
        mode = _validated_download_mode(mode_value)
        patch_kwargs = _patch_kwargs_from_extra(extra)
        turn.download_mode = mode
        if mode in {"missing", "unsupported"}:
            return
        if mode == "wrong_older":
            for previous in reversed(conversation.turns):
                if previous.role == "assistant" and previous.download_artifact_ids:
                    turn.download_artifact_ids = [previous.download_artifact_ids[0]]
                    return
            turn.download_artifact_ids = [
                self._create_artifact_unlocked(
                    source_turn_id="older-turn",
                    mode=mode,
                    filename="patch-bundle-older.zip",
                    **patch_kwargs,
                )
            ]
            return
        if mode == "collision":
            filename = "patch-bundle-collision.zip"
            turn.download_artifact_ids = [
                self._create_artifact_unlocked(source_turn_id=turn.turn_id, mode=mode, filename=filename),
                self._create_artifact_unlocked(
                    source_turn_id=turn.turn_id,
                    mode=mode,
                    filename=filename,
                    changed_files={"src/collision-second.txt": "second artifact sharing a filename\n"},
                ),
            ]
            return
        turn.download_artifact_ids = [self._create_artifact_unlocked(source_turn_id=turn.turn_id, mode=mode, **patch_kwargs)]
        if mode == "delayed":
            turn.download_delay_reads_remaining = 2

    def _create_artifact_unlocked(
        self,
        *,
        source_turn_id: str,
        mode: str,
        filename: str | None = None,
        changed_files: dict[str, str | bytes] | None = None,
        deleted_files: list[str] | tuple[str, ...] | str | None = None,
        operations: dict[str, str] | None = None,
    ) -> str:
        self._artifact_counter += 1
        artifact_id = f"artifact-{self._artifact_counter}"
        zip_bytes, manifest = build_mock_patch_zip(
            changed_files=changed_files,
            deleted_files=deleted_files,
            operations=operations,
        )
        body = zip_bytes
        if mode == "corrupt":
            body = b"not a valid zip artifact\n"
        elif mode == "truncated":
            body = zip_bytes[: max(1, len(zip_bytes) // 3)]
        safe_filename = filename or f"patch-bundle-{artifact_id}.zip"
        self._artifacts[artifact_id] = Artifact(
            artifact_id=artifact_id,
            filename=safe_filename,
            body=body,
            manifest=manifest,
            source_turn_id=source_turn_id,
            mode=mode,
        )
        return artifact_id

    def get_artifact(self, artifact_id: str) -> Artifact:
        with self._lock:
            artifact = self._artifacts.get(artifact_id)
            if artifact is None:
                raise ValueError(f"unknown artifact: {artifact_id}")
            return artifact

    def record_upload(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            filename = _upload_basename(str(payload.get("filename") or payload.get("name") or ""))
            if not filename:
                raise ValueError("filename is required")
            size = _as_int(payload.get("size"), default=0)
            content_type = str(payload.get("content_type") or payload.get("type") or "")
            if not content_type and filename.lower().endswith(".zip"):
                content_type = "application/zip"
            sha_value = str(payload.get("sha256") or "")
            mode = _validated_upload_mode(self._upload_mode)
            if mode == "ok":
                record = {
                    "filename": filename,
                    "size": size,
                    "sha256": sha_value,
                    "content_type": content_type,
                    "status": "ok",
                }
            elif mode == "reject_size_type":
                record = {
                    "filename": filename,
                    "size": size,
                    "sha256": sha_value,
                    "content_type": content_type,
                    "status": "rejected",
                    "reason": "file size/type rejected by mock",
                }
            elif mode == "corrupt":
                record = {
                    "filename": filename,
                    "size": size,
                    "sha256": "0" * 64,
                    "original_sha256": sha_value,
                    "content_type": content_type,
                    "status": "corrupt",
                    "reason": "corrupted upload recorded by mock",
                }
            else:
                record = {
                    "filename": filename,
                    "size": size,
                    "sha256": sha_value,
                    "content_type": content_type,
                    "status": "unsupported",
                    "reason": "file upload unsupported by mock",
                }
            self._uploads.append(record)
            result = {"ok": record["status"] == "ok", "status": record["status"]}
            if "reason" in record:
                result["reason"] = record["reason"]
            return result

    def _set_failure_mode_unlocked(self, mode: str, payload: dict[str, Any]) -> None:
        normalized = mode.strip().lower()
        if normalized in {"normal", "none", "ok", "clear"}:
            self._failure_mode = None
            return
        if normalized not in _FAILURE_MODES:
            raise ValueError(f"unsupported failure mode: {mode}")
        self._failure_mode = normalized
        if normalized == "model_unavailable":
            self._unavailable_model = str(payload.get("unavailable_model") or "mock-reasoning")
        if normalized == "upload_unsupported":
            self._upload_mode = "unsupported"

    @staticmethod
    def _advance_streaming_turns(conversation: Conversation) -> None:
        for turn in conversation.turns:
            if turn.role != "assistant":
                continue
            if turn.download_delay_reads_remaining > 0:
                turn.download_delay_reads_remaining -= 1
            if not turn.streaming:
                continue
            if turn.stream_reads_remaining > 0:
                turn.stream_reads_remaining -= 1
            else:
                turn.streaming = False
                turn.complete = True

    def _script_for(self, conversation_ref: str) -> NextScript | None:
        if self._next_script is None:
            return None
        if self._next_script.conversation_ref in (None, conversation_ref):
            return self._next_script
        return None

    def _next_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn-{self._turn_counter}"

    @staticmethod
    def _validate_ref(value: str) -> str:
        ref = str(value)
        if not _SAFE_REF.fullmatch(ref):
            raise ValueError(f"invalid conversation_ref: {value!r}")
        return ref


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _as_int(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected integer value, got {value!r}") from exc


def _validated_layout_variant(value: Any) -> str:
    variant = "stable" if value in (None, "") else str(value).strip().lower()
    if variant not in _LAYOUT_VARIANTS:
        raise ValueError(f"unsupported layout variant: {value!r}")
    return variant


def _validated_copy_mode(value: Any) -> str:
    mode = "ok" if value in (None, "") else str(value).strip().lower()
    if mode not in _COPY_MODES:
        raise ValueError(f"unsupported copy_mode: {value!r}")
    return mode


def _validated_download_mode(value: Any) -> str:
    mode = "ok" if value in (None, "") else str(value).strip().lower()
    if mode not in _DOWNLOAD_MODES:
        raise ValueError(f"unsupported download_mode: {value!r}")
    return mode


def _validated_fenced_mode(value: Any) -> str:
    mode = "ok" if value in (None, "") else str(value).strip().lower()
    if mode not in _FENCED_MODES:
        raise ValueError(f"unsupported fenced_mode: {value!r}")
    return mode


def _validated_upload_mode(value: Any) -> str:
    mode = "ok" if value in (None, "") else str(value).strip().lower()
    if mode not in _UPLOAD_MODES:
        raise ValueError(f"unsupported upload_mode: {value!r}")
    return mode


def _patch_kwargs_from_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return {}
    kwargs: dict[str, Any] = {}
    changed_files = extra.get("patch_changed_files")
    if changed_files not in (None, ""):
        if not isinstance(changed_files, dict):
            raise ValueError("patch_changed_files must be an object mapping paths to text")
        kwargs["changed_files"] = {str(path): data for path, data in changed_files.items()}
    deleted_files = extra.get("patch_deleted_files")
    if deleted_files not in (None, ""):
        kwargs["deleted_files"] = _as_path_tuple(deleted_files)
    operations = extra.get("patch_operations")
    if operations not in (None, ""):
        if not isinstance(operations, dict):
            raise ValueError("patch_operations must be an object mapping paths to operations")
        kwargs["operations"] = {str(path): str(operation) for path, operation in operations.items()}
    return kwargs


def _text_with_fenced_bundle(prefix: str, mode_value: Any, extra: dict[str, Any] | None = None) -> str:
    fenced_text, _zip_bytes, _manifest = build_mock_fenced_patch_bundle(
        _validated_fenced_mode(mode_value),
        **_patch_kwargs_from_extra(extra),
    )
    clean_prefix = str(prefix).rstrip()
    return fenced_text if not clean_prefix else clean_prefix + "\n\n" + fenced_text


def _recall_text_from_history(extra: dict[str, Any], prior_turns: list[Turn]) -> str | None:
    mode = _optional_str(extra.get("recall_mode"))
    if mode is None:
        return None
    normalized_mode = mode.strip().lower()
    if normalized_mode not in _RECALL_MODES:
        raise ValueError(f"unsupported recall_mode: {mode}")
    if normalized_mode == "planted_token":
        return _recall_planted_token(extra.get("recall_pattern"), prior_turns)
    raise ValueError(f"unsupported recall_mode: {mode}")


def _recall_planted_token(pattern_value: Any, prior_turns: list[Turn]) -> str:
    pattern_text = _optional_str(pattern_value)
    if pattern_text is None:
        raise ValueError("recall_pattern is required for recall_mode='planted_token'")
    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        raise ValueError(f"invalid recall_pattern: {exc}") from exc

    for turn in reversed(prior_turns):
        matches = list(pattern.finditer(turn.text))
        for match in reversed(matches):
            token = _token_from_recall_match(match)
            if token:
                return token
    return _RECALL_NO_TOKEN_SENTINEL


def _token_from_recall_match(match: re.Match[str]) -> str:
    group_names = match.re.groupindex
    if "token" in group_names:
        value = match.group("token")
        if value:
            return value
    if match.groups():
        for value in match.groups():
            if value:
                return value
    return match.group(0)


def _upload_basename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def _selected_conversation(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    selected = snapshot.get("selected_conversation_ref")
    if selected is None:
        return None
    return snapshot["conversations"].get(selected)


def _render_chat_list(snapshot: dict[str, Any]) -> str:
    items = []
    for ref, conversation in snapshot["conversations"].items():
        safe_ref = escape(ref, quote=True)
        title = escape(str(conversation["title"]))
        items.append(
            '<li><a data-testid="mock-chat-item" '
            f'data-conversation-ref="{safe_ref}" href="/c/{quote(ref)}">{title}</a></li>'
        )
    return "\n".join(items)


def _latest_completed_assistant_index(turns: list[dict[str, Any]]) -> int | None:
    latest: int | None = None
    for index, turn in enumerate(turns):
        if (
            turn.get("role") == "assistant"
            and turn.get("complete")
            and not turn.get("streaming")
            and not turn.get("truncated")
        ):
            latest = index
    return latest


def _copy_text_for(conversation: dict[str, Any], latest_index: int, mode: str) -> str:
    turns = conversation["turns"]
    latest_text = str(turns[latest_index]["text"])
    if mode == "ok":
        return latest_text
    if mode == "wrong":
        for index, turn in enumerate(turns):
            if index != latest_index and turn.get("role") == "assistant":
                return str(turn["text"])
        return "BOOBYTRAP-WRONG-COPY"
    if mode == "truncated":
        return latest_text[: max(1, len(latest_text) // 2)] if latest_text else ""
    return ""


def _render_markers(turn: dict[str, Any]) -> str:
    if turn.get("role") != "assistant":
        return ""
    markers = ""
    if turn.get("streaming"):
        markers += '<span data-testid="assistant-streaming" aria-label="Assistant streaming">Streaming</span>'
    if turn.get("complete"):
        markers += '<span data-testid="assistant-turn-complete" aria-label="Assistant turn complete">Complete</span>'
    if turn.get("truncated"):
        markers += '<span data-testid="assistant-truncated" aria-label="Assistant response truncated">Truncated</span>'
    return markers


def _render_copy_button(conversation: dict[str, Any], latest_index: int) -> str:
    mode = str(conversation.get("copy_mode") or "ok")
    if mode == "missing":
        return ""
    copy_text = _copy_text_for(conversation, latest_index, mode)
    mode_attr = escape(mode, quote=True)
    text_attr = escape(copy_text, quote=True)
    return (
        '<button data-testid="mock-copy-button" type="button" '
        f'data-copy-mode="{mode_attr}" data-copy-text="{text_attr}" '
        'aria-label="Copy latest assistant response">Copy</button>'
    )


def _render_download_artifacts(turn: dict[str, Any], artifacts: dict[str, Any]) -> str:
    if turn.get("role") != "assistant":
        return ""
    mode = str(turn.get("download_mode") or "")
    if mode == "unsupported":
        return '<div data-testid="download-unsupported" role="status">Download artifacts unsupported</div>'
    if mode == "missing":
        return ""
    if _as_int(turn.get("download_delay_reads_remaining"), default=0) > 0:
        return '<div data-testid="download-delayed" role="status">Download artifact preparing</div>'
    rendered = []
    for artifact_id in turn.get("download_artifact_ids") or []:
        artifact = artifacts.get(str(artifact_id))
        if not artifact:
            continue
        safe_artifact_id = escape(str(artifact_id), quote=True)
        filename = escape(str(artifact["filename"]), quote=True)
        source_turn_id = escape(str(artifact["source_turn_id"]), quote=True)
        artifact_mode = escape(str(artifact["mode"]), quote=True)
        byte_count = escape(str(artifact["byte_count"]), quote=True)
        digest = escape(str(artifact["sha256"]), quote=True)
        href = "/download/" + quote(str(artifact_id))
        if artifact["mode"] == "opaque":
            rendered.append(
                '<div data-testid="mock-artifact-card" '
                f'data-artifact-id="{safe_artifact_id}" data-artifact-mode="{artifact_mode}">'
                '<a data-testid="mock-download-artifact" '
                f'href="{href}">Download the patch bundle</a></div>'
            )
            continue
        rendered.append(
            '<div data-testid="mock-artifact-card" '
            f'data-artifact-id="{safe_artifact_id}" data-artifact-mode="{artifact_mode}">'
            '<a data-testid="mock-download-artifact" '
            f'href="{href}" download="{filename}" data-artifact-id="{safe_artifact_id}" '
            f'data-filename="{filename}" data-byte-count="{byte_count}" data-sha256="{digest}" '
            f'data-source-turn-id="{source_turn_id}">Download {filename}</a></div>'
        )
    return "".join(rendered)


def _render_turns(conversation: dict[str, Any] | None, artifacts: dict[str, Any]) -> str:
    if conversation is None:
        return ""
    ref = escape(str(conversation["conversation_ref"]), quote=True)
    turns = conversation["turns"]
    layout_variant = str(conversation.get("layout_variant") or "stable")
    latest_completed = _latest_completed_assistant_index(turns)
    visible_virtualized_index = latest_completed if latest_completed is not None else (len(turns) - 1 if turns else None)
    rendered = []
    for index, turn in enumerate(turns):
        role = escape(str(turn["role"]), quote=True)
        turn_id = escape(str(turn["turn_id"]), quote=True)
        if layout_variant == "virtualized" and index != visible_virtualized_index:
            rendered.append(
                '<article data-testid="mock-virtualized-placeholder" data-virtualized="true" '
                f'data-turn-id="{turn_id}" data-conversation-ref="{ref}">Virtualized older turn</article>'
            )
            continue
        body = escape(str(turn["text"]))
        markers = _render_markers(turn)
        copy_button = _render_copy_button(conversation, latest_completed) if index == latest_completed else ""
        download_artifacts = _render_download_artifacts(turn, artifacts)
        data_layout = ' data-layout="virtualized-latest"' if layout_variant == "virtualized" else ""
        body_testid = "mock-message-content" if layout_variant == "virtualized" else "mock-message-body"
        rendered.append(
            '<article data-testid="mock-turn" '
            f'data-message-author-role="{role}" data-turn-id="{turn_id}" '
            f'data-conversation-ref="{ref}"{data_layout}>'
            f'<div data-testid="{body_testid}">{body}</div>{markers}{copy_button}{download_artifacts}</article>'
        )
    return "\n".join(rendered)


def _render_model_options(snapshot: dict[str, Any]) -> str:
    unavailable = str(snapshot.get("unavailable_model") or "") if snapshot.get("failure_mode") == "model_unavailable" else ""
    options = []
    for value, label, selected in (
        ("mock-default", "Mock default", True),
        ("mock-reasoning", "Mock reasoning", False),
    ):
        selected_attr = " selected" if selected else ""
        disabled_attr = ""
        if value == unavailable:
            disabled_attr = ' disabled data-disabled="true" aria-disabled="true"'
        options.append(
            f'<option data-testid="mock-model-option" value="{escape(value, quote=True)}"{selected_attr}{disabled_attr}>'
            f'{escape(label)}</option>'
        )
    return "\n        ".join(options)


def _render_upload_controls(snapshot: dict[str, Any]) -> str:
    mode = str(snapshot.get("upload_mode") or "ok")
    mode_attr = escape(mode, quote=True)
    if mode == "unsupported":
        return f"""
  <section data-testid="mock-upload-section" data-upload-mode="{mode_attr}" aria-label="Upload bundle">
    <div data-testid="upload-unsupported" role="status">File upload unsupported</div>
    <div data-testid="mock-upload-status" data-upload-status="unsupported" role="status">File upload unsupported</div>
  </section>"""
    return f"""
  <section data-testid="mock-upload-section" data-upload-mode="{mode_attr}" aria-label="Upload bundle">
    <label>Upload bundle
      <input data-testid="mock-upload-input" name="bundle" type="file" accept=".zip,application/zip">
    </label>
    <div data-testid="mock-upload-status" data-upload-status="idle" role="status">No upload recorded</div>
  </section>"""


def _render_conversation_not_found(conversation_ref: str) -> str:
    safe_ref = escape(conversation_ref, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Conversation not found</title></head>
<body>
<main data-testid="conversation-not-found" data-conversation-ref="{safe_ref}" role="alert">
  Conversation not found
</main>
</body>
</html>"""


def _render_page(snapshot: dict[str, Any]) -> str:
    conversation = _selected_conversation(snapshot)
    selected_ref = "" if conversation is None else str(conversation["conversation_ref"])
    selected_attr = escape(selected_ref, quote=True)
    failure_mode = snapshot.get("failure_mode")
    failure_attr = escape(str(failure_mode or ""), quote=True)
    chat_list = _render_chat_list(snapshot)
    turns = _render_turns(conversation, snapshot.get("artifacts", {}))
    model_options = _render_model_options(snapshot)
    upload_controls = _render_upload_controls(snapshot)
    login_wall = (
        '<section data-testid="login-wall" role="alert">Login required</section>'
        if failure_mode == "login_required"
        else ""
    )
    rate_limit = (
        '<div data-testid="rate-limit" data-retry-after-seconds="60" role="status">Rate limited; retry after 60 seconds</div>'
        if failure_mode == "rate_limited"
        else ""
    )
    selector_unavailable = (
        '<div data-testid="selector-unavailable" role="alert">Required composer selector unavailable</div>'
        if failure_mode == "selector_unavailable"
        else ""
    )
    download_unsupported = (
        '<div data-testid="download-unsupported" role="status">Download artifacts unsupported</div>'
        if failure_mode == "download_unsupported"
        else ""
    )
    composer = ""
    if failure_mode not in {"login_required", "selector_unavailable"}:
        composer = f"""
  <form data-testid="mock-composer-form" action="/__send__" method="post">
    <input type="hidden" name="conversation_ref" value="{selected_attr}">
    <label>Message
      <textarea data-testid="mock-composer" name="prompt" aria-label="Message composer"></textarea>
    </label>
    <button data-testid="mock-send-button" type="submit">Send</button>
  </form>"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mock ChatGPT</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1rem; }}
    textarea {{ display: block; width: min(48rem, 90vw); min-height: 6rem; }}
    [data-testid="mock-chat-list"] {{ min-height: 1rem; }}
    [data-testid="mock-turn"], [data-testid="mock-virtualized-placeholder"] {{ border: 1px solid #bbb; margin: 0.5rem 0; padding: 0.5rem; }}
    [data-testid="mock-virtualized-placeholder"] {{ color: #555; font-style: italic; }}
    [data-testid="mock-message-body"], [data-testid="mock-message-content"] {{ white-space: pre-wrap; }}
    [data-testid="mock-copy-button"], [data-testid="mock-download-artifact"] {{ margin-left: 0.5rem; }}
  </style>
</head>
<body>
<main data-testid="mock-ready-root" data-conversation-ref="{selected_attr}" data-failure-mode="{failure_attr}">
  <h1>Mock ChatGPT</h1>
  {login_wall}
  {rate_limit}
  {selector_unavailable}
  {download_unsupported}
  <nav aria-label="Conversations">
    <ol data-testid="mock-chat-list">
      {chat_list}
    </ol>
    <form action="/__new_chat__" method="post">
      <button data-testid="mock-new-chat-button" type="submit">New chat</button>
    </form>
  </nav>
  <section aria-label="Model">
    <label>Model
      <select data-testid="mock-model-menu" name="model">
        {model_options}
      </select>
    </label>
  </section>
  {upload_controls}
  <section data-testid="mock-turn-list" aria-label="Conversation turns">
    {turns}
  </section>{composer}
</main>
<script>
(function () {{
  document.addEventListener('click', async function (event) {{
    const target = event.target;
    if (!(target instanceof Element)) {{ return; }}
    const button = target.closest('[data-testid="mock-copy-button"]');
    if (!button) {{ return; }}
    if (button.getAttribute('data-copy-mode') === 'stale') {{ return; }}
    if (!navigator.clipboard || !navigator.clipboard.writeText) {{ return; }}
    await navigator.clipboard.writeText(button.getAttribute('data-copy-text') || '');
  }});
  const uploadInput = document.querySelector('[data-testid="mock-upload-input"]');
  if (uploadInput) {{
    uploadInput.addEventListener('change', async function () {{
      const status = document.querySelector('[data-testid="mock-upload-status"]');
      const file = uploadInput.files && uploadInput.files[0];
      if (!file) {{ return; }}
      try {{
        const bytes = await file.arrayBuffer();
        const digest = await crypto.subtle.digest('SHA-256', bytes);
        const hex = Array.from(new Uint8Array(digest)).map(function (byte) {{ return byte.toString(16).padStart(2, '0'); }}).join('');
        const contentType = file.type || (file.name.toLowerCase().endsWith('.zip') ? 'application/zip' : 'application/octet-stream');
        const response = await fetch('/__upload__', {{
          method: 'POST',
          headers: {{ 'content-type': 'application/json', 'accept': 'application/json' }},
          body: JSON.stringify({{ filename: file.name, size: file.size, sha256: hex, content_type: contentType }})
        }});
        const payload = await response.json();
        if (status) {{
          status.setAttribute('data-upload-status', payload.status || 'error');
          if (payload.reason) {{
            status.setAttribute('data-reason', payload.reason);
          }} else {{
            status.removeAttribute('data-reason');
          }}
          status.textContent = payload.reason ? String(payload.reason) : 'Upload ' + String(payload.status || 'error');
        }}
      }} catch (error) {{
        if (status) {{
          status.setAttribute('data-upload-status', 'error');
          status.setAttribute('data-reason', String(error));
          status.textContent = 'Upload error: ' + String(error);
        }}
      }}
    }});
  }}
}}());
</script>
</body>
</html>"""


def _json_bytes(payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, bytes, str]:
    return int(status), json.dumps(payload, sort_keys=True).encode("utf-8"), "application/json; charset=utf-8"


def _html_bytes(body: str, *, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, bytes, str]:
    return int(status), body.encode("utf-8"), "text/html; charset=utf-8"


class _LoopbackThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def _make_handler(state: MockChatGPTState) -> type[BaseHTTPRequestHandler]:
    class MockChatGPTHandler(BaseHTTPRequestHandler):
        server_version = "MockChatGPT/1"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _send_download(self, artifact: Artifact) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{artifact.filename}"')
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(artifact.body)))
            self.end_headers()
            if artifact.body:
                self.wfile.write(artifact.body)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("location", location)
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", "0")
            self.end_headers()

        def _payload(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length") or "0")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            content_type = (self.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            if content_type == "application/json":
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("JSON body must be an object")
                return value
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
            return {key: values[-1] if values else "" for key, values in parsed.items()}

        def do_GET(self) -> None:  # noqa: N802 - stdlib signature
            path = urlparse(self.path).path
            try:
                if path == "/":
                    status, body, content_type = _html_bytes(_render_page(state.snapshot()))
                elif path.startswith("/c/"):
                    ref = MockChatGPTState._validate_ref(unquote(path.removeprefix("/c/")))
                    if state.snapshot().get("failure_mode") == "session_not_found":
                        status, body, content_type = _html_bytes(
                            _render_conversation_not_found(ref), status=HTTPStatus.NOT_FOUND
                        )
                    else:
                        state.select_or_create(ref)
                        status, body, content_type = _html_bytes(_render_page(state.snapshot(advance_stream_ref=ref)))
                elif path == "/__inspect__":
                    status, body, content_type = _json_bytes(state.snapshot())
                elif path.startswith("/download/"):
                    artifact_id = unquote(path.removeprefix("/download/"))
                    self._send_download(state.get_artifact(artifact_id))
                    return
                elif path == "/favicon.ico":
                    status, body, content_type = int(HTTPStatus.NO_CONTENT), b"", "text/plain; charset=utf-8"
                else:
                    status, body, content_type = _json_bytes({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                status, body, content_type = _json_bytes({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            self._send(status, body, content_type)

        def do_POST(self) -> None:  # noqa: N802 - stdlib signature
            path = urlparse(self.path).path
            try:
                payload = self._payload()
                if path == "/__reset__":
                    state.reset()
                    status, body, content_type = _json_bytes({"ok": True, "state": state.snapshot()})
                    self._send(status, body, content_type)
                elif path == "/__script__":
                    result = state.apply_script(payload)
                    status, body, content_type = _json_bytes({"ok": True, **result})
                    self._send(status, body, content_type)
                elif path == "/__upload__":
                    result = state.record_upload(payload)
                    status, body, content_type = _json_bytes(result)
                    self._send(status, body, content_type)
                elif path == "/__new_chat__":
                    ref = state.create_conversation()
                    self._redirect(f"/c/{quote(ref)}")
                elif path == "/__send__":
                    if state.snapshot().get("failure_mode") == "rate_limited":
                        status, body, content_type = _html_bytes(_render_page(state.snapshot()))
                        self._send(status, body, content_type)
                    else:
                        prompt = str(payload.get("prompt") or payload.get("prompt_text") or payload.get("text") or "")
                        ref_value = payload.get("conversation_ref")
                        ref = None if ref_value in (None, "") else str(ref_value)
                        conversation_ref = state.append_exchange(prompt, ref)
                        self._redirect(f"/c/{quote(conversation_ref)}")
                else:
                    status, body, content_type = _json_bytes({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
                    self._send(status, body, content_type)
            except (ValueError, json.JSONDecodeError) as exc:
                status, body, content_type = _json_bytes({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                self._send(status, body, content_type)

    return MockChatGPTHandler


class MockChatGPTServer:
    """Loopback-only ephemeral-port mock ChatGPT server."""

    def __init__(self, *, host: str = LOOPBACK_HOST) -> None:
        if host != LOOPBACK_HOST:
            raise ValueError("mock ChatGPT server binds 127.0.0.1 only")
        self.host = host
        self.requested_port = 0
        self.state = MockChatGPTState()
        self._server: _LoopbackThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int | None = None

    @property
    def base_url(self) -> str:
        if self.port is None:
            raise RuntimeError("mock ChatGPT server is not started")
        return f"http://{self.host}:{self.port}"

    def url(self, path: str = "/") -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def start(self) -> MockChatGPTServer:
        if self._server is not None:
            return self
        handler = _make_handler(self.state)
        server = _LoopbackThreadingHTTPServer((self.host, self.requested_port), handler)
        bound_host, bound_port = server.server_address[:2]
        if bound_host != LOOPBACK_HOST or int(bound_port) == 0:
            server.server_close()
            raise RuntimeError("mock ChatGPT server failed to bind loopback ephemeral port")
        self._server = server
        self.port = int(bound_port)
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.05},
            name="mock-chatgpt-server",
            daemon=False,
        )
        self._thread = thread
        thread.start()
        self._wait_until_accepting()
        return self

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("mock ChatGPT server thread did not stop")

    def _wait_until_accepting(self, *, timeout_seconds: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            try:
                with urlopen(self.url("/__inspect__"), timeout=0.5) as response:
                    if response.status == HTTPStatus.OK:
                        return
            except (OSError, URLError) as exc:
                last_error = exc
                time.sleep(0.025)
        self.stop()
        raise RuntimeError("mock ChatGPT server did not become ready") from last_error

    def make_handle(self) -> MockChatGPTHandle:
        if self.port is None:
            raise RuntimeError("mock ChatGPT server is not started")
        return MockChatGPTHandle(
            base_url=self.base_url,
            host=self.host,
            port=self.port,
            requested_port=self.requested_port,
        )

    def __enter__(self) -> MockChatGPTServer:
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()


@dataclass(frozen=True, slots=True)
class MockChatGPTHandle:
    """HTTP control-plane wrapper returned by the pytest fixture."""

    base_url: str
    host: str
    port: int
    requested_port: int = 0

    def reset(self) -> None:
        self._request("POST", "/__reset__", {})

    def inspect(self) -> dict[str, Any]:
        return self._request("GET", "/__inspect__")

    def script_next_response(
        self,
        text: str,
        *,
        conversation_ref: str | None = None,
        streaming: bool = False,
        complete: bool = True,
        **failure_fields: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "text": text,
            "conversation_ref": conversation_ref,
            "streaming": streaming,
            "complete": complete,
        }
        payload.update(failure_fields)
        self._request("POST", "/__script__", payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"accept": "application/json"}
        if data is not None:
            headers["content-type"] = "application/json"
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"mock ChatGPT control request failed: {exc.code} {body}") from exc
        if not raw:
            return {}
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("mock ChatGPT control response was not a JSON object")
        return value


__all__ = ["LOOPBACK_HOST", "MockChatGPTHandle", "MockChatGPTServer", "build_mock_fenced_patch_bundle", "build_mock_patch_zip"]
