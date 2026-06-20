# M-008a / T5 Lens A — correctness / reproduction (independent non-producer). READ-ONLY.

You are a pi (GPT-5.5) worker acting as an INDEPENDENT non-producer verifier. You inherit NOTHING except this file and what you read. You did NOT produce this code; verify it from ground truth, do not rubber-stamp.

## Rules (MANDATORY)
- Repo root: `/home/abhmul/dev/ask-chatgpt`. Use `uv run` from repo root for any python; NEVER bare `python`/`python3`; NEVER touch `~/.local/share/agent-python/.venv`.
- **READ-ONLY:** do NOT edit/commit/checkout/stash any file. Do NOT set `ASK_CHATGPT_REAL`. Do NOT touch `127.0.0.1:9222`.
- **Do NOT re-run the full `uv run pytest`** — it was already run authoritatively; read the captured output at `orchestration/reports/M-008a/authoritative-pytest.txt`. You MAY read/grep source + tests and run at most tiny targeted greps. Reason from ground truth.

## Context
M-008a (mock/build half, NO real site) made three changes, committed: `87a0ee8` (T1: harden `BrowserSession.wait_for_completion` real/cdp branch so a mid-stream micro-pause no longer returns a clipped turn; progress-aware timeout), `c71c96a` (T2: rewrote bundle prompt to ask for a downloadable `.zip`, base64=parser-only), `484cacf` (T3: falsifiable continuity + truncation harness on the mock).

## Your lens — correctness / reproduction. Verify each, independently:
1. **Authoritative suite green:** read `orchestration/reports/M-008a/authoritative-pytest.txt`. Confirm it ends `206 passed, 1 deselected` with `ASK_CHATGPT_REAL=<unset>`, and that ZERO `real_site` tests were collected (the `1 deselected` is the gated real_site test). Confirm the count is the prior baseline (198) + the mission's new tests (8).
2. **New tests are NON-VACUOUS:** read the new/changed tests — in `tests/test_driver.py` the `wait_for_completion` real/cdp tests (the micro-pause / completion-marker / optional-affordance / progress-extension / fail-closed-timeout cases, ~lines 808-884), `tests/test_bundle_out.py` the downloadable-zip guard test, `tests/test_continuity_mock.py` (all three functions). For each, confirm the assertions are meaningful (would fail if the behavior regressed) and not trivially true.
3. **The truncation test genuinely fails pre-fix (show the RED):** read `orchestration/reports/M-008a/T1-worker-report.md`. Confirm it contains a captured pre-fix failure where the real `wait_for_completion` returned a CLIPPED body (≈5359 chars) MISSING the terminal sentinel `__TURN_COMPLETE_…`, i.e. the completeness assertion genuinely failed on the unfixed code. Confirm the test drives the REAL method (not a reimplementation). Do NOT re-run pre-fix code (git checkout is blocked); reason from the captured RED + the test source.
4. Spot-check that the T1 fix removed the `text_stable`-alone return path (read `src/ask_chatgpt/driver.py` `wait_for_completion`): completion now requires `not streaming_visible and completion_visible`; pure text stability cannot return.

## Deliverable — write `orchestration/reports/M-008a/T5-lensA.md`:
- A short evidence table (claim → file:line / artifact line → PASS/FAIL).
- Any defects (be specific) or "none".
- Final line exactly: `VERDICT: PASS` (or `PARTIAL` / `FAIL`) with a one-clause reason.
Do NOT edit code. Stop when the report is written.
