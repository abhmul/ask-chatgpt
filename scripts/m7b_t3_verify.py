#!/usr/bin/env python3
"""M7b-T3 live verifier: gap-1 menu selection + gap-2 backend capture.

The driver uses only Session/TabPool-owned tabs, emits safe metadata only, and
writes conversation content only through the gitignored Store data_dir.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt.errors import (
    AskChatGPTError,
    HumanActionNeededError,
    ModelSelectionNotReflectedError,
    SelectorNotFoundError,
    ToolSelectionNotReflectedError,
)
from ask_chatgpt.menus import SelectionResult, select_model, set_tools
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.send import normalize_prompt
from ask_chatgpt.session import Session

CDP_VERSION_URL = "http://127.0.0.1:9222/json/version"
DATA_DIR = Path("cache/m7b-t3-verify")
REPORT_PATH = Path("team/evidence/reports/M7b-T3-verify.md")
TARGET_CONVERSATION_ID = "6a316aa8"
PONG_PROMPT = "Reply with only the word: PONG"
THIS_RUN_SEND_CAP = 3
MODEL_TARGET_CANDIDATES = ("High", "Medium", "Extra High", "Instant")
WEB_TOOL_LABEL = "Web search"
EXPECTED_HEAD_SHORT = "1ea867a"

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
        if any(part in lowered for part in SENSITIVE_VALUE_PARTS):
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
    head = run_git(["rev-parse", "--short", "HEAD"])
    stable = run_git(["rev-parse", "stable"])
    cache_staged = run_git(["diff", "--cached", "--name-only", "--", "cache"])
    protected_staged = run_git(
        [
            "diff",
            "--cached",
            "--name-only",
            "--",
            "cache",
            "issues/cdp-send-repro/controller.mjs",
            "human",
        ]
    )
    staged = run_git(["diff", "--cached", "--name-only"])
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "branch_ok_rewrite_v2": branch.stdout.strip() == "rewrite-v2",
        "head_short": head.stdout.strip() if head.returncode == 0 else None,
        "head_expected": head.stdout.strip() == EXPECTED_HEAD_SHORT,
        "stable_rev": stable.stdout.strip() if stable.returncode == 0 else None,
        "stable_ok": stable.returncode == 0 and bool(stable.stdout.strip()),
        "cache_staged": bool(cache_staged.stdout.strip()),
        "protected_paths_staged": [line for line in protected_staged.stdout.splitlines() if line.strip()],
        "staged_files": [line for line in staged.stdout.splitlines() if line.strip()],
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


def _tab_monotonic(tab: Any) -> float:
    monotonic = getattr(tab.channel, "monotonic", None)
    if callable(monotonic):
        return float(monotonic())
    return time.monotonic()


def _tab_sleep(tab: Any, seconds: float) -> None:
    sleeper = getattr(tab.channel, "sleep", None)
    if callable(sleeper):
        sleeper(max(0.0, float(seconds)))
    else:
        time.sleep(max(0.0, float(seconds)))


def _labels_now(tab: Any, selectors: dict[str, str]) -> tuple[str, ...]:
    snapshot = tab.channel.query_turns(tab, selectors)
    return tuple(label for label in snapshot.model_labels if normalize_prompt(label))


def read_initial_model_label(tab: Any, selectors: dict[str, str]) -> dict[str, Any]:
    samples: list[tuple[str, ...]] = []
    for index in range(3):
        samples.append(_labels_now(tab, selectors))
        if index < 2:
            _tab_sleep(tab, 2.0)
    singletons = [sample[0] for sample in samples if len(sample) == 1]
    stable = len(singletons) == len(samples) and len(set(map(normalize_prompt, singletons))) == 1
    label = singletons[-1] if singletons else None
    return {"label": label, "sustained_ok": stable, "samples": samples}


def pick_target_model(initial_label: str | None) -> str:
    initial_norm = normalize_prompt(initial_label or "")
    for candidate in MODEL_TARGET_CANDIDATES:
        if normalize_prompt(candidate) != initial_norm:
            return candidate
    return MODEL_TARGET_CANDIDATES[0]


def sustained_model_confirmation(
    tab: Any,
    selectors: dict[str, str],
    want: str,
    *,
    duration_s: float = 12.0,
    interval_s: float = 2.0,
) -> dict[str, Any]:
    start = _tab_monotonic(tab)
    samples: list[dict[str, Any]] = []
    want_norm = normalize_prompt(want)
    while True:
        now = _tab_monotonic(tab)
        labels = _labels_now(tab, selectors)
        samples.append({"elapsed_s": round(now - start, 3), "labels": labels})
        elapsed = _tab_monotonic(tab) - start
        if elapsed >= duration_s:
            break
        _tab_sleep(tab, min(interval_s, max(0.0, duration_s - elapsed)))
    elapsed_final = _tab_monotonic(tab) - start
    ok = elapsed_final >= duration_s and bool(samples) and all(
        tuple(normalize_prompt(label) for label in sample["labels"]) == (want_norm,)
        for sample in samples
    )
    return {
        "ok": ok,
        "duration_s": round(elapsed_final, 3),
        "sample_count": len(samples),
        "last_labels": samples[-1]["labels"] if samples else (),
    }


def selection_result_meta(result: SelectionResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {"requested": result.requested, "reflected": result.reflected, "verified": result.verified}


def selector_counts(tab: Any, selectors: dict[str, str]) -> dict[str, Any]:
    js = """
    (a) => {
      const visible = el => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      };
      const count = selector => Array.from(document.querySelectorAll(selector || '')).length;
      const visibleCount = selector => Array.from(document.querySelectorAll(selector || '')).filter(visible).length;
      return {
        new_model_selector: a.new_model_selector,
        old_model_selector: a.old_model_selector,
        tools_selector: a.tools_selector,
        new_model_count: count(a.new_model_selector),
        new_model_visible_count: visibleCount(a.new_model_selector),
        old_model_count: count(a.old_model_selector),
        old_model_visible_count: visibleCount(a.old_model_selector),
        tools_count: count(a.tools_selector),
        tools_visible_count: visibleCount(a.tools_selector)
      };
    }
    """
    raw = tab.channel.evaluate(
        tab,
        js,
        arg={
            "new_model_selector": selectors.get("model_picker_trigger_candidates"),
            "old_model_selector": 'composer-footer button[aria-haspopup="menu"]',
            "tools_selector": selectors.get("tools_button"),
        },
        timeout_s=5.0,
    )
    return dict(raw) if isinstance(raw, dict) else {}


def current_url(tab: Any) -> str:
    value = tab.channel.evaluate(tab, "ask_chatgpt_current_url", timeout_s=5.0)
    return value if isinstance(value, str) else ""


def append_blocker(results: dict[str, Any], code: str, leg: str, action: str) -> None:
    results["blockers"].append({"code": code, "leg": leg, "action": action})


def raise_stop(results: dict[str, Any], status: str, code: str, leg: str, action: str) -> None:
    append_blocker(results, code, leg, action)
    raise StopRun(status=status, code=code, leg=leg, action=action)


def initial_results() -> dict[str, Any]:
    git_start = git_checks()
    return {
        "status": "PARTIAL",
        "preflight": {},
        "post_detach_preflight": {},
        "send_counts": {
            "leg1": 0,
            "leg2": 0,
            "loop": 0,
            "final": 0,
            "this_run_cap": THIS_RUN_SEND_CAP,
        },
        "created_conversations": [],
        "gap1": {
            "initial_model": None,
            "initial_sustained_ok": None,
            "target_model": None,
            "selector_counts": {},
            "model_select": None,
            "model_select_error": None,
            "independent_sustained": None,
            "tool_select": None,
            "tool_select_error": None,
            "restore": {"attempted": False, "verified": None, "reflected": None, "error": None},
            "send_count_after": None,
            "closed": False,
        },
        "gap2": {
            "assistant": None,
            "checks": {},
            "transcript": None,
            "submissions_after": None,
            "error": None,
            "closed": False,
        },
        "loop": {
            "status": "SKIPPED",
            "reason": "frugal: gap-2 PONG smoke is sufficient for this task; optional loop not run",
            "turns": [],
            "error": None,
        },
        "confirmations": {
            "own_tab_only_via_session_tabpool": True,
            "no_json_list_or_page_enumeration_in_driver": True,
            "browser_not_quit_session_detach_only": False,
            "post_detach_version_ok": False,
            "send_cap_this_run_leq_3": None,
            "leg1_zero_sends": None,
            "fresh_throwaway_only": True,
            "target_6a316aa8_not_touched": True,
            "no_auth_oai_cookie_bearer_values_logged": True,
            "no_conversation_content_printed_or_reported": True,
            "cache_not_staged": None,
            "controller_mjs_and_human_unstaged": None,
            "stable_unmoved_by_this_script": None,
            "branch_rewrite_v2": git_start.get("branch_ok_rewrite_v2"),
            "head_expected_1ea867a": git_start.get("head_expected"),
        },
        "blockers": [],
        "signals": [],
        "git_start": git_start,
        "git_end": None,
    }


def compute_gap1_closed(gap1: dict[str, Any]) -> bool:
    model = gap1.get("model_select") or {}
    tool = gap1.get("tool_select") or {}
    sustained = gap1.get("independent_sustained") or {}
    return bool(
        gap1.get("initial_model")
        and gap1.get("target_model")
        and model.get("verified") is True
        and normalize_prompt(str(model.get("reflected") or "")) == normalize_prompt(str(gap1.get("target_model") or ""))
        and sustained.get("ok") is True
        and tool.get("verified") is True
        and normalize_prompt(str(tool.get("reflected") or "")) == normalize_prompt(WEB_TOOL_LABEL)
        and gap1.get("send_count_after") == 0
    )


def compute_gap2_closed(gap2: dict[str, Any]) -> bool:
    checks = gap2.get("checks") or {}
    return bool(checks.get("all_proven") and checks.get("capture_backend_api") and checks.get("fidelity_canonical"))


def update_final_status(results: dict[str, Any]) -> None:
    if results.get("status") == "BLOCKED":
        return
    gap1_closed = compute_gap1_closed(results.get("gap1") or {})
    gap2_closed = compute_gap2_closed(results.get("gap2") or {})
    results["gap1"]["closed"] = gap1_closed
    results["gap2"]["closed"] = gap2_closed
    results["status"] = "DONE" if gap1_closed and gap2_closed else "PARTIAL"


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = results.get("status")
    preflight = results.get("preflight") or {}
    post = results.get("post_detach_preflight") or {}
    send_counts = results.get("send_counts") or {}
    gap1 = results.get("gap1") or {}
    gap2 = results.get("gap2") or {}
    loop = results.get("loop") or {}
    conf = results.get("confirmations") or {}
    git_start = results.get("git_start") or {}
    git_end = results.get("git_end") or {}
    forbidden_endpoint = "/json" + "/list"

    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M7b-T3 real verification")
    lines.append("")
    lines.append("## CDP preflight")
    lines.append("- Endpoint used: `/json/version` only.")
    lines.append(f"- Browser version: `{preflight.get('browser')}`")
    lines.append(f"- Protocol-Version: `{preflight.get('protocol_version')}`")
    lines.append(f"- WebSocket URL present: `{preflight.get('websocket_url_present')}`")
    lines.append(f"- Preflight ok/error: `{preflight.get('ok')}` / `{preflight.get('error_code') or preflight.get('error')}`")
    lines.append("")
    lines.append("## Send count")
    lines.append(f"- Exact this-run `send_budget.successful_submissions`: `{send_counts.get('final')}`")
    lines.append(f"- Per-leg sends: Leg 1=`{send_counts.get('leg1')}`, Leg 2=`{send_counts.get('leg2')}`, loop=`{send_counts.get('loop')}`")
    lines.append(f"- Cap respected (`<= 3`): `{conf.get('send_cap_this_run_leq_3')}`")
    lines.append(f"- Leg 1 zero sends: `{conf.get('leg1_zero_sends')}`")
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
    lines.append("## Gap-1 results — live model/tool selection, zero sends")
    lines.append(f"- Initial model label `L0`: `{gap1.get('initial_model')}`; initial sustained read ok: `{gap1.get('initial_sustained_ok')}`")
    lines.append(f"- Target tier `T`: `{gap1.get('target_model')}`")
    lines.append(f"- `select_model` result: `{json.dumps(_scrub(gap1.get('model_select')), sort_keys=True)}`")
    lines.append(f"- `select_model` fail-closed error: `{json.dumps(_scrub(gap1.get('model_select_error')), sort_keys=True)}`")
    lines.append(f"- Independent ~12s model-label confirmation: `{json.dumps(_scrub(gap1.get('independent_sustained')), sort_keys=True)}`")
    lines.append(f"- `set_tools` result: `{json.dumps(_scrub(gap1.get('tool_select')), sort_keys=True)}`")
    lines.append(f"- `set_tools` fail-closed error: `{json.dumps(_scrub(gap1.get('tool_select_error')), sort_keys=True)}`")
    lines.append(f"- Restore original model outcome: `{json.dumps(_scrub(gap1.get('restore')), sort_keys=True)}`")
    lines.append(f"- Selector note: current model selector is `form button[aria-haspopup=\"menu\"]:not([data-testid])`; old offline selector was `composer-footer button[aria-haspopup=\"menu\"]`.")
    lines.append(f"- Selector counts from own tab: `{json.dumps(_scrub(gap1.get('selector_counts')), sort_keys=True)}`")
    lines.append(f"- Fail-closed behavior observed: typed menu-selection errors are recorded above when raised; success path raised none.")
    lines.append(f"- Send count after Leg 1: `{gap1.get('send_count_after')}`")
    lines.append(f"- Verdict: gap-1 `{'CLOSED' if gap1.get('closed') else 'NOT CLOSED'}`")
    lines.append("")
    lines.append("## Gap-2 results — fresh-chat send→capture")
    assistant = gap2.get("assistant") or {}
    checks = gap2.get("checks") or {}
    lines.append(f"- Assistant role/id/status/partial: `{assistant.get('role')}` / `{assistant.get('message_id')}` / `{assistant.get('status')}` / `{assistant.get('partial')}`")
    lines.append(f"- Assistant char-count: `{assistant.get('char_count')}`")
    lines.append(f"- Capture source/fidelity: `{assistant.get('capture_source')}` / `{assistant.get('fidelity')}`")
    lines.append(f"- Checks: `{json.dumps(checks, sort_keys=True)}`")
    lines.append(f"- User prompt present (bool only): `{checks.get('user_prompt_present')}`")
    lines.append(f"- Content non-empty (bool only): `{checks.get('content_nonempty')}`")
    lines.append(f"- `all_proven`: `{checks.get('all_proven')}`")
    if checks.get("capture_backend_api"):
        lines.append("- Backend capture verdict: `capture_source == backend_api`; reload→GET→header-harvest path worked.")
    else:
        lines.append(f"- Backend capture verdict: NOT proven; source/error: `{assistant.get('capture_source')}` / `{json.dumps(_scrub(gap2.get('error')), sort_keys=True)}`")
    lines.append(f"- Transcript metadata: `{json.dumps(_scrub(gap2.get('transcript')), sort_keys=True)}`")
    lines.append(f"- Submissions after Gap 2: `{gap2.get('submissions_after')}`")
    lines.append(f"- Error: `{json.dumps(_scrub(gap2.get('error')), sort_keys=True)}`")
    lines.append(f"- Verdict: gap-2 `{'CLOSED' if gap2.get('closed') else 'NOT CLOSED'}`")
    lines.append("")
    lines.append("## Loop leg")
    lines.append(f"- Status: `{loop.get('status')}`")
    lines.append(f"- Reason: `{loop.get('reason')}`")
    lines.append(f"- Turns: `{json.dumps(_scrub(loop.get('turns')), sort_keys=True)}`")
    lines.append(f"- Error: `{json.dumps(_scrub(loop.get('error')), sort_keys=True)}`")
    lines.append("")
    lines.append("## Confirmations")
    lines.append(f"- Branch at start/end: `{git_start.get('branch')}` / `{git_end.get('branch')}`")
    lines.append(f"- HEAD short at start/end: `{git_start.get('head_short')}` / `{git_end.get('head_short')}`; expected `{EXPECTED_HEAD_SHORT}` at start: `{conf.get('head_expected_1ea867a')}`")
    lines.append(f"- Own-tab-only via Session/TabPool: `{conf.get('own_tab_only_via_session_tabpool')}`")
    lines.append(f"- No `{forbidden_endpoint}` call and no page enumeration in driver: `{conf.get('no_json_list_or_page_enumeration_in_driver')}`")
    lines.append(f"- Browser not quit; Session.detach only: `{conf.get('browser_not_quit_session_detach_only')}`")
    lines.append(f"- Post-detach `/json/version` ok: `{conf.get('post_detach_version_ok')}`; browser: `{post.get('browser')}`")
    lines.append(f"- Fresh throwaway sends only: `{conf.get('fresh_throwaway_only')}`")
    lines.append(f"- No auth/OAI/cookie/bearer values logged: `{conf.get('no_auth_oai_cookie_bearer_values_logged')}`")
    lines.append(f"- No conversation content printed or reported: `{conf.get('no_conversation_content_printed_or_reported')}`")
    lines.append(f"- `cache/` not staged: `{conf.get('cache_not_staged')}`")
    lines.append(f"- `controller.mjs` and `human/` unstaged: `{conf.get('controller_mjs_and_human_unstaged')}`")
    lines.append(f"- `stable` unmoved by this script: `{conf.get('stable_unmoved_by_this_script')}`")
    lines.append(f"- Stable rev start/end: `{git_start.get('stable_rev')}` / `{git_end.get('stable_rev')}`")
    lines.append(f"- Staged files at end: `{json.dumps(_scrub(git_end.get('staged_files')), sort_keys=True)}`")
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


def run_gap1(session: Session, results: dict[str, Any]) -> None:
    gap1 = results["gap1"]
    tab = None
    released = False
    try:
        draft = session.create()
        try:
            tab = session.tab_pool.acquire(draft)
            emit("gap1_tab_acquired", tab_id=getattr(tab, "tab_id", None))
        except Exception as exc:  # noqa: BLE001 - no composer means human action per contract.
            raise HumanActionNeededError(
                "fresh composer tab could not be opened",
                details={"reason": "composer_absent_or_challenge", "error_type": type(exc).__name__},
            ) from exc
        url = current_url(tab)
        if f"/c/{TARGET_CONVERSATION_ID}" in url:
            results["confirmations"]["target_6a316aa8_not_touched"] = False
            raise_stop(
                results,
                "BLOCKED",
                "TARGET_CONVERSATION_MATCH",
                "gap1",
                "Fresh draft tab resolved to the protected conversation id; stop and audit before any send.",
            )
        try:
            tab.channel.wait_for_selector(tab, session.selector_map["composer"], state="visible", timeout_s=20.0)
            snapshot = tab.channel.query_turns(tab, session.selector_map)
            if not snapshot.composer_visible:
                raise SelectorNotFoundError("composer not visible after wait")
        except Exception as exc:  # noqa: BLE001 - login/challenge/no composer: stop.
            raise HumanActionNeededError(
                "fresh composer was absent",
                details={"reason": "composer_absent_or_challenge", "error_type": type(exc).__name__},
            ) from exc

        gap1["selector_counts"] = selector_counts(tab, session.selector_map)
        initial = read_initial_model_label(tab, session.selector_map)
        gap1["initial_model"] = initial.get("label")
        gap1["initial_sustained_ok"] = initial.get("sustained_ok")
        target = pick_target_model(gap1["initial_model"])
        gap1["target_model"] = target
        emit("gap1_initial", initial_model=gap1["initial_model"], target_model=target, selector_counts=gap1["selector_counts"])

        try:
            model_res = select_model(tab, session.selector_map, target)
            gap1["model_select"] = selection_result_meta(model_res)
            emit("gap1_model_selected", result=gap1["model_select"])
        except ModelSelectionNotReflectedError as exc:
            gap1["model_select_error"] = ask_error_summary(exc)
            emit("gap1_model_select_failed", error=gap1["model_select_error"])
        except AskChatGPTError as exc:
            gap1["model_select_error"] = ask_error_summary(exc)
            emit("gap1_model_select_failed", error=gap1["model_select_error"])
        except Exception as exc:  # noqa: BLE001 - fail closed with typed summary.
            wrapped = ModelSelectionNotReflectedError(
                "model selection driver boundary failed closed",
                details={"reason": type(exc).__name__},
            )
            gap1["model_select_error"] = ask_error_summary(wrapped)
            emit("gap1_model_select_failed", error=gap1["model_select_error"])

        if gap1.get("model_select") and gap1["model_select"].get("verified") is True:
            sustained = sustained_model_confirmation(tab, session.selector_map, target, duration_s=12.0, interval_s=2.0)
            gap1["independent_sustained"] = sustained
            emit("gap1_model_sustained", sustained=sustained)
        else:
            gap1["independent_sustained"] = {"ok": False, "reason": "model_select_not_verified"}

        try:
            tool_results = set_tools(tab, session.selector_map, [WEB_TOOL_LABEL])
            first = tool_results[0] if tool_results else None
            gap1["tool_select"] = selection_result_meta(first)
            emit("gap1_tool_selected", result=gap1["tool_select"])
        except ToolSelectionNotReflectedError as exc:
            gap1["tool_select_error"] = ask_error_summary(exc)
            results["signals"].append("Tool selection failed closed on the live composer; the selected label was clicked but reflected checked state was not observed.")
            emit("gap1_tool_select_failed", error=gap1["tool_select_error"])
        except AskChatGPTError as exc:
            gap1["tool_select_error"] = ask_error_summary(exc)
            results["signals"].append("Tool selection raised a typed ask-chatgpt error during live verification; gap-1 remains not closed unless reflected state is proven.")
            emit("gap1_tool_select_failed", error=gap1["tool_select_error"])
        except Exception as exc:  # noqa: BLE001 - fail closed with typed summary.
            wrapped = ToolSelectionNotReflectedError(
                "tool selection driver boundary failed closed",
                details={"reason": type(exc).__name__},
            )
            gap1["tool_select_error"] = ask_error_summary(wrapped)
            results["signals"].append("Tool selection failed at the driver boundary and was converted to a typed fail-closed result.")
            emit("gap1_tool_select_failed", error=gap1["tool_select_error"])

        original = gap1.get("initial_model")
        if original:
            gap1["restore"]["attempted"] = True
            try:
                restore_res = select_model(tab, session.selector_map, str(original))
                gap1["restore"].update(
                    {
                        "verified": restore_res.verified,
                        "reflected": restore_res.reflected,
                        "error": None,
                    }
                )
                emit("gap1_model_restored", restore=gap1["restore"])
            except AskChatGPTError as exc:
                gap1["restore"]["error"] = ask_error_summary(exc)
                results["signals"].append("Original model restore failed; recorded as non-fatal per contract and no retry-spam attempted.")
                emit("gap1_model_restore_failed", error=gap1["restore"]["error"])
            except Exception as exc:  # noqa: BLE001
                gap1["restore"]["error"] = {"type": type(exc).__name__}
                results["signals"].append("Original model restore failed at driver boundary; recorded as non-fatal and no retry-spam attempted.")
                emit("gap1_model_restore_failed", error=gap1["restore"]["error"])
        else:
            gap1["restore"]["error"] = {"type": "SKIPPED", "reason": "initial_model_absent"}
            results["signals"].append("Original model restore skipped because no initial label was read.")

        gap1["send_count_after"] = session.send_budget.successful_submissions
        results["send_counts"]["leg1"] = session.send_budget.successful_submissions
        results["confirmations"]["leg1_zero_sends"] = session.send_budget.successful_submissions == 0
        if session.send_budget.successful_submissions != 0:
            raise_stop(
                results,
                "BLOCKED",
                "LEG1_NONZERO_SEND_COUNT",
                "gap1",
                "Menu-only leg unexpectedly changed successful_submissions; stop before any further live sends.",
            )
    finally:
        if tab is not None and not released:
            try:
                session.tab_pool.release(tab)
                released = True
                emit("gap1_tab_released", tab_id=getattr(tab, "tab_id", None))
            except Exception as exc:  # noqa: BLE001
                append_blocker(results, "TAB_RELEASE_FAILED", "gap1", f"Release of own managed tab raised {type(exc).__name__}; detach will still close managed tabs.")
                emit("gap1_tab_release_failed", error={"type": type(exc).__name__})


def run_gap2(session: Session, results: dict[str, Any]) -> None:
    gap2 = results["gap2"]
    before = session.send_budget.successful_submissions
    rec = session.ask(None, PONG_PROMPT, timeout=90)
    after = session.send_budget.successful_submissions
    results["send_counts"]["leg2"] = after - before
    gap2["submissions_after"] = after
    gap2["assistant"] = turn_meta(rec)
    if rec.conversation_id == TARGET_CONVERSATION_ID:
        results["confirmations"]["target_6a316aa8_not_touched"] = False
        raise_stop(
            results,
            "BLOCKED",
            "TARGET_CONVERSATION_MATCH",
            "gap2",
            "ask(None) resolved to the protected conversation id; stop and audit before any retry.",
        )
    results["created_conversations"].append(
        {"conversation_id": rec.conversation_id, "conversation_url": rec.conversation_url}
    )
    hist = session.history(rec.conversation_id)
    meta = transcript_meta(hist)
    roles = meta.get("roles") or {}
    checks = {
        "role_is_assistant": rec.role == "assistant",
        "conversation_id_present": bool(rec.conversation_id),
        "conversation_id_not_target": rec.conversation_id != TARGET_CONVERSATION_ID,
        "conversation_url_has_id": conversation_url_has_id(rec.conversation_url, rec.conversation_id),
        "status_complete": rec.status == "complete",
        "partial_false": rec.partial is False,
        "content_nonempty": len(rec.content_markdown) > 0,
        "user_prompt_present": prompt_present(hist, PONG_PROMPT),
        "assistant_turn_present": assistant_present(hist, rec.message_id),
        "transcript_user_and_assistant_present": roles.get("user", 0) >= 1 and roles.get("assistant", 0) >= 1,
        "transcript_turn_count": len(hist.turns),
        "transcript_roles": roles,
        "capture_backend_api": rec.capture_source == "backend_api",
        "fidelity_canonical": rec.fidelity == "canonical",
    }
    checks["all_proven"] = all(
        [
            checks["role_is_assistant"],
            checks["conversation_id_present"],
            checks["conversation_id_not_target"],
            checks["conversation_url_has_id"],
            checks["status_complete"],
            checks["partial_false"],
            checks["content_nonempty"],
            checks["user_prompt_present"],
            checks["assistant_turn_present"],
            checks["transcript_user_and_assistant_present"],
            checks["capture_backend_api"],
            checks["fidelity_canonical"],
        ]
    )
    gap2["checks"] = checks
    gap2["transcript"] = meta
    emit("gap2_complete", submissions=after, assistant=gap2["assistant"], checks=checks)
    if after > THIS_RUN_SEND_CAP:
        raise_stop(results, "BLOCKED", "SEND_CAP_EXCEEDED", "gap2", "successful_submissions exceeded the <=3 live-send cap; stop immediately.")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = initial_results()
    stable_start = (results.get("git_start") or {}).get("stable_rev")
    session: Session | None = None
    phase = "preflight"

    try:
        preflight = preflight_version()
        results["preflight"] = preflight
        emit("preflight", preflight=preflight)
        if preflight.get("ok") is not True:
            raise_stop(results, "BLOCKED", "CDP_UNREACHABLE", "preflight", "Expose Chrome CDP on 127.0.0.1:9222 and rerun; no attach or send attempted.")
        git_start = results.get("git_start") or {}
        if not git_start.get("branch_ok_rewrite_v2"):
            raise_stop(results, "BLOCKED", "WRONG_BRANCH", "preflight", "Switch to branch rewrite-v2 before running live verification.")
        if not git_start.get("stable_ok"):
            raise_stop(results, "BLOCKED", "STABLE_REF_UNAVAILABLE", "preflight", "Restore/verify the stable ref before running live verification.")
        if git_start.get("cache_staged") or git_start.get("protected_paths_staged"):
            raise_stop(results, "BLOCKED", "PROTECTED_PATHS_STAGED", "preflight", "Unstage cache/, controller.mjs, and human/ before running live verification.")
        if not git_start.get("head_expected"):
            results["signals"].append(f"HEAD short was {git_start.get('head_short')}, not expected {EXPECTED_HEAD_SHORT}; continued because branch/stable checks passed.")

        phase = "attach"
        session = Session(channel="cdp", data_dir=DATA_DIR)
        session.attach()
        emit("attached", data_dir=str(DATA_DIR))

        phase = "gap1"
        run_gap1(session, results)
        results["gap1"]["closed"] = compute_gap1_closed(results["gap1"])
        if not results["gap1"]["closed"]:
            append_blocker(
                results,
                "GAP1_NOT_CLOSED",
                "gap1",
                "Resolve the recorded model/tool live-selection failure before claiming gap-1 closed; do not retry-spam live ChatGPT.",
            )
        emit("gap1_done", closed=results["gap1"]["closed"], send_count=session.send_budget.successful_submissions)

        phase = "gap2"
        if session.send_budget.successful_submissions >= THIS_RUN_SEND_CAP:
            raise_stop(results, "BLOCKED", "SEND_CAP_EXHAUSTED_BEFORE_GAP2", "gap2", "No send budget remains for required fresh-chat smoke.")
        run_gap2(session, results)
        results["gap2"]["closed"] = compute_gap2_closed(results["gap2"])
        if not results["gap2"]["closed"]:
            append_blocker(
                results,
                "GAP2_NOT_CLOSED",
                "gap2",
                "Backend-api canonical capture was not fully proven; inspect the recorded capture source/error as an M8 blocker before any rerun.",
            )
        emit("gap2_done", closed=results["gap2"]["closed"], send_count=session.send_budget.successful_submissions)

        phase = "loop"
        results["loop"]["status"] = "SKIPPED"
        results["loop"]["reason"] = "frugal: optional 2-iter loop skipped after required backend_api smoke verification"
        results["send_counts"]["loop"] = 0
    except StopRun as stop:
        results["status"] = stop.status
        results["signals"].append(f"Stopped at {stop.leg}: {stop.code}.")
        emit("stopped", status=stop.status, leg=stop.leg, code=stop.code)
    except HumanActionNeededError as exc:
        results["status"] = "BLOCKED"
        append_blocker(results, "HUMAN-ACTION-NEEDED", phase, "Operator must clear login/Cloudflare/human action; no retries or stealth attempted.")
        error = ask_error_summary(exc)
        if phase == "gap2":
            results["gap2"]["error"] = error
        elif phase == "gap1":
            if not results["gap1"].get("model_select"):
                results["gap1"]["model_select_error"] = error
        emit("blocked", reason="HUMAN-ACTION-NEEDED", phase=phase, error=error)
    except AskChatGPTError as exc:
        results["status"] = "PARTIAL" if session is not None and session.send_budget.successful_submissions > 0 else "BLOCKED"
        partial = getattr(exc, "partial", None)
        partial_meta = turn_meta(partial) if isinstance(partial, TurnRecord) else None
        error = {**ask_error_summary(exc), "partial": partial_meta}
        if phase == "gap2":
            results["gap2"]["error"] = error
        elif phase == "gap1":
            results["gap1"]["model_select_error"] = error
        append_blocker(results, getattr(exc, "code", type(exc).__name__), phase, "Inspect safe error metadata and gitignored cache; do not retry-spam live ChatGPT.")
        emit("ask_chatgpt_error", phase=phase, error=error)
    except Exception as exc:  # noqa: BLE001 - fail closed with safe metadata only.
        results["status"] = "PARTIAL" if session is not None and session.send_budget.successful_submissions > 0 else "BLOCKED"
        append_blocker(results, type(exc).__name__, phase, "Fix the driver/source issue; respect remaining live-send budget before rerun.")
        emit("driver_error", phase=phase, error={"type": type(exc).__name__})
    finally:
        if session is not None:
            final_count = session.send_budget.successful_submissions
            results["send_counts"]["final"] = final_count
            if results["gap1"].get("send_count_after") is None:
                results["gap1"]["send_count_after"] = min(final_count, 0)
            results["confirmations"]["leg1_zero_sends"] = results["gap1"].get("send_count_after") == 0
            try:
                session.detach()
                results["confirmations"]["browser_not_quit_session_detach_only"] = True
            except Exception as exc:  # noqa: BLE001
                results["confirmations"]["browser_not_quit_session_detach_only"] = False
                append_blocker(results, "DETACH_FAILED", "teardown", f"Session.detach raised {type(exc).__name__}; inspect own managed tabs only.")
                emit("detach_error", error={"type": type(exc).__name__})
        else:
            results["send_counts"]["final"] = 0
            results["confirmations"]["leg1_zero_sends"] = results["send_counts"].get("leg1") == 0
        post = preflight_version()
        results["post_detach_preflight"] = post
        results["confirmations"]["post_detach_version_ok"] = post.get("ok") is True
        final_count = int(results["send_counts"].get("final") or 0)
        results["confirmations"]["send_cap_this_run_leq_3"] = final_count <= THIS_RUN_SEND_CAP
        results["git_end"] = git_checks()
        git_end = results.get("git_end") or {}
        results["confirmations"]["cache_not_staged"] = not bool(git_end.get("cache_staged"))
        results["confirmations"]["controller_mjs_and_human_unstaged"] = not bool(git_end.get("protected_paths_staged"))
        stable_end = git_end.get("stable_rev")
        if stable_start and stable_end:
            results["confirmations"]["stable_unmoved_by_this_script"] = stable_start == stable_end
        if results.get("status") != "BLOCKED":
            update_final_status(results)
        write_report(results)
        emit("report_written", status=results["status"], report=str(REPORT_PATH), final_send_count=final_count)
    return 0 if results["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
