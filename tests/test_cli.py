from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ask_chatgpt import __version__
from ask_chatgpt.errors import CompletionTimeoutError, PromptNotSubmittedError
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


def _patch_session(monkeypatch):
    import ask_chatgpt.cli as cli

    RecordingSession.instances = []
    RecordingSession.raise_from = None
    monkeypatch.setattr(cli, "Session", RecordingSession)
    return cli


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
        )
    ]


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
            "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button",
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
        ("scrape", ("conv_cli",), {"with_attachments": True, "out": out})
    ]

    assert cli.main(["fetch", "conv_cli", "att-1", "--selector-channel", "mock", "--json"]) == 0
    fetched = json.loads(capsys.readouterr().out)
    assert fetched == {"path": "/tmp/cached-attachment.txt"}
    assert RecordingSession.instances[-2].calls == [
        ("scrape", ("conv_cli",), {"with_attachments": True, "out": out})
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


def test_cli_loop_max_iterations_two_emits_exactly_two_jsonl_envelopes(tmp_path, capsys) -> None:
    from ask_chatgpt.cli import main

    code = main([
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


def test_cli_version_still_prints_package_version(capsys) -> None:
    from ask_chatgpt.cli import main

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__
