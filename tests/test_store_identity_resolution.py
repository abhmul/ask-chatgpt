from __future__ import annotations

import json

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.store import Store


def test_resolve_conversation_uses_index_only_for_aliases_and_sessions(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aliases": {"math-long": "chat_alias"},
                "sessions": {"last": "chat_session"},
                "conversations": {
                    "chat_alias": {
                        "conversation_id": "chat_alias",
                        "url": "https://chatgpt.com/c/chat_alias",
                        "project_id": None,
                        "title": "Alias title",
                        "current_node": "node_a",
                        "model": {"slug": "gpt-4o", "display": None},
                        "last_updated": None,
                    },
                    "chat_session": {
                        "conversation_id": "chat_session",
                        "url": "https://chatgpt.com/g/g-p-proj_1/c/chat_session",
                        "project_id": "proj_1",
                        "title": None,
                        "current_node": None,
                        "model": {"slug": None, "display": None},
                        "last_updated": None,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    alias = store.resolve_conversation("math-long")
    session = store.resolve_conversation("last")

    assert alias == ConversationRef(
        conversation_id="chat_alias",
        url="https://chatgpt.com/c/chat_alias",
        title="Alias title",
        current_node="node_a",
        default_model_slug="gpt-4o",
    )
    assert session == ConversationRef(
        conversation_id="chat_session",
        url="https://chatgpt.com/g/g-p-proj_1/c/chat_session",
        project_id="proj_1",
    )


def test_corrupt_index_does_not_break_stateless_id_or_url_resolution(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    (tmp_path / "index.json").write_text("{not json", encoding="utf-8")

    assert store.resolve_conversation("chat_123") == ConversationRef(
        "chat_123", "https://chatgpt.com/c/chat_123"
    )
    assert store.resolve_conversation("https://chatgpt.com/c/chat_123") == ConversationRef(
        "chat_123", "https://chatgpt.com/c/chat_123"
    )
