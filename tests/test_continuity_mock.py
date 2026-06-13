from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from ask_chatgpt import ask_chatgpt
from ask_chatgpt.session_registry import SessionRegistry

ROOT = Path(__file__).resolve().parents[1]
NONCE_PREFIX = "ASKCG-NONCE-"
RECALL_PATTERN = rf"\b(?P<token>{NONCE_PREFIX}[0-9a-f]{{32}})\b"
RECALL_PROMPT = "What was the token I asked you to remember? Reply with only the token."
NO_TOKEN_SENTINEL = "NO_TOKEN_RECALLED"
LONG_LINE_COUNT = 180
# markdown-inert (no _ * ` # ~ [] |): __..__ renders as bold and .markdown inner_text strips it on the real site (M-008b T3 finding).
LONG_SENTINEL = "ELICIT-COMPLETE-SENTINEL"


# M-008b-ready: these builders/verifiers are channel-agnostic. Mock tests below pass
# channel="mock" and a loopback base_url; the later real leg should swap only the
# channel/fixture plumbing, not the nonce/control/completeness assertions.
def _new_nonce() -> str:
    nonce = f"{NONCE_PREFIX}{secrets.token_hex(16)}"
    assert len(nonce) >= 32
    return nonce


def _plant_prompt(nonce: str) -> str:
    return f"Remember this token for later: {nonce}. Reply with ACK only."


def _truncation_elicitation_prompt(*, line_count: int, token: str) -> str:
    return (
        f"Output exactly {line_count} numbered lines, then exactly one completion marker line. "
        f"For k=1 through {line_count}, line k must be exactly `LINE-<k> {token}` with <k> replaced by decimal k and no zero padding. "
        f"After line {line_count}, output exactly `{LONG_SENTINEL}` on its own line and nothing after it."
    )


def _long_response_body(*, line_count: int, token: str) -> str:
    return "\n".join([f"LINE-{index} {token}" for index in range(1, line_count + 1)] + [LONG_SENTINEL])


def _tmp_registry(tmp_path: Path) -> SessionRegistry:
    return SessionRegistry(store_path=tmp_path / "sessions.json")


def _script_recall_response(mock_chatgpt) -> None:
    mock_chatgpt.script_next_response(
        "UNUSED_RECALL_FALLBACK",
        recall_mode="planted_token",
        recall_pattern=RECALL_PATTERN,
    )


def _ask_via_public_api(
    prompt: str,
    *,
    mock_chatgpt,
    registry: SessionRegistry,
    session_identifier: str,
    timeout_s: float = 5,
) -> str:
    return ask_chatgpt(
        prompt,
        session_identifier=session_identifier,
        channel="mock",
        base_url=mock_chatgpt.base_url,
        registry=registry,
        timeout_s=timeout_s,
    )


def _run_cli_subprocess(
    prompt: str,
    *,
    mock_chatgpt,
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
            "mock",
            "--base-url",
            mock_chatgpt.base_url,
            "--timeout",
            "5",
            "--session",
            session_identifier,
            "--prompt",
            prompt,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _assert_recall_prompt_does_not_leak_nonce(prompt: str, nonce: str) -> None:
    random_suffix = nonce.removeprefix(NONCE_PREFIX)
    assert nonce not in prompt
    assert random_suffix not in prompt
    assert NONCE_PREFIX not in prompt


def _assert_exact_nonce_recalled(text: str, nonce: str) -> None:
    assert text.strip() == nonce


def _assert_nonce_absent(text: str, nonce: str) -> None:
    assert nonce not in text


def _assert_complete_long_response(text: str, *, line_count: int, token: str) -> None:
    expected_lines = [f"LINE-{index} {token}" for index in range(1, line_count + 1)] + [LONG_SENTINEL]
    assert len(text.encode("utf-8")) >= 4096
    assert text.splitlines() == expected_lines
    assert text.endswith(LONG_SENTINEL)


def _user_texts(snapshot: dict[str, object], conversation_ref: str) -> list[str]:
    conversations = snapshot["conversations"]
    assert isinstance(conversations, dict)
    conversation = conversations[conversation_ref]
    assert isinstance(conversation, dict)
    turns = conversation["turns"]
    assert isinstance(turns, list)
    return [turn["text"] for turn in turns if isinstance(turn, dict) and turn.get("role") == "user"]


def test_mock_recall_mode_continuity_is_falsifiable_in_process(mock_chatgpt, tmp_path):
    mock_chatgpt.reset()
    registry = _tmp_registry(tmp_path)
    nonce = _new_nonce()
    plant_prompt = _plant_prompt(nonce)
    recall_prompt = RECALL_PROMPT
    control_prompt = RECALL_PROMPT
    assert control_prompt == recall_prompt
    _assert_recall_prompt_does_not_leak_nonce(recall_prompt, nonce)

    mock_chatgpt.script_next_response("ACK")
    planted = _ask_via_public_api(
        plant_prompt,
        mock_chatgpt=mock_chatgpt,
        registry=registry,
        session_identifier="continuity-session",
    )
    assert planted == "ACK"

    _script_recall_response(mock_chatgpt)
    recalled = _ask_via_public_api(
        recall_prompt,
        mock_chatgpt=mock_chatgpt,
        registry=registry,
        session_identifier="continuity-session",
    )
    _assert_exact_nonce_recalled(recalled, nonce)

    _script_recall_response(mock_chatgpt)
    control = _ask_via_public_api(
        control_prompt,
        mock_chatgpt=mock_chatgpt,
        registry=registry,
        session_identifier="fresh-control-session",
    )
    _assert_nonce_absent(control, nonce)
    assert control == NO_TOKEN_SENTINEL


def test_mock_recall_mode_continuity_survives_cli_subprocesses(mock_chatgpt, tmp_path):
    mock_chatgpt.reset()
    state_dir = tmp_path / "state"
    nonce = _new_nonce()
    plant_prompt = _plant_prompt(nonce)
    recall_prompt = RECALL_PROMPT
    control_prompt = RECALL_PROMPT
    assert control_prompt == recall_prompt
    _assert_recall_prompt_does_not_leak_nonce(recall_prompt, nonce)

    mock_chatgpt.script_next_response("ACK")
    planted = _run_cli_subprocess(
        plant_prompt,
        mock_chatgpt=mock_chatgpt,
        state_dir=state_dir,
        session_identifier="cli-continuity-session",
    )
    assert planted.returncode == 0
    assert planted.stdout == "ACK"
    assert planted.stderr == ""

    registry_path = state_dir / "sessions.json"
    assert registry_path.exists()

    _script_recall_response(mock_chatgpt)
    recalled = _run_cli_subprocess(
        recall_prompt,
        mock_chatgpt=mock_chatgpt,
        state_dir=state_dir,
        session_identifier="cli-continuity-session",
    )
    assert recalled.returncode == 0
    assert recalled.stderr == ""
    _assert_exact_nonce_recalled(recalled.stdout, nonce)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    session_ref = registry["sessions"]["cli-continuity-session"]["conversation_ref"]
    snapshot = mock_chatgpt.inspect()
    assert _user_texts(snapshot, session_ref) == [plant_prompt, recall_prompt]

    _script_recall_response(mock_chatgpt)
    control = _run_cli_subprocess(
        control_prompt,
        mock_chatgpt=mock_chatgpt,
        state_dir=state_dir,
        session_identifier="cli-fresh-control-session",
    )
    assert control.returncode == 0
    assert control.stderr == ""
    _assert_nonce_absent(control.stdout, nonce)
    assert control.stdout == NO_TOKEN_SENTINEL

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    control_ref = registry["sessions"]["cli-fresh-control-session"]["conversation_ref"]
    assert control_ref != session_ref
    snapshot = mock_chatgpt.inspect()
    assert _user_texts(snapshot, control_ref) == [control_prompt]


def test_mock_long_response_completeness_via_public_api(mock_chatgpt, tmp_path):
    mock_chatgpt.reset()
    registry = _tmp_registry(tmp_path)
    token = f"ELICIT-{secrets.token_hex(12)}"
    prompt = _truncation_elicitation_prompt(line_count=LONG_LINE_COUNT, token=token)
    body = _long_response_body(line_count=LONG_LINE_COUNT, token=token)
    assert len(body.encode("utf-8")) >= 4096

    mock_chatgpt.script_next_response(body, streaming=True, stream_reads=2)
    text = _ask_via_public_api(
        prompt,
        mock_chatgpt=mock_chatgpt,
        registry=registry,
        session_identifier="long-response-session",
        timeout_s=5,
    )

    _assert_complete_long_response(text, line_count=LONG_LINE_COUNT, token=token)
