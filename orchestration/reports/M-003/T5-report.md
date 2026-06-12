ESTIMATE: T5 60m
START_TIMESTAMP: 2026-06-12T03:39:30-05:00
END_TIMESTAMP: 2026-06-12T03:39:59-05:00

## Files changed
- Added `src/ask_chatgpt/cli.py`.
- Added `[project.scripts]` line in `pyproject.toml`: `ask-chatgpt = "ask_chatgpt.cli:main"`.
- Added `tests/test_cli.py` with in-process and subprocess UC3 coverage.
- Added `scripts/accept_uc3.sh` and `scripts/accept_uc3.py`.

## CLI flag table as implemented
| Flag/argument | Implementation |
| --- | --- |
| `prompt` | Optional positional prompt; rejected if combined with `--prompt`; one prompt form required. |
| `--prompt TEXT` | Option prompt form for shell quoting. |
| `--session ID` | Passed as `session_identifier`. |
| `--model-settings JSON` | Parsed with stdlib `json`; must be a JSON object or exits 2 before browser/upload side effects. |
| `--files PATH` | Repeatable; passed as `files` to `ask_chatgpt`; enables UC2 result mode when non-empty. |
| `--dirs PATH` | Repeatable; passed as `dirs` to `ask_chatgpt`. |
| `--out FILE` | Writes assistant response text to FILE instead of stdout; in `--dry-run`/`--apply`, stdout remains JSON diff summary. |
| `--dry-run` | Mutually exclusive with `--apply`; requires at least one `--files`/`--dirs` and explicit `--root`; calls `apply_patch(..., dry_run=True)` if a patch bundle is returned. |
| `--apply` | Mutually exclusive with `--dry-run`; requires at least one `--files`/`--dirs` and explicit `--root`; only path that calls `apply_patch(..., dry_run=False)`. |
| `--root DIR` | Passed as `bundle_root`; required before browser/upload side effects for `--dry-run` and `--apply`; passed as `root` to `apply_patch`. |
| `--channel {real,mock}` | Passed through; tests/acceptance use `mock` only with loopback `--base-url`. |
| `--base-url URL` | Passed through for mock/local fixtures. |
| `--profile-path PATH` | Passed through without inspection. |
| `--timeout SECONDS` | Parsed as float and passed as `timeout_s`; default `30.0`. |

## Exit-code mapping
| Exit | Error |
| ---: | --- |
| 0 | Success |
| 2 | CLI usage errors from argparse/custom validation |
| 3 | `LoginRequiredError` |
| 4 | `SessionNotFoundError` |
| 5 | `ModelUnavailableError` |
| 6 | `RateLimitedError` |
| 7 | `ResponseTruncatedError` |
| 8 | `SelectorUnavailableError` |
| 9 | `UploadUnsupportedError` |
| 10 | `DownloadUnsupportedError` |
| 11 | `PatchBundleValidationError`, `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError` |
| 12 | `PatchApplyError` |
| 1 | Other `AskChatGPTError` or unexpected failures with a credential-free diagnostic |

## Thin-wrapper proof
- `src/ask_chatgpt/cli.py` imports public names only from `ask_chatgpt`: `ask_chatgpt`, `apply_patch`, `AskChatGPTResult`, `DiffSummary`, and exported named errors.
- The CLI parses args, validates usage errors before side effects, calls `ask_chatgpt(...)`, optionally calls `apply_patch(...)`, formats text/JSON output, and maps exceptions to exit codes.
- It does not walk bundles, parse manifests, validate zip structure, implement path containment, inspect symlinks, or write patch files itself.

## No-mutation enforcement
- Default ask/bundle mode never calls `apply_patch(..., dry_run=False)`; `tests/test_cli.py::test_files_without_apply_does_not_mutate_by_default` proves a returned patch bundle does not mutate the project tree without `--apply`.
- `--dry-run` requires `--root` and calls `apply_patch(..., dry_run=True)` only; the test and acceptance script compare before/after trees and assert no `.ask-chatgpt-tmp` exists.
- `--apply` requires explicit `--root` before browser/upload side effects; `--apply` and `--dry-run` are an argparse mutually exclusive group.

## Validation evidence
- STEP 0 inherited green: `uv sync --all-groups`; `uv run pytest -q` -> `91 passed in 43.03s`.
- After editing `pyproject.toml`, re-ran `uv sync --all-groups`; package rebuilt and console script registered.
- New CLI tests: `uv run pytest tests/test_cli.py -q` -> `28 passed in 4.90s`.
- Full suite: `uv run pytest -q` -> `119 passed in 42.92s`.
- UC3 acceptance: `bash scripts/accept_uc3.sh` -> `overall=pass`; artifact path `tmp/accept-uc3-20260612-033824/`; `results.json` includes prompt stdout, `--out`, and `--files --dry-run` no-mutation steps.

## Trust notes
- Automated tests and acceptance use `--channel mock` with `http://127.0.0.1:<ephemeral>` only; no test/script sets `channel="real"`.
- No credentials, cookies, tokens, browser profile contents, or external URLs are read/stored/logged by the CLI.
- No new dependencies; CLI uses stdlib `argparse`/`json` only.
- No git commit or push performed.
- Deviation note: START timestamp was recorded late after implementation because the initial `date -Iseconds` command was missed; END timestamp is from the final timestamp command.
T5-STATUS: DONE
