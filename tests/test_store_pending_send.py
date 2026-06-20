from __future__ import annotations

import json
from datetime import UTC, datetime

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import ModelRef, TurnRecord
from ask_chatgpt.store import Store


def canonical_user(client_send_id: str) -> TurnRecord:
    return TurnRecord(
        conversation_id="chat_123",
        conversation_url="https://chatgpt.com/c/chat_123",
        project_id=None,
        message_id="backend_user_1",
        parent_id="parent_0",
        turn_index=0,
        role="user",
        content_markdown="prompt text",
        model=ModelRef(slug="gpt-4o", display="GPT-4o"),
        active_tools=("web_search",),
        kind="normal",
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        user_message_id=None,
        turn_exchange_id=None,
        client_send_id=client_send_id,
        supersedes_message_id=None,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def test_begin_send_persists_unique_hidden_pending_stubs_and_index(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")

    first = store.begin_send(ref, "prompt one", model=ModelRef("gpt-4o", "GPT-4o"), active_tools=["web_search"])
    second = store.begin_send(ref, "prompt two", model=None, active_tools=[])

    assert first.message_id == f"local:{first.client_send_id}"
    assert second.message_id == f"local:{second.client_send_id}"
    assert first.client_send_id != second.client_send_id
    assert first.content_markdown == "prompt one"
    assert first.model == ModelRef("gpt-4o", "GPT-4o")
    assert first.active_tools == ("web_search",)
    assert first.turn_index is None
    assert first.created_at is None
    assert first.status == "partial"
    assert first.partial is True
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["conversations"]["chat_123"]["conversation_id"] == "chat_123"
    assert store.load_transcript("chat_123").turns == ()
    pending_contents = {record.content_markdown for record in store.load_transcript("chat_123", include_pending=True).turns}
    assert pending_contents == {"prompt one", "prompt two"}


def test_commit_send_appends_canonical_user_superseding_stub_without_editing_stub_line(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")
    stub = store.begin_send(ref, "prompt text", model=None, active_tools=[])

    store.commit_send(stub.client_send_id, canonical_user(stub.client_send_id))  # type: ignore[arg-type]

    transcript_path = tmp_path / "conversations" / "chat_123" / "transcript.jsonl"
    raw_lines = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert len(raw_lines) == 2
    assert raw_lines[0]["message_id"] == f"local:{stub.client_send_id}"
    assert raw_lines[1]["message_id"] == "backend_user_1"
    assert raw_lines[1]["supersedes_message_id"] == f"local:{stub.client_send_id}"
    default = store.load_transcript("chat_123")
    assert [(record.role, record.content_markdown) for record in default.turns] == [("user", "prompt text")]
