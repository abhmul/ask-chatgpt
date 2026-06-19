from __future__ import annotations

from ask_chatgpt.channels.base import RequestSnapshot, TurnDom, TurnDomSnapshot
from ask_chatgpt.channels.mock import (
    HEADER_CANARIES,
    MockBackendResponse,
    MockChannel,
    MockScenario,
    ScriptedClock,
    TimedBackendResponse,
    TimedTurnSnapshot,
)
import pytest

from ask_chatgpt.errors import InternalError, PromptNotSubmittedError
from ask_chatgpt.session import Session
from ask_chatgpt.store import Store


SELECTORS = {
    "composer": "#prompt-textarea",
    "tools_button": "button[data-testid=\"composer-plus-btn\"]",
    "message_turn": "[data-message-id][data-message-author-role]",
    "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
    "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
    "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
    "stop_button": "button[data-testid=\"stop-button\"]",
    "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button",
    "radix_portal": "[data-radix-popper-content-wrapper]",
    "model_picker_trigger_candidates": "composer-footer button[aria-haspopup=\"menu\"]",
}
PROMPT = "MOCK_PROMPT_DRAFT_SEND_CANARY"
ANSWER = "MOCK_ASSISTANT_DRAFT_SEND_CANARY"


def _message(message_id: str, role: str, text: str) -> dict[str, object]:
    return {
        "id": message_id,
        "author": {"role": role},
        "create_time": 1_700_000_000.0,
        "content": {"content_type": "text", "parts": [text]},
        "metadata": {"is_complete": True},
        "status": "finished_successfully",
    }


def _raw_conversation(conversation_id: str, *, user_id: str = "user-draft-1", assistant_id: str = "assistant-draft-1") -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
        "async_status": "complete",
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["user"], "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "children": ["assistant"],
                "message": _message(user_id, "user", PROMPT),
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": _message(assistant_id, "assistant", ANSWER),
            },
        },
        "current_node": "assistant",
        "default_model_slug": "mock-model",
    }


def _request_snapshots(conversation_id: str, count: int = 6) -> tuple[RequestSnapshot, ...]:
    return tuple(
        RequestSnapshot(
            url=f"https://chatgpt.com/backend-api/conversation/{conversation_id}",
            method="GET",
            headers={name: f"{value}_{index}" for name, value in HEADER_CANARIES.items()},
        )
        for index in range(count)
    )


def _draft_scenario(*, learned_url: str = "https://chatgpt.com/c/learned-123", submit_turn: bool = True) -> MockScenario:
    baseline = TurnDomSnapshot(users=(), assistants=(), stop_visible=False, composer_visible=True, model_labels=())
    submitted = TurnDomSnapshot(
        users=(TurnDom("user-draft-1", "user", PROMPT),),
        assistants=(),
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete = TurnDomSnapshot(
        users=submitted.users,
        assistants=(TurnDom("assistant-draft-1", "assistant", ANSWER),),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    timeline = (
        TimedTurnSnapshot(0.0, baseline),
        TimedTurnSnapshot(0.5, submitted),
        TimedTurnSnapshot(1.0, complete),
    ) if submit_turn else (TimedTurnSnapshot(0.0, baseline), TimedTurnSnapshot(5.0, baseline))
    return MockScenario(
        name="draft_send_happy",
        current_url=learned_url,
        turn_timeline=timeline,
        backend_timeline=(TimedBackendResponse(0.0, MockBackendResponse(200, _raw_conversation("learned-123"))),),
        request_snapshots=_request_snapshots("learned-123"),
    )


def _session(tmp_path, channel: MockChannel, *, send_verify_timeout_s: float = 2.0) -> Session:
    return Session(
        data_dir=tmp_path,
        channel=channel,
        selector_map=SELECTORS,
        send_verify_timeout_s=send_verify_timeout_s,
        composer_wait_timeout_s=1.0,
        progress_poll_interval_s=0.5,
        backend_check_interval_s=0.5,
        activity_timeout_s=5.0,
    )


def test_draft_ask_learns_server_conversation_id_and_writes_transcript_under_real_id(tmp_path) -> None:
    clock = ScriptedClock()
    channel = MockChannel(_draft_scenario(), monotonic=clock.monotonic, sleeper=clock.sleep)
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT)

    assert answer.conversation_id == "learned-123"
    assert answer.message_id == "assistant-draft-1"
    assert answer.content_markdown == ANSWER
    transcript = Store(data_dir=tmp_path).load_transcript("learned-123")
    assert [turn.message_id for turn in transcript.turns] == ["user-draft-1", "assistant-draft-1"]
    assert all(turn.conversation_id == "learned-123" for turn in transcript.turns)
    assert (tmp_path / "conversations" / "learned-123" / "transcript.jsonl").is_file()


def test_draft_ask_fails_closed_when_post_submit_url_has_no_conversation_id(tmp_path) -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        _draft_scenario(learned_url="https://chatgpt.com/"),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with pytest.raises(InternalError):
        _session(tmp_path, channel).ask(None, PROMPT)

    assert channel.method_counts.get("current_url_reads", 0) == 1
    assert channel.method_counts.get("full_raw_fetches", 0) == 0
    assert not (tmp_path / "conversations" / "learned-123" / "transcript.jsonl").exists()


def test_draft_ask_gotcha4_no_new_user_turn_stops_before_id_learning_or_completion(tmp_path) -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        _draft_scenario(submit_turn=False),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with pytest.raises(PromptNotSubmittedError):
        _session(tmp_path, channel, send_verify_timeout_s=1.0).ask(None, PROMPT)

    assert channel.method_counts.get("current_url_reads", 0) == 0
    assert channel.method_counts.get("full_raw_fetches", 0) == 0
    assert not (tmp_path / "conversations").exists()
