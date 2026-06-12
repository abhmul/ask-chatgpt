"""JSON-backed mapping from caller session identifiers to conversations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile

from ask_chatgpt.errors import AskChatGPTError


_BAD_FILE_ACTION = "Operator action: repair, replace, or delete the registry file and retry."
_BAD_ENTRY_ACTION = "Operator action: repair or delete the registry entry and retry."


@dataclass
class ConversationRef:
    conversation_ref: str
    url: str | None = None
    model_settings: dict | None = None


class SessionRegistry:
    _VERSION = 1
    _FILENAME = "sessions.json"

    def __init__(self, store_path: Path | str | None = None):
        self.store_path = self._resolve_store_path(store_path)
        self._sessions = self._load()

    def get(self, session_identifier: str) -> ConversationRef | None:
        self._validate_session_identifier(session_identifier)
        ref = self._sessions.get(session_identifier)
        return self._copy_ref(ref) if ref is not None else None

    def set(self, session_identifier: str, ref: ConversationRef) -> None:
        self._validate_session_identifier(session_identifier)
        if not isinstance(ref, ConversationRef):
            raise AskChatGPTError(
                "Session registry set expected a ConversationRef. Operator action: "
                "pass ConversationRef(conversation_ref=..., url=...) and retry."
            )
        updated = dict(self._sessions)
        updated[session_identifier] = self._copy_ref(ref)
        self._persist(updated)
        self._sessions = updated

    def list(self) -> dict[str, ConversationRef]:
        return {key: self._copy_ref(ref) for key, ref in self._sessions.items()}

    def delete(self, session_identifier: str) -> bool:
        self._validate_session_identifier(session_identifier)
        if session_identifier not in self._sessions:
            return False
        updated = dict(self._sessions)
        del updated[session_identifier]
        self._persist(updated)
        self._sessions = updated
        return True

    @classmethod
    def _resolve_store_path(cls, store_path: Path | str | None) -> Path:
        if store_path is not None:
            return Path(store_path).expanduser()
        if state_dir := os.environ.get("ASK_CHATGPT_STATE_DIR"):
            return Path(state_dir).expanduser() / cls._FILENAME
        return Path.home() / ".local" / "state" / "ask-chatgpt" / cls._FILENAME

    def _load(self) -> dict[str, ConversationRef]:
        if not self.store_path.exists():
            return {}
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise AskChatGPTError(
                f"Session registry file is not valid JSON: {self.store_path}. {_BAD_FILE_ACTION}"
            ) from None
        except OSError as exc:
            raise AskChatGPTError(
                f"Session registry file could not be read: {self.store_path}. "
                "Operator action: check permissions and retry."
            ) from exc

        raw_sessions = payload.get("sessions") if isinstance(payload, dict) else None
        if not isinstance(raw_sessions, dict):
            raise AskChatGPTError(
                f"Session registry file has an unsupported shape: {self.store_path}. {_BAD_FILE_ACTION}"
            )
        return {session_id: self._ref_from_json(raw_ref) for session_id, raw_ref in raw_sessions.items()}

    def _persist(self, sessions: dict[str, ConversationRef]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self._VERSION,
            "sessions": {key: asdict(ref) for key, ref in sessions.items()},
        }
        tmp_path = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{self.store_path.name}.", suffix=".tmp", dir=self.store_path.parent
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_path, self.store_path)
        except (OSError, TypeError, ValueError) as exc:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise AskChatGPTError(
                "Session registry could not be written atomically. Operator action: "
                f"check permissions/free space for {self.store_path.parent} and retry."
            ) from exc

    @staticmethod
    def _copy_ref(ref: ConversationRef) -> ConversationRef:
        return ConversationRef(ref.conversation_ref, ref.url, deepcopy(ref.model_settings))

    @staticmethod
    def _ref_from_json(raw_ref: object) -> ConversationRef:
        if not isinstance(raw_ref, dict):
            raise AskChatGPTError(f"Session registry entry is malformed. {_BAD_ENTRY_ACTION}")
        conversation_ref = raw_ref.get("conversation_ref")
        url = raw_ref.get("url")
        model_settings = raw_ref.get("model_settings")
        if not isinstance(conversation_ref, str) or not conversation_ref:
            raise AskChatGPTError(
                f"Session registry entry is missing a conversation reference. {_BAD_ENTRY_ACTION}"
            )
        if url is not None and not isinstance(url, str):
            raise AskChatGPTError(f"Session registry entry has an invalid URL field. {_BAD_ENTRY_ACTION}")
        if model_settings is not None and not isinstance(model_settings, dict):
            raise AskChatGPTError(
                f"Session registry entry has invalid model settings. {_BAD_ENTRY_ACTION}"
            )
        return ConversationRef(conversation_ref, url, deepcopy(model_settings))

    @staticmethod
    def _validate_session_identifier(session_identifier: str) -> None:
        if not isinstance(session_identifier, str) or not session_identifier:
            raise AskChatGPTError(
                "Session identifier must be a non-empty string. Operator action: "
                "pass a stable session_identifier and retry."
            )


__all__ = ["ConversationRef", "SessionRegistry"]
