from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ask_chatgpt.errors import StoreError, StoreWarning
from ask_chatgpt.models import TurnRecord
from ask_chatgpt.store import Store


def turn(message_id: str = "msg_1") -> TurnRecord:
    return TurnRecord(
        conversation_id="chat_123",
        conversation_url="https://chatgpt.com/c/chat_123",
        project_id=None,
        message_id=message_id,
        parent_id=None,
        turn_index=0,
        role="assistant",
        content_markdown="safe complete line",
        model=None,
        active_tools=(),
        kind="normal",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        user_message_id=None,
        turn_exchange_id=None,
        client_send_id=None,
        supersedes_message_id=None,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def transcript_path(tmp_path):
    return tmp_path / "conversations" / "chat_123" / "transcript.jsonl"


def test_one_torn_trailing_line_warns_and_loads_prior_valid_records(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    store.upsert_turn(turn())
    transcript_path(tmp_path).write_bytes(transcript_path(tmp_path).read_bytes() + b'{"message_id"')

    with pytest.warns(StoreWarning):
        loaded = store.load_transcript("chat_123")

    assert [record.message_id for record in loaded.turns] == ["msg_1"]


def test_mid_file_invalid_json_raises_store_error(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    store.upsert_turn(turn("msg_1"))
    path = transcript_path(tmp_path)
    path.write_bytes(path.read_bytes() + b'{"bad"\n')
    store.upsert_turn(turn("msg_2"))

    with pytest.raises(StoreError):
        store.load_transcript("chat_123")


def test_more_than_one_trailing_invalid_json_line_raises_store_error(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    store.upsert_turn(turn())
    path = transcript_path(tmp_path)
    path.write_bytes(path.read_bytes() + b'{"bad1"\n{"bad2"')

    with pytest.raises(StoreError):
        store.load_transcript("chat_123")
