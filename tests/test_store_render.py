from __future__ import annotations

from datetime import UTC, datetime

from ask_chatgpt.models import AttachmentRef, CitationRef, TurnRecord
from ask_chatgpt.store import Store


CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def turn(message_id: str, role: str, turn_index: int, content: str) -> TurnRecord:
    return TurnRecord(
        conversation_id="chat_123",
        conversation_url="https://chatgpt.com/c/chat_123",
        project_id=None,
        message_id=message_id,
        parent_id=None,
        turn_index=turn_index,
        role=role,  # type: ignore[arg-type]
        content_markdown=content,
        model=None,
        active_tools=(),
        kind="normal",
        created_at=CREATED,
        attachments=(
            AttachmentRef(
                source_kind="generated_asset",
                source_ref="asset_1",
                raw_path="/mapping/asset",
                filename="asset.png",
                mime="image/png",
                bytes=None,
                sha256=None,
                local_path=None,
                download_state="pending",
                metadata={},
            ),
        ),
        citations=(
            CitationRef(
                title="Citation",
                url="https://example.invalid/must-not-fetch",
                source="citations",
                citation_type="webpage",
                start_ix=None,
                end_ix=None,
                citation_format_type=None,
                raw_path="/mapping/citation",
                metadata={},
            ),
        ),
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


def pending_stub() -> TurnRecord:
    return TurnRecord(
        conversation_id="chat_123",
        conversation_url="https://chatgpt.com/c/chat_123",
        project_id=None,
        message_id="local:send_1",
        parent_id=None,
        turn_index=None,
        role="user",
        content_markdown="PENDING_STUB_SHOULD_NOT_RENDER",
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="partial",
        partial=True,
        user_message_id=None,
        turn_exchange_id=None,
        client_send_id="send_1",
        supersedes_message_id=None,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def test_render_markdown_visible_only_literal_math_and_exact_trailing_newline(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    user = turn("user_1", "user", 0, "What about \\widehat{x}?")
    assistant = turn(
        "assistant_1",
        "assistant",
        1,
        "A table:\n\n| a | b |\n| - | - |\n| \\ne | \\frac{}{} |\n\n```python\nprint('\\\\widehat')\n```",
    )
    store.upsert_many([pending_stub(), assistant, user])
    raw_path = tmp_path / "conversations" / "chat_123" / "raw-mapping.json"
    raw_path.write_text('{"mapping":{"hidden":"HIDDEN_RAW_SENTINEL"},"current_node":"hidden"}', encoding="utf-8")

    rendered = store.render_markdown(store.load_transcript("chat_123"))

    assert rendered == (
        "## User\n\n"
        "What about \\widehat{x}?\n\n"
        "## Assistant\n\n"
        "A table:\n\n| a | b |\n| - | - |\n| \\ne | \\frac{}{} |\n\n```python\nprint('\\\\widehat')\n```\n"
    )
    assert "PENDING_STUB_SHOULD_NOT_RENDER" not in rendered
    assert "HIDDEN_RAW_SENTINEL" not in rendered
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
