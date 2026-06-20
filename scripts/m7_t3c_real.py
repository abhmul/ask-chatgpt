#!/usr/bin/env python3
"""M7-T3c live CDP revalidation driver.

The script uses only Session.attach/ask/loop/history/detach for live browser work,
writes conversation content only through the gitignored Store data_dir, and emits
safe metadata only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt.errors import AskChatGPTError, HumanActionNeededError
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.session import Session

CDP_VERSION_URL = "http://127.0.0.1:9222/json/version"
DATA_DIR = Path("cache/m7-t3c-real")
REPORT_PATH = Path("team/evidence/reports/M7-T3c.md")
TARGET_CONVERSATION_ID = "6a316aa8"
PONG_PROMPT = "Reply with only the word: PONG"
LOOP_MESSAGE = "continue"
PRIOR_MISSION_SENDS = 1
THIS_RUN_SEND_CAP = 3

SENSITIVE_KEY_PARTS = (
    "authorization",
    "bearer",
    "body",
    "content",
    "content_markdown",
    "cookie",
    "header",
    "markdown",
    "oai",
    "password",
    "prompt",
    "response",
    "secret",
    "text",
    "token",
)
SENSITIVE_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "cookie:",
    "oai-",
    "password",
    "reply with only the word",
    "secret",
    "token",
)


@dataclass
class StopRun(Exception):
    status: str
    code: str
    leg: str
    action: str


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEY_PARTS):
                out[key_text] = "<redacted>"
            else:
                out[key_text] = _scrub(nested)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_scrub(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        lowered = value.lower()
        if value.strip() == LOOP_MESSAGE or any(part in lowered for part in SENSITIVE_VALUE_PARTS):
            return "<redacted>"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return repr(value)


def emit(event: str, **payload: Any) -> None:
    print(json.dumps(_scrub({"event": event, **payload}), sort_keys=True), flush=True)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def git_checks() -> dict[str, Any]:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    cache_staged = run_git(["diff", "--cached", "--name-only", "--", "cache"])
    protected_staged = run_git(
        [
            "diff",
            "--cached",
            "--name-only",
            "--",
            "controller.mjs",
            "issues/cdp-send-repro/controller.mjs",
            "human",
        ]
    )
    stable = run_git(["rev-parse", "stable"])
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "branch_ok_rewrite_v2": branch.stdout.strip() == "rewrite-v2",
        "cache_staged": bool(cache_staged.stdout.strip()),
        "protected_paths_staged": [line for line in protected_staged.stdout.splitlines() if line.strip()],
        "stable_rev": stable.stdout.strip() if stable.returncode == 0 else None,
    }


def preflight_version() -> dict[str, Any]:
    completed = subprocess.run(
        ["curl", "-s", "--max-time", "5", CDP_VERSION_URL],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    result: dict[str, Any] = {
        "ok": False,
        "endpoint": "version",
        "browser": None,
        "protocol_version": None,
        "websocket_url_present": False,
        "error_code": None,
        "error": None,
        "curl_returncode": completed.returncode,
    }
    if completed.returncode != 0:
        result.update({"error_code": "CDP_UNREACHABLE", "error": "curl_failed"})
        return result
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result.update({"error_code": "CDP_UNREACHABLE", "error": "invalid_json"})
        return result
    if not isinstance(data, dict):
        result.update({"error_code": "CDP_UNREACHABLE", "error": "non_object_json"})
        return result
    browser = data.get("Browser") if isinstance(data.get("Browser"), str) else None
    protocol = data.get("Protocol-Version") if isinstance(data.get("Protocol-Version"), str) else None
    ws_present = isinstance(data.get("webSocketDebuggerUrl"), str) and bool(data.get("webSocketDebuggerUrl"))
    result.update(
        {
            "ok": ws_present,
            "browser": browser,
            "protocol_version": protocol,
            "websocket_url_present": ws_present,
            "error_code": None if ws_present else "CDP_UNREACHABLE",
            "error": None if ws_present else "websocket_url_missing",
        }
    )
    return result


def ask_error_summary(exc: BaseException, *, include_details: bool = True) -> dict[str, Any]:
    summary: dict[str, Any] = {"type": type(exc).__name__}
    if isinstance(exc, AskChatGPTError):
        summary.update(
            {
                "code": exc.code,
                "message": exc.message,
                "exit_code": exc.exit_code,
                "retryable": exc.retryable,
                "retry_action": exc.retry_action,
            }
        )
        if include_details:
            summary["details"] = dict(exc.details)
    return _scrub(summary)


def turn_meta(turn: TurnRecord) -> dict[str, Any]:
    return {
        "conversation_id": turn.conversation_id,
        "conversation_url": turn.conversation_url,
        "message_id": turn.message_id,
        "role": turn.role,
        "status": turn.status,
        "partial": turn.partial,
        "char_count": len(turn.content_markdown),
        "capture_source": turn.capture_source,
        "fidelity": turn.fidelity,
        "turn_index": turn.turn_index,
        "user_message_id": turn.user_message_id,
    }


def transcript_meta(transcript: Transcript) -> dict[str, Any]:
    roles: dict[str, int] = {}
    ids_by_role: dict[str, list[str]] = {"user": [], "assistant": []}
    for turn in transcript.turns:
        roles[turn.role] = roles.get(turn.role, 0) + 1
        ids_by_role.setdefault(turn.role, []).append(turn.message_id)
    return {
        "conversation_id": transcript.conversation.conversation_id,
        "conversation_url": transcript.conversation.url,
        "turn_count": len(transcript.turns),
        "roles": roles,
        "ids_by_role": ids_by_role,
        "transcript_path": str(transcript.transcript_path) if transcript.transcript_path else None,
        "raw_mapping_path": str(transcript.raw_mapping_path) if transcript.raw_mapping_path else None,
    }


def prompt_present(transcript: Transcript, prompt: str) -> bool:
    expected = " ".join(prompt.split())
    for turn in transcript.turns:
        if turn.role != "user":
            continue
        if " ".join(turn.content_markdown.split()) == expected:
            return True
    return False


def assistant_present(transcript: Transcript, message_id: str) -> bool:
    return any(turn.role == "assistant" and turn.message_id == message_id for turn in transcript.turns)


def conversation_url_has_id(url: str, conversation_id: str) -> bool:
    return bool(conversation_id) and f"/c/{conversation_id}" in url


def initial_results() -> dict[str, Any]:
    git_start = git_checks()
    return {
        "status": "PARTIAL",
        "preflight": {},
        "send_counts": {"leg_a": None, "leg_b": None, "final": 0, "this_run_cap": THIS_RUN_SEND_CAP},
        "mission_send_total": None,
        "created_conversations": [],
        "leg_a": {
            "assistant": None,
            "checks": {},
            "transcript": None,
            "submissions": None,
            "fresh_draft_ask_none_attempted": False,
            "fresh_draft_submission_without_learned_id": False,
            "error": None,
        },
        "leg_b": {
            "turns": [],
            "before_turn_count": None,
            "after_turn_count": None,
            "expected_after_turn_count": None,
            "distinct_assistant_ids": False,
            "transcript_grew": False,
            "completion_clipping_observed": None,
            "submissions": None,
            "error": None,
        },
        "leg_c": {"status": "SKIPPED", "reason": "optional_read_only_hint_skipped", "hints": []},
        "confirmations": {
            "own_tab_only_via_session_ask_loop": True,
            "no_forbidden_cdp_endpoint_or_tab_walking_in_driver": True,
            "browser_not_quit_session_detach_only": False,
            "no_send_retries": True,
            "send_cap_this_run_leq_3": None,
            "fresh_throwaway_only": True,
            "target_6a316aa8_not_touched": True,
            "no_auth_oai_cookie_bearer_values_logged": True,
            "no_conversation_content_printed_or_reported": True,
            "cache_not_staged": None,
            "controller_mjs_and_human_unstaged": None,
            "stable_unmoved_by_this_script": None,
            "branch_rewrite_v2": git_start.get("branch_ok_rewrite_v2"),
        },
        "blockers": [],
        "signals": [],
        "git_start": git_start,
        "git_end": None,
    }


def append_blocker(results: dict[str, Any], code: str, leg: str, action: str) -> None:
    results["blockers"].append({"code": code, "leg": leg, "action": action})


def raise_stop(results: dict[str, Any], status: str, code: str, leg: str, action: str) -> None:
    append_blocker(results, code, leg, action)
    raise StopRun(status=status, code=code, leg=leg, action=action)


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = results["status"]
    preflight = results.get("preflight") or {}
    send_counts = results.get("send_counts") or {}
    leg_a = results.get("leg_a") or {}
    leg_b = results.get("leg_b") or {}
    leg_c = results.get("leg_c") or {}
    conf = results.get("confirmations") or {}
    git_start = results.get("git_start") or {}
    git_end = results.get("git_end") or {}
    forbidden_endpoint = "/json" + "/list"

    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M7-T3c real send + loop revalidation")
    lines.append("")
    lines.append("## CDP preflight")
    lines.append("- Endpoint used: `/json/version` only.")
    lines.append(f"- Browser version: `{preflight.get('browser')}`")
    lines.append(f"- Protocol-Version: `{preflight.get('protocol_version')}`")
    lines.append(f"- WebSocket URL present: `{preflight.get('websocket_url_present')}`")
    lines.append(f"- Preflight ok/error: `{preflight.get('ok')}` / `{preflight.get('error_code') or preflight.get('error')}`")
    lines.append("")
    lines.append("## Send count")
    final_count = send_counts.get("final")
    mission_total = results.get("mission_send_total")
    lines.append(f"- Exact this-run `send_budget.successful_submissions`: `{final_count}`")
    lines.append(f"- Per-leg cumulative/delta: Leg A=`{send_counts.get('leg_a')}`, Leg B delta=`{send_counts.get('leg_b')}`")
    lines.append(f"- Mission total: prior T3 `1` + this run `{final_count}` = `{mission_total}`")
    lines.append(f"- This-run cap respected (`<=3`): `{conf.get('send_cap_this_run_leq_3')}`")
    lines.append("")
    lines.append("## NEW throwaway conversations created")
    created = results.get("created_conversations") or []
    if created:
        for item in created:
            lines.append(f"- `/c/{item.get('conversation_id')}` — `{item.get('conversation_url')}`")
    else:
        lines.append("- None recorded.")
    lines.append(f"- Protected conversation `6a316aa8` touched: `{not conf.get('target_6a316aa8_not_touched')}`")
    lines.append("")
    lines.append("## Leg A — PONG smoke")
    assistant = leg_a.get("assistant") or {}
    checks = leg_a.get("checks") or {}
    lines.append(f"- Gotcha-4 + id-learned + completion + capture all proven: `{checks.get('all_proven')}`")
    lines.append(f"- Fresh draft `ask(None)` attempted: `{leg_a.get('fresh_draft_ask_none_attempted')}`")
    lines.append(f"- Successful submission happened before id was learned: `{leg_a.get('fresh_draft_submission_without_learned_id')}`")
    lines.append(f"- Draft `/c/<id>` learned: `{checks.get('conversation_url_has_id')}`")
    lines.append(f"- Assistant role/id/status/partial: `{assistant.get('role')}` / `{assistant.get('message_id')}` / `{assistant.get('status')}` / `{assistant.get('partial')}`")
    lines.append(f"- Assistant char-count: `{assistant.get('char_count')}`")
    lines.append(f"- Capture source/fidelity: `{assistant.get('capture_source')}` / `{assistant.get('fidelity')}`")
    lines.append(f"- Transcript user+assistant present: `{checks.get('transcript_user_and_assistant_present')}`")
    lines.append(f"- Transcript prompt user turn present (bool only): `{checks.get('user_prompt_present')}`")
    lines.append(f"- Transcript assistant turn present by id: `{checks.get('assistant_turn_present')}`")
    lines.append(f"- Transcript metadata: `{json.dumps(_scrub(leg_a.get('transcript')), sort_keys=True)}`")
    lines.append(f"- Submissions after Leg A: `{leg_a.get('submissions')}`")
    lines.append(f"- Error: `{json.dumps(_scrub(leg_a.get('error')), sort_keys=True)}`")
    lines.append("")
    lines.append("## Leg B — 2-turn loop")
    lines.append(f"- Exactly 2 iterations yielded: `{len(leg_b.get('turns') or []) == 2}`")
    lines.append(f"- Two distinct assistant ids, distinct from Leg A: `{leg_b.get('distinct_assistant_ids')}`")
    lines.append(f"- Transcript grew: `{leg_b.get('transcript_grew')}`")
    lines.append(f"- Turn counts before/after/expected-after: `{leg_b.get('before_turn_count')}` / `{leg_b.get('after_turn_count')}` / `{leg_b.get('expected_after_turn_count')}`")
    lines.append(f"- Completion clipping observed: `{leg_b.get('completion_clipping_observed')}`")
    lines.append(f"- Per-turn metadata: `{json.dumps(_scrub(leg_b.get('turns')), sort_keys=True)}`")
    lines.append(f"- Submissions after Leg B: `{leg_b.get('submissions')}`")
    lines.append(f"- Error: `{json.dumps(_scrub(leg_b.get('error')), sort_keys=True)}`")
    lines.append("")
    lines.append("## M8 leg-1 selector hints")
    lines.append(f"- Leg C status: `{leg_c.get('status')}`; reason: `{leg_c.get('reason')}`")
    hints = leg_c.get("hints") or []
    if hints:
        lines.append(f"- Button structural attributes only: `{json.dumps(_scrub(hints), sort_keys=True)}`")
    else:
        lines.append("- Not run.")
    lines.append("")
    lines.append("## Confirmations")
    lines.append(f"- Branch at start/end: `{git_start.get('branch')}` / `{git_end.get('branch')}`")
    lines.append(f"- Own-tab-only via Session/ask/loop: `{conf.get('own_tab_only_via_session_ask_loop')}`")
    lines.append(f"- No `{forbidden_endpoint}` call and no ad-hoc tab walking in driver: `{conf.get('no_forbidden_cdp_endpoint_or_tab_walking_in_driver')}`")
    lines.append(f"- Browser not quit; Session.detach only: `{conf.get('browser_not_quit_session_detach_only')}`")
    lines.append(f"- No send retries: `{conf.get('no_send_retries')}`")
    lines.append(f"- Fresh throwaway only: `{conf.get('fresh_throwaway_only')}`")
    lines.append(f"- No auth/OAI/cookie/bearer values logged: `{conf.get('no_auth_oai_cookie_bearer_values_logged')}`")
    lines.append(f"- No conversation content printed or reported: `{conf.get('no_conversation_content_printed_or_reported')}`")
    lines.append(f"- `cache/` not staged: `{conf.get('cache_not_staged')}`")
    lines.append(f"- `controller.mjs` and `human/` unstaged: `{conf.get('controller_mjs_and_human_unstaged')}`")
    lines.append(f"- `stable` unmoved by this script: `{conf.get('stable_unmoved_by_this_script')}`")
    lines.append(f"- Stable rev start/end: `{git_start.get('stable_rev')}` / `{git_end.get('stable_rev')}`")
    lines.append("")
    lines.append("## Blockers")
    blockers = results.get("blockers") or []
    if blockers:
        for item in blockers:
            lines.append(f"- `{item.get('code')}` in `{item.get('leg')}`: {item.get('action')}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Signals")
    signals = results.get("signals") or []
    if signals:
        for item in signals:
            lines.append(f"- {item}")
    else:
        lines.append("- No paradigm-shift signal; task stayed procedural.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = initial_results()
    stable_start = (results.get("git_start") or {}).get("stable_rev")
    session: Session | None = None
    phase = "leg0"
    leg_a_submissions = 0

    try:
        preflight = preflight_version()
        results["preflight"] = preflight
        emit("preflight", preflight=preflight)
        if preflight.get("ok") is not True:
            raise_stop(results, "BLOCKED", "CDP_UNREACHABLE", "leg0", "Expose Chrome CDP on 127.0.0.1:9222 and rerun; no send attempted.")
        if not (results.get("git_start") or {}).get("branch_ok_rewrite_v2"):
            raise_stop(results, "BLOCKED", "WRONG_BRANCH", "pre-run", "Switch to branch rewrite-v2 before running live sends.")

        phase = "attach"
        session = Session(channel="cdp", data_dir=DATA_DIR)
        session.attach()
        emit("attached", data_dir=str(DATA_DIR))

        phase = "leg_a"
        results["leg_a"]["fresh_draft_ask_none_attempted"] = True
        rec = session.ask(None, PONG_PROMPT, timeout=90)
        leg_a_submissions = session.send_budget.successful_submissions
        results["send_counts"]["leg_a"] = leg_a_submissions
        results["leg_a"]["submissions"] = leg_a_submissions
        results["leg_a"]["assistant"] = turn_meta(rec)
        if rec.conversation_id == TARGET_CONVERSATION_ID:
            results["confirmations"]["target_6a316aa8_not_touched"] = False
            raise_stop(results, "BLOCKED", "TARGET_CONVERSATION_MATCH", "leg_a", "ask(None) resolved to the protected conversation id; stop and audit before any retry.")
        results["created_conversations"].append(
            {"conversation_id": rec.conversation_id, "conversation_url": rec.conversation_url}
        )
        hist_a = session.history(rec.conversation_id)
        transcript_a = transcript_meta(hist_a)
        roles_a = transcript_a.get("roles") or {}
        checks_a = {
            "role_is_assistant": rec.role == "assistant",
            "conversation_id_present": bool(rec.conversation_id),
            "conversation_id_not_target": rec.conversation_id != TARGET_CONVERSATION_ID,
            "conversation_url_has_id": conversation_url_has_id(rec.conversation_url, rec.conversation_id),
            "status_complete": rec.status == "complete",
            "partial_false": rec.partial is False,
            "content_nonempty": len(rec.content_markdown) > 0,
            "user_prompt_present": prompt_present(hist_a, PONG_PROMPT),
            "assistant_turn_present": assistant_present(hist_a, rec.message_id),
            "transcript_user_and_assistant_present": roles_a.get("user", 0) >= 1 and roles_a.get("assistant", 0) >= 1,
            "transcript_turn_count": len(hist_a.turns),
            "transcript_roles": roles_a,
            "capture_source_present": bool(rec.capture_source),
            "fidelity_present": bool(rec.fidelity),
        }
        checks_a["gotcha4_capture_proven"] = bool(
            checks_a["user_prompt_present"] and checks_a["assistant_turn_present"]
        )
        checks_a["all_proven"] = all(
            [
                checks_a["role_is_assistant"],
                checks_a["conversation_id_present"],
                checks_a["conversation_id_not_target"],
                checks_a["conversation_url_has_id"],
                checks_a["status_complete"],
                checks_a["partial_false"],
                checks_a["content_nonempty"],
                checks_a["gotcha4_capture_proven"],
                checks_a["transcript_user_and_assistant_present"],
                checks_a["capture_source_present"],
                checks_a["fidelity_present"],
            ]
        )
        results["leg_a"]["checks"] = checks_a
        results["leg_a"]["transcript"] = transcript_a
        emit("leg_a_complete", submissions=leg_a_submissions, assistant=results["leg_a"]["assistant"], checks=checks_a)
        if leg_a_submissions != 1:
            raise_stop(results, "PARTIAL", "SEND_COUNT_MISMATCH_LEG_A", "leg_a", "Expected exactly one successful submission after PONG smoke; do not run loop.")
        if not checks_a["all_proven"]:
            raise_stop(results, "PARTIAL", "LEG_A_VERIFICATION_FAILED", "leg_a", "PONG smoke did not fully prove id/completion/capture; do not run loop or resend.")

        phase = "leg_b"
        hist_before = session.history(rec.conversation_url)
        before_count = len(hist_before.turns)
        expected_after = before_count + 4
        results["leg_b"]["before_turn_count"] = before_count
        results["leg_b"]["expected_after_turn_count"] = expected_after
        loop_records: list[TurnRecord] = []
        for turn in session.loop(rec.conversation_url, message=LOOP_MESSAGE, max_iterations=2, timeout=90):
            loop_records.append(turn)
            current_hist = session.history(rec.conversation_url)
            per_turn = turn_meta(turn)
            per_turn.update(
                {
                    "iteration": len(loop_records),
                    "appended_to_transcript": assistant_present(current_hist, turn.message_id),
                    "transcript_turn_count_after_yield": len(current_hist.turns),
                    "distinct_from_leg_a": turn.message_id != rec.message_id,
                }
            )
            results["leg_b"]["turns"].append(per_turn)
            emit("leg_b_turn", iteration=len(loop_records), turn=per_turn, submissions=session.send_budget.successful_submissions)
        hist_after = session.history(rec.conversation_url)
        after_count = len(hist_after.turns)
        ids = [turn.message_id for turn in loop_records]
        distinct_ids = len(ids) == 2 and len(set(ids)) == 2 and rec.message_id not in set(ids)
        transcript_grew = after_count >= expected_after and all(assistant_present(hist_after, turn.message_id) for turn in loop_records)
        completion_clipping = any(turn.partial or turn.status != "complete" for turn in loop_records)
        final_after_b = session.send_budget.successful_submissions
        results["send_counts"]["leg_b"] = final_after_b - leg_a_submissions
        results["leg_b"].update(
            {
                "after_turn_count": after_count,
                "distinct_assistant_ids": distinct_ids,
                "transcript_grew": transcript_grew,
                "completion_clipping_observed": completion_clipping,
                "submissions": final_after_b,
            }
        )
        emit(
            "leg_b_complete",
            yielded=len(loop_records),
            distinct_assistant_ids=distinct_ids,
            transcript_grew=transcript_grew,
            completion_clipping_observed=completion_clipping,
            submissions=final_after_b,
        )
        if final_after_b != 3 or results["send_counts"]["leg_b"] != 2:
            raise_stop(results, "PARTIAL", "SEND_COUNT_MISMATCH_LEG_B", "leg_b", "Expected final successful_submissions to equal 3 with two loop submissions; do not send again.")
        if len(loop_records) != 2 or not distinct_ids or not transcript_grew or completion_clipping:
            raise_stop(results, "PARTIAL", "LEG_B_VERIFICATION_FAILED", "leg_b", "Loop did not fully prove two complete distinct assistant turns and transcript growth; do not send again.")

        results["status"] = "DONE"
    except StopRun as stop:
        results["status"] = stop.status
        results["signals"].append(f"Stopped at {stop.leg}: {stop.code}.")
        emit("stopped", status=stop.status, leg=stop.leg, code=stop.code)
    except HumanActionNeededError as exc:
        results["status"] = "BLOCKED"
        append_blocker(results, "HUMAN-ACTION-NEEDED", phase, "Operator must clear login/Cloudflare/human action; no retry-spam from this task.")
        error = ask_error_summary(exc)
        if phase == "leg_a":
            results["leg_a"]["error"] = error
        elif phase == "leg_b":
            results["leg_b"]["error"] = error
        emit("blocked", reason="HUMAN-ACTION-NEEDED", phase=phase, error=error)
    except AskChatGPTError as exc:
        if session is not None and session.send_budget.successful_submissions > 0:
            results["status"] = "PARTIAL"
        else:
            results["status"] = "BLOCKED"
        partial = getattr(exc, "partial", None)
        partial_meta = turn_meta(partial) if isinstance(partial, TurnRecord) else None
        error = {**ask_error_summary(exc), "partial": partial_meta}
        if phase == "leg_a" or results["leg_a"].get("assistant") is None:
            results["leg_a"]["error"] = error
        else:
            results["leg_b"]["error"] = error
        append_blocker(results, getattr(exc, "code", type(exc).__name__), phase, "Inspect safe error metadata and gitignored cache; do not retry-spam live ChatGPT.")
        emit("ask_chatgpt_error", phase=phase, error=error)
    except Exception as exc:  # noqa: BLE001 - fail closed with safe metadata only.
        if session is not None and session.send_budget.successful_submissions > 0:
            results["status"] = "PARTIAL"
        else:
            results["status"] = "BLOCKED"
        append_blocker(results, type(exc).__name__, phase, "Fix the driver/source issue; respect remaining live-send budget before rerun.")
        emit("driver_error", phase=phase, error={"type": type(exc).__name__})
    finally:
        if session is not None:
            final_count = session.send_budget.successful_submissions
            results["send_counts"]["final"] = final_count
            if results["send_counts"].get("leg_a") is None and final_count <= 1:
                results["send_counts"]["leg_a"] = final_count
                results["leg_a"]["submissions"] = final_count
            if results["send_counts"].get("leg_b") is None:
                results["send_counts"]["leg_b"] = max(0, final_count - int(results["send_counts"].get("leg_a") or 0))
            if (
                results["leg_a"].get("fresh_draft_ask_none_attempted")
                and results["leg_a"].get("assistant") is None
                and final_count > 0
            ):
                results["leg_a"]["fresh_draft_submission_without_learned_id"] = True
            try:
                session.detach()
                results["confirmations"]["browser_not_quit_session_detach_only"] = True
            except Exception as exc:  # noqa: BLE001 - report detach failure safely.
                results["confirmations"]["browser_not_quit_session_detach_only"] = False
                append_blocker(results, "DETACH_FAILED", "teardown", f"Session.detach raised {type(exc).__name__}; inspect own managed tabs only.")
                emit("detach_error", error={"type": type(exc).__name__})
        else:
            results["send_counts"]["final"] = 0
            if results["send_counts"].get("leg_a") is None:
                results["send_counts"]["leg_a"] = 0
            if results["send_counts"].get("leg_b") is None:
                results["send_counts"]["leg_b"] = 0
        final_count = int(results["send_counts"].get("final") or 0)
        results["mission_send_total"] = PRIOR_MISSION_SENDS + final_count
        results["confirmations"]["send_cap_this_run_leq_3"] = final_count <= THIS_RUN_SEND_CAP
        results["git_end"] = git_checks()
        git_end = results.get("git_end") or {}
        results["confirmations"]["cache_not_staged"] = not bool(git_end.get("cache_staged"))
        results["confirmations"]["controller_mjs_and_human_unstaged"] = not bool(git_end.get("protected_paths_staged"))
        stable_end = git_end.get("stable_rev")
        if stable_start and stable_end:
            results["confirmations"]["stable_unmoved_by_this_script"] = stable_start == stable_end
        write_report(results)
        emit("report_written", status=results["status"], report=str(REPORT_PATH), final_send_count=final_count)
    return 0 if results["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
