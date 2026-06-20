#!/usr/bin/env python3
"""M9-W6 attended real-site re-verify: DR chip, family retry, upload smoke.

Own-tab-only CDP driver. It emits and writes safe metadata only; any
conversation text captured by the library remains only in the gitignored Store
DATA_DIR.
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
    AttachmentUploadError,
    HumanActionNeededError,
    ModelSelectionNotReflectedError,
    SelectorNotFoundError,
    ToolSelectionNotReflectedError,
)
from ask_chatgpt.menus import (
    SelectionResult,
    enumerate_radix_options,
    open_radix_menu,
    select_model,
    select_radix_label,
    set_tools,
)
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.send import normalize_prompt
from ask_chatgpt.session import Session

CDP_VERSION_URL = "http://127.0.0.1:9222/json/version"
DATA_DIR = Path("cache/m9-w6-reverify")
REPORT_PATH = Path("team/evidence/reports/M9-W6-reverify.txt")
TARGET_CONVERSATION_ID = "6a316aa8"
TARGET_CONVERSATION_FULL_ID = "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"
THIS_RUN_SEND_CAP = 2
EXPECTED_INITIAL_MODEL = "Pro Extended"
FAMILY_TARGET_MODEL = "GPT-5.4"
DR_LABEL = "Deep research"
UPLOAD_PATH = Path("/tmp/m9-upload.txt")
UPLOAD_TEXT = "m9 upload smoke canary\n"
PONG_PROMPT = "Reply with only the word: PONG"

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
    "m9 upload smoke canary",
    "oai-",
    "password",
    "reply with only the word",
    "secret",
    "token",
)

DR_COMPOSER_SIGNAL_JS = r"""
(a) => {
  a = a || {};
  const wanted = String(a.label || '').toLowerCase();
  const portalSelector = '[data-radix-popper-content-wrapper]';
  const root = document.querySelector('form') || document.body;
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const esc = value => {
    try { return CSS.escape(value); } catch (_) { return String(value).replace(/"/g, '\\"'); }
  };
  const selectorFor = (el, ariaLabel, testid, role, matchedBy) => {
    const tag = el.tagName.toLowerCase();
    if (testid) return `[data-testid="${esc(testid)}"]`;
    if (ariaLabel && ariaLabel.toLowerCase().includes(wanted)) return `${tag}[aria-label*="${a.label}" i]`;
    if (role === 'button' && matchedBy === 'ui_text') return `${tag}[role="button"] /* visible text: ${a.label} */`;
    if (tag === 'button' && matchedBy === 'ui_text') return `button /* visible text: ${a.label} */`;
    return null;
  };
  const candidates = [];
  const seen = new Set();
  const nodes = Array.from(root.querySelectorAll('button,[role="button"],[aria-label],[data-testid],span,div'));
  for (const el of nodes) {
    if (seen.has(el) || el.closest(portalSelector) || !visible(el)) continue;
    seen.add(el);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || null;
    const ariaLabel = norm(el.getAttribute('aria-label'));
    const testid = norm(el.getAttribute('data-testid'));
    const title = norm(el.getAttribute('title'));
    const uiText = norm(el.innerText || el.textContent || '');
    const fields = [
      ['aria_label', ariaLabel],
      ['data_testid', testid],
      ['title', title],
      ['ui_text', uiText],
    ].filter(item => item[1]);
    const match = fields.find(item => item[1].toLowerCase().includes(wanted));
    if (!match) continue;
    candidates.push({
      tag,
      role,
      aria_label: ariaLabel || null,
      data_testid: testid || null,
      title: title || null,
      matched_by: match[0],
      stable_selector: selectorFor(el, ariaLabel, testid, role, match[0]),
    });
    if (candidates.length >= 8) break;
  }
  return {has_signal: candidates.length > 0, candidate_count: candidates.length, candidates};
}
"""

ACTIVE_TOOL_CHIP_SIGNAL_JS = r"""
(a) => {
  a = a || {};
  const selector = String(a.selector || '');
  const wanted = String(a.label || '').toLowerCase();
  const root = document.querySelector('form') || document.body;
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const candidates = [];
  let nodes = [];
  try {
    nodes = Array.from(root.querySelectorAll(selector));
  } catch (err) {
    return {selector_used: selector, has_signal: false, candidate_count: 0, candidates: [], error: 'invalid_selector'};
  }
  for (const el of nodes) {
    if (!visible(el)) continue;
    const ariaLabel = norm(el.getAttribute('aria-label'));
    const uiText = norm(el.innerText || el.textContent || '');
    const labelText = ariaLabel || uiText;
    if (wanted && !labelText.toLowerCase().includes(wanted)) continue;
    candidates.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || null,
      aria_label: ariaLabel || null,
      ui_text: uiText || null,
    });
    if (candidates.length >= 8) break;
  }
  return {selector_used: selector, has_signal: candidates.length > 0, candidate_count: candidates.length, candidates};
}
"""


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


def append_blocker(results: dict[str, Any], code: str, leg: str, action: str) -> None:
    results["blockers"].append({"code": code, "leg": leg, "action": action})


def raise_stop(results: dict[str, Any], status: str, code: str, leg: str, action: str) -> None:
    append_blocker(results, code, leg, action)
    raise StopRun(status=status, code=code, leg=leg, action=action)


def is_target_conversation_id(value: str | None) -> bool:
    return bool(value) and str(value).startswith(TARGET_CONVERSATION_ID)


def guard_not_target(
    results: dict[str, Any],
    leg: str,
    *,
    conversation_id: str | None = None,
    url: str | None = None,
) -> None:
    if is_target_conversation_id(conversation_id) or (url and f"/c/{TARGET_CONVERSATION_ID}" in url):
        results["confirmations"]["target_6a316aa8_not_touched"] = False
        raise_stop(
            results,
            "BLOCKED",
            "TARGET_CONVERSATION_MATCH",
            leg,
            "An owned draft/send resolved to the protected conversation id; stopped before any retry.",
        )


def current_url(tab: Any) -> str:
    value = tab.channel.evaluate(tab, "ask_chatgpt_current_url", timeout_s=5.0)
    return value if isinstance(value, str) else ""


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


def sustained_label_read(
    tab: Any,
    selectors: dict[str, str],
    *,
    duration_s: float = 12.0,
    interval_s: float = 2.0,
) -> dict[str, Any]:
    start = _tab_monotonic(tab)
    samples: list[dict[str, Any]] = []
    while True:
        now = _tab_monotonic(tab)
        labels = _labels_now(tab, selectors)
        samples.append({"elapsed_s": round(now - start, 3), "labels": labels})
        elapsed = _tab_monotonic(tab) - start
        if elapsed >= duration_s:
            break
        _tab_sleep(tab, min(interval_s, max(0.0, duration_s - elapsed)))
    elapsed_final = _tab_monotonic(tab) - start
    singletons = [sample["labels"][0] for sample in samples if len(sample["labels"]) == 1]
    stable = len(singletons) == len(samples) and len(set(map(normalize_prompt, singletons))) == 1
    label = singletons[-1] if singletons else None
    return {
        "label": label,
        "ok": stable and elapsed_final >= duration_s,
        "duration_s": round(elapsed_final, 3),
        "sample_count": len(samples),
        "last_labels": samples[-1]["labels"] if samples else (),
    }


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


def menu_option_meta(option: Any) -> dict[str, Any]:
    return {
        "label": getattr(option, "label", None),
        "role": getattr(option, "role", None),
        "checked": getattr(option, "checked", None),
        "disabled": getattr(option, "disabled", None),
        "path": list(getattr(option, "path", ()) or ()),
    }


def wait_for_composer_or_human(session: Session, tab: Any, results: dict[str, Any], leg: str) -> None:
    try:
        tab.channel.wait_for_selector(tab, session.selector_map["composer"], state="visible", timeout_s=20.0)
        snapshot = tab.channel.query_turns(tab, session.selector_map)
        if not snapshot.composer_visible:
            raise SelectorNotFoundError("composer not visible after wait")
    except Exception as exc:  # noqa: BLE001 - login/challenge/no composer means stop for human action.
        raise HumanActionNeededError(
            "fresh composer was absent",
            details={"reason": "composer_absent_or_challenge", "error_type": type(exc).__name__},
        ) from exc
    guard_not_target(results, leg, url=current_url(tab))


def acquire_fresh_draft(session: Session, results: dict[str, Any], leg: str) -> Any:
    draft = session.create()
    try:
        tab = session.tab_pool.acquire(draft)
        emit(f"{leg}_tab_acquired", tab_id=getattr(tab, "tab_id", None))
    except Exception as exc:  # noqa: BLE001
        raise HumanActionNeededError(
            "fresh composer tab could not be opened",
            details={"reason": "composer_absent_or_challenge", "error_type": type(exc).__name__},
        ) from exc
    guard_not_target(results, leg, url=current_url(tab))
    wait_for_composer_or_human(session, tab, results, leg)
    return tab


def release_tab(session: Session, tab: Any | None, results: dict[str, Any], leg: str, *, close_after: bool) -> None:
    if tab is not None:
        try:
            session.tab_pool.release(tab)
            emit(f"{leg}_tab_released", tab_id=getattr(tab, "tab_id", None))
        except Exception as exc:  # noqa: BLE001
            append_blocker(results, "TAB_RELEASE_FAILED", leg, f"Own managed tab release raised {type(exc).__name__}.")
            emit(f"{leg}_tab_release_failed", error={"type": type(exc).__name__})
    if close_after:
        try:
            session.tab_pool.close_all()
            emit(f"{leg}_own_tabs_closed")
        except Exception as exc:  # noqa: BLE001
            append_blocker(results, "OWN_TAB_CLOSE_FAILED", leg, f"Own managed tab close_all raised {type(exc).__name__}.")
            emit(f"{leg}_own_tab_close_failed", error={"type": type(exc).__name__})


def close_owned_tabs(session: Session, results: dict[str, Any], leg: str) -> None:
    try:
        session.tab_pool.close_all()
        emit(f"{leg}_own_tabs_closed")
    except Exception as exc:  # noqa: BLE001
        append_blocker(results, "OWN_TAB_CLOSE_FAILED", leg, f"Own managed tab close_all raised {type(exc).__name__}.")
        emit(f"{leg}_own_tab_close_failed", error={"type": type(exc).__name__})


def turn_meta(turn: TurnRecord) -> dict[str, Any]:
    return {
        "conversation_id": turn.conversation_id,
        "conversation_url": turn.conversation_url,
        "role": turn.role,
        "status": turn.status,
        "partial": turn.partial,
        "nonempty": len(turn.content_markdown) > 0,
        "char_count": len(turn.content_markdown),
        "capture_source": turn.capture_source,
        "fidelity": turn.fidelity,
        "turn_index": turn.turn_index,
        "user_message_id_present": bool(turn.user_message_id),
    }


def transcript_meta(transcript: Transcript) -> dict[str, Any]:
    roles: dict[str, int] = {}
    attachment_counts_by_role: dict[str, int] = {}
    for turn in transcript.turns:
        roles[turn.role] = roles.get(turn.role, 0) + 1
        attachment_counts_by_role[turn.role] = attachment_counts_by_role.get(turn.role, 0) + len(turn.attachments)
    return {
        "conversation_id": transcript.conversation.conversation_id,
        "conversation_url": transcript.conversation.url,
        "turn_count": len(transcript.turns),
        "roles": roles,
        "attachment_counts_by_role": attachment_counts_by_role,
        "transcript_path": str(transcript.transcript_path) if transcript.transcript_path else None,
        "raw_mapping_path": str(transcript.raw_mapping_path) if transcript.raw_mapping_path else None,
    }


def conversation_url_has_id(url: str, conversation_id: str) -> bool:
    return bool(conversation_id) and f"/c/{conversation_id}" in url


def tool_menu_state(tab: Any, selectors: dict[str, str], label: str = DR_LABEL) -> dict[str, Any]:
    state: dict[str, Any] = {
        "opened": False,
        "present": False,
        "match_count": 0,
        "matches": [],
        "deep_checked": None,
        "checked_labels": [],
        "error": None,
    }
    try:
        open_radix_menu(tab, selectors["tools_button"])
        state["opened"] = True
        options = enumerate_radix_options(tab)
        normalized = normalize_prompt(label)
        matches = [option for option in options if normalize_prompt(option.label) == normalized]
        checked = [option.label for option in options if option.checked is True]
        state.update(
            {
                "present": bool(matches),
                "match_count": len(matches),
                "matches": [menu_option_meta(option) for option in matches],
                "deep_checked": matches[0].checked if len(matches) == 1 else None,
                "checked_labels": checked,
            }
        )
    except AskChatGPTError as exc:
        state["error"] = ask_error_summary(exc)
    except Exception as exc:  # noqa: BLE001
        state["error"] = {"type": type(exc).__name__}
    finally:
        try:
            tab.channel.press(tab, "body", "Escape")
        except Exception:
            pass
    return _scrub(state)


def dr_composer_signal(tab: Any, label: str = DR_LABEL) -> dict[str, Any]:
    try:
        raw = tab.channel.evaluate(tab, DR_COMPOSER_SIGNAL_JS, arg={"label": label}, timeout_s=5.0)
        if isinstance(raw, dict):
            return _scrub(raw)
    except Exception as exc:  # noqa: BLE001
        return {"has_signal": False, "candidate_count": 0, "candidates": [], "error": {"type": type(exc).__name__}}
    return {"has_signal": False, "candidate_count": 0, "candidates": [], "error": {"type": "non_object_result"}}


def active_tool_chip_signal(tab: Any, selectors: dict[str, str], label: str | None = DR_LABEL) -> dict[str, Any]:
    try:
        raw = tab.channel.evaluate(
            tab,
            ACTIVE_TOOL_CHIP_SIGNAL_JS,
            arg={"selector": selectors.get("active_tool_chip"), "label": label or ""},
            timeout_s=5.0,
        )
        if isinstance(raw, dict):
            return _scrub(raw)
    except Exception as exc:  # noqa: BLE001
        return {"has_signal": False, "candidate_count": 0, "candidates": [], "error": {"type": type(exc).__name__}}
    return {"has_signal": False, "candidate_count": 0, "candidates": [], "error": {"type": "non_object_result"}}


def dr_state(tab: Any, selectors: dict[str, str]) -> dict[str, Any]:
    # Ensure a stale menu portal is not mistaken for a composer chip.
    try:
        tab.channel.press(tab, "body", "Escape")
    except Exception:
        pass
    chip = dr_composer_signal(tab, DR_LABEL)
    active_chip = active_tool_chip_signal(tab, selectors, DR_LABEL)
    menu = tool_menu_state(tab, selectors, DR_LABEL)
    armed = bool(chip.get("has_signal")) or bool(active_chip.get("has_signal")) or menu.get("deep_checked") is True
    return {"chip": chip, "active_tool_chip": active_chip, "menu": menu, "armed": armed}


def reload_own_tab(session: Session, tab: Any, results: dict[str, Any], leg: str) -> None:
    tab.channel.reload(tab)
    tab.channel.wait_for_load_state(tab, timeout_s=20.0)
    wait_for_composer_or_human(session, tab, results, leg)


def clear_dr_if_needed(session: Session, tab: Any, results: dict[str, Any]) -> dict[str, Any]:
    before = dr_state(tab, session.selector_map)
    outcome: dict[str, Any] = {
        "before": before,
        "method": "not_armed",
        "after_reload": None,
        "after_toggle": None,
        "cleared": before.get("armed") is False,
    }
    if outcome["cleared"]:
        return outcome

    outcome["method"] = "reload"
    reload_own_tab(session, tab, results, "dr")
    after_reload = dr_state(tab, session.selector_map)
    outcome["after_reload"] = after_reload
    if after_reload.get("armed") is False:
        outcome["cleared"] = True
        return outcome

    menu = after_reload.get("menu") if isinstance(after_reload, dict) else {}
    if isinstance(menu, dict) and menu.get("deep_checked") is True:
        outcome["method"] = "reload_then_toggle_menu"
        try:
            open_radix_menu(tab, session.selector_map["tools_button"])
            select_radix_label(tab, DR_LABEL)
        finally:
            try:
                tab.channel.press(tab, "body", "Escape")
            except Exception:
                pass
        _tab_sleep(tab, 1.0)
        after_toggle = dr_state(tab, session.selector_map)
        outcome["after_toggle"] = after_toggle
        outcome["cleared"] = after_toggle.get("armed") is False
    return outcome


def run_family(session: Session, results: dict[str, Any]) -> None:
    family = results["family"]
    start_count = session.send_budget.successful_submissions
    tab = None
    try:
        tab = acquire_fresh_draft(session, results, "family")
        initial = sustained_label_read(tab, session.selector_map, duration_s=12.0, interval_s=2.0)
        family["initial"] = initial
        family["initial_expected_pro_extended"] = normalize_prompt(str(initial.get("label") or "")) == normalize_prompt(EXPECTED_INITIAL_MODEL)
        emit("family_initial", label=initial.get("label"), expected=family["initial_expected_pro_extended"], sustained=initial.get("ok"))

        try:
            model_res = select_model(tab, session.selector_map, FAMILY_TARGET_MODEL)
            family["select_model"] = selection_result_meta(model_res)
            emit("family_model_selected", result=family["select_model"])
        except ModelSelectionNotReflectedError as exc:
            family["select_model_error"] = ask_error_summary(exc)
            emit("family_model_select_failed", error=family["select_model_error"])
        except AskChatGPTError as exc:
            family["select_model_error"] = ask_error_summary(exc)
            emit("family_model_select_failed", error=family["select_model_error"])
        except Exception as exc:  # noqa: BLE001
            wrapped = ModelSelectionNotReflectedError(
                "model selection driver boundary failed closed",
                details={"requested_model": FAMILY_TARGET_MODEL, "reason": type(exc).__name__},
            )
            family["select_model_error"] = ask_error_summary(wrapped)
            emit("family_model_select_failed", error=family["select_model_error"])

        original = initial.get("label") if isinstance(initial, dict) else None
        if family.get("select_model") and family["select_model"].get("verified") is True:
            sustained = sustained_model_confirmation(tab, session.selector_map, FAMILY_TARGET_MODEL, duration_s=12.0, interval_s=2.0)
            family["sustained_target"] = sustained
            emit("family_model_sustained", sustained=sustained)
            if original:
                family["restore"]["attempted"] = True
                try:
                    restore_res = select_model(tab, session.selector_map, str(original))
                    family["restore"].update(selection_result_meta(restore_res) or {})
                    family["restore_confirmation"] = sustained_model_confirmation(tab, session.selector_map, str(original), duration_s=12.0, interval_s=2.0)
                    emit("family_model_restored", restore=family["restore"], confirmation=family["restore_confirmation"])
                except AskChatGPTError as exc:
                    family["restore"]["error"] = ask_error_summary(exc)
                    emit("family_model_restore_failed", error=family["restore"]["error"])
                except Exception as exc:  # noqa: BLE001
                    family["restore"]["error"] = {"type": type(exc).__name__}
                    emit("family_model_restore_failed", error=family["restore"]["error"])
            else:
                family["restore"]["attempted"] = False
                family["restore"]["error"] = {"type": "SKIPPED", "reason": "initial_label_absent"}
        else:
            family["sustained_target"] = {"ok": False, "reason": "select_model_not_verified"}
            family["restore"]["attempted"] = False
            family["restore"]["error"] = {"type": "SKIPPED", "reason": "select_model_not_verified"}

        end_count = session.send_budget.successful_submissions
        family["send_count_delta"] = end_count - start_count
        family["send_count_after"] = end_count
        family["zero_sends"] = end_count == start_count
        results["send_counts"]["family"] = end_count - start_count
        if end_count != start_count:
            raise_stop(results, "BLOCKED", "FAMILY_NONZERO_SEND_COUNT", "family", "No-send family leg changed successful_submissions.")
    finally:
        release_tab(session, tab, results, "family", close_after=True)


def run_dr(session: Session, results: dict[str, Any]) -> None:
    dr = results["dr"]
    start_count = session.send_budget.successful_submissions
    tab = None
    try:
        tab = acquire_fresh_draft(session, results, "dr")
        initial_menu = tool_menu_state(tab, session.selector_map, DR_LABEL)
        dr["initial_menu"] = initial_menu
        dr["present"] = initial_menu.get("present") is True
        emit("dr_initial_menu", present=dr["present"], state=initial_menu)

        if dr["present"]:
            try:
                tool_results = set_tools(tab, session.selector_map, [DR_LABEL])
                first = tool_results[0] if tool_results else None
                dr["set_tools"] = selection_result_meta(first)
                emit("dr_set_tools", result=dr["set_tools"])
            except ToolSelectionNotReflectedError as exc:
                dr["set_tools_error"] = ask_error_summary(exc)
                emit("dr_set_tools_failed", error=dr["set_tools_error"])
            except AskChatGPTError as exc:
                dr["set_tools_error"] = ask_error_summary(exc)
                emit("dr_set_tools_failed", error=dr["set_tools_error"])
            except Exception as exc:  # noqa: BLE001
                wrapped = ToolSelectionNotReflectedError(
                    "tool selection driver boundary failed closed",
                    details={"requested_tool": DR_LABEL, "reason": type(exc).__name__},
                )
                dr["set_tools_error"] = ask_error_summary(wrapped)
                emit("dr_set_tools_failed", error=dr["set_tools_error"])
            finally:
                try:
                    tab.channel.press(tab, "body", "Escape")
                except Exception:
                    pass
        else:
            dr["set_tools_error"] = {"type": "SKIPPED", "reason": "deep_research_absent"}

        after_attempt = dr_state(tab, session.selector_map)
        dr["after_attempt_state"] = after_attempt
        dr["active_tool_chip_present"] = bool((after_attempt.get("active_tool_chip") or {}).get("has_signal")) if isinstance(after_attempt, dict) else False
        dr["verified_via_active_tool_chip"] = bool((dr.get("set_tools") or {}).get("verified") is True and dr.get("active_tool_chip_present") is True)
        dr["diagnostic_captured"] = True
        emit("dr_after_attempt", state=after_attempt, verified_via_active_tool_chip=dr["verified_via_active_tool_chip"])

        clear = clear_dr_if_needed(session, tab, results)
        dr["clear"] = clear
        dr["cleared"] = clear.get("cleared") is True
        emit("dr_clear", cleared=dr["cleared"], clear=clear)
        if not dr["cleared"]:
            raise_stop(results, "BLOCKED", "DR_NOT_CLEARED", "dr", "Deep Research/tool state could not be proven clear; stopped before upload send.")

        signal = after_attempt.get("chip") if isinstance(after_attempt, dict) else {}
        active_signal = after_attempt.get("active_tool_chip") if isinstance(after_attempt, dict) else {}
        menu = after_attempt.get("menu") if isinstance(after_attempt, dict) else {}
        selector = None
        if isinstance(active_signal, dict) and active_signal.get("has_signal"):
            selector = active_signal.get("selector_used")
        if selector is None and isinstance(signal, dict):
            candidates = signal.get("candidates")
            if isinstance(candidates, list):
                for candidate in candidates:
                    if isinstance(candidate, dict) and candidate.get("stable_selector"):
                        selector = candidate.get("stable_selector")
                        break
        if selector:
            dr["recommendation"] = f"cheap_wire_composer_chip_selector: {selector}"
        elif isinstance(menu, dict) and menu.get("deep_checked") is True:
            dr["recommendation"] = "cheap_wire_menu_reopen_aria_checked"
        elif dr.get("set_tools_error"):
            dr["recommendation"] = "fails_closed_or_untested_live_no_authoritative_reflection_signal_found"
        else:
            dr["recommendation"] = "no_dr_reflection_signal_observed_after_attempt"

        end_count = session.send_budget.successful_submissions
        dr["send_count_delta"] = end_count - start_count
        dr["send_count_after"] = end_count
        dr["zero_sends"] = end_count == start_count
        results["send_counts"]["dr"] = end_count - start_count
        if end_count != start_count:
            raise_stop(results, "BLOCKED", "DR_NONZERO_SEND_COUNT", "dr", "No-send DR diagnostic changed successful_submissions.")
    finally:
        release_tab(session, tab, results, "dr", close_after=True)


def checked_tools_for_upload(tab: Any, selectors: dict[str, str]) -> dict[str, Any]:
    menu = tool_menu_state(tab, selectors, DR_LABEL)
    chip = dr_composer_signal(tab, DR_LABEL)
    active_chips = active_tool_chip_signal(tab, selectors, None)
    checked_labels = menu.get("checked_labels") if isinstance(menu, dict) else []
    return {
        "menu": menu,
        "dr_chip": chip,
        "active_tool_chips": active_chips,
        "checked_labels": checked_labels if isinstance(checked_labels, list) else [],
        "any_tool_armed": bool(checked_labels) or bool(chip.get("has_signal")) or bool(active_chips.get("has_signal")),
    }


def ensure_upload_draft_pristine(session: Session, results: dict[str, Any]) -> None:
    tab = None
    released = False
    try:
        tab = acquire_fresh_draft(session, results, "upload_precheck")
        state = checked_tools_for_upload(tab, session.selector_map)
        results["upload"]["precheck_initial"] = state
        if state.get("any_tool_armed"):
            reload_own_tab(session, tab, results, "upload_precheck")
            state = checked_tools_for_upload(tab, session.selector_map)
            results["upload"]["precheck_after_reload"] = state
        if state.get("any_tool_armed"):
            raise_stop(results, "BLOCKED", "TOOL_ARMED_BEFORE_UPLOAD", "upload", "Fresh upload draft had a reflected tool/DR state; stopped before send.")
        session.tab_pool.release(tab)
        released = True
        emit("upload_precheck_tab_released_for_ask_reuse", tab_id=getattr(tab, "tab_id", None), clear=True)
    finally:
        if tab is not None and not released:
            release_tab(session, tab, results, "upload_precheck", close_after=True)


def attachment_evidence_from_history(transcript: Transcript, rec: TurnRecord, upload_path: Path) -> dict[str, Any]:
    expected_name = upload_path.name
    expected_size = upload_path.stat().st_size
    user_turns = [turn for turn in transcript.turns if turn.role == "user"]
    selected = [turn for turn in user_turns if rec.user_message_id and turn.message_id == rec.user_message_id]
    found_by_user_message_id = bool(selected)
    if not selected and user_turns:
        selected = [user_turns[-1]]
    attachments = [attachment for turn in selected for attachment in turn.attachments]
    return {
        "user_turn_count": len(user_turns),
        "user_turn_found_by_user_message_id": found_by_user_message_id,
        "selected_user_turn_count": len(selected),
        "user_turn_has_attachment": bool(attachments),
        "attachment_count": len(attachments),
        "name_matches_m9_upload": any(attachment.filename == expected_name for attachment in attachments),
        "size_matches": any(attachment.bytes == expected_size for attachment in attachments),
        "source_ref_present_count_redacted": sum(1 for attachment in attachments if attachment.source_ref),
    }


def attachment_evidence_from_raw_mapping(raw_mapping_path: Path | None, rec: TurnRecord, upload_path: Path) -> dict[str, Any]:
    expected_name = upload_path.name
    expected_size = upload_path.stat().st_size
    out: dict[str, Any] = {
        "raw_mapping_available": False,
        "user_message_match_count": 0,
        "user_turn_has_attachment": False,
        "attachment_count": 0,
        "name_matches_m9_upload": False,
        "size_matches": False,
        "file_id_present_count_redacted": 0,
        "error": None,
    }
    if raw_mapping_path is None or not raw_mapping_path.exists():
        return out
    out["raw_mapping_available"] = True
    try:
        raw = json.loads(raw_mapping_path.read_text(encoding="utf-8"))
        mapping = raw.get("mapping") if isinstance(raw, dict) else None
        if not isinstance(mapping, dict):
            out["error"] = "mapping_absent"
            return out
        selected_messages: list[dict[str, Any]] = []
        all_user_messages: list[dict[str, Any]] = []
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            author = message.get("author")
            role = author.get("role") if isinstance(author, dict) else None
            if role != "user":
                continue
            all_user_messages.append(message)
            message_id = message.get("id") if isinstance(message.get("id"), str) else str(node_id)
            if rec.user_message_id and message_id == rec.user_message_id:
                selected_messages.append(message)
        if not selected_messages and all_user_messages:
            selected_messages = [all_user_messages[-1]]
        out["user_message_match_count"] = len(selected_messages)
        attachment_items: list[dict[str, Any]] = []
        for message in selected_messages:
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            items = metadata.get("attachments")
            if isinstance(items, list):
                attachment_items.extend(item for item in items if isinstance(item, dict))
        out["attachment_count"] = len(attachment_items)
        out["user_turn_has_attachment"] = bool(attachment_items)
        out["name_matches_m9_upload"] = any(item.get("name") == expected_name for item in attachment_items)
        out["size_matches"] = any(item.get("size") == expected_size for item in attachment_items)
        out["file_id_present_count_redacted"] = sum(1 for item in attachment_items if isinstance(item.get("id"), str) and item.get("id"))
    except Exception as exc:  # noqa: BLE001
        out["error"] = type(exc).__name__
    return out


def run_upload(session: Session, results: dict[str, Any]) -> None:
    upload = results["upload"]
    UPLOAD_PATH.write_text(UPLOAD_TEXT, encoding="utf-8")
    upload["throwaway_file"] = {"path": str(UPLOAD_PATH), "size": UPLOAD_PATH.stat().st_size, "created": True}
    upload["file_content_logged"] = False

    rec: TurnRecord | None = None
    last_error: dict[str, Any] | None = None
    for attempt in range(1, 3):
        ensure_upload_draft_pristine(session, results)
        before = session.send_budget.successful_submissions
        if before >= THIS_RUN_SEND_CAP:
            raise_stop(results, "BLOCKED", "SEND_CAP_EXHAUSTED_BEFORE_UPLOAD", "upload", "No send budget remained for upload smoke.")
        upload["attempts"] = attempt
        upload["send_budget_before_attempt"] = before
        emit("upload_attempt_start", attempt=attempt, before=before)
        try:
            rec = session.ask(None, PONG_PROMPT, attach=[UPLOAD_PATH], timeout=180)
            after = session.send_budget.successful_submissions
            upload["send_budget_after_success"] = after
            upload["send_count_delta_success"] = after - before
            upload["no_attachment_upload_error"] = True
            if after - before != 1:
                raise_stop(results, "BLOCKED", "UPLOAD_SEND_DELTA_NOT_ONE", "upload", "Upload smoke successful_submissions delta was not exactly 1.")
            if after > THIS_RUN_SEND_CAP:
                raise_stop(results, "BLOCKED", "SEND_CAP_EXCEEDED", "upload", "successful_submissions exceeded the <=2 cap.")
            break
        except StopRun:
            raise
        except AttachmentUploadError as exc:
            last_error = ask_error_summary(exc)
            upload["no_attachment_upload_error"] = False
            upload.setdefault("errors", []).append({"attempt": attempt, "error": last_error})
            emit("upload_attachment_error", attempt=attempt, error=last_error, sends=session.send_budget.successful_submissions)
        except HumanActionNeededError:
            raise
        except AskChatGPTError as exc:
            partial = getattr(exc, "partial", None)
            partial_meta = turn_meta(partial) if isinstance(partial, TurnRecord) else None
            if isinstance(partial, TurnRecord):
                guard_not_target(results, "upload", conversation_id=partial.conversation_id, url=partial.conversation_url)
            last_error = {**ask_error_summary(exc), "partial": partial_meta}
            upload.setdefault("errors", []).append({"attempt": attempt, "error": last_error})
            emit("upload_ask_error", attempt=attempt, error=last_error, sends=session.send_budget.successful_submissions)
        except Exception as exc:  # noqa: BLE001
            last_error = {"type": type(exc).__name__}
            upload.setdefault("errors", []).append({"attempt": attempt, "error": last_error})
            emit("upload_driver_error", attempt=attempt, error=last_error, sends=session.send_budget.successful_submissions)

        if session.send_budget.successful_submissions > THIS_RUN_SEND_CAP:
            raise_stop(results, "BLOCKED", "SEND_CAP_EXCEEDED", "upload", "successful_submissions exceeded the <=2 cap.")
        close_owned_tabs(session, results, "upload_retry")
        if attempt >= 2:
            break
        if session.send_budget.successful_submissions >= THIS_RUN_SEND_CAP:
            break
        emit("upload_retry_allowed", next_attempt=attempt + 1, sends=session.send_budget.successful_submissions)

    final_after = session.send_budget.successful_submissions
    upload["send_count_delta"] = final_after - int(results["send_counts"].get("before_upload", 0))
    upload["send_count_after"] = final_after
    results["send_counts"]["upload"] = final_after - int(results["send_counts"].get("before_upload", 0))
    if rec is None:
        upload["error"] = last_error
        append_blocker(results, "UPLOAD_SMOKE_FAILED", "upload", "Upload smoke did not produce a captured assistant turn within the allowed attempts/send cap.")
        return

    guard_not_target(results, "upload", conversation_id=rec.conversation_id, url=rec.conversation_url)
    results["created_conversations"].append({"conversation_id": rec.conversation_id, "conversation_url": rec.conversation_url})
    upload["conversation"] = {"conversation_id": rec.conversation_id, "conversation_url": rec.conversation_url}
    upload["conversation_id_not_target"] = not is_target_conversation_id(rec.conversation_id)
    upload["conversation_url_has_id"] = conversation_url_has_id(rec.conversation_url, rec.conversation_id)
    upload["assistant"] = turn_meta(rec)
    upload["assistant_checks"] = {
        "role_is_assistant": rec.role == "assistant",
        "status_complete": rec.status == "complete",
        "partial_false": rec.partial is False,
        "content_nonempty": len(rec.content_markdown) > 0,
        "capture_source": rec.capture_source,
        "fidelity": rec.fidelity,
    }

    hist = session.history(rec.conversation_id)
    upload["transcript"] = transcript_meta(hist)
    history_evidence = attachment_evidence_from_history(hist, rec, UPLOAD_PATH)
    raw_path = Path(hist.raw_mapping_path) if hist.raw_mapping_path else None
    raw_evidence = attachment_evidence_from_raw_mapping(raw_path, rec, UPLOAD_PATH)
    backend_has = bool(history_evidence.get("user_turn_has_attachment") or raw_evidence.get("user_turn_has_attachment"))
    name_match = bool(history_evidence.get("name_matches_m9_upload") or raw_evidence.get("name_matches_m9_upload"))
    size_match = bool(history_evidence.get("size_matches") or raw_evidence.get("size_matches"))
    upload["attachment_evidence"] = {
        "chip_appeared_no_attachment_upload_error": upload.get("no_attachment_upload_error") is True,
        "history": history_evidence,
        "raw_mapping": raw_evidence,
        "backend_user_turn_has_attachment": backend_has,
        "backend_name_matches_m9_upload": name_match,
        "backend_size_matches": size_match,
        "chip_only_fallback_used": not backend_has,
    }
    emit(
        "upload_complete",
        sends=final_after,
        conversation=upload["conversation"],
        attachment=upload["attachment_evidence"],
        assistant=upload["assistant_checks"],
    )


def initial_results() -> dict[str, Any]:
    git_start = git_checks()
    return {
        "status": "PARTIAL",
        "preflight": {},
        "post_detach_preflight": {},
        "send_counts": {
            "family": 0,
            "dr": 0,
            "upload": 0,
            "before_upload": 0,
            "final": 0,
            "this_run_cap": THIS_RUN_SEND_CAP,
        },
        "created_conversations": [],
        "family": {
            "initial": None,
            "initial_expected_pro_extended": None,
            "select_model": None,
            "select_model_error": None,
            "sustained_target": None,
            "restore": {"attempted": False, "requested": None, "reflected": None, "verified": None, "error": None},
            "restore_confirmation": None,
            "send_count_delta": 0,
            "send_count_after": None,
            "zero_sends": None,
        },
        "dr": {
            "initial_menu": None,
            "present": None,
            "set_tools": None,
            "set_tools_error": None,
            "after_attempt_state": None,
            "active_tool_chip_present": None,
            "verified_via_active_tool_chip": None,
            "diagnostic_captured": False,
            "clear": None,
            "cleared": None,
            "recommendation": None,
            "send_count_delta": 0,
            "send_count_after": None,
            "zero_sends": None,
        },
        "upload": {
            "throwaway_file": None,
            "file_content_logged": False,
            "precheck_initial": None,
            "precheck_after_reload": None,
            "attempts": 0,
            "send_budget_before_attempt": None,
            "send_budget_after_success": None,
            "send_count_delta_success": None,
            "send_count_delta": 0,
            "send_count_after": None,
            "conversation": None,
            "conversation_id_not_target": None,
            "conversation_url_has_id": None,
            "no_attachment_upload_error": None,
            "attachment_evidence": None,
            "assistant": None,
            "assistant_checks": None,
            "transcript": None,
            "error": None,
            "errors": [],
        },
        "confirmations": {
            "own_tab_only_via_session_tabpool": True,
            "no_json_list_or_page_enumeration_in_driver": True,
            "browser_not_quit_session_detach_only": False,
            "post_detach_version_ok": False,
            "send_cap_this_run_leq_2": None,
            "fresh_throwaway_only": True,
            "target_6a316aa8_not_touched": True,
            "foreign_tabs_untouched": True,
            "no_auth_oai_cookie_bearer_values_logged": True,
            "no_conversation_content_printed_or_reported": True,
            "no_deep_research_run": True,
            "no_send_while_tool_armed": None,
            "branch_rewrite_v2": git_start.get("branch_ok_rewrite_v2"),
            "cache_not_staged": None,
            "controller_mjs_and_human_unstaged": None,
            "stable_unmoved_by_this_script": None,
        },
        "blockers": [],
        "signals": [],
        "git_start": git_start,
        "git_end": None,
    }


def update_final_status(results: dict[str, Any]) -> None:
    if results.get("status") in {"BLOCKED", "HUMAN-ACTION-NEEDED", "CDP_UNREACHABLE"}:
        return
    upload = results.get("upload") or {}
    family = results.get("family") or {}
    dr = results.get("dr") or {}
    conf = results.get("confirmations") or {}
    assistant_checks = upload.get("assistant_checks") or {}
    attachment = upload.get("attachment_evidence") or {}
    upload_ok = bool(
        upload.get("no_attachment_upload_error") is True
        and upload.get("conversation_id_not_target") is True
        and assistant_checks.get("role_is_assistant") is True
        and assistant_checks.get("status_complete") is True
        and assistant_checks.get("content_nonempty") is True
        and attachment.get("chip_appeared_no_attachment_upload_error") is True
    )
    family_attempted = bool(
        family.get("zero_sends") is True
        and family.get("initial")
        and (family.get("select_model") or family.get("select_model_error"))
    )
    dr_done = bool(
        dr.get("zero_sends") is True
        and dr.get("diagnostic_captured") is True
        and dr.get("cleared") is True
        and dr.get("recommendation")
    )
    safety_ok = bool(
        conf.get("send_cap_this_run_leq_2") is True
        and conf.get("target_6a316aa8_not_touched") is True
        and conf.get("post_detach_version_ok") is True
        and conf.get("no_send_while_tool_armed") is not False
    )
    results["status"] = "DONE" if upload_ok and family_attempted and dr_done and safety_ok else "PARTIAL"


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = results.get("status")
    preflight = results.get("preflight") or {}
    post = results.get("post_detach_preflight") or {}
    sends = results.get("send_counts") or {}
    family = results.get("family") or {}
    dr = results.get("dr") or {}
    upload = results.get("upload") or {}
    conf = results.get("confirmations") or {}
    git_start = results.get("git_start") or {}
    git_end = results.get("git_end") or {}
    forbidden_endpoint = "/json" + "/list"

    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M9-W6 reverify report")
    lines.append("")
    lines.append("## CDP")
    lines.append("- Endpoint used: `/json/version` only.")
    lines.append(f"- Preflight ok/error: `{preflight.get('ok')}` / `{preflight.get('error_code') or preflight.get('error')}`")
    lines.append(f"- Browser preflight: `{preflight.get('browser')}`; Protocol-Version: `{preflight.get('protocol_version')}`; websocket present: `{preflight.get('websocket_url_present')}`")
    lines.append(f"- Browser post-detach alive: `{conf.get('post_detach_version_ok')}`; browser: `{post.get('browser')}`")
    lines.append("")
    lines.append("## Sends")
    lines.append(f"- Family sends: `{sends.get('family')}`")
    lines.append(f"- DR sends: `{sends.get('dr')}`")
    lines.append(f"- Upload sends: `{sends.get('upload')}`")
    lines.append(f"- Final `send_budget.successful_submissions`: `{sends.get('final')}` / cap `{sends.get('this_run_cap')}`")
    lines.append(f"- Cap respected (`<=2`): `{conf.get('send_cap_this_run_leq_2')}`")
    lines.append("")
    lines.append("## C — Deep Research diagnostic (NO send; never run)")
    lines.append(f"- Deep Research present in tools menu: `{dr.get('present')}`")
    lines.append(f"- Initial menu state: `{json.dumps(_scrub(dr.get('initial_menu')), sort_keys=True)}`")
    lines.append(f"- `set_tools([Deep research])`: `{json.dumps(_scrub(dr.get('set_tools')), sort_keys=True)}`")
    lines.append(f"- `set_tools` typed fail-closed error: `{json.dumps(_scrub(dr.get('set_tools_error')), sort_keys=True)}`")
    lines.append(f"- Active-tool-chip present after set: `{dr.get('active_tool_chip_present')}`; verified via chip: `{dr.get('verified_via_active_tool_chip')}`")
    lines.append(f"- After-attempt authoritative-signal diagnostic: `{json.dumps(_scrub(dr.get('after_attempt_state')), sort_keys=True)}`")
    lines.append(f"- Clear outcome: `{json.dumps(_scrub(dr.get('clear')), sort_keys=True)}`")
    lines.append(f"- Cleared before upload: `{dr.get('cleared')}`")
    lines.append(f"- Recommendation: `{dr.get('recommendation')}`")
    lines.append(f"- Zero sends: `{dr.get('zero_sends')}`; send delta: `{dr.get('send_count_delta')}`")
    lines.append("")
    lines.append("## B — GPT-5.5 family re-verify (NO send)")
    initial = family.get("initial") or {}
    lines.append(f"- Initial label: `{initial.get('label')}`; sustained ~12s: `{initial.get('ok')}`; expected `Pro Extended`: `{family.get('initial_expected_pro_extended')}`")
    lines.append(f"- `select_model(\"GPT-5.4\")`: `{json.dumps(_scrub(family.get('select_model')), sort_keys=True)}`")
    lines.append(f"- `select_model` typed fail-closed error: `{json.dumps(_scrub(family.get('select_model_error')), sort_keys=True)}`")
    lines.append(f"- Independent ~12s target confirmation: `{json.dumps(_scrub(family.get('sustained_target')), sort_keys=True)}`")
    lines.append(f"- Restore original: `{json.dumps(_scrub(family.get('restore')), sort_keys=True)}`")
    lines.append(f"- Restore confirmation: `{json.dumps(_scrub(family.get('restore_confirmation')), sort_keys=True)}`")
    lines.append(f"- Zero sends: `{family.get('zero_sends')}`; send delta: `{family.get('send_count_delta')}`")
    lines.append("")
    lines.append("## A — Upload smoke")
    conv = upload.get("conversation") or {}
    assistant = upload.get("assistant_checks") or {}
    attachment = upload.get("attachment_evidence") or {}
    lines.append(f"- Attempts: `{upload.get('attempts')}`")
    lines.append(f"- Upload send delta on successful attempt: `{upload.get('send_count_delta_success')}`; upload leg sends recorded: `{sends.get('upload')}`")
    lines.append(f"- Throwaway conversation: `{conv.get('conversation_id')}` — `{conv.get('conversation_url')}`")
    lines.append(f"- Conversation id/url target-safe: `{upload.get('conversation_id_not_target')}` / `{upload.get('conversation_url_has_id')}`")
    lines.append(f"- No `AttachmentUploadError` (composer chip appeared): `{upload.get('no_attachment_upload_error')}`")
    lines.append(f"- User-turn attachment evidence: `{json.dumps(_scrub(attachment), sort_keys=True)}`")
    lines.append(f"- Assistant captured: role assistant `{assistant.get('role_is_assistant')}`, status complete `{assistant.get('status_complete')}`, content_nonempty `{assistant.get('content_nonempty')}`, capture_source `{assistant.get('capture_source')}`, fidelity `{assistant.get('fidelity')}`")
    lines.append(f"- Transcript metadata: `{json.dumps(_scrub(upload.get('transcript')), sort_keys=True)}`")
    lines.append(f"- Upload errors: `{json.dumps(_scrub(upload.get('errors')), sort_keys=True)}`")
    lines.append("")
    lines.append("## Safety")
    lines.append(f"- Own-tab-only via Session/TabPool: `{conf.get('own_tab_only_via_session_tabpool')}`")
    lines.append(f"- No `{forbidden_endpoint}` and no page enumeration in driver: `{conf.get('no_json_list_or_page_enumeration_in_driver')}`")
    lines.append(f"- Fresh throwaway chats only: `{conf.get('fresh_throwaway_only')}`")
    lines.append(f"- Protected `6a316aa8` / foreign tabs untouched: `{conf.get('target_6a316aa8_not_touched')}` / `{conf.get('foreign_tabs_untouched')}`")
    lines.append(f"- Browser not quit; Session.detach only: `{conf.get('browser_not_quit_session_detach_only')}`")
    lines.append(f"- Never ran Deep Research: `{conf.get('no_deep_research_run')}`")
    lines.append(f"- No send while tool/DR armed: `{conf.get('no_send_while_tool_armed')}`")
    lines.append(f"- No auth/OAI/cookie/bearer values logged: `{conf.get('no_auth_oai_cookie_bearer_values_logged')}`")
    lines.append(f"- No conversation content printed/reported: `{conf.get('no_conversation_content_printed_or_reported')}`")
    lines.append(f"- Branch start/end: `{git_start.get('branch')}` / `{git_end.get('branch')}`; HEAD start/end: `{git_start.get('head_short')}` / `{git_end.get('head_short')}`")
    lines.append(f"- `cache/` not staged: `{conf.get('cache_not_staged')}`; protected paths unstaged: `{conf.get('controller_mjs_and_human_unstaged')}`")
    lines.append(f"- Stable rev start/end same: `{conf.get('stable_unmoved_by_this_script')}`")
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
        lines.append("- None.")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("- `scripts/m9_w6_reverify.py`")
    lines.append("- `team/evidence/reports/M9-W6-reverify.txt`")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


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
            raise_stop(results, "CDP_UNREACHABLE", "CDP_UNREACHABLE", "preflight", "Expose Chrome CDP on 127.0.0.1:9222 and rerun; no attach/send attempted.")
        git_start = results.get("git_start") or {}
        if not git_start.get("branch_ok_rewrite_v2"):
            raise_stop(results, "BLOCKED", "WRONG_BRANCH", "preflight", "Switch to branch rewrite-v2 before running live verification.")
        if not git_start.get("stable_ok"):
            raise_stop(results, "BLOCKED", "STABLE_REF_UNAVAILABLE", "preflight", "Restore/verify the stable ref before running live verification.")
        if git_start.get("cache_staged") or git_start.get("protected_paths_staged"):
            raise_stop(results, "BLOCKED", "PROTECTED_PATHS_STAGED", "preflight", "Unstage cache/, controller.mjs, and human/ before running live verification.")

        phase = "attach"
        session = Session(channel="cdp", data_dir=DATA_DIR)
        session.attach()
        emit("attached", data_dir=str(DATA_DIR))

        phase = "dr"
        run_dr(session, results)
        emit("dr_done", zero_sends=results["dr"].get("zero_sends"), cleared=results["dr"].get("cleared"), sends=session.send_budget.successful_submissions)

        phase = "family"
        run_family(session, results)
        emit("family_done", zero_sends=results["family"].get("zero_sends"), sends=session.send_budget.successful_submissions)

        phase = "upload"
        results["send_counts"]["before_upload"] = session.send_budget.successful_submissions
        if session.send_budget.successful_submissions >= THIS_RUN_SEND_CAP:
            raise_stop(results, "BLOCKED", "SEND_CAP_EXHAUSTED_BEFORE_UPLOAD", "upload", "No send budget remained for upload smoke.")
        run_upload(session, results)
        emit("upload_done", sends=session.send_budget.successful_submissions, success=results["upload"].get("conversation") is not None)
    except StopRun as stop:
        results["status"] = stop.status
        results["signals"].append(f"Stopped at {stop.leg}: {stop.code}.")
        emit("stopped", status=stop.status, leg=stop.leg, code=stop.code)
    except HumanActionNeededError as exc:
        results["status"] = "HUMAN-ACTION-NEEDED"
        append_blocker(results, "HUMAN-ACTION-NEEDED", phase, "Operator must clear login/Cloudflare/human action; no retries or stealth attempted.")
        error = ask_error_summary(exc)
        if phase == "family":
            results["family"]["select_model_error"] = error
        elif phase == "dr":
            results["dr"]["set_tools_error"] = error
        elif phase == "upload":
            results["upload"]["error"] = error
        emit("human_action_needed", phase=phase, error=error)
    except AskChatGPTError as exc:
        results["status"] = "PARTIAL" if session is not None and session.send_budget.successful_submissions > 0 else "BLOCKED"
        partial = getattr(exc, "partial", None)
        partial_meta = turn_meta(partial) if isinstance(partial, TurnRecord) else None
        error = {**ask_error_summary(exc), "partial": partial_meta}
        if phase == "family":
            results["family"]["select_model_error"] = error
        elif phase == "dr":
            results["dr"]["set_tools_error"] = error
        elif phase == "upload":
            results["upload"]["error"] = error
        append_blocker(results, getattr(exc, "code", type(exc).__name__), phase, "Inspect safe error metadata and gitignored cache; respect remaining live-send budget.")
        emit("ask_chatgpt_error", phase=phase, error=error)
    except Exception as exc:  # noqa: BLE001
        results["status"] = "PARTIAL" if session is not None and session.send_budget.successful_submissions > 0 else "BLOCKED"
        append_blocker(results, type(exc).__name__, phase, "Fix the driver/source issue; respect remaining live-send budget before rerun.")
        emit("driver_error", phase=phase, error={"type": type(exc).__name__})
    finally:
        if session is not None:
            final_count = session.send_budget.successful_submissions
            results["send_counts"]["final"] = final_count
            upload_state = results.get("upload") or {}
            precheck_final = upload_state.get("precheck_after_reload") or upload_state.get("precheck_initial") or {}
            results["confirmations"]["no_send_while_tool_armed"] = not bool(precheck_final.get("any_tool_armed")) if isinstance(precheck_final, dict) else True
            try:
                session.detach()
                results["confirmations"]["browser_not_quit_session_detach_only"] = True
            except Exception as exc:  # noqa: BLE001
                results["confirmations"]["browser_not_quit_session_detach_only"] = False
                append_blocker(results, "DETACH_FAILED", "teardown", f"Session.detach raised {type(exc).__name__}; inspect own managed tabs only.")
                emit("detach_error", error={"type": type(exc).__name__})
        else:
            results["send_counts"]["final"] = 0
            results["confirmations"]["no_send_while_tool_armed"] = True
        post = preflight_version()
        results["post_detach_preflight"] = post
        results["confirmations"]["post_detach_version_ok"] = post.get("ok") is True
        final_count = int(results["send_counts"].get("final") or 0)
        results["confirmations"]["send_cap_this_run_leq_2"] = final_count <= THIS_RUN_SEND_CAP
        results["git_end"] = git_checks()
        git_end = results.get("git_end") or {}
        results["confirmations"]["cache_not_staged"] = not bool(git_end.get("cache_staged"))
        results["confirmations"]["controller_mjs_and_human_unstaged"] = not bool(git_end.get("protected_paths_staged"))
        stable_end = git_end.get("stable_rev")
        if stable_start and stable_end:
            results["confirmations"]["stable_unmoved_by_this_script"] = stable_start == stable_end
        update_final_status(results)
        write_report(results)
        emit("report_written", status=results["status"], report=str(REPORT_PATH), final_send_count=final_count)
    return 0 if results["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
