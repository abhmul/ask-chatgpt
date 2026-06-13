#!/usr/bin/env python3
"""M-008b real-site CDP probe toolkit.

This module is intentionally inert on import. The CLI attaches only through
BrowserSession(channel="cdp") when an operator explicitly runs a subcommand.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from playwright.sync_api import Error as PlaywrightError  # noqa: E402

from ask_chatgpt.bundle import build_bundle, generate_prompt_instructions  # noqa: E402
from ask_chatgpt.driver import BrowserSession  # noqa: E402
from ask_chatgpt.errors import (  # noqa: E402
    AskChatGPTError,
    CDPUnreachableError,
    ChallengePresentError,
    LoginRequiredError,
    ProfileLockedError,
    RateLimitedError,
    ResponseTruncatedError,
)

try:
    from tests.test_continuity_mock import (  # noqa: E402
        RECALL_PROMPT,
        _assert_recall_prompt_does_not_leak_nonce,
        _new_nonce,
        _plant_prompt,
    )
except ModuleNotFoundError as exc:
    _continuity_mock_path = ROOT / "tests" / "test_continuity_mock.py"
    if exc.name not in {"tests", "tests.test_continuity_mock"} or not _continuity_mock_path.exists():
        raise
    _spec = importlib.util.spec_from_file_location("_m008b_continuity_mock", _continuity_mock_path)
    if _spec is None or _spec.loader is None:
        raise
    _continuity_mock = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _continuity_mock
    _spec.loader.exec_module(_continuity_mock)
    RECALL_PROMPT = _continuity_mock.RECALL_PROMPT
    _assert_recall_prompt_does_not_leak_nonce = _continuity_mock._assert_recall_prompt_does_not_leak_nonce
    _new_nonce = _continuity_mock._new_nonce
    _plant_prompt = _continuity_mock._plant_prompt

BASE_URL = "https://chatgpt.com"
TEMP_URL = "https://chatgpt.com/?temporary-chat=true"
REPORT_DIR = ROOT / "orchestration" / "reports" / "M-008b"
AUDIT_LOG = REPORT_DIR / "real-audit-log.md"
T2_OBSERVATIONS = REPORT_DIR / "T2-completion-observations.json"
T5_TEMP_RECALL = REPORT_DIR / "T5-temp-recall.txt"
T5_TEMP_CONTROL = REPORT_DIR / "T5-temp-control.txt"
T5_TEMP_CONTINUITY = REPORT_DIR / "T5-temp-continuity.json"
T4_DOWNLOAD_DISCOVERY = REPORT_DIR / "T4-download-discovery.json"

DOWNLOAD_DISCOVERY_USER_TASK = "In example.txt, change favorite_color from red to blue."
DOWNLOAD_DISCOVERY_EXAMPLE = 'favorite_color = "red"\n'

REDACT_C_RE = re.compile(r"/c/[^/?#\s]+")
URLISH_RE = re.compile(r"\b(?:https?|blob|sandbox):[^\s<>)\"']+", re.IGNORECASE)
SECRET_PARAM_RE = re.compile(
    r"\b(access_token|token|sig|signature|x-amz-signature|key|jwt|session|cookie)=[^&\s)\"']+",
    re.IGNORECASE,
)
BASE64_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9+/=])(?:[A-Za-z0-9+/]{160,}={0,2})(?![A-Za-z0-9+/=])")
BASE64_LINE_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
FENCED_BLOCK_RE = re.compile(r"```(?:[^\n`]*)\n(.*?)```", re.DOTALL)
AUDIT_DATA_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")
AUDIT_HEADER = """# M-008b — Real-site per-message audit log (transparency, not rationing)

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
"""

PROMPTS: tuple[tuple[str, str], ...] = (
    ("short-ping", "Reply with exactly the word PING and nothing else."),
    ("short-two", "In one short sentence, say hello."),
    ("medium-40", "Output the numbers 1 through 40, one per line, then a final line with exactly DONE."),
    ("long-120", "Output the numbers 1 through 120, one per line, then a final line with exactly DONE."),
)

HUMAN_ERRORS = (ChallengePresentError, LoginRequiredError, ProfileLockedError)
POLL_INTERVAL_S = 0.25
POLL_CAP_S = 90.0
STABLE_COMPLETION_S = 2.0
HUMAN_PACE_S = 4.0

_audit_next_number: int | None = None


class HumanActionStop(RuntimeError):
    """Raised internally when a read-only safety recheck says the operator must intervene."""

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.label = label


def redact(value: object) -> str:
    """Redact ChatGPT conversation URL segments from any string-like value."""

    return REDACT_C_RE.sub("/c/<redacted>", str(value))


def _redact_jsonable(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {redact(key): _redact_jsonable(item) for key, item in value.items()}
    return value


def _emit(message: str) -> None:
    print(_redact_urlish_text(message), flush=True)


def _human_label(exc: BaseException) -> str:
    if isinstance(exc, ChallengePresentError):
        return "CHALLENGE_PRESENT"
    return exc.__class__.__name__


def _emit_human_action_needed(exc_or_label: BaseException | str) -> None:
    label = exc_or_label if isinstance(exc_or_label, str) else _human_label(exc_or_label)
    _emit(f"HUMAN-ACTION-NEEDED: {label}")


def _md_cell(value: object) -> str:
    text = _redact_urlish_text("n/a" if value is None else value)
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
    """Append one redacted Markdown table row to the M-008b real audit log."""

    global _audit_next_number
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not AUDIT_LOG.exists():
        AUDIT_LOG.write_text(AUDIT_HEADER, encoding="utf-8")
    if _audit_next_number is None:
        _audit_next_number = _initial_audit_number()

    number = _audit_next_number
    _audit_next_number += 1
    timestamp = datetime.now().astimezone().isoformat()
    prompt_label = row.get("prompt-label", row.get("prompt_label", "n/a"))
    cells = [
        number,
        timestamp,
        row.get("leg", "n/a"),
        row.get("action", "n/a"),
        prompt_label,
        row.get("observation", "n/a"),
        row.get("markers", "n/a"),
        row.get("result", "n/a"),
    ]
    line = "| " + " | ".join(_md_cell(cell) for cell in cells) + " |\n"
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)


def connect() -> BrowserSession:
    """Attach to the operator-owned browser over CDP and fail closed on preconditions."""

    session = BrowserSession(channel="cdp", base_url=BASE_URL)
    try:
        return session.start()
    except CDPUnreachableError:
        _emit("CDP_UNREACHABLE")
        raise SystemExit(3) from None
    except (LoginRequiredError, ProfileLockedError) as exc:
        _emit_human_action_needed(exc)
        raise SystemExit(4) from None
    except ChallengePresentError:
        _emit_human_action_needed("CHALLENGE_PRESENT")
        raise SystemExit(5) from None


def _check_safe_or_raise(session: BrowserSession) -> None:
    try:
        session._raise_challenge_present_if_detected()
        session._raise_open_failures()
        if session.page is None:
            raise AskChatGPTError("browser page is unavailable during safety recheck")
        session._raise_login_required_for_auth_redirect(session.page.url)
    except Exception as exc:  # noqa: BLE001 - any safety recheck failure must stop sending.
        raise HumanActionStop(_human_label(exc)) from exc


def recheck_safe(session: BrowserSession) -> bool:
    """Read-only challenge/login/logout check; never clicks through or fixes the UI."""

    try:
        _check_safe_or_raise(session)
    except HumanActionStop as exc:
        _emit_human_action_needed(exc.label)
        return False
    return True


def _redacted_path_shape(url: str) -> str:
    path = urlparse(str(url)).path or "/"
    return redact(path)


def _first_path_segment(path: str) -> str:
    clean = str(path or "").split("?", 1)[0].split("#", 1)[0]
    for segment in clean.split("/"):
        if segment:
            return segment[:80]
    return ""


def _href_public_shape(value: object) -> str | None:
    text = redact(value).strip()
    if not text:
        return None
    parsed = urlparse(text)
    scheme = parsed.scheme.lower()
    if not scheme:
        if text.startswith("/"):
            first = _first_path_segment(text)
            return f"relative:/{first}" if first else "relative:/"
        return None
    if scheme == "blob":
        return "blob:"
    if scheme == "sandbox":
        first = _first_path_segment(parsed.path)
        return f"sandbox:/{first}" if first else "sandbox:"
    first = _first_path_segment(parsed.path)
    if scheme in {"http", "https"}:
        return f"{scheme}:/{first}" if first else f"{scheme}:/"
    return f"{scheme}:/{first}" if first else f"{scheme}:"


def _redact_urlish_text(value: object, *, limit: int | None = None) -> str:
    text = redact(value)
    text = URLISH_RE.sub(lambda match: _href_public_shape(match.group(0)) or "<url>", text)
    text = SECRET_PARAM_RE.sub(lambda match: match.group(0).split("=", 1)[0] + "=<redacted>", text)
    if limit is not None and len(text) > limit:
        return text[:limit]
    return text


_DOWNLOAD_DISCOVERY_EVALUATE_JS = r"""
(arg) => {
  const assistantSelector = arg && arg.assistantSelector;
  const found = new Map();

  function firstPathSegment(pathname) {
    const pieces = String(pathname || '').split(/[?#]/, 1)[0].split('/').filter(Boolean);
    return pieces.length ? pieces[0].slice(0, 80) : '';
  }

  function hrefShape(raw) {
    if (!raw) return null;
    try {
      const url = new URL(String(raw), window.location.href);
      const scheme = url.protocol.replace(/:$/, '').toLowerCase();
      if (!scheme) return null;
      if (scheme === 'blob') return 'blob:';
      if (scheme === 'sandbox') {
        const first = firstPathSegment(url.pathname);
        return first ? `sandbox:/${first}` : 'sandbox:';
      }
      const first = firstPathSegment(url.pathname);
      if (scheme === 'http' || scheme === 'https') return first ? `${scheme}:/${first}` : `${scheme}:/`;
      return first ? `${scheme}:/${first}` : `${scheme}:`;
    } catch (_error) {
      const text = String(raw);
      if (text.startsWith('/')) {
        const first = firstPathSegment(text);
        return first ? `relative:/${first}` : 'relative:/';
      }
      return null;
    }
  }

  function safeText(value) {
    let text = String(value || '').replace(/\s+/g, ' ').trim();
    text = text.replace(/\b(?:https?|blob|sandbox):[^\s<>)"']+/gi, (match) => hrefShape(match) || '<url>');
    text = text.replace(/\b(access_token|token|sig|signature|x-amz-signature|key|jwt|session|cookie)=[^&\s)"']+/gi, (match) => `${match.split('=')[0]}=<redacted>`);
    return text.length > 80 ? `${text.slice(0, 77)}...` : text;
  }

  function selectorGuess(element) {
    const tag = String(element.tagName || '').toLowerCase() || 'element';
    const dataTestId = element.getAttribute('data-testid');
    if (dataTestId) return `[data-testid=${JSON.stringify(safeText(dataTestId))}]`;
    const aria = element.getAttribute('aria-label') || element.getAttribute('title');
    if (aria) return `${tag}[aria-label=${JSON.stringify(safeText(aria))}]`;
    const role = element.getAttribute('role');
    const text = safeText(element.innerText || element.textContent || '');
    if (role && text) return `[role=${JSON.stringify(safeText(role))}]:has-text(${JSON.stringify(text)})`;
    if (role) return `[role=${JSON.stringify(safeText(role))}]`;
    if (/download/i.test(text)) return `${tag}:has-text(${JSON.stringify(text)})`;
    const className = typeof element.className === 'string' ? element.className : '';
    if (/download/i.test(className)) return `${tag}[class*="download" i]`;
    return tag;
  }

  function candidateHref(element) {
    if (element instanceof HTMLAnchorElement && element.href) return element.href;
    const anchor = element.querySelector && element.querySelector('a[href]');
    return anchor ? anchor.href : null;
  }

  function add(element, scope, reason) {
    if (!element || !(element instanceof Element)) return;
    if (element.matches('input[type="file"]')) return;
    let meta = found.get(element);
    if (!meta) {
      meta = {scopes: new Set(), reasons: new Set()};
      found.set(element, meta);
    }
    meta.scopes.add(scope);
    meta.reasons.add(reason);
  }

  function query(root, scope, selector, reason) {
    try {
      root.querySelectorAll(selector).forEach((element) => add(element, scope, reason));
    } catch (_error) {
      // Ignore selector support drift; discovery is best-effort and read-only.
    }
  }

  const specs = [
    ['a[download]', 'a_download'],
    ['a[href^="blob:"]', 'blob_href'],
    ['a[href^="sandbox:"]', 'sandbox_href'],
    ['a[href*="/backend-api/"][href*="download"]', 'backend_api_download_href'],
    ['a[href*="files"]', 'files_href'],
    ['[data-testid*="file" i]', 'file_data_testid'],
    ['[class*="download" i]', 'download_class'],
  ];

  let latestAssistant = null;
  if (assistantSelector) {
    try {
      const turns = document.querySelectorAll(assistantSelector);
      latestAssistant = turns.length ? turns[turns.length - 1] : null;
    } catch (_error) {
      latestAssistant = null;
    }
  }

  for (const [selector, reason] of specs) {
    query(document, 'page', selector, reason);
    if (latestAssistant) query(latestAssistant, 'latest_assistant', selector, reason);
  }

  function queryDownloadText(root, scope) {
    try {
      root.querySelectorAll('a, button, [role="button"], [role="link"]').forEach((element) => {
        const text = safeText(element.innerText || element.textContent || element.getAttribute('aria-label') || '');
        if (/download/i.test(text)) add(element, scope, 'download_text');
      });
    } catch (_error) {
      // Ignore transient DOM churn.
    }
  }
  queryDownloadText(document, 'page');
  if (latestAssistant) queryDownloadText(latestAssistant, 'latest_assistant');

  return Array.from(found.entries()).slice(0, 100).map(([element, meta]) => ({
    tagName: String(element.tagName || '').toUpperCase(),
    selector_guess: selectorGuess(element),
    href_shape: hrefShape(candidateHref(element)),
    scope: Array.from(meta.scopes).sort().join('+'),
    reasons: Array.from(meta.reasons).sort(),
  }));
}
"""


def _round_s(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def _format_s(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _marker_selectors(session: BrowserSession) -> tuple[str, str, str, str]:
    return (
        session.selectors.selector("streaming_marker"),
        session.selectors.selector("completion_marker"),
        session.selectors.selector("assistant_message"),
        session.selectors.selector("message_body"),
    )


def _latest_assistant_text_len(session: BrowserSession, assistant_locator: Any | None = None) -> int:
    try:
        if assistant_locator is not None:
            return len(session._latest_assistant_body_text(assistant_locator))
        page = session.page
        if page is None:
            return 0
        assistant_selector = session.selectors.selector("assistant_message")
        body_selector = session.selectors.selector("message_body")
        assistants = page.locator(assistant_selector)
        assistant_count = assistants.count()
        if assistant_count < 1:
            return 0
        latest = assistants.nth(assistant_count - 1)
        bodies = latest.locator(body_selector)
        if bodies.count() > 0:
            return len(bodies.last.inner_text(timeout=1000))
        return len(latest.inner_text(timeout=1000))
    except (AskChatGPTError, PlaywrightError):
        return 0


def _latest_assistant_text(session: BrowserSession) -> str:
    """Return the latest assistant turn's full Markdown body text."""

    try:
        latest = session._latest_assistant_turn()
        if latest is None:
            return ""
        body_selector = session.selectors.selector("message_body")
        bodies = latest.locator(body_selector)
        if bodies.count() > 0:
            return bodies.last.inner_text(timeout=1000)
        return session._latest_assistant_body_text(latest)
    except (AskChatGPTError, PlaywrightError):
        return ""


def _sample_markers(session: BrowserSession, started_at: float) -> dict[str, object]:
    page = session.page
    if page is None:
        raise AskChatGPTError("browser page is unavailable during marker sampling")
    stop_selector, copy_selector, assistant_selector, body_selector = _marker_selectors(session)

    stop_count = page.locator(stop_selector).count()
    copy_locator = page.locator(copy_selector)
    copy_count = copy_locator.count()
    copy_visible = False
    if copy_count > 0:
        try:
            copy_visible = bool(copy_locator.nth(copy_count - 1).is_visible())
        except PlaywrightError:
            copy_visible = False

    text_len = 0
    try:
        assistants = page.locator(assistant_selector)
        assistant_count = assistants.count()
        if assistant_count > 0:
            latest = assistants.nth(assistant_count - 1)
            bodies = latest.locator(body_selector)
            if bodies.count() > 0:
                text_len = len(bodies.last.inner_text(timeout=250))
            else:
                text_len = len(latest.inner_text(timeout=250))
    except PlaywrightError:
        text_len = 0

    return {
        "t": _round_s(time.monotonic() - started_at),
        "stop_count": stop_count,
        "copy_count": copy_count,
        "copy_visible": copy_visible,
        "text_len": text_len,
    }


def _baseline_marker_counts(session: BrowserSession) -> dict[str, int]:
    page = session.page
    if page is None:
        raise AskChatGPTError("browser page is unavailable during marker baseline")
    stop_selector, copy_selector, _, _ = _marker_selectors(session)
    return {
        "stop_count": page.locator(stop_selector).count(),
        "copy_count": page.locator(copy_selector).count(),
        "text_len": _latest_assistant_text_len(session),
    }


def _open_temp_chat(session: BrowserSession) -> None:
    page = session.page
    if page is None:
        raise AskChatGPTError("browser page is unavailable while opening temporary chat")
    page.goto(TEMP_URL, wait_until="load", timeout=60000)
    page.wait_for_selector('main:has(#prompt-textarea)', timeout=30000, state="attached")


def _send_prompt_or_human_stop(session: BrowserSession, prompt: str) -> None:
    try:
        session.send_prompt(prompt)
    except HUMAN_ERRORS as exc:
        raise HumanActionStop(_human_label(exc)) from exc


def _wait_for_completion_or_human_stop(session: BrowserSession) -> None:
    try:
        session.wait_for_completion(timeout_s=120, max_total_wait_s=300)
    except HUMAN_ERRORS as exc:
        raise HumanActionStop(_human_label(exc)) from exc


def capture_marker_timeline(session: BrowserSession, *, baseline: dict[str, int]) -> dict[str, object]:
    """Poll marker counts and derive completion-affordance timing without hovering or clicking."""

    started_at = time.monotonic()
    samples: list[dict[str, object]] = []
    stop_gone_at: float | None = None
    copy_present_at: float | None = None
    copy_count_increased_at: float | None = None
    stable_since: float | None = None
    copy_stable_2s = False
    copy_visible_without_hover = False
    baseline_copy_count = baseline.get("copy_count", 0)

    while True:
        _check_safe_or_raise(session)
        sample = _sample_markers(session, started_at)
        samples.append(sample)
        t = float(sample["t"])
        stop_count = int(sample["stop_count"])
        copy_count = int(sample["copy_count"])
        copy_visible_without_hover = copy_visible_without_hover or bool(sample["copy_visible"])

        if stop_count == 0 and stop_gone_at is None:
            stop_gone_at = t
        if copy_count >= 1 and copy_present_at is None:
            copy_present_at = t
        if copy_count > baseline_copy_count and copy_count_increased_at is None:
            copy_count_increased_at = t

        stable_condition = stop_count == 0 and copy_count >= 1
        if stable_condition:
            if stable_since is None:
                stable_since = t
            if t - stable_since >= STABLE_COMPLETION_S:
                copy_stable_2s = True
                break
        else:
            stable_since = None

        if time.monotonic() - started_at >= POLL_CAP_S:
            break
        time.sleep(POLL_INTERVAL_S)

    final_sample = samples[-1] if samples else {"stop_count": 0, "copy_count": 0, "text_len": 0}
    gap = None
    if stop_gone_at is not None and copy_present_at is not None:
        gap = max(0.0, copy_present_at - stop_gone_at)

    return {
        "samples": samples,
        "baseline_stop_count": baseline.get("stop_count", 0),
        "baseline_copy_count": baseline_copy_count,
        "baseline_text_len": baseline.get("text_len", 0),
        "copy_appeared": copy_present_at is not None,
        "copy_count_increased": copy_count_increased_at is not None,
        "stop_gone_at": _round_s(stop_gone_at),
        "copy_present_at": _round_s(copy_present_at),
        "stop_gone_at_s": _round_s(stop_gone_at),
        "copy_present_at_s": _round_s(copy_present_at),
        "copy_count_increased_at_s": _round_s(copy_count_increased_at),
        "gap_stop_gone_to_copy_present_s": _round_s(gap),
        "copy_stable_2s": copy_stable_2s,
        "copy_visible_without_hover": copy_visible_without_hover,
        "final_stop_count": int(final_sample["stop_count"]),
        "final_copy_count": int(final_sample["copy_count"]),
        "final_text_len": int(final_sample["text_len"]),
        "poll_elapsed_s": _round_s(time.monotonic() - started_at),
    }


def _summarize_turns(turns: list[dict[str, object]], *, attempted: int) -> dict[str, object]:
    copy_count = sum(1 for turn in turns if bool(turn.get("copy_appeared")))
    returned_count = sum(1 for turn in turns if turn.get("wait_outcome") == "returned")
    gaps = [turn.get("gap_stop_gone_to_copy_present_s") for turn in turns]
    numeric_gaps = [float(gap) for gap in gaps if isinstance(gap, (int, float))]
    max_gap = max(numeric_gaps) if numeric_gaps else None
    return {
        "turns": len(turns),
        "attempted": attempted,
        "planned": len(PROMPTS),
        "all_copy_appeared": bool(turns) and copy_count == len(turns),
        "all_wait_returned": bool(turns) and returned_count == len(turns),
        "copy_appeared_count": copy_count,
        "wait_returned_count": returned_count,
        "max_gap_stop_to_copy_s": _round_s(max_gap),
        "any_false_truncation": any(
            turn.get("wait_outcome") == "ResponseTruncatedError" and bool(turn.get("copy_appeared")) for turn in turns
        ),
    }


def _write_t2_observations(turns: list[dict[str, object]], *, attempted: int, stopped_early: str | None = None) -> dict[str, object]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = _summarize_turns(turns, attempted=attempted)
    payload: dict[str, object] = {"summary": summary, "turns": turns}
    if stopped_early:
        payload["stopped_early"] = stopped_early
    text = json.dumps(_redact_jsonable(payload), indent=2, sort_keys=True)
    T2_OBSERVATIONS.write_text(redact(text) + "\n", encoding="utf-8")
    return summary


def run_connectivity(_args: argparse.Namespace) -> int:
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
        page_url = session.page.url if session.page is not None else ""
        audit(
            {
                "leg": "T0-connectivity",
                "action": "open new conversation (no send)",
                "prompt-label": "n/a",
                "observation": "ready_root+composer present",
                "markers": "n/a",
                "result": "OK",
            }
        )
        _emit(f"CONNECTIVITY: OK {_redacted_path_shape(page_url)}")
        return 0
    except SystemExit:
        raise
    except HumanActionStop as exc:
        close_on_exit = False
        _emit_human_action_needed(exc.label)
        return 5
    except Exception as exc:  # noqa: BLE001 - top-level CLI must fail closed and surface safe detail.
        _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def _wait_for_real_completion(session: BrowserSession) -> tuple[str, int, bool]:
    """Call the driver completion logic and return outcome, body length, and whether it is an unexpected error."""

    try:
        completed = session.wait_for_completion(timeout_s=120, max_total_wait_s=300)
    except ResponseTruncatedError:
        return "ResponseTruncatedError", _latest_assistant_text_len(session), False
    except HUMAN_ERRORS as exc:
        raise HumanActionStop(_human_label(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - the contract records non-truncation wait errors by name.
        return exc.__class__.__name__, _latest_assistant_text_len(session), True
    return "returned", _latest_assistant_text_len(session, completed), False


def run_completion_reliability(_args: argparse.Namespace) -> int:
    session: BrowserSession | None = None
    close_on_exit = True
    turns: list[dict[str, object]] = []
    attempted = 0
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

        exit_code = 0
        stopped_early: str | None = None
        for label, prompt_text in PROMPTS:
            if not recheck_safe(session):
                close_on_exit = False
                stopped_early = "safety-recheck"
                exit_code = 5
                break

            baseline = _baseline_marker_counts(session)
            attempted += 1
            try:
                session.send_prompt(prompt_text)
            except HUMAN_ERRORS as exc:
                close_on_exit = False
                _emit_human_action_needed(exc)
                stopped_early = _human_label(exc)
                exit_code = 5
                break
            except RateLimitedError as exc:
                audit(
                    {
                        "leg": "T2",
                        "action": "send",
                        "prompt-label": label,
                        "observation": "rate-limit marker visible after send attempt",
                        "markers": f"stop:{baseline['stop_count']}/copy:{baseline['copy_count']}",
                        "result": exc.__class__.__name__,
                    }
                )
                _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
                stopped_early = exc.__class__.__name__
                exit_code = 1
                break
            except Exception as exc:  # noqa: BLE001 - do not keep sending after an unknown send failure.
                audit(
                    {
                        "leg": "T2",
                        "action": "send",
                        "prompt-label": label,
                        "observation": "send failed; stopping before any further prompts",
                        "markers": f"stop:{baseline['stop_count']}/copy:{baseline['copy_count']}",
                        "result": exc.__class__.__name__,
                    }
                )
                _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
                stopped_early = exc.__class__.__name__
                exit_code = 1
                break

            audit(
                {
                    "leg": "T2",
                    "action": "send",
                    "prompt-label": label,
                    "observation": f"sent; prompt_chars={len(prompt_text)}",
                    "markers": f"stop:{baseline['stop_count']}/copy:{baseline['copy_count']}",
                    "result": "OK",
                }
            )

            timeline = capture_marker_timeline(session, baseline=baseline)
            if not recheck_safe(session):
                close_on_exit = False
                stopped_early = "safety-recheck-after-timeline"
                exit_code = 5
                break

            wait_outcome, body_len, unexpected_wait_error = _wait_for_real_completion(session)
            turn: dict[str, object] = {
                "label": label,
                **timeline,
                "wait_outcome": wait_outcome,
                "body_len": body_len,
            }
            turns.append(turn)

            audit(
                {
                    "leg": "T2",
                    "action": "observe-completion",
                    "prompt-label": label,
                    "observation": (
                        f"copy_appeared={turn['copy_appeared']},"
                        f"gap={_format_s(turn['gap_stop_gone_to_copy_present_s'])}s,"
                        f"stable={turn['copy_stable_2s']},"
                        f"visible_no_hover={turn['copy_visible_without_hover']}"
                    ),
                    "markers": f"stop:{turn['final_stop_count']}/copy:{turn['final_copy_count']}",
                    "result": wait_outcome,
                }
            )

            time.sleep(HUMAN_PACE_S)
            if unexpected_wait_error:
                stopped_early = wait_outcome
                exit_code = 1
                break

        if session is not None and exit_code == 0:
            session.refresh_active_conversation_ref()
        summary = _write_t2_observations(turns, attempted=attempted, stopped_early=stopped_early)
        if exit_code == 0:
            _emit(
                "T2-SUMMARY: "
                f"copy_appeared={summary['copy_appeared_count']}/{len(PROMPTS)} "
                f"wait_returned={summary['wait_returned_count']}/{len(PROMPTS)} "
                f"max_gap={_format_s(summary['max_gap_stop_to_copy_s'])}s"
            )
        return exit_code
    except SystemExit:
        raise
    except HumanActionStop as exc:
        close_on_exit = False
        _emit_human_action_needed(exc.label)
        _write_t2_observations(turns, attempted=attempted, stopped_early=exc.label)
        return 5
    except Exception as exc:  # noqa: BLE001 - top-level CLI must fail closed and surface safe detail.
        _write_t2_observations(turns, attempted=attempted, stopped_early=exc.__class__.__name__)
        _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def _write_redacted_text(path: Path, text: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(text).rstrip("\n") + "\n", encoding="utf-8")


def _build_download_discovery_bundle(temp_root: Path) -> tuple[Path, str, int, str]:
    project_root = temp_root / "tiny-project"
    project_root.mkdir(parents=True, exist_ok=False)
    (project_root / "example.txt").write_text(DOWNLOAD_DISCOVERY_EXAMPLE, encoding="utf-8")
    bundle = build_bundle(files=("example.txt",), root=project_root)
    zip_path = temp_root / bundle.filename
    zip_path.write_bytes(bundle.content)
    prompt = generate_prompt_instructions(DOWNLOAD_DISCOVERY_USER_TASK, bundle_filename=bundle.filename)
    return zip_path, bundle.filename, bundle.byte_count, prompt


def _upload_bundle_zip_path(session: BrowserSession, zip_path: Path) -> str:
    page = session.page
    if page is None:
        raise AskChatGPTError("browser page is unavailable during upload")
    selector = session.selectors.selector("upload_input")
    try:
        upload_input = page.locator(selector)
        if upload_input.count() < 1:
            raise AskChatGPTError(f"upload input absent; upload basename={zip_path.name}")
        upload_input.first.set_input_files(str(zip_path), timeout=90000)
    except AskChatGPTError:
        raise
    except PlaywrightError as exc:
        raise AskChatGPTError(f"upload input rejected file; upload basename={zip_path.name}") from exc
    return selector


def _sanitize_download_candidates(raw_candidates: Any) -> list[dict[str, object]]:
    if not isinstance(raw_candidates, list):
        return []
    sanitized: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in raw_candidates[:100]:
        if not isinstance(item, dict):
            continue
        raw_reasons = item.get("reasons", [])
        if isinstance(raw_reasons, list):
            reasons = sorted({_redact_urlish_text(reason, limit=80) for reason in raw_reasons if reason is not None})
        elif raw_reasons is None:
            reasons = []
        else:
            reasons = [_redact_urlish_text(raw_reasons, limit=80)]
        candidate: dict[str, object] = {
            "tagName": _redact_urlish_text(item.get("tagName", ""), limit=40),
            "selector_guess": _redact_urlish_text(item.get("selector_guess", ""), limit=180),
            "href_shape": _href_public_shape(item.get("href_shape")),
            "scope": _redact_urlish_text(item.get("scope", ""), limit=80),
            "reasons": reasons[:8],
        }
        key = json.dumps(candidate, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        sanitized.append(candidate)
    return sanitized


def _inspect_download_affordances(session: BrowserSession) -> list[dict[str, object]]:
    page = session.page
    if page is None:
        raise AskChatGPTError("browser page is unavailable during download discovery")
    assistant_selector = session.selectors.selector("assistant_message")
    raw_candidates = page.evaluate(_DOWNLOAD_DISCOVERY_EVALUATE_JS, {"assistantSelector": assistant_selector})
    return _sanitize_download_candidates(raw_candidates)


def _candidate_indicates_download_affordance(candidate: dict[str, object]) -> bool:
    raw_reasons = candidate.get("reasons", [])
    reasons = set(raw_reasons if isinstance(raw_reasons, list) else [])
    href_shape = candidate.get("href_shape")
    if isinstance(href_shape, str) and href_shape:
        return True
    if reasons.intersection({"a_download", "blob_href", "sandbox_href", "backend_api_download_href", "files_href"}):
        return True
    selector_guess = str(candidate.get("selector_guess", "")).lower()
    if "download_text" in reasons or "download_class" in reasons or "download" in selector_guess:
        return True
    scope = str(candidate.get("scope", ""))
    return "latest_assistant" in scope and "file_data_testid" in reasons


def _has_base64_lines(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matching = [line for line in lines if BASE64_LINE_RE.fullmatch(line)]
    return len(matching) >= 2 and sum(len(line) for line in matching) >= 160


def _looks_like_base64_text(text: str) -> bool:
    if BASE64_TOKEN_RE.search(text):
        return True
    if _has_base64_lines(text):
        return True
    return any(_has_base64_lines(block) for block in FENCED_BLOCK_RE.findall(text))


def _classify_download_discovery_response(*, download_affordance_found: bool, response_text: str) -> str:
    if download_affordance_found:
        return "file_link"
    if _looks_like_base64_text(response_text):
        return "base64_text"
    return "prose_only"


def _write_download_discovery_report(payload: dict[str, object]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_redact_jsonable(payload), indent=2, sort_keys=True)
    T4_DOWNLOAD_DISCOVERY.write_text(redact(text) + "\n", encoding="utf-8")


def run_download_discovery(_args: argparse.Namespace) -> int:
    session: BrowserSession | None = None
    close_on_exit = True
    try:
        with tempfile.TemporaryDirectory(prefix="m008b-download-discovery-") as tmp_text:
            zip_path, bundle_filename, bundle_size, prompt = _build_download_discovery_bundle(Path(tmp_text))
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

            _upload_bundle_zip_path(session, zip_path)
            audit(
                {
                    "leg": "T4-download-discovery",
                    "action": "upload-bundle",
                    "prompt-label": "tiny-one-file-bundle",
                    "observation": f"uploaded basename={bundle_filename},bytes={bundle_size}",
                    "markers": "n/a",
                    "result": "OK",
                }
            )
            time.sleep(HUMAN_PACE_S)
            if not recheck_safe(session):
                close_on_exit = False
                return 5

            _send_prompt_or_human_stop(session, prompt)
            audit(
                {
                    "leg": "T4-download-discovery",
                    "action": "send-rewritten-bundle-prompt",
                    "prompt-label": "download-discovery-task",
                    "observation": f"sent; prompt_chars={len(prompt)}; bundle={bundle_filename}",
                    "markers": "n/a",
                    "result": "OK",
                }
            )
            _wait_for_completion_or_human_stop(session)
            if not recheck_safe(session):
                close_on_exit = False
                return 5

            response_text = _latest_assistant_text(session)
            candidates = _inspect_download_affordances(session)
            download_affordance_found = any(_candidate_indicates_download_affordance(candidate) for candidate in candidates)
            response_kind = _classify_download_discovery_response(
                download_affordance_found=download_affordance_found,
                response_text=response_text,
            )
            payload: dict[str, object] = {
                "download_affordance_found": download_affordance_found,
                "candidates": candidates,
                "response_kind": response_kind,
                "response_excerpt": _redact_urlish_text(response_text, limit=400),
            }
            _write_download_discovery_report(payload)
            audit(
                {
                    "leg": "T4-download-discovery",
                    "action": "summary",
                    "prompt-label": "download-discovery-task",
                    "observation": (
                        f"found={download_affordance_found},kind={response_kind},"
                        f"candidates={len(candidates)},response_chars={len(response_text)}"
                    ),
                    "markers": "n/a",
                    "result": "OK",
                }
            )
            _emit(
                "DOWNLOAD-DISCOVERY: "
                f"found={download_affordance_found} kind={response_kind} candidates={len(candidates)}"
            )
            return 0
    except SystemExit as exc:
        if exc.code == 4:
            return 5
        raise
    except HumanActionStop as exc:
        close_on_exit = False
        _emit_human_action_needed(exc.label)
        return 5
    except Exception as exc:  # noqa: BLE001 - top-level CLI must fail closed and surface safe detail.
        _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if session is not None and close_on_exit:
            session.close()


def run_continuity_temp(_args: argparse.Namespace) -> int:
    session_a: BrowserSession | None = None
    session_b: BrowserSession | None = None
    close_a = True
    close_b = True
    try:
        nonce = _new_nonce()
        _assert_recall_prompt_does_not_leak_nonce(RECALL_PROMPT, nonce)
        plant_prompt = _plant_prompt(nonce)

        session_a = connect()
        _open_temp_chat(session_a)
        if not recheck_safe(session_a):
            close_a = False
            return 5

        _send_prompt_or_human_stop(session_a, plant_prompt)
        audit(
            {
                "leg": "T5-temp-A",
                "action": "send-plant",
                "prompt-label": "plant-nonce",
                "observation": f"sent; prompt_chars={len(plant_prompt)}",
                "markers": "n/a",
                "result": "OK",
            }
        )
        _wait_for_completion_or_human_stop(session_a)
        plant_text = _latest_assistant_text(session_a)
        audit(
            {
                "leg": "T5-temp-A",
                "action": "observe-plant",
                "prompt-label": "plant-nonce",
                "observation": f"plant_reply={plant_text}",
                "markers": "n/a",
                "result": "OK",
            }
        )

        time.sleep(HUMAN_PACE_S)
        if not recheck_safe(session_a):
            close_a = False
            return 5

        _send_prompt_or_human_stop(session_a, RECALL_PROMPT)
        audit(
            {
                "leg": "T5-temp-A",
                "action": "send-recall",
                "prompt-label": "recall-same-temp-chat",
                "observation": f"sent; prompt_chars={len(RECALL_PROMPT)}",
                "markers": "n/a",
                "result": "OK",
            }
        )
        _wait_for_completion_or_human_stop(session_a)
        recall_text = _latest_assistant_text(session_a)
        recall_ok = nonce in recall_text
        _write_redacted_text(T5_TEMP_RECALL, recall_text)
        session_a.close()
        session_a = None

        time.sleep(HUMAN_PACE_S)

        session_b = connect()
        _open_temp_chat(session_b)
        if not recheck_safe(session_b):
            close_b = False
            return 5

        _send_prompt_or_human_stop(session_b, RECALL_PROMPT)
        audit(
            {
                "leg": "T5-temp-B",
                "action": "send-control",
                "prompt-label": "recall-fresh-temp-control",
                "observation": f"sent; prompt_chars={len(RECALL_PROMPT)}",
                "markers": "n/a",
                "result": "OK",
            }
        )
        _wait_for_completion_or_human_stop(session_b)
        control_text = _latest_assistant_text(session_b)
        control_clean = nonce not in control_text
        _write_redacted_text(T5_TEMP_CONTROL, control_text)
        session_b.close()
        session_b = None

        recall_len = len(recall_text)
        control_len = len(control_text)
        if recall_ok and control_clean:
            verdict = "FALSIFIABLE_CONTINUITY_PROVEN"
        elif not recall_ok:
            verdict = "RECALL_FAILED"
        else:
            verdict = "CONTROL_LEAKED"
        payload = {
            "nonce_recalled_in_conversation": recall_ok,
            "control_is_clean": control_clean,
            "recall_len": recall_len,
            "control_len": control_len,
            "verdict": verdict,
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        T5_TEMP_CONTINUITY.write_text(
            redact(json.dumps(_redact_jsonable(payload), indent=2, sort_keys=True)) + "\n",
            encoding="utf-8",
        )
        audit(
            {
                "leg": "T5-temp",
                "action": "summary",
                "prompt-label": "temp-continuity",
                "observation": (
                    f"recall_ok={recall_ok},control_clean={control_clean},"
                    f"recall_len={recall_len},control_len={control_len}"
                ),
                "markers": "n/a",
                "result": verdict,
            }
        )
        _emit(f"TEMP-CONTINUITY: recall_ok={recall_ok} control_clean={control_clean} verdict={verdict}")
        return 0
    except SystemExit:
        raise
    except HumanActionStop as exc:
        if session_b is not None:
            close_b = False
        elif session_a is not None:
            close_a = False
        _emit_human_action_needed(exc.label)
        return 5
    except Exception as exc:  # noqa: BLE001 - top-level CLI must fail closed and surface safe detail.
        _emit(f"ERROR: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if session_b is not None and close_b:
            session_b.close()
        if session_a is not None and close_a:
            session_a.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M-008b attach-only real ChatGPT probe toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    connectivity = subparsers.add_parser("connectivity", help="open a fresh conversation without sending a prompt")
    connectivity.set_defaults(func=run_connectivity)

    completion = subparsers.add_parser(
        "completion-reliability",
        help="measure completion-marker reliability for a small varied prompt set",
    )
    completion.set_defaults(func=run_completion_reliability)

    continuity_temp = subparsers.add_parser(
        "continuity-temp",
        help="plant and recall a nonce in one Temporary Chat, with a fresh Temporary Chat control",
    )
    continuity_temp.set_defaults(func=run_continuity_temp)

    download_discovery = subparsers.add_parser(
        "download-discovery",
        help="upload a tiny bundle and discover whether the real surface exposes a download affordance",
    )
    download_discovery.set_defaults(func=run_download_discovery)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
