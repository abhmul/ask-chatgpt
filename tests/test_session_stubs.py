from __future__ import annotations

from types import SimpleNamespace

from ask_chatgpt.channels.mock import MockChannel, ScriptedClock
from ask_chatgpt.completion import CompletionState
from ask_chatgpt.identity import ConversationRef, conversation_url
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.send import SubmittedTurn, TurnBaseline
from ask_chatgpt.session import Session


SELECTORS = {
    "composer": "#prompt-textarea",
    "tools_button": "button[data-testid=\"composer-plus-btn\"]",
    "message_turn": "[data-message-id][data-message-author-role]",
    "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
    "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
    "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
    "stop_button": "button[data-testid=\"stop-button\"]",
    "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button, button[aria-label=\"Send prompt\"]",
    "file_input": "input[type=\"file\"]",
    "attachment_chip": "[data-testid=\"composer-attachment\"], div[data-testid*=\"attachment\"], button[aria-label*=\"Remove\" i]",
    "active_tool_chip": "button[aria-label*=\"click to remove\" i]",
    "radix_portal": "[data-radix-popper-content-wrapper]",
    "model_picker_trigger_candidates": "composer-footer button[aria-haspopup=\"menu\"]",
}
CONV = ConversationRef("conv_repeated_123", "https://chatgpt.com/c/conv_repeated_123")


def _assistant(ref: ConversationRef, index: int, user_id: str) -> TurnRecord:
    return TurnRecord(
        conversation_id=ref.conversation_id or "",
        conversation_url=conversation_url(ref),
        project_id=ref.project_id,
        message_id=f"assistant-{index}",
        parent_id=user_id,
        turn_index=1,
        role="assistant",
        content_markdown=f"answer {index}",
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        user_message_id=user_id,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def test_session_status_no_browser_probe_never_calls_channel_preflight(tmp_path) -> None:
    class NoProbeChannel(MockChannel):
        def preflight(self, *, timeout_s: float = 5.0):  # noqa: ANN201
            raise AssertionError("preflight must not run when probe_browser=False")

    session = Session(data_dir=tmp_path, channel=NoProbeChannel(), selector_map=SELECTORS)

    report = session.status(probe_browser=False)

    assert report.ok is True
    assert report.cdp is None
    assert report.details["selectors"]["composer"]["present"] is None


def test_repeated_successful_mock_sends_in_one_session_have_no_hidden_message_cap(tmp_path, monkeypatch) -> None:
    import ask_chatgpt.session as session_module

    send_index = {"value": 0}

    def wait_idle(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return None

    def read_baseline(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return TurnBaseline(None, 0, None, 0)

    def wait_composer(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return None

    def upload(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return ()

    def fill(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return None

    def submit(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return None

    def verify(tab, selectors, baseline, prompt, *, timeout_s, has_attachments=False):  # noqa: ANN001, ANN003
        assert has_attachments is False
        send_index["value"] += 1
        return SubmittedTurn(baseline, f"user-{send_index['value']}", 1, prompt.strip())

    def wait_completion(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        index = send_index["value"]
        return CompletionState(True, f"assistant-{index}", None, None, f"tok-{index}", f"answer {index}", "dom", 0.0)

    def capture(tab, ref, store, *, send_context=None, **kwargs):  # noqa: ANN001, ANN003
        index = send_index["value"]
        user_id = send_context.user_message_id if send_context is not None else f"user-{index}"
        turn = _assistant(ref, index, user_id)
        store.upsert_turn(turn)
        return SimpleNamespace(transcript=Transcript(ref, (turn,), None, None))

    monkeypatch.setattr(session_module, "wait_for_idle_and_reload_if_needed", wait_idle)
    monkeypatch.setattr(session_module, "read_turn_baseline", read_baseline)
    monkeypatch.setattr(session_module, "wait_for_composer", wait_composer)
    monkeypatch.setattr(session_module, "upload_attachments", upload)
    monkeypatch.setattr(session_module, "fill_composer", fill)
    monkeypatch.setattr(session_module, "submit_composer", submit)
    monkeypatch.setattr(session_module, "verify_prompt_submitted", verify)
    monkeypatch.setattr(session_module, "wait_for_completion", wait_completion)
    monkeypatch.setattr(session_module, "capture_conversation", capture)

    clock = ScriptedClock()
    channel = MockChannel(monotonic=clock.monotonic, sleeper=clock.sleep)
    session = Session(data_dir=tmp_path, channel=channel, selector_map=SELECTORS)

    answers = [session.ask(CONV, f"prompt {index}") for index in range(15)]

    assert [answer.message_id for answer in answers] == [f"assistant-{index}" for index in range(1, 16)]
    assert session.send_budget.successful_submissions == 15
    assert session.tab_pool.snapshot()["managed_tabs"] == 1
    assert clock.sleeps
