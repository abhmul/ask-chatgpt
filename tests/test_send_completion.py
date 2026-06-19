from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

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
from ask_chatgpt.completion import CompletionState, poll_backend_completion, salvage_partial, wait_for_completion
from ask_chatgpt.errors import (
    CompletionTimeoutError,
    HumanActionNeededError,
    InternalError,
    MaxTotalWaitExceededError,
    ModelSelectionNotReflectedError,
    PromptNotSubmittedError,
    SelectorNotFoundError,
)
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.selectors import load_selector_map
from ask_chatgpt.send import (
    TurnBaseline,
    fill_composer,
    normalize_prompt,
    read_turn_baseline,
    submit_composer,
    verify_prompt_submitted,
    wait_for_composer,
)
from ask_chatgpt.session import Session
from ask_chatgpt.store import Store
from tests.mock_scenarios import completion_scenarios, current_branch_ids, send_ui_scenarios


SELECTORS = load_selector_map(
    {
        "composer": "#prompt-textarea",
        "tools_button": "button[data-testid=\"composer-plus-btn\"]",
        "message_turn": "[data-message-id][data-message-author-role]",
        "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
        "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
        "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
        "stop_button": "button[data-testid=\"stop-button\"]",
        "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button, button[aria-label=\"Send prompt\"]",
        "radix_portal": "[data-radix-popper-content-wrapper]",
        "model_picker_trigger_candidates": "composer-footer button[aria-haspopup=\"menu\"]",
    }
)
CONV = ConversationRef("conv_mock_completion", "https://chatgpt.com/c/conv_mock_completion")


def _open_mock_tab(mock: MockChannel):
    return mock.open_tab(CONV.url)


def _baseline_snapshot(*, composer_visible: bool = True, stop_visible: bool = False) -> TurnDomSnapshot:
    return TurnDomSnapshot(
        users=(TurnDom("baseline-user-1", "user", "baseline prompt"),),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=stop_visible,
        composer_visible=composer_visible,
        model_labels=("Pro Extended",),
    )


def _message(message_id: str, role: str, text: str, *, status: str = "complete") -> dict[str, object]:
    metadata = {
        "is_complete": status == "complete",
        "is_finalizing": status == "finalizing",
    }
    if status != "complete":
        metadata["pro_progress"] = text
    return {
        "id": message_id,
        "author": {"role": role},
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "content": {"content_type": "text", "parts": [text]},
        "metadata": metadata,
        "status": status,
    }


def _raw_conversation(
    *,
    conversation_id: str = "conv_mock_completion",
    user_id: str = "user-new-2",
    assistant_id: str = "assistant-new-2",
    assistant_text: str = "final answer",
    status: str = "complete",
    update_time: float = 1_700_000_100.0,
) -> dict[str, object]:
    raw: dict[str, object] = {
        "conversation_id": conversation_id,
        "update_time": update_time,
        "async_status": status,
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["user"], "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "children": ["assistant"],
                "message": _message(user_id, "user", "literal prompt", status="complete"),
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": _message(assistant_id, "assistant", assistant_text, status=status),
            },
        },
        "current_node": "assistant",
        "default_model_slug": "mock-model",
    }
    assert current_branch_ids(raw) == ["root", "user", "assistant"]
    return raw


def _assistant_record(message_id: str, text: str, *, user_message_id: str = "user-new-2") -> TurnRecord:
    return TurnRecord(
        conversation_id=CONV.conversation_id or "",
        conversation_url=CONV.url,
        project_id=CONV.project_id,
        message_id=message_id,
        parent_id=user_message_id,
        turn_index=1,
        role="assistant",
        content_markdown=text,
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        user_message_id=user_message_id,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def _request_snapshots(conversation_id: str = "conv_mock_completion", count: int = 8) -> tuple[RequestSnapshot, ...]:
    snapshots = []
    for index in range(count):
        headers = {
            name: f"{value}_{index}"
            for name, value in HEADER_CANARIES.items()
        }
        snapshots.append(
            RequestSnapshot(
                url=f"https://chatgpt.com/backend-api/conversation/{conversation_id}",
                method="GET",
                headers=headers,
            )
        )
    return tuple(snapshots)


def _session_success_scenario() -> MockScenario:
    baseline = _baseline_snapshot()
    submitted = TurnDomSnapshot(
        users=(
            TurnDom("baseline-user-1", "user", "baseline prompt"),
            TurnDom("user-new-2", "user", "literal prompt"),
        ),
        assistants=baseline.assistants,
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    complete = TurnDomSnapshot(
        users=submitted.users,
        assistants=(
            *baseline.assistants,
            TurnDom("assistant-new-2", "assistant", "final answer"),
        ),
        stop_visible=False,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    return MockScenario(
        name="session_success",
        turn_timeline=(
            TimedTurnSnapshot(0.0, baseline),
            TimedTurnSnapshot(3.0, submitted),
            TimedTurnSnapshot(5.0, complete),
        ),
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(200, _raw_conversation(assistant_text="draft", status="in_progress"))),
            TimedBackendResponse(5.0, MockBackendResponse(200, _raw_conversation())),
        ),
        request_snapshots=_request_snapshots(count=12),
    )


def _long_progress_scenario() -> MockScenario:
    baseline = _baseline_snapshot()
    snapshots = []
    for seconds in (0, 300, 600, 900, 1200):
        snapshots.append(
            TimedTurnSnapshot(
                float(seconds),
                TurnDomSnapshot(
                    users=baseline.users,
                    assistants=(
                        *baseline.assistants,
                        TurnDom("assistant-long", "assistant", f"progress {seconds}"),
                    ),
                    stop_visible=seconds != 1200,
                    composer_visible=True,
                    model_labels=baseline.model_labels,
                ),
            )
        )
    return MockScenario(name="long_progress_literal", turn_timeline=tuple(snapshots))


def test_normalize_prompt_strips_edges_and_line_endings_literal() -> None:
    assert normalize_prompt("  alpha\r\nbravo\rcharlie\n  ") == "alpha\nbravo\ncharlie"
    assert normalize_prompt("one  \t  two") == "one  \t  two"


def test_no_op_submit_verification_raises_prompt_not_submitted() -> None:
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["no_op_submit"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)
    baseline = read_turn_baseline(tab, SELECTORS)

    with pytest.raises(PromptNotSubmittedError) as excinfo:
        verify_prompt_submitted(
            tab,
            SELECTORS,
            baseline,
            "literal prompt",
            timeout_s=4.0,
        )

    assert excinfo.value.code == "PROMPT_NOT_SUBMITTED"
    assert mock.method_counts["query_turns"] >= 2
    assert clock.monotonic() >= 4.0


def test_wrong_new_user_turn_is_not_verified() -> None:
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["new_wrong_user_turn"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)
    baseline = read_turn_baseline(tab, SELECTORS)

    with pytest.raises(PromptNotSubmittedError) as excinfo:
        verify_prompt_submitted(tab, SELECTORS, baseline, "literal prompt", timeout_s=4.0)

    assert excinfo.value.code == "PROMPT_NOT_SUBMITTED"
    assert clock.monotonic() >= 4.0


def test_composer_transient_fill_normalization_and_safe_click() -> None:
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["composer_absent_then_visible"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)

    wait_for_composer(tab, SELECTORS, timeout_s=3.0)
    fill_composer(tab, SELECTORS, "  hello\r\nthere\r  ")
    submit_composer(tab, SELECTORS)

    assert clock.monotonic() == 2.0
    assert mock.composer_text(tab) == "hello\nthere"
    assert "click" in mock.call_order
    assert not any(call.method == "press" and call.details.get("selector") in {"body", "html", "document"} for call in mock.calls)


def test_submit_waits_for_enabled_send_button() -> None:
    clock = ScriptedClock()
    selector = SELECTORS["send_button_unverified_no_input"]
    mock = MockChannel(
        MockScenario(
            name="send_button_enables_after_settle",
            selector_enabled_sequence={selector: (False, False, True)},
            turn_timeline=(TimedTurnSnapshot(0.0, _baseline_snapshot()),),
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)

    submit_composer(tab, SELECTORS)

    assert mock.method_counts["click"] == 1
    assert mock.method_counts["wait_for_selector"] >= 3
    assert mock.method_counts["evaluate"] >= 3
    assert clock.monotonic() > 0.0


def test_submit_fails_closed_if_send_button_never_enables() -> None:
    clock = ScriptedClock()
    selector = SELECTORS["send_button_unverified_no_input"]
    mock = MockChannel(
        MockScenario(
            name="send_button_never_enables",
            selector_enabled={selector: False},
            turn_timeline=(TimedTurnSnapshot(0.0, _baseline_snapshot()),),
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)

    with pytest.raises(SelectorNotFoundError) as excinfo:
        submit_composer(tab, SELECTORS)

    assert excinfo.value.code == "SELECTOR_NOT_FOUND"
    assert mock.method_counts["wait_for_selector"] > 1
    assert mock.method_counts.get("click", 0) == 0
    assert clock.monotonic() >= 2.0


def test_composer_never_visible_raises_selector_not_found() -> None:
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["composer_never_visible"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)

    with pytest.raises(SelectorNotFoundError) as excinfo:
        wait_for_composer(tab, SELECTORS, timeout_s=1.0)

    assert excinfo.value.code == "SELECTOR_NOT_FOUND"
    assert mock.method_counts.get("click", 0) == 0


def test_session_no_op_preserves_pending_and_never_calls_completion(tmp_path, monkeypatch) -> None:
    import ask_chatgpt.session as session_module

    def completion_sentinel(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("completion sentinel was reached")

    monkeypatch.setattr(session_module, "wait_for_completion", completion_sentinel)
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["no_op_submit"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = Session(
        data_dir=tmp_path,
        channel=mock,
        selector_map=SELECTORS,
        send_verify_timeout_s=4.0,
        composer_wait_timeout_s=2.0,
    )

    with pytest.raises(PromptNotSubmittedError) as excinfo:
        session.ask(CONV, "literal prompt")

    assert excinfo.value.code == "PROMPT_NOT_SUBMITTED"
    store = Store(data_dir=tmp_path)
    assert store.load_transcript(CONV).turns == ()
    pending = store.load_transcript(CONV, include_pending=True).turns
    assert len(pending) == 1
    assert pending[0].message_id.startswith("local:")
    assert pending[0].content_markdown == "literal prompt"


def test_session_composer_absence_preserves_hidden_pending_stub(tmp_path, monkeypatch) -> None:
    import ask_chatgpt.session as session_module

    def completion_sentinel(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("completion sentinel was reached")

    monkeypatch.setattr(session_module, "wait_for_completion", completion_sentinel)
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["composer_never_visible"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = Session(
        data_dir=tmp_path,
        channel=mock,
        selector_map=SELECTORS,
        composer_wait_timeout_s=1.0,
    )

    with pytest.raises(SelectorNotFoundError) as excinfo:
        session.ask(CONV, "literal prompt")

    assert excinfo.value.code == "SELECTOR_NOT_FOUND"
    assert Store(data_dir=tmp_path).load_transcript(CONV).turns == ()
    pending = Store(data_dir=tmp_path).load_transcript(CONV, include_pending=True).turns
    assert len(pending) == 1
    assert pending[0].message_id.startswith("local:")



def test_requested_model_change_fails_before_submit_and_committing_user(tmp_path) -> None:
    clock = ScriptedClock()
    mock = MockChannel(
        send_ui_scenarios()["successful_new_user_turn"],
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = Session(data_dir=tmp_path, channel=mock, selector_map=SELECTORS)

    with pytest.raises(ModelSelectionNotReflectedError) as excinfo:
        session.ask(CONV, "literal prompt", model="Missing Model")

    assert excinfo.value.code == "MODEL_SELECTION_NOT_REFLECTED"
    assert mock.method_counts.get("fill", 0) == 0
    assert mock.method_counts.get("menu_label_clicks", 0) == 0
    store = Store(data_dir=tmp_path)
    assert store.load_transcript(CONV).turns == ()
    assert store.load_transcript(CONV, include_pending=True).turns == ()


def test_successful_ask_returns_new_assistant_and_supersedes_pending(tmp_path) -> None:
    clock = ScriptedClock()
    mock = MockChannel(_session_success_scenario(), monotonic=clock.monotonic, sleeper=clock.sleep)
    session = Session(
        data_dir=tmp_path,
        channel=mock,
        selector_map=SELECTORS,
        send_verify_timeout_s=4.0,
        composer_wait_timeout_s=2.0,
        progress_poll_interval_s=1.0,
        backend_check_interval_s=1.0,
        activity_timeout_s=10.0,
    )

    answer = session.ask(CONV, "literal prompt")

    assert answer.role == "assistant"
    assert answer.message_id == "assistant-new-2"
    assert answer.user_message_id == "user-new-2"
    assert answer.content_markdown == "final answer"
    assert answer.message_id != "baseline-assistant-1"
    assert mock.call_order.index("query_turns") < mock.call_order.index("fill") < mock.call_order.index("click")
    assert mock.method_counts["full_raw_fetches"] >= 1
    assert mock.method_counts.get("backend_checks", 0) == 0
    visible = Store(data_dir=tmp_path).load_transcript(CONV).turns
    assert [turn.message_id for turn in visible] == ["user-new-2", "assistant-new-2"]
    assert all(not turn.message_id.startswith("local:") for turn in visible)


def test_session_completion_id_absent_does_not_return_stale_assistant_and_salvages(tmp_path, monkeypatch) -> None:
    import ask_chatgpt.session as session_module

    baseline = _baseline_snapshot()
    dom_new = TurnDomSnapshot(
        users=(*baseline.users, TurnDom("user-new-2", "user", "literal prompt")),
        assistants=(*baseline.assistants, TurnDom("assistant-new-2", "assistant", "dom new partial")),
        stop_visible=False,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    clock = ScriptedClock()
    mock = MockChannel(
        MockScenario(
            name="completion_id_absent_from_capture",
            turn_timeline=(TimedTurnSnapshot(0.0, baseline), TimedTurnSnapshot(0.5, dom_new)),
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    stale = _assistant_record("assistant-mid", "stale captured answer")

    def wait_completion(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return CompletionState(
            True,
            "assistant-new-2",
            "complete",
            "finished_successfully",
            "verified-new-id",
            "backend final answer",
            "backend",
            clock.monotonic(),
        )

    def capture(tab, ref, store, *, send_context=None, **kwargs):  # noqa: ANN001, ANN003
        del tab, store, kwargs
        stale_for_user = _assistant_record(
            stale.message_id,
            stale.content_markdown,
            user_message_id=send_context.user_message_id if send_context is not None else "user-new-2",
        )
        return SimpleNamespace(transcript=Transcript(ref, (stale_for_user,), None, None))

    monkeypatch.setattr(session_module, "wait_for_completion", wait_completion)
    monkeypatch.setattr(session_module, "capture_conversation", capture)
    session = Session(
        data_dir=tmp_path,
        channel=mock,
        selector_map=SELECTORS,
        send_verify_timeout_s=2.0,
        composer_wait_timeout_s=1.0,
    )

    with pytest.raises(InternalError) as excinfo:
        session.ask(CONV, "literal prompt")

    partial = getattr(excinfo.value, "partial", None)
    assert excinfo.value.code == "INTERNAL_ERROR"
    assert partial is not None
    assert partial.message_id == "assistant-new-2"
    assert partial.content_markdown == "dom new partial"
    assert partial.content_markdown != stale.content_markdown


def test_old_stable_assistant_is_not_completion() -> None:
    clock = ScriptedClock()
    mock = MockChannel(
        MockScenario(name="old_stable", turn_timeline=(TimedTurnSnapshot(0.0, _baseline_snapshot()),)),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    with pytest.raises(CompletionTimeoutError) as excinfo:
        wait_for_completion(
            tab,
            CONV,
            SELECTORS,
            baseline,
            activity_timeout_s=3.0,
            max_total_wait_s=None,
            progress_poll_interval_s=1.0,
            backend_check_interval_s=10.0,
        )

    assert excinfo.value.code == "COMPLETION_TIMEOUT"


def test_continuous_progress_past_600_without_total_cap_completes() -> None:
    clock = ScriptedClock()
    mock = MockChannel(_long_progress_scenario(), monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    state = wait_for_completion(
        tab,
        CONV,
        SELECTORS,
        baseline,
        activity_timeout_s=301.0,
        max_total_wait_s=None,
        progress_poll_interval_s=300.0,
        backend_check_interval_s=900.0,
    )

    assert clock.monotonic() == 1500.0
    assert state.complete is True
    assert state.assistant_message_id == "assistant-long"
    assert state.partial_markdown == "progress 1200"


def test_explicit_total_cap_raises_even_with_continuous_progress() -> None:
    clock = ScriptedClock()
    mock = MockChannel(_long_progress_scenario(), monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    with pytest.raises(MaxTotalWaitExceededError) as excinfo:
        wait_for_completion(
            tab,
            CONV,
            SELECTORS,
            baseline,
            activity_timeout_s=301.0,
            max_total_wait_s=601.0,
            progress_poll_interval_s=300.0,
            backend_check_interval_s=900.0,
        )

    assert excinfo.value.code == "MAX_TOTAL_WAIT_EXCEEDED"
    assert clock.monotonic() == 900.0


def test_session_timeout_salvage_persists_partial_assistant(tmp_path) -> None:
    baseline = _baseline_snapshot()
    submitted = TurnDomSnapshot(
        users=(*baseline.users, TurnDom("user-new-2", "user", "literal prompt")),
        assistants=baseline.assistants,
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    partial = TurnDomSnapshot(
        users=submitted.users,
        assistants=(*baseline.assistants, TurnDom("assistant-partial-2", "assistant", "partial only")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    clock = ScriptedClock()
    mock = MockChannel(
        MockScenario(
            name="session_timeout_partial",
            turn_timeline=(TimedTurnSnapshot(0.0, baseline), TimedTurnSnapshot(1.0, submitted), TimedTurnSnapshot(2.0, partial)),
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    session = Session(
        data_dir=tmp_path,
        channel=mock,
        selector_map=SELECTORS,
        send_verify_timeout_s=2.0,
        progress_poll_interval_s=1.0,
        backend_check_interval_s=10.0,
        activity_timeout_s=3.0,
    )

    with pytest.raises(CompletionTimeoutError) as excinfo:
        session.ask(CONV, "literal prompt")

    assert excinfo.value.code == "COMPLETION_TIMEOUT"
    turns = Store(data_dir=tmp_path).load_transcript(CONV).turns
    partials = [turn for turn in turns if turn.role == "assistant" and turn.partial]
    assert len(partials) == 1
    assert partials[0].content_markdown == "partial only"
    assert partials[0].status == "partial"
    assert partials[0].capture_source == "dom_text"


def test_poll_backend_completion_default_uses_full_conversation_endpoint_not_stream_status() -> None:
    scenario = MockScenario(
        name="backend_completion_default_full_raw",
        backend_responses={
            "/backend-api/conversation/conv_mock_completion": MockBackendResponse(
                200,
                _raw_conversation(assistant_text="full raw default answer"),
            ),
            "/backend-api/conversation/conv_mock_completion/stream_status": MockBackendResponse(
                200,
                _raw_conversation(assistant_text="stream status answer"),
            ),
        },
        request_snapshots=_request_snapshots(count=1),
    )
    mock = MockChannel(scenario)
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    state = poll_backend_completion(tab, CONV, baseline)

    fetch_urls = [call.details["url"] for call in mock.calls if call.method == "fetch_in_page"]
    assert state.partial_markdown == "full raw default answer"
    assert fetch_urls == ["/backend-api/conversation/conv_mock_completion"]
    assert mock.method_counts["full_raw_fetches"] == 1
    assert mock.method_counts.get("backend_checks", 0) == 0


def test_sparse_backend_cadence_uses_fresh_one_use_headers() -> None:
    baseline = _baseline_snapshot()
    growing = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new-2", "assistant", "working")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    scenario = MockScenario(
        name="sparse_backend_cadence",
        one_use_headers=True,
        turn_timeline=(TimedTurnSnapshot(0.0, growing),),
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(200, _raw_conversation(assistant_text="working", status="in_progress", update_time=1.0))),
            TimedBackendResponse(30.0, MockBackendResponse(200, _raw_conversation(assistant_text="still", status="in_progress", update_time=2.0))),
            TimedBackendResponse(60.0, MockBackendResponse(200, _raw_conversation(assistant_text="done", status="complete", update_time=3.0))),
        ),
        request_snapshots=_request_snapshots(count=4),
    )
    clock = ScriptedClock()
    mock = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = _open_mock_tab(mock)
    baseline_turns = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    state = wait_for_completion(
        tab,
        CONV,
        SELECTORS,
        baseline_turns,
        activity_timeout_s=100.0,
        max_total_wait_s=None,
        progress_poll_interval_s=2.0,
        backend_check_interval_s=30.0,
    )

    assert state.assistant_message_id == "assistant-new-2"
    assert mock.method_counts["full_raw_fetches"] == 3
    assert mock.method_counts["header_acquisitions"] == 3
    assert mock.method_counts.get("backend_checks", 0) == 0
    assert mock.method_counts["dom_polls"] >= 30
    assert mock.method_counts["full_raw_fetches"] < mock.method_counts["dom_polls"]


def test_backend_interval_none_uses_sparse_mock_default_not_dom_cadence() -> None:
    baseline = _baseline_snapshot()
    growing = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new-2", "assistant", "working")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    scenario = MockScenario(
        name="none_backend_interval_sparse",
        turn_timeline=(TimedTurnSnapshot(0.0, growing),),
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(200, _raw_conversation(assistant_text="working", status="in_progress", update_time=1.0))),
            TimedBackendResponse(30.0, MockBackendResponse(200, _raw_conversation(assistant_text="done", status="complete", update_time=2.0))),
        ),
        request_snapshots=_request_snapshots(count=3),
    )
    clock = ScriptedClock()
    mock = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = _open_mock_tab(mock)

    state = wait_for_completion(
        tab,
        CONV,
        SELECTORS,
        TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1),
        activity_timeout_s=100.0,
        max_total_wait_s=None,
        progress_poll_interval_s=2.0,
        backend_check_interval_s=None,
    )

    assert state.partial_markdown == "done"
    assert mock.method_counts["full_raw_fetches"] == 2
    assert mock.method_counts.get("backend_checks", 0) == 0
    assert mock.method_counts["dom_polls"] >= 15


def test_active_or_unknown_statuses_do_not_complete_conservatively() -> None:
    scenario = completion_scenarios()["active_finalizing_unknown_statuses"]
    scenario = MockScenario(
        name=scenario.name,
        backend_timeline=scenario.backend_timeline,
        turn_timeline=scenario.turn_timeline,
        request_snapshots=_request_snapshots(count=4),
    )
    clock = ScriptedClock()
    mock = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    with pytest.raises(CompletionTimeoutError):
        wait_for_completion(
            tab,
            CONV,
            SELECTORS,
            baseline,
            activity_timeout_s=5.0,
            max_total_wait_s=12.0,
            progress_poll_interval_s=2.0,
            backend_check_interval_s=2.0,
        )


def test_salvage_partial_skips_clipboard_by_default_even_when_granted_and_uses_dom() -> None:
    baseline_snapshot = _baseline_snapshot()
    dom_partial = TurnDomSnapshot(
        users=baseline_snapshot.users,
        assistants=(*baseline_snapshot.assistants, TurnDom("assistant-dom-partial", "assistant", "visible DOM partial")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline_snapshot.model_labels,
    )
    mock = MockChannel(
        MockScenario(
            name="clipboard_would_succeed_but_dom_default",
            turn_timeline=(TimedTurnSnapshot(0.0, dom_partial),),
            clipboard_permission="granted",
            clipboard_text="clipboard text must not be read by default",
        )
    )
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    partial = salvage_partial(tab, CONV, baseline, backend_partial=None)

    assert partial is not None
    assert partial.message_id == "assistant-dom-partial"
    assert partial.content_markdown == "visible DOM partial"
    assert partial.capture_source == "dom_text"
    assert mock.method_counts.get("read_clipboard", 0) == 0


def test_clipboard_prompt_salvage_requires_human_action_without_success() -> None:
    clock = ScriptedClock()
    mock = MockChannel(MockScenario(name="clipboard_prompt", clipboard_permission="prompt"), monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = _open_mock_tab(mock)
    baseline = TurnBaseline("baseline-user-1", 1, "baseline-assistant-1", 1)

    with pytest.raises(HumanActionNeededError) as excinfo:
        salvage_partial(tab, CONV, baseline, backend_partial=None)

    assert excinfo.value.code == "HUMAN-ACTION-NEEDED"
    assert mock.method_counts.get("read_clipboard", 0) == 0


def test_send_and_completion_sources_remain_offline_channel_only() -> None:
    source_root = Path(__file__).parents[1] / "src" / "ask_chatgpt"
    for relative in ("send.py", "completion.py"):
        text = (source_root / relative).read_text(encoding="utf-8")
        assert "playwright" not in text.lower()
        assert "CdpChannel" not in text
        assert ".context.pages" not in text
