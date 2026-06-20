from __future__ import annotations

import builtins
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import (
    AttachmentRef,
    AttachmentSpec,
    CitationRef,
    ModelRef,
    PreflightResult,
    SendTimeouts,
    StatusReport,
    Transcript,
    TurnRecord,
)


CREATED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def attachment(kind: str, index: int) -> AttachmentRef:
    return AttachmentRef(
        source_kind=kind,  # type: ignore[arg-type]
        source_ref=f"ref-{index}",
        raw_path=f"/mapping/node/attachments/{index}",
        filename=f"file-{index}.dat",
        mime="application/octet-stream",
        bytes=10 + index,
        sha256=None,
        local_path=None,
        download_state="pending",
        metadata={"safe": index},
    )


def complete_turn(**overrides: object) -> TurnRecord:
    values = {
        "conversation_id": "chat_123",
        "conversation_url": "https://chatgpt.com/c/chat_123",
        "project_id": None,
        "message_id": "msg_456",
        "parent_id": "parent_1",
        "turn_index": 3,
        "role": "assistant",
        "content_markdown": "final answer",
        "model": ModelRef(slug="gpt-4o", display="GPT-4o"),
        "active_tools": ("web_search", "deep_research"),
        "kind": "deep_research",
        "created_at": CREATED_AT,
        "attachments": (
            attachment("user_upload", 0),
            attachment("file_reference", 1),
            attachment("generated_asset", 2),
            attachment("code_execution_output", 3),
        ),
        "citations": (
            CitationRef(
                title="Allowed source",
                url="https://openai.com/research",
                source="citations",
                citation_type="webpage",
                start_ix=0,
                end_ix=7,
                citation_format_type="webpage",
                raw_path="/mapping/msg/citations/0",
                metadata={"safe": True},
            ),
            CitationRef(
                title="Untrusted source stays a citation only",
                url="https://not-allowed.example/source",
                source="search_result_groups",
                citation_type="webpage",
                start_ix=8,
                end_ix=15,
                citation_format_type="webpage",
                raw_path="/mapping/msg/citations/1",
                metadata={"rank": 2},
            ),
        ),
        "status": "complete",
        "partial": False,
        "user_message_id": "user_msg_1",
        "turn_exchange_id": "exchange_1",
        "client_send_id": "send_1",
        "supersedes_message_id": None,
        "capture_source": "backend_api",
        "fidelity": "canonical",
        "error": None,
    }
    values.update(overrides)
    return TurnRecord(**values)  # type: ignore[arg-type]


def test_turn_record_is_complete_single_seam_with_attachments_and_citations(monkeypatch) -> None:
    def forbidden_open(*args, **kwargs):  # pragma: no cover - failure path only
        raise AssertionError("construction must not open or fetch attachment/citation targets")

    monkeypatch.setattr(builtins, "open", forbidden_open)

    turn = complete_turn()

    assert turn.message_id == "msg_456"
    assert turn.model == ModelRef(slug="gpt-4o", display="GPT-4o")
    assert turn.active_tools == ("web_search", "deep_research")
    assert {item.source_kind for item in turn.attachments} == {
        "user_upload",
        "file_reference",
        "generated_asset",
        "code_execution_output",
    }
    assert len(turn.citations) == 2
    assert all(isinstance(item, CitationRef) for item in turn.citations)
    assert all(not isinstance(item, AttachmentRef) for item in turn.citations)
    assert turn.citations[1].url == "https://not-allowed.example/source"
    assert turn.turn_exchange_id == "exchange_1"
    assert turn.error is None


def test_supporting_dataclasses_preserve_public_fields() -> None:
    conversation = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")
    transcript = Transcript(
        conversation=conversation,
        turns=(complete_turn(),),
        raw_mapping_path=Path("raw-mapping.json"),
        transcript_path=Path("transcript.jsonl"),
    )

    assert transcript.conversation is conversation
    assert transcript.turns[0].content_markdown == "final answer"
    assert SendTimeouts(1.0, 2.0, 3.0, 4.0).submit_verify_s == 3.0
    assert AttachmentSpec(Path("input.txt"), display_name="shown.txt").path == Path(
        "input.txt"
    )
    assert PreflightResult(
        ok=True,
        cdp_endpoint="http://127.0.0.1:9222",
        browser="Chrome",
        protocol_version="1.3",
        websocket_url_present=True,
    ).ok is True
    assert StatusReport(
        ok=False,
        cdp=None,
        signed_in=None,
        login_or_challenge=None,
        selector_valid=False,
        conversations=None,
        blocking_code="SELECTOR_NOT_FOUND",
        details={"present": None},
    ).blocking_code == "SELECTOR_NOT_FOUND"


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "complete", "partial": True},
        {"status": "partial", "partial": False},
        {"status": "error", "partial": False},
        {"message_id": "local:send_1", "status": "complete", "partial": False},
        {
            "message_id": "local:send_1",
            "status": "partial",
            "partial": True,
            "turn_index": 1,
            "created_at": None,
            "client_send_id": "send_1",
            "role": "user",
        },
        {"turn_index": None},
        {
            "message_id": "local:send_1",
            "status": "partial",
            "partial": True,
            "turn_index": None,
            "created_at": CREATED_AT,
            "client_send_id": "send_1",
            "role": "user",
        },
        {
            "message_id": "local:send_1",
            "status": "error",
            "partial": True,
            "turn_index": None,
            "created_at": None,
            "client_send_id": "send_1",
            "role": "user",
        },
    ],
)
def test_turn_record_rejects_inconsistent_status_and_identity(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        complete_turn(**overrides)


def test_backend_turn_record_allows_missing_backend_created_at() -> None:
    turn = complete_turn(created_at=None, message_id="msg_backend_missing_timestamp", turn_index=0)

    assert turn.created_at is None
    assert turn.message_id == "msg_backend_missing_timestamp"
    assert turn.turn_index == 0
    assert turn.status == "complete"
    assert turn.partial is False


def test_pending_local_stub_is_valid_only_with_pending_shape() -> None:
    pending = complete_turn(
        message_id="local:send_1",
        parent_id=None,
        turn_index=None,
        role="user",
        content_markdown="prompt text",
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
    )

    assert pending.message_id == "local:send_1"
    assert pending.turn_index is None
    assert pending.created_at is None


@pytest.mark.parametrize("obj", [complete_turn(), ModelRef("slug", "display"), attachment("unknown", 9)])
def test_frozen_dataclasses_reject_attribute_mutation(obj: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(obj, "kind" if isinstance(obj, TurnRecord) else "metadata", "mutated")


def test_citation_ref_is_frozen_too() -> None:
    citation = complete_turn().citations[0]

    with pytest.raises(FrozenInstanceError):
        citation.title = "mutated"  # type: ignore[misc]
