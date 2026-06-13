#!/usr/bin/env python3
"""M-009 real-site CDP probe toolkit (attach-only).

Inert on import. Drives the PRODUCTION ask_chatgpt code paths over an
operator-launched CDP browser so real behavior is observed through the same
code an agent consumer would call. Fail-closed, human-paced, redacted, with a
per-message audit log. Never launches a browser; never automates login; any
challenge/logout -> HUMAN-ACTION-NEEDED and stop.
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
REPORT_DIR = ROOT / "orchestration" / "reports" / "M-009"
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
AUDIT_HEADER = """# M-009 — Real-site per-message audit log (transparency, not rationing)

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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(json.dumps(payload, indent=2, sort_keys=True)) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M-009 attach-only real ChatGPT probe toolkit")
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
