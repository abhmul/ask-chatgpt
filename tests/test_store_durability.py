from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime

import pytest

from ask_chatgpt.errors import StoreError
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import TurnRecord
from ask_chatgpt.store import Store


def turn(index: int, *, conversation_id: str = "chat_123") -> TurnRecord:
    return TurnRecord(
        conversation_id=conversation_id,
        conversation_url=f"https://chatgpt.com/c/{conversation_id}",
        project_id=None,
        message_id=f"msg_{index}",
        parent_id=None,
        turn_index=index,
        role="assistant",
        content_markdown=f"content {index}",
        model=None,
        active_tools=(),
        kind="normal",
        created_at=datetime(2026, 1, 1, 0, index % 60, tzinfo=UTC),
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


def test_prior_complete_lines_survive_append_fsync_failure(tmp_path, monkeypatch) -> None:
    store = Store(data_dir=tmp_path)
    store.upsert_turn(turn(0))
    real_fsync = os.fsync
    calls = 0

    def fail_next_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected fsync failure")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_next_fsync)

    with pytest.raises(StoreError):
        store.upsert_turn(turn(1))

    assert store.load_transcript("chat_123").turns[0].message_id == "msg_0"


def test_concurrent_appenders_never_byte_interleave_json_objects(tmp_path) -> None:
    Store(data_dir=tmp_path).ensure_conversation(ConversationRef("chat_123", "https://chatgpt.com/c/chat_123"))

    def append_range(start: int) -> None:
        local_store = Store(data_dir=tmp_path)
        for index in range(start, start + 5):
            local_store.upsert_turn(turn(index))

    threads = [threading.Thread(target=append_range, args=(start,)) for start in (0, 5, 10, 15)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    transcript_path = tmp_path / "conversations" / "chat_123" / "transcript.jsonl"
    lines = transcript_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    assert {json.loads(line)["message_id"] for line in lines} == {f"msg_{index}" for index in range(20)}
    assert [record.message_id for record in Store(data_dir=tmp_path).load_transcript("chat_123").turns] == [f"msg_{index}" for index in range(20)]
