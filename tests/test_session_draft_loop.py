from __future__ import annotations

from dataclasses import replace

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

from ask_chatgpt.errors import AttachmentUploadError, InternalError, PromptNotSubmittedError
from ask_chatgpt.identity import conversation_url
from ask_chatgpt.models import TurnRecord
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
    "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button, button[aria-label=\"Send prompt\"]",
    "file_input": "input[type=\"file\"]",
    "attachment_chip": "[data-testid=\"composer-attachment\"], div[data-testid*=\"attachment\"], button[aria-label*=\"Remove\" i]",
    "active_tool_chip": "button[aria-label*=\"click to remove\" i]",
    "radix_portal": "[data-radix-popper-content-wrapper]",
    "model_picker_trigger_candidates": "form button[aria-haspopup=\"menu\"]:not([data-testid])",
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


def _raw_conversation(
    conversation_id: str,
    *,
    user_id: str = "user-draft-1",
    assistant_id: str = "assistant-draft-1",
    prompt: str = PROMPT,
    answer: str = ANSWER,
) -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
        "async_status": "complete",
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["user"], "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "children": ["assistant"],
                "message": _message(user_id, "user", prompt),
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": _message(assistant_id, "assistant", answer),
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


def _draft_scenario(
    *,
    learned_url: str = "https://chatgpt.com/c/learned-123",
    conversation_id: str = "learned-123",
    submit_turn: bool = True,
    submitted_user_text: str = PROMPT,
    current_url_sequence: tuple[str, ...] = (),
    requests_require_reload: bool = False,
) -> MockScenario:
    baseline = TurnDomSnapshot(users=(), assistants=(), stop_visible=False, composer_visible=True, model_labels=())
    submitted = TurnDomSnapshot(
        users=(TurnDom("user-draft-1", "user", submitted_user_text),),
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
        current_url_sequence=current_url_sequence,
        turn_timeline=timeline,
        backend_timeline=(TimedBackendResponse(0.0, MockBackendResponse(200, _raw_conversation(conversation_id))),),
        request_snapshots=_request_snapshots(conversation_id),
        requests_require_reload=requests_require_reload,
    )


def _session(
    tmp_path,
    channel: MockChannel,
    *,
    send_verify_timeout_s: float = 2.0,
    draft_url_learn_timeout_s: float = 2.0,
) -> Session:
    return Session(
        data_dir=tmp_path,
        channel=channel,
        selector_map=SELECTORS,
        send_verify_timeout_s=send_verify_timeout_s,
        composer_wait_timeout_s=1.0,
        progress_poll_interval_s=0.5,
        backend_check_interval_s=0.5,
        draft_url_learn_timeout_s=draft_url_learn_timeout_s,
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


def test_draft_ask_uploads_attached_file_before_submit(tmp_path) -> None:
    attachment = tmp_path / "m9-upload.txt"
    attachment.write_text("offline upload canary", encoding="utf-8")
    clock = ScriptedClock()
    channel = MockChannel(
        replace(
            _draft_scenario(),
            selector_presence={SELECTORS["attachment_chip"]: True},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT, attach=[attachment])

    assert answer.conversation_id == "learned-123"
    upload_calls = [call for call in channel.calls if call.method == "upload_files"]
    assert len(upload_calls) == 1
    assert upload_calls[0].details["selector"] == SELECTORS["file_input"]
    assert upload_calls[0].details["file_count"] == 1
    methods = list(channel.call_order)
    assert methods.index("upload_files") < methods.index("fill")
    assert methods.index("upload_files") < methods.index("click")


def test_draft_ask_attach_verifies_user_turn_when_dom_includes_attachment_filename(tmp_path) -> None:
    attachment = tmp_path / "m9-upload.txt"
    attachment.write_text("offline upload canary", encoding="utf-8")
    clock = ScriptedClock()
    channel = MockChannel(
        replace(
            _draft_scenario(submitted_user_text=f"{attachment.name}\n{PROMPT}"),
            selector_presence={SELECTORS["attachment_chip"]: True},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT, attach=[attachment])

    assert answer.conversation_id == "learned-123"
    transcript = Store(data_dir=tmp_path).load_transcript("learned-123")
    user_turns = [turn for turn in transcript.turns if turn.role == "user"]
    assert [turn.content_markdown for turn in user_turns] == [PROMPT]
    assert channel.method_counts.get("upload_files", 0) == 1


def test_draft_ask_attach_waits_past_default_send_enable_settle(tmp_path) -> None:
    attachment = tmp_path / "m9-delayed-enable.txt"
    attachment.write_text("offline upload canary", encoding="utf-8")
    clock = ScriptedClock()
    send_selector = SELECTORS["send_button_unverified_no_input"]
    channel = MockChannel(
        replace(
            _draft_scenario(),
            selector_presence={SELECTORS["attachment_chip"]: True},
            selector_enabled_sequence={send_selector: (False,) * 10 + (True,)},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT, attach=[attachment])

    assert answer.conversation_id == "learned-123"
    assert channel.method_counts.get("click", 0) == 1
    assert clock.monotonic() > 2.0
    methods = list(channel.call_order)
    assert methods.index("upload_files") < methods.index("fill") < methods.index("click")


def test_draft_ask_attach_fails_closed_when_chip_never_appears(tmp_path) -> None:
    attachment = tmp_path / "m9-missing-chip.txt"
    attachment.write_text("offline upload canary", encoding="utf-8")
    clock = ScriptedClock()
    channel = MockChannel(
        replace(
            _draft_scenario(),
            selector_presence={SELECTORS["attachment_chip"]: False},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with pytest.raises(AttachmentUploadError) as exc_info:
        _session(tmp_path, channel).ask(None, PROMPT, attach=[attachment])

    assert exc_info.value.code == "ATTACHMENT_UPLOAD_FAILED"
    assert exc_info.value.details["file_count"] == 1
    assert channel.method_counts.get("upload_files", 0) == 1
    assert channel.method_counts.get("fill", 0) == 0
    assert channel.method_counts.get("click", 0) == 0
    assert clock.monotonic() >= 30.0


def test_draft_ask_reloads_learned_chat_before_capture_when_backend_get_requires_reload(tmp_path) -> None:
    # Falsifiability: removing the draft-path reload leaves the mock with no backend GET and capture cannot succeed.
    clock = ScriptedClock()
    channel = MockChannel(
        _draft_scenario(requests_require_reload=True),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT)

    assert answer.conversation_id == "learned-123"
    assert answer.content_markdown == ANSWER
    assert answer.capture_source == "backend_api"
    transcript = Store(data_dir=tmp_path).load_transcript("learned-123")
    assert [turn.message_id for turn in transcript.turns] == ["user-draft-1", "assistant-draft-1"]
    assert (tmp_path / "conversations" / "learned-123" / "transcript.jsonl").is_file()
    assert channel.method_counts.get("reload", 0) >= 1
    methods = list(channel.call_order)
    reload_index = methods.index("reload")
    fetch_index = methods.index("fetch_in_page")
    assert reload_index < fetch_index


def test_draft_send_capture_uses_exact_conversation_header_harvest_not_ambient(tmp_path) -> None:
    conversation_id = "learned-exact-harvest"
    generic_path = "/backend-api/accounts/check"
    exact_path = f"/backend-api/conversation/{conversation_id}"
    generic_auth = "Bearer MOCK_GENERIC_SEND_CAPTURE_AUTH"
    exact_auth = "Bearer MOCK_EXACT_SEND_CAPTURE_AUTH"

    def request_snapshot(path: str, auth: str) -> RequestSnapshot:
        headers = dict(HEADER_CANARIES)
        headers["authorization"] = auth
        headers["x-openai-target-path"] = path
        return RequestSnapshot(url=f"https://chatgpt.com{path}", method="GET", headers=headers)

    class RecordingChannel(MockChannel):
        def __init__(self, scenario: MockScenario, *, monotonic, sleeper) -> None:  # noqa: ANN001
            super().__init__(scenario, monotonic=monotonic, sleeper=sleeper)
            self.streamed_conversation_auths: list[str | None] = []

        def fetch_in_page(self, tab, url, *, method="GET", headers=None, body=None, stream_to=None, timeout_s=None):  # noqa: ANN001, ANN201
            if url == exact_path and stream_to is not None:
                lower_headers = {str(key).lower(): str(value) for key, value in dict(headers or {}).items()}
                self.streamed_conversation_auths.append(lower_headers.get("authorization"))
            return super().fetch_in_page(
                tab,
                url,
                method=method,
                headers=headers,
                body=body,
                stream_to=stream_to,
                timeout_s=timeout_s,
            )

    scenario = replace(
        _draft_scenario(
            learned_url=f"https://chatgpt.com/c/{conversation_id}",
            conversation_id=conversation_id,
            requests_require_reload=True,
        ),
        request_snapshots=(
            request_snapshot(generic_path, generic_auth),
            request_snapshot(exact_path, exact_auth),
        ),
    )
    clock = ScriptedClock()
    channel = RecordingChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT)

    assert answer.conversation_id == conversation_id
    assert answer.capture_source == "backend_api"
    assert channel.streamed_conversation_auths == [exact_auth]


def test_draft_url_poll_tolerates_spa_navigation_latency(tmp_path) -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        _draft_scenario(
            learned_url="https://chatgpt.com/c/learned-xyz",
            conversation_id="learned-xyz",
            current_url_sequence=(
                "https://chatgpt.com/",
                "https://chatgpt.com/",
                "https://chatgpt.com/c/learned-xyz",
            ),
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = _session(tmp_path, channel)

    answer = session.ask(None, PROMPT)

    assert answer.conversation_id == "learned-xyz"
    transcript = Store(data_dir=tmp_path).load_transcript("https://chatgpt.com/c/learned-xyz")
    assert [turn.message_id for turn in transcript.turns] == ["user-draft-1", "assistant-draft-1"]
    assert (tmp_path / "conversations" / "learned-xyz" / "transcript.jsonl").is_file()
    assert channel.method_counts.get("current_url_reads", 0) >= 3


def test_draft_url_poll_fails_closed_when_never_navigates(tmp_path) -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        _draft_scenario(learned_url="https://chatgpt.com/"),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with pytest.raises(
        InternalError,
        match=r"post-submit URL did not navigate to /c/<id> within 1s",
    ) as exc_info:
        _session(tmp_path, channel, draft_url_learn_timeout_s=1.0).ask(None, PROMPT)

    assert exc_info.value.details["saw_url"] is True
    assert exc_info.value.details["attempts"] == channel.method_counts.get("current_url_reads", 0)
    assert "https://chatgpt.com" not in str(exc_info.value)
    assert channel.method_counts.get("current_url_reads", 0) > 1
    assert channel.method_counts.get("full_raw_fetches", 0) == 0
    assert not (tmp_path / "conversations").exists()
    assert not list(tmp_path.rglob("transcript.jsonl"))


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


def test_loop_verify_each_turn_no_op_submit_raises_prompt_not_submitted(tmp_path) -> None:
    conversation_id = "loop-noop-123"
    message = "MOCK_PROMPT_LOOP_NOOP_CANARY"
    baseline = TurnDomSnapshot(users=(), assistants=(), stop_visible=False, composer_visible=True, model_labels=())
    scenario = MockScenario(
        name="loop_noop_submit",
        turn_timeline=(TimedTurnSnapshot(0.0, baseline), TimedTurnSnapshot(5.0, baseline)),
    )
    clock = ScriptedClock()
    channel = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    session = _session(tmp_path, channel, send_verify_timeout_s=1.0)

    with pytest.raises(PromptNotSubmittedError):
        list(session.loop(conversation_id, message=message, max_iterations=1))

    assert session.send_budget.successful_submissions == 0
    assert channel.method_counts.get("full_raw_fetches", 0) == 0


def test_loop_on_cdp_channel_arg_no_longer_raises_mock_only_guard(tmp_path) -> None:
    conversation_id = "loop-cdp-structural"
    channel = MockChannel()
    session = Session(data_dir=tmp_path, channel=channel, selector_map=SELECTORS)
    session._channel_arg = "cdp"

    def fake_run(tab, ref, prompt, **kwargs):  # noqa: ANN001, ANN003
        del tab, prompt, kwargs
        return TurnRecord(
            conversation_id=conversation_id,
            conversation_url=conversation_url(ref),
            project_id=None,
            message_id="assistant-cdp-structural",
            parent_id="user-cdp-structural",
            turn_index=1,
            role="assistant",
            content_markdown="MOCK_ASSISTANT_CDP_LOOP_STRUCTURAL_CANARY",
            model=None,
            active_tools=(),
            kind="normal",
            created_at=None,
            attachments=(),
            citations=(),
            status="complete",
            partial=False,
            user_message_id="user-cdp-structural",
            capture_source="dom_text",
            fidelity="lossy_dom_text",
            error=None,
        ), ref

    session._run_send_turn = fake_run  # type: ignore[method-assign]

    answers = list(session.loop(conversation_id, max_iterations=1))

    assert [answer.message_id for answer in answers] == ["assistant-cdp-structural"]
    assert channel.method_counts.get("open_tab", 0) == 1


def test_loop_sigint_salvages_partial_turn_then_reraises(tmp_path, monkeypatch) -> None:
    import ask_chatgpt.session as session_module

    conversation_id = "loop-sigint-123"
    message = "MOCK_PROMPT_LOOP_SIGINT_CANARY"
    partial_text = "MOCK_ASSISTANT_LOOP_SIGINT_PARTIAL_CANARY"
    baseline = TurnDomSnapshot(users=(), assistants=(), stop_visible=False, composer_visible=True, model_labels=())
    submitted_with_partial = TurnDomSnapshot(
        users=(TurnDom("user-sigint-1", "user", message),),
        assistants=(TurnDom("assistant-sigint-partial", "assistant", partial_text),),
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    scenario = MockScenario(
        name="loop_sigint_partial",
        turn_timeline=(TimedTurnSnapshot(0.0, baseline), TimedTurnSnapshot(0.5, submitted_with_partial)),
    )
    clock = ScriptedClock()
    channel = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    session = _session(tmp_path, channel)

    def interrupt(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise KeyboardInterrupt()

    monkeypatch.setattr(session_module, "wait_for_completion", interrupt)

    iterator = session.loop(conversation_id, message=message, max_iterations=1)
    partial = next(iterator)

    assert partial.partial is True
    assert partial.status == "partial"
    assert partial.message_id == "assistant-sigint-partial"
    assert partial.content_markdown == partial_text
    assert Store(data_dir=tmp_path).load_transcript(conversation_id).turns[-1].message_id == "assistant-sigint-partial"
    with pytest.raises(KeyboardInterrupt):
        next(iterator)


def test_loop_two_iterations_sends_real_turns_and_appends_transcript_without_cap(tmp_path) -> None:
    conversation_id = "loop-real-123"
    message = "MOCK_PROMPT_LOOP_CANARY"
    answer1 = "MOCK_ASSISTANT_LOOP_CANARY_ONE"
    answer2 = "MOCK_ASSISTANT_LOOP_CANARY_TWO"
    baseline = TurnDomSnapshot(users=(), assistants=(), stop_visible=False, composer_visible=True, model_labels=())
    submitted1 = TurnDomSnapshot(
        users=(TurnDom("user-loop-1", "user", message),),
        assistants=(),
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete1 = TurnDomSnapshot(
        users=submitted1.users,
        assistants=(TurnDom("assistant-loop-1", "assistant", answer1),),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    submitted2 = TurnDomSnapshot(
        users=(*submitted1.users, TurnDom("user-loop-2", "user", message)),
        assistants=complete1.assistants,
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete2 = TurnDomSnapshot(
        users=submitted2.users,
        assistants=(*complete1.assistants, TurnDom("assistant-loop-2", "assistant", answer2)),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    scenario = MockScenario(
        name="loop_two_real_sends",
        turn_timeline=(
            TimedTurnSnapshot(0.0, baseline),
            TimedTurnSnapshot(0.5, submitted1),
            TimedTurnSnapshot(1.0, complete1),
            TimedTurnSnapshot(2.0, submitted2),
            TimedTurnSnapshot(2.5, complete2),
        ),
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(200, _raw_conversation(conversation_id, user_id="user-loop-1", assistant_id="assistant-loop-1", prompt=message, answer=answer1))),
            TimedBackendResponse(2.0, MockBackendResponse(200, _raw_conversation(conversation_id, user_id="user-loop-2", assistant_id="assistant-loop-2", prompt=message, answer=answer2))),
        ),
        request_snapshots=_request_snapshots(conversation_id, count=8),
    )
    clock = ScriptedClock()
    channel = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    session = _session(tmp_path, channel)
    session.send_budget.politeness_floor_s = 0.0
    session.send_budget.current_rate_per_min = 60_000.0
    session.send_budget.max_rate_per_min = 60_000.0

    answers = list(session.loop(conversation_id, message=message, max_iterations=2))

    assert [answer.message_id for answer in answers] == ["assistant-loop-1", "assistant-loop-2"]
    assert answers[0].message_id != answers[1].message_id
    transcript = Store(data_dir=tmp_path).load_transcript(conversation_id)
    assert {turn.message_id for turn in transcript.turns} == {"user-loop-1", "assistant-loop-1", "user-loop-2", "assistant-loop-2"}
    assert [turn.message_id for turn in transcript.turns if turn.role == "assistant"] == ["assistant-loop-1", "assistant-loop-2"]
    assert session.send_budget.successful_submissions == 2
    assert session.tab_pool.snapshot()["managed_tabs"] == 1
