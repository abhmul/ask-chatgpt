from __future__ import annotations

from datetime import UTC, datetime

from ask_chatgpt.models import ModelRef, TurnRecord
from ask_chatgpt.store import Store


T0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
T2 = datetime(2026, 1, 1, 0, 2, tzinfo=UTC)


def turn(**overrides: object) -> TurnRecord:
    values = {
        "conversation_id": "chat_123",
        "conversation_url": "https://chatgpt.com/c/chat_123",
        "project_id": None,
        "message_id": "msg",
        "parent_id": None,
        "turn_index": 0,
        "role": "assistant",
        "content_markdown": "content",
        "model": ModelRef(slug="gpt-4o", display="GPT-4o"),
        "active_tools": (),
        "kind": "normal",
        "created_at": T0,
        "attachments": (),
        "citations": (),
        "status": "complete",
        "partial": False,
        "user_message_id": None,
        "turn_exchange_id": None,
        "client_send_id": None,
        "supersedes_message_id": None,
        "capture_source": "backend_api",
        "fidelity": "canonical",
        "error": None,
    }
    values.update(overrides)
    return TurnRecord(**values)  # type: ignore[arg-type]


def pending_stub(client_send_id: str, prompt: str) -> TurnRecord:
    return turn(
        message_id=f"local:{client_send_id}",
        turn_index=None,
        role="user",
        content_markdown=prompt,
        model=None,
        created_at=None,
        status="partial",
        partial=True,
        client_send_id=client_send_id,
    )


def test_load_transcript_last_writer_wins_hides_pending_and_sorts_by_turn_index(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    stale = turn(
        message_id="assistant_1",
        turn_index=1,
        role="assistant",
        content_markdown="stale partial",
        status="partial",
        partial=True,
        created_at=T1,
    )
    later = turn(
        message_id="assistant_1",
        turn_index=1,
        role="assistant",
        content_markdown="complete answer",
        status="complete",
        partial=False,
        created_at=T2,
    )
    canonical_user = turn(
        message_id="user_backend_1",
        turn_index=0,
        role="user",
        content_markdown="verified prompt",
        created_at=T0,
        supersedes_message_id="local:send_1",
    )
    unsuperseded = pending_stub("send_2", "draft prompt")
    superseded = pending_stub("send_1", "verified prompt")
    store.upsert_many([stale, unsuperseded, later, superseded, canonical_user])

    default = store.load_transcript("chat_123")
    with_pending = store.load_transcript("chat_123", include_pending=True)

    assert [record.message_id for record in default.turns] == ["user_backend_1", "assistant_1"]
    assert [record.content_markdown for record in default.turns] == ["verified prompt", "complete answer"]
    assert [record.message_id for record in with_pending.turns] == [
        "user_backend_1",
        "assistant_1",
        "local:send_1",
        "local:send_2",
    ]
    assert with_pending.turns[2].turn_index is None
    assert with_pending.turns[3].turn_index is None
