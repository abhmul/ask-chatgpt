# T4b — Docs lens: independent re-verification of D1 (+ spot-recheck of M-004 docs PASS items)

You are a FRESH, INDEPENDENT verification worker. You did NOT write any of the code/docs under test. You inherit NOTHING except this file. Reason from GROUND TRUTH (the committed files) + the authoritative evidence already captured under `tmp/verify-m005/` by the evidence runner. Do NOT re-run the heavy test suite (it was already run once authoritatively — reasoning over it is your job). You may run lightweight read-only commands (`uv run ask-chatgpt --help`, greps).

## Context: the defect you are re-checking

D1 (material): `docs/runbooks/real-site-acceptance.md` previously referenced NON-EXISTENT CLI flags/subcommands (`--profile`, `--patch-out`, `--bundle`, `ask-chatgpt apply-patch`) and WRONG error class names (`PatchBundleMalformedError`, `PatchBundleIntegrityError`, `PatchBundleTooLargeError`, `PatchPathEscapeError`). It was rewritten in commit `0179400` ("M-005: fix D1 real-site acceptance runbook"). Your job: independently decide whether D1 is ACTUALLY fixed — i.e. the runbook is now runnable as written against the real CLI/error surface.

## Ground truth (re-derive, do not trust this prose)

- Authoritative CLI surface: run `uv sync --all-groups` then `uv run ask-chatgpt --help` (this is a local `--help`, no network to chatgpt; PyPI for sync is fine), AND read `src/ask_chatgpt/cli.py`. The ONLY flags that exist: positional `prompt`, `--prompt`, `--session`, `--model-settings`, `--files`, `--dirs`, `--out`, `--apply`, `--dry-run`, `--root`, `--channel {real,mock}`, `--base-url`, `--profile-path`, `--timeout`, `-h/--help`. There are NO subcommands.
- Authoritative error names: read `src/ask_chatgpt/errors.py`. The real classes: `AskChatGPTError`, `LoginRequiredError`, `SessionNotFoundError`, `ModelUnavailableError`, `ResponseTruncatedError`, `RateLimitedError`, `SelectorUnavailableError`, `UploadUnsupportedError`, `DownloadUnsupportedError`, `PatchBundleValidationError`, `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`, `PatchApplyError`.

## D1 re-check (the core of your verdict)

1. Read the CURRENT `docs/runbooks/real-site-acceptance.md` in full.
2. Extract EVERY token that is a CLI command, a flag, a subcommand, or an exception class name appearing in it.
3. Build a CONFORMANCE TABLE: token -> exists in the real CLI surface / `errors.py`? (yes/no, with the `--help` line or `cli.py`/`errors.py` line as evidence). EVERY row MUST be `yes`. If ANY token is a nonexistent flag/subcommand or a nonexistent error class, D1 is NOT fixed -> FAIL, and list the offending tokens.
4. Operator-runnability: confirm each UC1/UC2/UC3 proof is expressed in 1-2 commands using ONLY real flags; that the typed-consent gates and the honest mock-vs-real failure-interpretation notes are still present (not deleted by the rewrite); and that the prerequisites section matches the real surface. Specifically confirm the previously-stale items are gone: no `--profile` (only `--profile-path`), no `--patch-out`, no `--bundle`, no `apply-patch` subcommand, and none of the four wrong error names above.

## Spot-recheck (confirm these M-004 docs-lens PASS items STILL hold on the new HEAD)

- D-001 conformance: `docs/DECISIONS.md` D-001 (channel layering / library-first posture) still matches the code (`src/ask_chatgpt/readers.py`, `patch.py`, `cli.py`). Sample and confirm.
- Bundle-protocol sampling: pick ~3 bundle/patch protocol claims stated in docs/runbook and confirm each against `src/ask_chatgpt/bundle.py` / `patch.py`.
- Mock-vs-real honesty: user-facing docs still clearly distinguish mock-proven vs real-site-unproven (e.g. `README.md`, the runbook header, `docs/runbooks/observe-chatgpt-unknowns.md`).

## Constraints / SAFETY (obey exactly)

- Loopback/local only; NEVER contact chatgpt.com/openai. `uv run ask-chatgpt --help` is fine (no chatgpt contact). PyPI for `uv sync` is permitted.
- Do NOT modify ANY file under test. Write ONLY your report at `orchestration/reports/M-005/T4b.md` (and you may read `tmp/verify-m005/` evidence). Do NOT write `.claude/`/`.agents/`; do NOT touch the shared agent venv. Do NOT commit. NEVER `git push`.

## Report (`orchestration/reports/M-005/T4b.md`, cap ~200 lines)

- First lines: `START_TIMESTAMP:` + `ESTIMATE: T4b <minutes>m`.
- The D1 conformance table (every token yes, or the offending tokens), the operator-runnability findings, and the 3 spot-recheck results.
- A single explicit line `D1-VERDICT: PASS` or `D1-VERDICT: FAIL` (with the exact remaining defects if FAIL).
- Last two lines: `END_TIMESTAMP:` + `T4b-STATUS: DONE` (or BLOCKED with the blocker). Also include an overall `T4b-VERDICT: PASS|FAIL` line.
