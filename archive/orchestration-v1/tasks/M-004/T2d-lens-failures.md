# T2d — VERIFY LENS: honest failure modes (independent NON-PRODUCER, read-only). Best-of-N panel member 4 of 5.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code, and you are NOT the evidence runner (T1) nor any other lens. You reason OVER the authoritative evidence set produced by T1 — you do **NOT** re-run the heavy suite or acceptance scripts. Re-derive every judgment from GROUND TRUTH = the committed source + the RAW T1 artifacts. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only.

## Your dimension: HONEST FAILURE MODES
The README promises failure modes "named actionably." For EACH named failure below, prove three things from ground truth: (1) it is **raisable** (a real error class exists for it), (2) it is **actually raised** by a real code path that a test or acceptance step exercises (cite the test id or raise site), and (3) its message is **actionable AND credential-free** (tells the operator what to do; contains no cookie/token/secret/profile content).

## The named failure modes to verify (each must map to a real error + a real raise + a real test)
From README + the mission, the failure taxonomy is:
- login required → `LoginRequiredError`
- session not found → `SessionNotFoundError`
- model unavailable → `ModelUnavailableError`
- response truncated → `ResponseTruncatedError`
- selector unavailable → `SelectorUnavailableError`
- upload unsupported → `UploadUnsupportedError`
- download unsupported → `DownloadUnsupportedError`
- patch malformed → `PatchMalformedError`
- hash / byte mismatch → `BundleIntegrityError`
- oversized → `OversizedPayloadError`
- path escape → `PathEscapeError`
(Also note the base classes `AskChatGPTError`, `PatchBundleValidationError`, and `RateLimitedError` / `PatchApplyError` if relevant.)

## Read FIRST (in order)
1. This contract in full.
2. `src/ask_chatgpt/errors.py` — every error class + its baked-in remediation message. Read each message in full.
3. The RAISE SITES: grep `src/` for each error class name and read where/why it is raised (`api.py`, `driver.py`, `patch.py`, `bundle.py`, `readers.py`, `selector_map.py`, `session_registry.py`).
4. The TESTS that exercise them: `tests/test_errors.py`, `tests/test_patch.py`, `tests/test_driver.py`, `tests/test_readers.py`, `tests/test_session_registry.py`, `tests/test_fixture_adversarial.py`, and any acceptance step. T1 artifacts: `tmp/verify-m004/clone_pytest.txt`, the three `accept_*_results.json`, `zipslip.txt` (PathEscapeError), `netguard.txt`.

## Method
- Build a FAILURE-MODE table: `failure mode | error class | raise site (file:line) | test/acceptance that triggers it (id) | message (quoted) | actionable? | credential-free?`.
- A row is PASS only if the error EXISTS, is RAISED by real code, is TRIGGERED by a real test/acceptance step, and the message is actionable + credential-free. A class that exists but is never raised, or raised but never tested, = FAIL (note which leg).
- For `PathEscapeError`, cross-cite `zipslip.txt`. For `LoginRequiredError` / `SessionNotFoundError` / `ResponseTruncatedError` / `ModelUnavailableError` / `SelectorUnavailableError`, find the driver/api path + the test (often via the mock fixture simulating that state). For `UploadUnsupportedError` / `DownloadUnsupportedError`, find the bundle/driver path. For `PatchMalformedError` / `BundleIntegrityError` / `OversizedPayloadError`, find the patch-validation path.
- Inspect each message string for actionability (does it tell the operator the next step?) and for credential leakage (must contain no secret/token/cookie/profile content).

## Deliverable — `orchestration/reports/M-004/lens-failures.md` (≤200 lines)
- Header `LENS: honest-failure-modes`.
- The full FAILURE-MODE table (all 11 named modes + any extras).
- A line `T2d-VERDICT: PASS|FAIL` (FAIL if ANY named mode is not raisable, not raised by real code, not exercised by a test/acceptance step, or has a non-actionable / credential-leaking message; name the offending modes).
- Telemetry v2: FIRST line `ESTIMATE: T2d <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:`.
- LAST line: `T2d-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything is loopback/local. ZERO new pip deps. You run NOTHING heavy — you READ source + T1 artifacts. Do NOT re-run the full suite or acceptance scripts — T1 is the sole heavy runner.
- This mission MUTATES NOTHING except your one report. NEVER edit or "fix" any source/tests/docs/scripts — REPORT defects instead (independence boundary).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents (you AUDIT error messages for leakage — quote the message text, which must already be credential-free). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY if strictly needed (you should not need to); never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T2d-STATUS: DONE|BLOCKED` as the LAST line.
