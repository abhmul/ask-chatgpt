# T2a — VERIFY LENS: spec-conformance (independent NON-PRODUCER, read-only). Best-of-N panel member 1 of 5.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code, and you are NOT the evidence runner (T1) nor any other lens. You reason OVER the authoritative evidence set produced by T1 — you do **NOT** re-run the heavy suite or acceptance scripts (a second concurrent heavy runner would contend on the shared workspace). Re-derive every judgment from GROUND TRUTH = the committed source + the RAW T1 artifacts. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only: do NOT edit any source/tests/scripts/docs; do NOT git commit/push.

## Your dimension: SPEC-CONFORMANCE
Map EVERY obligation sentence of the README.md directive to CONCRETE evidence (file:line, test name, AND/OR acceptance-artifact line). Anything you cannot map = FAIL with the exact gap named. Do not accept a producer's claim — find the code/test/artifact yourself.

## Read FIRST (in order)
1. This contract in full.
2. `README.md` — the binding directive. The obligations to map (re-read the file; these are the spine):
   - **UC1:** `ask_chatgpt(prompt, session_identifier, model_settings...) -> text`; same `session_identifier` → same conversation (continuity); `model_settings` selects model/options where the UI allows; returns the assistant response text.
   - **UC2:** caller passes files/dirs → tool zips a bundle INCLUDING a catalogue/README for GPT (what's inside, how to respond) → GPT asked to return a PATCH bundle (changed files ONLY) → tool retrieves and CAN APPLY locally. Round-trip: bundle out → (mock) GPT edits → patch back → applied → diff matches expectation.
   - **UC3:** `ask-chatgpt` CLI wrapping the function (prompt, session, file args, output to stdout/file).
   - **Acceptance shape:** each UC has automated E2E acceptance vs a local mock ChatGPT (loopback; tests NEVER contact chatgpt.com/openai) + an operator-gated runbook half for the real site.
   - **Posture:** library-first (function is the product; CLI wraps it); operator owns credentials/profile/quota (tool never touches credentials); D-001 (docs/DECISIONS.md) governs channel layering; Python/uv; zero-dep bias.
3. T1 evidence index: `orchestration/reports/M-004/verify-run.md` + the raw artifacts it manifests under `tmp/verify-m004/` (esp. `accept_uc1_results.json`, `accept_uc2_results.json`, `accept_uc3_results.json`, `clone_pytest.txt`).
4. Source to cite: `src/ask_chatgpt/api.py` (the `ask_chatgpt` signature + `AskChatGPTResult`), `bundle.py` (catalogue README in bundle), `patch.py` (changed-files-only patch + apply), `cli.py` (CLI surface), `session_registry.py` (continuity). Tests: `tests/test_ask_chatgpt_uc1.py`, `tests/test_bundle_out.py`, `tests/test_uc2_roundtrip.py`, `tests/test_cli.py`.

## Method
- Build an OBLIGATION → EVIDENCE table. One row per obligation clause (decompose UC1/UC2/UC3/acceptance/posture into atomic clauses — aim for ~15–20 rows). Each row: `obligation clause | concrete evidence (file:line / test id / artifact line, quoted) | PASS|FAIL`.
- A clause is PASS only if you can point at code that implements it AND a test or acceptance artifact that exercises it. Signature-only with no test = note it as weak. Unmapped or contradicted = FAIL with the gap.
- Confirm the function signature literally matches `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` (read `api.py`); confirm the CLI literally wraps that function (read `cli.py`); confirm the bundle literally includes a catalogue README for GPT (read `bundle.py` + the round-trip artifact). Confirm patch bundles carry CHANGED FILES ONLY.
- Confirm continuity: same `session_identifier` returns to the same conversation — find the mechanism (`session_registry.py`) AND the test/artifact that proves a 2nd call with the same id reuses the conversation.
- Confirm "where the UI allows" for model_settings is honestly scoped (selection attempted via selector map; unavailable → a named error — cross-check, don't overclaim).

## Deliverable — `orchestration/reports/M-004/lens-spec.md` (≤200 lines)
- Header `LENS: spec-conformance`.
- The full OBLIGATION → EVIDENCE table.
- A short GAPS section: every clause you could NOT map, stated as an actionable defect.
- A line `T2a-VERDICT: PASS|FAIL` (FAIL if ANY obligation clause is unmapped or contradicted; name them).
- Telemetry v2: FIRST line `ESTIMATE: T2a <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:`.
- LAST line: `T2a-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything is loopback/local. The mock fixture binds loopback (127.0.0.1) ONLY. ZERO new pip deps. You run NOTHING heavy — you READ source + T1 artifacts. Do NOT re-run the full suite or acceptance scripts — T1 is the sole heavy runner.
- This mission MUTATES NOTHING except your one report. NEVER edit or "fix" any source/tests/docs/scripts — REPORT defects instead (independence boundary).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY if you must run anything read-only (you should not need to); never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T2a-STATUS: DONE|BLOCKED` as the LAST line.
