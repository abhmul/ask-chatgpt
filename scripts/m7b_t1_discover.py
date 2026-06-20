#!/usr/bin/env python3
"""M7b-T1 live selector rediscovery driver.

Own-tab-only CDP workflow: opens one fresh chatgpt.com tab, opens the model and
composer tools Radix menus, records structural metadata only, sends nothing, and
writes the selector verdict report.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt.channels.cdp import CdpChannel

CDP_ENDPOINT = "http://127.0.0.1:9222"
CDP_VERSION_URL = f"{CDP_ENDPOINT}/json/version"
REPORT_PATH = Path("team/evidence/reports/M7b-T1-selectors.md")
RADIX_PORTAL = "[data-radix-popper-content-wrapper]"
REQUIRED_BRANCH = "rewrite-v2"
OLD_MODEL_SELECTOR = 'composer-footer button[aria-haspopup="menu"]'
OLD_TOOLS_SELECTOR = 'button[data-testid="composer-plus-btn"]'

SENSITIVE_KEY_PARTS = (
    "authorization",
    "bearer",
    "cookie",
    "header",
    "oai",
    "password",
    "secret",
    "session",
    "token",
)
SENSITIVE_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "cookie:",
    "cf_clearance",
    "__secure-",
    "oai-",
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
    challenge_likely: /just a moment|checking your browser|verify you are human|cloudflare/.test((title + ' ' + body).toLowerCase()),
    login_likely: /log in|sign up|continue with google|continue with microsoft|continue with apple/.test(body),
  };
}
"""

JS_BUTTON_DUMP = r"""
(a) => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const short = (v, n = 40) => {
    const s = norm(v);
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  };
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const prompt = document.querySelector('#prompt-textarea');
  const promptRect = prompt ? prompt.getBoundingClientRect() : null;
  const form = prompt ? prompt.closest('form') : null;
  const composerish = prompt ? (
    prompt.closest('[data-testid*="composer" i]') ||
    prompt.closest('[class*="composer" i]') ||
    form
  ) : null;
  const distance = el => {
    if (!promptRect) return 0;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const px = promptRect.left + promptRect.width / 2;
    const py = promptRect.top + promptRect.height / 2;
    return Math.round(Math.hypot(cx - px, cy - py));
  };
  const buttons = Array.from(document.querySelectorAll('button,[role="button"]'))
    .filter(visible)
    .map((el, rawIndex) => {
      const classHint = short(Array.from(el.classList || []).slice(0, 5).join(' '), 80);
      const inForm = Boolean(form && form.contains(el));
      const inComposerish = Boolean(composerish && composerish.contains(el));
      const keep = inForm || inComposerish;
      return {
        keep,
        sort_distance: distance(el),
        raw_index: rawIndex,
        tagName: el.tagName,
        role: el.getAttribute('role') || null,
        id: el.id || null,
        data_testid: el.getAttribute('data-testid'),
        aria_haspopup: el.getAttribute('aria-haspopup'),
        aria_expanded: el.getAttribute('aria-expanded'),
        aria_label: short(el.getAttribute('aria-label') || '', 80) || null,
        title: short(el.getAttribute('title') || '', 80) || null,
        type: el.getAttribute('type') || null,
        disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled')),
        class_hint: classHint || null,
        innerText: short(el.innerText || el.textContent || '', 40),
        in_form: inForm,
        in_composerish: inComposerish,
      };
    })
    .filter(item => item.keep)
    .sort((a, b) => a.sort_distance - b.sort_distance || a.raw_index - b.raw_index)
    .map((item, index) => ({index, ...item}));
  return {
    scope: a && a.scope || 'composer-nearby',
    total_nearby: buttons.length,
    old_model_selector_count: (() => { try { return document.querySelectorAll('composer-footer button[aria-haspopup="menu"]').length; } catch (_) { return null; } })(),
    old_tools_selector_count: (() => { try { return document.querySelectorAll('button[data-testid="composer-plus-btn"]').length; } catch (_) { return null; } })(),
    candidates: buttons.slice(0, 80),
  };
}
"""

JS_DISCOVER_SELECTORS = r"""
() => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const cssString = v => '"' + String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const count = sel => {
    try { return document.querySelectorAll(sel).length; }
    catch (e) { return -1; }
  };
  const uniqueVisible = sel => {
    try {
      const items = Array.from(document.querySelectorAll(sel));
      return items.length === 1 && visible(items[0]);
    } catch (e) { return false; }
  };
  const prompt = document.querySelector('#prompt-textarea');
  const form = prompt ? prompt.closest('form') : null;
  const composerish = prompt ? (
    prompt.closest('[data-testid*="composer" i]') ||
    prompt.closest('[class*="composer" i]') ||
    form
  ) : null;
  const near = el => {
    if (!visible(el)) return false;
    return Boolean((form && form.contains(el)) || (composerish && composerish.contains(el)));
  };
  const buttons = Array.from(document.querySelectorAll('button,[role="button"]')).filter(near);
  const buttonIndexSelector = el => {
    const visibleButtons = Array.from(document.querySelectorAll('button,[role="button"]')).filter(near);
    const idx = visibleButtons.indexOf(el) + 1;
    return idx > 0 ? `button:nth-of-type(${idx})` : null;
  };
  const addIf = (list, sel, why) => {
    if (!sel) return;
    list.push({selector: sel, count: count(sel), unique_visible: uniqueVisible(sel), why});
  };
  const selectorOptions = (el, kind) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role');
    const dt = el.getAttribute('data-testid');
    const aria = el.getAttribute('aria-label');
    const haspopup = el.getAttribute('aria-haspopup');
    const txt = norm(el.innerText || el.textContent || '');
    const id = el.id;
    const options = [];
    if (kind === 'model') {
      addIf(options, 'button[aria-haspopup="menu"][aria-label*="Model" i]', 'aria-label contains Model');
      addIf(options, 'button[aria-haspopup="menu"][aria-label*="model" i]', 'aria-label contains model');
      addIf(options, 'form button[aria-haspopup="menu"][aria-label*="Model" i]', 'form + model aria label');
      addIf(options, 'form button[aria-haspopup="menu"]:not([data-testid])', 'form menu button without data-testid');
      addIf(options, 'form button[aria-haspopup="menu"]', 'all form menu buttons');
      addIf(options, '[data-testid="composer-footer-actions"] button[aria-haspopup="menu"]:not([data-testid])', 'composer footer actions menu button without testid');
      addIf(options, '[data-testid="composer-footer-actions"] button[aria-haspopup="menu"]', 'composer footer actions menu button');
      if (txt) {
        addIf(options, `button[aria-haspopup="menu"]:has(span)`, 'menu button with span descendant');
      }
    } else if (kind === 'tools') {
      addIf(options, 'button[data-testid="composer-plus-btn"]', 'legacy/offline data-testid');
      addIf(options, 'button[aria-label*="Add" i][aria-haspopup="menu"]', 'Add aria-label menu button');
      addIf(options, 'button[aria-label*="Attach" i][aria-haspopup="menu"]', 'Attach aria-label menu button');
      addIf(options, 'form button[aria-haspopup="menu"][data-testid*="plus" i]', 'form plus testid');
      addIf(options, 'form button[aria-haspopup="menu"][aria-label*="Add" i]', 'form add menu button');
      addIf(options, 'form button[aria-haspopup="menu"]:has(svg)', 'form menu button with svg');
    }
    if (id) addIf(options, `${tag}#${CSS.escape(id)}`, 'id exact');
    if (dt) addIf(options, `${tag}[data-testid=${cssString(dt)}]`, 'data-testid exact');
    if (aria) {
      addIf(options, `${tag}[aria-label=${cssString(aria)}]`, 'aria-label exact');
      if (haspopup) addIf(options, `${tag}[aria-haspopup=${cssString(haspopup)}][aria-label=${cssString(aria)}]`, 'aria-haspopup + aria-label exact');
    }
    if (role) addIf(options, `${tag}[role=${cssString(role)}]`, 'role exact');
    return options;
  };
  const modelRegex = /(gpt|chatgpt|o\d|thinking|auto)/i;
  const modelCandidates = buttons
    .filter(el => el.getAttribute('aria-haspopup') === 'menu')
    .map(el => ({el, text: norm(el.innerText || el.textContent || ''), aria: norm(el.getAttribute('aria-label') || ''), data_testid: el.getAttribute('data-testid')}))
    .filter(item => modelRegex.test(item.text) || /model/i.test(item.aria) || (item.text && item.data_testid !== 'composer-plus-btn' && !/(add|attach|upload|file|photo|dictation|voice)/i.test(item.aria)));
  const toolsRegex = /(add|attach|upload|plus|tool|photos|files)/i;
  const toolsCandidates = buttons
    .filter(el => el.getAttribute('aria-haspopup') === 'menu' || el.getAttribute('data-testid') === 'composer-plus-btn')
    .map(el => ({el, text: norm(el.innerText || el.textContent || ''), aria: norm(el.getAttribute('aria-label') || ''), data_testid: el.getAttribute('data-testid')}))
    .filter(item => item.data_testid === 'composer-plus-btn' || toolsRegex.test(item.text) || toolsRegex.test(item.aria) || /plus/i.test(item.data_testid || ''));
  const pick = (items, kind) => {
    const scored = items.map(item => {
      let score = 0;
      if (kind === 'model') {
        if (/model/i.test(item.aria)) score += 100;
        if (/(gpt|chatgpt|o\d|thinking)/i.test(item.text)) score += 80;
        if (!item.data_testid) score += 5;
      } else {
        if (item.data_testid === 'composer-plus-btn') score += 100;
        if (/add|attach|upload|photos|files/i.test(item.aria)) score += 80;
        if (/plus/i.test(item.data_testid || '')) score += 60;
        if (/^\+$/.test(item.text)) score += 30;
      }
      return {score, item};
    }).sort((a, b) => b.score - a.score);
    if (!scored.length) return null;
    const item = scored[0].item;
    const options = selectorOptions(item.el, kind);
    const preferred = options.find(o => o.unique_visible) || options.find(o => o.count === 1) || options[0] || null;
    return {
      text: item.text.slice(0, 80),
      aria_label: item.aria.slice(0, 120) || null,
      data_testid: item.data_testid,
      selector: preferred ? preferred.selector : null,
      selector_count: preferred ? preferred.count : null,
      selector_why: preferred ? preferred.why : null,
      all_selector_options: options,
    };
  };
  return {model: pick(modelCandidates, 'model'), tools: pick(toolsCandidates, 'tools')};
}
"""

JS_ACTIVATE_SELECTOR = r"""
(a) => {
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const enabled = el => !(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const matches = Array.from(document.querySelectorAll(a.selector));
  const target = matches.filter(visible).find(enabled);
  if (!target) return {ok: false, reason: 'no_visible_enabled_match', count: matches.length};
  target.scrollIntoView({block: 'center', inline: 'center'});
  target.focus();
  const rect = target.getBoundingClientRect();
  const base = {bubbles: true, cancelable: true, view: window, button: 0, buttons: 1, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2};
  try { target.dispatchEvent(new PointerEvent('pointerdown', {...base, pointerType: 'mouse', pointerId: 1, isPrimary: true})); } catch (_) {}
  target.dispatchEvent(new MouseEvent('mousedown', base));
  try { target.dispatchEvent(new PointerEvent('pointerup', {...base, pointerType: 'mouse', pointerId: 1, isPrimary: true, buttons: 0})); } catch (_) {}
  target.dispatchEvent(new MouseEvent('mouseup', {...base, buttons: 0}));
  target.click();
  return {ok: true, count: matches.length};
}
"""

JS_SELECTOR_INFO = r"""
(a) => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  try {
    const nodes = Array.from(document.querySelectorAll(a.selector));
    return {
      selector: a.selector,
      count: nodes.length,
      visible_count: nodes.filter(visible).length,
      texts: nodes.slice(0, 5).map(n => norm(n.innerText || n.textContent || '').slice(0, 120)).filter(Boolean),
      aria_labels: nodes.slice(0, 5).map(n => norm(n.getAttribute('aria-label') || '').slice(0, 120)).filter(Boolean),
    };
  } catch (e) {
    return {selector: a.selector, count: -1, visible_count: 0, texts: [], aria_labels: [], error: String(e && e.name || e)};
  }
}
"""

JS_PORTAL_ENUMERATE = r"""
(a) => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const disabled = el => Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const portals = Array.from(document.querySelectorAll(a.portal_selector || '[data-radix-popper-content-wrapper]'))
    .filter(visible)
    .map((portal, portal_index) => {
      const items = Array.from(portal.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'))
        .filter(visible)
        .map((el, index) => {
          const ariaChecked = el.getAttribute('aria-checked');
          const label = norm(el.innerText || el.textContent || el.getAttribute('aria-label') || '');
          return {
            index,
            label: label.slice(0, 120),
            role: el.getAttribute('role'),
            aria_checked: ariaChecked,
            checked: ariaChecked === 'true' ? true : (ariaChecked === 'false' ? false : null),
            disabled: disabled(el),
            aria_haspopup: el.getAttribute('aria-haspopup'),
            aria_expanded: el.getAttribute('aria-expanded'),
          };
        })
        .filter(item => item.label);
      return {portal_index, item_count: items.length, items};
    });
  return {portal_count: portals.length, portals, all_items: portals.flatMap(p => p.items)};
}
"""

JS_OPEN_SUBMENU = r"""
(a) => {
  const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const enabled = el => !(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const targetLabel = norm(a.label);
  const matches = Array.from(document.querySelectorAll('[data-radix-popper-content-wrapper] [role="menuitem"]'))
    .filter(el => visible(el) && enabled(el))
    .filter(el => norm(el.innerText || el.textContent || el.getAttribute('aria-label') || '') === targetLabel);
  if (matches.length !== 1) return {ok: false, reason: 'match_count', count: matches.length};
  const target = matches[0];
  target.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, cancelable: true, view: window}));
  target.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true, cancelable: true, view: window}));
  target.focus();
  return {ok: true};
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
        "recommended": {
            "model_picker_trigger_candidates": None,
            "tools_button": None,
            "model_label_readout": None,
            "model_label_same_as_trigger": None,
            "tools_menu_shape": None,
            "tools_submenu_path": [],
        },
        "model": {
            "button_dump": None,
            "discovery": None,
            "selector": None,
            "selector_info": None,
            "opened": False,
            "portal_item_count": 0,
            "portal_sample_labels": [],
            "portal_items": [],
            "label_readout_selector": None,
            "label_readout_info": None,
            "error": None,
        },
        "tools": {
            "button_dump": None,
            "discovery": None,
            "offline_guess_info": None,
            "selector": None,
            "selector_info": None,
            "opened": False,
            "portal_item_count": 0,
            "portal_sample_labels": [],
            "portal_items": [],
            "direct_tool_labels": [],
            "submenu_path": [],
            "submenu_probe": None,
            "error": None,
        },
        "git_start": None,
        "git_end": None,
        "confirmations": {
            "own_tab_only_no_json_list_no_page_enumeration": True,
            "zero_sends_no_session_send_used": True,
            "browser_not_quit_post_detach_version_ok": False,
            "no_auth_cookie_oai_values_logged": True,
            "no_conversation_content": True,
            "branch_rewrite_v2": None,
            "stable_unmoved_start_end": None,
            "nothing_staged": None,
            "protected_paths_not_staged": None,
            "old_model_selector_count": None,
            "old_tools_selector_count": None,
        },
        "blockers": [],
        "signals": [],
    }


def append_blocker(results: dict[str, Any], code: str, action: str) -> None:
    results["blockers"].append({"code": code, "action": action})


def stop(results: dict[str, Any], status: str, code: str, action: str) -> None:
    append_blocker(results, code, action)
    raise StopRun(status=status, code=code, action=action)


def sample_labels(items: list[dict[str, Any]], limit: int = 5) -> list[str]:
    out: list[str] = []
    for item in items:
        label = item.get("label")
        if isinstance(label, str) and label and label not in out:
            out.append(label)
        if len(out) >= limit:
            break
    return out


def compact_menu_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(
            {
                "label": item.get("label"),
                "role": item.get("role"),
                "aria_checked": item.get("aria_checked"),
                "checked": item.get("checked"),
                "disabled": item.get("disabled"),
            }
        )
    return out


def all_items(enum_result: Any) -> list[dict[str, Any]]:
    if not isinstance(enum_result, dict):
        return []
    items = enum_result.get("all_items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def selector_info(channel: CdpChannel, tab: Any, selector: str) -> dict[str, Any]:
    info = channel.evaluate(tab, JS_SELECTOR_INFO, arg={"selector": selector})
    return info if isinstance(info, dict) else {"selector": selector, "count": None, "visible_count": None}


def choose_readout_selector(channel: CdpChannel, tab: Any, trigger_selector: str) -> tuple[str | None, dict[str, Any] | None, bool | None]:
    trigger_info = selector_info(channel, tab, trigger_selector)
    texts = trigger_info.get("texts") if isinstance(trigger_info.get("texts"), list) else []
    if trigger_info.get("count") == 1 and any(isinstance(t, str) and t.strip() for t in texts):
        return trigger_selector, trigger_info, True
    probes = [
        f"{trigger_selector} span",
        f"{trigger_selector} div",
        f"{trigger_selector} [dir]",
    ]
    for probe in probes:
        info = selector_info(channel, tab, probe)
        probe_texts = info.get("texts") if isinstance(info.get("texts"), list) else []
        non_empty = [t for t in probe_texts if isinstance(t, str) and t.strip()]
        if info.get("count") == 1 and non_empty:
            return probe, info, False
    return None, trigger_info, None


def close_menu(channel: CdpChannel, tab: Any) -> None:
    try:
        channel.press(tab, "body", "Escape")
        channel.sleep(0.25)
    except Exception:
        try:
            channel.evaluate(tab, "() => document.body && document.body.click()")
            channel.sleep(0.25)
        except Exception:
            pass


def open_and_dump_menu(channel: CdpChannel, tab: Any, selector: str) -> tuple[bool, list[dict[str, Any]], str | None]:
    try:
        activated = channel.evaluate(tab, JS_ACTIVATE_SELECTOR, arg={"selector": selector}, timeout_s=5.0)
        if not isinstance(activated, dict) or activated.get("ok") is not True:
            return False, [], "ACTIVATE_FAILED"
        channel.wait_for_selector(tab, RADIX_PORTAL, state="visible", timeout_s=5.0)
        enum_result = channel.evaluate(tab, JS_PORTAL_ENUMERATE, arg={"portal_selector": RADIX_PORTAL}, timeout_s=5.0)
        items = all_items(enum_result)
        return True, items, None
    except Exception as exc:  # noqa: BLE001 - fail closed with safe type only.
        return False, [], type(exc).__name__


def analyze_tools_shape(channel: CdpChannel, tab: Any, items: list[dict[str, Any]]) -> tuple[str, list[str], list[str], dict[str, Any] | None]:
    labels = [item.get("label") for item in items if isinstance(item.get("label"), str)]
    known = [label for label in labels if label in {"Web search", "Deep research", "Create image", "Study"}]
    if known:
        return "direct", [], known, None
    submenu_labels = [label for label in labels if label in {"More", "More tools", "Tools"}]
    if submenu_labels:
        label = submenu_labels[0]
        probe: dict[str, Any] = {"attempted_label": label, "open_result": None, "items": []}
        result = channel.evaluate(tab, JS_OPEN_SUBMENU, arg={"label": label}, timeout_s=5.0)
        probe["open_result"] = result if isinstance(result, dict) else {"raw": result}
        try:
            channel.wait_for_selector(tab, RADIX_PORTAL, state="visible", timeout_s=2.0)
        except Exception:
            pass
        enum_result = channel.evaluate(tab, JS_PORTAL_ENUMERATE, arg={"portal_selector": RADIX_PORTAL}, timeout_s=5.0)
        submenu_items = all_items(enum_result)
        probe["items"] = submenu_items
        submenu_known = [item.get("label") for item in submenu_items if item.get("label") in {"Web search", "Deep research", "Create image", "Study"}]
        return "submenu", [label], [x for x in submenu_known if isinstance(x, str)], probe
    return "unknown", [], [], None


def determine_status(results: dict[str, Any]) -> str:
    model_ok = bool(
        results["model"].get("selector")
        and (results["model"].get("selector_info") or {}).get("count") == 1
        and results["model"].get("opened")
        and results["model"].get("portal_item_count", 0) > 0
    )
    tools_ok = bool(
        results["tools"].get("selector")
        and (results["tools"].get("selector_info") or {}).get("count") == 1
        and results["tools"].get("opened")
        and results["tools"].get("portal_item_count", 0) > 0
    )
    if model_ok and tools_ok:
        return "DONE"
    if model_ok or tools_ok:
        return "PARTIAL"
    return "PARTIAL"


def fmt_bool(value: Any) -> str:
    return "true" if value is True else "false" if value is False else "unknown"


def json_block(value: Any) -> str:
    return json.dumps(_scrub(value), indent=2, sort_keys=True, ensure_ascii=False)


def write_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    preflight = results.get("preflight") or {}
    rec = results.get("recommended") or {}
    model = results.get("model") or {}
    tools = results.get("tools") or {}
    conf = results.get("confirmations") or {}
    git_start = results.get("git_start") or {}
    git_end = results.get("git_end") or {}
    status = results.get("status") or "PARTIAL"
    model_selector = rec.get("model_picker_trigger_candidates") or "<not verified>"
    tools_selector = rec.get("tools_button") or "<not verified>"
    label_selector = rec.get("model_label_readout")
    lines: list[str] = []
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("# M7b-T1 live selector rediscovery")
    lines.append("")
    lines.append("## CDP preflight")
    lines.append("- Endpoint used: `/json/version` only (no `/json/list`).")
    lines.append(f"- Browser version: `{preflight.get('browser')}`")
    lines.append(f"- Protocol-Version: `{preflight.get('protocol_version')}`")
    lines.append(f"- WebSocket URL present: `{preflight.get('websocket_url_present')}`")
    lines.append(f"- Preflight ok/error: `{preflight.get('ok')}` / `{preflight.get('error_code') or preflight.get('error')}`")
    lines.append("")
    lines.append("## Recommended real.json selectors")
    lines.append("```json")
    selector_payload: dict[str, Any] = {
        "model_picker_trigger_candidates": model_selector,
        "tools_button": tools_selector,
    }
    if label_selector:
        selector_payload["model_label_readout"] = label_selector
    lines.append(json.dumps(selector_payload, indent=2, ensure_ascii=False))
    lines.append("```")
    if label_selector:
        lines.append("- `model_label_readout` differs from the trigger. Editor must add it to `REQUIRED_SELECTOR_KEYS` in `src/ask_chatgpt/selectors/__init__.py` and update mocks/tests.")
    else:
        same = rec.get("model_label_same_as_trigger")
        lines.append(f"- Current-model-label readout: trigger text itself (`same_as_trigger={same}`).")
    lines.append(f"- Tools menu shape: `{rec.get('tools_menu_shape')}`; `submenu_path`: `{rec.get('tools_submenu_path') or []}`.")
    lines.append("")
    lines.append("## Evidence")
    model_info = model.get("selector_info") or {}
    label_info = model.get("label_readout_info") or {}
    tools_info = tools.get("selector_info") or {}
    offline_info = tools.get("offline_guess_info") or {}
    lines.append("### Model picker")
    lines.append(f"- Selector: `{model.get('selector')}`")
    lines.append(f"- `querySelectorAll(...).length`: `{model_info.get('count')}`; visible count: `{model_info.get('visible_count')}`")
    lines.append(f"- Opened portal: `{model.get('opened')}`; item count: `{model.get('portal_item_count')}`")
    lines.append(f"- Sample menuitem labels: `{model.get('portal_sample_labels')}`")
    lines.append(f"- Portal item dump (label/role/aria-checked): `{json.dumps(compact_menu_items(model.get('portal_items') or []), ensure_ascii=False)}`")
    lines.append(f"- Label readout selector: `{model.get('label_readout_selector')}`; count: `{label_info.get('count')}`; sample text: `{(label_info.get('texts') or [None])[0] if isinstance(label_info.get('texts'), list) and label_info.get('texts') else None}`")
    lines.append(f"- Old offline model selector `{OLD_MODEL_SELECTOR}` count: `{conf.get('old_model_selector_count')}`")
    lines.append(f"- Error: `{model.get('error')}`")
    lines.append("")
    lines.append("### Tools button")
    lines.append(f"- Selector: `{tools.get('selector')}`")
    lines.append(f"- `querySelectorAll(...).length`: `{tools_info.get('count')}`; visible count: `{tools_info.get('visible_count')}`")
    lines.append(f"- Opened portal: `{tools.get('opened')}`; item count: `{tools.get('portal_item_count')}`")
    lines.append(f"- Sample menuitem labels: `{tools.get('portal_sample_labels')}`")
    lines.append(f"- Portal item dump (label/role/aria-checked): `{json.dumps(compact_menu_items(tools.get('portal_items') or []), ensure_ascii=False)}`")
    lines.append(f"- Direct known tool labels observed: `{tools.get('direct_tool_labels')}`")
    lines.append(f"- Old offline tools selector `{OLD_TOOLS_SELECTOR}` count: `{offline_info.get('count')}`; visible count: `{offline_info.get('visible_count')}`")
    lines.append(f"- Error: `{tools.get('error')}`")
    lines.append("")
    lines.append("## Button dumps")
    lines.append("### Model-area structural candidates")
    lines.append("```json")
    lines.append(json_block(model.get("button_dump")))
    lines.append("```")
    lines.append("")
    lines.append("### Tools-area structural candidates")
    lines.append("```json")
    lines.append(json_block(tools.get("button_dump")))
    lines.append("```")
    lines.append("")
    lines.append("## Confirmations")
    lines.append(f"- Own-tab-only: `{fmt_bool(conf.get('own_tab_only_no_json_list_no_page_enumeration'))}` (driver uses `CdpChannel.open_tab(...)`; no `/json/list`; no page enumeration; only closes its lease).")
    lines.append("- ZERO sends: `true` (`Session.ask/loop` and composer submit were never used; `successful_submissions` not applicable).")
    lines.append(f"- Browser not quit: `{fmt_bool(conf.get('browser_not_quit_post_detach_version_ok'))}`; post-detach `/json/version` ok: `{(results.get('post_detach_preflight') or {}).get('ok')}`")
    lines.append(f"- No auth/cookie/oai values logged: `{fmt_bool(conf.get('no_auth_cookie_oai_values_logged'))}`")
    lines.append(f"- No conversation content: `{fmt_bool(conf.get('no_conversation_content'))}`")
    lines.append(f"- Branch start/end: `{git_start.get('branch')}` / `{git_end.get('branch')}`; rewrite-v2: `{fmt_bool(conf.get('branch_rewrite_v2'))}`")
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
    stable_start: str | None = None
    try:
        preflight = preflight_version()
        results["preflight"] = preflight
        emit("preflight", browser=preflight.get("browser"), websocket_url_present=preflight.get("websocket_url_present"), ok=preflight.get("ok"), error_code=preflight.get("error_code"))
        if preflight.get("ok") is not True:
            stop(results, "BLOCKED", "CDP_UNREACHABLE", "Expose Chrome CDP on 127.0.0.1:9222 and rerun; no browser attach attempted.")

        git_start = git_checks()
        results["git_start"] = git_start
        stable_start = git_start.get("stable_rev") if isinstance(git_start.get("stable_rev"), str) else None
        results["confirmations"]["branch_rewrite_v2"] = git_start.get("branch_ok_rewrite_v2")
        emit("git_start", branch=git_start.get("branch"), stable_rev=git_start.get("stable_rev"), staged_count=len(git_start.get("staged_files") or []))
        if git_start.get("branch_ok_rewrite_v2") is not True:
            stop(results, "BLOCKED", "WRONG_BRANCH", "Switch to branch rewrite-v2 before running selector discovery; no browser attach attempted.")

        channel = CdpChannel(cdp_endpoint=CDP_ENDPOINT)
        channel.attach()
        emit("attached")
        tab = channel.open_tab("https://chatgpt.com/")
        emit("opened_own_tab", tab_id=getattr(tab, "tab_id", None))
        try:
            channel.wait_for_selector(tab, "#prompt-textarea", state="visible", timeout_s=20.0)
        except Exception:
            page_state = channel.evaluate(tab, JS_PAGE_STATE, timeout_s=5.0)
            results["signals"].append(f"Composer unavailable; page_state={json.dumps(_scrub(page_state), sort_keys=True)}")
            stop(results, "BLOCKED", "HUMAN-ACTION-NEEDED", "Operator must clear login/Cloudflare/human action until a fresh ChatGPT composer is visible; no retries attempted.")
        page_state = channel.evaluate(tab, JS_PAGE_STATE, timeout_s=5.0)
        if isinstance(page_state, dict) and (page_state.get("challenge_likely") or page_state.get("login_likely") or not page_state.get("has_composer")):
            results["signals"].append(f"Blocked page state after load: {json.dumps(_scrub(page_state), sort_keys=True)}")
            stop(results, "BLOCKED", "HUMAN-ACTION-NEEDED", "Operator must clear login/Cloudflare/human action until a fresh ChatGPT composer is visible; no retries attempted.")

        model_dump = channel.evaluate(tab, JS_BUTTON_DUMP, arg={"scope": "model-before-open"}, timeout_s=5.0)
        results["model"]["button_dump"] = model_dump
        if isinstance(model_dump, dict):
            results["confirmations"]["old_model_selector_count"] = model_dump.get("old_model_selector_count")
            results["confirmations"]["old_tools_selector_count"] = model_dump.get("old_tools_selector_count")
        discovery = channel.evaluate(tab, JS_DISCOVER_SELECTORS, timeout_s=5.0)
        results["model"]["discovery"] = discovery.get("model") if isinstance(discovery, dict) else None
        results["tools"]["discovery"] = discovery.get("tools") if isinstance(discovery, dict) else None
        model_selector = (results["model"].get("discovery") or {}).get("selector") if isinstance(results["model"].get("discovery"), dict) else None
        if isinstance(model_selector, str) and model_selector:
            model_info = selector_info(channel, tab, model_selector)
            results["model"]["selector"] = model_selector
            results["model"]["selector_info"] = model_info
            opened, items, err = open_and_dump_menu(channel, tab, model_selector)
            results["model"]["opened"] = opened
            results["model"]["portal_items"] = items
            results["model"]["portal_item_count"] = len(items)
            results["model"]["portal_sample_labels"] = sample_labels(items)
            if err:
                results["model"]["error"] = err
            if opened:
                readout_selector, readout_info, same = choose_readout_selector(channel, tab, model_selector)
                results["model"]["label_readout_selector"] = readout_selector
                results["model"]["label_readout_info"] = readout_info
                if same is False and readout_selector:
                    results["recommended"]["model_label_readout"] = readout_selector
                    results["recommended"]["model_label_same_as_trigger"] = False
                elif same is True:
                    results["recommended"]["model_label_same_as_trigger"] = True
                close_menu(channel, tab)
        else:
            results["model"]["error"] = "NO_MODEL_SELECTOR_CANDIDATE"
            results["signals"].append("No model trigger candidate found by label/aria heuristics; button dump is the evidence.")

        tools_dump = channel.evaluate(tab, JS_BUTTON_DUMP, arg={"scope": "tools-before-open"}, timeout_s=5.0)
        results["tools"]["button_dump"] = tools_dump
        results["tools"]["offline_guess_info"] = selector_info(channel, tab, OLD_TOOLS_SELECTOR)
        tools_selector = (results["tools"].get("discovery") or {}).get("selector") if isinstance(results["tools"].get("discovery"), dict) else None
        if isinstance(tools_selector, str) and tools_selector:
            tools_info = selector_info(channel, tab, tools_selector)
            results["tools"]["selector"] = tools_selector
            results["tools"]["selector_info"] = tools_info
            opened, items, err = open_and_dump_menu(channel, tab, tools_selector)
            results["tools"]["opened"] = opened
            results["tools"]["portal_items"] = items
            results["tools"]["portal_item_count"] = len(items)
            results["tools"]["portal_sample_labels"] = sample_labels(items)
            if err:
                results["tools"]["error"] = err
            if opened:
                shape, path, known, probe = analyze_tools_shape(channel, tab, items)
                results["tools"]["direct_tool_labels"] = known
                results["tools"]["submenu_path"] = path
                results["tools"]["submenu_probe"] = probe
                results["recommended"]["tools_menu_shape"] = shape
                results["recommended"]["tools_submenu_path"] = path
                close_menu(channel, tab)
        else:
            results["tools"]["error"] = "NO_TOOLS_SELECTOR_CANDIDATE"
            results["signals"].append("No tools trigger candidate found by label/aria/testid heuristics; button dump is the evidence.")

        if results["model"].get("selector") and (results["model"].get("selector_info") or {}).get("count") == 1 and results["model"].get("opened"):
            results["recommended"]["model_picker_trigger_candidates"] = results["model"].get("selector")
        if results["tools"].get("selector") and (results["tools"].get("selector_info") or {}).get("count") == 1 and results["tools"].get("opened"):
            results["recommended"]["tools_button"] = results["tools"].get("selector")
        if results["recommended"].get("tools_menu_shape") is None and results["tools"].get("opened"):
            results["recommended"]["tools_menu_shape"] = "unknown"
        results["status"] = determine_status(results)
        if results["model"].get("opened") or results["tools"].get("opened"):
            results["signals"].append("Menu opening was verified with JS-dispatched pointer/mouse/click activation; no composer submission was made.")
        if results["recommended"].get("tools_button") == OLD_TOOLS_SELECTOR:
            results["signals"].append("Tools selector is unchanged from the offline map; live evidence says the selector is present and opens the Radix tools portal under pointer/mouse activation.")
        if results["confirmations"].get("old_model_selector_count") == 0:
            results["signals"].append("Offline model selector misses because the live composer no longer has a `composer-footer` ancestor for the model trigger.")
        if results["status"] != "DONE":
            append_blocker(results, "SELECTOR_DISCOVERY_PARTIAL", "One or both menus did not produce a unique selector and visible Radix portal; inspect button dumps.")
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
        if channel is not None:
            try:
                if tab is not None:
                    try:
                        channel.close_tab(tab)
                        emit("closed_own_tab", tab_id=getattr(tab, "tab_id", None))
                    except Exception as exc:  # noqa: BLE001
                        append_blocker(results, "CLOSE_TAB_FAILED", f"Own tab close raised {type(exc).__name__}; channel.detach attempted next.")
                channel.detach()
                emit("detached")
            except Exception as exc:  # noqa: BLE001
                append_blocker(results, "DETACH_FAILED", f"CdpChannel.detach raised {type(exc).__name__}; do not kill browser manually.")
                emit("detach_error", error_type=type(exc).__name__)
        if channel is not None:
            post = preflight_version()
        else:
            post = {}
        results["post_detach_preflight"] = post
        results["confirmations"]["browser_not_quit_post_detach_version_ok"] = post.get("ok") is True if post else False
        git_end = git_checks() if results.get("git_start") is not None else None
        results["git_end"] = git_end
        if git_end is not None:
            results["confirmations"]["nothing_staged"] = not bool(git_end.get("staged_files"))
            results["confirmations"]["protected_paths_not_staged"] = not bool(git_end.get("protected_staged"))
            stable_end = git_end.get("stable_rev")
            results["confirmations"]["stable_unmoved_start_end"] = bool(stable_start and stable_end and stable_start == stable_end)
            results["confirmations"]["branch_rewrite_v2"] = git_end.get("branch_ok_rewrite_v2")
        write_report(results)
        emit("report_written", status=results.get("status"), report=str(REPORT_PATH))
    return 0 if results.get("status") == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
