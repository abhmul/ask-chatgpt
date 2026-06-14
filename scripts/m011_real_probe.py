#!/usr/bin/env python3
"""M-011 real-site CDP tools-menu + Deep Research discovery probe.

Attach-only discovery tooling for an operator-launched Chrome over CDP. This
script never launches a browser, never automates login, and writes only redacted
M-011 discovery artifacts under orchestration/reports/M-011/.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import time
from typing import Any

from playwright.sync_api import Error as PlaywrightError  # noqa: E402

from m010_real_probe import (  # noqa: E402
    redact, _emit, _emit_human_action_needed,
    connect, recheck_safe, HUMAN_ERRORS, HumanActionStop,
    BASE_URL, CDP_ENDPOINT, HUMAN_PACE_S,
)

REPORT_DIR = Path(__file__).resolve().parents[1] / "orchestration" / "reports" / "M-011"
AUDIT_LOG = REPORT_DIR / "real-audit-log.md"
DR_PROMPT = "Compare LFP vs NMC lithium battery chemistries for consumer EVs in exactly 3 bullet points, with a source per bullet."
CLARIFY_ANSWER = "Keep it brief — 3 bullets, consumer-EV context, recent sources; no need to go deep."

AUDIT_DATA_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")
AUDIT_HEADER = """# M-011 — Real-site per-message audit log (transparency, not rationing)

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
"""

_audit_next: int | None = None


def _md_cell(value: object) -> str:
    text = redact("n/a" if value is None else value)
    return text.replace("\r", " ").replace("\n", "\\n").replace("|", "\\|")


def _initial_audit_number() -> int:
    if not AUDIT_LOG.exists():
        return 0
    try:
        lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    return sum(1 for line in lines if AUDIT_DATA_ROW_RE.match(line))


def audit(row: dict[str, object]) -> None:
    global _audit_next
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not AUDIT_LOG.exists():
        AUDIT_LOG.write_text(AUDIT_HEADER, encoding="utf-8")
    if _audit_next is None:
        _audit_next = _initial_audit_number()
    number = _audit_next
    _audit_next += 1
    timestamp = datetime.now().astimezone().isoformat()
    cells = [
        number,
        timestamp,
        row.get("leg", "n/a"),
        row.get("action", "n/a"),
        row.get("prompt-label", "n/a"),
        row.get("observation", "n/a"),
        row.get("markers", "n/a"),
        row.get("result", "n/a"),
    ]
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write("| " + " | ".join(_md_cell(c) for c in cells) + " |\n")


def _write_json(path: Path, payload: Any) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(json.dumps(payload, indent=2, sort_keys=True, default=str)), encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(redact(json.dumps(payload, sort_keys=True, default=str)) + "\n")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _require_page(session: Any) -> Any:
    page = session.page
    if page is None:
        raise RuntimeError("Browser page is unavailable after connect")
    return page


def _selector_count(page: Any, selector: str | None) -> int:
    if not selector:
        return 0
    try:
        return int(page.locator(selector).count())
    except PlaywrightError:
        return -1


def _human_label(exc: BaseException) -> str:
    return "CHALLENGE_PRESENT" if exc.__class__.__name__ == "ChallengePresentError" else exc.__class__.__name__


# Copied verbatim from scripts/m010_real_probe.py::_MODEL_ENUMERATE_JS for the named leak-guard helpers.
_M010_JS_HELPERS = r'''
  // Privacy: never emit the operator's identity. Skip the account/profile control entirely and
  // drop any aria-label that mentions a profile/account so personal names never reach an artifact.
  function isAccount(el) {
    const t = (el.getAttribute('data-testid') || '').toLowerCase();
    const a = (el.getAttribute('aria-label') || '').toLowerCase();
    return t.includes('account') || t.includes('profile') || a.includes('profile menu')
        || a.includes('open profile') || a.includes('account');
  }
  function safeAria(el) {
    const a = el.getAttribute('aria-label');
    if (!a) return null;
    const low = a.toLowerCase();
    if (low.includes('profile') || low.includes('account') || low.includes('open project options')
        || low.includes('conversation options')) return '<omitted>';
    return a.slice(0, 60);
  }
  function ownText(el) {
    let s = '';
    for (const n of el.childNodes) if (n.nodeType === 3) s += n.textContent;
    return s.replace(/\s+/g, ' ').trim();
  }

  const MODEL_RE = /gpt|chatgpt|thinking|legacy|^auto$|\bauto\b|o[1-9]|[45]\.\d/i;
  const NON_MODEL_TEXT = '<non-model-text>';
  const NON_MODEL_ARIA = '<non-model-aria>';
  const SENSITIVE_TEXT_RE = /\b(account|profile|email|avatar|personal|plan|billing|subscription)\b|user[-_ ]?menu|display[-_ ]?name/i;

  function compact(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }
  function rawVisibleText(el) {
    return String(el.innerText || el.textContent || '').trim();
  }
  function textLooksSafeModel(value) {
    const text = compact(value);
    return !!text && MODEL_RE.test(text) && !SENSITIVE_TEXT_RE.test(text);
  }
  function attrBlob(el) {
    return [
      el.getAttribute('data-testid') || '',
      el.getAttribute('aria-label') || '',
      el.getAttribute('id') || '',
      el.getAttribute('class') || '',
      el.getAttribute('role') || '',
    ].join(' ').toLowerCase();
  }
  function isSensitive(el) {
    let cur = el;
    let hops = 0;
    while (cur && cur.nodeType === 1 && hops < 7) {
      if (isAccount(cur)) return true;
      if (SENSITIVE_TEXT_RE.test(attrBlob(cur))) return true;
      cur = cur.parentElement;
      hops += 1;
    }
    return false;
  }
  function isVisible(el) {
    if (!el || !(el instanceof Element)) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.right >= 0
        && rect.top <= (window.innerHeight || document.documentElement.clientHeight)
        && rect.left <= (window.innerWidth || document.documentElement.clientWidth);
  }
  function qAttr(value) {
    return JSON.stringify(String(value));
  }
  function selectorCount(selector) {
    try { return document.querySelectorAll(selector).length; } catch (e) { return -1; }
  }
  function structuralPath(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.body) {
      const tag = (cur.tagName || '').toLowerCase();
      if (!tag) break;
      let nth = 1;
      let prev = cur.previousElementSibling;
      while (prev) {
        if ((prev.tagName || '').toLowerCase() === tag) nth += 1;
        prev = prev.previousElementSibling;
      }
      parts.unshift(tag + ':nth-of-type(' + nth + ')');
      cur = cur.parentElement;
    }
    if (cur === document.body) return 'body > ' + parts.join(' > ');
    return parts.join(' > ');
  }
  function uniqueSelector(el) {
    const tag = (el.tagName || '').toLowerCase() || '*';
    const tid = el.getAttribute('data-testid');
    if (tid) {
      const selector = tag + '[data-testid=' + qAttr(tid) + ']';
      return {selector, count: selectorCount(selector), basis: 'testid'};
    }
    const role = el.getAttribute('role');
    if (role) {
      const selector = tag + '[role=' + qAttr(role) + ']';
      if (selectorCount(selector) === 1) return {selector, count: 1, basis: 'role'};
    }
    const aria = el.getAttribute('aria-label');
    if (aria && textLooksSafeModel(aria)) {
      const selector = tag + '[aria-label=' + qAttr(aria) + ']';
      if (selectorCount(selector) >= 1) return {selector, count: selectorCount(selector), basis: 'model-aria'};
    }
    const state = el.getAttribute('data-state');
    const haspopup = el.getAttribute('aria-haspopup');
    if (state && haspopup) {
      const selector = tag + '[data-state=' + qAttr(state) + '][aria-haspopup=' + qAttr(haspopup) + ']';
      if (selectorCount(selector) === 1) return {selector, count: 1, basis: 'state+haspopup'};
    }
    const path = structuralPath(el);
    return {selector: path, count: selectorCount(path), basis: 'structural-path'};
  }
  function rectShape(el) {
    const r = el.getBoundingClientRect();
    return {top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width), height: Math.round(r.height)};
  }
'''

_JS_LABEL_GATES = r'''
  const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+/;            // never emit anything email-shaped
  const LONGID_RE = /[A-Za-z0-9_-]{20,}/;                          // never emit long id/token-shaped tokens
  function labelSafe(value){                                       // gate for tool/option labels
    const t = compact(value);
    if(!t) return false;
    if(t.length > 80) return false;
    if(SENSITIVE_TEXT_RE.test(t)) return false;
    if(EMAIL_RE.test(t)) return false;
    if(t.indexOf('@') !== -1) return false;
    if(LONGID_RE.test(t)) return false;
    return true;
  }
  function gatedLabel(value, limit){ const t = compact(value); return labelSafe(t) ? t.slice(0, limit||80) : '<omitted-or-unsafe>'; }
'''

_TOOLS_ENUMERATE_JS = r'''() => {
''' + _M010_JS_HELPERS + _JS_LABEL_GATES + r'''
  const MODEL_PICKER_SELECTOR = 'form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])';
  const TOOLISH_RE = /\b(tool|tools|add|attach|attachment|upload|paperclip|plus|compose|composer|create|image|file|canvas|research)\b|\+/i;
  const MODELISH_RE = /\b(model|switcher|reasoning|thinking effort|effort|instant|medium|extra high|pro extended|gpt|chatgpt)\b/i;
  const UPGRADE_LOCK_RE = /\b(upgrade|locked?|paid|plus|pro|team|enterprise|unavailable|disabled|subscribe|plan)\b/i;

  function isDisabled(el) {
    return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.getAttribute('data-disabled') === 'true'
        || !!el.closest('[aria-disabled=true], [data-disabled=true], [disabled]');
  }
  function safeAriaLabel(el) {
    const a = safeAria(el);
    if (!a || a === '<omitted>') return a;
    return gatedLabel(a, 80);
  }
  function promptElement() { return document.querySelector('#prompt-textarea'); }
  function composerForm() { const p = promptElement(); return p ? p.closest('form') : null; }
  function composerRoots() {
    const p = promptElement();
    if (!p) return [];
    const roots = [];
    const form = composerForm();
    if (form) roots.push(form);
    let cur = p.parentElement;
    let hops = 0;
    while (cur && cur !== document.body && hops < 8) {
      const r = cur.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.height <= 420) roots.push(cur);
      cur = cur.parentElement;
      hops += 1;
    }
    return Array.from(new Set(roots));
  }
  function isNearComposer(el) {
    const roots = composerRoots();
    if (roots.some((root) => root.contains(el))) return true;
    const p = promptElement();
    if (!p) return false;
    const pr = p.getBoundingClientRect();
    const er = el.getBoundingClientRect();
    const vertical = Math.abs(((er.top + er.bottom) / 2) - ((pr.top + pr.bottom) / 2));
    const overlapsX = er.right >= pr.left - 180 && er.left <= pr.right + 180;
    return vertical <= 180 && overlapsX;
  }
  function isKnownModelPicker(el) {
    let matches = false;
    try { matches = el.matches(MODEL_PICKER_SELECTOR); } catch (e) { matches = false; }
    const blob = attrBlob(el);
    const text = compact(ownText(el) || rawVisibleText(el));
    return matches && MODELISH_RE.test(blob + ' ' + text) && !TOOLISH_RE.test(blob + ' ' + text);
  }
  function baseShape(el) {
    return {
      tag: (el.tagName || '').toLowerCase(),
      testid: el.getAttribute('data-testid'),
      role: el.getAttribute('role'),
      aria_label: safeAriaLabel(el),
      aria_haspopup: el.getAttribute('aria-haspopup'),
      aria_expanded: el.getAttribute('aria-expanded'),
      aria_checked: el.getAttribute('aria-checked'),
      aria_selected: el.getAttribute('aria-selected'),
      data_state: el.getAttribute('data-state'),
      data_radix_collection_item: el.hasAttribute('data-radix-collection-item'),
      disabled: isDisabled(el),
    };
  }
  function shapeFor(el) {
    const unique = uniqueSelector(el);
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      label: gatedLabel(ownText(el) || safeAria(el) || rawVisibleText(el), 80),
    });
  }
  function triggerReasons(el) {
    const blob = attrBlob(el);
    const text = compact(ownText(el) || rawVisibleText(el));
    const joined = blob + ' ' + text.toLowerCase();
    const reasons = [];
    if (!isNearComposer(el)) return reasons;
    if (isKnownModelPicker(el)) return reasons;
    if (el.getAttribute('aria-haspopup') === 'menu') reasons.push('composer-aria-haspopup-menu');
    if (/tool|tools/.test(joined)) reasons.push('tools-attr-or-text');
    if (/add|plus|composer-plus|compose/.test(joined) || text === '+' || text === '＋') reasons.push('add-plus-attr-or-text');
    if (/attach|attachment|upload|paperclip|file/.test(joined)) reasons.push('attach-upload-file-attr-or-text');
    if (/create|image|canvas|research/.test(joined)) reasons.push('tool-family-attr-or-text');
    if (text === '+' || text === '＋') reasons.push('visible-plus');
    return reasons;
  }
  function triggerScore(shape) {
    const reasons = shape.candidate_reasons || [];
    let score = 0;
    if (reasons.includes('visible-plus')) score += 100;
    if (reasons.includes('add-plus-attr-or-text')) score += 80;
    if (reasons.includes('tools-attr-or-text')) score += 70;
    if (reasons.includes('attach-upload-file-attr-or-text')) score += 45;
    if (reasons.includes('tool-family-attr-or-text')) score += 25;
    if (reasons.includes('composer-aria-haspopup-menu')) score += 20;
    if (shape.disabled) score -= 1000;
    score -= Math.max(0, Math.round((shape.rect.top || 0) / 1000));
    return score;
  }
  function optionKind(el) {
    const role = el.getAttribute('role');
    if (el.getAttribute('aria-haspopup') === 'menu') return 'submenu';
    if (role === 'menuitemradio' || role === 'menuitemcheckbox' || el.getAttribute('aria-checked') !== null) return 'toggle';
    return 'one-shot';
  }
  function optionShape(el) {
    const unique = uniqueSelector(el);
    const raw = rawVisibleText(el);
    const label = gatedLabel(raw || ownText(el) || safeAria(el), 80);
    const rawBlob = raw + ' ' + attrBlob(el);
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      kind: optionKind(el),
      label,
      paid_or_disabled: isDisabled(el) || el.getAttribute('aria-disabled') === 'true' || UPGRADE_LOCK_RE.test(rawBlob),
    });
  }
  function visibleCount(selector) {
    try { return Array.from(document.querySelectorAll(selector)).filter((el) => isVisible(el) && !isSensitive(el)).length; }
    catch (e) { return -1; }
  }
  function portalRoots() {
    const roots = [];
    const seen = new Set();
    const rootSelector = '[data-radix-popper-content-wrapper], [role="menu"], [data-radix-menu-content], [data-radix-dropdown-menu-content]';
    Array.from(document.querySelectorAll(rootSelector)).forEach((el) => {
      if (!isVisible(el) || isSensitive(el)) return;
      const unique = uniqueSelector(el);
      if (!unique.selector || seen.has(unique.selector)) return;
      seen.add(unique.selector);
      roots.push(Object.assign(baseShape(el), {selector: unique.selector, selector_count: unique.count, selector_basis: unique.basis, rect: rectShape(el)}));
    });
    return roots;
  }
  function portalOptions() {
    const options = [];
    const seen = new Set();
    const optionSelector = [
      '[data-radix-popper-content-wrapper] [role="menuitem"]',
      '[data-radix-popper-content-wrapper] [role="menuitemradio"]',
      '[data-radix-popper-content-wrapper] [role="menuitemcheckbox"]',
      '[data-radix-popper-content-wrapper] [role="option"]',
      '[role="menu"] [role="menuitem"]',
      '[role="menu"] [role="menuitemradio"]',
      '[role="menu"] [role="menuitemcheckbox"]',
      '[role="menu"] [role="option"]'
    ].join(', ');
    Array.from(document.querySelectorAll(optionSelector)).forEach((el) => {
      if (!isVisible(el) || isSensitive(el)) return;
      if (seen.has(el)) return;
      seen.add(el);
      options.push(optionShape(el));
    });
    return options;
  }
  function selectorCounts() {
    const candidates = [
      '[data-radix-popper-content-wrapper] [role="menuitem"]',
      '[data-radix-popper-content-wrapper] [role="menuitemradio"]',
      '[data-radix-popper-content-wrapper] [role="menuitemcheckbox"]',
      '[data-radix-popper-content-wrapper] [role="option"]',
      '[role="menu"] [role="menuitem"]',
      '[role="menu"] [role="menuitemradio"]',
      '[role="menu"] [role="menuitemcheckbox"]',
      '[role="menu"] [role="option"]'
    ];
    return candidates.map((selector) => ({selector, visible_count: visibleCount(selector), dom_count: selectorCount(selector)}));
  }
  function armedState() {
    const chips = [];
    const seen = new Set();
    const roots = composerRoots();
    const chipSelector = 'button, [role="button"], [data-testid], [aria-label], span, div';
    roots.forEach((root) => {
      Array.from(root.querySelectorAll(chipSelector)).forEach((el) => {
        if (!isVisible(el) || isSensitive(el)) return;
        const label = gatedLabel(rawVisibleText(el) || ownText(el) || safeAria(el), 80);
        if (label === '<omitted-or-unsafe>' || !/deep\s*research|research/i.test(label)) return;
        const unique = uniqueSelector(el);
        if (!unique.selector || seen.has(unique.selector)) return;
        seen.add(unique.selector);
        let remove = null;
        const removeEl = Array.from(el.querySelectorAll('button, [role="button"], [aria-label]')).find((child) => {
          const b = attrBlob(child) + ' ' + compact(rawVisibleText(child)).toLowerCase();
          return /remove|clear|close|dismiss|x\b/.test(b);
        });
        if (removeEl && !isSensitive(removeEl)) {
          const ru = uniqueSelector(removeEl);
          remove = {selector: ru.selector, selector_count: ru.count, role: removeEl.getAttribute('role'), aria_label: safeAriaLabel(removeEl)};
        }
        chips.push({selector: unique.selector, selector_count: unique.count, role: el.getAttribute('role'), label, rect: rectShape(el), remove_affordance: remove});
      });
    });
    return {
      composer_present: !!promptElement(),
      chip_count: chips.length,
      deep_research_armed: chips.some((chip) => /deep\s*research/i.test(chip.label || '')),
      chips,
    };
  }

  const out = {
    url_path: location.pathname.replace(/\/c\/[^/?#\s]+/g, '/c/<redacted>'),
    hydrated_markers: {
      ready_root_present: document.querySelectorAll('main:has(#prompt-textarea)').length,
      composer_present: document.querySelectorAll('#prompt-textarea').length,
      composer_form_present: composerForm() ? 1 : 0,
    },
    trigger_candidates: [],
    best_trigger: null,
    best_trigger_reason: null,
    portal_roots: [],
    options: [],
    option_selector_counts: [],
    deep_research_option: null,
    armed_state: null,
  };

  const seenTriggers = new Set();
  const clickableSelector = 'button, [role="button"], [aria-haspopup], [data-state]';
  Array.from(document.querySelectorAll(clickableSelector)).forEach((el) => {
    if (!isVisible(el) || isSensitive(el)) return;
    const reasons = triggerReasons(el);
    if (!reasons.length) return;
    const shape = shapeFor(el);
    if (!shape.selector || seenTriggers.has(shape.selector)) return;
    seenTriggers.add(shape.selector);
    shape.candidate_reasons = reasons;
    shape.trigger_score = triggerScore(shape);
    out.trigger_candidates.push(shape);
  });
  out.trigger_candidates.sort((a, b) => b.trigger_score - a.trigger_score || a.rect.top - b.rect.top || a.rect.left - b.rect.left);
  if (out.trigger_candidates.length) {
    out.best_trigger = out.trigger_candidates[0];
    out.best_trigger_reason = (out.best_trigger.candidate_reasons || []).join(',') || 'highest-score';
  }

  out.portal_roots = portalRoots();
  out.options = portalOptions();
  out.option_selector_counts = selectorCounts();
  out.deep_research_option = out.options.find((opt) => /deep\s*research/i.test(opt.label || '')) || null;
  out.armed_state = armedState();
  return out;
}'''

_DR_STATE_JS = r'''(args) => {
''' + _M010_JS_HELPERS + _JS_LABEL_GATES + r'''
  args = args || {};
  const startedAtMs = Number(args.started_at_ms || Date.now());
  const nowMs = Date.now();
  const ASSISTANT_SELECTOR = '[data-message-author-role="assistant"]';
  const STOP_SELECTOR = 'button[data-testid="stop-button"]';
  const COPY_SELECTOR = 'button[data-testid="copy-turn-action-button"]';
  const COMPOSER_SELECTOR = '#prompt-textarea';
  const DR_VOCAB_RE = /research|searching|reading|browsing|analyz|thinking|sources?|activity|steps?|working|planning/i;

  function isDisabled(el) {
    return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.getAttribute('data-disabled') === 'true'
        || !!el.closest('[aria-disabled=true], [data-disabled=true], [disabled]');
  }
  function safeAriaLabel(el) {
    const a = safeAria(el);
    if (!a || a === '<omitted>') return a;
    return gatedLabel(a, 80);
  }
  function visibleCount(selector) {
    try { return Array.from(document.querySelectorAll(selector)).filter((el) => isVisible(el) && !isSensitive(el)).length; }
    catch (e) { return -1; }
  }
  function latestAssistantTurn() {
    const turns = Array.from(document.querySelectorAll(ASSISTANT_SELECTOR)).filter((el) => isVisible(el) && !isSensitive(el));
    return turns.length ? turns[turns.length - 1] : null;
  }
  function allAssistantTurns() {
    return Array.from(document.querySelectorAll(ASSISTANT_SELECTOR)).filter((el) => isVisible(el) && !isSensitive(el));
  }
  function gatedLines(el, maxLines) {
    if (!el) return [];
    const lines = String(rawVisibleText(el) || '').split(/\n+/).map((line) => compact(line)).filter(Boolean);
    const out = [];
    for (const line of lines) {
      const gated = gatedLabel(line, 80);
      if (gated && !out.includes(gated)) out.push(gated);
      if (out.length >= maxLines) break;
    }
    return out;
  }
  function elementShape(el) {
    const unique = uniqueSelector(el);
    return {selector: unique.selector, selector_count: unique.count, selector_basis: unique.basis, role: el.getAttribute('role'), aria_label: safeAriaLabel(el), rect: rectShape(el)};
  }
  function composerState() {
    const composer = document.querySelector(COMPOSER_SELECTOR);
    if (!composer || !isVisible(composer) || isSensitive(composer)) return {present: false, editable: false};
    const editable = composer.isContentEditable || composer.getAttribute('contenteditable') === 'true' || /textarea|input/i.test(composer.tagName || '');
    return {present: true, editable: !!editable && !isDisabled(composer)};
  }
  function progressUi() {
    const texts = [];
    const shapes = [];
    const seenText = new Set();
    const seenShape = new Set();
    const candidates = Array.from(document.querySelectorAll('main [role="status"], main [aria-live], main [data-testid], main ' + ASSISTANT_SELECTOR + ' *'));
    let count = 0;
    candidates.forEach((el) => {
      if (!isVisible(el) || isSensitive(el)) return;
      const raw = compact(rawVisibleText(el) || ownText(el) || safeAria(el));
      if (!raw || !DR_VOCAB_RE.test(raw)) return;
      count += 1;
      const gated = gatedLabel(raw, 80);
      if (gated !== '<omitted-or-unsafe>' && !seenText.has(gated) && texts.length < 6) {
        seenText.add(gated);
        texts.push(gated);
      }
      const unique = uniqueSelector(el);
      if (unique.selector && !seenShape.has(unique.selector) && shapes.length < 5) {
        seenShape.add(unique.selector);
        shapes.push({selector: unique.selector, selector_count: unique.count, selector_basis: unique.basis, role: el.getAttribute('role'), rect: rectShape(el)});
      }
    });
    return {present: count > 0, gated_texts: texts, element_count: count, element_shapes: shapes};
  }
  function suggestionChips(latest) {
    const chips = [];
    const seen = new Set();
    const roots = [];
    if (latest) roots.push(latest);
    const main = document.querySelector('main');
    if (main) roots.push(main);
    roots.forEach((root) => {
      Array.from(root.querySelectorAll('button, [role="button"], [data-testid*="suggest"], [data-testid*="chip"]')).forEach((el) => {
        if (!isVisible(el) || isSensitive(el) || isDisabled(el)) return;
        const label = gatedLabel(rawVisibleText(el) || ownText(el) || safeAria(el), 80);
        if (label === '<omitted-or-unsafe>' || seen.has(label)) return;
        seen.add(label);
        if (chips.length < 6) chips.push({label, role: el.getAttribute('role'), selector: uniqueSelector(el).selector});
      });
    });
    return chips;
  }
  function reportStructure(latest) {
    if (!latest) {
      return {present: false, heading_count: 0, listitem_count: 0, paragraph_count: 0, link_count: 0, has_sources_panel: false, has_numbered_citations: false, gated_snippets: [], report_turn_selector: null};
    }
    const headings = latest.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]');
    const listitems = latest.querySelectorAll('li,[role="listitem"]');
    const paragraphs = latest.querySelectorAll('p');
    const links = latest.querySelectorAll('a[href]');
    const text = compact(rawVisibleText(latest));
    const hasSources = /\b(sources?|references?|citations?)\b/i.test(text) || Array.from(latest.querySelectorAll('[data-testid], [aria-label]')).some((el) => /source|citation|reference/i.test(attrBlob(el)));
    const hasNumbered = /(?:\[\d+\]|\(\d+\)|\b\d+\s*[.)]\s+)/.test(text);
    const present = (listitems.length >= 2 || paragraphs.length >= 2 || links.length >= 1 || headings.length >= 1) && text.length > 20;
    const unique = uniqueSelector(latest);
    return {
      present,
      heading_count: headings.length,
      listitem_count: listitems.length,
      paragraph_count: paragraphs.length,
      link_count: links.length,
      has_sources_panel: hasSources,
      has_numbered_citations: hasNumbered,
      gated_snippets: present ? gatedLines(latest, 6) : [],
      report_turn_selector: unique.selector,
      report_turn_selector_count: unique.count,
    };
  }
  function citationStructure(latest) {
    if (!latest) return {link_count: 0, citation_like_count: 0, selectors: []};
    const selector = 'a[href], sup, [data-testid*="citation"], [aria-label*="citation"], [data-testid*="source"], [aria-label*="source"]';
    const nodes = Array.from(latest.querySelectorAll(selector)).filter((el) => isVisible(el) && !isSensitive(el));
    const shapes = [];
    const seen = new Set();
    nodes.forEach((el) => {
      const unique = uniqueSelector(el);
      if (!unique.selector || seen.has(unique.selector) || shapes.length >= 8) return;
      seen.add(unique.selector);
      shapes.push({selector: unique.selector, selector_count: unique.count, selector_basis: unique.basis, tag: (el.tagName || '').toLowerCase(), role: el.getAttribute('role'), label: gatedLabel(rawVisibleText(el) || ownText(el) || safeAria(el), 60)});
    });
    return {link_count: latest.querySelectorAll('a[href]').length, citation_like_count: nodes.length, selectors: shapes};
  }

  const turns = allAssistantTurns();
  const latest = latestAssistantTurn();
  const streamingActive = visibleCount(STOP_SELECTOR) > 0;
  const completionMarkerPresent = visibleCount(COPY_SELECTOR) > 0;
  const composer = composerState();
  const progress = progressUi();
  const report = reportStructure(latest);
  const chips = suggestionChips(latest);
  const clarifyLooks = turns.length >= 1 && !streamingActive && composer.editable && !progress.present && !report.present;
  const citations = citationStructure(latest);
  return {
    ts: new Date(nowMs).toISOString(),
    elapsed_s: Math.round((nowMs - startedAtMs) / 1000),
    assistant_turn_count: turns.length,
    streaming_active: streamingActive,
    completion_marker_present: completionMarkerPresent,
    composer_present: composer.present,
    composer_editable: composer.editable,
    progress_ui: progress,
    report,
    citation_structure: citations,
    clarify_ui: {
      looks_like_clarify: clarifyLooks,
      suggestion_chip_count: chips.length,
      gated_chip_texts: chips.map((chip) => chip.label),
      suggestion_chips: chips,
    },
    verified_selectors: {
      assistant_turn: ASSISTANT_SELECTOR,
      assistant_turn_count: turns.length,
      stop_button: STOP_SELECTOR,
      stop_button_count: visibleCount(STOP_SELECTOR),
      completion_marker: COPY_SELECTOR,
      completion_marker_count: visibleCount(COPY_SELECTOR),
      composer: COMPOSER_SELECTOR,
      composer_count: selectorCount(COMPOSER_SELECTOR),
      progress_ui_strategy: 'visible main status/aria-live/data-testid/assistant descendants with DR lifecycle vocabulary',
      report_turn_selector: report.report_turn_selector,
      citation_selector: 'a[href], sup, [data-testid*="citation"], [aria-label*="citation"], [data-testid*="source"], [aria-label*="source"]',
    },
  };
}'''


def _wait_for_tools_trigger(page: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    poll_rows: list[dict[str, Any]] = []
    t0 = time.monotonic()
    state: dict[str, Any] = {}
    while True:
        state = page.evaluate(_TOOLS_ENUMERATE_JS)
        elapsed = round(time.monotonic() - t0, 2)
        poll_rows.append({
            "elapsed_s": elapsed,
            "trigger_candidates": len(state.get("trigger_candidates") or []),
            "best_trigger": bool(state.get("best_trigger")),
            "portal_roots": len(state.get("portal_roots") or []),
        })
        if state.get("best_trigger") or elapsed >= 10.0:
            break
        page.wait_for_timeout(500)
    return state, poll_rows


def _open_tools_menu(page: Any, trigger: dict[str, Any]) -> dict[str, Any]:
    selector = trigger.get("selector")
    if not isinstance(selector, str) or not selector:
        raise RuntimeError("tools trigger selector unavailable")
    page.locator(selector).first.click(timeout=5000)
    page.wait_for_timeout(1000)
    return page.evaluate(_TOOLS_ENUMERATE_JS)


def _click_selector_first(page: Any, selector: str) -> int:
    loc = page.locator(selector)
    count = int(loc.count())
    if count > 0:
        loc.first.click(timeout=5000)
    return count


def _phase_guess(snapshot: dict[str, Any], stable_completion_polls: int = 0) -> str:
    if stable_completion_polls >= 2:
        return "complete"
    if (snapshot.get("clarify_ui") or {}).get("looks_like_clarify"):
        return "clarify"
    if (snapshot.get("report") or {}).get("present") and snapshot.get("streaming_active"):
        return "drafting-report"
    if (snapshot.get("report") or {}).get("present"):
        return "report-visible"
    if (snapshot.get("progress_ui") or {}).get("present"):
        return "researching"
    if snapshot.get("streaming_active"):
        return "streaming"
    return "observing"


def _timeline_summary(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    def first_ts(predicate: Any) -> str | None:
        for snap in snapshots:
            if predicate(snap):
                return snap.get("ts")
        return None

    def last_ts(predicate: Any) -> str | None:
        for snap in reversed(snapshots):
            if predicate(snap):
                return snap.get("ts")
        return None

    return {
        "poll_count": len(snapshots),
        "first_streaming_at": first_ts(lambda s: bool(s.get("streaming_active"))),
        "last_streaming_at": last_ts(lambda s: bool(s.get("streaming_active"))),
        "first_progress_at": first_ts(lambda s: bool((s.get("progress_ui") or {}).get("present"))),
        "last_progress_at": last_ts(lambda s: bool((s.get("progress_ui") or {}).get("present"))),
        "first_report_at": first_ts(lambda s: bool((s.get("report") or {}).get("present"))),
        "first_completion_marker_at": first_ts(lambda s: bool(s.get("completion_marker_present"))),
        "first_clarify_at": first_ts(lambda s: bool((s.get("clarify_ui") or {}).get("looks_like_clarify"))),
        "max_assistant_turn_count": max((int(s.get("assistant_turn_count") or 0) for s in snapshots), default=0),
    }


def leg_tools_menu(_args: argparse.Namespace) -> int:
    report = REPORT_DIR / "T1-tools-menu.json"
    payload: dict[str, Any] = {
        "stage": "start",
        "verdict": "HONEST-FAIL-CLOSED",
        "started_at": _now_iso(),
        "base_url": BASE_URL,
        "cdp_endpoint": CDP_ENDPOINT,
    }
    session: Any | None = None
    close_on_exit = True
    try:
        session = connect()
        try:
            session.open_or_create_conversation(None)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            payload.update({"stage": "open", "result": _human_label(exc)})
            _write_json(report, payload)
            return 5
        if not recheck_safe(session):
            close_on_exit = False
            payload.update({"stage": "open-safety", "result": "HUMAN-ACTION-NEEDED"})
            _write_json(report, payload)
            return 5
        page = _require_page(session)

        closed, poll_rows = _wait_for_tools_trigger(page)
        payload["hydration_poll"] = poll_rows
        payload["closed_state"] = closed
        audit({"leg": "T1-tools-menu", "action": "closed-state enumerate after hydration wait", "prompt-label": "n/a",
               "observation": "triggers=%s,best=%s" % (len(closed.get("trigger_candidates") or []), bool(closed.get("best_trigger"))),
               "markers": "no prompt sent", "result": "OK"})
        if not recheck_safe(session):
            close_on_exit = False
            payload.update({"stage": "post-hydration-safety", "result": "HUMAN-ACTION-NEEDED"})
            _write_json(report, payload)
            return 5

        chosen = closed.get("best_trigger")
        payload["chosen_trigger"] = chosen
        payload["chosen_trigger_reason"] = closed.get("best_trigger_reason")
        if not isinstance(chosen, dict) or not chosen.get("selector"):
            payload.update({
                "stage": "done",
                "verdict": "HONEST-FAIL-CLOSED",
                "fail_closed_reason": "no tools-menu trigger candidate after hydrated composer search",
                "ended_at": _now_iso(),
            })
            _write_json(report, payload)
            audit({"leg": "T1-tools-menu", "action": "choose trigger", "prompt-label": "n/a",
                   "observation": "no trigger candidate", "markers": "no prompt sent", "result": "HONEST-FAIL-CLOSED"})
            _emit("TOOLS-MENU: HONEST-FAIL-CLOSED no-trigger")
            return 0

        trigger_selector = str(chosen.get("selector"))
        trigger_count = _selector_count(page, trigger_selector)
        payload["trigger_selector"] = trigger_selector
        payload["trigger_count"] = trigger_count
        opened: dict[str, Any] = {"options": [], "portal_roots": []}
        try:
            opened = _open_tools_menu(page, chosen)
        except PlaywrightError as exc:
            payload["open_error"] = exc.__class__.__name__
        payload["opened_state"] = opened
        options = list(opened.get("options") or [])
        dr_option = opened.get("deep_research_option")
        payload["deep_research_option"] = dr_option
        audit({"leg": "T1-tools-menu", "action": "open trigger + enumerate tool options", "prompt-label": "n/a",
               "observation": "trigger_count=%s,options=%s,dr_found=%s" % (trigger_count, len(options), bool(dr_option)),
               "markers": "Escape pending,no prompt sent", "result": "OK"})

        armed_state: dict[str, Any] = {"attempted": False}
        if isinstance(dr_option, dict) and dr_option.get("selector"):
            try:
                armed_state["attempted"] = True
                armed_state["option_selector"] = dr_option.get("selector")
                armed_state["option_selector_count_before_click"] = _click_selector_first(page, str(dr_option.get("selector")))
                page.wait_for_timeout(800)
                armed_state["state"] = page.evaluate(_TOOLS_ENUMERATE_JS).get("armed_state")
                audit({"leg": "T1-tools-menu", "action": "best-effort select Deep Research without submit", "prompt-label": "n/a",
                       "observation": "selector_count=%s,armed=%s" % (armed_state.get("option_selector_count_before_click"), bool((armed_state.get("state") or {}).get("deep_research_armed"))),
                       "markers": "no prompt sent", "result": "OK"})
            except Exception as exc:  # noqa: BLE001 - best effort must not fail T1.
                armed_state["error"] = exc.__class__.__name__
        payload["armed_state"] = armed_state

        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except PlaywrightError as exc:
            payload["escape_error"] = exc.__class__.__name__
        after_escape = page.evaluate(_TOOLS_ENUMERATE_JS)
        payload["after_escape"] = {
            "portal_roots": after_escape.get("portal_roots"),
            "options": after_escape.get("options"),
            "armed_state": after_escape.get("armed_state"),
            "best_trigger": after_escape.get("best_trigger"),
        }
        payload["refindability"] = {
            "trigger_selector": trigger_selector,
            "trigger_count": _selector_count(page, trigger_selector),
            "option_selector_strategy_counts": opened.get("option_selector_counts"),
            "deep_research_option_selector": (dr_option or {}).get("selector") if isinstance(dr_option, dict) else None,
            "deep_research_option_selector_count": _selector_count(page, (dr_option or {}).get("selector") if isinstance(dr_option, dict) else None),
        }

        dr_found = isinstance(dr_option, dict) and bool(dr_option.get("selector"))
        if len(options) >= 1 and dr_found:
            payload["verdict"] = "FOUND"
        else:
            payload["verdict"] = "HONEST-FAIL-CLOSED"
            payload["fail_closed_reason"] = "options enumerated but Deep Research option not located" if options else "trigger opened but no tool options were enumerated"
        payload.update({"stage": "done", "ended_at": _now_iso()})
        _write_json(report, payload)
        audit({"leg": "T1-tools-menu", "action": "Escape close + write report", "prompt-label": "n/a",
               "observation": "trigger_count=%s,options=%s,dr_found=%s" % (trigger_count, len(options), dr_found),
               "markers": "no prompt sent", "result": payload.get("verdict")})
        _emit("TOOLS-MENU: %s trigger_count=%s options=%s dr_found=%s" % (payload.get("verdict"), trigger_count, len(options), dr_found))
        return 0
    except SystemExit:
        raise
    except HUMAN_ERRORS as exc:
        close_on_exit = False
        _emit_human_action_needed(exc)
        payload.update({"stage": "human-action-needed", "result": _human_label(exc), "ended_at": _now_iso()})
        _write_json(report, payload)
        return 5
    except Exception as exc:  # noqa: BLE001
        payload.update({"stage": "error", "error": "%s: %s" % (exc.__class__.__name__, redact(str(exc))[:240]), "ended_at": _now_iso()})
        _write_json(report, payload)
        _emit("ERROR: %s: %s" % (exc.__class__.__name__, exc))
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def _write_t2_status(status: str, **extra: Any) -> None:
    payload = {"status": status, **extra}
    _write_json(REPORT_DIR / "T2-status.json", payload)


def _open_tools_and_find_dr(session: Any, page: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    closed, poll_rows = _wait_for_tools_trigger(page)
    chosen = closed.get("best_trigger")
    if not isinstance(chosen, dict) or not chosen.get("selector"):
        return closed, {"options": [], "portal_roots": [], "open_error": "no-trigger"}, None, poll_rows
    opened = _open_tools_menu(page, chosen)
    dr_option = opened.get("deep_research_option")
    return closed, opened, dr_option if isinstance(dr_option, dict) else None, poll_rows


def leg_deep_research(args: argparse.Namespace) -> int:
    report = REPORT_DIR / "T2-deep-research.json"
    progress_jsonl = REPORT_DIR / "T2-dr-progress.jsonl"
    latest_json = REPORT_DIR / "T2-dr-latest.json"
    if report.exists() and not args.force:
        _emit("DR-ALREADY-RAN: refusing (T2-deep-research.json exists; pass --force to override)")
        return 0

    started_at = _now_iso()
    _write_t2_status("STARTED", started_at=started_at)
    payload: dict[str, Any] = {
        "stage": "start",
        "status": "PARTIAL",
        "started_at": started_at,
        "prompt_label": "lfp-vs-nmc-3bullets",
        "prompt_chars": len(DR_PROMPT),
    }
    session: Any | None = None
    close_on_exit = True
    t0 = time.monotonic()
    try:
        session = connect()
        try:
            session.open_or_create_conversation(None)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            payload.update({"stage": "open", "status": "HUMAN-ACTION-NEEDED", "result": _human_label(exc), "ended_at": _now_iso()})
            _write_json(report, payload)
            _write_t2_status("HUMAN-ACTION-NEEDED", ended_at=_now_iso(), partial=True, reason=_human_label(exc))
            return 5
        if not recheck_safe(session):
            close_on_exit = False
            payload.update({"stage": "open-safety", "status": "HUMAN-ACTION-NEEDED", "result": "HUMAN-ACTION-NEEDED", "ended_at": _now_iso()})
            _write_json(report, payload)
            _write_t2_status("HUMAN-ACTION-NEEDED", ended_at=_now_iso(), partial=True, reason="open-safety")
            return 5
        page = _require_page(session)

        closed, opened, dr_option, poll_rows = _open_tools_and_find_dr(session, page)
        payload["hydration_poll"] = poll_rows
        payload["closed_state"] = closed
        payload["opened_state"] = opened
        payload["chosen_trigger"] = closed.get("best_trigger")
        payload["deep_research_option"] = dr_option
        if not dr_option or not dr_option.get("selector"):
            payload.update({
                "stage": "done",
                "status": "PARTIAL",
                "fail_closed_reason": "Deep Research option not found; prompt not submitted",
                "ended_at": _now_iso(),
                "total_wall_clock_s": round(time.monotonic() - t0, 2),
            })
            _write_json(report, payload)
            _write_t2_status("PARTIAL", ended_at=_now_iso(), total_wall_clock_s=payload["total_wall_clock_s"], reason=payload["fail_closed_reason"])
            audit({"leg": "T2-deep-research", "action": "select-deep-research", "prompt-label": "n/a",
                   "observation": "Deep Research option not found; nothing submitted", "markers": "no prompt sent", "result": "HONEST-FAIL-CLOSED"})
            _emit("DEEP-RESEARCH: PARTIAL wall_clock=%ss turns=0 report_present=False" % payload["total_wall_clock_s"])
            return 0

        option_selector = str(dr_option.get("selector"))
        option_count = _click_selector_first(page, option_selector)
        page.wait_for_timeout(800)
        audit({"leg": "T2-deep-research", "action": "select-deep-research", "prompt-label": "n/a",
               "observation": "option_selector_count=%s" % option_count, "markers": "no prompt sent yet", "result": "OK"})
        armed_capture = page.evaluate(_TOOLS_ENUMERATE_JS).get("armed_state")
        payload["armed_state"] = armed_capture
        # Close the tools menu before composing. Deep Research stays armed after Escape (verified in
        # T1 tools-menu: after_escape.armed_state.deep_research_armed=True), so the composer is clear
        # and the prompt is not swallowed by an open Radix menu overlay.
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except PlaywrightError:
            pass

        try:
            session.send_prompt(DR_PROMPT)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            payload.update({"stage": "send", "status": "HUMAN-ACTION-NEEDED", "result": _human_label(exc), "ended_at": _now_iso()})
            _write_json(report, payload)
            _write_t2_status("HUMAN-ACTION-NEEDED", ended_at=_now_iso(), partial=True, reason=_human_label(exc))
            return 5
        submitted_at = _now_iso()
        payload["submitted_at"] = submitted_at
        audit({"leg": "T2-deep-research", "action": "submit-dr-prompt", "prompt-label": "lfp-vs-nmc-3bullets",
               "observation": "sent via BrowserSession.send_prompt", "markers": "recorder starting", "result": "OK"})

        snapshots: list[dict[str, Any]] = []
        clarify_capture: dict[str, Any] | None = None
        clarify_observed = False
        answered = False
        completion_streak = 0
        progress_seen = False
        turns_at_answer: int | None = None
        final_status = "PARTIAL-TIMEOUT"
        final_snapshot: dict[str, Any] | None = None
        started_at_ms = int(time.time() * 1000)
        max_observe_s = max(0.0, float(args.max_observe_s))
        clarify_wait_s = max(0.0, float(args.clarify_wait_s))
        poll_s = max(8.0, float(args.poll_s))
        poll_index = 0

        while True:
            snapshot = page.evaluate(_DR_STATE_JS, {"started_at_ms": started_at_ms})
            poll_index += 1
            report_present = bool((snapshot.get("report") or {}).get("present"))
            progress_seen = progress_seen or bool((snapshot.get("progress_ui") or {}).get("present"))
            turn_count = int(snapshot.get("assistant_turn_count") or 0)
            turns_grew_since_answer = turns_at_answer is not None and turn_count > turns_at_answer
            # A Deep Research clarifying question can render as a bulleted/multi-paragraph turn
            # (report_present True) with a copy button and no stop button. Without this gate it would
            # be mistaken for the final report and the one-shot run would stop ~16s in, never
            # answering the clarification or observing the research. Only trust a "report" once the
            # clarify phase is resolved: the research/progress phase was seen, OR we answered a
            # clarification AND a NEW assistant turn (the report) has since appeared. Premature DONE
            # loses the report irrecoverably; over-conservatism only costs wall-clock (the snapshots
            # keep the full timeline either way, and the manager is polling the heartbeat live).
            completion_allowed = progress_seen or (answered and turns_grew_since_answer)
            complete_now = (
                report_present
                and not snapshot.get("streaming_active")
                and bool(snapshot.get("completion_marker_present"))
                and completion_allowed
            )
            completion_streak = completion_streak + 1 if complete_now else 0
            phase = _phase_guess(snapshot, completion_streak)
            snapshot["phase_guess"] = phase
            snapshot["poll_index"] = poll_index
            snapshots.append(snapshot)
            final_snapshot = snapshot
            _append_jsonl(progress_jsonl, snapshot)
            _write_json(latest_json, {"phase_guess": phase, "stable_completion_polls": completion_streak, "snapshot": snapshot})

            if poll_index % 5 == 0:
                if not recheck_safe(session):
                    close_on_exit = False
                    final_status = "HUMAN-ACTION-NEEDED"
                    payload.update({"stage": "observe-safety", "status": final_status, "snapshots_recorded": len(snapshots), "ended_at": _now_iso()})
                    _write_json(report, payload)
                    _write_t2_status(final_status, ended_at=_now_iso(), partial=True, total_wall_clock_s=round(time.monotonic() - t0, 2))
                    return 5

            elapsed_s = float(snapshot.get("elapsed_s") or 0.0)
            clarify_ui = snapshot.get("clarify_ui") or {}
            # Clarify trigger does NOT require !report.present (a clarifying question may be bulleted
            # / multi-paragraph). The reliable discriminator vs the final report is that the research
            # phase has not happened yet (progress never seen). JS looks_like_clarify kept as a fallback.
            clarify_phase_open = elapsed_s <= clarify_wait_s and not progress_seen
            py_clarify = (
                turn_count >= 1
                and not bool(snapshot.get("streaming_active"))
                and bool(snapshot.get("composer_editable"))
                and clarify_phase_open
            )
            if not answered and (py_clarify or (clarify_phase_open and clarify_ui.get("looks_like_clarify"))):
                clarify_observed = True
                clarify_capture = {
                    "ts": snapshot.get("ts"),
                    "elapsed_s": snapshot.get("elapsed_s"),
                    "clarify_ui": clarify_ui,
                    "assistant_turn_count": snapshot.get("assistant_turn_count"),
                    "composer_present": snapshot.get("composer_present"),
                    "composer_editable": snapshot.get("composer_editable"),
                }
                try:
                    session.send_prompt(CLARIFY_ANSWER)
                except HUMAN_ERRORS as exc:
                    close_on_exit = False
                    _emit_human_action_needed(exc)
                    final_status = "HUMAN-ACTION-NEEDED"
                    payload.update({"stage": "clarify-send", "status": final_status, "result": _human_label(exc), "clarify_capture": clarify_capture, "ended_at": _now_iso()})
                    _write_json(report, payload)
                    _write_t2_status(final_status, ended_at=_now_iso(), partial=True, reason=_human_label(exc), total_wall_clock_s=round(time.monotonic() - t0, 2))
                    return 5
                answered = True
                turns_at_answer = turn_count
                audit({"leg": "T2-deep-research", "action": "answer-clarification", "prompt-label": "brief-3bullets",
                       "observation": "clarify_ui observed and answered once", "markers": "recorder continuing", "result": "OK"})

            if completion_streak >= 2:
                final_status = "DONE"
                break
            if elapsed_s >= max_observe_s:
                final_status = "PARTIAL-TIMEOUT"
                break
            page.wait_for_timeout(int(poll_s * 1000))

        timeline = _timeline_summary(snapshots)
        final_report = (final_snapshot or {}).get("report") or {}
        final_citations = (final_snapshot or {}).get("citation_structure") or {}
        total_wall = round(time.monotonic() - t0, 2)
        payload.update({
            "stage": "done",
            "status": final_status,
            "ended_at": _now_iso(),
            "total_wall_clock_s": total_wall,
            "clarify_observed": clarify_observed,
            "clarify_capture": clarify_capture,
            "answered": answered,
            "phase_timeline_summary": timeline,
            "final_report_structure": final_report,
            "citation_structure": final_citations,
            "verified_selectors_used": {
                "tools_trigger": (closed.get("best_trigger") or {}).get("selector") if isinstance(closed.get("best_trigger"), dict) else None,
                "tools_trigger_count": _selector_count(page, (closed.get("best_trigger") or {}).get("selector") if isinstance(closed.get("best_trigger"), dict) else None),
                "deep_research_option": option_selector,
                "deep_research_option_count": _selector_count(page, option_selector),
                "progress_ui": ((final_snapshot or {}).get("verified_selectors") or {}).get("progress_ui_strategy"),
                "report_turn": final_report.get("report_turn_selector"),
                "citations": ((final_snapshot or {}).get("verified_selectors") or {}).get("citation_selector"),
                "copy_marker": ((final_snapshot or {}).get("verified_selectors") or {}).get("completion_marker"),
                "stop_marker": ((final_snapshot or {}).get("verified_selectors") or {}).get("stop_button"),
                "composer": ((final_snapshot or {}).get("verified_selectors") or {}).get("composer"),
            },
            "timing": {
                "submitted_at": submitted_at,
                "first_progress_at": timeline.get("first_progress_at"),
                "report_at": timeline.get("first_report_at"),
                "total_wall_clock_s": total_wall,
            },
            "snapshots_recorded": len(snapshots),
        })
        _write_json(report, payload)
        _write_t2_status(final_status, ended_at=_now_iso(), total_wall_clock_s=total_wall)
        audit({"leg": "T2-deep-research", "action": "write final DR structured capture", "prompt-label": "lfp-vs-nmc-3bullets",
               "observation": "status=%s,snapshots=%s,report_present=%s" % (final_status, len(snapshots), bool(final_report.get("present"))),
               "markers": "stop=%s,copy=%s" % ((final_snapshot or {}).get("streaming_active"), (final_snapshot or {}).get("completion_marker_present")), "result": final_status})
        _emit("DEEP-RESEARCH: %s wall_clock=%ss turns=%s report_present=%s" % (final_status, total_wall, (final_snapshot or {}).get("assistant_turn_count", 0), bool(final_report.get("present"))))
        return 0
    except SystemExit:
        raise
    except HUMAN_ERRORS as exc:
        close_on_exit = False
        _emit_human_action_needed(exc)
        payload.update({"stage": "human-action-needed", "status": "HUMAN-ACTION-NEEDED", "result": _human_label(exc), "ended_at": _now_iso(), "total_wall_clock_s": round(time.monotonic() - t0, 2)})
        _write_json(report, payload)
        _write_t2_status("HUMAN-ACTION-NEEDED", ended_at=_now_iso(), partial=True, reason=_human_label(exc), total_wall_clock_s=payload["total_wall_clock_s"])
        return 5
    except Exception as exc:  # noqa: BLE001
        payload.update({"stage": "error", "status": "PARTIAL", "error": "%s: %s" % (exc.__class__.__name__, redact(str(exc))[:240]), "ended_at": _now_iso(), "total_wall_clock_s": round(time.monotonic() - t0, 2)})
        _write_json(report, payload)
        _write_t2_status("PARTIAL", ended_at=_now_iso(), reason="error", total_wall_clock_s=payload["total_wall_clock_s"])
        _emit("ERROR: %s: %s" % (exc.__class__.__name__, exc))
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M-011 attach-only real ChatGPT tools-menu + Deep Research discovery probe")
    sub = p.add_subparsers(dest="command", required=True)

    tm = sub.add_parser("tools-menu", help="repeatable: enumerate the composer tools/add-on menu; no prompt send")
    tm.set_defaults(func=leg_tools_menu)

    dr = sub.add_parser("deep-research", help="exactly-once quota-heavy Deep Research lifecycle recorder")
    dr.add_argument("--max-observe-s", type=float, default=2400.0)
    dr.add_argument("--clarify-wait-s", type=float, default=150.0)
    dr.add_argument("--poll-s", type=float, default=8.0)
    dr.add_argument("--force", action="store_true")
    dr.set_defaults(func=leg_deep_research)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
