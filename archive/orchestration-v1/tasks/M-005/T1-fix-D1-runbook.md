# T1 — Fix D1: regenerate the real-site acceptance runbook from ground truth (single editor)

You are a fresh worker. You inherit NOTHING except this file and the files it tells you to read. Everything you need is below. Do not assume any context.

## Your one job

`docs/runbooks/real-site-acceptance.md` references NON-EXISTENT CLI flags/subcommands and WRONG error class names. Rewrite the runbook so every command, flag, and error-name it contains matches the ACTUAL committed CLI/error surface, and so an operator can run it as written. This is a single-file documentation edit (you MAY also need to fix `docs/runbooks/observe-chatgpt-unknowns.md` ONLY if it shares the same stale commands — check, but do not gratuitously edit it).

## Ground truth — re-derive, do not trust this prose blindly

1. Capture the authoritative CLI surface yourself and PASTE it into your report:
   ```
   uv sync --all-groups
   uv run ask-chatgpt --help
   ```
   For reference, the surface at HEAD is (verify it matches your capture):
   ```
   usage: ask-chatgpt [-h] [--prompt PROMPT_OPTION] [--session ID]
                      [--model-settings JSON] [--files PATH] [--dirs PATH]
                      [--out FILE] [--apply | --dry-run] [--root DIR]
                      [--channel {real,mock}] [--base-url URL]
                      [--profile-path PATH] [--timeout SECONDS]
                      [prompt]
   ```
   There are NO subcommands. The ONLY flags that exist are: positional `prompt`, `--prompt`, `--session`, `--model-settings`, `--files`, `--dirs`, `--out`, `--apply`, `--dry-run`, `--root`, `--channel`, `--base-url`, `--profile-path`, `--timeout`, `-h/--help`.
2. Read `src/ask_chatgpt/cli.py` (the argparse surface + how args map to `ask_chatgpt(...)`) and `src/ask_chatgpt/errors.py` (the REAL exception class names).
3. Read the CURRENT `docs/runbooks/real-site-acceptance.md` in full.

## Known stale items to eliminate (verify each against ground truth, then remove/replace ALL of them)

- Flags/subcommands that DO NOT EXIST and must be removed/replaced: `--profile` (real flag is `--profile-path`), `--patch-out`, `--bundle`, and the subcommand `ask-chatgpt apply-patch`. The one-shot CLI has no subcommands: a patch round-trip is `ask-chatgpt "<prompt>" --files ... --dirs ... --root <DIR> --dry-run` (validate/summarize, no writes) then `--apply` (apply). `--out FILE` writes the assistant text. `--session ID` pins a conversation. `--channel real --profile-path <DIR>` selects the real browser channel.
- Error class names that DO NOT EXIST and must be replaced with the real ones from `errors.py`:
  - `PatchBundleMalformedError`  -> `PatchMalformedError`
  - `PatchBundleIntegrityError`  -> `BundleIntegrityError`
  - `PatchBundleTooLargeError`   -> `OversizedPayloadError`
  - `PatchPathEscapeError`       -> `PathEscapeError`
  - (the base validation class is `PatchBundleValidationError`; apply-stage failures are `PatchApplyError`; selector failures `SelectorUnavailableError`. Use ONLY names that appear in `errors.py`.)

## Acceptance / what "fixed" means (your report MUST prove all of this)

1. EVERY command in the runbook is runnable as written against the real CLI surface (1-2 commands per proof; preserve the operator-facing intent of each UC1/UC2/UC3 proof, the prerequisites section, the typed-consent gates, and the honest mock-vs-real failure-interpretation notes — do NOT delete the consent gating or honesty content; only correct the mechanics).
2. EVERY error-name in the runbook exists in `errors.py`.
3. Cross-check ALL THREE UC sections (UC1, UC2, UC3) AND the prerequisites section against the real surface.
4. Provide in your report a CONFORMANCE TABLE: one row per command-or-flag-or-error-name appearing in your rewritten runbook -> `exists-in-CLI/errors.py? yes/no` with the cli.py/errors.py line or `--help` token as evidence. ALL rows must be `yes`. Also paste the full `uv run ask-chatgpt --help` output you captured.
5. Do NOT invent new product behavior. If the old runbook documented a workflow the current CLI cannot express (e.g. a separate patch-out file), re-express it using only real flags (`--files/--dirs/--root/--dry-run/--apply/--out`), or note it as an operator-manual step — do not fabricate a flag.

## Constraints / SAFETY (transcribed verbatim — obey exactly)

- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; loopback/local only. (This is a docs edit — you should not need network at all beyond `uv sync` package fetches.)
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Do NOT write `.claude/` or `.agents/`. Do NOT touch the shared agent venv (`~/.local/share/agent-python/.venv`); use `uv run`/`uv sync` from the repo root which targets the project `.venv`.
- `uv sync --all-groups` ALWAYS before any `uv run`. NEVER `git push`.
- ESTIMATE BEFORE EXECUTE: state expected wall-clock before any command.

## Commit

When done, `git add` the runbook (and observe-unknowns.md only if you corrected shared stale commands) and commit with a message starting `M-005: ` (e.g. `M-005: fix D1 — regenerate real-site-acceptance runbook from committed CLI/error surface`). Do NOT commit anything else. Report the commit SHA.

## Telemetry + report (write to `orchestration/reports/M-005/T1.md`, cap ~200 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T1 <minutes>m`.
- Body: the `--help` capture, the conformance table (all `yes`), a short summary of what you changed, and the commit SHA.
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T1-STATUS: DONE` (or `T1-STATUS: BLOCKED` with the exact blocker).
