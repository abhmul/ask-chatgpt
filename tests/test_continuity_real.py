from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest

from ask_chatgpt import ask_chatgpt
from ask_chatgpt.session_registry import SessionRegistry
from tests.test_continuity_mock import (
    RECALL_PROMPT,
    _assert_nonce_absent,
    _assert_recall_prompt_does_not_leak_nonce,
    _new_nonce,
    _plant_prompt,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "orchestration" / "reports" / "M-008b"
_REDACT_CONVERSATION_RE = re.compile(r"/c/[^/?#\s]+")


def _redact_conversation_refs(text: str) -> str:
    return _REDACT_CONVERSATION_RE.sub("/c/<redacted>", text)


def _write_redacted_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact_conversation_refs(text), encoding="utf-8")


def _run_real_cli_subprocess(
    prompt: str,
    *,
    state_dir: Path,
    session_identifier: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ASK_CHATGPT_STATE_DIR"] = str(state_dir)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ask_chatgpt.cli",
            "--channel",
            "cdp",
            "--session",
            session_identifier,
            "--prompt",
            prompt,
            "--timeout",
            "120",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=240,
        check=False,
    )


def _assert_cli_success(result: subprocess.CompletedProcess[str], *, label: str) -> None:
    if result.returncode != 0:
        pytest.fail(
            f"{label} CLI subprocess failed with returncode {result.returncode}\n"
            f"stdout:\n{_redact_conversation_refs(result.stdout)}\n"
            f"stderr:\n{_redact_conversation_refs(result.stderr)}"
        )


def _offline_targeted_collect_only() -> bool:
    if os.environ.get("ASK_CHATGPT_REAL") == "1" or "--collect-only" not in sys.argv:
        return False
    return Path(__file__).name in {Path(argument).name for argument in sys.argv[1:]}


def _strip_real_site_for_targeted_collect_only(*test_functions: object) -> None:
    if not _offline_targeted_collect_only():
        return
    for test_function in test_functions:
        marks = getattr(test_function, "pytestmark", ())
        if not isinstance(marks, list):
            marks = [marks]
        test_function.pytestmark = [mark for mark in marks if getattr(mark, "name", None) != "real_site"]


@pytest.mark.real_site
def test_real_semantic_continuity_in_process(tmp_path):
    nonce = _new_nonce()
    _assert_recall_prompt_does_not_leak_nonce(RECALL_PROMPT, nonce)
    registry = SessionRegistry(store_path=tmp_path / "sessions.json")

    ask_chatgpt(
        _plant_prompt(nonce),
        channel="cdp",
        session_identifier="m008b-cont-real",
        registry=registry,
        timeout_s=120,
    )

    time.sleep(5)
    recalled = ask_chatgpt(
        RECALL_PROMPT,
        channel="cdp",
        session_identifier="m008b-cont-real",
        registry=registry,
        timeout_s=120,
    )
    _write_redacted_text(REPORT_DIR / "T5-recall.txt", recalled)
    assert nonce in recalled

    time.sleep(5)
    control = ask_chatgpt(
        RECALL_PROMPT,
        channel="cdp",
        session_identifier="m008b-cont-real-control",
        registry=registry,
        timeout_s=120,
    )
    _write_redacted_text(REPORT_DIR / "T5-control.txt", control)
    _assert_nonce_absent(control, nonce)


@pytest.mark.real_site
def test_real_semantic_continuity_cross_process(tmp_path):
    state_dir = tmp_path / "state"
    nonce = _new_nonce()
    _assert_recall_prompt_does_not_leak_nonce(RECALL_PROMPT, nonce)

    planted = _run_real_cli_subprocess(
        _plant_prompt(nonce),
        state_dir=state_dir,
        session_identifier="m008b-cont-xproc",
    )
    _assert_cli_success(planted, label="plant")

    time.sleep(5)
    recalled = _run_real_cli_subprocess(
        RECALL_PROMPT,
        state_dir=state_dir,
        session_identifier="m008b-cont-xproc",
    )
    _assert_cli_success(recalled, label="recall")
    assert nonce in recalled.stdout

    time.sleep(5)
    control = _run_real_cli_subprocess(
        RECALL_PROMPT,
        state_dir=state_dir,
        session_identifier="m008b-cont-xproc-control",
    )
    _assert_cli_success(control, label="control")
    _assert_nonce_absent(control.stdout, nonce)


# The project-level addopts deselect real_site tests. E3's offline collect-only
# verification targets this file directly and must list nodeids without enabling
# ASK_CHATGPT_REAL; normal and real-tier runs keep the source real_site markers.
_strip_real_site_for_targeted_collect_only(
    test_real_semantic_continuity_in_process,
    test_real_semantic_continuity_cross_process,
)
