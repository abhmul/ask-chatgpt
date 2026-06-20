from __future__ import annotations

import json

from ask_chatgpt import __version__
from ask_chatgpt.cli import main
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.models import TurnRecord
from ask_chatgpt.store import Store


def test_package_exposes_non_empty_version() -> None:
    assert isinstance(__version__, str)
    assert __version__


def test_version_flag_prints_version(capsys) -> None:
    assert main(["--version"]) == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == __version__
    assert captured.err == ""


def test_help_flag_describes_real_cli_verbs(capsys) -> None:
    assert main(["--help"]) == 0

    captured = capsys.readouterr()
    assert "usage: ask-chatgpt" in captured.out
    assert "ask" in captured.out
    assert "status" in captured.out
    assert captured.err == ""


def test_history_real_cli_renders_store_only_payload(tmp_path, capsys) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")
    store.put_conversation_ref(ref)
    store.upsert_many([
        TurnRecord(
            conversation_id="chat_123",
            conversation_url="https://chatgpt.com/c/chat_123",
            project_id=None,
            message_id="u1",
            parent_id=None,
            turn_index=0,
            role="user",
            content_markdown="hello",
            model=None,
            active_tools=(),
            kind="normal",
            created_at=None,
            attachments=(),
            citations=(),
            status="complete",
            partial=False,
        ),
        TurnRecord(
            conversation_id="chat_123",
            conversation_url="https://chatgpt.com/c/chat_123",
            project_id=None,
            message_id="a1",
            parent_id="u1",
            turn_index=1,
            role="assistant",
            content_markdown="stored answer",
            model=None,
            active_tools=(),
            kind="normal",
            created_at=None,
            attachments=(),
            citations=(),
            status="complete",
            partial=False,
        ),
    ])

    assert main(["history", "chat_123", "--selector-channel", "mock", "--data-dir", str(tmp_path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == "## User\n\nhello\n\n## Assistant\n\nstored answer\n"
    assert captured.err == ""


def test_status_json_no_browser_probe_real_cli_schema(tmp_path, capsys) -> None:
    assert main(["status", "--selector-channel", "mock", "--data-dir", str(tmp_path), "--json", "--no-browser-probe"]) == 0

    captured = capsys.readouterr()
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
    assert captured.err == ""


def test_real_cli_error_mapping_is_actionable_and_nonzero(tmp_path, capsys) -> None:
    assert main(["history", "missing_alias", "--selector-channel", "mock", "--data-dir", str(tmp_path)]) == 23

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines()[0] == "ERROR CONVERSATION_NOT_FOUND: conversation alias not found"
