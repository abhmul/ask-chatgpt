from __future__ import annotations

import re
from pathlib import Path

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.store import Store


def test_record_partial_appends_honest_partial_salvage_with_redacted_details(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")
    error = RuntimeError("Bearer SECRET_AUTH cookie=SECRET_COOKIE PROMPT_CANARY should not persist")

    record = store.record_partial(
        ref,
        client_send_id="send_123",
        partial_markdown="partial answer",
        error=error,
    )

    assert record.role == "assistant"
    assert record.content_markdown == "partial answer"
    assert record.status == "partial"
    assert record.partial is True
    assert record.created_at is None
    assert record.client_send_id == "send_123"
    assert record.capture_source == "dom_text"
    assert record.fidelity == "lossy_dom_text"
    assert record.error == {"type": "RuntimeError", "message": "<redacted>"}
    persisted = (tmp_path / "conversations" / "chat_123" / "transcript.jsonl").read_text(encoding="utf-8")
    assert "partial answer" in persisted
    assert "SECRET_AUTH" not in persisted
    assert "SECRET_COOKIE" not in persisted
    assert "PROMPT_CANARY" not in persisted
    assert store.load_transcript("chat_123").turns == (record,)


def test_record_partial_empty_salvage_is_error_without_fabricated_created_at(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")

    record = store.record_partial(
        ref,
        client_send_id=None,
        partial_markdown="",
        error=RuntimeError("no salvage"),
    )

    assert record.status == "error"
    assert record.partial is True
    assert record.created_at is None
    assert record.content_markdown == ""


def test_no_source_assigns_created_at_from_agent_wall_clock() -> None:
    source_root = Path(__file__).parents[1] / "src" / "ask_chatgpt"
    forbidden = re.compile(r"created_at\s*=\s*(?:datetime\.(?:now|utcnow)|time\.time)\b")
    offenders = []
    for path in sorted(source_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{path.relative_to(source_root)}:{line_number}:{line.strip()}")

    assert offenders == []
