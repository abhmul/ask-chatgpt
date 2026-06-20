# T9·RV — INDEPENDENT re-verification after the T4c remediation

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any of this code. Re-derive verdicts from GROUND TRUTH (run it / read it). Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). A prior verification panel PASSED on the build + safety + most completeness, but found ONE gap (memo §6 "simulate permission denial"), which a remediation leg (T4c) just closed. Confirm the tree is green AND the gap is genuinely closed, with NO regression.

## Read FIRST
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-002/verify-completeness.md` — the FAIL that flagged the gap (CHECK 2 "Copy permission-denied variant MISSING").

## Checks (run/read each; record PASS/FAIL + evidence)
1. **Fresh sync + full suite:** `uv sync --all-groups` then `uv run pytest -q` (~30s; state estimate). Capture the EXACT summary line. PASS only if all-passed, ZERO failures (expect ~60 passed). Record the count.
2. **Gap closed — permission denial now simulated & proven:** open `tests/test_readers.py` and confirm there is a test that constructs `BrowserSession(channel="mock", ..., grant_clipboard=False)` and asserts the `CopyButtonReader` raises the NAMED `SelectorUnavailableError` (graceful, not a raw Playwright error). Confirm `src/ask_chatgpt/driver.py` grants clipboard perms on the mock context ONLY when `grant_clipboard` is true (default true). Quote the test name + the driver guard line. PASS/FAIL.
3. **DOM-primary robust under denial:** confirm a test shows `read_response` (DOM-primary default) still returns the correct latest text when `grant_clipboard=False`. PASS/FAIL.
4. **No regression on the safety boundary:** `grep -rn "chatgpt.com\|channel=\"real\"\|launch_persistent_context" tests/ scripts/` (ignore `.pyc`) — confirm still NO real-channel navigation/invocation in tests/scripts (only inert constant/stored-URL literals). PASS/FAIL.

## Deliverable — `orchestration/reports/M-002/verify-reverify.md`
- Header `LENS: reverify-after-T4c`.
- One line per check (1–4): `CHECK <n>: PASS|FAIL` + evidence (exact pytest summary; the test name + driver line; the grep judgment).
- `RV-VERDICT: PASS|FAIL`.
- Telemetry v2: `START_TIMESTAMP:`/`END_TIMESTAMP:` (`date -Iseconds`); `ESTIMATE: T9RV <min>m`.
- End with `RV-STATUS: DONE` (or `BLOCKED`) LAST. ≤120 lines.

## SAFETY BLOCK (verbatim)
- NEVER contact chatgpt.com/openai/any external service; loopback-only (the suite uses channel="mock"); the ONLY permitted external download is chromium (ALREADY CACHED) — download nothing; no new deps; no sudo/apt.
- Never read/store/log credentials/cookies/tokens/profile contents.
- Write ONLY your report inside `/home/abhmul/dev/ask-chatgpt`. Edit NO source/tests. Archive READ-ONLY. Never write `.claude/`/`.agents/`. `uv run` from repo root ONLY; never bare `python`; never the shared agent venv. NEVER `git push`/`git commit`.
