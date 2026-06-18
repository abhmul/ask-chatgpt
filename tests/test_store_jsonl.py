from __future__ import annotations

import json
from datetime import UTC, datetime

from ask_chatgpt.models import AttachmentRef, CitationRef, ModelRef, TurnRecord
from ask_chatgpt.store import Store


CREATED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def complete_turn(**overrides: object) -> TurnRecord:
    values = {
        "conversation_id": "chat_123",
        "conversation_url": "https://chatgpt.com/c/chat_123",
        "project_id": None,
        "message_id": "msg_1",
        "parent_id": "parent_0",
        "turn_index": 1,
        "role": "assistant",
        "content_markdown": "Answer with unicode π and math \\frac{}{}",
        "model": ModelRef(slug="gpt-4o", display="GPT-4o"),
        "active_tools": ("web_search", "deep_research"),
        "kind": "deep_research",
        "created_at": CREATED_AT,
        "attachments": (
            AttachmentRef(
                source_kind="generated_asset",
                source_ref="asset_1",
                raw_path="/mapping/msg/metadata/assets/0",
                filename="chart.png",
                mime="image/png",
                bytes=123,
                sha256=None,
                local_path=None,
                download_state="pending",
                metadata={"width": 640},
            ),
        ),
        "citations": (
            CitationRef(
                title="Source",
                url="https://openai.com/research",
                source="citations",
                citation_type="webpage",
                start_ix=0,
                end_ix=6,
                citation_format_type="webpage",
                raw_path="/mapping/msg/metadata/citations/0",
                metadata={"rank": 1},
            ),
        ),
        "status": "complete",
        "partial": False,
        "user_message_id": "user_1",
        "turn_exchange_id": "exchange_1",
        "client_send_id": "send_1",
        "supersedes_message_id": None,
        "capture_source": "backend_api",
        "fidelity": "canonical",
        "error": None,
    }
    values.update(overrides)
    return TurnRecord(**values)  # type: ignore[arg-type]


def test_upsert_turn_writes_one_compact_jsonl_line_and_loads_semantically_equal(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    turn = complete_turn()

    store.upsert_turn(turn)

    transcript_path = tmp_path / "conversations" / "chat_123" / "transcript.jsonl"
    raw = transcript_path.read_bytes()
    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 1
    line = raw.decode("utf-8").rstrip("\n")
    assert "\n" not in line
    assert ": " not in line
    data = json.loads(line)
    assert sorted(data) == [
        "active_tools",
        "attachments",
        "capture_source",
        "citations",
        "client_send_id",
        "content_markdown",
        "conversation_id",
        "conversation_url",
        "created_at",
        "error",
        "fidelity",
        "kind",
        "message_id",
        "model",
        "parent_id",
        "partial",
        "project_id",
        "role",
        "status",
        "supersedes_message_id",
        "turn_exchange_id",
        "turn_index",
        "user_message_id",
    ]
    assert data["created_at"] == "2026-01-02T03:04:05+00:00"
    assert data["active_tools"] == ["web_search", "deep_research"]
    assert data["model"] == {"slug": "gpt-4o", "display": "GPT-4o"}
    assert data["attachments"][0]["download_state"] == "pending"
    assert data["error"] is None

    loaded = store.load_transcript("chat_123")

    assert loaded.conversation.conversation_id == "chat_123"
    assert loaded.transcript_path == transcript_path
    assert loaded.turns == (turn,)


def test_upsert_many_appends_multiple_complete_lines(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    first = complete_turn(message_id="msg_1", turn_index=0, role="user", content_markdown="question")
    second = complete_turn(message_id="msg_2", turn_index=1, role="assistant", content_markdown="answer")

    store.upsert_many([first, second])

    transcript_path = tmp_path / "conversations" / "chat_123" / "transcript.jsonl"
    assert len(transcript_path.read_text(encoding="utf-8").splitlines()) == 2
    assert store.load_transcript("chat_123").turns == (first, second)
