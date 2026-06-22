# `--max-total-wait` cutoff (`MaxTotalWaitExceededError`) does not auto-salvage the partial to `--out`/stdout

Filed 2026-06-22 (M14 triage re-file). **Severity: minor** (salvage-convenience gap — no data loss; the partial is persisted to the store and recoverable via `history`/`scrape`). Scope: `src/ask_chatgpt/cli.py`.

## Summary
`ask` (and other send paths) can end a wait two ways:
- **Activity timeout** → `CompletionTimeoutError` (`errors.py`, exit 50).
- **Total-wait cap** (`--max-total-wait` / `max_total_wait_s`) → `MaxTotalWaitExceededError` (`errors.py`, exit 51).

These are **sibling** classes (neither subclasses the other). The CLI's salvage path only catches the first:

- `cli.py:92` `except CompletionTimeoutError as exc:` → emits the attached partial to stdout and the `--out` file before exiting (pinned by `tests/test_cli.py::test_cli_completion_timeout_prints_salvage_to_stdout_and_out_before_error`).
- `cli.py:103` `except AskChatGPTError as exc:` → the generic handler that `MaxTotalWaitExceededError` falls through to. It does **not** write the partial to `--out`/stdout, even though `completion.py:156` (`_attach_partials`) attaches the partial text to the exception.

So a caller who bounds a long Pro-Extended generation with `--max-total-wait` (exactly the original truncation issue's use case) and hits the cap gets a clean error but **no partial in their `--out` file** — unlike the activity-timeout path, which salvages it. (The partial IS in the store, so `history`/`scrape` recover it; this is strictly a convenience asymmetry, not the irrecoverable v1 loss.)

## Root cause
`MaxTotalWaitExceededError` is not imported or specially handled in `cli.py` (line 14 imports only `AskChatGPTError, CompletionTimeoutError`), so the dedicated salvage branch added for `CompletionTimeoutError` never runs for the total-wait cap.

## Suggested fix
Mirror the `CompletionTimeoutError` salvage branch for `MaxTotalWaitExceededError`: either widen the `cli.py:92` handler to catch both (they carry the same attached-partial shape) or add a parallel branch. Emit the attached partial to stdout + `--out` before the non-zero exit, exactly as the activity-timeout path does.

## Falsifiable test
Add `tests/test_cli.py::test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error` mirroring the existing `test_cli_completion_timeout_*` test: drive `ask` so completion raises `MaxTotalWaitExceededError` with an attached partial + `--out FILE`; assert the partial appears on stdout AND in `FILE`, and the exit code is 51. It must FAIL on current `main` (the partial is currently dropped from `--out`/stdout on this path).

## Provenance
Re-filed from the archived v1 issue `archive/issues/2026-06-14-response-truncated-drops-out-file-and-session.md`, whose original v1 bug (lost `--out` + lost session registry, hidden 600 s ceiling, `ResponseTruncatedError`) is obsolete and substantively fixed in v2. This file tracks only the narrow residual. See `team/evidence/handoffs/M14-triage-issues.md` §2 (#3) for the full both-readings analysis.
