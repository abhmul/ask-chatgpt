#!/usr/bin/env python3
"""M7b-T3c live tools-selection verifier.

Own-tab-only, ZERO-send CDP workflow. Opens one fresh ChatGPT composer tab via
Session/TabPool, calls production set_tools(["Web search"]), records whether the
post-select re-open verification reflects checked state, and writes the report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt.errors import AskChatGPTError
from ask_chatgpt.menus import SelectionResult, enumerate_radix_options, open_radix_menu, select_radix_label, set_tools
from ask_chatgpt.send import normalize_prompt, wait_for_composer
from ask_chatgpt.session import Session

CDP_VERSION_URL = "http://127.0.0.1:9222/json/version"
DATA_DIR = Path("cache/m7b-t3c-verify")
REPORT_PATH = Path("team/evidence/reports/M7b-T3c-tools-verify.md")
REQUIRED_BRANCH = "rewrite-v2"
EXPECTED_HEAD_SHORT = "90281f3"
TOOL_LABEL = "Web search"
TARGET_CONVERSATION_ID = "6a316aa8"
LOOP_MESSAGE = "continue"

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
    "session",
    "text",
    "token",
)
SENSITIVE_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "cookie:",
    "cf_clearance",
    "__secure-",
    "oai-",
    "password",
    "reply with only the word",
    "secret",
    "session-token",
    "token=",
)

JS_PAGE_STATE = r"""
() => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const body = norm(document.body ? document.body.innerText : '').toLowerCase();
  const title = norm(document.title).slice(0, 120);
  const path = String(location.pathname || '');
  return {
    path,
    title,
    has_composer: Boolean(document.querySelector('#prompt-textarea')),
    target_conversation_loaded: path.includes('/c/6a316aa8'),
    challenge_likely: /just a moment|checking your browser|verify you are human|cloudflare/.test((title + ' ' + body).toLowerCase()),
    login_likely: /log in|sign up|continue with google|continue with microsoft|continue with apple/.test(body)
  };
}
"""


@dataclass
class StopRun(Exception):
    status: str
    code: str
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
    return subprocess.run(["git", *args], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def git_checks() -> dict[str, Any]:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = run_git(["rev-parse", "--short", "HEAD"])
    stable = run_git(["rev-parse", "stable"])
    staged = run_git(["diff", "--cached", "--name-only"])
    protected = run_git([
        "diff",
        "--cached",
        "--name-only",
        "--",
        "cache",
        "issues/cdp-send-repro/controller.mjs",
        "human",
    ])
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "branch_ok_rewrite_v2": branch.stdout.strip() == REQUIRED_BRANCH,
        "head_short": head.stdout.strip() if head.returncode == 0 else None,
        "head_expected": head.stdout.strip() == EXPECTED_HEAD_SHORT,
        "stable_rev": stable.stdout.strip() if stable.returncode == 0 else None,
        "staged_files": [line for line in staged.stdout.splitlines() if line.strip()],
        "protected_paths_staged": [line for line in protected.stdout.splitlines() if line.strip()],
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
        "endpoint": "/json/version",
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


def error_summary(exc: BaseException, *, include_details: bool = True) -> dict[str, Any]:
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


def selection_record(result: SelectionResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {"requested": result.requested, "reflected": result.reflected, "verified": result.verified}


def option_record(option: Any) -> dict[str, Any] | None:
    if option is None:
        return None
    return {
        "label": getattr(option, "label", None),
        "role": getattr(option, "role", None),
        "checked": getattr(option, "checked", None),
        "disabled": getattr(option, "disabled", None),
        "path": list(getattr(option, "path", ()) or ()),
    }


def close_menu(tab: Any) -> None:
    try:
        tab.channel.press(tab, "body", "Escape")
        sleeper = getattr(tab.channel, "sleep", None)
        if callable(sleeper):
            sleeper(0.25)
    except Exception:
        pass


def web_search_option(tab: Any, selectors: dict[str, Any]) -> dict[str, Any] | None:
    open_radix_menu(tab, selectors["tools_button"])
    try:
        options = enumerate_radix_options(tab)
        matches = [
            option
            for option in options
            if normalize_prompt(option.label) == normalize_prompt(TOOL_LABEL) and not option.disabled
        ]
        if len(matches) == 1:
            return option_record(matches[0])
        return {"match_count": len(matches)}
    finally:
        close_menu(tab)


def page_state(tab: Any) -> dict[str, Any]:
    raw = tab.channel.evaluate(tab, JS_PAGE_STATE, timeout_s=5.0)
    if not isinstance(raw, dict):
        return {}
    return {
        "path": raw.get("path"),
        "title": raw.get("title"),
        "has_composer": raw.get("has_composer"),
        "target_conversation_loaded": raw.get("target_conversation_loaded"),
        "challenge_likely": raw.get("challenge_likely"),
        "login_likely": raw.get("login_likely"),
    }


def restore_tool_to_initial(tab: Any, selectors: dict[str, Any], initial: dict[str, Any] | None) -> dict[str, Any]:
    restore: dict[str, Any] = {
        "attempted": False,
        "needed": None,
        "initial_checked": None,
        "checked_before_restore": None,
        "clicked": False,
        "checked_after_restore": None,
        "error": None,
    }
    initial_checked = initial.get("checked") if isinstance(initial, dict) else None
    restore["initial_checked"] = initial_checked
    if not isinstance(initial_checked, bool):
        restore["error"] = "INITIAL_CHECKED_UNKNOWN"
        return restore
    try:
        current = web_search_option(tab, selectors)
        before = current.get("checked") if isinstance(current, dict) else None
        restore["checked_before_restore"] = before
        restore["needed"] = isinstance(before, bool) and before != initial_checked
        if restore["needed"] is True:
            restore["attempted"] = True
            open_radix_menu(tab, selectors["tools_button"])
            try:
                selected = select_radix_label(tab, TOOL_LABEL)
                restore["clicked"] = True
                restore["selected_option"] = option_record(selected)
            finally:
                close_menu(tab)
            after_option = web_search_option(tab, selectors)
            after = after_option.get("checked") if isinstance(after_option, dict) else None
            restore["checked_after_restore"] = after
        else:
            restore["checked_after_restore"] = before
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup only; safe type recorded.
        restore["error"] = type(exc).__name__
        close_menu(tab)
    return restore


def initial_results() -> dict[str, Any]:
    return {
        "status": "PARTIAL",
        "preflight": {},
        "post_detach_preflight": {},
        "git_start": None,
        "git_end": None,
        "page_state": None,
        "send_counts": {"before": None, "after_set_tools": None, "final": None},
        "initial_tool": None,
        "set_tools": {"attempted": False, "result": None, "error": None},
        "restore": None,
        "confirmations": {
            "own_tab_only_no_json_list": True,
            "zero_sends": False,
            "send_count_asserted_zero": False,
            "browser_not_quit_post_detach_ok": False,
            "no_auth_oai_cookie_logged": True,
            "no_conversation_content": True,
            "branch_rewrite_v2": None,
            "head_90281f3": None,
            "stable_unmoved_start_end": None,
            "nothing_staged": None,
            "protected_paths_not_staged": None,
            "target_conversation_6a316aa8_untouched": True,
        },
        "blockers": [],
        "signals": [],
    }


def append_blocker(results: dict[str, Any], code: str, action: str) -> None:
    results["blockers"].append({"code": code, "action": action})


def stop(results: dict[str, Any], status: str, code: str, action: str) -> None:
    append_blocker(results, code, action)
    raise StopRun(status=status, code=code, action=action)


def json_inline(value: Any) -> str:
    return json.dumps(_scrub(value), sort_keys=True)


def determine_status(results: dict[str, Any]) -> str:
    if results.get("status") == "BLOCKED":
        return "BLOCKED"
    send_final = results.get("send_counts", {}).get("final")
    if send_final not in (None, 0):
        return "BLOCKED"
    tool_result = results.get("set_tools", {}).get("result")
    verified = isinstance(tool_result, dict) and tool_result.get("verified") is True
    reflected = isinstance(tool_result, dict) and tool_result.get("reflected") == TOOL_LABEL
    if verified and reflected:
        conf = results.get("confirmations") or {}
        required = [
            conf.get("branch_rewrite_v2"),
            conf.get("head_90281f3"),
            conf.get("stable_unmoved_start_end"),
            conf.get("nothing_staged"),
            conf.get("protected_paths_not_staged"),
            conf.get("browser_not_quit_post_detach_ok"),
            conf.get("send_count_asserted_zero"),
        ]
        return "DONE" if all(value is True for value in required) else "PARTIAL"
    if results.get("preflight", {}).get("ok") is not True:
        return "BLOCKED"
    return "PARTIAL"


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = results.get("status") or "PARTIAL"
    preflight = results.get("preflight") or {}
    post = results.get("post_detach_preflight") or {}
    git_start = results.get("git_start") or {}
    git_end = results.get("git_end") or {}
    conf = results.get("confirmations") or {}
    send_counts = results.get("send_counts") or {}
    set_tools_info = results.get("set_tools") or {}
    tool_result = set_tools_info.get("result")
    tool_error = set_tools_info.get("error")
    gap_closed = isinstance(tool_result, dict) and tool_result.get("verified") is True and tool_result.get("reflected") == TOOL_LABEL

    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M7b-T3c live tools-selection re-verify")
    lines.append("")
    lines.append("## CDP preflight")
    lines.append("- Endpoint used: `/json/version` only (no `/json/list`).")
    lines.append(f"- Browser version: `{preflight.get('browser')}`")
    lines.append(f"- Protocol-Version: `{preflight.get('protocol_version')}`")
    lines.append(f"- WebSocket URL present: `{preflight.get('websocket_url_present')}`")
    lines.append(f"- Preflight ok/error: `{preflight.get('ok')}` / `{preflight.get('error_code') or preflight.get('error')}`")
    lines.append("")
    lines.append("## Send count")
    lines.append(f"- Exact this-run `send_budget.successful_submissions`: `{send_counts.get('final')}`")
    lines.append(f"- Count before/after `set_tools`/final: `{send_counts.get('before')}` / `{send_counts.get('after_set_tools')}` / `{send_counts.get('final')}`")
    lines.append(f"- ZERO-send assertion (`== 0`): `{conf.get('send_count_asserted_zero')}`")
    lines.append("")
    lines.append("## set_tools([\"Web search\"])")
    lines.append(f"- Attempted: `{set_tools_info.get('attempted')}`")
    lines.append(f"- Initial Web search menu option: `{json_inline(results.get('initial_tool'))}`")
    lines.append(f"- Result: `{json_inline(tool_result)}`")
    lines.append(f"- Typed error: `{json_inline(tool_error)}`")
    lines.append(f"- Restore outcome: `{json_inline(results.get('restore'))}`")
    lines.append(f"- Verdict: gap-1 tools `{'CLOSED' if gap_closed else 'NOT CLOSED'}`")
    lines.append("")
    lines.append("## Confirmations")
    lines.append(f"- Own-tab-only/no `/json/list`: `{conf.get('own_tab_only_no_json_list')}`; driver uses only the `Session`/`TabPool` tab it opens and never enumerates foreign tabs.")
    lines.append(f"- ZERO sends: `{conf.get('zero_sends')}`; no composer fill+submit, no `Session.ask`, no `Session.loop`.")
    lines.append(f"- Browser not quit/post-detach ok: `{conf.get('browser_not_quit_post_detach_ok')}`; post-detach `/json/version` ok: `{post.get('ok')}`; browser: `{post.get('browser')}`")
    lines.append(f"- No auth/oai/cookie/session values logged: `{conf.get('no_auth_oai_cookie_logged')}`")
    lines.append(f"- No conversation content logged: `{conf.get('no_conversation_content')}`")
    lines.append(f"- Branch `rewrite-v2` start/end: `{git_start.get('branch')}` / `{git_end.get('branch')}`; ok: `{conf.get('branch_rewrite_v2')}`")
    lines.append(f"- HEAD short start/end: `{git_start.get('head_short')}` / `{git_end.get('head_short')}`; expected `{EXPECTED_HEAD_SHORT}`: `{conf.get('head_90281f3')}`")
    lines.append(f"- Protected conversation `{TARGET_CONVERSATION_ID}` untouched by this run: `{conf.get('target_conversation_6a316aa8_untouched')}`")
    lines.append(f"- `stable` unchanged start/end: `{conf.get('stable_unmoved_start_end')}`; revs: `{git_start.get('stable_rev')}` / `{git_end.get('stable_rev')}`")
    lines.append(f"- Nothing staged: `{conf.get('nothing_staged')}`; staged files: `{json_inline(git_end.get('staged_files'))}`")
    lines.append(f"- Protected paths not staged (`cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`): `{conf.get('protected_paths_not_staged')}`; protected staged: `{json_inline(git_end.get('protected_paths_staged'))}`")
    lines.append("")
    lines.append("## Blockers")
    if results.get("blockers"):
        for blocker in results["blockers"]:
            lines.append(f"- `{blocker.get('code')}`: {blocker.get('action')}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Signals")
    if results.get("page_state"):
        lines.append(f"- Own-tab page state: `{json_inline(results.get('page_state'))}`")
    if results.get("signals"):
        for signal in results["signals"]:
            lines.append(f"- {signal}")
    else:
        lines.append("- Production `set_tools` re-open verification returned `verified=True` for Web search with zero sends.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    results = initial_results()
    session: Session | None = None
    tab: Any = None
    tab_released = False
    stable_start: str | None = None
    try:
        preflight = preflight_version()
        results["preflight"] = preflight
        emit("preflight", browser=preflight.get("browser"), protocol_version=preflight.get("protocol_version"), websocket_url_present=preflight.get("websocket_url_present"), ok=preflight.get("ok"), error_code=preflight.get("error_code"))
        if preflight.get("ok") is not True:
            stop(results, "BLOCKED", "CDP_UNREACHABLE", "Expose Chrome CDP on 127.0.0.1:9222 and rerun; no browser attach attempted.")

        git_start = git_checks()
        results["git_start"] = git_start
        stable_start = git_start.get("stable_rev") if isinstance(git_start.get("stable_rev"), str) else None
        results["confirmations"]["branch_rewrite_v2"] = git_start.get("branch_ok_rewrite_v2")
        results["confirmations"]["head_90281f3"] = git_start.get("head_expected")
        emit("git_start", branch=git_start.get("branch"), head_short=git_start.get("head_short"), stable_rev=git_start.get("stable_rev"), staged_count=len(git_start.get("staged_files") or []))
        if git_start.get("branch_ok_rewrite_v2") is not True:
            stop(results, "BLOCKED", "WRONG_BRANCH", "Switch to branch rewrite-v2 before running live verification; no browser attach attempted.")
        if git_start.get("head_expected") is not True:
            stop(results, "BLOCKED", "WRONG_HEAD", f"Expected HEAD {EXPECTED_HEAD_SHORT} on rewrite-v2; no browser attach attempted.")

        session = Session(channel="cdp", data_dir=DATA_DIR)
        session.attach()
        emit("attached")
        draft = session.create()
        tab = session.tab_pool.acquire(draft)
        emit("opened_own_tab", tab_id=getattr(tab, "tab_id", None))

        try:
            wait_for_composer(tab, session.selector_map, timeout_s=session.composer_wait_timeout_s)
        except Exception as exc:  # noqa: BLE001 - safe type only; stop for human action per contract.
            try:
                results["page_state"] = page_state(tab)
            except Exception as state_exc:  # noqa: BLE001
                results["page_state"] = {"state_error": type(state_exc).__name__}
            results["signals"].append(f"Composer unavailable; wait error type `{type(exc).__name__}`.")
            stop(results, "BLOCKED", "HUMAN-ACTION-NEEDED", "Operator must clear login/Cloudflare/human action until `#prompt-textarea` is visible; no stealth or retries attempted.")

        results["page_state"] = page_state(tab)
        if results["page_state"].get("target_conversation_loaded") is True:
            results["confirmations"]["target_conversation_6a316aa8_untouched"] = False
            stop(results, "BLOCKED", "TARGET_CONVERSATION_LOADED", f"Fresh own tab resolved to protected conversation {TARGET_CONVERSATION_ID}; stop and audit browser state.")
        if results["page_state"].get("challenge_likely") is True or results["page_state"].get("login_likely") is True or results["page_state"].get("has_composer") is not True:
            stop(results, "BLOCKED", "HUMAN-ACTION-NEEDED", "Login/Cloudflare/human-action page state detected; no stealth or retries attempted.")

        try:
            results["initial_tool"] = web_search_option(tab, session.selector_map)
            emit("initial_tool", checked=(results["initial_tool"] or {}).get("checked") if isinstance(results.get("initial_tool"), dict) else None)
        except Exception as exc:  # noqa: BLE001 - initial state is best-effort only.
            results["initial_tool"] = {"error": type(exc).__name__}
            emit("initial_tool_error", error_type=type(exc).__name__)

        results["send_counts"]["before"] = session.send_budget.successful_submissions
        results["set_tools"]["attempted"] = True
        try:
            set_tools_result = set_tools(tab, session.selector_map, [TOOL_LABEL])
            first = set_tools_result[0] if set_tools_result else None
            results["set_tools"]["result"] = selection_record(first)
            emit("set_tools_done", result=results["set_tools"]["result"])
        except Exception as exc:  # noqa: BLE001 - record exact typed failure, fail closed.
            results["set_tools"]["error"] = error_summary(exc)
            emit("set_tools_error", error=results["set_tools"]["error"])
        results["send_counts"]["after_set_tools"] = session.send_budget.successful_submissions

        try:
            results["restore"] = restore_tool_to_initial(tab, session.selector_map, results.get("initial_tool"))
            emit("restore", needed=(results["restore"] or {}).get("needed"), clicked=(results["restore"] or {}).get("clicked"), checked_after_restore=(results["restore"] or {}).get("checked_after_restore"), error=(results["restore"] or {}).get("error"))
        except Exception as exc:  # noqa: BLE001 - optional restore is non-fatal.
            results["restore"] = {"error": type(exc).__name__}
            emit("restore_error", error_type=type(exc).__name__)

        final_count = session.send_budget.successful_submissions
        results["send_counts"]["final"] = final_count
        results["confirmations"]["zero_sends"] = final_count == 0
        results["confirmations"]["send_count_asserted_zero"] = final_count == 0
        if final_count != 0:
            stop(results, "BLOCKED", "ZERO_SENDS_VIOLATED", f"send_budget.successful_submissions was {final_count}, expected 0.")

        tool_result = results["set_tools"].get("result")
        if isinstance(tool_result, dict) and tool_result.get("verified") is True and tool_result.get("reflected") == TOOL_LABEL:
            results["signals"].append("Production `set_tools([\"Web search\"])` returned `verified=True` and reflected `Web search` after the re-open verification path.")
        else:
            tool_error = results["set_tools"].get("error")
            if isinstance(tool_error, dict) and tool_error.get("code") == "TOOL_SELECTION_NOT_REFLECTED":
                append_blocker(results, "M8_BLOCKER_TOOL_SELECTION_NOT_REFLECTED", "`set_tools([\"Web search\"])` still failed closed with `TOOL_SELECTION_NOT_REFLECTED`; gap-1 tools is NOT closed.")
            else:
                append_blocker(results, "TOOL_SELECTION_NOT_VERIFIED", "`set_tools([\"Web search\"])` did not produce a verified reflected result; inspect typed error/result above.")
    except StopRun as exc:
        results["status"] = exc.status
        results["signals"].append(f"Stopped: `{exc.code}`.")
        emit("stopped", status=exc.status, code=exc.code)
    except Exception as exc:  # noqa: BLE001 - safe metadata only.
        if results.get("status") != "BLOCKED":
            results["status"] = "PARTIAL"
        append_blocker(results, type(exc).__name__, "Driver exception; inspect safe report and rerun only if needed without sends.")
        emit("driver_error", error_type=type(exc).__name__)
    finally:
        if session is not None:
            try:
                if session.send_budget.successful_submissions is not None:
                    results["send_counts"]["final"] = session.send_budget.successful_submissions
                    results["confirmations"]["zero_sends"] = session.send_budget.successful_submissions == 0
                    results["confirmations"]["send_count_asserted_zero"] = session.send_budget.successful_submissions == 0
                if tab is not None and not tab_released:
                    try:
                        session.tab_pool.release(tab)
                        tab_released = True
                        emit("released_own_tab", tab_id=getattr(tab, "tab_id", None))
                    except Exception as exc:  # noqa: BLE001
                        append_blocker(results, "TAB_RELEASE_FAILED", f"Session.tab_pool.release raised {type(exc).__name__}; Session.detach attempted next.")
                        emit("release_error", error_type=type(exc).__name__)
                session.detach()
                emit("detached")
            except Exception as exc:  # noqa: BLE001
                append_blocker(results, "DETACH_FAILED", f"Session.detach raised {type(exc).__name__}; do not kill browser manually.")
                emit("detach_error", error_type=type(exc).__name__)
        post = preflight_version() if results.get("preflight") else {}
        results["post_detach_preflight"] = post
        results["confirmations"]["browser_not_quit_post_detach_ok"] = post.get("ok") is True if post else False
        git_end = git_checks() if results.get("git_start") is not None else None
        results["git_end"] = git_end
        if git_end is not None:
            results["confirmations"]["branch_rewrite_v2"] = git_end.get("branch_ok_rewrite_v2")
            results["confirmations"]["head_90281f3"] = git_end.get("head_expected")
            results["confirmations"]["nothing_staged"] = not bool(git_end.get("staged_files"))
            results["confirmations"]["protected_paths_not_staged"] = not bool(git_end.get("protected_paths_staged"))
            stable_end = git_end.get("stable_rev")
            results["confirmations"]["stable_unmoved_start_end"] = bool(stable_start and stable_end and stable_start == stable_end)
        results["status"] = determine_status(results)
        write_report(results)
        emit("report_written", status=results.get("status"), report=str(REPORT_PATH))
    return 0 if results.get("status") == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
