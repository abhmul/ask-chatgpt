from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ask_chatgpt import __version__
from ask_chatgpt.errors import CompletionTimeoutError, MaxTotalWaitExceededError, PromptNotSubmittedError
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import PreflightResult, StatusReport, Transcript, TurnRecord
from ask_chatgpt.store import Store


def _assistant_turn(text: str = "assistant body") -> TurnRecord:
    return TurnRecord(
        conversation_id="conv_cli",
        conversation_url="https://chatgpt.com/c/conv_cli",
        project_id=None,
        message_id="assistant-cli-1",
        parent_id="user-cli-1",
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
        user_message_id="user-cli-1",
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def _user_turn(text: str = "stored prompt") -> TurnRecord:
    return TurnRecord(
        conversation_id="conv_cli",
        conversation_url="https://chatgpt.com/c/conv_cli",
        project_id=None,
        message_id="user-cli-1",
        parent_id=None,
        turn_index=0,
        role="user",
        content_markdown=text,
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def _loop_turn(conv: str, index: int, *, partial: bool = False) -> TurnRecord:
    return TurnRecord(
        conversation_id=conv,
        conversation_url=f"https://chatgpt.com/c/{conv}",
        project_id=None,
        message_id=f"assistant-loop-{index}",
        parent_id=f"user-loop-{index}",
        turn_index=index,
        role="assistant",
        content_markdown=("MOCK_ASSISTANT_LOOP_PARTIAL_CANARY" if partial else f"MOCK_ASSISTANT_LOOP_CANARY_{index}"),
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="partial" if partial else "complete",
        partial=partial,
        user_message_id=f"user-loop-{index}",
        capture_source="dom_text",
        fidelity="lossy_dom_text",
        error=None,
    )


@dataclass
class RecordingSession:
    cdp_endpoint: str = ""
    data_dir: str | Path | None = None
    channel: str = ""
    selector_map: object | None = None

    instances: list["RecordingSession"] = None  # type: ignore[assignment]
    raise_from: str | None = None
    timeout_partial: str = "partial salvage"

    def __post_init__(self) -> None:
        if type(self).instances is None:
            type(self).instances = []
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.store = Store(data_dir=self.data_dir)
        type(self).instances.append(self)

    def ask(self, conv, prompt, **kwargs):
        self.calls.append(("ask", (conv, prompt), kwargs))
        if type(self).raise_from == "ask_timeout":
            err = CompletionTimeoutError("timed out safely", details={"authorization": "Bearer SECRET_TOKEN"})
            err.partial_markdown = type(self).timeout_partial
            raise err
        if type(self).raise_from == "ask_max_total_wait":
            err = MaxTotalWaitExceededError("max total wait elapsed safely")
            err.partial_markdown = type(self).timeout_partial
            raise err
        if type(self).raise_from == "ask_prompt":
            raise PromptNotSubmittedError(
                "prompt body SECRET_PROMPT_BODY was not submitted",
                details={"prompt": "SECRET_PROMPT_BODY", "cookie": "SECRET_COOKIE"},
            )
        return _assistant_turn("assistant body")

    def create(self, *, project=None):
        self.calls.append(("create", (), {"project": project}))
        return ConversationRef(None, "https://chatgpt.com/", project_id=project, is_draft=True)

    def scrape(self, conv, **kwargs):
        self.calls.append(("scrape", (conv,), kwargs))
        return Transcript(
            ConversationRef("conv_cli", "https://chatgpt.com/c/conv_cli"),
            (_user_turn(), _assistant_turn("scraped answer")),
            None,
            None,
        )

    def history(self, conv):
        self.calls.append(("history", (conv,), {}))
        return Transcript(
            ConversationRef("conv_cli", "https://chatgpt.com/c/conv_cli"),
            (_user_turn(), _assistant_turn("history answer")),
            None,
            None,
        )

    def fetch(self, conv, attachment):
        self.calls.append(("fetch", (conv, attachment), {}))
        return Path("/tmp/cached-attachment.txt")

    def status(self, conv=None, *, probe_browser=True):
        self.calls.append(("status", (conv,), {"probe_browser": probe_browser}))
        return StatusReport(
            ok=True,
            cdp=None,
            signed_in=None,
            login_or_challenge=None,
            selector_valid=True,
            conversations=3,
            blocking_code=None,
            details={"selectors": {"composer": {"present": None}}},
        )

    def loop(self, conv, **kwargs):
        self.calls.append(("loop", (conv,), kwargs))
        if type(self).raise_from == "loop_sigint":
            err = KeyboardInterrupt()
            err.partial = _loop_turn(str(conv), 1, partial=True)
            raise err
        iterations = int(kwargs.get("max_iterations") or 1)
        for index in range(1, iterations + 1):
            yield _loop_turn(str(conv), index)

    def detach(self, *, close_managed_tabs: bool = True):
        self.calls.append(("detach", (), {"close_managed_tabs": close_managed_tabs}))


def _patch_session(monkeypatch):
    import ask_chatgpt.cli as cli

    RecordingSession.instances = []
    RecordingSession.raise_from = None
    monkeypatch.setattr(cli, "Session", RecordingSession)
    return cli


_CLI_SELECTORS = {
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


def _backend_raw(conversation_id: str, *, user_id: str, assistant_id: str, prompt: str, answer_text: str) -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
        "async_status": "complete",
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["user"], "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "children": ["assistant"],
                "message": {
                    "id": user_id,
                    "author": {"role": "user"},
                    "create_time": 1_700_000_000.0,
                    "content": {"content_type": "text", "parts": [prompt]},
                    "metadata": {"is_complete": True},
                    "status": "finished_successfully",
                },
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": {
                    "id": assistant_id,
                    "author": {"role": "assistant"},
                    "create_time": 1_700_000_001.0,
                    "content": {"content_type": "text", "parts": [answer_text]},
                    "metadata": {"is_complete": True},
                    "status": "finished_successfully",
                },
            },
        },
        "current_node": "assistant",
        "default_model_slug": "mock-model",
    }


def _backend_request_snapshots(conversation_id: str, count: int = 6):
    from ask_chatgpt.channels.base import RequestSnapshot
    from ask_chatgpt.channels.mock import HEADER_CANARIES

    return tuple(
        RequestSnapshot(
            url=f"https://chatgpt.com/backend-api/conversation/{conversation_id}",
            method="GET",
            headers={name: f"{value}_{index}" for name, value in HEADER_CANARIES.items()},
        )
        for index in range(count)
    )


def _ask_scenario(conversation_id: str, *, prompt: str, answer_text: str):
    from ask_chatgpt.channels.base import TurnDom, TurnDomSnapshot
    from ask_chatgpt.channels.mock import MockBackendResponse, MockScenario, TimedBackendResponse, TimedTurnSnapshot

    baseline = TurnDomSnapshot(
        users=(TurnDom("baseline-user-1", "user", "baseline prompt"),),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    submitted = TurnDomSnapshot(
        users=(*baseline.users, TurnDom("user-new-2", "user", prompt)),
        assistants=baseline.assistants,
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete = TurnDomSnapshot(
        users=submitted.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new-2", "assistant", answer_text)),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    return MockScenario(
        name=f"cli_ask_lifecycle_{conversation_id}",
        turn_timeline=(
            TimedTurnSnapshot(0.0, baseline),
            TimedTurnSnapshot(0.5, submitted),
            TimedTurnSnapshot(1.0, complete),
        ),
        backend_timeline=(
            TimedBackendResponse(
                0.0,
                MockBackendResponse(
                    200,
                    _backend_raw(
                        conversation_id,
                        user_id="user-new-2",
                        assistant_id="assistant-new-2",
                        prompt=prompt,
                        answer_text=answer_text,
                    ),
                ),
            ),
        ),
        request_snapshots=_backend_request_snapshots(conversation_id),
    )


def _scrape_scenario(conversation_id: str, *, answer_text: str):
    from ask_chatgpt.channels.mock import MockScenario

    return MockScenario(
        name=f"cli_scrape_lifecycle_{conversation_id}",
        backend_conversations={
            conversation_id: _backend_raw(
                conversation_id,
                user_id="user-scrape-1",
                assistant_id="assistant-scrape-1",
                prompt="stored scrape prompt",
                answer_text=answer_text,
            )
        },
        request_snapshots=_backend_request_snapshots(conversation_id),
    )


def _loop_scenario(conversation_id: str, *, message: str, answer_text: str):
    from ask_chatgpt.channels.base import TurnDom, TurnDomSnapshot
    from ask_chatgpt.channels.mock import MockBackendResponse, MockScenario, TimedBackendResponse, TimedTurnSnapshot

    baseline = TurnDomSnapshot(users=(), assistants=(), stop_visible=False, composer_visible=True, model_labels=())
    submitted = TurnDomSnapshot(
        users=(TurnDom("user-loop-1", "user", message),),
        assistants=(),
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete = TurnDomSnapshot(
        users=submitted.users,
        assistants=(TurnDom("assistant-loop-1", "assistant", answer_text),),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    return MockScenario(
        name=f"cli_loop_lifecycle_{conversation_id}",
        turn_timeline=(
            TimedTurnSnapshot(0.0, baseline),
            TimedTurnSnapshot(0.5, submitted),
            TimedTurnSnapshot(1.0, complete),
        ),
        backend_timeline=(
            TimedBackendResponse(
                0.0,
                MockBackendResponse(
                    200,
                    _backend_raw(
                        conversation_id,
                        user_id="user-loop-1",
                        assistant_id="assistant-loop-1",
                        prompt=message,
                        answer_text=answer_text,
                    ),
                ),
            ),
        ),
        request_snapshots=_backend_request_snapshots(conversation_id),
    )


def _real_session_factory(mock):
    from ask_chatgpt.session import Session as RealSession

    def session_factory(*, cdp_endpoint, data_dir, channel):  # noqa: ANN001
        del cdp_endpoint, channel
        return RealSession(
            data_dir=data_dir,
            channel=mock,
            selector_map=_CLI_SELECTORS,
            send_verify_timeout_s=2.0,
            composer_wait_timeout_s=1.0,
            progress_poll_interval_s=0.5,
            backend_check_interval_s=0.5,
            activity_timeout_s=5.0,
        )

    return session_factory


def _assert_opened_and_closed_once(mock) -> None:
    assert mock.method_counts.get("open_tab", 0) == 1
    assert mock.method_counts.get("close_tab", 0) == 1
    order = list(mock.call_order)
    assert order.index("open_tab") < order.index("close_tab")


def test_cli_ask_forwards_flags_and_stdout_and_out_are_identical(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    out = tmp_path / "answer.md"

    code = cli.main([
        "ask",
        "conv_cli",
        "literal prompt",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
        "--model",
        "GPT-Mock",
        "--tool",
        "web",
        "--tool",
        "deep research",
        "--attach",
        "a.txt",
        "--attach",
        "b.txt",
        "--timeout",
        "7.5",
        "--max-total-wait",
        "123",
        "--out",
        str(out),
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "assistant body\n"
    assert captured.err == ""
    assert out.read_bytes() == captured.out.encode("utf-8")
    session = RecordingSession.instances[-1]
    assert session.channel == "mock"
    assert session.calls == [
        (
            "ask",
            ("conv_cli", "literal prompt"),
            {
                "model": "GPT-Mock",
                "tools": ("web", "deep research"),
                "attach": ("a.txt", "b.txt"),
                "timeout": 7.5,
                "max_total_wait": 123.0,
                "out": out,
            },
        ),
        ("detach", (), {"close_managed_tabs": True}),
    ]


def test_cli_ask_closes_tab_on_success(tmp_path, capsys, monkeypatch) -> None:
    import ask_chatgpt.cli as cli
    from ask_chatgpt.channels.mock import MockChannel, ScriptedClock

    conversation_id = "conv_cli_ask_close_success"
    answer_text = "REAL SESSION ASK CLOSE SUCCESS"
    clock = ScriptedClock()
    mock = MockChannel(
        _ask_scenario(conversation_id, prompt="literal prompt", answer_text=answer_text),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    monkeypatch.setattr(cli, "Session", _real_session_factory(mock))

    code = cli.main([
        "ask",
        f"https://chatgpt.com/c/{conversation_id}",
        "literal prompt",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == f"{answer_text}\n"
    assert captured.err == ""
    _assert_opened_and_closed_once(mock)


def test_cli_capture_429_returns_52_without_stdout_out_or_clipboard_salvage(tmp_path, capsys, monkeypatch) -> None:
    import ask_chatgpt.cli as cli
    from ask_chatgpt.channels.base import TurnDom, TurnDomSnapshot
    from ask_chatgpt.channels.mock import MockBackendResponse, MockChannel, MockScenario, ScriptedClock, TimedBackendResponse, TimedTurnSnapshot

    conversation_id = "conv_cli_rate_limited"
    prompt = "literal prompt"
    baseline = TurnDomSnapshot(
        users=(TurnDom("baseline-user-1", "user", "baseline prompt"),),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    submitted = TurnDomSnapshot(
        users=(*baseline.users, TurnDom("user-new-2", "user", prompt)),
        assistants=baseline.assistants,
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete = TurnDomSnapshot(
        users=submitted.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new-2", "assistant", "answer after old swallow")),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    scenario = MockScenario(
        name="cli_capture_429_rate_limited",
        turn_timeline=(
            TimedTurnSnapshot(0.0, baseline),
            TimedTurnSnapshot(0.5, submitted),
            TimedTurnSnapshot(1.0, complete),
        ),
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(429, {"detail": "too many requests"}, headers={"retry-after": "45"})),
        ),
        request_snapshots=_backend_request_snapshots(conversation_id, count=6),
        clipboard_permission="granted",
        clipboard_text="clipboard salvage must not be emitted",
    )
    clock = ScriptedClock()
    mock = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    monkeypatch.setattr(cli, "Session", _real_session_factory(mock))
    out = tmp_path / "answer.md"

    code = cli.main([
        "ask",
        f"https://chatgpt.com/c/{conversation_id}",
        prompt,
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
        "--out",
        str(out),
    ])

    captured = capsys.readouterr()
    assert code == 52
    assert captured.out == ""
    assert not out.exists()
    assert captured.err.splitlines() == ["ERROR RATE_LIMITED: rate limited"]
    assert mock.method_counts.get("read_clipboard", 0) == 0


def test_cli_ask_closes_tab_on_error_after_acquire(tmp_path, capsys, monkeypatch) -> None:
    import ask_chatgpt.cli as cli
    from ask_chatgpt.channels.mock import MockChannel, ScriptedClock
    from ask_chatgpt.errors import StoreError

    conversation_id = "conv_cli_ask_close_error"
    answer_text = "REAL SESSION ASK CLOSE ERROR"
    clock = ScriptedClock()
    mock = MockChannel(
        _ask_scenario(conversation_id, prompt="literal prompt", answer_text=answer_text),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    def fail_atomic_write(self, out, content):  # noqa: ANN001
        del self, out, content
        raise StoreError("injected out write failure")

    monkeypatch.setattr(cli, "Session", _real_session_factory(mock))
    monkeypatch.setattr(Store, "atomic_write_payload", fail_atomic_write)

    code = cli.main([
        "ask",
        f"https://chatgpt.com/c/{conversation_id}",
        "literal prompt",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
        "--out",
        str(tmp_path / "answer.md"),
    ])

    captured = capsys.readouterr()
    assert code == 70
    assert captured.out == f"{answer_text}\n"
    assert captured.err.splitlines() == ["ERROR STORE_ERROR: injected out write failure"]
    _assert_opened_and_closed_once(mock)


def test_cli_scrape_closes_tab_on_success(tmp_path, capsys, monkeypatch) -> None:
    import ask_chatgpt.cli as cli
    from ask_chatgpt.channels.mock import MockChannel, ScriptedClock

    conversation_id = "conv_cli_scrape_close_success"
    answer_text = "REAL SESSION SCRAPE CLOSE SUCCESS"
    clock = ScriptedClock()
    mock = MockChannel(
        _scrape_scenario(conversation_id, answer_text=answer_text),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    monkeypatch.setattr(cli, "Session", _real_session_factory(mock))

    code = cli.main([
        "scrape",
        f"https://chatgpt.com/c/{conversation_id}",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert answer_text in captured.out
    assert captured.err == ""
    _assert_opened_and_closed_once(mock)


def test_cli_loop_closes_tab_on_keyboard_interrupt(tmp_path, capsys, monkeypatch) -> None:
    import ask_chatgpt.cli as cli
    from ask_chatgpt.channels.mock import MockChannel, ScriptedClock

    conversation_id = "conv_cli_loop_close_sigint"
    message = "REAL SESSION LOOP CLOSE PROMPT"
    answer_text = "REAL SESSION LOOP CLOSE ANSWER"
    clock = ScriptedClock()
    mock = MockChannel(
        _loop_scenario(conversation_id, message=message, answer_text=answer_text),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    def interrupt_on_write(payload):  # noqa: ANN001
        del payload
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "Session", _real_session_factory(mock))
    monkeypatch.setattr(cli, "_write_jsonl_stdout", interrupt_on_write)

    code = cli.main([
        "loop",
        conversation_id,
        "--message",
        message,
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
        "--max-iterations",
        "1",
    ])

    captured = capsys.readouterr()
    assert code == 130
    assert captured.out == ""
    assert captured.err == ""
    _assert_opened_and_closed_once(mock)


def test_cli_real_session_ask_out_write_failure_keeps_stdout_first(tmp_path, capsys, monkeypatch) -> None:
    import ask_chatgpt.cli as cli
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
    from ask_chatgpt.errors import StoreError
    from ask_chatgpt.selectors import load_selector_map
    from ask_chatgpt.session import Session as RealSession

    selectors = load_selector_map(
        {
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
    )
    conversation_id = "conv_cli_real_out"
    answer_text = "REAL SESSION STDOUT SURVIVES OUT FAILURE"
    raw = {
        "conversation_id": conversation_id,
        "async_status": "complete",
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["user"], "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "children": ["assistant"],
                "message": {
                    "id": "user-new-2",
                    "author": {"role": "user"},
                    "create_time": 1_700_000_000.0,
                    "content": {"content_type": "text", "parts": ["literal prompt"]},
                    "metadata": {"is_complete": True},
                    "status": "finished_successfully",
                },
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": {
                    "id": "assistant-new-2",
                    "author": {"role": "assistant"},
                    "create_time": 1_700_000_001.0,
                    "content": {"content_type": "text", "parts": [answer_text]},
                    "metadata": {"is_complete": True},
                    "status": "finished_successfully",
                },
            },
        },
        "current_node": "assistant",
        "default_model_slug": "mock-model",
    }
    baseline = TurnDomSnapshot(
        users=(TurnDom("baseline-user-1", "user", "baseline prompt"),),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    submitted = TurnDomSnapshot(
        users=(*baseline.users, TurnDom("user-new-2", "user", "literal prompt")),
        assistants=baseline.assistants,
        stop_visible=True,
        composer_visible=True,
        model_labels=(),
    )
    complete = TurnDomSnapshot(
        users=submitted.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new-2", "assistant", answer_text)),
        stop_visible=False,
        composer_visible=True,
        model_labels=(),
    )
    scenario = MockScenario(
        name="real_session_out_write_failure",
        turn_timeline=(
            TimedTurnSnapshot(0.0, baseline),
            TimedTurnSnapshot(0.5, submitted),
            TimedTurnSnapshot(1.0, complete),
        ),
        backend_timeline=(TimedBackendResponse(0.0, MockBackendResponse(200, raw)),),
        request_snapshots=tuple(
            RequestSnapshot(
                url=f"https://chatgpt.com/backend-api/conversation/{conversation_id}",
                method="GET",
                headers={name: f"{value}_{index}" for name, value in HEADER_CANARIES.items()},
            )
            for index in range(4)
        ),
    )
    clock = ScriptedClock()
    mock = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)

    def session_factory(*, cdp_endpoint, data_dir, channel):  # noqa: ANN001
        del cdp_endpoint, channel
        return RealSession(
            data_dir=data_dir,
            channel=mock,
            selector_map=selectors,
            send_verify_timeout_s=2.0,
            composer_wait_timeout_s=1.0,
            progress_poll_interval_s=0.5,
            backend_check_interval_s=0.5,
            activity_timeout_s=5.0,
        )

    def fail_atomic_write(self, out, content):  # noqa: ANN001
        del self, out, content
        raise StoreError("injected out write failure")

    monkeypatch.setattr(cli, "Session", session_factory)
    monkeypatch.setattr(Store, "atomic_write_payload", fail_atomic_write)

    code = cli.main([
        "ask",
        f"https://chatgpt.com/c/{conversation_id}",
        "literal prompt",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path / "data"),
        "--out",
        str(tmp_path / "answer.md"),
    ])

    captured = capsys.readouterr()
    assert code == 70
    assert captured.out == f"{answer_text}\n"
    assert captured.err.splitlines() == ["ERROR STORE_ERROR: injected out write failure"]


def test_cli_export_dispatches_history_not_scrape_and_out_does_not_suppress_stdout(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    out = tmp_path / "history.md"

    code = cli.main(["export", "conv_cli", "--selector-channel", "mock", "--out", str(out)])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "## User\n\nstored prompt\n\n## Assistant\n\nhistory answer\n"
    assert out.read_bytes() == captured.out.encode("utf-8")
    assert [call[0] for call in RecordingSession.instances[-1].calls] == ["history"]


def test_cli_scrape_and_fetch_dispatch_documented_methods(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    out = tmp_path / "scrape.md"

    assert cli.main(["scrape", "conv_cli", "--selector-channel", "mock", "--with-attachments", "--out", str(out)]) == 0
    scraped = capsys.readouterr()
    assert scraped.out == "## User\n\nstored prompt\n\n## Assistant\n\nscraped answer\n"
    assert out.read_bytes() == scraped.out.encode("utf-8")
    assert RecordingSession.instances[-1].calls == [
        ("scrape", ("conv_cli",), {"with_attachments": True, "out": out}),
        ("detach", (), {"close_managed_tabs": True}),
    ]

    assert cli.main(["fetch", "conv_cli", "att-1", "--selector-channel", "mock", "--json"]) == 0
    fetched = json.loads(capsys.readouterr().out)
    assert fetched == {"path": "/tmp/cached-attachment.txt"}
    assert RecordingSession.instances[-2].calls == [
        ("scrape", ("conv_cli",), {"with_attachments": True, "out": out}),
        ("detach", (), {"close_managed_tabs": True}),
    ]
    assert RecordingSession.instances[-1].calls == [("fetch", ("conv_cli", "att-1"), {})]


def test_cli_create_forwards_project_but_ask_rejects_project(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)

    assert cli.main(["create", "--selector-channel", "mock", "--project", "g-p-proj_123", "--json"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created == {
        "conversation_id": None,
        "url": "https://chatgpt.com/",
        "project_id": "g-p-proj_123",
        "is_draft": True,
    }
    assert RecordingSession.instances[-1].calls == [("create", (), {"project": "g-p-proj_123"})]

    assert cli.main(["ask", "conv_cli", "prompt", "--project", "proj_123"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--project" in captured.err
    assert RecordingSession.instances[-1].calls == [("create", (), {"project": "g-p-proj_123"})]


def test_cli_completion_timeout_prints_salvage_to_stdout_and_out_before_error(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    RecordingSession.raise_from = "ask_timeout"
    out = tmp_path / "partial.md"

    code = cli.main(["ask", "conv_cli", "prompt", "--selector-channel", "mock", "--out", str(out)])

    captured = capsys.readouterr()
    assert code == 50
    assert captured.out == "partial salvage\n"
    assert out.read_bytes() == captured.out.encode("utf-8")
    assert captured.err.splitlines()[0] == "ERROR COMPLETION_TIMEOUT: timed out safely"
    assert "SECRET_TOKEN" not in captured.err


def test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    RecordingSession.raise_from = "ask_max_total_wait"
    RecordingSession.timeout_partial = "PARTIAL-ANSWER-SENTINEL"
    out = tmp_path / "partial.md"

    code = cli.main(["ask", "conv_cli", "prompt", "--selector-channel", "mock", "--out", str(out)])

    captured = capsys.readouterr()
    assert code == 51
    assert captured.out == "PARTIAL-ANSWER-SENTINEL\n"
    assert out.read_bytes() == captured.out.encode("utf-8")
    assert captured.err.splitlines()[0] == "ERROR MAX_TOTAL_WAIT_EXCEEDED: max total wait elapsed safely"


def test_cli_prompt_not_submitted_error_exit_code_and_redaction(capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    RecordingSession.raise_from = "ask_prompt"

    code = cli.main(["ask", "conv_cli", "SECRET_PROMPT_BODY", "--selector-channel", "mock"])

    captured = capsys.readouterr()
    assert code == 30
    assert captured.out == ""
    assert captured.err.splitlines()[0] == "ERROR PROMPT_NOT_SUBMITTED: <redacted>"
    assert "SECRET_PROMPT_BODY" not in captured.err
    assert "SECRET_COOKIE" not in captured.err


def test_cli_status_json_no_browser_probe_uses_exact_top_level_schema(capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)

    code = cli.main(["status", "conv_cli", "--selector-channel", "mock", "--json", "--no-browser-probe"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    report = json.loads(captured.out)
    assert list(report) == [
        "ok",
        "cdp",
        "signed_in",
        "login_or_challenge",
        "selector_valid",
        "conversations",
        "blocking_code",
        "details",
    ]
    assert report["cdp"] is None
    assert report["details"]["selectors"]["composer"]["present"] is None
    assert RecordingSession.instances[-1].calls == [("status", ("conv_cli",), {"probe_browser": False})]


def test_cli_loop_max_iterations_two_emits_exactly_two_jsonl_envelopes(tmp_path, capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)

    code = cli.main([
        "loop",
        "conv_loop_123",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path),
        "--max-iterations",
        "2",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert len(lines) == 2
    envelopes = [json.loads(line) for line in lines]
    assert [item["schema_version"] for item in envelopes] == [1, 1]
    assert [item["type"] for item in envelopes] == ["turn", "turn"]
    assert [item["iteration"] for item in envelopes] == [1, 2]
    assert [item["conversation_id"] for item in envelopes] == ["conv_loop_123", "conv_loop_123"]
    assert [item["status"] for item in envelopes] == ["complete", "complete"]


def test_cli_loop_keyboard_interrupt_emits_partial_jsonl_and_returns_130(capsys, monkeypatch) -> None:
    cli = _patch_session(monkeypatch)
    RecordingSession.raise_from = "loop_sigint"

    code = cli.main(["loop", "conv_loop_sigint", "--selector-channel", "mock"])

    captured = capsys.readouterr()
    assert code == 130
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["iteration"] == 1
    assert envelope["conversation_id"] == "conv_loop_sigint"
    assert envelope["status"] == "partial"
    assert envelope["partial"] is True
    assert envelope["message_id"] == "assistant-loop-1"


def test_cli_version_still_prints_package_version(capsys) -> None:
    from ask_chatgpt.cli import main

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__
