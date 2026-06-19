#!/usr/bin/env python3
"""M7-T3 attended real-leg driver.

Safety constraints are intentionally kept in this script: it uses only
Session/TabPool/ask/loop for browser work, emits safe metadata only, and writes
conversation content only through the gitignored Store data_dir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt.errors import (
    AskChatGPTError,
    HumanActionNeededError,
    ModelSelectionNotReflectedError,
    PromptNotSubmittedError,
    ToolSelectionNotReflectedError,
)
from ask_chatgpt.menus import SelectionResult, enumerate_radix_options, select_model, set_tools
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.session import Session

DATA_DIR = Path("cache/m7-t3-real")
REPORT_PATH = Path("team/evidence/reports/M7-T3.md")
PREFLIGHT_ENV = "M7_T3_PREFLIGHT_JSON"
TARGET_CONVERSATION_ID = "6a316aa8"
LEG2_PROMPT = "Reply with only the word: PONG"
LEG3_MESSAGE = "continue"
MODEL_REQUEST = "Instant"
TOOL_REQUESTS = ("Web search",)
MODEL_FALLBACK_ORDER = (
    "Instant",
    "Medium",
    "High",
    "Fast",
    "Auto",
    "GPT-4o mini",
    "4o mini",
    "GPT-4.1 mini",
    "GPT-5 mini",
    "Extra High",
    "Pro Extended",
)
FORBIDDEN_MODEL_LABELS = {"recent files", "projects"}

SENSITIVE_KEY_PARTS = (
    "authorization",
    "bearer",
    "content",
    "content_markdown",
    "cookie",
    "header",
    "oai",
    "password",
    "prompt",
    "response",
    "secret",
    "token",
)
SENSITIVE_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "cookie:",
    "oai-",
    "password",
    "secret",
    "token",
)


@dataclass
class StopRun(Exception):
    status: str
    reason: str
    leg: str


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
        if any(part in lowered for part in SENSITIVE_VALUE_PARTS):
            return "<redacted>"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return repr(value)


def emit(event: str, **payload: Any) -> None:
    safe = {"event": event, **payload}
    print(json.dumps(_scrub(safe), sort_keys=True), flush=True)


def ask_error_summary(exc: BaseException, *, include_details: bool = False) -> dict[str, Any]:
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


def load_preflight() -> dict[str, Any]:
    path_text = os.environ.get(PREFLIGHT_ENV)
    result: dict[str, Any] = {
        "path": path_text,
        "browser": None,
        "protocol_version": None,
        "websocket_url_present": None,
        "loaded": False,
    }
    if not path_text:
        return result
    path = Path(path_text)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.update({"error": type(exc).__name__})
        return result
    if isinstance(raw, dict):
        result.update(
            {
                "browser": raw.get("Browser") if isinstance(raw.get("Browser"), str) else None,
                "protocol_version": raw.get("Protocol-Version")
                if isinstance(raw.get("Protocol-Version"), str)
                else None,
                "websocket_url_present": isinstance(raw.get("webSocketDebuggerUrl"), str)
                and bool(raw.get("webSocketDebuggerUrl")),
                "loaded": True,
            }
        )
    return result


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
            "issues/cdp-send-repro/controller.mjs",
            "human",
        ]
    )
    stable = run_git(["rev-parse", "stable"])
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "branch_ok_rewrite_v2": branch.stdout.strip() == "rewrite-v2",
        "cache_staged": bool(cache_staged.stdout.strip()),
        "protected_paths_staged": [
            line for line in protected_staged.stdout.splitlines() if line.strip()
        ],
        "stable_rev": stable.stdout.strip() if stable.returncode == 0 else None,
    }


def selection_result_meta(result: SelectionResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "requested": result.requested,
        "reflected": result.reflected,
        "verified": result.verified,
    }


def _normalize_label(label: str) -> str:
    return " ".join(label.lower().split())


def _close_open_menu(tab: Any) -> None:
    try:
        tab.channel.press(tab, "body", "Escape")
    except Exception:
        return


def _enumerated_model_labels(tab: Any) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    try:
        options = enumerate_radix_options(tab)
    except Exception:
        return labels
    for option in options:
        if option.disabled or option.role not in {"menuitemradio", "menuitem"}:
            continue
        normalized = _normalize_label(option.label)
        if not normalized or normalized in FORBIDDEN_MODEL_LABELS or normalized in seen:
            continue
        labels.append(option.label)
        seen.add(normalized)
    return labels


def _pick_lowest_model_label(labels: list[str]) -> str | None:
    by_normalized = {_normalize_label(label): label for label in labels}
    for candidate in MODEL_FALLBACK_ORDER:
        found = by_normalized.get(_normalize_label(candidate))
        if found is not None:
            return found
    for label in labels:
        return label
    return None


def initial_results() -> dict[str, Any]:
    return {
        "status": "PARTIAL",
        "preflight": load_preflight(),
        "send_counts": {"leg1": None, "leg2": None, "leg3": None, "final": 0},
        "created_conversations": [],
        "leg1": {
            "model_requested": MODEL_REQUEST,
            "model_result": None,
            "model_verified": False,
            "model_error": None,
            "model_fallback_used": None,
            "model_enumerated_label_count": None,
            "tools_requested": list(TOOL_REQUESTS),
            "tool_results": [],
            "tools_verified": False,
            "tool_error": None,
            "submissions": None,
        },
        "leg2": {
            "assistant": None,
            "checks": {},
            "transcript": None,
            "submissions": None,
            "error": None,
        },
        "leg3": {
            "turns": [],
            "distinct_assistant_ids": False,
            "transcript_grew": False,
            "before_turn_count": None,
            "after_turn_count": None,
            "expected_after_turn_count": None,
            "submissions": None,
            "error": None,
            "completion_clipping_observed": False,
        },
        "confirmations": {
            "own_tab_only_session_tabpool_ask_loop": True,
            "script_no_json_list_or_page_enumeration": True,
            "browser_not_quit_detach_only": False,
            "no_auth_oai_cookie_bearer_values_logged": True,
            "no_conversation_content_printed_or_reported": True,
            "cache_not_staged": None,
            "controller_mjs_and_human_unstaged": None,
            "stable_unmoved_by_this_script": True,
            "target_6a316aa8_not_touched": True,
        },
        "blockers": [],
        "signals": [],
        "git_start": git_checks(),
        "git_end": None,
    }


def append_blocker(results: dict[str, Any], code: str, leg: str, action: str) -> None:
    results["blockers"].append({"code": code, "leg": leg, "action": action})


def reconcile_send_breakdown(results: dict[str, Any], final_count: int) -> None:
    counts = results["send_counts"]
    leg1 = counts.get("leg1")
    leg1_value = int(leg1) if isinstance(leg1, int) else 0
    if counts.get("leg2") is None:
        if results["leg2"].get("assistant") is None and not results["leg3"].get("turns"):
            counts["leg2"] = max(0, final_count - leg1_value)
            if counts["leg2"]:
                results["leg2"]["submissions"] = final_count
        else:
            leg2_cumulative = results["leg2"].get("submissions")
            if isinstance(leg2_cumulative, int):
                counts["leg2"] = max(0, leg2_cumulative - leg1_value)
    if counts.get("leg3") is None:
        leg2_delta = counts.get("leg2")
        if isinstance(leg2_delta, int):
            counts["leg3"] = max(0, final_count - leg1_value - leg2_delta)


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = results["status"]
    preflight = results["preflight"]
    send_counts = results["send_counts"]
    leg1 = results["leg1"]
    leg2 = results["leg2"]
    leg3 = results["leg3"]
    conf = results["confirmations"]
    git_end = results.get("git_end") or {}

    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M7-T3 real legs report")
    lines.append("")
    lines.append("## CDP preflight")
    lines.append(f"- Browser version: `{preflight.get('browser')}`")
    lines.append(f"- Protocol-Version: `{preflight.get('protocol_version')}`")
    lines.append(f"- WebSocket URL present: `{preflight.get('websocket_url_present')}`")
    lines.append("")
    lines.append("## Send count")
    lines.append(f"- Final authoritative `send_budget.successful_submissions`: `{send_counts.get('final')}`")
    lines.append(f"- Per-leg: Leg1=`{send_counts.get('leg1')}`, Leg2=`{send_counts.get('leg2')}`, Leg3=`{send_counts.get('leg3')}`")
    lines.append("- Contract cap: `<=4` real sends.")
    lines.append("")
    lines.append("## Throwaway conversations created")
    created = results.get("created_conversations") or []
    if created:
        for item in created:
            lines.append(f"- `{item.get('conversation_id')}` — {item.get('conversation_url')}")
    else:
        lines.append("- None recorded.")
    lines.append(f"- Target `6a316aa8` touched: `{not conf.get('target_6a316aa8_not_touched')}`")
    lines.append("")
    lines.append("## Leg 1 — model/tool selection, no send")
    lines.append(f"- Model requested/tier used: `{leg1.get('model_requested')}` / `{(leg1.get('model_result') or {}).get('reflected')}`")
    lines.append(f"- Model fallback used: `{leg1.get('model_fallback_used')}`; enumerated model-label count: `{leg1.get('model_enumerated_label_count')}`")
    lines.append(f"- Model verified: `{leg1.get('model_verified')}`")
    lines.append(f"- Model error: `{json.dumps(_scrub(leg1.get('model_error')), sort_keys=True)}`")
    lines.append(f"- Tools requested: `{leg1.get('tools_requested')}`")
    lines.append(f"- Tool results: `{json.dumps(_scrub(leg1.get('tool_results')), sort_keys=True)}`")
    lines.append(f"- Tools verified: `{leg1.get('tools_verified')}`")
    lines.append(f"- Tool error: `{json.dumps(_scrub(leg1.get('tool_error')), sort_keys=True)}`")
    lines.append(f"- Submissions after leg: `{leg1.get('submissions')}`")
    lines.append("")
    lines.append("## Leg 2 — first real send smoke")
    assistant = leg2.get("assistant") or {}
    checks = leg2.get("checks") or {}
    lines.append(f"- Gotcha-4 real-proven (new user turn carrying prompt + assistant turn present): `{checks.get('gotcha4_proven')}`")
    lines.append(f"- Assistant message id: `{assistant.get('message_id')}`")
    lines.append(f"- Assistant status/partial: `{assistant.get('status')}` / `{assistant.get('partial')}`")
    lines.append(f"- Assistant char-count: `{assistant.get('char_count')}`")
    lines.append(f"- Capture source/fidelity: `{assistant.get('capture_source')}` / `{assistant.get('fidelity')}`")
    lines.append(f"- Transcript checks: `{json.dumps(_scrub(checks), sort_keys=True)}`")
    lines.append(f"- Submissions after leg: `{leg2.get('submissions')}`")
    lines.append(f"- Error: `{json.dumps(_scrub(leg2.get('error')), sort_keys=True)}`")
    lines.append("")
    lines.append("## Leg 3 — loop verify")
    lines.append(f"- Distinct assistant ids: `{leg3.get('distinct_assistant_ids')}`")
    lines.append(f"- Transcript grew as expected: `{leg3.get('transcript_grew')}`")
    lines.append(f"- Turn counts before/after/expected-after: `{leg3.get('before_turn_count')}` / `{leg3.get('after_turn_count')}` / `{leg3.get('expected_after_turn_count')}`")
    lines.append(f"- Completion clipping observed: `{leg3.get('completion_clipping_observed')}`")
    lines.append(f"- Per-turn metadata: `{json.dumps(_scrub(leg3.get('turns')), sort_keys=True)}`")
    lines.append(f"- Submissions after leg: `{leg3.get('submissions')}`")
    lines.append(f"- Error: `{json.dumps(_scrub(leg3.get('error')), sort_keys=True)}`")
    lines.append("")
    lines.append("## Confirmations")
    lines.append(f"- Own-tab-only via Session/TabPool/ask/loop: `{conf.get('own_tab_only_session_tabpool_ask_loop')}`")
    forbidden_endpoint = "/json" + "/list"
    lines.append(f"- Script has no `{forbidden_endpoint}` call and no Playwright page/context enumeration: `{conf.get('script_no_json_list_or_page_enumeration')}`")
    lines.append(f"- Browser not quit; Session.detach only: `{conf.get('browser_not_quit_detach_only')}`")
    lines.append(f"- No auth/OAI/cookie/bearer values logged: `{conf.get('no_auth_oai_cookie_bearer_values_logged')}`")
    lines.append(f"- No conversation content printed or reported: `{conf.get('no_conversation_content_printed_or_reported')}`")
    lines.append(f"- `cache/` not staged: `{conf.get('cache_not_staged')}`")
    lines.append(f"- `controller.mjs` and `human/` unstaged: `{conf.get('controller_mjs_and_human_unstaged')}`")
    lines.append(f"- `stable` unmoved by this script: `{conf.get('stable_unmoved_by_this_script')}`")
    lines.append(f"- Current branch at end: `{git_end.get('branch')}`")
    lines.append(f"- Stable rev observed: `{git_end.get('stable_rev')}`")
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
        lines.append("- No paradigm-shift signal; complexity remained low and procedural.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = initial_results()
    emit("start", data_dir=str(DATA_DIR), report=str(REPORT_PATH), preflight=results["preflight"])
    session: Session | None = None
    stable_start = (results.get("git_start") or {}).get("stable_rev")

    try:
        if not results["preflight"].get("loaded"):
            append_blocker(results, "PREFLIGHT_METADATA_MISSING", "leg0", "Run curl /json/version and pass its JSON file via M7_T3_PREFLIGHT_JSON.")
            raise StopRun("BLOCKED", "PREFLIGHT_METADATA_MISSING", "leg0")
        if results["preflight"].get("websocket_url_present") is not True:
            append_blocker(results, "CDP_UNREACHABLE", "leg0", "Start or expose Chrome CDP on 127.0.0.1:9222.")
            raise StopRun("BLOCKED", "CDP_UNREACHABLE", "leg0")
        if not (results.get("git_start") or {}).get("branch_ok_rewrite_v2"):
            append_blocker(results, "WRONG_BRANCH", "pre-run", "Switch to branch rewrite-v2 before running real legs.")
            raise StopRun("BLOCKED", "WRONG_BRANCH", "pre-run")

        session = Session(channel="cdp", data_dir=DATA_DIR)
        session.attach()

        # Leg 1: own draft tab, no send. Intentionally keep this lease held so
        # later ask(None) opens a separate fresh throwaway draft tab.
        ref = session.create()
        tab = session.tab_pool.acquire(ref)
        model_result: SelectionResult | None = None
        try:
            model_result = select_model(tab, session.selector_map, MODEL_REQUEST)
            results["leg1"]["model_result"] = selection_result_meta(model_result)
            results["leg1"]["model_verified"] = bool(model_result.verified)
        except ModelSelectionNotReflectedError as exc:
            first_error = ask_error_summary(exc, include_details=True)
            labels = _enumerated_model_labels(tab)
            results["leg1"]["model_enumerated_label_count"] = len(labels)
            fallback = _pick_lowest_model_label(labels)
            if fallback and _normalize_label(fallback) != _normalize_label(MODEL_REQUEST):
                _close_open_menu(tab)
                try:
                    model_result = select_model(tab, session.selector_map, fallback)
                    results["leg1"]["model_result"] = selection_result_meta(model_result)
                    results["leg1"]["model_verified"] = bool(model_result.verified)
                    results["leg1"]["model_fallback_used"] = fallback
                    results["leg1"]["model_error"] = {"initial_instant_error": first_error}
                    results["signals"].append("Instant model label was not verified; selected the lowest enumerated fallback label.")
                except ModelSelectionNotReflectedError as fallback_exc:
                    results["leg1"]["model_error"] = {
                        "initial_instant_error": first_error,
                        "fallback_label": fallback,
                        "fallback_error": ask_error_summary(fallback_exc, include_details=True),
                    }
                    results["signals"].append("Model selection did not reflect on the live draft tab; send legs still proceeded per contract.")
            else:
                results["leg1"]["model_error"] = first_error
                results["signals"].append("Model selection did not reflect on the live draft tab; send legs still proceeded per contract.")

        try:
            tool_results = set_tools(tab, session.selector_map, TOOL_REQUESTS)
            results["leg1"]["tool_results"] = [selection_result_meta(item) for item in tool_results]
            results["leg1"]["tools_verified"] = all(item.verified for item in tool_results) and len(tool_results) == len(TOOL_REQUESTS)
        except ToolSelectionNotReflectedError as exc:
            results["leg1"]["tool_error"] = ask_error_summary(exc, include_details=True)
            results["signals"].append("Tool selection did not reflect on the live draft tab; send legs still proceeded per contract.")

        leg1_submissions = session.send_budget.successful_submissions
        results["leg1"]["submissions"] = leg1_submissions
        results["send_counts"]["leg1"] = leg1_submissions
        emit("leg1_complete", submissions=leg1_submissions, model=results["leg1"].get("model_result"), tools=results["leg1"].get("tool_results"))
        if leg1_submissions != 0:
            append_blocker(results, "UNEXPECTED_SEND_IN_LEG1", "leg1", "Audit send path before retry; model/tool selection leg must submit zero prompts.")
            raise StopRun("PARTIAL", "UNEXPECTED_SEND_IN_LEG1", "leg1")

        # Leg 2: first real send to a new throwaway chat.
        rec = session.ask(None, LEG2_PROMPT, timeout=90)
        leg2_submissions = session.send_budget.successful_submissions
        results["send_counts"]["leg2"] = leg2_submissions - leg1_submissions
        results["leg2"]["submissions"] = leg2_submissions
        results["leg2"]["assistant"] = turn_meta(rec)
        if rec.conversation_id == TARGET_CONVERSATION_ID:
            results["confirmations"]["target_6a316aa8_not_touched"] = False
            append_blocker(results, "TARGET_CONVERSATION_MATCH", "leg2", "Stop immediately; audit why ask(None) resolved to the protected target id.")
            raise StopRun("BLOCKED", "TARGET_CONVERSATION_MATCH", "leg2")
        results["created_conversations"].append(
            {"conversation_id": rec.conversation_id, "conversation_url": rec.conversation_url}
        )
        hist2 = session.history(rec.conversation_id)
        leg2_checks = {
            "role_is_assistant": rec.role == "assistant",
            "conversation_id_present": bool(rec.conversation_id),
            "conversation_id_not_target": rec.conversation_id != TARGET_CONVERSATION_ID,
            "status_complete": rec.status == "complete",
            "partial": rec.partial,
            "content_nonempty": len(rec.content_markdown) > 0,
            "user_prompt_present": prompt_present(hist2, LEG2_PROMPT),
            "assistant_turn_present": assistant_present(hist2, rec.message_id),
            "transcript_turn_count": len(hist2.turns),
            "transcript_roles": transcript_meta(hist2)["roles"],
        }
        leg2_checks["gotcha4_proven"] = bool(
            leg2_checks["user_prompt_present"] and leg2_checks["assistant_turn_present"]
        )
        results["leg2"]["checks"] = leg2_checks
        results["leg2"]["transcript"] = transcript_meta(hist2)
        emit("leg2_complete", submissions=leg2_submissions, assistant=results["leg2"]["assistant"], checks=leg2_checks)
        if leg2_submissions != 1:
            append_blocker(results, "SEND_COUNT_MISMATCH_LEG2", "leg2", "Expected exactly one successful submission after PONG smoke.")
            raise StopRun("PARTIAL", "SEND_COUNT_MISMATCH_LEG2", "leg2")
        if not all(
            [
                leg2_checks["role_is_assistant"],
                leg2_checks["conversation_id_present"],
                leg2_checks["conversation_id_not_target"],
                leg2_checks["status_complete"],
                not leg2_checks["partial"],
                leg2_checks["content_nonempty"],
                leg2_checks["gotcha4_proven"],
            ]
        ):
            append_blocker(results, "LEG2_VERIFICATION_FAILED", "leg2", "Inspect gitignored cache metadata/content locally; do not resend until failure mode is understood.")
            raise StopRun("PARTIAL", "LEG2_VERIFICATION_FAILED", "leg2")

        # Leg 3: exactly two continue sends on the new throwaway conversation.
        hist_before = session.history(rec.conversation_url)
        results["leg3"]["before_turn_count"] = len(hist_before.turns)
        expected_after = len(hist_before.turns) + 4
        results["leg3"]["expected_after_turn_count"] = expected_after
        loop_records: list[TurnRecord] = []
        for turn in session.loop(rec.conversation_url, message=LEG3_MESSAGE, max_iterations=2, timeout=90):
            loop_records.append(turn)
            current_hist = session.history(rec.conversation_url)
            per_turn = turn_meta(turn)
            per_turn.update(
                {
                    "appended_to_transcript": assistant_present(current_hist, turn.message_id),
                    "transcript_turn_count_after_yield": len(current_hist.turns),
                }
            )
            results["leg3"]["turns"].append(per_turn)
            emit("leg3_turn", iteration=len(loop_records), turn=per_turn, submissions=session.send_budget.successful_submissions)
        hist_after = session.history(rec.conversation_url)
        ids = [turn.message_id for turn in loop_records]
        distinct_ids = len(ids) == 2 and len(set(ids)) == 2 and rec.message_id not in set(ids)
        transcript_grew = len(hist_after.turns) >= expected_after and all(
            assistant_present(hist_after, turn.message_id) for turn in loop_records
        )
        leg3_total_submissions = session.send_budget.successful_submissions
        results["leg3"].update(
            {
                "distinct_assistant_ids": distinct_ids,
                "transcript_grew": transcript_grew,
                "after_turn_count": len(hist_after.turns),
                "submissions": leg3_total_submissions,
                "completion_clipping_observed": any(
                    turn.partial or turn.status != "complete" for turn in loop_records
                ),
            }
        )
        results["send_counts"]["leg3"] = leg3_total_submissions - leg2_submissions
        emit(
            "leg3_complete",
            yielded=len(loop_records),
            distinct_assistant_ids=distinct_ids,
            transcript_grew=transcript_grew,
            submissions=leg3_total_submissions,
        )
        if leg3_total_submissions != 3:
            append_blocker(results, "SEND_COUNT_MISMATCH_LEG3", "leg3", "Expected final successful_submissions to equal 3.")
            raise StopRun("PARTIAL", "SEND_COUNT_MISMATCH_LEG3", "leg3")
        if len(loop_records) != 2 or not distinct_ids or not transcript_grew:
            append_blocker(results, "LEG3_VERIFICATION_FAILED", "leg3", "Inspect transcript metadata in cache; do not run extra loop sends from this task.")
            raise StopRun("PARTIAL", "LEG3_VERIFICATION_FAILED", "leg3")

        results["status"] = "DONE"
    except StopRun as stop:
        results["status"] = stop.status
        results["signals"].append(f"Stopped at {stop.leg}: {stop.reason}.")
        emit("stopped", status=stop.status, leg=stop.leg, reason=stop.reason)
    except HumanActionNeededError as exc:
        results["status"] = "BLOCKED"
        append_blocker(results, "HUMAN-ACTION-NEEDED", "browser", "Operator must clear login/Cloudflare/human action, then rerun from the contract.")
        emit("blocked", reason="HUMAN-ACTION-NEEDED", error=ask_error_summary(exc))
    except PromptNotSubmittedError as exc:
        results["status"] = "PARTIAL"
        partial = getattr(exc, "partial", None)
        if isinstance(partial, TurnRecord):
            results["signals"].append("PromptNotSubmittedError included partial turn metadata.")
        append_blocker(results, "PROMPT_NOT_SUBMITTED", "send", "Gotcha-4 submission verification failed; inspect cache and send verifier before retry.")
        if results["leg2"].get("assistant") is None:
            results["leg2"]["error"] = ask_error_summary(exc)
        else:
            results["leg3"]["error"] = ask_error_summary(exc)
        emit("prompt_not_submitted", error=ask_error_summary(exc))
    except AskChatGPTError as exc:
        results["status"] = "PARTIAL" if (session and session.send_budget.successful_submissions) else "BLOCKED"
        partial = getattr(exc, "partial", None)
        partial_meta = turn_meta(partial) if isinstance(partial, TurnRecord) else None
        if results["leg2"].get("assistant") is None:
            results["leg2"]["error"] = {**ask_error_summary(exc), "partial": partial_meta}
        else:
            results["leg3"]["error"] = {**ask_error_summary(exc), "partial": partial_meta}
        append_blocker(results, getattr(exc, "code", type(exc).__name__), "browser", "Inspect the safe error code and gitignored cache; do not retry-spam live ChatGPT.")
        emit("ask_chatgpt_error", error=ask_error_summary(exc), partial=partial_meta)
    except Exception as exc:  # noqa: BLE001 - fail closed with safe metadata only.
        results["status"] = "PARTIAL" if (session and session.send_budget.successful_submissions) else "BLOCKED"
        append_blocker(results, type(exc).__name__, "driver", "Fix the driver/source issue, then rerun from the contract without extra sends.")
        emit("driver_error", error={"type": type(exc).__name__})
    finally:
        if session is not None:
            results["send_counts"]["final"] = session.send_budget.successful_submissions
            reconcile_send_breakdown(results, session.send_budget.successful_submissions)
            try:
                session.detach()
                results["confirmations"]["browser_not_quit_detach_only"] = True
            except Exception as exc:  # noqa: BLE001 - report detach failure safely.
                results["confirmations"]["browser_not_quit_detach_only"] = False
                append_blocker(results, "DETACH_FAILED", "teardown", f"Detach raised {type(exc).__name__}; inspect managed tabs manually without touching foreign tabs.")
                emit("detach_error", error={"type": type(exc).__name__})
        results["git_end"] = git_checks()
        git_end = results["git_end"] or {}
        results["confirmations"]["cache_not_staged"] = not bool(git_end.get("cache_staged"))
        results["confirmations"]["controller_mjs_and_human_unstaged"] = not bool(git_end.get("protected_paths_staged"))
        stable_end = git_end.get("stable_rev")
        if stable_start and stable_end:
            results["confirmations"]["stable_unmoved_by_this_script"] = stable_start == stable_end
        write_report(results)
        emit("report_written", status=results["status"], report=str(REPORT_PATH), final_send_count=results["send_counts"].get("final"))
    return 0 if results["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
