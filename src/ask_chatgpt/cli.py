"""Command-line interface for ask-chatgpt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from ask_chatgpt import (
    AskChatGPTError,
    AskChatGPTResult,
    BundleIntegrityError,
    DiffSummary,
    DownloadUnsupportedError,
    LoginRequiredError,
    ModelUnavailableError,
    OversizedPayloadError,
    PatchApplyError,
    PatchBundleValidationError,
    PatchMalformedError,
    PathEscapeError,
    RateLimitedError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
    UploadUnsupportedError,
    apply_patch,
    ask_chatgpt,
)

_USAGE = 2

_ERROR_EXIT_CODES: tuple[tuple[type[BaseException], int], ...] = (
    (LoginRequiredError, 3),
    (SessionNotFoundError, 4),
    (ModelUnavailableError, 5),
    (RateLimitedError, 6),
    (ResponseTruncatedError, 7),
    (SelectorUnavailableError, 8),
    (UploadUnsupportedError, 9),
    (DownloadUnsupportedError, 10),
    (PatchMalformedError, 11),
    (BundleIntegrityError, 11),
    (OversizedPayloadError, 11),
    (PathEscapeError, 11),
    (PatchBundleValidationError, 11),
    (PatchApplyError, 12),
    (AskChatGPTError, 1),
)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        prompt, model_settings = _validated_runtime_args(parser, args)
        result = ask_chatgpt(
            prompt,
            session_identifier=args.session,
            model_settings=model_settings,
            channel=args.channel,
            base_url=args.base_url,
            profile_path=args.profile_path,
            timeout_s=args.timeout,
            files=args.files or None,
            dirs=args.dirs or None,
            bundle_root=args.root,
        )
        text = result.text if isinstance(result, AskChatGPTResult) else str(result)
        patch_bundle = result.patch_bundle if isinstance(result, AskChatGPTResult) else None

        if args.apply or args.dry_run:
            if args.out is not None:
                _write_text(args.out, text)
            dry_run = not args.apply
            if patch_bundle is None:
                _write_json(_empty_summary_payload(args.root, dry_run=dry_run))
            else:
                summary = apply_patch(patch_bundle, args.root, dry_run=dry_run)
                _write_json(_summary_payload(summary))
            return 0

        _write_default_response(args.out, text)
        return 0
    except SystemExit as exc:
        return _system_exit_code(exc)
    except Exception as exc:  # noqa: BLE001 - CLI boundary maps all failures to safe diagnostics.
        return _error_exit(exc)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask-chatgpt",
        description="Send a prompt to ChatGPT through the public ask_chatgpt API.",
    )
    parser.add_argument("prompt", nargs="?", help="prompt text; mutually exclusive with --prompt")
    parser.add_argument("--prompt", dest="prompt_option", help="prompt text as an option")
    parser.add_argument("--session", metavar="ID", help="stored session identifier")
    parser.add_argument("--model-settings", metavar="JSON", help="JSON object passed as model_settings")
    parser.add_argument("--files", metavar="PATH", action="append", default=[], help="file to include in the outgoing bundle; repeatable")
    parser.add_argument("--dirs", metavar="PATH", action="append", default=[], help="directory to include in the outgoing bundle; repeatable")
    parser.add_argument("--out", metavar="FILE", type=Path, help="write assistant response text to FILE")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="apply a returned patch bundle to --root")
    mode.add_argument("--dry-run", action="store_true", help="validate and summarize a returned patch bundle without writes")
    parser.add_argument("--root", metavar="DIR", type=Path, help="explicit apply root and bundle root for patch modes")
    parser.add_argument("--channel", choices=("real", "mock"), default="real", help="browser channel; tests use mock with --base-url")
    parser.add_argument("--base-url", metavar="URL", help="mock/local base URL")
    parser.add_argument("--profile-path", metavar="PATH", type=Path, help="browser profile path passed through without inspection")
    parser.add_argument("--timeout", metavar="SECONDS", type=float, default=30.0, help="completion timeout in seconds")
    return parser


def _validated_runtime_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[str, dict[str, Any] | None]:
    if args.prompt is not None and args.prompt_option is not None:
        parser.error("positional prompt and --prompt are mutually exclusive")
    prompt = args.prompt_option if args.prompt_option is not None else args.prompt
    if prompt is None:
        parser.error("prompt is required: use positional prompt or --prompt TEXT")

    model_settings = _parse_model_settings(parser, args.model_settings)
    has_bundle_paths = bool(args.files or args.dirs)
    if (args.apply or args.dry_run) and not has_bundle_paths:
        parser.error("--apply/--dry-run require at least one --files/--dirs path")
    if (args.apply or args.dry_run) and args.root is None:
        parser.error("--apply/--dry-run require explicit --root")
    return str(prompt), model_settings


def _parse_model_settings(parser: argparse.ArgumentParser, value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parser.error("invalid --model-settings: expected a JSON object")
    if not isinstance(parsed, dict):
        parser.error("invalid --model-settings: expected a JSON object")
    return parsed


def _write_default_response(out_path: Path | None, text: str) -> None:
    if out_path is None:
        sys.stdout.write(text)
    else:
        _write_text(out_path, text)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _summary_payload(summary: DiffSummary) -> dict[str, Any]:
    return {
        "root": str(summary.root),
        "dry_run": summary.dry_run,
        "files": [
            {
                "path": item.path,
                "change_kind": item.change_kind,
                "old_sha256": item.old_sha256,
                "new_sha256": item.new_sha256,
                "old_bytes": item.old_bytes,
                "new_bytes": item.new_bytes,
                "byte_delta": item.byte_delta,
                "lines_added": item.lines_added,
                "lines_deleted": item.lines_deleted,
            }
            for item in summary.files
        ],
        "added": summary.added,
        "modified": summary.modified,
        "deleted": summary.deleted,
        "total_files": summary.total_files,
        "total_byte_delta": summary.total_byte_delta,
        "total_bytes_changed": summary.total_bytes_changed,
    }


def _empty_summary_payload(root: Path, *, dry_run: bool) -> dict[str, Any]:
    return {
        "root": str(root.resolve()),
        "dry_run": dry_run,
        "files": [],
        "added": 0,
        "modified": 0,
        "deleted": 0,
        "total_files": 0,
        "total_byte_delta": 0,
        "total_bytes_changed": 0,
    }


def _system_exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _error_exit(exc: BaseException) -> int:
    code = _exit_code_for_exception(exc)
    if isinstance(exc, AskChatGPTError):
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
    else:
        print(
            f"{exc.__class__.__name__}: unexpected ask-chatgpt failure. Operator action: retry or inspect the local environment.",
            file=sys.stderr,
        )
    return code


def _exit_code_for_exception(exc: BaseException) -> int:
    for error_type, code in _ERROR_EXIT_CODES:
        if isinstance(exc, error_type):
            return code
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
