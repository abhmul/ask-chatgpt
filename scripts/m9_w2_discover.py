#!/usr/bin/env python3
"""M9-W2 attended real-site discovery driver.

Own-tab-only CDP workflow. Opens one fresh ChatGPT tab via production CdpChannel,
stages one throwaway upload, enumerates/selects menus without sending, restores
state, detaches, and prints credential-free JSON evidence to stdout.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from ask_chatgpt import menus
from ask_chatgpt.channels.cdp import CdpChannel
from ask_chatgpt.errors import AskChatGPTError
from ask_chatgpt.selectors import load_selector_map

CDP_ENDPOINT = "http://127.0.0.1:9222"
CDP_VERSION_URL = f"{CDP_ENDPOINT}/json/version"
CHATGPT_URL = "https://chatgpt.com/"
TARGET_SHORT = "6a316aa8"
TARGET_FULL = "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"
UPLOAD_PATH = Path("/tmp/m9-upload.txt")
UPLOAD_NAME = UPLOAD_PATH.name

SENSITIVE_KEY_PARTS = (
    "authorization",
    "bearer",
    "cookie",
    "header",
    "html",
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
    "password",
    "secret",
    "session-token",
    "token=",
)

JS_PAGE_STATE = r"""
() => {
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const title = norm(document.title).slice(0, 120);
  const body = norm(document.body ? document.body.innerText : '').toLowerCase();
  const url = String(location.href || '');
  const path = String(location.pathname || '');
  const hasComposer = Boolean(document.querySelector('#prompt-textarea'));
  return {
    path,
    title,
    has_composer: hasComposer,
    target_conversation_loaded: url.includes('/c/6a316aa8') || url.includes('6a316aa8-5dc8-83ea-9014-b8ea38dabc31'),
    challenge_likely: /just a moment|checking your browser|verify you are human|cloudflare/.test((title + ' ' + body).toLowerCase()),
    login_likely: !hasComposer && /log in|sign up|continue with google|continue with microsoft|continue with apple/.test(body),
  };
}
"""

JS_FILE_INPUTS = r"""
(a) => {
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const cssEscape = value => {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(String(value));
    return String(value).replace(/[^a-zA-Z0-9_-]/g, ch => '\\' + ch);
  };
  const cssString = value => '"' + String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  const count = selector => { try { return document.querySelectorAll(selector).length; } catch (_) { return null; } };
  const unique = selector => count(selector) === 1;
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const childSelector = el => {
    const parent = el.parentElement;
    const tag = el.tagName.toLowerCase();
    if (!parent) return tag;
    const sameTag = Array.from(parent.children).filter(child => child.tagName === el.tagName);
    const index = sameTag.indexOf(el) + 1;
    return `${tag}:nth-of-type(${Math.max(1, index)})`;
  };
  const selectorFor = el => {
    const tag = el.tagName.toLowerCase();
    if (el.id) {
      const selector = `${tag}#${cssEscape(el.id)}`;
      if (unique(selector)) return selector;
    }
    for (const attr of ['data-testid', 'name', 'aria-label']) {
      const value = el.getAttribute(attr);
      if (value) {
        const selector = `${tag}[${attr}=${cssString(value)}]`;
        if (unique(selector)) return selector;
      }
    }
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE && cur !== document.body && parts.length < 8) {
      if (cur.id) {
        parts.unshift(`${cur.tagName.toLowerCase()}#${cssEscape(cur.id)}`);
        break;
      }
      const testid = cur.getAttribute && cur.getAttribute('data-testid');
      if (testid) {
        parts.unshift(`${cur.tagName.toLowerCase()}[data-testid=${cssString(testid)}]`);
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
    if (path && unique(path)) return path;
    return path || tag;
  };
  const prompt = document.querySelector(a.composer_selector || '#prompt-textarea');
  const tools = document.querySelector(a.tools_selector || 'button[data-testid="composer-plus-btn"]');
  const form = prompt ? prompt.closest('form') : (tools ? tools.closest('form') : null);
  const scope = form || document.body;
  const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
  const inScope = inputs.filter(input => scope.contains(input));
  const inForm = form ? inputs.filter(input => form.contains(input)) : [];
  const descriptors = inputs.map((input, index) => ({
    index,
    in_form: form ? form.contains(input) : false,
    in_composer_scope: scope.contains(input),
    visible: visible(input),
    disabled: Boolean(input.disabled || input.getAttribute('aria-disabled') === 'true' || input.hasAttribute('disabled')),
    multiple: Boolean(input.multiple),
    accept: norm(input.getAttribute('accept') || ''),
    name: norm(input.getAttribute('name') || ''),
    id: norm(input.id || ''),
    data_testid: norm(input.getAttribute('data-testid') || ''),
    aria_label: norm(input.getAttribute('aria-label') || ''),
    selector: selectorFor(input),
    selector_count: count(selectorFor(input)),
  }));
  let preferred = null;
  let reason = null;
  if (form && inForm.length === 1) {
    if (unique('form input[type="file"]')) {
      preferred = 'form input[type="file"]';
      reason = 'single_file_input_in_the_only_form';
    } else {
      preferred = selectorFor(inForm[0]);
      reason = 'single_file_input_in_composer_form';
    }
  } else if (inputs.length === 1) {
    preferred = 'input[type="file"]';
    reason = 'single_file_input_on_page';
  } else if (inScope.length === 1) {
    preferred = selectorFor(inScope[0]);
    reason = 'single_file_input_in_composer_scope';
  }
  return {
    all_file_input_count: inputs.length,
    composer_form_present: Boolean(form),
    file_inputs_in_form_count: inForm.length,
    file_inputs_in_composer_scope_count: inScope.length,
    original_selector: a.original_selector,
    original_selector_count: count(a.original_selector || 'input[type="file"]'),
    form_selector_count: count('form input[type="file"]'),
    preferred_selector: preferred,
    preferred_reason: reason,
    inputs: descriptors,
  };
}
"""

JS_ATTACHMENT_CANDIDATES = r"""
(a) => {
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const cssEscape = value => {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(String(value));
    return String(value).replace(/[^a-zA-Z0-9_-]/g, ch => '\\' + ch);
  };
  const cssString = value => '"' + String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  const count = selector => { try { return document.querySelectorAll(selector).length; } catch (_) { return null; } };
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const unique = selector => count(selector) === 1;
  const childSelector = el => {
    const parent = el.parentElement;
    const tag = el.tagName.toLowerCase();
    if (!parent) return tag;
    const sameTag = Array.from(parent.children).filter(child => child.tagName === el.tagName);
    const index = sameTag.indexOf(el) + 1;
    return `${tag}:nth-of-type(${Math.max(1, index)})`;
  };
  const selectorFor = el => {
    const tag = el.tagName.toLowerCase();
    if (el.id) {
      const selector = `${tag}#${cssEscape(el.id)}`;
      if (unique(selector)) return selector;
    }
    const testid = el.getAttribute('data-testid');
    if (testid) {
      const selector = `${tag}[data-testid=${cssString(testid)}]`;
      if (unique(selector)) return selector;
    }
    const aria = el.getAttribute('aria-label');
    if (aria) {
      const selector = `${tag}[aria-label=${cssString(aria)}]`;
      if (unique(selector)) return selector;
    }
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE && cur !== document.body && parts.length < 8) {
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
    if (path && unique(path)) return path;
    return path || tag;
  };
  const prompt = document.querySelector(a.composer_selector || '#prompt-textarea');
  const form = prompt ? prompt.closest('form') : null;
  const scope = form || document.body;
  const portals = Array.from(document.querySelectorAll('[data-radix-popper-content-wrapper]'));
  const inPortal = el => portals.some(portal => portal.contains(el));
  const productionMatches = Array.from(document.querySelectorAll(a.attachment_selector || '[data-testid="composer-attachment"], div[data-testid*="attachment"], button[aria-label*="Remove" i]'));
  const productionVisible = productionMatches.filter(visible);
  const fileName = norm(a.file_name || '');
  const nodes = Array.from(scope.querySelectorAll('[data-testid],button,[role="button"],[aria-label],div,span'));
  const rawCandidates = nodes
    .filter(el => visible(el) && !inPortal(el))
    .map((el, raw_index) => {
      const display = norm(el.innerText || el.textContent || '').slice(0, 160);
      const aria = norm(el.getAttribute('aria-label') || '').slice(0, 160);
      const title = norm(el.getAttribute('title') || '').slice(0, 160);
      const testid = norm(el.getAttribute('data-testid') || '').slice(0, 160);
      const klass = norm(Array.from(el.classList || []).slice(0, 8).join(' ')).slice(0, 160);
      const combined = norm([display, aria, title, testid, klass].join(' '));
      return {el, raw_index, display, aria, title, testid, klass, combined};
    })
    .filter(item => {
      const c = item.combined.toLowerCase();
      return (fileName && c.includes(fileName.toLowerCase())) || /attachment|attach|file|uploaded|remove/.test(c);
    });
  const candidates = rawCandidates.map((item, index) => {
    const el = item.el;
    const rect = el.getBoundingClientRect();
    const selector = selectorFor(el);
    return {
      index,
      raw_index: item.raw_index,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role'),
      data_testid: el.getAttribute('data-testid'),
      aria_label: item.aria || null,
      title: item.title || null,
      display_label: item.display || null,
      class_hint: item.klass || null,
      selector,
      selector_count: count(selector),
      production_selector_match: productionMatches.includes(el),
      rect: {width: Math.round(rect.width), height: Math.round(rect.height)},
    };
  }).slice(0, 80);
  return {
    production_selector: a.attachment_selector,
    production_match_count: productionMatches.length,
    production_visible_count: productionVisible.length,
    candidate_count: candidates.length,
    candidates,
  };
}
"""

JS_COMPOSER_EMPTY = r"""
(a) => {
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const prompt = document.querySelector(a.composer_selector || '#prompt-textarea');
  const form = prompt ? prompt.closest('form') : null;
  const scope = form || document.body;
  const composerText = prompt ? norm(prompt.innerText || prompt.textContent || prompt.value || '') : '';
  const chips = Array.from(scope.querySelectorAll(a.attachment_selector || '[data-testid="composer-attachment"], div[data-testid*="attachment"], button[aria-label*="Remove" i]')).filter(visible);
  const fileName = String(a.file_name || '');
  const fileNameVisible = fileName ? norm(scope.innerText || scope.textContent || '').includes(fileName) : false;
  const fileInputs = Array.from(scope.querySelectorAll('input[type="file"]')).map(input => ({files_length: input.files ? input.files.length : null}));
  return {
    composer_present: Boolean(prompt),
    composer_text_empty: composerText.length === 0,
    attachment_visible_count: chips.length,
    staged_file_name_visible: fileNameVisible,
    file_input_file_lengths: fileInputs,
    empty_confirmed: Boolean(prompt) && composerText.length === 0 && chips.length === 0 && !fileNameVisible,
  };
}
"""

JS_MODEL_TRIGGER_LABELS = r"""
(a) => {
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const disabled = el => Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  return Array.from(document.querySelectorAll(a.selector))
    .filter(visible)
    .map((el, index) => ({
      index,
      label: norm(el.innerText || el.textContent || el.getAttribute('aria-label') || ''),
      aria_expanded: el.getAttribute('aria-expanded'),
      disabled: disabled(el),
    }))
    .filter(item => item.label);
}
"""

JS_ALL_PORTAL_OPTIONS = r"""
(a) => {
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const disabled = el => Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'));
  const portalSelector = a.portal_selector || '[data-radix-popper-content-wrapper]';
  const familyLabel = norm(a.family_label || '');
  const topPairs = new Set((a.top_pairs || []).map(pair => `${norm(pair.label)}\u0000${pair.role || ''}`));
  const portals = Array.from(document.querySelectorAll(portalSelector));
  const portalRecords = portals.map((portal, portal_index) => {
    const rect = portal.getBoundingClientRect();
    const items = Array.from(portal.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'))
      .filter(visible)
      .map((el, index) => {
        const label = norm(el.innerText || el.textContent || el.getAttribute('aria-label') || '');
        const ariaChecked = el.getAttribute('aria-checked');
        return {
          index,
          label,
          role: el.getAttribute('role'),
          checked: ariaChecked === 'true' ? true : (ariaChecked === 'false' ? false : null),
          aria_checked: ariaChecked,
          disabled: disabled(el),
          aria_haspopup: el.getAttribute('aria-haspopup'),
          aria_expanded: el.getAttribute('aria-expanded'),
          data_state: el.getAttribute('data-state'),
        };
      })
      .filter(item => item.label);
    return {
      portal_index,
      visible: visible(portal),
      rect: {left: Math.round(rect.left), top: Math.round(rect.top), width: Math.round(rect.width), height: Math.round(rect.height)},
      item_count: items.length,
      items,
    };
  });
  const visiblePortals = portalRecords.filter(record => record.visible);
  let topPortalIndex = visiblePortals.length ? visiblePortals[0].portal_index : null;
  for (const record of visiblePortals) {
    if (record.items.some(item => item.label === familyLabel && item.role === 'menuitem')) {
      topPortalIndex = record.portal_index;
      break;
    }
  }
  let subEntries = [];
  for (const record of visiblePortals) {
    if (record.portal_index === topPortalIndex && visiblePortals.length > 1) continue;
    for (const item of record.items) {
      if (item.role === 'menuitemradio') subEntries.push({portal_index: record.portal_index, ...item});
    }
  }
  if (!subEntries.length) {
    for (const record of visiblePortals) {
      for (const item of record.items) {
        const key = `${item.label}\u0000${item.role || ''}`;
        if (item.role === 'menuitemradio' && !topPairs.has(key)) subEntries.push({portal_index: record.portal_index, ...item});
      }
    }
  }
  return {
    portal_count: portals.length,
    visible_portal_count: visiblePortals.length,
    top_portal_index: topPortalIndex,
    portals: portalRecords,
    sub_entries_guess: subEntries,
  };
}
"""


def scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEY_PARTS):
                out[key_text] = "<redacted>"
            else:
                out[key_text] = scrub(nested)
        return out
    if isinstance(value, (list, tuple, set)):
        return [scrub(item) for item in value]
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
    print(json.dumps(scrub({"event": event, **payload}), sort_keys=True, ensure_ascii=False), flush=True)


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
        "curl_returncode": completed.returncode,
        "error_code": None,
        "error": None,
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
    ws_present = isinstance(data.get("webSocketDebuggerUrl"), str) and bool(data.get("webSocketDebuggerUrl"))
    result.update(
        {
            "ok": ws_present,
            "browser": data.get("Browser") if isinstance(data.get("Browser"), str) else None,
            "protocol_version": data.get("Protocol-Version") if isinstance(data.get("Protocol-Version"), str) else None,
            "websocket_url_present": ws_present,
            "error_code": None if ws_present else "CDP_UNREACHABLE",
            "error": None if ws_present else "websocket_url_missing",
        }
    )
    return result


def option_records(options: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "label": getattr(option, "label", None),
            "role": getattr(option, "role", None),
            "checked": getattr(option, "checked", None),
            "disabled": getattr(option, "disabled", None),
            "path": list(getattr(option, "path", ()) or ()),
        }
        for option in options
    ]


def selection_result_record(result: Any) -> dict[str, Any]:
    return {
        "requested": getattr(result, "requested", None),
        "reflected": getattr(result, "reflected", None),
        "verified": getattr(result, "verified", None),
    }


def error_record(exc: BaseException) -> dict[str, Any]:
    rec: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, AskChatGPTError):
        rec["code"] = exc.code
        rec["details"] = dict(exc.details)
    return rec


def normalize_label(label: str) -> str:
    return " ".join(str(label).split()).casefold()


def pace(seconds: float = 0.65) -> None:
    time.sleep(seconds)


def close_menu(channel: CdpChannel, tab: Any) -> None:
    for _ in range(2):
        try:
            channel.press(tab, "body", "Escape")
            pace(0.25)
        except Exception:
            break


def page_state(channel: CdpChannel, tab: Any) -> dict[str, Any]:
    raw = channel.evaluate(tab, JS_PAGE_STATE, timeout_s=5.0)
    return raw if isinstance(raw, dict) else {"raw_type": type(raw).__name__}


def stop_if_human_needed(state: Mapping[str, Any]) -> None:
    if state.get("target_conversation_loaded"):
        raise RuntimeError("PROTECTED_TARGET_LOADED")
    if state.get("challenge_likely") or state.get("login_likely") or state.get("has_composer") is False:
        raise RuntimeError("HUMAN-ACTION-NEEDED")


def model_trigger_labels(channel: CdpChannel, tab: Any, selector: str) -> list[dict[str, Any]]:
    raw = channel.evaluate(tab, JS_MODEL_TRIGGER_LABELS, arg={"selector": selector}, timeout_s=5.0)
    return raw if isinstance(raw, list) else []


def current_model_label(channel: CdpChannel, tab: Any, selector: str) -> str | None:
    labels = [item.get("label") for item in model_trigger_labels(channel, tab, selector) if isinstance(item, dict) and item.get("label")]
    if len(labels) == 1 and isinstance(labels[0], str):
        return labels[0]
    return None


def choose_attachment_selector(info: Mapping[str, Any], production_selector: str) -> str:
    candidates = info.get("candidates") if isinstance(info.get("candidates"), list) else []
    typed = [item for item in candidates if isinstance(item, dict)]
    for item in typed:
        testid = str(item.get("data_testid") or "").lower()
        if "attachment" in testid and item.get("selector_count") == 1:
            return str(item.get("selector"))
    for item in typed:
        testid = str(item.get("data_testid") or "").lower()
        if ("file" in testid or "upload" in testid or "attachment" in testid) and item.get("selector_count") == 1:
            return str(item.get("selector"))
    for item in typed:
        aria = str(item.get("aria_label") or "").lower()
        if "remove" in aria and item.get("selector_count") == 1:
            return str(item.get("selector"))
    for item in typed:
        display = str(item.get("display_label") or "").lower()
        if UPLOAD_NAME.lower() in display and item.get("selector_count") == 1:
            return str(item.get("selector"))
    if info.get("production_visible_count") == 1:
        return production_selector
    return production_selector


def find_option(options: Sequence[Mapping[str, Any]], label: str) -> Mapping[str, Any] | None:
    wanted = normalize_label(label)
    for option in options:
        if normalize_label(str(option.get("label") or "")) == wanted:
            return option
    return None


def select_model_attempt(tab: Any, selectors: Mapping[str, str], label: str, channel: CdpChannel) -> dict[str, Any]:
    before = model_trigger_labels(channel, tab, selectors["model_picker_trigger_candidates"])
    out: dict[str, Any] = {"label": label, "before_trigger_labels": before, "ok": False, "result": None, "error": None}
    try:
        result = menus.select_model(tab, selectors, label)  # production path under test
        out.update({"ok": True, "result": selection_result_record(result)})
    except Exception as exc:  # noqa: BLE001 - safe metadata only.
        out["error"] = error_record(exc)
    finally:
        try:
            close_menu(channel, tab)
        finally:
            out["after_trigger_labels"] = model_trigger_labels(channel, tab, selectors["model_picker_trigger_candidates"])
    emit("model_select_attempt", label=label, ok=out["ok"], result=out.get("result"), error=out.get("error"), after_trigger_labels=out.get("after_trigger_labels"))
    pace()
    return out


def tool_state(channel: CdpChannel, tab: Any, selectors: Mapping[str, str], label: str) -> dict[str, Any]:
    state: dict[str, Any] = {"opened": False, "options": [], "target": None, "error": None}
    try:
        menus.open_radix_menu(tab, selectors["tools_button"])
        state["opened"] = True
        options = option_records(menus.enumerate_radix_options(tab))
        state["options"] = options
        state["target"] = find_option(options, label)
    except Exception as exc:  # noqa: BLE001 - safe metadata only.
        state["error"] = error_record(exc)
    finally:
        close_menu(channel, tab)
    return state


def run() -> tuple[str, dict[str, Any]]:
    summary: dict[str, Any] = {
        "status": "PARTIAL",
        "preflight": None,
        "page_state": None,
        "A_upload_affordance": {},
        "B_models": {},
        "C_deep_research": {},
        "teardown": {},
        "confirmations": {
            "own_tab_only": True,
            "never_enumerated_pages_or_json_list": True,
            "target_6a316aa8_touched": False,
            "send_count": 0,
            "zero_sends": True,
        },
        "blockers": [],
    }
    channel: CdpChannel | None = None
    tab: Any = None
    attached = False

    preflight = preflight_version()
    summary["preflight"] = preflight
    emit("preflight_curl", ok=preflight.get("ok"), browser=preflight.get("browser"), protocol_version=preflight.get("protocol_version"), websocket_url_present=preflight.get("websocket_url_present"), error_code=preflight.get("error_code"))
    if preflight.get("ok") is not True:
        summary["status"] = "CDP_UNREACHABLE"
        summary["blockers"].append({"code": "CDP_UNREACHABLE", "action": "Expose Chrome CDP at 127.0.0.1:9222; no attach attempted."})
        return "CDP_UNREACHABLE", summary

    try:
        selectors = dict(load_selector_map("real"))
        emit("selector_map_loaded", file_input=selectors.get("file_input"), attachment_chip=selectors.get("attachment_chip"), model_trigger=selectors.get("model_picker_trigger_candidates"), tools_button=selectors.get("tools_button"))
        channel = CdpChannel(cdp_endpoint=CDP_ENDPOINT)
        channel.attach()
        attached = True
        emit("attached")
        try:
            tab = channel.open_tab(CHATGPT_URL)
            emit("opened_own_fresh_tab", tab_id=getattr(tab, "tab_id", None), url=CHATGPT_URL)
            channel.wait_for_load_state(tab, timeout_s=30)
        except Exception as exc:  # noqa: BLE001 - contract says open/load failure needs human action.
            summary["blockers"].append({"code": "OPEN_OR_LOAD_FAILED", "error": error_record(exc)})
            emit("open_or_load_failed", error=error_record(exc))
            raise RuntimeError("HUMAN-ACTION-NEEDED") from exc
        pace(1.0)
        state = page_state(channel, tab)
        summary["page_state"] = state
        emit("page_state_after_load", **state)
        if state.get("target_conversation_loaded"):
            summary["confirmations"]["target_6a316aa8_touched"] = True
            raise RuntimeError("PROTECTED_TARGET_LOADED")
        if state.get("challenge_likely") or state.get("login_likely"):
            raise RuntimeError("HUMAN-ACTION-NEEDED")
        if not state.get("has_composer"):
            try:
                channel.wait_for_selector(tab, selectors["composer"], state="visible", timeout_s=10)
            except Exception as exc:  # noqa: BLE001
                summary["blockers"].append({"code": "COMPOSER_UNAVAILABLE", "error": error_record(exc)})
                state = page_state(channel, tab)
                summary["page_state"] = state
                emit("page_state_no_composer", **state)
                raise RuntimeError("HUMAN-ACTION-NEEDED")
        else:
            channel.wait_for_selector(tab, selectors["composer"], state="visible", timeout_s=10)

        # A. Upload affordance.
        UPLOAD_PATH.write_text("m9 upload probe\n", encoding="utf-8")
        file_info_raw = channel.evaluate(
            tab,
            JS_FILE_INPUTS,
            arg={
                "composer_selector": selectors["composer"],
                "tools_selector": selectors["tools_button"],
                "original_selector": selectors["file_input"],
            },
            timeout_s=5.0,
        )
        file_info = file_info_raw if isinstance(file_info_raw, dict) else {"raw_type": type(file_info_raw).__name__}
        chosen_file_selector = file_info.get("preferred_selector") if isinstance(file_info.get("preferred_selector"), str) else selectors["file_input"]
        selectors["file_input"] = str(chosen_file_selector)
        summary["A_upload_affordance"]["file_input_probe"] = file_info
        summary["A_upload_affordance"]["confirmed_file_input_selector"] = selectors["file_input"]
        emit("A_file_input_probe", chosen_selector=selectors["file_input"], info=file_info)
        pace()
        upload_ok = False
        try:
            channel.upload_files(tab, selectors["file_input"], [UPLOAD_PATH])
            upload_ok = True
            summary["A_upload_affordance"]["set_input_files_accepted"] = True
            emit("A_upload_staged", selector=selectors["file_input"], accepted=True, file_name=UPLOAD_NAME)
        except Exception as exc:  # noqa: BLE001 - safe metadata only.
            summary["A_upload_affordance"]["set_input_files_accepted"] = False
            summary["A_upload_affordance"]["upload_error"] = error_record(exc)
            emit("A_upload_staged", selector=selectors["file_input"], accepted=False, error=error_record(exc))
            raise
        pace(1.5)
        production_chip_wait_ok = False
        production_chip_error: dict[str, Any] | None = None
        if upload_ok:
            try:
                channel.wait_for_selector(tab, selectors["attachment_chip"], state="visible", timeout_s=10)
                production_chip_wait_ok = True
            except Exception as exc:  # noqa: BLE001 - safe metadata only.
                production_chip_error = error_record(exc)
            chip_raw = channel.evaluate(
                tab,
                JS_ATTACHMENT_CANDIDATES,
                arg={
                    "composer_selector": selectors["composer"],
                    "attachment_selector": selectors["attachment_chip"],
                    "file_name": UPLOAD_NAME,
                },
                timeout_s=5.0,
            )
            chip_info = chip_raw if isinstance(chip_raw, dict) else {"raw_type": type(chip_raw).__name__}
            real_chip_selector = choose_attachment_selector(chip_info, selectors["attachment_chip"])
            summary["A_upload_affordance"].update(
                {
                    "production_attachment_chip_selector": selectors["attachment_chip"],
                    "production_chip_wait_visible": production_chip_wait_ok,
                    "production_chip_wait_error": production_chip_error,
                    "attachment_chip_probe": chip_info,
                    "real_attachment_chip_selector": real_chip_selector,
                }
            )
            emit("A_attachment_chip_probe", production_wait_visible=production_chip_wait_ok, production_error=production_chip_error, real_selector=real_chip_selector, info=chip_info)
        pace()
        channel.reload(tab)
        channel.wait_for_load_state(tab, timeout_s=30)
        try:
            channel.wait_for_selector(tab, selectors["composer"], state="visible", timeout_s=15)
        except Exception as exc:  # noqa: BLE001
            summary["A_upload_affordance"]["reload_wait_error"] = error_record(exc)
            raise RuntimeError("HUMAN-ACTION-NEEDED") from exc
        pace(1.0)
        empty_raw = channel.evaluate(
            tab,
            JS_COMPOSER_EMPTY,
            arg={
                "composer_selector": selectors["composer"],
                "attachment_selector": summary["A_upload_affordance"].get("real_attachment_chip_selector") or selectors["attachment_chip"],
                "file_name": UPLOAD_NAME,
            },
            timeout_s=5.0,
        )
        empty_info = empty_raw if isinstance(empty_raw, dict) else {"raw_type": type(empty_raw).__name__}
        summary["A_upload_affordance"]["after_reload_empty"] = empty_info
        emit("A_reload_discard_confirm", info=empty_info)

        # B. GPT-5.5 family submenu model selection.
        model_trigger_before = model_trigger_labels(channel, tab, selectors["model_picker_trigger_candidates"])
        original_model = current_model_label(channel, tab, selectors["model_picker_trigger_candidates"])
        menus.open_radix_menu(tab, selectors["model_picker_trigger_candidates"])
        top_options = option_records(menus.enumerate_radix_options(tab))
        current_checked = [item for item in top_options if item.get("checked") is True]
        summary["B_models"].update(
            {
                "original_model_label": original_model,
                "trigger_labels_before": model_trigger_before,
                "top_level_options": top_options,
                "top_level_checked_options": current_checked,
            }
        )
        emit("B_model_top_level", original_model_label=original_model, trigger_labels=model_trigger_before, top_level_options=top_options, checked=current_checked)
        close_menu(channel, tab)
        pace()

        menus.open_radix_menu(tab, selectors["model_picker_trigger_candidates"])
        family_option = find_option([item for item in top_options if item.get("role") == "menuitem"], "GPT-5.5")
        family_label = str(family_option.get("label")) if isinstance(family_option, Mapping) and family_option.get("label") else "GPT-5.5"
        submenu_open_result: Any = None
        submenu_info: dict[str, Any] = {}
        try:
            submenu_open_result = channel.evaluate(
                tab,
                "ask_chatgpt_menu_click_label",
                arg={"label": family_label, "role": "menuitem", "path": [], "action": "open_submenu"},
                timeout_s=5.0,
            )
            pace(1.0)
            submenu_raw = channel.evaluate(
                tab,
                JS_ALL_PORTAL_OPTIONS,
                arg={
                    "portal_selector": selectors["radix_portal"],
                    "family_label": family_label,
                    "top_pairs": [{"label": item.get("label"), "role": item.get("role")} for item in top_options],
                },
                timeout_s=5.0,
            )
            submenu_info = submenu_raw if isinstance(submenu_raw, dict) else {"raw_type": type(submenu_raw).__name__}
        except Exception as exc:  # noqa: BLE001 - safe metadata only.
            submenu_info = {"error": error_record(exc)}
        finally:
            close_menu(channel, tab)
        sub_entries = [item for item in submenu_info.get("sub_entries_guess", []) if isinstance(item, dict)] if isinstance(submenu_info.get("sub_entries_guess"), list) else []
        summary["B_models"].update(
            {
                "family_label_requested": "GPT-5.5",
                "family_label_found": family_label,
                "family_top_option": family_option,
                "submenu_open_result": submenu_open_result,
                "submenu_probe": submenu_info,
                "gpt55_sub_entries": sub_entries,
            }
        )
        emit("B_gpt55_submenu", family_label=family_label, open_result=submenu_open_result, sub_entries=sub_entries, submenu_probe=submenu_info)
        pace()

        current_sub_labels = {str(item.get("label")) for item in sub_entries if item.get("checked") is True and item.get("label")}
        subentry_to_test = None
        for item in sub_entries:
            if item.get("disabled") is True:
                continue
            label = item.get("label")
            if not isinstance(label, str) or not label:
                continue
            if item.get("checked") is True:
                continue
            if original_model and normalize_label(label) == normalize_label(original_model):
                continue
            subentry_to_test = label
            break
        summary["B_models"]["current_checked_sub_entries"] = sorted(current_sub_labels)
        summary["B_models"]["subentry_test_label"] = subentry_to_test
        if subentry_to_test:
            summary["B_models"]["select_model_subentry_attempt"] = select_model_attempt(tab, selectors, subentry_to_test, channel)
        else:
            summary["B_models"]["select_model_subentry_attempt"] = {"skipped": True, "reason": "no_non_current_enabled_subentry_found"}
            emit("B_select_model_subentry_skipped", reason="no_non_current_enabled_subentry_found")
        summary["B_models"]["select_model_family_attempt"] = select_model_attempt(tab, selectors, "GPT-5.5", channel)

        restore_info: dict[str, Any] = {"needed": False, "attempted": False, "ok": None, "error": None, "after_trigger_labels": None}
        after_model = current_model_label(channel, tab, selectors["model_picker_trigger_candidates"])
        any_selection_ok = any(
            isinstance(summary["B_models"].get(key), dict) and summary["B_models"][key].get("ok") is True
            for key in ("select_model_subentry_attempt", "select_model_family_attempt")
        )
        if original_model and (any_selection_ok or (after_model and normalize_label(after_model) != normalize_label(original_model))):
            restore_info["needed"] = True
            restore_info["attempted"] = True
            try:
                result = menus.select_model(tab, selectors, original_model)
                restore_info.update({"ok": True, "result": selection_result_record(result)})
            except Exception as exc:  # noqa: BLE001 - safe metadata only.
                restore_info.update({"ok": False, "error": error_record(exc)})
            finally:
                close_menu(channel, tab)
                restore_info["after_trigger_labels"] = model_trigger_labels(channel, tab, selectors["model_picker_trigger_candidates"])
        else:
            restore_info["after_trigger_labels"] = model_trigger_labels(channel, tab, selectors["model_picker_trigger_candidates"])
        summary["B_models"]["restore_original_model"] = restore_info
        emit("B_model_restore", info=restore_info)
        pace()

        # C. Deep Research tool selection.
        tools_initial = tool_state(channel, tab, selectors, "Deep research")
        deep_present = tools_initial.get("target") is not None
        summary["C_deep_research"]["initial_tools_menu"] = tools_initial
        summary["C_deep_research"]["deep_research_present"] = deep_present
        emit("C_tools_initial", deep_research_present=deep_present, tools=tools_initial)
        pace()
        set_tools_info: dict[str, Any] = {"attempted": False, "ok": False, "result": None, "error": None}
        if deep_present:
            set_tools_info["attempted"] = True
            try:
                result = menus.set_tools(tab, selectors, ["Deep research"])
                set_tools_info.update({"ok": True, "result": [selection_result_record(item) for item in result]})
            except Exception as exc:  # noqa: BLE001 - safe metadata only.
                set_tools_info["error"] = error_record(exc)
            finally:
                close_menu(channel, tab)
        else:
            set_tools_info["error"] = {"type": "Absent", "message": "Deep research option was not present"}
        summary["C_deep_research"]["set_tools_deep_research"] = set_tools_info
        emit("C_set_tools_deep_research", info=set_tools_info)
        pace()
        after_set_state = tool_state(channel, tab, selectors, "Deep research")
        summary["C_deep_research"]["after_set_tools_menu"] = after_set_state
        emit("C_after_set_tools_state", state=after_set_state)
        pace()
        deselect_info: dict[str, Any] = {"attempted": False, "clicked": False, "ok": None, "error": None, "after": None}
        target_state = after_set_state.get("target") if isinstance(after_set_state.get("target"), Mapping) else None
        if target_state and target_state.get("checked") is True:
            deselect_info["attempted"] = True
            try:
                menus.open_radix_menu(tab, selectors["tools_button"])
                selected = menus.select_radix_label(tab, "Deep research")
                deselect_info["clicked"] = True
                deselect_info["selected_option"] = {
                    "label": selected.label,
                    "role": selected.role,
                    "checked_before_click": selected.checked,
                    "disabled": selected.disabled,
                }
            except Exception as exc:  # noqa: BLE001 - safe metadata only.
                deselect_info["error"] = error_record(exc)
            finally:
                close_menu(channel, tab)
                pace()
            final_state = tool_state(channel, tab, selectors, "Deep research")
            deselect_info["after"] = final_state
            after_target = final_state.get("target") if isinstance(final_state.get("target"), Mapping) else None
            deselect_info["ok"] = bool(after_target and after_target.get("checked") is False)
        else:
            deselect_info["after"] = after_set_state
            deselect_info["ok"] = bool(target_state and target_state.get("checked") is False)
        summary["C_deep_research"]["deselect_restore"] = deselect_info
        emit("C_deep_research_deselect", info=deselect_info)

        summary["status"] = "DONE"
        return "DONE", summary
    except RuntimeError as exc:
        code = str(exc)
        if code == "HUMAN-ACTION-NEEDED":
            summary["status"] = "HUMAN-ACTION-NEEDED"
            summary["blockers"].append({"code": "HUMAN-ACTION-NEEDED", "action": "Human must clear login/Cloudflare/challenge; no bypass attempted."})
            emit("stopped", status="HUMAN-ACTION-NEEDED", code="HUMAN-ACTION-NEEDED")
            return "HUMAN-ACTION-NEEDED", summary
        if code == "PROTECTED_TARGET_LOADED":
            summary["status"] = "BLOCKED"
            summary["blockers"].append({"code": "PROTECTED_TARGET_LOADED", "action": f"Fresh tab resolved to protected target {TARGET_FULL}; stopped."})
            emit("stopped", status="BLOCKED", code="PROTECTED_TARGET_LOADED")
            return "BLOCKED", summary
        summary["status"] = "PARTIAL"
        summary["blockers"].append({"code": type(exc).__name__, "message": str(exc)})
        emit("driver_runtime_error", error=error_record(exc))
        return "PARTIAL", summary
    except Exception as exc:  # noqa: BLE001 - safe metadata only.
        summary["status"] = "PARTIAL"
        summary["blockers"].append({"code": type(exc).__name__, "error": error_record(exc)})
        emit("driver_error", error=error_record(exc))
        return "PARTIAL", summary
    finally:
        if channel is not None and attached:
            try:
                channel.detach()
                emit("detached")
            except Exception as exc:  # noqa: BLE001 - safe metadata only.
                summary["blockers"].append({"code": "DETACH_FAILED", "error": error_record(exc)})
                emit("detach_error", error=error_record(exc))
        post = preflight_version()
        summary["teardown"]["post_detach_preflight"] = post
        summary["teardown"]["browser_alive_post_detach"] = post.get("ok") is True
        emit("post_detach_curl", ok=post.get("ok"), browser=post.get("browser"), protocol_version=post.get("protocol_version"), websocket_url_present=post.get("websocket_url_present"), error_code=post.get("error_code"))


def main() -> int:
    status, summary = run()
    emit("FINAL_RESULT", status=status, summary=summary)
    return 0 if status in {"DONE", "PARTIAL", "HUMAN-ACTION-NEEDED", "CDP_UNREACHABLE", "BLOCKED"} else 1


if __name__ == "__main__":
    sys.exit(main())
