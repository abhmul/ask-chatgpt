"""Command-line interface for the M4 offline-core rewrite."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from ask_chatgpt import __version__
from ask_chatgpt.errors import AskChatGPTError, CompletionTimeoutError, MaxTotalWaitExceededError
from ask_chatgpt.models import StatusReport, Transcript, TurnRecord
from ask_chatgpt.session import Session
from ask_chatgpt.store import Store

_STATUS_FIELD_ORDER = (
    "ok",
    "cdp",
    "signed_in",
    "login_or_challenge",
    "selector_valid",
    "conversations",
    "blocking_code",
    "details",
)
_ERROR_EXIT_BY_CODE = {
    "CDP_UNREACHABLE": 20,
    "HUMAN-ACTION-NEEDED": 21,
    "DOMAIN_NOT_ALLOWED": 22,
    "CONVERSATION_NOT_FOUND": 23,
    "SELECTOR_NOT_FOUND": 24,
    "PROMPT_NOT_SUBMITTED": 30,
    "MODEL_SELECTION_NOT_REFLECTED": 31,
    "TOOL_SELECTION_NOT_REFLECTED": 32,
    "BACKEND_AUTH_UNAVAILABLE": 40,
    "BACKEND_CAPTURE_SHAPE": 41,
    "CAPTURE_FAIL_CLOSED": 42,
    "COMPLETION_TIMEOUT": 50,
    "MAX_TOTAL_WAIT_EXCEEDED": 51,
    "RATE_LIMITED": 52,
    "ATTACHMENT_NOT_FOUND": 60,
    "ATTACHMENT_FETCH_FAILED": 61,
    "TAB_POOL_EXHAUSTED": 62,
    "ATTACHMENT_UPLOAD_FAILED": 63,
    "STORE_ERROR": 70,
    "INTERNAL_ERROR": 99,
}
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "bearer",
    "cookie",
    "header",
    "key",
    "oai",
    "password",
    "prompt",
    "secret",
    "token",
)
_SENSITIVE_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "cookie:",
    "oai-",
    "password",
    "secret",
    "token",
    "canary",
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised through main parse path
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    parser = _build_parser()
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    json_mode = bool(getattr(args, "json", False))
    try:
        return int(args.handler(args))
    except (CompletionTimeoutError, MaxTotalWaitExceededError) as exc:
        if getattr(args, "command", None) == "ask":
            partial = _partial_markdown_from_error(exc)
            if partial:
                try:
                    _emit_payload(_ask_payload(partial), getattr(args, "out", None), getattr(args, "data_dir", None), None)
                except AskChatGPTError as out_exc:
                    _write_error(out_exc, json_mode=json_mode)
                    return out_exc.exit_code
        _write_error(exc, json_mode=json_mode)
        return exc.exit_code
    except AskChatGPTError as exc:
        _write_error(exc, json_mode=json_mode)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 - public CLI boundary must not traceback by default.
        _write_internal_error(exc, json_mode=json_mode)
        return 99


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, default=None)
    common.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    common.add_argument("--selector-channel", choices=("real", "mock"), default="real")

    parser = _Parser(
        prog="ask-chatgpt",
        description="Programmatic ChatGPT CLI (offline-core M4 verbs).",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    ask = subcommands.add_parser("ask", parents=[common], allow_abbrev=False, help="send a prompt")
    ask.add_argument("args", nargs="+", metavar="ARG", help="optional conversation followed by prompt")
    ask.add_argument("--model", default=None)
    ask.add_argument("--tool", action="append", default=[])
    ask.add_argument("--attach", action="append", default=[])
    ask.add_argument("--timeout", type=float, default=None)
    ask.add_argument("--max-total-wait", type=float, default=None)
    ask.add_argument("--out", type=Path, default=None)
    ask.set_defaults(handler=_handle_ask)

    create = subcommands.add_parser("create", parents=[common], allow_abbrev=False, help="create a conversation")
    create.add_argument("--project", default=None)
    create.add_argument("--json", action="store_true")
    create.set_defaults(handler=_handle_create)

    scrape = subcommands.add_parser("scrape", parents=[common], allow_abbrev=False, help="scrape a conversation")
    scrape.add_argument("conv")
    scrape.add_argument("--with-attachments", action="store_true")
    scrape.add_argument("--out", type=Path, default=None)
    scrape.set_defaults(handler=_handle_scrape)

    history = subcommands.add_parser("history", parents=[common], allow_abbrev=False, help="render local history")
    history.add_argument("conv")
    history.add_argument("--out", type=Path, default=None)
    history.set_defaults(handler=_handle_history)

    export = subcommands.add_parser("export", parents=[common], allow_abbrev=False, help="render local history")
    export.add_argument("conv")
    export.add_argument("--out", type=Path, default=None)
    export.set_defaults(handler=_handle_history)

    fetch = subcommands.add_parser("fetch", parents=[common], allow_abbrev=False, help="fetch a cached attachment")
    fetch.add_argument("conv")
    fetch.add_argument("attachment")
    fetch.add_argument("--json", action="store_true")
    fetch.set_defaults(handler=_handle_fetch)

    status = subcommands.add_parser("status", parents=[common], allow_abbrev=False, help="show diagnostics")
    status.add_argument("conv", nargs="?")
    status.add_argument("--json", action="store_true")
    status.add_argument("--no-browser-probe", action="store_true")
    status.set_defaults(handler=_handle_status)

    loop = subcommands.add_parser("loop", parents=[common], allow_abbrev=False, help="bounded M4 mock loop stub")
    loop.add_argument("conv")
    loop.add_argument("--message", default="keep pushing!!")
    loop.add_argument("--model", default=None)
    loop.add_argument("--tool", action="append", default=[])
    loop.add_argument("--attach", action="append", default=[])
    loop.add_argument("--timeout", type=float, default=None)
    loop.add_argument("--max-total-wait", type=float, default=None)
    loop.add_argument("--max-iterations", type=int, default=1)
    loop.add_argument("--out-dir", type=Path, default=None)
    loop.set_defaults(handler=_handle_loop)

    return parser


def _new_session(args: argparse.Namespace) -> Session:
    channel = "mock" if args.selector_channel == "mock" else "cdp"
    return Session(cdp_endpoint=args.cdp_endpoint, data_dir=args.data_dir, channel=channel)


def _handle_ask(args: argparse.Namespace) -> int:
    conv, prompt = _split_ask_positionals(args.args)
    session = _new_session(args)
    try:
        answer = session.ask(
            conv,
            prompt,
            model=args.model,
            tools=tuple(args.tool),
            attach=tuple(args.attach),
            timeout=args.timeout,
            max_total_wait=args.max_total_wait,
            out=args.out,
        )
        content = answer.content_markdown if isinstance(answer, TurnRecord) else str(answer)
        _emit_payload(_ask_payload(content), args.out, args.data_dir, session)
        return 0
    finally:
        session.detach()


def _handle_create(args: argparse.Namespace) -> int:
    session = _new_session(args)
    ref = session.create(project=args.project)
    if args.json:
        _write_json_stdout(
            {
                "conversation_id": ref.conversation_id,
                "url": ref.url,
                "project_id": ref.project_id,
                "is_draft": ref.is_draft,
            }
        )
    else:
        sys.stdout.write(f"{ref.url}\n")
        sys.stdout.flush()
    return 0


def _handle_scrape(args: argparse.Namespace) -> int:
    session = _new_session(args)
    try:
        transcript = session.scrape(args.conv, with_attachments=args.with_attachments, out=args.out)
        _emit_payload(_render_transcript(session, transcript), args.out, args.data_dir, session)
        return 0
    finally:
        session.detach()


def _handle_history(args: argparse.Namespace) -> int:
    session = _new_session(args)
    transcript = session.history(args.conv)
    _emit_payload(_render_transcript(session, transcript), args.out, args.data_dir, session)
    return 0


def _handle_fetch(args: argparse.Namespace) -> int:
    session = _new_session(args)
    fetched = session.fetch(args.conv, args.attachment)
    if args.json:
        _write_json_stdout({"path": str(fetched)} if isinstance(fetched, Path) else fetched)
    else:
        sys.stdout.write(f"{fetched}\n")
        sys.stdout.flush()
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    session = _new_session(args)
    report = session.status(args.conv, probe_browser=not args.no_browser_probe)
    if args.json:
        _write_json_stdout(report)
    else:
        _write_status_human(report)
    return 0 if report.ok else _ERROR_EXIT_BY_CODE.get(report.blocking_code or "", 1)


def _handle_loop(args: argparse.Namespace) -> int:
    if args.max_iterations < 0:
        raise ValueError("--max-iterations must be non-negative")
    session = _new_session(args)
    try:
        iteration = 0
        last_emitted: TurnRecord | None = None
        try:
            for iteration, turn in enumerate(
                session.loop(
                    args.conv,
                    message=args.message,
                    model=args.model,
                    tools=tuple(args.tool),
                    attach=tuple(args.attach),
                    timeout=args.timeout,
                    max_total_wait=args.max_total_wait,
                    max_iterations=args.max_iterations,
                    out_dir=args.out_dir,
                ),
                start=1,
            ):
                _write_jsonl_stdout(_loop_envelope(iteration, turn))
                last_emitted = turn
        except KeyboardInterrupt as exc:
            partial = getattr(exc, "partial", None)
            if isinstance(partial, TurnRecord) and (
                last_emitted is None or last_emitted.message_id != partial.message_id
            ):
                _write_jsonl_stdout(_loop_envelope(iteration + 1, partial))
            return 130
        return 0
    finally:
        session.detach()


def _split_ask_positionals(values: Sequence[str]) -> tuple[str | None, str]:
    if len(values) == 1:
        return None, values[0]
    return values[0], " ".join(values[1:])


def _ask_payload(content: str) -> str:
    return content.rstrip("\n") + "\n"


def _render_transcript(session: object, transcript: object) -> str:
    if isinstance(transcript, str):
        return transcript
    store = getattr(session, "store", None)
    renderer = getattr(store, "render_markdown", None)
    if callable(renderer):
        return str(renderer(transcript))
    if isinstance(transcript, Transcript):
        sections: list[str] = []
        for turn in transcript.turns:
            heading = "User" if turn.role == "user" else "Assistant"
            sections.append(f"## {heading}\n\n{turn.content_markdown}")
        return "" if not sections else "\n\n".join(sections).rstrip("\n") + "\n"
    return str(transcript)


def _emit_payload(content: str | bytes, out: Path | None, data_dir: Path | None, session: object | None) -> None:
    store = getattr(session, "store", None)
    if not isinstance(store, Store):
        store = Store(data_dir=data_dir)
    store.emit_payload(content, out=out)


def _partial_markdown_from_error(exc: BaseException) -> str | None:
    direct = getattr(exc, "partial_markdown", None)
    if isinstance(direct, str) and direct:
        return direct
    for attr in ("backend_partial", "dom_partial"):
        state = getattr(exc, attr, None)
        text = getattr(state, "partial_markdown", None)
        if isinstance(text, str) and text:
            return text
    record = getattr(exc, "partial", None)
    text = getattr(record, "content_markdown", None)
    return text if isinstance(text, str) and text else None


def _loop_envelope(iteration: int, turn: TurnRecord) -> Mapping[str, Any]:
    return {
        "schema_version": 1,
        "type": "turn",
        "iteration": iteration,
        "conversation_id": turn.conversation_id,
        "conversation_url": turn.conversation_url,
        "user_message_id": turn.user_message_id,
        "message_id": turn.message_id,
        "status": turn.status,
        "partial": turn.partial,
        "capture_source": turn.capture_source,
        "fidelity": turn.fidelity,
        "content_markdown": turn.content_markdown,
        "paths": {},
    }


def _write_status_human(report: StatusReport) -> None:
    lines = [
        f"ok: {str(report.ok).lower()}",
        f"blocking_code: {report.blocking_code or ''}",
        f"conversations: {'' if report.conversations is None else report.conversations}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


def _write_error(exc: AskChatGPTError, *, json_mode: bool) -> None:
    if json_mode:
        _write_json_stderr(_error_to_json(exc))
        return
    sys.stderr.write(f"ERROR {exc.code}: {_sanitize_message(exc.message)}\n")
    sys.stderr.flush()


def _write_internal_error(exc: BaseException, *, json_mode: bool) -> None:
    del exc
    payload = {
        "code": "INTERNAL_ERROR",
        "message": "unexpected internal error",
        "exit_code": 99,
        "retryable": False,
        "retry_action": "report_bug",
        "details": {},
    }
    if json_mode:
        _write_json_stderr(payload)
    else:
        sys.stderr.write("ERROR INTERNAL_ERROR: unexpected internal error\n")
        sys.stderr.flush()


def _error_to_json(exc: AskChatGPTError) -> Mapping[str, Any]:
    return {
        "code": exc.code,
        "message": _sanitize_message(exc.message),
        "exit_code": exc.exit_code,
        "retryable": exc.retryable,
        "retry_action": exc.retry_action,
        "details": _json_safe(exc.details),
    }


def _write_json_stdout(value: Any) -> None:
    sys.stdout.write(json.dumps(_json_safe(value), ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _write_jsonl_stdout(value: Any) -> None:
    _write_json_stdout(value)


def _write_json_stderr(value: Any) -> None:
    sys.stderr.write(json.dumps(_json_safe(value), ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stderr.flush()


def _json_safe(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        if isinstance(value, StatusReport):
            return {name: _json_safe(getattr(value, name)) for name in _STATUS_FIELD_ORDER}
        return {field.name: _json_safe(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(_redact_for_key(key, nested)) for key, nested in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if isinstance(value, str):
        return _sanitize_string_value(value)
    return value


def _redact_for_key(key: object, value: Any) -> Any:
    if _looks_sensitive_key(key):
        return "<redacted>"
    return value


def _sanitize_message(message: str) -> str:
    if not message:
        return ""
    return "<redacted>" if _looks_sensitive_value(message) else message


def _sanitize_string_value(value: str) -> str:
    return "<redacted>" if _looks_sensitive_value(value) else value


def _looks_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _looks_sensitive_value(value: str) -> bool:
    lowered = value.lower()
    return any(part in lowered for part in _SENSITIVE_VALUE_PARTS)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
