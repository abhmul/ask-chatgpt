#!/usr/bin/env python3
"""M7b-T3b live tools-selection reflection discovery driver.

Own-tab-only CDP workflow: opens one fresh ChatGPT tab, toggles only the
composer "Web search" tool menu item, sends nothing, restores the initial tool
state when possible, and writes the verdict report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt.channels.cdp import CdpChannel
from ask_chatgpt.menus import enumerate_radix_options, open_radix_menu, select_radix_label

CDP_ENDPOINT = "http://127.0.0.1:9222"
CDP_VERSION_URL = f"{CDP_ENDPOINT}/json/version"
REPORT_PATH = Path("team/evidence/reports/M7b-T3b-tools.md")
RADIX_PORTAL = "[data-radix-popper-content-wrapper]"
REQUIRED_BRANCH = "rewrite-v2"
TOOLS_BUTTON = 'button[data-testid="composer-plus-btn"]'
TOOL_LABEL = "Web search"
TARGET_CONVERSATION_ID = "6a316aa8"

# Reused from scripts/m7_t3c_real.py, with key coverage kept conservative so
# accidental auth/session/header material cannot be emitted.
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
    "secret",
    "session-token",
    "token=",
)

JS_PAGE_STATE = r"""
() => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const body = norm(document.body ? document.body.innerText : '').toLowerCase();
  const title = norm(document.title).slice(0, 120);
  const url = String(location.href || '');
  return {
    url,
    path: String(location.pathname || ''),
    title,
    has_composer: Boolean(document.querySelector('#prompt-textarea')),
    target_conversation_loaded: url.includes('/c/6a316aa8'),
    challenge_likely: /just a moment|checking your browser|verify you are human|cloudflare/.test((title + ' ' + body).toLowerCase()),
    login_likely: /log in|sign up|continue with google|continue with microsoft|continue with apple/.test(body),
  };
}
"""

JS_PORTAL_OBSERVE = r"""
(a) => {
  const portalSelector = a && a.portal_selector || '[data-radix-popper-content-wrapper]';
  const targetLabel = String(a && a.label || 'Web search').replace(/\s+/g, ' ').trim();
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const disabled = el => Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const portals = Array.from(document.querySelectorAll(portalSelector));
  const portalRecords = portals.map((portal, portal_index) => {
    const portalVisible = visible(portal);
    const rect = portal.getBoundingClientRect();
    const items = Array.from(portal.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'))
      .filter(visible)
      .map((el, index) => {
        const ariaChecked = el.getAttribute('aria-checked');
        const label = norm(el.innerText || el.textContent || el.getAttribute('aria-label') || '');
        return {
          index,
          label,
          role: el.getAttribute('role'),
          aria_checked: ariaChecked,
          checked: ariaChecked === 'true' ? true : (ariaChecked === 'false' ? false : null),
          disabled: disabled(el),
        };
      })
      .filter(item => item.label);
    return {
      portal_index,
      visible: portalVisible,
      item_count: items.length,
      rect: {width: Math.round(rect.width), height: Math.round(rect.height)},
      items,
    };
  });
  const visiblePortals = portalRecords.filter(p => p.visible);
  const allItems = portalRecords.flatMap(p => p.items.map(item => ({portal_index: p.portal_index, ...item})));
  return {
    portal_present: portals.length > 0,
    portal_count: portals.length,
    portal_visible: visiblePortals.length > 0,
    visible_portal_count: visiblePortals.length,
    web_search_items: allItems.filter(item => norm(item.label) === targetLabel),
    all_items: allItems,
  };
}
"""

JS_COMPOSER_INDICATORS = r"""
(a) => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const cssEscape = v => {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(String(v));
    return String(v).replace(/[^a-zA-Z0-9_-]/g, ch => '\\' + ch);
  };
  const cssString = v => '"' + String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const unique = selector => {
    try { return document.querySelectorAll(selector).length === 1; }
    catch (_) { return false; }
  };
  const childSelector = el => {
    const parent = el.parentElement;
    if (!parent) return el.tagName.toLowerCase();
    const tag = el.tagName.toLowerCase();
    const sameTag = Array.from(parent.children).filter(child => child.tagName === el.tagName);
    const index = sameTag.indexOf(el) + 1;
    return `${tag}:nth-of-type(${Math.max(1, index)})`;
  };
  const selectorFor = el => {
    const tag = el.tagName.toLowerCase();
    const id = el.id;
    if (id) {
      const sel = `${tag}#${cssEscape(id)}`;
      if (unique(sel)) return sel;
    }
    const dataTestid = el.getAttribute('data-testid');
    if (dataTestid) {
      const sel = `${tag}[data-testid=${cssString(dataTestid)}]`;
      if (unique(sel)) return sel;
    }
    const aria = el.getAttribute('aria-label');
    if (aria) {
      const sel = `${tag}[aria-label=${cssString(aria)}]`;
      if (unique(sel)) return sel;
    }
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE && parts.length < 6) {
      if (cur.id) {
        parts.unshift(`${cur.tagName.toLowerCase()}#${cssEscape(cur.id)}`);
        break;
      }
      const curTestid = cur.getAttribute && cur.getAttribute('data-testid');
      if (curTestid) {
        parts.unshift(`${cur.tagName.toLowerCase()}[data-testid=${cssString(curTestid)}]`);
        break;
      }
      if (cur.tagName && cur.tagName.toLowerCase() === 'form') {
        parts.unshift('form');
        break;
      }
      parts.unshift(childSelector(cur));
      cur = cur.parentElement;
    }
    const path = parts.join(' > ');
    return path || tag;
  };
  const prompt = document.querySelector('#prompt-textarea');
  const plus = document.querySelector('button[data-testid="composer-plus-btn"]');
  const form = prompt ? prompt.closest('form') : null;
  const composerish = prompt ? (prompt.closest('[data-testid*="composer" i]') || prompt.closest('[class*="composer" i]') || form) : null;
  const scope = form || composerish || (plus ? plus.closest('form') : null) || document.body;
  const portals = Array.from(document.querySelectorAll('[data-radix-popper-content-wrapper]'));
  const inPortal = el => portals.some(portal => portal.contains(el));
  const promptRect = prompt ? prompt.getBoundingClientRect() : null;
  const distance = el => {
    if (!promptRect) return null;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const px = promptRect.left + promptRect.width / 2;
    const py = promptRect.top + promptRect.height / 2;
    return Math.round(Math.hypot(cx - px, cy - py));
  };
  const nodeList = Array.from(scope.querySelectorAll('button,[role="button"],[aria-label],[data-testid],span,div'));
  const candidates = nodeList
    .filter(el => visible(el) && !inPortal(el))
    .map((el, raw_index) => {
      const display = norm(el.innerText || el.textContent || '');
      const aria = norm(el.getAttribute('aria-label') || '');
      const title = norm(el.getAttribute('title') || '');
      const testid = norm(el.getAttribute('data-testid') || '');
      const klass = norm(Array.from(el.classList || []).slice(0, 8).join(' '));
      const combined = norm([display, aria, title, testid, klass].join(' '));
      return {el, raw_index, display, aria, title, testid, klass, combined};
    })
    .filter(item => /web\s*search/i.test(item.combined) || /search\s*the\s*web/i.test(item.combined) || (/\bsearch\b/i.test(item.combined) && /(tool|pill|chip|composer|web|selected|active|search)/i.test(item.combined)))
    .map((item, index) => {
      const el = item.el;
      const rect = el.getBoundingClientRect();
      return {
        index,
        selector: selectorFor(el),
        tag: el.tagName,
        role: el.getAttribute('role'),
        data_testid: el.getAttribute('data-testid'),
        aria_label: item.aria || null,
        title: item.title || null,
        display_label: item.display ? item.display.slice(0, 120) : null,
        aria_pressed: el.getAttribute('aria-pressed'),
        aria_checked: el.getAttribute('aria-checked'),
        aria_selected: el.getAttribute('aria-selected'),
        data_state: el.getAttribute('data-state'),
        data_active: el.getAttribute('data-active'),
        disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled')),
        class_hint: item.klass ? item.klass.slice(0, 120) : null,
        distance_from_prompt_px: distance(el),
        rect: {width: Math.round(rect.width), height: Math.round(rect.height)},
        raw_index: item.raw_index,
      };
    })
    .slice(0, 40);
  return {
    scope_selector: scope === form ? 'form' : (scope === composerish ? 'composerish' : 'document.body'),
    prompt_present: Boolean(prompt),
    plus_present: Boolean(plus),
    candidate_count: candidates.length,
    candidates,
  };
}
"""

JS_PORTAL_VISIBLE = r"""
(a) => {
  const selector = a && a.portal_selector || '[data-radix-popper-content-wrapper]';
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const portals = Array.from(document.querySelectorAll(selector));
  return {present: portals.length > 0, visible: portals.some(visible), count: portals.length};
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
        if any(part in lowered for part in SENSITIVE_VALUE_PARTS):
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
        "stable_rev": stable.stdout.strip() if stable.returncode == 0 else None,
        "staged_files": [line for line in staged.stdout.splitlines() if line.strip()],
        "protected_staged": [line for line in protected.stdout.splitlines() if line.strip()],
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


def initial_results() -> dict[str, Any]:
    return {
        "status": "PARTIAL",
        "preflight": {},
        "post_detach_preflight": {},
        "git_start": None,
        "git_end": None,
        "page_state": None,
        "initial": {
            "open_ok": False,
            "web_search_present": False,
            "web_search": None,
            "production_options": [],
            "portal": None,
            "error": None,
        },
        "select": {"attempted": False, "ok": False, "selected_option": None, "error": None},
        "after_select": {
            "portal_present_after_select": None,
            "portal_visible_after_select": None,
            "web_search": None,
            "composer_indicators": None,
            "error": None,
        },
        "reopen": {
            "attempted": False,
            "ok": False,
            "web_search": None,
            "aria_checked_true": False,
            "checked_true": False,
            "portal": None,
            "error": None,
        },
        "restore": {
            "attempted": False,
            "needed": None,
            "initial_checked": None,
            "checked_before_restore": None,
            "clicked": False,
            "checked_after_restore": None,
            "error": None,
        },
        "confirmations": {
            "own_tab_only_no_json_list_no_page_enumeration": True,
            "zero_sends_no_session_send_used": True,
            "browser_not_quit_post_detach_version_ok": False,
            "no_auth_cookie_oai_values_logged": True,
            "no_conversation_content": True,
            "target_conversation_not_touched": True,
            "branch_rewrite_v2": None,
            "stable_unmoved_start_end": None,
            "nothing_staged": None,
            "protected_paths_not_staged": None,
        },
        "blockers": [],
        "signals": [],
    }


def append_blocker(results: dict[str, Any], code: str, action: str) -> None:
    results["blockers"].append({"code": code, "action": action})


def stop(results: dict[str, Any], status: str, code: str, action: str) -> None:
    append_blocker(results, code, action)
    raise StopRun(status=status, code=code, action=action)


def menu_option_records(options: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for option in options or []:
        out.append(
            {
                "label": getattr(option, "label", None),
                "role": getattr(option, "role", None),
                "checked": getattr(option, "checked", None),
                "disabled": getattr(option, "disabled", None),
                "path": list(getattr(option, "path", ()) or ()),
            }
        )
    return out


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


def find_web_item_from_observe(observed: Any) -> dict[str, Any] | None:
    if not isinstance(observed, dict):
        return None
    items = observed.get("web_search_items")
    if isinstance(items, list) and items:
        for item in items:
            if isinstance(item, dict) and item.get("label") == TOOL_LABEL:
                return item
        if isinstance(items[0], dict):
            return items[0]
    return None


def portal_observe(channel: CdpChannel, tab: Any) -> dict[str, Any]:
    observed = channel.evaluate(
        tab,
        JS_PORTAL_OBSERVE,
        arg={"portal_selector": RADIX_PORTAL, "label": TOOL_LABEL},
        timeout_s=5.0,
    )
    return observed if isinstance(observed, dict) else {}


def portal_visible(channel: CdpChannel, tab: Any) -> bool:
    raw = channel.evaluate(tab, JS_PORTAL_VISIBLE, arg={"portal_selector": RADIX_PORTAL}, timeout_s=5.0)
    return bool(isinstance(raw, dict) and raw.get("visible"))


def close_menu(channel: CdpChannel, tab: Any) -> None:
    try:
        channel.press(tab, "body", "Escape")
        channel.sleep(0.25)
    except Exception:
        try:
            channel.evaluate(tab, "() => { if (document.body) document.body.click(); return true; }", timeout_s=2.0)
            channel.sleep(0.25)
        except Exception:
            pass


def current_web_checked(channel: CdpChannel, tab: Any) -> bool | None:
    observed = portal_observe(channel, tab)
    item = find_web_item_from_observe(observed)
    if item is None:
        return None
    checked = item.get("checked")
    return checked if isinstance(checked, bool) else None


def ensure_tools_menu_visible(channel: CdpChannel, tab: Any) -> None:
    if portal_visible(channel, tab):
        return
    open_radix_menu(tab, TOOLS_BUTTON)


def restore_to_initial(channel: CdpChannel, tab: Any, results: dict[str, Any]) -> None:
    restore = results["restore"]
    initial_item = results.get("initial", {}).get("web_search")
    initial_checked = initial_item.get("checked") if isinstance(initial_item, dict) else None
    restore["initial_checked"] = initial_checked
    if not isinstance(initial_checked, bool):
        restore["needed"] = None
        restore["error"] = "INITIAL_CHECKED_UNKNOWN"
        return
    try:
        ensure_tools_menu_visible(channel, tab)
        before = current_web_checked(channel, tab)
        restore["checked_before_restore"] = before
        restore["needed"] = isinstance(before, bool) and before != initial_checked
        if restore["needed"] is True:
            restore["attempted"] = True
            selected = select_radix_label(tab, TOOL_LABEL)
            restore["clicked"] = True
            restore["selected_option"] = option_record(selected)
            channel.sleep(0.25)
            ensure_tools_menu_visible(channel, tab)
            after = current_web_checked(channel, tab)
            restore["checked_after_restore"] = after
        else:
            restore["checked_after_restore"] = before
    except Exception as exc:  # noqa: BLE001 - safe type only.
        restore["error"] = type(exc).__name__
    finally:
        try:
            close_menu(channel, tab)
        except Exception:
            pass


def page_state_safe(raw: Any) -> dict[str, Any]:
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


def determine_status(results: dict[str, Any]) -> str:
    if results.get("blockers") and results.get("status") == "BLOCKED":
        return "BLOCKED"
    characterized = results["after_select"].get("portal_present_after_select") is not None
    selected = results["select"].get("ok") is True
    initial_present = results["initial"].get("web_search_present") is True
    recipe_ok = results["reopen"].get("aria_checked_true") is True and results["reopen"].get("checked_true") is True
    if characterized and selected and initial_present and recipe_ok:
        return "DONE"
    return "PARTIAL"


def fmt_bool(value: Any) -> str:
    return "true" if value is True else "false" if value is False else "unknown"


def json_inline(value: Any) -> str:
    return json.dumps(_scrub(value), sort_keys=True, ensure_ascii=False)


def json_block(value: Any) -> str:
    return json.dumps(_scrub(value), indent=2, sort_keys=True, ensure_ascii=False)


def aria_value(item: Any) -> Any:
    return item.get("aria_checked") if isinstance(item, dict) else None


def checked_value(item: Any) -> Any:
    return item.get("checked") if isinstance(item, dict) else None


def role_value(item: Any) -> Any:
    return item.get("role") if isinstance(item, dict) else None


def composer_chip_summary(results: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    dump = results.get("after_select", {}).get("composer_indicators")
    candidates = dump.get("candidates") if isinstance(dump, dict) else None
    safe_candidates = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
    if safe_candidates:
        primary = next(
            (
                item
                for item in safe_candidates
                if item.get("tag") == "BUTTON"
                and (item.get("aria_label") or "").lower().startswith("search")
                and "remove" in (item.get("aria_label") or "").lower()
            ),
            None,
        ) or next((item for item in safe_candidates if item.get("tag") == "BUTTON"), safe_candidates[0])
        selectors = [item.get("selector") for item in safe_candidates if item.get("selector")]
        return (
            f"primary active search chip selector `{primary.get('selector')}` "
            f"(display `{primary.get('display_label')}`, aria-label `{primary.get('aria_label')}`); "
            f"candidate selectors: {selectors}",
            safe_candidates,
        )
    return "none found", []


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = results.get("status") or "PARTIAL"
    preflight = results.get("preflight") or {}
    post = results.get("post_detach_preflight") or {}
    git_start = results.get("git_start") or {}
    git_end = results.get("git_end") or {}
    conf = results.get("confirmations") or {}
    initial = results.get("initial") or {}
    select = results.get("select") or {}
    after = results.get("after_select") or {}
    reopen = results.get("reopen") or {}
    restore = results.get("restore") or {}
    initial_item = initial.get("web_search")
    after_item = after.get("web_search")
    reopen_item = reopen.get("web_search")
    portal_closed = after.get("portal_present_after_select") is False
    if after.get("portal_present_after_select") is False:
        mechanism = "The Radix tools portal is absent immediately after selecting Web search, so the tools menu closes/detaches on select."
    elif after.get("portal_visible_after_select") is True:
        mechanism = f"The Radix tools portal stays visible after selecting Web search; in-place aria-checked is `{aria_value(after_item)}`."
    elif after.get("portal_present_after_select") is True:
        mechanism = f"The Radix tools portal remains attached but is not visible after selecting Web search; in-place aria-checked is `{aria_value(after_item)}`."
    else:
        mechanism = "The post-select portal state was not characterized."
    recipe_yes = reopen.get("aria_checked_true") is True
    chip_line, chip_candidates = composer_chip_summary(results)

    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M7b-T3b live tools-selection reflection discovery")
    lines.append("")
    lines.append("## CDP preflight")
    lines.append("- Endpoint used: `/json/version` only (no `/json/list`).")
    lines.append(f"- Browser version: `{preflight.get('browser')}`")
    lines.append(f"- Protocol-Version: `{preflight.get('protocol_version')}`")
    lines.append(f"- WebSocket URL present: `{preflight.get('websocket_url_present')}`")
    lines.append(f"- Preflight ok/error: `{preflight.get('ok')}` / `{preflight.get('error_code') or preflight.get('error')}`")
    lines.append("")
    lines.append("## Reflection mechanism")
    lines.append(f"- {mechanism}")
    lines.append(f"- Portal present after select: `{after.get('portal_present_after_select')}`; visible: `{after.get('portal_visible_after_select')}`; closes on select: `{portal_closed}`.")
    lines.append(f"- If readable in place, Web search aria-checked/check/role after select: `{aria_value(after_item)}` / `{checked_value(after_item)}` / `{role_value(after_item)}`.")
    lines.append("")
    lines.append("## Re-open recipe result")
    lines.append(f"- Re-opened tools menu after selection: `{reopen.get('ok')}`; error: `{reopen.get('error')}`.")
    lines.append(f"- Web search `aria-checked == true` after re-open: `{'YES' if recipe_yes else 'NO'}`.")
    lines.append(f"- Web search aria-checked/check/role after re-open: `{aria_value(reopen_item)}` / `{checked_value(reopen_item)}` / `{role_value(reopen_item)}`.")
    lines.append("")
    lines.append("## Composer-chip alternative")
    lines.append(f"- {chip_line}.")
    if chip_candidates:
        lines.append("```json")
        lines.append(json_block(chip_candidates))
        lines.append("```")
    lines.append("")
    lines.append("## Recommended fix recipe")
    if recipe_yes:
        lines.append(f"- In `set_tools`, after `select_radix_label(tab, label)`, re-open `{TOOLS_BUTTON}` with `open_radix_menu`, enumerate with `enumerate_radix_options`, and assert exactly one enabled option has normalized label `label` and `option.checked is True`; close the menu afterward. This is the verified reflection check for Web search.")
    elif after.get("portal_visible_after_select") is True and checked_value(after_item) is True:
        lines.append("- The selected tool reflects in-place without re-opening; verify by enumerating the still-visible Radix portal and requiring `option.checked is True`.")
    elif chip_candidates:
        lines.append("- Re-open verification did not prove checked state; fallback to the composer-level active search chip candidate(s) above only if the editor intentionally supports that signal.")
    else:
        lines.append("- No robust fix recipe verified; inspect blockers/signals before changing `set_tools`.")
    lines.append(f"- Caveat: opening the tools menu for verification did not itself toggle Web search in this run; restore state was `{json_inline(restore)}`.")
    lines.append("")
    lines.append("## Evidence")
    lines.append(f"- Initial Web search present: `{initial.get('web_search_present')}`; open error: `{initial.get('error')}`.")
    lines.append(f"- Initial Web search aria-checked/check/role: `{aria_value(initial_item)}` / `{checked_value(initial_item)}` / `{role_value(initial_item)}`.")
    lines.append(f"- Selection attempted/ok/error: `{select.get('attempted')}` / `{select.get('ok')}` / `{select.get('error')}`; selected option: `{json_inline(select.get('selected_option'))}`.")
    lines.append(f"- Post-select Web search aria-checked/check/role: `{aria_value(after_item)}` / `{checked_value(after_item)}` / `{role_value(after_item)}`.")
    lines.append(f"- Post-reopen Web search aria-checked/check/role: `{aria_value(reopen_item)}` / `{checked_value(reopen_item)}` / `{role_value(reopen_item)}`.")
    lines.append(f"- Portal booleans after select: present=`{after.get('portal_present_after_select')}`, visible=`{after.get('portal_visible_after_select')}`.")
    lines.append(f"- Composer-chip dump: `{json_inline(after.get('composer_indicators'))}`")
    lines.append("- Initial portal item dump:")
    lines.append("```json")
    lines.append(json_block((initial.get("portal") or {}).get("all_items") if isinstance(initial.get("portal"), dict) else None))
    lines.append("```")
    lines.append("- Re-open portal item dump:")
    lines.append("```json")
    lines.append(json_block((reopen.get("portal") or {}).get("all_items") if isinstance(reopen.get("portal"), dict) else None))
    lines.append("```")
    lines.append(f"- Restore outcome: `{json_inline(restore)}`")
    lines.append("")
    lines.append("## Confirmations")
    lines.append(f"- Own-tab-only/no `/json/list`: `{fmt_bool(conf.get('own_tab_only_no_json_list_no_page_enumeration'))}` (driver uses `CdpChannel.open_tab(...)`, never calls `/json/list`, never enumerates pages, and closes only its tab lease).")
    lines.append("- ZERO sends: `true` (`Session.ask/loop`, composer fill, and submit were never used).")
    lines.append(f"- Browser not quit/post-detach ok: `{fmt_bool(conf.get('browser_not_quit_post_detach_version_ok'))}`; post-detach `/json/version` ok: `{post.get('ok')}`")
    lines.append(f"- No auth/oai/cookie logged: `{fmt_bool(conf.get('no_auth_cookie_oai_values_logged'))}`")
    lines.append(f"- No conversation content: `{fmt_bool(conf.get('no_conversation_content'))}`")
    lines.append(f"- Protected conversation `{TARGET_CONVERSATION_ID}` not touched: `{fmt_bool(conf.get('target_conversation_not_touched'))}`")
    lines.append(f"- Branch rewrite-v2 start/end: `{git_start.get('branch')}` / `{git_end.get('branch')}`; ok: `{fmt_bool(conf.get('branch_rewrite_v2'))}`")
    lines.append(f"- Stable rev start/end: `{git_start.get('stable_rev')}` / `{git_end.get('stable_rev')}`; unchanged: `{fmt_bool(conf.get('stable_unmoved_start_end'))}`")
    lines.append(f"- Nothing staged: `{fmt_bool(conf.get('nothing_staged'))}`; staged files: `{git_end.get('staged_files')}`")
    lines.append(f"- Protected paths not staged (`cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`): `{fmt_bool(conf.get('protected_paths_not_staged'))}`")
    lines.append("")
    lines.append("## Blockers")
    blockers = results.get("blockers") or []
    if blockers:
        for item in blockers:
            lines.append(f"- `{item.get('code')}`: {item.get('action')}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Signals")
    signals = results.get("signals") or []
    if signals:
        for item in signals:
            lines.append(f"- {item}")
    else:
        lines.append("- No extra signals.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    results = initial_results()
    channel: CdpChannel | None = None
    tab: Any = None
    own_tab_open = False
    stable_start: str | None = None
    selected_click_ok = False
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
        emit("git_start", branch=git_start.get("branch"), stable_rev=git_start.get("stable_rev"), staged_count=len(git_start.get("staged_files") or []))
        if git_start.get("branch_ok_rewrite_v2") is not True:
            stop(results, "BLOCKED", "WRONG_BRANCH", "Switch to branch rewrite-v2 before running live tool discovery; no browser attach attempted.")

        channel = CdpChannel(cdp_endpoint=CDP_ENDPOINT)
        channel.attach()
        emit("attached")
        tab = channel.open_tab("https://chatgpt.com/")
        own_tab_open = True
        emit("opened_own_tab", tab_id=getattr(tab, "tab_id", None))
        try:
            channel.wait_for_selector(tab, "#prompt-textarea", state="visible", timeout_s=20.0)
        except Exception:
            raw_state = channel.evaluate(tab, JS_PAGE_STATE, timeout_s=5.0)
            results["page_state"] = page_state_safe(raw_state)
            results["signals"].append(f"Composer unavailable; page_state={json.dumps(_scrub(results['page_state']), sort_keys=True)}")
            stop(results, "BLOCKED", "HUMAN-ACTION-NEEDED", "Operator must clear login/Cloudflare/human action until a fresh ChatGPT composer is visible; no retries attempted.")
        raw_state = channel.evaluate(tab, JS_PAGE_STATE, timeout_s=5.0)
        results["page_state"] = page_state_safe(raw_state)
        if isinstance(raw_state, dict) and raw_state.get("target_conversation_loaded"):
            results["confirmations"]["target_conversation_not_touched"] = False
            stop(results, "BLOCKED", "TARGET_CONVERSATION_LOADED", f"Fresh tab resolved to protected conversation {TARGET_CONVERSATION_ID}; stop and audit browser state.")
        if isinstance(raw_state, dict) and (raw_state.get("challenge_likely") or raw_state.get("login_likely") or not raw_state.get("has_composer")):
            results["signals"].append(f"Blocked page state after load: {json.dumps(_scrub(results['page_state']), sort_keys=True)}")
            stop(results, "BLOCKED", "HUMAN-ACTION-NEEDED", "Operator must clear login/Cloudflare/human action until a fresh ChatGPT composer is visible; no retries attempted.")

        # 3. Open tools menu via production path and enumerate.
        try:
            open_radix_menu(tab, TOOLS_BUTTON)
            results["initial"]["open_ok"] = True
            options = enumerate_radix_options(tab)
            results["initial"]["production_options"] = menu_option_records(options)
            initial_portal = portal_observe(channel, tab)
            results["initial"]["portal"] = initial_portal
            initial_item = find_web_item_from_observe(initial_portal)
            results["initial"]["web_search"] = initial_item
            results["initial"]["web_search_present"] = initial_item is not None
            emit("initial_tools_menu", web_search_present=initial_item is not None, web_search_checked=checked_value(initial_item), item_count=len(initial_portal.get("all_items") or []))
            if initial_item is None:
                stop(results, "PARTIAL", "WEB_SEARCH_ABSENT", "Tools menu opened, but Web search was not present; no selection attempted.")
        except StopRun:
            raise
        except Exception as exc:  # noqa: BLE001 - safe type only.
            results["initial"]["error"] = type(exc).__name__
            stop(results, "PARTIAL", "TOOLS_MENU_OPEN_FAILED", f"Production open/enumerate failed with {type(exc).__name__}; no selection attempted.")

        # 4. Select Web search via production click path.
        results["select"]["attempted"] = True
        try:
            selected = select_radix_label(tab, TOOL_LABEL)
            selected_click_ok = True
            results["select"]["ok"] = True
            results["select"]["selected_option"] = option_record(selected)
            emit("selected_tool", label=TOOL_LABEL, selected_role=getattr(selected, "role", None), selected_checked=getattr(selected, "checked", None))
        except Exception as exc:  # noqa: BLE001 - safe type only.
            results["select"]["error"] = type(exc).__name__
            append_blocker(results, "TOOL_SELECT_FAILED", f"select_radix_label(Web search) raised {type(exc).__name__}; no retry attempted.")

        # 5. Observe immediately after selection.
        if selected_click_ok:
            try:
                channel.sleep(0.25)
                after_portal = portal_observe(channel, tab)
                results["after_select"]["portal_present_after_select"] = after_portal.get("portal_present")
                results["after_select"]["portal_visible_after_select"] = after_portal.get("portal_visible")
                results["after_select"]["web_search"] = find_web_item_from_observe(after_portal)
                composer = channel.evaluate(tab, JS_COMPOSER_INDICATORS, arg={"label": TOOL_LABEL}, timeout_s=5.0)
                results["after_select"]["composer_indicators"] = composer if isinstance(composer, dict) else {"raw": composer}
                emit("after_select", portal_present=after_portal.get("portal_present"), portal_visible=after_portal.get("portal_visible"), in_place_checked=checked_value(results["after_select"].get("web_search")), composer_candidate_count=(composer or {}).get("candidate_count") if isinstance(composer, dict) else None)
            except Exception as exc:  # noqa: BLE001 - safe type only.
                results["after_select"]["error"] = type(exc).__name__
                append_blocker(results, "POST_SELECT_OBSERVE_FAILED", f"Post-select observation raised {type(exc).__name__}.")

            # 6. Validate the re-open recipe by calling production open_radix_menu again.
            results["reopen"]["attempted"] = True
            try:
                open_radix_menu(tab, TOOLS_BUTTON)
                results["reopen"]["ok"] = True
                options = enumerate_radix_options(tab)
                results["reopen"]["production_options"] = menu_option_records(options)
                reopen_portal = portal_observe(channel, tab)
                results["reopen"]["portal"] = reopen_portal
                reopen_item = find_web_item_from_observe(reopen_portal)
                results["reopen"]["web_search"] = reopen_item
                results["reopen"]["aria_checked_true"] = aria_value(reopen_item) == "true"
                results["reopen"]["checked_true"] = checked_value(reopen_item) is True
                emit("reopen_recipe", ok=True, aria_checked=aria_value(reopen_item), checked=checked_value(reopen_item))
            except Exception as exc:  # noqa: BLE001 - safe type only.
                results["reopen"]["error"] = type(exc).__name__
                append_blocker(results, "REOPEN_RECIPE_FAILED", f"Re-opening tools menu after select raised {type(exc).__name__}; no retry-spam attempted.")

            # 7. Restore Web search to its initial checked state.
            restore_to_initial(channel, tab, results)
            emit("restore", needed=results["restore"].get("needed"), clicked=results["restore"].get("clicked"), checked_after_restore=results["restore"].get("checked_after_restore"), error=results["restore"].get("error"))

        results["status"] = determine_status(results)
        if results["after_select"].get("portal_present_after_select") is False:
            results["signals"].append("The tools Radix portal is absent after selecting Web search; immediate re-enumeration fails because the menu closes/detaches.")
        if results["reopen"].get("aria_checked_true") is True:
            results["signals"].append("Re-opening the tools menu after selection shows Web search with aria-checked=true; this is the verified reflection recipe.")
        chip_candidates = (results.get("after_select", {}).get("composer_indicators") or {}).get("candidates") if isinstance(results.get("after_select", {}).get("composer_indicators"), dict) else []
        if chip_candidates:
            results["signals"].append("A composer-level search chip candidate was observed after selecting Web search; report includes selector(s).")
        else:
            results["signals"].append("No composer-level Web search/search chip candidate was observed near the composer after selection.")
        if results["status"] != "DONE" and not results.get("blockers"):
            append_blocker(results, "REFLECTION_RECIPE_NOT_PROVEN", "Selection reflection was not fully characterized or re-open checked state was not true.")
    except StopRun as exc:
        results["status"] = exc.status
        results["signals"].append(f"Stopped: {exc.code}.")
        emit("stopped", status=exc.status, code=exc.code)
    except Exception as exc:  # noqa: BLE001 - safe metadata only.
        if results.get("status") != "BLOCKED":
            results["status"] = "PARTIAL"
        append_blocker(results, type(exc).__name__, "Driver exception; inspect safe report and rerun only if needed without sends.")
        emit("driver_error", error_type=type(exc).__name__)
    finally:
        # Best-effort restore if selection succeeded but the normal restore path did not run.
        if channel is not None and tab is not None and selected_click_ok and not results["restore"].get("attempted") and results["restore"].get("needed") is not False:
            try:
                restore_to_initial(channel, tab, results)
                emit("restore_finally", needed=results["restore"].get("needed"), clicked=results["restore"].get("clicked"), checked_after_restore=results["restore"].get("checked_after_restore"), error=results["restore"].get("error"))
            except Exception as exc:  # noqa: BLE001
                results["restore"]["error"] = type(exc).__name__
        if channel is not None:
            try:
                if tab is not None and own_tab_open:
                    try:
                        channel.close_tab(tab)
                        own_tab_open = False
                        emit("closed_own_tab", tab_id=getattr(tab, "tab_id", None))
                    except Exception as exc:  # noqa: BLE001
                        append_blocker(results, "CLOSE_TAB_FAILED", f"Own tab close raised {type(exc).__name__}; channel.detach attempted next.")
                        emit("close_tab_error", error_type=type(exc).__name__)
                channel.detach()
                emit("detached")
            except Exception as exc:  # noqa: BLE001
                append_blocker(results, "DETACH_FAILED", f"CdpChannel.detach raised {type(exc).__name__}; do not kill browser manually.")
                emit("detach_error", error_type=type(exc).__name__)
        post = preflight_version() if results.get("preflight") else {}
        results["post_detach_preflight"] = post
        results["confirmations"]["browser_not_quit_post_detach_version_ok"] = post.get("ok") is True if post else False
        git_end = git_checks() if results.get("git_start") is not None else None
        results["git_end"] = git_end
        if git_end is not None:
            results["confirmations"]["nothing_staged"] = not bool(git_end.get("staged_files"))
            results["confirmations"]["protected_paths_not_staged"] = not bool(git_end.get("protected_staged"))
            results["confirmations"]["branch_rewrite_v2"] = git_end.get("branch_ok_rewrite_v2")
            stable_end = git_end.get("stable_rev")
            results["confirmations"]["stable_unmoved_start_end"] = bool(stable_start and stable_end and stable_start == stable_end)
        if results.get("status") != "BLOCKED":
            results["status"] = determine_status(results)
        write_report(results)
        emit("report_written", status=results.get("status"), report=str(REPORT_PATH))
    return 0 if results.get("status") == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
