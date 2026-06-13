#!/usr/bin/env python3
"""M-008b real-site CDP probe toolkit.

This module is intentionally inert on import. The CLI attaches only through
BrowserSession(channel="cdp") when an operator explicitly runs a subcommand.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from playwright.sync_api import Error as PlaywrightError  # noqa: E402

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

BASE_URL = "https://chatgpt.com"
REPORT_DIR = ROOT / "orchestration" / "reports" / "M-008b"
AUDIT_LOG = REPORT_DIR / "real-audit-log.md"
T2_OBSERVATIONS = REPORT_DIR / "T2-completion-observations.json"

REDACT_C_RE = re.compile(r"/c/[^/?#\s]+")
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
    print(redact(message), flush=True)


def _human_label(exc: BaseException) -> str:
    if isinstance(exc, ChallengePresentError):
        return "CHALLENGE_PRESENT"
    return exc.__class__.__name__


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
