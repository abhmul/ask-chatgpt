from __future__ import annotations

import json
from datetime import UTC, datetime

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.store import Store


def test_put_conversation_ref_patches_index_preserving_aliases_sessions_and_no_wall_clock(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aliases": {"math": "old_chat"},
                "sessions": {"last": "old_chat"},
                "conversations": {
                    "old_chat": {
                        "conversation_id": "old_chat",
                        "url": "https://chatgpt.com/c/old_chat",
                        "project_id": None,
                        "title": "Old",
                        "model": {"slug": "gpt-old", "display": "Old Model"},
                        "current_node": "old_node",
                        "last_updated": "2025-01-01T00:00:00+00:00",
                    }
                },
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    ref = ConversationRef(
        conversation_id="new_chat",
        url="https://chatgpt.com/c/new_chat",
        title="New",
        default_model_slug="gpt-4o",
        current_node="node_2",
        updated_at=None,
    )

    store.put_conversation_ref(ref)

    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["aliases"] == {"math": "old_chat"}
    assert data["sessions"] == {"last": "old_chat"}
    assert data["conversations"]["old_chat"]["title"] == "Old"
    assert data["conversations"]["new_chat"] == {
        "conversation_id": "new_chat",
        "url": "https://chatgpt.com/c/new_chat",
        "project_id": None,
        "title": "New",
        "model": {"slug": "gpt-4o", "display": None},
        "current_node": "node_2",
        "last_updated": None,
    }
    assert data["conversations"]["new_chat"]["last_updated"] != "2099-09-09T09:09:09+00:00"


def test_put_conversation_ref_uses_backend_updated_at_rfc3339_literal(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef(
        conversation_id="chat_123",
        url="https://chatgpt.com/c/chat_123",
        updated_at=datetime(2026, 6, 1, 2, 3, 4, tzinfo=UTC),
    )

    store.put_conversation_ref(ref)

    data = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert data["conversations"]["chat_123"]["last_updated"] == "2026-06-01T02:03:04+00:00"
