#!/usr/bin/env python3
"""M-010 real-site CDP model-picker discovery probe (attach-only).

Inert on import. Drives the PRODUCTION ask_chatgpt open-conversation path over
an operator-launched CDP browser, then opens the real ChatGPT model dropdown,
enumerates model options, and closes it with Escape. Fail-closed, human-paced,
redacted, and never launches a browser or automates login.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (SRC, ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from playwright.sync_api import Error as PlaywrightError  # noqa: E402

from ask_chatgpt.api import ask_chatgpt  # noqa: E402
from ask_chatgpt.bundle import build_bundle, generate_prompt_instructions, upload_bundle  # noqa: E402
from ask_chatgpt.driver import BrowserSession  # noqa: E402
from ask_chatgpt.errors import (  # noqa: E402
    AskChatGPTError,
    CDPUnreachableError,
    ChallengePresentError,
    LoginRequiredError,
    ProfileLockedError,
)
from ask_chatgpt.patch import apply_patch, retrieve_patch_bundle  # noqa: E402

BASE_URL = "https://chatgpt.com"
CDP_ENDPOINT = "http://127.0.0.1:9222"
REPORT_DIR = ROOT / "orchestration" / "reports" / "M-010"
AUDIT_LOG = REPORT_DIR / "real-audit-log.md"
HUMAN_PACE_S = 4.0
HUMAN_ERRORS = (ChallengePresentError, LoginRequiredError, ProfileLockedError)

REDACT_C_RE = re.compile(r"/c/[^/?#\s]+")
URLISH_RE = re.compile(r"\b(?:https?|blob|sandbox):[^\s<>)\"']+", re.IGNORECASE)
SECRET_PARAM_RE = re.compile(
    r"\b(access_token|token|sig|signature|x-amz-signature|key|jwt|session|cookie)=[^&\s)\"']+",
    re.IGNORECASE,
)
AUDIT_DATA_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")
AUDIT_HEADER = """# M-010 — Real-site per-message audit log (transparency, not rationing)

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
"""

_audit_next: int | None = None


class HumanActionStop(RuntimeError):
    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.label = label


def redact(value: object) -> str:
    text = REDACT_C_RE.sub("/c/<redacted>", str(value))
    text = URLISH_RE.sub("<url>", text)
    text = SECRET_PARAM_RE.sub(lambda m: m.group(0).split("=", 1)[0] + "=<redacted>", text)
    return text


def _emit(message: str) -> None:
    print(redact(message), flush=True)


def _human_label(exc: BaseException) -> str:
    return "CHALLENGE_PRESENT" if isinstance(exc, ChallengePresentError) else exc.__class__.__name__


def _emit_human_action_needed(exc_or_label: BaseException | str) -> None:
    label = exc_or_label if isinstance(exc_or_label, str) else _human_label(exc_or_label)
    _emit(f"HUMAN-ACTION-NEEDED: {label}")


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


def connect(*, maps_dir: Path | None = None) -> BrowserSession:
    session = BrowserSession(channel="cdp", base_url=BASE_URL, cdp_endpoint=CDP_ENDPOINT, maps_dir=maps_dir)
    try:
        return session.start()
    except CDPUnreachableError:
        _emit("CDP_UNREACHABLE")
        raise SystemExit(3) from None
    except HUMAN_ERRORS as exc:
        _emit_human_action_needed(exc)
        raise SystemExit(5) from None


def recheck_safe(session: BrowserSession) -> bool:
    """Read-only challenge/login/logout recheck; never clicks through."""
    try:
        session._raise_challenge_present_if_detected()
        session._raise_open_failures()
        if session.page is not None:
            session._raise_login_required_for_auth_redirect(session.page.url)
    except Exception as exc:  # noqa: BLE001 - any safety failure stops sending.
        _emit_human_action_needed(_human_label(exc))
        return False
    return True


def _temp_maps_with_download(selector: str) -> Path:
    """Write a temp real.json identical to the shipped map but with download_artifact set."""
    shipped = json.loads((SRC / "ask_chatgpt" / "selector_maps" / "real.json").read_text(encoding="utf-8"))
    shipped["selectors"]["download_artifact"] = selector
    tmp = Path(tempfile.mkdtemp(prefix="m009-maps-"))
    (tmp / "real.json").write_text(json.dumps(shipped, indent=2), encoding="utf-8")
    return tmp


# --------------------------------------------------------------------------- legs


def leg_connectivity(_args: argparse.Namespace) -> int:
    session: BrowserSession | None = None
    close_on_exit = True
    try:
        session = connect()
        try:
            session.open_or_create_conversation(None)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            return 5
        if not recheck_safe(session):
            close_on_exit = False
            return 5
        audit({
            "leg": "T0-connectivity", "action": "open new conversation (no send)",
            "prompt-label": "n/a", "observation": "ready_root+composer present",
            "markers": "n/a", "result": "OK",
        })
        _emit("CONNECTIVITY: OK")
        return 0
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def _build_uc2_bundle(temp_root: Path) -> tuple[Any, str, Path]:
    proj = temp_root / "tiny-project"
    proj.mkdir(parents=True, exist_ok=False)
    (proj / "example.txt").write_text('favorite_color = "red"\nfavorite_food = "pizza"\n', encoding="utf-8")
    bundle = build_bundle(files=("example.txt",), root=proj)
    return bundle, bundle.filename, proj


def leg_uc2(args: argparse.Namespace) -> int:
    """Real UC2 round-trip via the PRODUCTION retrieve_patch_bundle path."""
    selector = args.download_selector
    maps_dir = _temp_maps_with_download(selector) if selector else None
    report = REPORT_DIR / "T1-uc2-roundtrip.json"
    payload: dict[str, Any] = {
        "download_selector_injected": selector or None,
        "stage": "start",
    }
    session: BrowserSession | None = None
    close_on_exit = True
    try:
        with tempfile.TemporaryDirectory(prefix="m009-uc2-") as td:
            bundle, bundle_filename, proj = _build_uc2_bundle(Path(td))
            user_task = "In example.txt, change favorite_color from red to blue. Leave every other line unchanged."
            prompt = generate_prompt_instructions(user_task, bundle_filename=bundle_filename)

            session = connect(maps_dir=maps_dir)
            try:
                session.open_or_create_conversation(None)
            except HUMAN_ERRORS as exc:
                close_on_exit = False
                _emit_human_action_needed(exc)
                payload["stage"] = "open"; payload["result"] = _human_label(exc)
                _write_json(report, payload)
                return 5
            if not recheck_safe(session):
                close_on_exit = False
                payload["stage"] = "open-safety"; payload["result"] = "HUMAN-ACTION-NEEDED"
                _write_json(report, payload)
                return 5

            upload_bundle(session, bundle, timeout_s=120)
            audit({"leg": "T1-uc2", "action": "upload-bundle", "prompt-label": "tiny-2key-bundle",
                   "observation": f"uploaded basename={bundle_filename},bytes={bundle.byte_count}",
                   "markers": "n/a", "result": "OK"})
            time.sleep(HUMAN_PACE_S)
            if not recheck_safe(session):
                close_on_exit = False
                payload["stage"] = "upload-safety"; payload["result"] = "HUMAN-ACTION-NEEDED"
                _write_json(report, payload)
                return 5

            try:
                session.send_prompt(prompt)
            except HUMAN_ERRORS as exc:
                close_on_exit = False
                _emit_human_action_needed(exc)
                payload["stage"] = "send"; payload["result"] = _human_label(exc)
                _write_json(report, payload)
                return 5
            audit({"leg": "T1-uc2", "action": "send-uc2-prompt", "prompt-label": "uc2-red-to-blue",
                   "observation": f"sent; prompt_chars={len(prompt)}", "markers": "n/a", "result": "OK"})

            # First production wait (api.py does this), then the retrieve path waits AGAIN internally.
            t_retrieve0 = time.monotonic()
            retrieve_outcome = "n/a"
            retrieve_detail = ""
            retrieved = None
            try:
                session.wait_for_completion(timeout_s=args.completion_timeout, max_total_wait_s=args.max_total_wait)
                payload["first_wait"] = "returned"
            except AskChatGPTError as exc:
                payload["first_wait"] = exc.__class__.__name__
                payload["first_wait_detail"] = redact(getattr(exc, "detail", "") or str(exc))[:240]
            audit({"leg": "T1-uc2", "action": "first-wait_for_completion",
                   "prompt-label": "uc2-red-to-blue", "observation": payload.get("first_wait", "n/a"),
                   "markers": "n/a", "result": payload.get("first_wait", "n/a")})

            if not recheck_safe(session):
                close_on_exit = False
                payload["stage"] = "post-wait-safety"; payload["result"] = "HUMAN-ACTION-NEEDED"
                _write_json(report, payload)
                return 5

            try:
                retrieved = retrieve_patch_bundle(session, timeout_s=args.retrieve_timeout, download_wait_s=args.download_wait)
                retrieve_outcome = "retrieved" if retrieved is not None else "NO_CHANGES_NEEDED"
            except AskChatGPTError as exc:
                retrieve_outcome = exc.__class__.__name__
                retrieve_detail = redact(getattr(exc, "detail", "") or str(exc))[:240]
            payload["retrieve_outcome"] = retrieve_outcome
            payload["retrieve_detail"] = retrieve_detail
            payload["retrieve_seconds"] = round(time.monotonic() - t_retrieve0, 2)
            audit({"leg": "T1-uc2", "action": "retrieve_patch_bundle (PRODUCTION path)",
                   "prompt-label": "uc2-red-to-blue",
                   "observation": f"outcome={retrieve_outcome}; {retrieve_detail}"[:200],
                   "markers": "n/a", "result": retrieve_outcome})

            if retrieved is not None:
                zip_bytes, patch_bundle = retrieved
                payload["bundle_bytes"] = len(zip_bytes)
                payload["bundle_filename"] = patch_bundle.filename
                payload["bundle_source"] = patch_bundle.source
                # Apply to a fresh copy of the original project tree and verify content-correctness.
                apply_root = Path(td) / "apply-target"
                apply_root.mkdir()
                (apply_root / "example.txt").write_text('favorite_color = "red"\nfavorite_food = "pizza"\n', encoding="utf-8")
                dry = apply_patch(patch_bundle, root=apply_root, dry_run=True)
                payload["diff_summary_dry"] = redact(str(dry))[:400]
                apply_patch(patch_bundle, root=apply_root, dry_run=False)
                applied = (apply_root / "example.txt").read_text(encoding="utf-8")
                payload["applied_example_txt"] = applied
                payload["content_correct"] = ('favorite_color = "blue"' in applied
                                              and 'favorite_food = "pizza"' in applied
                                              and 'favorite_color = "red"' not in applied)
                _emit(f"UC2: retrieved {len(zip_bytes)}B source={patch_bundle.source} content_correct={payload['content_correct']}")
            else:
                _emit(f"UC2: retrieve_outcome={retrieve_outcome} detail={retrieve_detail}")

            payload["stage"] = "done"
            _write_json(report, payload)
            return 0
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        payload["stage"] = "error"; payload["error"] = f"{exc.__class__.__name__}: {redact(str(exc))[:240]}"
        _write_json(report, payload)
        _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def leg_short(args: argparse.Namespace) -> int:
    """Send several SHORT prompts via the PRODUCTION ask_chatgpt()->text path; record hit/miss."""
    prompts = [
        ("short-ping", "Reply with exactly the word PING and nothing else."),
        ("short-hi", "Reply with just: hi"),
        ("short-num", "Reply with just the number 7 and nothing else."),
        ("short-ok", "Reply with only the word OK."),
    ]
    report = REPORT_DIR / "T2-short-response.json"
    results: list[dict[str, Any]] = []
    for label, prompt in prompts:
        entry: dict[str, Any] = {"label": label}
        t0 = time.monotonic()
        try:
            text = ask_chatgpt(prompt, channel="cdp", cdp_endpoint=CDP_ENDPOINT,
                               timeout_s=args.completion_timeout)
            entry["outcome"] = "returned"
            entry["text_len"] = len(text) if isinstance(text, str) else -1
            entry["text"] = redact(text)[:120] if isinstance(text, str) else str(type(text))
        except AskChatGPTError as exc:
            entry["outcome"] = exc.__class__.__name__
            entry["detail"] = redact(getattr(exc, "detail", "") or str(exc))[:200]
        entry["seconds"] = round(time.monotonic() - t0, 2)
        results.append(entry)
        audit({"leg": "T2-short", "action": "ask_chatgpt()->text (PRODUCTION)",
               "prompt-label": label, "observation": f"outcome={entry['outcome']},len={entry.get('text_len','n/a')}",
               "markers": "n/a", "result": entry["outcome"]})
        _emit(f"SHORT[{label}]: {entry['outcome']} len={entry.get('text_len','n/a')} {entry['seconds']}s")
        time.sleep(HUMAN_PACE_S)
        if any(r["outcome"] in ("ChallengePresentError", "LoginRequiredError", "ProfileLockedError") for r in results[-1:]):
            _emit_human_action_needed(results[-1]["outcome"])
            break
    spurious = [r["label"] for r in results if r["outcome"] == "ResponseTruncatedError"]
    summary = {"prompts": len(results), "returned": sum(1 for r in results if r["outcome"] == "returned"),
               "spurious_truncations": spurious}
    _write_json(report, {"summary": summary, "results": results})
    _emit(f"T2-SUMMARY: returned={summary['returned']}/{summary['prompts']} spurious_truncations={spurious}")
    return 0


_MODEL_ENUMERATE_JS = r'''
() => {
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
  function gatedRaw(value, limit) {
    if (!textLooksSafeModel(value)) return NON_MODEL_TEXT;
    return String(value || '').trim().slice(0, limit);
  }
  function gatedElementText(el, limit) {
    return gatedRaw(rawVisibleText(el), limit);
  }
  function gatedOwnText(el, limit) {
    return gatedRaw(ownText(el), limit);
  }
  function safeAriaForOutput(el) {
    const a = safeAria(el);
    if (!a) return null;
    if (a === '<omitted>') return a;
    if (!textLooksSafeModel(a)) return NON_MODEL_ARIA;
    return a.slice(0, 80);
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
  function isHeaderish(el) {
    if (!isVisible(el)) return false;
    const r = el.getBoundingClientRect();
    const topLimit = Math.max(180, Math.round((window.innerHeight || 900) * 0.18));
    return r.top >= -8 && r.top <= topLimit;
  }
  function isSidebarControl(el) {
    if (!isVisible(el)) return false;
    const r = el.getBoundingClientRect();
    return !!el.closest('nav') && !el.closest('header') && r.left < 260;
  }
  function isHomeLinkLike(el) {
    const a = el.closest('a[href]');
    if (!a) return false;
    const href = a.getAttribute('href') || '';
    return href === '/' || href === '' || href === location.origin || href === location.origin + '/';
  }
  function isDisabled(el) {
    return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.getAttribute('data-disabled') === 'true'
        || !!el.closest('[aria-disabled=true], [data-disabled=true], [disabled]');
  }
  function isComposerControl(el) {
    const blob = attrBlob(el);
    const text = compact(rawVisibleText(el));
    const rect = el.getBoundingClientRect();
    if (rect.top > (window.innerHeight || 900) * 0.45 && el.closest('form, [contenteditable=true], #prompt-textarea')) return true;
    return blob.includes('upload') || blob.includes('attach') || blob.includes('composer') || blob.includes('send-button')
        || blob.includes('voice') || blob.includes('file') || text === '+' || text === '＋';
  }
  function isReasoningControl(el) {
    const blob = attrBlob(el) + ' ' + compact(rawVisibleText(el)).toLowerCase();
    return /\b(extra high|high|medium|low|reasoning|thinking effort|effort)\b/.test(blob);
  }
  function baseShape(el) {
    return {
      tag: (el.tagName || '').toLowerCase(),
      testid: el.getAttribute('data-testid'),
      role: el.getAttribute('role'),
      aria_label: safeAriaForOutput(el),
      aria_haspopup: el.getAttribute('aria-haspopup'),
      aria_expanded: el.getAttribute('aria-expanded'),
      aria_checked: el.getAttribute('aria-checked'),
      aria_selected: el.getAttribute('aria-selected'),
      data_state: el.getAttribute('data-state'),
      data_radix_collection_item: el.hasAttribute('data-radix-collection-item'),
      disabled: isDisabled(el),
    };
  }
  function buttonShape(el) {
    const unique = uniqueSelector(el);
    const text = rawVisibleText(el);
    const own = ownText(el);
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      text: gatedRaw(text, 140),
      own_text: gatedRaw(own, 140),
      text_matches_model: textLooksSafeModel(own) || textLooksSafeModel(text),
      headerish: isHeaderish(el),
      sidebar_like: isSidebarControl(el),
      home_link_like: isHomeLinkLike(el),
      composer_like: isComposerControl(el),
      reasoning_like: isReasoningControl(el),
    });
  }
  function firstModelLine(raw) {
    const lines = String(raw || '').split(/\n+/).map((line) => compact(line)).filter(Boolean);
    for (const line of lines) {
      if (/legacy models|more models|show more/i.test(line)) continue;
      if (textLooksSafeModel(line)) return line.slice(0, 140);
    }
    return NON_MODEL_TEXT;
  }
  function optionShape(el) {
    const unique = uniqueSelector(el);
    const raw = rawVisibleText(el);
    const normalized = compact(raw);
    const modelLabel = firstModelLine(raw);
    const submenu = /legacy models|more models|show more/i.test(normalized) || el.getAttribute('aria-haspopup') === 'menu';
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      full_label_text: gatedRaw(raw, 900),
      model_label: modelLabel,
      is_submenu_or_more_models: submenu,
      is_model_option: modelLabel !== NON_MODEL_TEXT && !submenu,
      enabled: !isDisabled(el),
    });
  }
  function visibleCount(selector) {
    try {
      return Array.from(document.querySelectorAll(selector)).filter((el) => isVisible(el) && !isSensitive(el)).length;
    } catch (e) {
      return -1;
    }
  }

  const out = {
    url_path: location.pathname.replace(/\/c\/[^/?#\s]+/g, '/c/<redacted>'),
    hydrated_markers: {
      ready_root_present: document.querySelectorAll('main:has(#prompt-textarea)').length,
      composer_present: document.querySelectorAll('#prompt-textarea').length,
    },
    testid_inventory: [],
    modelish_testids: [],
    header_buttons: [],
    top_main_elements: [],
    doc_model_candidates: [],
    text_model_candidates: [],
    trigger_candidates: [],
    best_trigger: null,
    best_trigger_reason: null,
    portal_roots: [],
    portal_options: [],
    model_option_selector: null,
    model_option_selector_counts: [],
    model_option_disabled_selector: null,
    available_model_labels: [],
    submenu_or_more_models_visible: false,
  };

  const seenTestids = new Set();
  document.querySelectorAll('[data-testid]').forEach((el) => {
    if (isSensitive(el)) return;
    const t = el.getAttribute('data-testid');
    if (t && !seenTestids.has(t)) {
      seenTestids.add(t);
      out.testid_inventory.push(t);
    }
  });
  out.testid_inventory.sort();
  out.modelish_testids = out.testid_inventory.filter((t) => /model|switcher/i.test(t));

  const headerSelector = 'button, [role=button], [aria-haspopup]';
  Array.from(document.querySelectorAll(headerSelector)).forEach((el) => {
    if (!isHeaderish(el) || isSensitive(el)) return;
    out.header_buttons.push(buttonShape(el));
  });

  Array.from(document.querySelectorAll('header *, main *, [data-testid=thread-header-right-actions-container] *')).forEach((el) => {
    if (!isVisible(el) || isSensitive(el)) return;
    const r = el.getBoundingClientRect();
    if (r.top < -8 || r.top > 180 || r.left < 245) return;
    if (out.top_main_elements.length >= 160) return;
    const unique = uniqueSelector(el);
    out.top_main_elements.push(Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      text: gatedElementText(el, 140),
      own_text: gatedOwnText(el, 140),
    }));
  });

  const clickableSelector = 'button, [role=button], [role=combobox], [aria-haspopup], [data-state]';
  const clickables = Array.from(document.querySelectorAll(clickableSelector)).filter((el) => isVisible(el) && !isSensitive(el));
  clickables.forEach((el) => {
    const blob = attrBlob(el);
    const shape = buttonShape(el);
    if (blob.includes('model') || blob.includes('switcher') || shape.text_matches_model || (shape.headerish && shape.aria_haspopup)) {
      out.trigger_candidates.push(shape);
    }
  });

  function modelClickableFor(el) {
    const direct = el.closest('button, [role=button], [role=combobox], [aria-haspopup], [data-state], [data-radix-collection-item], a, summary');
    if (direct && isVisible(direct) && !isSensitive(direct)) return direct;
    let cur = el;
    let hops = 0;
    while (cur && cur.nodeType === 1 && hops < 6) {
      if (isHeaderish(cur) && !isSensitive(cur)) {
        const style = window.getComputedStyle(cur);
        if (style.cursor === 'pointer' || cur.onclick || cur.getAttribute('tabindex') !== null) return cur;
      }
      cur = cur.parentElement;
      hops += 1;
    }
    return el;
  }

  const docSelector = 'button, [role=button], [role=combobox], a, span, div';
  Array.from(document.querySelectorAll(docSelector)).forEach((el) => {
    if (!isVisible(el) || isSensitive(el)) return;
    const own = ownText(el).slice(0, 140);
    if (!textLooksSafeModel(own)) return;
    const clickable = modelClickableFor(el);
    const unique = clickable ? uniqueSelector(clickable) : {selector: null, count: 0, basis: null};
    const selfUnique = uniqueSelector(el);
    out.doc_model_candidates.push({
      text: own.slice(0, 140),
      tag: (el.tagName || '').toLowerCase(),
      testid: el.getAttribute('data-testid'),
      role: el.getAttribute('role'),
      rect: rectShape(el),
      element_headerish: isHeaderish(el),
      element_selector: selfUnique.selector,
      element_selector_count: selfUnique.count,
      element_selector_basis: selfUnique.basis,
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      clickable_tag: clickable ? (clickable.tagName || '').toLowerCase() : null,
      clickable_testid: clickable ? clickable.getAttribute('data-testid') : null,
      clickable_role: clickable ? clickable.getAttribute('role') : null,
      clickable_haspopup: clickable ? clickable.getAttribute('aria-haspopup') : null,
      clickable_data_state: clickable ? clickable.getAttribute('data-state') : null,
      clickable_headerish: clickable ? isHeaderish(clickable) : false,
      clickable_sidebar_like: clickable ? isSidebarControl(clickable) : false,
      clickable_home_link_like: clickable ? isHomeLinkLike(clickable) : false,
      clickable_composer_like: clickable ? isComposerControl(clickable) : false,
      clickable_reasoning_like: clickable ? isReasoningControl(clickable) : false,
    });
  });

  const textCandidateSelector = 'button, [role=button], [role=combobox], [aria-haspopup], a, span, div';
  Array.from(document.querySelectorAll(textCandidateSelector)).forEach((el) => {
    if (!isHeaderish(el) || isSensitive(el)) return;
    const raw = rawVisibleText(el);
    const text = compact(raw);
    if (!textLooksSafeModel(text) || text.length > 100) return;
    const clickable = modelClickableFor(el);
    const unique = clickable ? uniqueSelector(clickable) : uniqueSelector(el);
    out.text_model_candidates.push({
      text: gatedRaw(text, 140),
      tag: (el.tagName || '').toLowerCase(),
      testid: el.getAttribute('data-testid'),
      role: el.getAttribute('role'),
      rect: rectShape(el),
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      clickable_tag: clickable ? (clickable.tagName || '').toLowerCase() : null,
      clickable_headerish: clickable ? isHeaderish(clickable) : false,
      clickable_sidebar_like: clickable ? isSidebarControl(clickable) : false,
      clickable_home_link_like: clickable ? isHomeLinkLike(clickable) : false,
      clickable_composer_like: clickable ? isComposerControl(clickable) : false,
      clickable_reasoning_like: clickable ? isReasoningControl(clickable) : false,
    });
  });

  function chooseBestTrigger() {
    const modelTestid = clickables
      .filter((el) => {
        const tid = (el.getAttribute('data-testid') || '').toLowerCase();
        return tid.includes('model-switcher') || tid.includes('model');
      })
      .sort((a, b) => {
        const at = (a.getAttribute('data-testid') || '').toLowerCase();
        const bt = (b.getAttribute('data-testid') || '').toLowerCase();
        const ap = at.includes('model-switcher') ? 0 : 1;
        const bp = bt.includes('model-switcher') ? 0 : 1;
        return ap - bp;
      });
    if (modelTestid.length) return {el: modelTestid[0], reason: 'priority-a:data-testid-model-or-switcher'};

    for (const candidate of out.doc_model_candidates) {
      if (candidate.clickable_headerish && !candidate.clickable_sidebar_like && !candidate.clickable_home_link_like && !candidate.clickable_composer_like && !candidate.clickable_reasoning_like && candidate.selector && candidate.selector_count >= 1) {
        const el = document.querySelector(candidate.selector);
        if (el && isVisible(el) && !isSensitive(el)) return {el, reason: 'priority-b:header-model-text-clickable-ancestor'};
      }
      if (candidate.element_headerish && !candidate.clickable_sidebar_like && !candidate.clickable_home_link_like && candidate.element_selector && candidate.element_selector_count >= 1) {
        const el = document.querySelector(candidate.element_selector);
        if (el && isVisible(el) && !isSensitive(el)) return {el, reason: 'priority-b:header-model-text-element'};
      }
    }
    for (const candidate of out.text_model_candidates) {
      if (candidate.clickable_headerish && !candidate.clickable_sidebar_like && !candidate.clickable_home_link_like && !candidate.clickable_composer_like && !candidate.clickable_reasoning_like && candidate.selector && candidate.selector_count >= 1) {
        const el = document.querySelector(candidate.selector);
        if (el && isVisible(el) && !isSensitive(el)) return {el, reason: 'priority-b:header-full-text-model-candidate'};
      }
    }

    const haspopup = clickables.filter((el) => {
      const hp = el.getAttribute('aria-haspopup');
      return isHeaderish(el) && !isSidebarControl(el) && hp === 'menu' && !isComposerControl(el) && !isReasoningControl(el);
    });
    if (haspopup.length) return {el: haspopup[0], reason: 'priority-c:header-menu-popup-not-composer-account-reasoning'};
    return null;
  }
  const chosen = chooseBestTrigger();
  if (chosen) {
    out.best_trigger = buttonShape(chosen.el);
    out.best_trigger_reason = chosen.reason;
  }

  const rootSelector = '[data-radix-popper-content-wrapper], [role=menu], [role=listbox], [data-radix-menu-content], [data-radix-dropdown-menu-content]';
  Array.from(document.querySelectorAll(rootSelector)).forEach((el) => {
    if (!isVisible(el) || isSensitive(el)) return;
    const unique = uniqueSelector(el);
    out.portal_roots.push(Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      text: gatedElementText(el, 160),
    }));
  });

  const optionQuery = [
    '[data-radix-popper-content-wrapper] [role=menuitemradio]',
    '[data-radix-popper-content-wrapper] [role=option]',
    '[data-radix-popper-content-wrapper] [role=menuitem]',
    '[role=menu] [role=menuitemradio]',
    '[role=menu] [role=option]',
    '[role=menu] [role=menuitem]',
    '[role=listbox] [role=option]',
    '[data-radix-collection-item]',
    '[data-testid^=model-switcher]',
  ].join(', ');
  const seenOptions = new Set();
  Array.from(document.querySelectorAll(optionQuery)).forEach((el) => {
    if (!isVisible(el) || isSensitive(el)) return;
    if (seenOptions.has(el)) return;
    seenOptions.add(el);
    const opt = optionShape(el);
    const raw = compact(rawVisibleText(el));
    if (opt.is_model_option || /legacy models|more models|show more/i.test(raw) || opt.role === 'menuitemradio' || opt.role === 'option') {
      out.portal_options.push(opt);
    }
  });

  const selectorCandidates = [
    '[data-radix-popper-content-wrapper] [role=menuitemradio]',
    '[data-radix-popper-content-wrapper] [role=option]',
    '[data-radix-popper-content-wrapper] [role=menuitem]',
    '[role=menu] [role=menuitemradio]',
    '[role=menu] [role=option]',
    '[role=menu] [role=menuitem]',
    '[role=listbox] [role=option]',
    '[data-radix-collection-item][role=menuitemradio]',
    '[data-radix-collection-item][role=option]',
    '[data-radix-collection-item]',
  ];
  out.model_option_selector_counts = selectorCandidates.map((selector) => ({selector, visible_count: visibleCount(selector), dom_count: selectorCount(selector)}));
  const selectedOptionSelector = out.model_option_selector_counts.find((entry) => entry.visible_count > 0);
  if (selectedOptionSelector) {
    out.model_option_selector = selectedOptionSelector.selector;
    out.model_option_disabled_selector = selectedOptionSelector.selector + '[aria-disabled=true], '
      + selectedOptionSelector.selector + '[data-disabled=true], '
      + selectedOptionSelector.selector + '[disabled]';
  }

  const labelSeen = new Set();
  out.portal_options.forEach((opt) => {
    if (!opt.enabled || !opt.is_model_option || opt.model_label === NON_MODEL_TEXT) return;
    if (!labelSeen.has(opt.model_label)) {
      labelSeen.add(opt.model_label);
      out.available_model_labels.push(opt.model_label);
    }
  });
  out.submenu_or_more_models_visible = out.portal_options.some((opt) => opt.is_submenu_or_more_models);
  return out;
}
'''


def _selector_count(page: Any, selector: str | None) -> int:
    if not selector:
        return 0
    try:
        return int(page.locator(selector).count())
    except PlaywrightError:
        return -1


def _trigger_state(page: Any, selector: str | None) -> dict[str, Any]:
    if not selector:
        return {}
    try:
        loc = page.locator(selector)
        if loc.count() < 1:
            return {'count': 0}
        return loc.first.evaluate('''element => ({
          count: 1,
          aria_expanded: element.getAttribute('aria-expanded'),
          data_state: element.getAttribute('data-state'),
          aria_haspopup: element.getAttribute('aria-haspopup')
        })''')
    except PlaywrightError as exc:
        return {'error': exc.__class__.__name__}


def _md_code(value: object) -> str:
    text = redact('n/a' if value in (None, '') else value)
    return '`' + text.replace('`', '\\`') + '`'


def _json_evidence(value: object) -> str:
    return redact(json.dumps(value, indent=2, sort_keys=True))


def _write_markdown(path: Path, text: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(text).rstrip() + '\n', encoding='utf-8')


def _write_discovery_markdown(path: Path, payload: dict[str, Any]) -> None:
    verdict = payload.get('verdict', 'HONEST-FAIL-CLOSED')
    model_menu_selector = payload.get('model_menu_selector')
    model_menu_count = payload.get('model_menu_count')
    option_selector = payload.get('model_option_selector')
    option_count = payload.get('model_option_count_open')
    disabled_selector = payload.get('model_option_disabled_selector')
    matching_rule = payload.get('matching_rule') or 'n/a'
    fail_closed_reason = payload.get('fail_closed_reason')
    labels = list(payload.get('available_model_labels') or [])
    if labels:
        label_lines = ['- ' + _md_code(label) for label in labels]
    else:
        label_lines = ['- n/a']
    evidence = {
        'chosen_trigger': payload.get('chosen_trigger'),
        'closed_modelish_testids': (payload.get('closed_state') or {}).get('modelish_testids'),
        'header_buttons': (payload.get('closed_state') or {}).get('header_buttons'),
        'text_model_candidates': (payload.get('closed_state') or {}).get('text_model_candidates'),
        'top_main_elements': (payload.get('closed_state') or {}).get('top_main_elements'),
        'portal_roots': (payload.get('opened_state') or {}).get('portal_roots'),
        'portal_options': (payload.get('opened_state') or {}).get('portal_options'),
        'refindability': payload.get('refindability'),
        'escape_confirmation': payload.get('escape_confirmation'),
    }
    lines = [
        '# M-010 model picker discovery',
        '',
        '## Verdict',
        '- Verdict: ' + _md_code(verdict),
        '- fail-closed reason: ' + _md_code(fail_closed_reason),
        '',
        '## Selectors',
        '- model_menu selector: ' + _md_code(model_menu_selector),
        '- model_menu .count(): ' + _md_code(model_menu_count),
        '- model_option selector strategy: ' + _md_code(option_selector),
        '- model_option count while open: ' + _md_code(option_count),
        '- matching rule: ' + matching_rule,
        '- model_option_disabled strategy: ' + _md_code(disabled_selector),
        '',
        '## Available model labels',
        *label_lines,
        '',
        '## Notes',
        '- If fewer than 2 available labels are listed, the account did not expose a two-switchable set in the observed top-level menu.',
        '- Portal dropdown behavior means production selection must open the trigger before locating options.',
        '',
        '## DOM evidence (redacted shapes)',
        '```json',
        _json_evidence(evidence),
        '```',
    ]
    _write_markdown(path, '\n'.join(lines))


def leg_model_discovery(_args: argparse.Namespace) -> int:
    '''Read-mostly: enumerate the real model picker. Open the menu, dump options, Escape (no select).'''
    report = REPORT_DIR / 'T1-model-discovery.json'
    discovery_md = REPORT_DIR / 'discovery.md'
    payload: dict[str, Any] = {
        'stage': 'start',
        'verdict': 'HONEST-FAIL-CLOSED',
        'started_at': datetime.now().astimezone().isoformat(),
    }
    session: BrowserSession | None = None
    close_on_exit = True
    try:
        session = connect()
        try:
            session.open_or_create_conversation(None)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            payload['stage'] = 'open'
            payload['result'] = _human_label(exc)
            _write_json(report, payload)
            return 5
        if not recheck_safe(session):
            close_on_exit = False
            payload['stage'] = 'open-safety'
            payload['result'] = 'HUMAN-ACTION-NEEDED'
            _write_json(report, payload)
            return 5
        page = session.page
        if page is None:
            raise AskChatGPTError('Browser page is unavailable after connect')

        poll_rows: list[dict[str, Any]] = []
        t0 = time.monotonic()
        closed: dict[str, Any] = {}
        while True:
            closed = page.evaluate(_MODEL_ENUMERATE_JS)
            elapsed = round(time.monotonic() - t0, 2)
            poll_rows.append({
                'elapsed_s': elapsed,
                'header_buttons': len(closed.get('header_buttons', [])),
                'trigger_candidates': len(closed.get('trigger_candidates', [])),
                'best_trigger': bool(closed.get('best_trigger')),
                'modelish_testids': closed.get('modelish_testids', []),
            })
            if elapsed >= 1.5 and closed.get('best_trigger'):
                break
            if elapsed >= 10.0:
                break
            page.wait_for_timeout(500)
        payload['hydration_poll'] = poll_rows
        payload['closed_state'] = closed
        audit({'leg': 'T1-model-discovery', 'action': 'closed-state enumerate after hydration wait',
               'prompt-label': 'n/a',
               'observation': 'headers=%s,triggers=%s,best=%s' % (len(closed.get('header_buttons', [])), len(closed.get('trigger_candidates', [])), bool(closed.get('best_trigger'))),
               'markers': 'n/a', 'result': 'OK'})
        if not recheck_safe(session):
            close_on_exit = False
            payload['stage'] = 'post-hydration-safety'
            payload['result'] = 'HUMAN-ACTION-NEEDED'
            _write_json(report, payload)
            return 5

        chosen = closed.get('best_trigger')
        payload['chosen_trigger'] = chosen
        payload['chosen_trigger_reason'] = closed.get('best_trigger_reason')
        opened: dict[str, Any] = {'portal_options': [], 'portal_roots': []}
        if not chosen or not chosen.get('selector'):
            payload['stage'] = 'done'
            payload['fail_closed_reason'] = 'no model-menu trigger candidate after broad hydrated search'
            _write_json(report, payload)
            _write_discovery_markdown(discovery_md, payload)
            audit({'leg': 'T1-model-discovery', 'action': 'choose trigger', 'prompt-label': 'n/a',
                   'observation': 'no trigger candidate', 'markers': 'n/a', 'result': 'HONEST-FAIL-CLOSED'})
            _emit('MODEL-DISCOVERY: HONEST-FAIL-CLOSED no-trigger')
            return 0

        selector = str(chosen.get('selector'))
        payload['model_menu_selector'] = selector
        payload['model_menu_count'] = _selector_count(page, selector)
        payload['trigger_state_before_open'] = _trigger_state(page, selector)
        try:
            page.locator(selector).first.click(timeout=5000)
            page.wait_for_timeout(1000)
            opened = page.evaluate(_MODEL_ENUMERATE_JS)
            payload['opened_state'] = opened
            option_selector = opened.get('model_option_selector')
            payload['model_option_selector'] = option_selector
            payload['model_option_disabled_selector'] = opened.get('model_option_disabled_selector')
            payload['model_option_count_open'] = _selector_count(page, option_selector)
            payload['available_model_labels'] = opened.get('available_model_labels', [])
            payload['submenu_or_more_models_visible'] = opened.get('submenu_or_more_models_visible')
            payload['matching_rule'] = (
                'For the observed Radix portal, open model_menu first, then inspect each model_option. '
                'The safe model label is the first visible line matching MODEL_RE (opened_state.portal_options[].model_label). '
                'Current production exact full inner_text matching will only work when requested equals option.inner_text().strip(); '
                'if full_label_text is multi-line, T2 should match requested against model_label and click its owning option.'
            )
            payload['refindability'] = {
                'model_menu_selector': selector,
                'model_menu_count': payload.get('model_menu_count'),
                'model_option_selector': option_selector,
                'model_option_count_open': payload.get('model_option_count_open'),
            }
            audit({'leg': 'T1-model-discovery', 'action': 'open trigger + enumerate portal options',
                   'prompt-label': 'n/a',
                   'observation': 'options=%s,available=%s' % (len(opened.get('portal_options', [])), len(opened.get('available_model_labels', []))),
                   'markers': 'Escape pending', 'result': 'OK'})
        except PlaywrightError as exc:
            payload['open_error'] = exc.__class__.__name__
        finally:
            try:
                page.keyboard.press('Escape')
                page.wait_for_timeout(500)
            except PlaywrightError as exc:
                payload['escape_error'] = exc.__class__.__name__
        after_escape = page.evaluate(_MODEL_ENUMERATE_JS)
        payload['after_escape_state_summary'] = {
            'portal_options': len(after_escape.get('portal_options', [])),
            'portal_roots': len(after_escape.get('portal_roots', [])),
            'best_trigger_state': after_escape.get('best_trigger'),
        }
        payload['escape_confirmation'] = {
            'trigger_state_after_escape': _trigger_state(page, selector),
            'open_portal_options_after_escape': len(after_escape.get('portal_options', [])),
            'script_clicked_option': False,
        }

        available = list(payload.get('available_model_labels') or [])
        option_count = int(payload.get('model_option_count_open') or 0)
        if option_count >= 1 and available:
            payload['verdict'] = 'FOUND'
        else:
            payload['fail_closed_reason'] = 'trigger opened but no targetable model options were found'
        payload['stage'] = 'done'
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        _write_json(report, payload)
        _write_discovery_markdown(discovery_md, payload)
        audit({'leg': 'T1-model-discovery', 'action': 'Escape close + refindability report',
               'prompt-label': 'n/a',
               'observation': 'menu_count=%s,option_count=%s,labels=%s' % (payload.get('model_menu_count'), payload.get('model_option_count_open'), len(available)),
               'markers': 'no option selected', 'result': payload.get('verdict')})
        _emit('MODEL-DISCOVERY: %s menu_count=%s option_count=%s labels=%s' % (payload.get('verdict'), payload.get('model_menu_count'), payload.get('model_option_count_open'), len(available)))
        return 0
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        payload['stage'] = 'error'
        payload['error'] = '%s: %s' % (exc.__class__.__name__, redact(str(exc))[:200])
        _write_json(report, payload)
        _emit('ERROR: %s: %s' % (exc.__class__.__name__, exc))
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


_MODEL_OPEN_PROBE_JS = r'''
(args) => {
  args = args || {};
  const mode = args.mode || 'full';
  const portalOnly = !!args.portal_only;
  const limit = Number(args.limit || 12);

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
  const MODEL_LABEL_RE = /\b(?:(?:ChatGPT\s*)?GPT[-\s]?\d(?:\.\d+)?(?:[-\s]?(?:mini|nano|thinking|pro|turbo|legacy|auto))?|o[1-9](?:[-\s]?(?:mini|pro|high|low|medium|preview))?|[45]\.\d+(?:\s*(?:Thinking|Auto|Pro|Mini))?|Auto|Thinking)\b/i;
  const NON_MODEL_TEXT = '<non-model-text>';
  const NON_MODEL_ARIA = '<non-model-aria>';
  const SENSITIVE_TEXT_RE = /\b(account|profile|email|avatar|personal|plan|billing|subscription|plus)\b|user[-_ ]?menu|display[-_ ]?name|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
  const CONTROL_SELECTOR = 'button, [role="button"], [aria-haspopup], [role="combobox"]';
  const DOC_CANDIDATE_SELECTOR = 'button, [role="button"], [role="combobox"]';

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
  function containsCaret(el) {
    const blob = attrBlob(el);
    if (/\b(chevron|caret|arrow-down|down-chevron|dropdown|select)\b/.test(blob)) return true;
    if (/[⌄⌃⌵⌃▾▴▿▵˅∨]/.test(ownText(el))) return true;
    return Array.from(el.querySelectorAll('svg')).some((svg) => {
      const s = attrBlob(svg) + ' ' + (svg.getAttribute('data-icon') || '').toLowerCase()
        + ' ' + (svg.getAttribute('aria-label') || '').toLowerCase();
      return /\b(chevron|caret|arrow-down|down-chevron|dropdown)\b/.test(s);
    });
  }
  function controlLooksLikeModelCarrier(el) {
    const blob = attrBlob(el);
    return /model|switcher/.test(blob) || el.getAttribute('role') === 'combobox'
        || !!el.getAttribute('aria-haspopup') || !!el.getAttribute('data-state') || containsCaret(el);
  }
  function gatedRaw(value, limit) {
    if (!textLooksSafeModel(value)) return NON_MODEL_TEXT;
    return String(value || '').trim().slice(0, limit);
  }
  function gatedControlRaw(el, value, limit) {
    if (!controlLooksLikeModelCarrier(el)) return NON_MODEL_TEXT;
    return gatedRaw(value, limit);
  }
  function safeAriaForOutput(el) {
    const a = safeAria(el);
    if (!a) return null;
    if (a === '<omitted>') return a;
    if (!textLooksSafeModel(a)) return NON_MODEL_ARIA;
    return a.slice(0, 80);
  }
  function hasSensitiveVisibleText(el) {
    return SENSITIVE_TEXT_RE.test(compact(rawVisibleText(el)));
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
      if (selectorCount(selector) === 1) return {selector, count: 1, basis: 'testid'};
    }
    const role = el.getAttribute('role');
    if (role) {
      const selector = tag + '[role=' + qAttr(role) + ']';
      if (selectorCount(selector) === 1) return {selector, count: 1, basis: 'role'};
    }
    const aria = el.getAttribute('aria-label');
    if (aria && textLooksSafeModel(aria)) {
      const selector = tag + '[aria-label=' + qAttr(aria) + ']';
      if (selectorCount(selector) === 1) return {selector, count: 1, basis: 'model-aria'};
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
  function isDisabled(el) {
    return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.getAttribute('data-disabled') === 'true'
        || !!el.closest('[aria-disabled=true], [data-disabled=true], [disabled]');
  }
  function baseShape(el) {
    return {
      tag: (el.tagName || '').toLowerCase(),
      testid: el.getAttribute('data-testid'),
      role: el.getAttribute('role'),
      aria_label: safeAriaForOutput(el),
      aria_haspopup: el.getAttribute('aria-haspopup'),
      aria_expanded: el.getAttribute('aria-expanded'),
      aria_checked: el.getAttribute('aria-checked'),
      aria_selected: el.getAttribute('aria-selected'),
      data_state: el.getAttribute('data-state'),
      disabled: isDisabled(el),
    };
  }
  function buttonShape(el) {
    const unique = uniqueSelector(el);
    const text = rawVisibleText(el);
    const own = ownText(el);
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      own_text: gatedControlRaw(el, own, 160),
      text: gatedControlRaw(el, text, 160),
      text_matches_model: textLooksSafeModel(own) || textLooksSafeModel(text),
      contains_caret: containsCaret(el),
      rect: rectShape(el),
    });
  }
  function containerShape(el, childIndex) {
    const unique = uniqueSelector(el);
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      child_index: childIndex,
      own_text: gatedControlRaw(el, ownText(el), 160),
      text: NON_MODEL_TEXT,
      rect: rectShape(el),
    });
  }
  function firstModelLine(raw) {
    const lines = String(raw || '').split(/\n+/).map((line) => compact(line)).filter(Boolean);
    for (const line of lines) {
      if (/legacy models|more models|show more|upgrade|plus|plan|billing|subscription/i.test(line)) continue;
      const match = line.match(MODEL_LABEL_RE);
      if (match && textLooksSafeModel(match[0])) return match[0].slice(0, 160);
      if (textLooksSafeModel(line) && line.length <= 40) return line.slice(0, 160);
    }
    return NON_MODEL_TEXT;
  }
  function optionShape(el) {
    const unique = uniqueSelector(el);
    const raw = rawVisibleText(el);
    const normalized = compact(raw);
    const modelLabel = firstModelLine(raw);
    const submenu = /legacy models|more models|show more/i.test(normalized) || el.getAttribute('aria-haspopup') === 'menu';
    return Object.assign(baseShape(el), {
      selector: unique.selector,
      selector_count: unique.count,
      selector_basis: unique.basis,
      rect: rectShape(el),
      full_label_text: gatedRaw(raw, 900),
      model_label: modelLabel,
      is_submenu_or_more_models: submenu,
      is_model_option: modelLabel !== NON_MODEL_TEXT && !submenu,
      value_attr_model_gated: gatedRaw(el.getAttribute('value') || '', 160),
    });
  }
  function visibleCount(selector) {
    try {
      return Array.from(document.querySelectorAll(selector)).filter((el) => isVisible(el) && !isSensitive(el) && !hasSensitiveVisibleText(el)).length;
    } catch (e) {
      return -1;
    }
  }
  function selectedOptionSelector(counts) {
    const found = counts.find((entry) => entry.visible_count > 0);
    return found ? found.selector : null;
  }
  function optionDisabledSelector(selector) {
    if (!selector) return null;
    return selector + '[aria-disabled=true], ' + selector + '[data-disabled=true], ' + selector + '[disabled]';
  }
  function addUniqueControl(list, seen, el, source) {
    if (!isVisible(el) || isSensitive(el) || hasSensitiveVisibleText(el)) return;
    const shape = buttonShape(el);
    if (!shape.selector || seen.has(shape.selector)) return;
    seen.add(shape.selector);
    shape.source = source;
    list.push(shape);
  }
  function isSidebarNavHistory(el) {
    const nav = el.closest('nav');
    if (nav && !el.closest('header')) return true;
    const tid = (el.getAttribute('data-testid') || '').toLowerCase();
    return tid.includes('history-item') || !!el.closest('a[href^="/c/"]');
  }
  function isComposerPlusUploadSend(el) {
    const blob = attrBlob(el);
    const text = compact(ownText(el) || rawVisibleText(el)).toLowerCase();
    return blob.includes('composer-plus') || blob.includes('upload') || blob.includes('attach')
        || blob.includes('send-button') || blob.includes('send message') || text === '+' || text === '＋';
  }
  function promptElement() {
    return document.querySelector('#prompt-textarea');
  }
  function composerForm() {
    const p = promptElement();
    return p ? p.closest('form') : null;
  }
  function composerRootElements() {
    const p = promptElement();
    if (!p) return [];
    const roots = [];
    const form = composerForm();
    if (form) roots.push(form);
    let cur = p.parentElement;
    let hops = 0;
    while (cur && cur !== document.body && hops < 6) {
      const r = cur.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.height <= 360) roots.push(cur);
      cur = cur.parentElement;
      hops += 1;
    }
    return Array.from(new Set(roots));
  }
  function isNearComposer(el) {
    return composerRootElements().some((root) => root.contains(el));
  }
  function inThreadScope(el) {
    if (mode !== 'thread') return true;
    return !!el.closest('header') || isNearComposer(el);
  }
  function docCandidateReasons(el) {
    const own = ownText(el);
    const text = rawVisibleText(el);
    const reasons = [];
    if (el.hasAttribute('aria-haspopup')) reasons.push('aria-haspopup');
    if (el.getAttribute('data-state') === 'closed') reasons.push('data-state=closed');
    if (containsCaret(el)) reasons.push('contains-caret');
    if (textLooksSafeModel(own) || textLooksSafeModel(text)) reasons.push('own-text-model');
    return reasons;
  }
  function candidateExcluded(el) {
    return isSensitive(el) || hasSensitiveVisibleText(el) || isSidebarNavHistory(el) || isComposerPlusUploadSend(el) || isDisabled(el) || !inThreadScope(el);
  }
  function addCandidate(map, el, source, reasons) {
    if (!isVisible(el) || candidateExcluded(el)) return;
    const shape = buttonShape(el);
    if (!shape.selector) return;
    if (!map.has(shape.selector)) {
      shape.sources = [];
      shape.candidate_reasons = [];
      map.set(shape.selector, shape);
    }
    const entry = map.get(shape.selector);
    if (!entry.sources.includes(source)) entry.sources.push(source);
    for (const reason of reasons) if (!entry.candidate_reasons.includes(reason)) entry.candidate_reasons.push(reason);
  }
  function enumeratePortal() {
    const roots = [];
    const options = [];
    const rootSelector = '[data-radix-popper-content-wrapper], [role="menu"], [role="listbox"], [data-radix-menu-content], [data-radix-dropdown-menu-content]';
    const optionSelector = '[role="menuitem"], [role="menuitemradio"], [role="option"], [data-radix-collection-item]';
    const seenRoots = new Set();
    const seenOptions = new Set();
    Array.from(document.querySelectorAll(rootSelector)).forEach((root) => {
      if (!isVisible(root) || isSensitive(root)) return;
      const unique = uniqueSelector(root);
      if (!unique.selector || seenRoots.has(unique.selector)) return;
      seenRoots.add(unique.selector);
      roots.push(Object.assign(baseShape(root), {
        selector: unique.selector,
        selector_count: unique.count,
        selector_basis: unique.basis,
        rect: rectShape(root),
        text: NON_MODEL_TEXT,
      }));
      Array.from(root.querySelectorAll(optionSelector)).forEach((el) => {
        if (!isVisible(el) || isSensitive(el) || hasSensitiveVisibleText(el)) return;
        if (seenOptions.has(el)) return;
        seenOptions.add(el);
        options.push(optionShape(el));
      });
    });
    const selectorCandidates = [
      '[data-radix-popper-content-wrapper] [role=menuitemradio]',
      '[data-radix-popper-content-wrapper] [role=option]',
      '[data-radix-popper-content-wrapper] [role=menuitem]',
      '[role=menu] [role=menuitemradio]',
      '[role=menu] [role=option]',
      '[role=menu] [role=menuitem]',
      '[role=listbox] [role=option]',
      '[data-radix-collection-item][role=menuitemradio]',
      '[data-radix-collection-item][role=option]',
      '[data-radix-collection-item]',
    ];
    const counts = selectorCandidates.map((selector) => ({selector, visible_count: visibleCount(selector), dom_count: selectorCount(selector)}));
    const optSelector = selectedOptionSelector(counts);
    const labelSeen = new Set();
    const available = [];
    options.forEach((opt) => {
      if (opt.disabled || !opt.is_model_option || opt.model_label === NON_MODEL_TEXT) return;
      if (!labelSeen.has(opt.model_label)) {
        labelSeen.add(opt.model_label);
        available.push(opt.model_label);
      }
    });
    return {roots, options, counts, optSelector, disabledSelector: optionDisabledSelector(optSelector), available};
  }

  const out = {
    url_path: location.pathname.replace(/\/c\/[^/?#\s]+/g, '/c/<redacted>'),
    mode,
    hydrated_markers: {
      ready_root_present: document.querySelectorAll('main:has(#prompt-textarea)').length,
      composer_present: document.querySelectorAll('#prompt-textarea').length,
      header_present: document.querySelectorAll('header').length,
    },
    composer_controls: [],
    header_controls_all: [],
    header_left_containers: [],
    header_left_controls: [],
    document_candidates: [],
    candidate_list: [],
    portal_roots: [],
    portal_options: [],
    model_option_selector_counts: [],
    model_option_selector: null,
    model_option_disabled_selector: null,
    available_model_labels: [],
  };

  const portal = enumeratePortal();
  out.portal_roots = portal.roots;
  out.portal_options = portal.options;
  out.model_option_selector_counts = portal.counts;
  out.model_option_selector = portal.optSelector;
  out.model_option_disabled_selector = portal.disabledSelector;
  out.available_model_labels = portal.available;
  if (portalOnly) return out;

  const composerSeen = new Set();
  const p = promptElement();
  const form = composerForm();
  if (p) {
    const composerCandidates = new Set();
    if (form) Array.from(form.querySelectorAll(CONTROL_SELECTOR)).forEach((el) => composerCandidates.add(el));
    let cur = p.parentElement;
    let hops = 0;
    while (cur && cur !== document.body && hops < 5) {
      Array.from(cur.querySelectorAll(CONTROL_SELECTOR)).forEach((el) => {
        if (isNearComposer(el)) composerCandidates.add(el);
      });
      cur = cur.parentElement;
      hops += 1;
    }
    Array.from(document.querySelectorAll(CONTROL_SELECTOR)).forEach((el) => {
      if (isNearComposer(el)) composerCandidates.add(el);
    });
    Array.from(composerCandidates).forEach((el) => addUniqueControl(out.composer_controls, composerSeen, el, 'composer'));
  }

  const header = document.querySelector('header');
  const headerSeen = new Set();
  const headerLeftSeen = new Set();
  const leftChildren = header ? Array.from(header.children).slice(0, 2) : [];
  if (header) {
    leftChildren.forEach((child, index) => {
      if (isVisible(child) && !isSensitive(child) && !hasSensitiveVisibleText(child)) out.header_left_containers.push(containerShape(child, index));
    });
    Array.from(header.querySelectorAll(CONTROL_SELECTOR)).forEach((el) => {
      addUniqueControl(out.header_controls_all, headerSeen, el, 'header');
      const inLeftChild = leftChildren.some((child) => child.contains(el));
      const r = el.getBoundingClientRect();
      const leftish = r.left < (window.innerWidth || 1200) * 0.62;
      const rightActions = !!el.closest('[data-testid="thread-header-right-actions"], [data-testid="thread-header-right-actions-container"]');
      if ((inLeftChild || leftish) && !rightActions) addUniqueControl(out.header_left_controls, headerLeftSeen, el, 'header-left');
    });
  }

  const candidateMap = new Map();
  out.composer_controls.forEach((shape) => {
    const el = document.querySelector(shape.selector);
    if (el && !isComposerPlusUploadSend(el)) addCandidate(candidateMap, el, 'composer', ['composer-step1']);
  });
  out.header_left_controls.forEach((shape) => {
    const el = document.querySelector(shape.selector);
    if (el) addCandidate(candidateMap, el, 'header-left', ['header-left-step2']);
  });
  const docSeen = new Set();
  Array.from(document.querySelectorAll(DOC_CANDIDATE_SELECTOR)).forEach((el) => {
    if (!isVisible(el) || candidateExcluded(el)) return;
    const reasons = docCandidateReasons(el);
    if (!reasons.length) return;
    const shape = buttonShape(el);
    if (!shape.selector || docSeen.has(shape.selector)) return;
    docSeen.add(shape.selector);
    shape.candidate_reasons = reasons;
    out.document_candidates.push(shape);
    addCandidate(candidateMap, el, 'document', reasons);
  });
  out.candidate_list = Array.from(candidateMap.values()).sort((a, b) => {
    const am = a.text_matches_model ? 0 : 1;
    const bm = b.text_matches_model ? 0 : 1;
    if (am !== bm) return am - bm;
    if (a.rect.top !== b.rect.top) return a.rect.top - b.rect.top;
    return a.rect.left - b.rect.left;
  }).slice(0, limit);
  return out;
}
'''


def _model_labels_from_options(options: list[dict[str, Any]] | None, *, require_enabled: bool = True) -> list[str]:
    labels: list[str] = []
    for option in options or []:
        label = option.get('model_label')
        if not isinstance(label, str) or label == '<non-model-text>' or not label:
            continue
        if option.get('is_submenu_or_more_models'):
            continue
        if require_enabled and option.get('disabled'):
            continue
        if label not in labels:
            labels.append(label)
    return labels


def _open_probe_matching_rule() -> str:
    return (
        'Open model_menu, then locate model_option elements. Production BrowserSession._find_model_option '
        'matches exactly when requested == option.get_attribute("value") OR requested == option.inner_text().strip(); '
        'the report labels are the first visible model-looking line (model_label) only for human-readable inventory.'
    )


def _portal_open_summary(state: dict[str, Any]) -> dict[str, Any]:
    options = list(state.get('portal_options') or [])
    labels = _model_labels_from_options(options, require_enabled=True)
    model_like = [opt for opt in options if opt.get('model_label') not in (None, '', '<non-model-text>') and not opt.get('is_submenu_or_more_models')]
    return {
        'portal_root_count': len(state.get('portal_roots') or []),
        'option_count': len(options),
        'model_like_option_count': len(model_like),
        'available_model_labels': labels,
        'model_option_selector': state.get('model_option_selector'),
        'model_option_disabled_selector': state.get('model_option_disabled_selector'),
    }


def _open_probe_click_candidate(session: BrowserSession, page: Any, *, pass_label: str, mode: str,
                                index: int, candidate: dict[str, Any]) -> dict[str, Any]:
    selector = candidate.get('selector')
    result: dict[str, Any] = {
        'pass_label': pass_label,
        'index': index,
        'candidate': candidate,
        'trigger_state_before': _trigger_state(page, str(selector) if selector else None),
    }
    stopped = False
    try:
        if not selector:
            result['open_error'] = 'missing-selector'
            return result
        if not recheck_safe(session):
            stopped = True
            raise HumanActionStop('HUMAN-ACTION-NEEDED')
        loc = page.locator(str(selector))
        result['selector_count_before_click'] = loc.count()
        if result['selector_count_before_click'] < 1:
            result['open_error'] = 'selector-not-found'
            return result
        loc.first.click(timeout=4000)
        page.wait_for_timeout(900)
        if not recheck_safe(session):
            stopped = True
            raise HumanActionStop('HUMAN-ACTION-NEEDED')
        opened = page.evaluate(_MODEL_OPEN_PROBE_JS, {'mode': mode, 'portal_only': True, 'limit': 12})
        result['opened_state'] = opened
        result['opened_summary'] = _portal_open_summary(opened)
        available = result['opened_summary']['available_model_labels']
        result['is_model_trigger'] = bool(result['opened_summary']['model_like_option_count'] >= 2 and len(available) >= 2)
        return result
    except HumanActionStop:
        raise
    except PlaywrightError as exc:
        result['open_error'] = exc.__class__.__name__
        return result
    finally:
        if not stopped:
            try:
                page.keyboard.press('Escape')
                page.wait_for_timeout(500)
                after_escape = page.evaluate(_MODEL_OPEN_PROBE_JS, {'mode': mode, 'portal_only': True, 'limit': 12})
                result['escape_confirmation'] = {
                    'trigger_state_after_escape': _trigger_state(page, str(selector) if selector else None),
                    'portal_roots_after_escape': len(after_escape.get('portal_roots') or []),
                    'portal_options_after_escape': len(after_escape.get('portal_options') or []),
                    'script_clicked_option': False,
                }
            except PlaywrightError as exc:
                result['escape_error'] = exc.__class__.__name__


def _run_model_open_pass(session: BrowserSession, page: Any, *, pass_label: str, mode: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = page.evaluate(_MODEL_OPEN_PROBE_JS, {'mode': mode, 'portal_only': False, 'limit': 12})
    candidates = list(state.get('candidate_list') or [])
    pass_payload: dict[str, Any] = {
        'pass_label': pass_label,
        'mode': mode,
        'enumeration': state,
        'candidate_results': [],
    }
    audit({'leg': 'T1b-model-open-probe', 'action': f'enumerate {pass_label}', 'prompt-label': 'n/a',
           'observation': 'composer=%s,header_left=%s,candidates=%s' % (len(state.get('composer_controls') or []), len(state.get('header_left_controls') or []), len(candidates)),
           'markers': 'no prompt sent', 'result': 'OK'})
    found: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        result = _open_probe_click_candidate(session, page, pass_label=pass_label, mode=mode, index=index, candidate=candidate)
        pass_payload['candidate_results'].append(result)
        summary = result.get('opened_summary') or {}
        audit({'leg': 'T1b-model-open-probe', 'action': f'click candidate {pass_label}#{index}',
               'prompt-label': 'n/a',
               'observation': 'roots=%s,options=%s,model_like=%s,labels=%s' % (summary.get('portal_root_count', 0), summary.get('option_count', 0), summary.get('model_like_option_count', 0), len(summary.get('available_model_labels') or [])),
               'markers': 'Escape,no selection', 'result': 'FOUND' if result.get('is_model_trigger') else result.get('open_error', 'not-model')})
        if result.get('is_model_trigger'):
            found.append(result)
    return pass_payload, found


def _compact_clicked_summary(passes: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for passed in passes:
        label = passed.get('pass_label')
        results = list(passed.get('candidate_results') or [])
        opened = []
        for result in results:
            summary = result.get('opened_summary') or {}
            opened.append('%s/%s' % (summary.get('option_count', 0), summary.get('model_like_option_count', 0)))
        parts.append('%s: clicked=%s opened(option/model-like)=[%s]' % (label, len(results), ','.join(opened) if opened else 'none'))
    return '; '.join(parts) if parts else 'none'


def _found_payload_from_result(page: Any, result: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(result.get('candidate') or {})
    selector = candidate.get('selector')
    opened = dict(result.get('opened_state') or {})
    labels = _model_labels_from_options(list(opened.get('portal_options') or []), require_enabled=True)
    return {
        'pass_label': result.get('pass_label'),
        'candidate_index': result.get('index'),
        'model_menu_selector': selector,
        'model_menu_count': _selector_count(page, str(selector) if selector else None),
        'model_menu': candidate,
        'model_option_selector': opened.get('model_option_selector'),
        'model_option_count_open': next((entry.get('visible_count') for entry in opened.get('model_option_selector_counts') or [] if entry.get('selector') == opened.get('model_option_selector')), None),
        'model_option_disabled_selector': opened.get('model_option_disabled_selector'),
        'matching_rule': _open_probe_matching_rule(),
        'available_model_labels': labels,
        'opened_state': opened,
    }


def _write_open_probe_discovery_markdown(path: Path, payload: dict[str, Any]) -> None:
    found = payload.get('found') or {}
    verdict = payload.get('verdict', 'HONEST-FAIL-CLOSED')
    labels = list((found or payload).get('available_model_labels') or [])
    if labels:
        label_lines = ['- ' + _md_code(label) for label in labels]
    else:
        label_lines = ['- n/a']
    clicked_evidence = []
    for passed in payload.get('passes') or []:
        clicked_evidence.append({
            'pass_label': passed.get('pass_label'),
            'mode': passed.get('mode'),
            'composer_controls': len((passed.get('enumeration') or {}).get('composer_controls') or []),
            'header_left_controls': len((passed.get('enumeration') or {}).get('header_left_controls') or []),
            'candidates': [
                {
                    'index': r.get('index'),
                    'selector': (r.get('candidate') or {}).get('selector'),
                    'sources': (r.get('candidate') or {}).get('sources'),
                    'reasons': (r.get('candidate') or {}).get('candidate_reasons'),
                    'rect': (r.get('candidate') or {}).get('rect'),
                    'opened_summary': r.get('opened_summary'),
                    'open_error': r.get('open_error'),
                    'is_model_trigger': r.get('is_model_trigger'),
                    'escape_confirmation': r.get('escape_confirmation'),
                }
                for r in (passed.get('candidate_results') or [])
            ],
        })
    lines = [
        '# M-010 model picker discovery',
        '',
        '## Verdict',
        '- Verdict: ' + _md_code(verdict),
        '- status: ' + _md_code(payload.get('status', 'DONE')),
        '- fail-closed reason: ' + _md_code(payload.get('fail_closed_reason')),
        '- step4 used: ' + _md_code(', '.join(payload.get('step4_used') or []) or 'not needed'),
        '',
        '## Selectors',
        '- model_menu selector: ' + _md_code(found.get('model_menu_selector')),
        '- model_menu .count(): ' + _md_code(found.get('model_menu_count')),
        '- model_option selector strategy: ' + _md_code(found.get('model_option_selector')),
        '- model_option count while open: ' + _md_code(found.get('model_option_count_open')),
        '- matching rule: ' + (found.get('matching_rule') or 'n/a'),
        '- model_option_disabled strategy: ' + _md_code(found.get('model_option_disabled_selector')),
        '',
        '## Available model labels',
        *label_lines,
        '',
        '## Open-probe evidence',
        '- Click summary: ' + _md_code(payload.get('clicked_summary')),
        '- Checked composer toolbar, header-left/header first two containers, document candidates, and (if needed) in-conversation header+composer only.',
        '',
        '```json',
        _json_evidence(clicked_evidence),
        '```',
    ]
    _write_markdown(path, '\n'.join(lines))


def leg_model_open_probe(_args: argparse.Namespace) -> int:
    '''Open plausible model-picker candidates and enumerate their portals without selecting.''' 
    report = REPORT_DIR / 'T1b-open-probe.json'
    discovery_md = REPORT_DIR / 'discovery.md'
    t0 = time.monotonic()
    payload: dict[str, Any] = {
        'stage': 'start',
        'status': 'DONE',
        'verdict': 'HONEST-FAIL-CLOSED',
        'started_at': datetime.now().astimezone().isoformat(),
        'passes': [],
        'step4_used': [],
    }
    session: BrowserSession | None = None
    close_on_exit = True
    try:
        session = connect()
        try:
            session.open_or_create_conversation(None)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            payload['stage'] = 'open'
            payload['result'] = _human_label(exc)
            payload['status'] = 'BLOCKED'
            _write_json(report, payload)
            return 5
        if not recheck_safe(session):
            close_on_exit = False
            payload['stage'] = 'open-safety'
            payload['result'] = 'HUMAN-ACTION-NEEDED'
            payload['status'] = 'BLOCKED'
            _write_json(report, payload)
            return 5
        page = session.page
        if page is None:
            raise AskChatGPTError('Browser page is unavailable after connect')
        try:
            page.locator('#prompt-textarea').first.wait_for(timeout=10000)
        except PlaywrightError:
            pass

        audit({'leg': 'T1b-model-open-probe', 'action': 'open own tab conversation', 'prompt-label': 'n/a',
               'observation': 'open_or_create_conversation(None); no prompt sent', 'markers': 'attach-only', 'result': 'OK'})
        initial_pass, found_results = _run_model_open_pass(session, page, pass_label='home-initial', mode='full')
        payload['passes'].append(initial_pass)

        if not found_results:
            payload['step4_used'].append('4a composer focus + space/delete (no send)')
            try:
                page.locator('#prompt-textarea').first.click(timeout=4000)
                page.keyboard.type(' ')
                page.keyboard.press('Backspace')
                page.wait_for_timeout(1000)
            except PlaywrightError as exc:
                payload['step4a_error'] = exc.__class__.__name__
            if not recheck_safe(session):
                close_on_exit = False
                raise HumanActionStop('HUMAN-ACTION-NEEDED')
            audit({'leg': 'T1b-model-open-probe', 'action': 'Step4a focus composer space-delete',
                   'prompt-label': 'n/a', 'observation': 'no prompt sent', 'markers': 'no send', 'result': 'OK'})
            focus_pass, focus_found = _run_model_open_pass(session, page, pass_label='home-after-composer-focus', mode='full')
            payload['passes'].append(focus_pass)
            found_results.extend(focus_found)

        if not found_results:
            payload['step4_used'].append('4b most recent history conversation')
            history_count = 0
            try:
                history = page.locator('nav a[href^="/c/"]')
                history_count = history.count()
                payload['history_conversation_link_count'] = history_count
                if history_count < 1:
                    payload['status'] = 'PARTIAL'
                    payload['partial_reason'] = 'no nav a[href^="/c/"] history conversation link available for Step4b'
                else:
                    history.first.click(timeout=4000)
                    try:
                        page.wait_for_function("location.pathname.startsWith('/c/')", timeout=15000)
                    except PlaywrightError:
                        page.wait_for_timeout(2000)
                    if not recheck_safe(session):
                        close_on_exit = False
                        raise HumanActionStop('HUMAN-ACTION-NEEDED')
                    audit({'leg': 'T1b-model-open-probe', 'action': 'Step4b open most recent history conversation',
                           'prompt-label': 'n/a', 'observation': 'thread loaded; URL redacted; message area not enumerated',
                           'markers': 'no prompt sent', 'result': 'OK'})
                    thread_pass, thread_found = _run_model_open_pass(session, page, pass_label='thread-recent-header-composer', mode='thread')
                    payload['passes'].append(thread_pass)
                    found_results.extend(thread_found)
            except HumanActionStop:
                raise
            except PlaywrightError as exc:
                payload['status'] = 'PARTIAL'
                payload['step4b_error'] = exc.__class__.__name__

        if found_results:
            found = _found_payload_from_result(page, found_results[0])
            payload['found'] = found
            payload['verdict'] = 'FOUND'
            payload['model_menu_selector'] = found.get('model_menu_selector')
            payload['model_menu_count'] = found.get('model_menu_count')
            payload['model_option_selector'] = found.get('model_option_selector')
            payload['model_option_disabled_selector'] = found.get('model_option_disabled_selector')
            payload['matching_rule'] = found.get('matching_rule')
            payload['available_model_labels'] = found.get('available_model_labels')
        else:
            if payload.get('status') == 'PARTIAL':
                payload['fail_closed_reason'] = payload.get('partial_reason') or payload.get('step4b_error') or 'not all Step4 checks completed'
            else:
                payload['fail_closed_reason'] = 'Steps 1-4 ran; no clicked candidate opened a portal with at least two non-disabled model-name options'
        payload['clicked_summary'] = _compact_clicked_summary(list(payload.get('passes') or []))
        payload['stage'] = 'done'
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
        _write_json(report, payload)
        _write_open_probe_discovery_markdown(discovery_md, payload)
        audit({'leg': 'T1b-model-open-probe', 'action': 'write report + discovery verdict',
               'prompt-label': 'n/a', 'observation': payload.get('clicked_summary'),
               'markers': 'no option selected', 'result': payload.get('verdict')})
        _emit('MODEL-OPEN-PROBE: %s status=%s %s' % (payload.get('verdict'), payload.get('status'), payload.get('clicked_summary')))
        return 0 if payload.get('status') != 'PARTIAL' else 2
    except SystemExit:
        raise
    except HumanActionStop as exc:
        payload['stage'] = 'human-action-needed'
        payload['status'] = 'BLOCKED'
        payload['result'] = exc.label
        payload['clicked_summary'] = _compact_clicked_summary(list(payload.get('passes') or []))
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
        _write_json(report, payload)
        _write_open_probe_discovery_markdown(discovery_md, payload)
        return 5
    except Exception as exc:  # noqa: BLE001
        payload['stage'] = 'error'
        payload['status'] = 'PARTIAL'
        payload['error'] = '%s: %s' % (exc.__class__.__name__, redact(str(exc))[:240])
        payload['clicked_summary'] = _compact_clicked_summary(list(payload.get('passes') or []))
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
        _write_json(report, payload)
        _write_open_probe_discovery_markdown(discovery_md, payload)
        _emit('ERROR: %s: %s' % (exc.__class__.__name__, exc))
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


MODEL_CAPTURE_OPTION_SELECTOR = '[data-radix-popper-content-wrapper] [role="menuitemradio"]'
MODEL_CAPTURE_MENUITEM_SELECTOR = '[data-radix-popper-content-wrapper] [role="menuitem"]'
MODEL_CAPTURE_DISABLED_SELECTOR = (
    '[data-radix-popper-content-wrapper] [role="menuitemradio"][aria-disabled="true"], '
    '[data-radix-popper-content-wrapper] [role="menuitemradio"][data-disabled="true"], '
    '[data-radix-popper-content-wrapper] [role="menuitemradio"][disabled]'
)
MODEL_CAPTURE_STRUCTURAL_FALLBACK = (
    'body > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > '
    'div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > main:nth-of-type(1) > '
    'div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > '
    'div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(1) > '
    'div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(2) > '
    'div:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(1) > '
    'button:nth-of-type(1)'
)

_MODEL_CAPTURE_COMPOSER_BUTTONS_JS = r'''
() => {
  // Privacy: enumerate only composer menu buttons; never emit account/profile text.
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
    return a.slice(0, 80);
  }
  function ownText(el) {
    let s = '';
    for (const n of el.childNodes) if (n.nodeType === 3) s += n.textContent;
    return s.replace(/\s+/g, ' ').trim();
  }
  const MODEL_RE = /gpt|chatgpt|thinking|legacy|^auto$|\bauto\b|o[1-9]|[45]\.\d/i;
  const NON_MODEL_TEXT = '<non-model-text>';
  const NON_MODEL_ARIA = '<non-model-aria>';
  const SENSITIVE_TEXT_RE = /\b(account|profile|email|avatar|personal|plan|billing|subscription)\b|user[-_ ]?menu|display[-_ ]?name|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
  function compact(value) { return String(value || '').replace(/\s+/g, ' ').trim(); }
  function rawVisibleText(el) { return String(el.innerText || el.textContent || '').trim(); }
  function textLooksSafeModel(value) {
    const text = compact(value);
    return !!text && MODEL_RE.test(text) && !SENSITIVE_TEXT_RE.test(text);
  }
  function gatedRaw(value, limit) {
    if (!textLooksSafeModel(value)) return NON_MODEL_TEXT;
    return String(value || '').trim().slice(0, limit);
  }
  function safeAriaForOutput(el) {
    const a = safeAria(el);
    if (!a) return null;
    if (a === '<omitted>') return a;
    if (!textLooksSafeModel(a)) return NON_MODEL_ARIA;
    return a.slice(0, 80);
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
  function hasSensitiveVisibleText(el) { return SENSITIVE_TEXT_RE.test(compact(rawVisibleText(el))); }
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
  function isDisabled(el) {
    return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.getAttribute('data-disabled') === 'true'
        || !!el.closest('[aria-disabled=true], [data-disabled=true], [disabled]');
  }
  function selectorCount(selector) {
    try { return document.querySelectorAll(selector).length; } catch (e) { return -1; }
  }
  function qAttr(value) { return JSON.stringify(String(value)); }
  function classHash(el) {
    const cls = String(el.getAttribute('class') || '');
    let h = 2166136261;
    for (let i = 0; i < cls.length; i += 1) {
      h ^= cls.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return cls ? ('fnv1a32:' + h.toString(16).padStart(8, '0')) : null;
  }
  function rectShape(el) {
    const r = el.getBoundingClientRect();
    return {top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width), height: Math.round(r.height)};
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
  function excludedReason(el) {
    const blob = attrBlob(el);
    const text = compact(ownText(el) || rawVisibleText(el)).toLowerCase();
    if (isSensitive(el) || hasSensitiveVisibleText(el)) return 'sensitive/account-plan-personal';
    if (isDisabled(el)) return 'disabled';
    if (blob.includes('composer-plus') || blob.includes('upload') || blob.includes('attach') || text === '+' || text === '＋') return 'composer-plus/upload/attach';
    if (blob.includes('send-button') || blob.includes('send message')) return 'send';
    if (blob.includes('voice') || blob.includes('dictation') || blob.includes('microphone')) return 'dictation/voice';
    return null;
  }
  function buttonShape(el) {
    const cls = String(el.getAttribute('class') || '').trim();
    const text = rawVisibleText(el);
    const own = ownText(el);
    return {
      tag: (el.tagName || '').toLowerCase(),
      selector: structuralPath(el),
      selector_count: selectorCount(structuralPath(el)),
      testid: el.getAttribute('data-testid'),
      class_hash: classHash(el),
      class_token_count: cls ? cls.split(/\s+/).filter(Boolean).length : 0,
      role: el.getAttribute('role'),
      aria_label: safeAriaForOutput(el),
      aria_haspopup: el.getAttribute('aria-haspopup'),
      aria_expanded: el.getAttribute('aria-expanded'),
      data_state: el.getAttribute('data-state'),
      disabled: isDisabled(el),
      rect: rectShape(el),
      innerText_gated: gatedRaw(text, 160),
      own_text_gated: gatedRaw(own, 160),
      text_matches_model: textLooksSafeModel(own) || textLooksSafeModel(text),
      excluded_reason: excludedReason(el),
    };
  }
  const prompt = document.querySelector('#prompt-textarea');
  const form = prompt ? prompt.closest('form') : null;
  const buttons = [];
  if (form) {
    Array.from(form.querySelectorAll('button[aria-haspopup="menu"], [role="button"][aria-haspopup="menu"]')).forEach((el) => {
      if (!isVisible(el)) return;
      buttons.push(buttonShape(el));
    });
  }
  const dataTestidSelectors = [];
  buttons.forEach((button) => {
    if (!button.testid || button.excluded_reason) return;
    const selector = 'form:has(#prompt-textarea) button[data-testid=' + qAttr(button.testid) + '][aria-haspopup="menu"]';
    if (!dataTestidSelectors.some((entry) => entry.selector === selector)) {
      dataTestidSelectors.push({basis: 'data-testid', testid: button.testid, selector, count: selectorCount(selector)});
    }
  });
  const attributeSelector = 'form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])';
  return {
    url_path: location.pathname.replace(/\/c\/[^/?#\s]+/g, '/c/<redacted>'),
    hydrated_markers: {
      ready_root_present: document.querySelectorAll('main:has(#prompt-textarea)').length,
      composer_present: document.querySelectorAll('#prompt-textarea').length,
      composer_form_present: form ? 1 : 0,
    },
    composer_menu_buttons: buttons,
    stable_selector_candidates: [
      ...dataTestidSelectors,
      {basis: 'attribute-no-testid', selector: attributeSelector, count: selectorCount(attributeSelector)},
    ],
  };
}
'''

_MODEL_CAPTURE_OPEN_MENU_JS = r'''
(args) => {
  args = args || {};
  const triggerSelector = args.trigger_selector;
  const optionSelector = args.option_selector || '[data-radix-popper-content-wrapper] [role="menuitemradio"]';
  const disabledSelector = args.disabled_selector || '[data-radix-popper-content-wrapper] [role="menuitemradio"][aria-disabled="true"], [data-radix-popper-content-wrapper] [role="menuitemradio"][data-disabled="true"], [data-radix-popper-content-wrapper] [role="menuitemradio"][disabled]';

  function isAccount(el) {
    const t = (el.getAttribute('data-testid') || '').toLowerCase();
    const a = (el.getAttribute('aria-label') || '').toLowerCase();
    return t.includes('account') || t.includes('profile') || a.includes('profile menu')
        || a.includes('open profile') || a.includes('account');
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
  const ACCOUNT_OR_PLAN_RE = /\b(account|profile|email|avatar|personal|billing|subscription|plan)\b|upgrade|user[-_ ]?menu|display[-_ ]?name|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
  function compact(value) { return String(value || '').replace(/\s+/g, ' ').trim(); }
  function rawVisibleText(el) { return String(el.innerText || el.textContent || '').trim(); }
  function isVisible(el) {
    if (!el || !(el instanceof Element)) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.right >= 0
        && rect.top <= (window.innerHeight || document.documentElement.clientHeight)
        && rect.left <= (window.innerWidth || document.documentElement.clientWidth);
  }
  function hasAccountOrPlanPersonal(el) {
    let cur = el;
    let hops = 0;
    while (cur && cur.nodeType === 1 && hops < 7) {
      if (isAccount(cur)) return true;
      if (ACCOUNT_OR_PLAN_RE.test(attrBlob(cur))) return true;
      cur = cur.parentElement;
      hops += 1;
    }
    return ACCOUNT_OR_PLAN_RE.test(compact(rawVisibleText(el)));
  }
  function isDisabled(el) {
    return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.getAttribute('data-disabled') === 'true'
        || !!el.closest('[aria-disabled=true], [data-disabled=true], [disabled]');
  }
  function selectorCount(selector) {
    try { return document.querySelectorAll(selector).length; } catch (e) { return -1; }
  }
  function visibleCount(selector) {
    try { return Array.from(document.querySelectorAll(selector)).filter((el) => isVisible(el) && !hasAccountOrPlanPersonal(el)).length; }
    catch (e) { return -1; }
  }
  function rectShape(el) {
    const r = el.getBoundingClientRect();
    return {top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width), height: Math.round(r.height)};
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
  function relativePath(parent, node) {
    if (node === parent) return ':scope';
    const parts = [];
    let cur = node;
    while (cur && cur.nodeType === 1 && cur !== parent) {
      const tag = (cur.tagName || '').toLowerCase();
      let nth = 1;
      let prev = cur.previousElementSibling;
      while (prev) {
        if ((prev.tagName || '').toLowerCase() === tag) nth += 1;
        prev = prev.previousElementSibling;
      }
      parts.unshift(tag + ':nth-of-type(' + nth + ')');
      cur = cur.parentElement;
    }
    if (cur !== parent) return null;
    return ':scope > ' + parts.join(' > ');
  }
  function textLines(raw) {
    return String(raw || '').split(/\n+/).map((line) => compact(line)).filter(Boolean);
  }
  function labelSubselector(el, firstLine) {
    if (!firstLine) return null;
    const matches = Array.from(el.querySelectorAll('div, span, p')).filter((node) => {
      if (!isVisible(node) || hasAccountOrPlanPersonal(node)) return false;
      return compact(rawVisibleText(node)) === firstLine;
    });
    if (!matches.length) return null;
    matches.sort((a, b) => {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      const areaA = ar.width * ar.height;
      const areaB = br.width * br.height;
      return areaA - areaB;
    });
    return relativePath(el, matches[0]);
  }
  function captureItem(el, index, role) {
    const raw = rawVisibleText(el);
    const lines = textLines(raw);
    const firstLine = lines[0] || '';
    return {
      index,
      selector: '[data-radix-popper-content-wrapper] [role="' + role + '"] >> nth=' + index,
      structural_selector: structuralPath(el),
      tag: (el.tagName || '').toLowerCase(),
      role: el.getAttribute('role'),
      innerText: raw,
      innerText_strip: raw.trim(),
      first_line: firstLine,
      line_count: lines.length,
      value_attr: el.getAttribute('value'),
      aria_checked: el.getAttribute('aria-checked'),
      data_state: el.getAttribute('data-state'),
      aria_disabled: el.getAttribute('aria-disabled'),
      data_disabled: el.getAttribute('data-disabled'),
      disabled_attr: el.hasAttribute('disabled'),
      disabled: isDisabled(el),
      aria_haspopup: el.getAttribute('aria-haspopup'),
      aria_expanded: el.getAttribute('aria-expanded'),
      has_submenu: role === 'menuitem' && (el.getAttribute('aria-haspopup') === 'menu' || ['open', 'closed'].includes(el.getAttribute('data-state'))),
      label_subselector_within_option: labelSubselector(el, firstLine),
      rect: rectShape(el),
    };
  }

  const roots = Array.from(document.querySelectorAll('[data-radix-popper-content-wrapper]')).filter((root) => {
    if (!isVisible(root) || hasAccountOrPlanPersonal(root)) return false;
    return Array.from(root.querySelectorAll('[role="menuitemradio"]')).some((el) => isVisible(el) && !hasAccountOrPlanPersonal(el));
  });
  const root = roots[0] || null;
  const trigger = triggerSelector ? document.querySelector(triggerSelector) : null;
  const radioEls = root ? Array.from(root.querySelectorAll('[role="menuitemradio"]')).filter((el) => isVisible(el) && !hasAccountOrPlanPersonal(el)) : [];
  const menuitemEls = root ? Array.from(root.querySelectorAll('[role="menuitem"]')).filter((el) => isVisible(el) && !hasAccountOrPlanPersonal(el)) : [];
  return {
    url_path: location.pathname.replace(/\/c\/[^/?#\s]+/g, '/c/<redacted>'),
    trigger: trigger && !hasAccountOrPlanPersonal(trigger) ? {
      selector: triggerSelector,
      innerText: rawVisibleText(trigger),
      innerText_strip: rawVisibleText(trigger).trim(),
      aria_haspopup: trigger.getAttribute('aria-haspopup'),
      aria_expanded: trigger.getAttribute('aria-expanded'),
      data_state: trigger.getAttribute('data-state'),
      rect: rectShape(trigger),
    } : {selector: triggerSelector, innerText: '<omitted>', innerText_strip: '<omitted>'},
    root_count: roots.length,
    root_selector: root ? structuralPath(root) : null,
    model_option_selector: optionSelector,
    model_option_count: visibleCount(optionSelector),
    model_option_dom_count: selectorCount(optionSelector),
    model_option_disabled_selector: disabledSelector,
    model_option_disabled_count: visibleCount(disabledSelector),
    options: radioEls.map((el, index) => captureItem(el, index, 'menuitemradio')),
    menuitems: menuitemEls.map((el, index) => captureItem(el, index, 'menuitem')),
  };
}
'''


def _model_capture_json_arg(trigger_selector: str) -> dict[str, str]:
    return {
        'trigger_selector': trigger_selector,
        'option_selector': MODEL_CAPTURE_OPTION_SELECTOR,
        'disabled_selector': MODEL_CAPTURE_DISABLED_SELECTOR,
    }


def _escape_close_model_menu(page: Any, trigger_selector: str | None = None) -> dict[str, Any]:
    confirmation: dict[str, Any] = {'script_clicked_option': False}
    try:
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
        confirmation['model_option_count_after_escape'] = _selector_count(page, MODEL_CAPTURE_OPTION_SELECTOR)
        confirmation['portal_root_count_after_escape'] = _selector_count(page, '[data-radix-popper-content-wrapper]')
        confirmation['trigger_state_after_escape'] = _trigger_state(page, trigger_selector)
    except PlaywrightError as exc:
        confirmation['escape_error'] = exc.__class__.__name__
    return confirmation


def _model_capture_test_selector(session: BrowserSession, page: Any, selector: str, *, basis: str) -> dict[str, Any]:
    attempt: dict[str, Any] = {'selector': selector, 'basis': basis, 'count': _selector_count(page, selector)}
    if attempt['count'] != 1:
        attempt['opens_menuitemradio'] = False
        attempt['reject_reason'] = 'selector-count-not-1'
        return attempt
    if not recheck_safe(session):
        raise HumanActionStop('HUMAN-ACTION-NEEDED')
    _escape_close_model_menu(page, selector)
    attempt['trigger_state_before'] = _trigger_state(page, selector)
    try:
        page.locator(selector).first.click(timeout=5000)
        page.wait_for_timeout(900)
        if not recheck_safe(session):
            raise HumanActionStop('HUMAN-ACTION-NEEDED')
        attempt['trigger_state_after_click'] = _trigger_state(page, selector)
        attempt['option_count_after_click'] = _selector_count(page, MODEL_CAPTURE_OPTION_SELECTOR)
        attempt['disabled_count_after_click'] = _selector_count(page, MODEL_CAPTURE_DISABLED_SELECTOR)
        attempt['opens_menuitemradio'] = int(attempt.get('option_count_after_click') or 0) >= 2
        if not attempt['opens_menuitemradio']:
            attempt['reject_reason'] = 'did-not-open-menuitemradio-options'
    except PlaywrightError as exc:
        attempt['opens_menuitemradio'] = False
        attempt['open_error'] = exc.__class__.__name__
    finally:
        attempt['escape_confirmation'] = _escape_close_model_menu(page, selector)
    return attempt


def _css_attr_value(value: object) -> str:
    return json.dumps(str(value))


def _model_capture_selector_candidates(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for button in inventory.get('composer_menu_buttons') or []:
        testid = button.get('testid')
        if not testid or button.get('excluded_reason'):
            continue
        selector = 'form:has(#prompt-textarea) button[data-testid=%s][aria-haspopup="menu"]' % _css_attr_value(testid)
        if selector in seen:
            continue
        seen.add(selector)
        candidates.append({'basis': 'data-testid', 'selector': selector, 'source_button': button})
    attribute_selector = 'form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])'
    if attribute_selector not in seen:
        seen.add(attribute_selector)
        candidates.append({'basis': 'attribute-no-testid', 'selector': attribute_selector, 'source_button': None})
    if MODEL_CAPTURE_STRUCTURAL_FALLBACK not in seen:
        candidates.append({'basis': 'verified-structural-fallback-from-T1b', 'selector': MODEL_CAPTURE_STRUCTURAL_FALLBACK, 'source_button': None})
    return candidates


def _model_capture_open_and_capture(session: BrowserSession, page: Any, selector: str, *, pass_label: str) -> dict[str, Any]:
    capture: dict[str, Any] = {'pass_label': pass_label, 'selector': selector, 'selector_count': _selector_count(page, selector)}
    if capture['selector_count'] != 1:
        capture['error'] = 'selector-count-not-1'
        return capture
    if not recheck_safe(session):
        raise HumanActionStop('HUMAN-ACTION-NEEDED')
    _escape_close_model_menu(page, selector)
    capture['trigger_state_before_open'] = _trigger_state(page, selector)
    try:
        page.locator(selector).first.click(timeout=5000)
        page.wait_for_timeout(900)
        if not recheck_safe(session):
            raise HumanActionStop('HUMAN-ACTION-NEEDED')
        capture['trigger_state_after_open'] = _trigger_state(page, selector)
        capture['open_capture'] = page.evaluate(_MODEL_CAPTURE_OPEN_MENU_JS, _model_capture_json_arg(selector))
    except PlaywrightError as exc:
        capture['error'] = exc.__class__.__name__
    finally:
        capture['escape_confirmation'] = _escape_close_model_menu(page, selector)
    return capture


def _capture_options(capture: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list(((capture or {}).get('open_capture') or {}).get('options') or [])


def _capture_menuitems(capture: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list(((capture or {}).get('open_capture') or {}).get('menuitems') or [])


def _selectable_model_labels_from_capture(capture: dict[str, Any] | None) -> list[str]:
    labels: list[str] = []
    for option in _capture_options(capture):
        label = option.get('first_line') or option.get('innerText_strip')
        if not isinstance(label, str) or not label.strip() or option.get('disabled'):
            continue
        if label not in labels:
            labels.append(label)
    return labels


def _current_model_label_from_capture(capture: dict[str, Any] | None) -> str | None:
    for option in _capture_options(capture):
        label = option.get('first_line') or option.get('innerText_strip')
        if option.get('aria_checked') == 'true' and isinstance(label, str) and label.strip():
            return label
    return None


def _two_switch_labels(capture: dict[str, Any] | None) -> list[str]:
    selectable = _selectable_model_labels_from_capture(capture)
    current = _current_model_label_from_capture(capture)
    ordered: list[str] = []
    if current and current in selectable:
        ordered.append(current)
    for label in selectable:
        if label not in ordered:
            ordered.append(label)
        if len(ordered) >= 2:
            break
    return ordered


def _model_capture_matching_rule(capture: dict[str, Any] | None) -> dict[str, Any]:
    options = _capture_options(capture)
    value_attrs = [opt.get('value_attr') for opt in options]
    value_null_for_all = all(value in (None, '') for value in value_attrs)
    returns = [
        {
            'label': opt.get('first_line'),
            'value_attr': opt.get('value_attr'),
            'inner_text_strip': opt.get('innerText_strip'),
            'line_count': opt.get('line_count'),
            'label_subselector_within_option': opt.get('label_subselector_within_option'),
        }
        for opt in options
    ]
    multiline = [opt for opt in options if (opt.get('innerText_strip') or '') != (opt.get('first_line') or '')]
    if multiline:
        exact_rule = (
            'Open model_menu, query model_option, skip model_option_disabled. For each option, prefer a nonempty value attribute; '
            'otherwise compute label = first nonempty line of option.inner_text().strip() (or the recorded label_subselector text when present). '
            'Click the option whose value or first-line label exactly equals requested.'
        )
    else:
        exact_rule = (
            'Open model_menu, query model_option, skip model_option_disabled. For each option, prefer a nonempty value attribute; '
            'otherwise compare requested exactly to option.inner_text().strip(). In this capture inner_text().strip() is single-line and equals the first-line label for every top-level radio option.'
        )
    return {
        'production_rule_under_test': 'requested in {option.get_attribute("value"), option.inner_text().strip()}',
        'value_attr_null_or_empty_for_all_options': value_null_for_all,
        'observed_option_returns': returns,
        'inner_text_is_single_line_for_all_options': not multiline,
        'exact_t2_recipe': exact_rule,
    }


def _model_capture_reproducible(first_capture: dict[str, Any] | None, second_capture: dict[str, Any] | None) -> bool:
    first_labels = [opt.get('innerText_strip') for opt in _capture_options(first_capture)]
    second_labels = [opt.get('innerText_strip') for opt in _capture_options(second_capture)]
    return bool(first_labels) and first_labels == second_labels


def _write_model_capture_discovery_markdown(path: Path, payload: dict[str, Any]) -> None:
    chosen = payload.get('chosen_trigger_selector')
    chosen_count = payload.get('chosen_trigger_count')
    robustness = payload.get('chosen_trigger_robustness_note') or 'n/a'
    first_capture = payload.get('first_capture') or {}
    open_capture = first_capture.get('open_capture') or {}
    matching = payload.get('matching_rule') or {}
    options = list(open_capture.get('options') or [])
    menuitems = list(open_capture.get('menuitems') or [])
    current = payload.get('current_model_label')
    two_switch = list(payload.get('two_switch_labels') or [])
    option_lines: list[str] = []
    for opt in options:
        label = opt.get('first_line') or opt.get('innerText_strip') or 'n/a'
        flags = []
        if label == current or opt.get('aria_checked') == 'true':
            flags.append('CURRENT/checked')
        if opt.get('disabled'):
            flags.append('disabled')
        else:
            flags.append('selectable')
        option_lines.append('- %s — %s; full inner_text=%s; value=%s' % (_md_code(label), ', '.join(flags), _md_code(opt.get('innerText_strip')), _md_code(opt.get('value_attr'))))
    if not option_lines:
        option_lines = ['- n/a']
    menuitem_lines: list[str] = []
    for item in menuitems:
        menuitem_lines.append('- %s — submenu=%s, aria-haspopup=%s, data-state=%s; expansion probe: not attempted (not needed for top-level two-switch)' % (_md_code(item.get('innerText_strip')), _md_code(item.get('has_submenu')), _md_code(item.get('aria_haspopup')), _md_code(item.get('data_state'))))
    if not menuitem_lines:
        menuitem_lines = ['- none observed']
    attempts = [
        {
            'basis': attempt.get('basis'),
            'selector': attempt.get('selector'),
            'count': attempt.get('count'),
            'opens_menuitemradio': attempt.get('opens_menuitemradio'),
            'reject_reason': attempt.get('reject_reason'),
            'option_count_after_click': attempt.get('option_count_after_click'),
        }
        for attempt in payload.get('selector_attempts') or []
    ]
    lines = [
        '# M-010 model picker discovery',
        '',
        '## Verdict',
        '- Verdict: `FOUND`',
        '- Source leg: `T1c-model-capture`',
        '- Ended at: ' + _md_code(payload.get('ended_at')),
        '',
        '## Selectors',
        '- model_menu (trigger) selector: ' + _md_code(chosen),
        '- model_menu .count(): ' + _md_code(chosen_count),
        '- Robustness note: ' + robustness,
        '- model_option selector: ' + _md_code(MODEL_CAPTURE_OPTION_SELECTOR),
        '- model_option count while open: ' + _md_code(open_capture.get('model_option_count')),
        '- model_option_disabled selector: ' + _md_code(MODEL_CAPTURE_DISABLED_SELECTOR),
        '- model_option_disabled count while open: ' + _md_code(open_capture.get('model_option_disabled_count')),
        '',
        '## Matching rule for `model_settings={"model": "<label>"}`',
        matching.get('exact_t2_recipe') or 'n/a',
        '- Observed `value` attrs null/empty for all options: ' + _md_code(matching.get('value_attr_null_or_empty_for_all_options')),
        '- Observed `inner_text().strip()` single-line for all options: ' + _md_code(matching.get('inner_text_is_single_line_for_all_options')),
        '',
        '## Available model labels',
        *option_lines,
        '',
        '## Two-switch labels',
        '- Use these distinct selectable labels: ' + _md_code(' -> '.join(two_switch) if len(two_switch) >= 2 else 'n/a'),
        '',
        '## Menuitem/submenu note',
        *menuitem_lines,
        '',
        '## Audit',
        '- `audit()` rows appended to `orchestration/reports/M-010/real-audit-log.md` for T1c enumerate, selector-test, capture, Escape, and reproducibility actions.',
        '',
        '## Selector-attempt evidence',
        '```json',
        _json_evidence(attempts),
        '```',
    ]
    _write_markdown(path, '\n'.join(lines))


def leg_model_capture(_args: argparse.Namespace) -> int:
    '''T1c: capture model labels verbatim from the verified model menu only, then Escape.''' 
    report = REPORT_DIR / 'T1c-model-capture.json'
    discovery_md = REPORT_DIR / 'discovery.md'
    t0 = time.monotonic()
    payload: dict[str, Any] = {
        'stage': 'start',
        'status': 'DONE',
        'verdict': 'FOUND',
        'started_at': datetime.now().astimezone().isoformat(),
        'model_option_selector': MODEL_CAPTURE_OPTION_SELECTOR,
        'model_option_disabled_selector': MODEL_CAPTURE_DISABLED_SELECTOR,
        'leak_guard': 'Captured verbatim text only from verified model-trigger and menuitemradio/menuitem option elements inside the model menu popper; all composer-button enumeration text is model-gated/redacted.',
    }
    session: BrowserSession | None = None
    close_on_exit = True
    try:
        session = connect()
        try:
            session.open_or_create_conversation(None)
        except HUMAN_ERRORS as exc:
            close_on_exit = False
            _emit_human_action_needed(exc)
            payload['stage'] = 'open'
            payload['status'] = 'BLOCKED'
            payload['result'] = _human_label(exc)
            _write_json(report, payload)
            return 5
        if not recheck_safe(session):
            close_on_exit = False
            payload['stage'] = 'open-safety'
            payload['status'] = 'BLOCKED'
            payload['result'] = 'HUMAN-ACTION-NEEDED'
            _write_json(report, payload)
            return 5
        page = session.page
        if page is None:
            raise AskChatGPTError('Browser page is unavailable after connect')
        try:
            page.locator('#prompt-textarea').first.wait_for(timeout=10000)
        except PlaywrightError:
            pass
        audit({'leg': 'T1c-model-capture', 'action': 'open own tab conversation', 'prompt-label': 'n/a',
               'observation': 'open_or_create_conversation(None); no prompt sent', 'markers': 'attach-only', 'result': 'OK'})

        inventory = page.evaluate(_MODEL_CAPTURE_COMPOSER_BUTTONS_JS)
        payload['composer_menu_button_inventory'] = inventory
        audit({'leg': 'T1c-model-capture', 'action': 'enumerate composer menu buttons', 'prompt-label': 'n/a',
               'observation': 'composer_menu_buttons=%s' % len(inventory.get('composer_menu_buttons') or []),
               'markers': 'model-gated text only', 'result': 'OK'})

        selector_attempts: list[dict[str, Any]] = []
        chosen_selector: str | None = None
        chosen_basis: str | None = None
        for candidate in _model_capture_selector_candidates(inventory):
            attempt = _model_capture_test_selector(session, page, str(candidate['selector']), basis=str(candidate['basis']))
            if candidate.get('source_button'):
                attempt['source_button'] = candidate.get('source_button')
            selector_attempts.append(attempt)
            audit({'leg': 'T1c-model-capture', 'action': 'test trigger selector %s' % candidate['basis'],
                   'prompt-label': 'n/a',
                   'observation': 'count=%s,opens=%s,options=%s' % (attempt.get('count'), attempt.get('opens_menuitemradio'), attempt.get('option_count_after_click')),
                   'markers': 'Escape,no selection', 'result': 'FOUND' if attempt.get('opens_menuitemradio') else attempt.get('reject_reason', attempt.get('open_error', 'not-model'))})
            if attempt.get('count') == 1 and attempt.get('opens_menuitemradio'):
                chosen_selector = str(candidate['selector'])
                chosen_basis = str(candidate['basis'])
                break
        payload['selector_attempts'] = selector_attempts
        if not chosen_selector:
            payload['stage'] = 'done'
            payload['status'] = 'PARTIAL'
            payload['verdict'] = 'HONEST-FAIL-CLOSED'
            payload['fail_closed_reason'] = 'no tested trigger selector had count==1 and opened >=2 menuitemradio options'
            payload['ended_at'] = datetime.now().astimezone().isoformat()
            payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
            _write_json(report, payload)
            audit({'leg': 'T1c-model-capture', 'action': 'choose trigger selector', 'prompt-label': 'n/a',
                   'observation': payload['fail_closed_reason'], 'markers': 'no prompt sent', 'result': 'PARTIAL'})
            _emit('MODEL-CAPTURE: PARTIAL no-trigger')
            return 2

        payload['chosen_trigger_selector'] = chosen_selector
        payload['chosen_trigger_basis'] = chosen_basis
        payload['chosen_trigger_count'] = _selector_count(page, chosen_selector)
        payload['chosen_trigger_robustness_note'] = (
            'Chosen by ordered T1c selector test: data-testid candidates first, then unique composer attribute selector, then T1b structural fallback. '
            'This selector had count==1 and reproducibly opened the Radix menuitemradio model menu.'
        )
        first_capture = _model_capture_open_and_capture(session, page, chosen_selector, pass_label='first-open')
        payload['first_capture'] = first_capture
        matching_rule = _model_capture_matching_rule(first_capture)
        payload['matching_rule'] = matching_rule
        payload['available_model_labels'] = _selectable_model_labels_from_capture(first_capture)
        payload['current_model_label'] = _current_model_label_from_capture(first_capture)
        payload['two_switch_labels'] = _two_switch_labels(first_capture)
        payload['menuitem_submenu_findings'] = [
            {
                'innerText': item.get('innerText'),
                'first_line': item.get('first_line'),
                'aria_haspopup': item.get('aria_haspopup'),
                'data_state': item.get('data_state'),
                'has_submenu': item.get('has_submenu'),
                'expansion_probe': 'not_attempted; attributes are sufficient to note submenu entry and top-level two-switch does not require expanding it',
            }
            for item in _capture_menuitems(first_capture)
        ]
        audit({'leg': 'T1c-model-capture', 'action': 'capture model option labels', 'prompt-label': 'n/a',
               'observation': 'options=%s,current=%s,selectable=%s' % (len(_capture_options(first_capture)), payload.get('current_model_label'), len(payload.get('available_model_labels') or [])),
               'markers': 'Escape,no selection', 'result': 'OK'})

        second_capture = _model_capture_open_and_capture(session, page, chosen_selector, pass_label='reopen-confirm')
        payload['reopen_capture'] = second_capture
        payload['reproducible'] = {
            'selector_count': _selector_count(page, chosen_selector),
            'same_option_labels': _model_capture_reproducible(first_capture, second_capture),
            'first_option_count': len(_capture_options(first_capture)),
            'second_option_count': len(_capture_options(second_capture)),
        }
        audit({'leg': 'T1c-model-capture', 'action': 're-open selector and confirm reproducible capture', 'prompt-label': 'n/a',
               'observation': 'same_labels=%s,second_options=%s' % (payload['reproducible']['same_option_labels'], payload['reproducible']['second_option_count']),
               'markers': 'Escape,no selection', 'result': 'OK' if payload['reproducible']['same_option_labels'] else 'PARTIAL'})

        if len(payload.get('available_model_labels') or []) < 2 or not payload.get('current_model_label'):
            payload['status'] = 'PARTIAL'
            payload['partial_reason'] = 'captured menu, but fewer than two selectable labels or no checked current label was found'
        payload['stage'] = 'done'
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
        _write_json(report, payload)
        _write_model_capture_discovery_markdown(discovery_md, payload)
        audit({'leg': 'T1c-model-capture', 'action': 'write T1c report + final discovery.md', 'prompt-label': 'n/a',
               'observation': 'selector_count=%s,labels=%s,current=%s' % (payload.get('chosen_trigger_count'), len(payload.get('available_model_labels') or []), payload.get('current_model_label')),
               'markers': 'no prompt sent; no option selected', 'result': payload.get('status')})
        _emit('MODEL-CAPTURE: %s selector_count=%s option_count=%s labels=%s current=%s' % (payload.get('status'), payload.get('chosen_trigger_count'), len(_capture_options(first_capture)), len(payload.get('available_model_labels') or []), payload.get('current_model_label')))
        return 0 if payload.get('status') == 'DONE' else 2
    except SystemExit:
        raise
    except HumanActionStop as exc:
        payload['stage'] = 'human-action-needed'
        payload['status'] = 'BLOCKED'
        payload['result'] = exc.label
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
        _write_json(report, payload)
        return 5
    except Exception as exc:  # noqa: BLE001
        payload['stage'] = 'error'
        payload['status'] = 'PARTIAL'
        payload['verdict'] = 'FOUND'
        payload['error'] = '%s: %s' % (exc.__class__.__name__, redact(str(exc))[:240])
        payload['ended_at'] = datetime.now().astimezone().isoformat()
        payload['actual_minutes'] = round((time.monotonic() - t0) / 60.0, 2)
        _write_json(report, payload)
        _emit('ERROR: %s: %s' % (exc.__class__.__name__, exc))
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(json.dumps(payload, indent=2, sort_keys=True)) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M-010 attach-only real ChatGPT model-picker discovery probe")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("connectivity", help="open a fresh conversation without sending a prompt")
    c.set_defaults(func=leg_connectivity)

    u = sub.add_parser("uc2", help="real UC2 round-trip via the PRODUCTION retrieve_patch_bundle path")
    u.add_argument("--download-selector", default="", help="inject real.json download_artifact via a temp maps dir")
    u.add_argument("--completion-timeout", type=float, default=120.0)
    u.add_argument("--max-total-wait", type=float, default=300.0)
    u.add_argument("--retrieve-timeout", type=float, default=30.0)
    u.add_argument("--download-wait", type=float, default=3.0)
    u.set_defaults(func=leg_uc2)

    s = sub.add_parser("short", help="short-response completion edge via PRODUCTION ask_chatgpt()->text")
    s.add_argument("--completion-timeout", type=float, default=60.0)
    s.set_defaults(func=leg_short)

    m = sub.add_parser("model-discovery", help="read-mostly: enumerate the real model picker (open menu, dump, Escape)")
    m.set_defaults(func=leg_model_discovery)

    mo = sub.add_parser("model-open-probe", help="open plausible model-picker candidates, enumerate portals, Escape")
    mo.set_defaults(func=leg_model_open_probe)

    mc = sub.add_parser("model-capture", help="capture verified model menu labels and stable trigger selector, Escape")
    mc.set_defaults(func=leg_model_capture)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
