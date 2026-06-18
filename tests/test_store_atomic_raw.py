from __future__ import annotations

import json
import os

import pytest

from ask_chatgpt.errors import StoreError
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.store import Store


def test_write_raw_mapping_atomic_invalid_candidate_leaves_old_raw_intact(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    store.ensure_conversation(ConversationRef("chat_123", "https://chatgpt.com/c/chat_123"))
    raw_path = tmp_path / "conversations" / "chat_123" / "raw-mapping.json"
    old = {"mapping": {"node_1": {"parent": None}}, "current_node": "node_1"}
    raw_path.write_text(json.dumps(old, separators=(",", ":")), encoding="utf-8")
    invalid = tmp_path / "candidate-invalid.json"
    invalid.write_text(json.dumps({"mapping": {}}), encoding="utf-8")

    with pytest.raises(StoreError):
        store.write_raw_mapping_atomic("chat_123", invalid)

    assert json.loads(raw_path.read_text(encoding="utf-8")) == old


def test_write_raw_mapping_atomic_unwraps_header_wrapper_and_never_persists_auth_oai_keys(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "headers": {
                    "authorization": "Bearer SECRET_AUTH",
                    "oai-device-id": "SECRET_DEVICE",
                },
                "body": {
                    "mapping": {
                        "node_1": {
                            "parent": None,
                            "message": {"metadata": {"oai-device-id": "SECRET_DEVICE", "safe": "kept"}},
                        }
                    },
                    "current_node": "node_1",
                    "authorization": "Bearer SECRET_AUTH",
                },
            }
        ),
        encoding="utf-8",
    )

    written = store.write_raw_mapping_atomic("chat_123", candidate)

    data = json.loads(written.read_text(encoding="utf-8"))
    assert data == {
        "mapping": {
            "node_1": {
                "parent": None,
                "message": {"metadata": {"safe": "kept"}},
            }
        },
        "current_node": "node_1",
    }
    persisted = written.read_text(encoding="utf-8").lower()
    assert "authorization" not in persisted
    assert "oai-device-id" not in persisted
    assert "secret" not in persisted


def test_index_atomic_replace_failure_keeps_old_complete_index(tmp_path, monkeypatch) -> None:
    store = Store(data_dir=tmp_path)
    index_path = tmp_path / "index.json"
    old = {"schema_version": 1, "aliases": {"a": "old"}, "sessions": {}, "conversations": {}}
    index_path.write_text(json.dumps(old, separators=(",", ":")), encoding="utf-8")

    real_replace = os.replace

    def fail_index_replace(src, dst):
        if os.fspath(dst) == os.fspath(index_path):
            raise OSError("injected replace failure")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_index_replace)

    with pytest.raises(StoreError):
        store.put_conversation_ref(ConversationRef("new_chat", "https://chatgpt.com/c/new_chat"))

    assert json.loads(index_path.read_text(encoding="utf-8")) == old
