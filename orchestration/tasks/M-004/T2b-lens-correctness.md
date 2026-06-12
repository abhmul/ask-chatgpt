# T2b — VERIFY LENS: correctness / reproduction (independent NON-PRODUCER, read-only). Best-of-N panel member 2 of 5.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code, and you are NOT the evidence runner (T1) nor any other lens. You reason OVER the authoritative evidence set produced by T1 — you do **NOT** re-run the heavy suite or acceptance scripts. Re-derive every judgment from GROUND TRUTH = the RAW T1 artifacts + the committed source. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only.

## Your dimension: CORRECTNESS / REPRODUCTION
Three questions, answered from ground truth:
1. **Did the CLEAN CLONE actually reproduce GREEN from committed state alone?** (i.e. committed HEAD, fresh `.venv`, no dirty-tree dependency.)
2. **Are the acceptance artifacts INTERNALLY CONSISTENT?** (UC1 continuity evidence really shows the same conversation reused; UC2 `diff_match`/round-trip evidence really shows the applied tree matches expectation; UC3 really shows stdout + `--out` write + dry-run-no-mutation.)
3. **Are the key tests NON-VACUOUS?** (Sample ~8 tests across UC1/UC2/UC3; would each actually FAIL if the behavior broke — real assertions on real outputs, not `assert True` / mocked-away tautologies?)

## Read FIRST (in order)
1. This contract in full.
2. T1 evidence: `orchestration/reports/M-004/verify-run.md`, then the raw artifacts:
   - `tmp/verify-m004/git_state.txt` + `clone_setup.txt` (clone HEAD == main HEAD?), `clone_sync.txt` (INITIAL offline-blocked attempt) AND `clone_sync_RECOVERY.txt` (the successful network-allowed venv rebuild — read this), `clone_pytest.txt` (EXACT summary line + any failing ids).
   - `tmp/verify-m004/accept_uc1_results.json`, `accept_uc2_results.json`, `accept_uc3_results.json` (open and inspect every field).
3. Tests to sample for non-vacuousness (read the bodies; pick ~8 spanning all three UCs): `tests/test_ask_chatgpt_uc1.py`, `tests/test_session_registry.py`, `tests/test_uc2_roundtrip.py`, `tests/test_patch.py`, `tests/test_bundle_out.py`, `tests/test_cli.py`, `tests/test_readers.py`, `tests/test_errors.py`. Also `scripts/accept_uc1.py`, `accept_uc2.py`, `accept_uc3.py` (what they actually assert).

## Method / Checks (each: PASS|FAIL + the raw-evidence quote)
1. **Clean-clone green:** From `clone_pytest.txt`, quote the EXACT summary line and confirm ZERO failures/errors. From `clone_setup.txt`/`git_state.txt`, confirm the cloned HEAD equals the main-repo HEAD (so the green result is from committed state, not a dirty tree). **Venv-build note (do NOT mis-FAIL on this):** `clone_sync.txt` shows an INITIAL `uv sync` run with `UV_OFFLINE=1` that FAILED on a `greenlet` cache miss — that was an over-strict offline setting, NOT a code defect. The manager then rebuilt the clone venv with a normal network-allowed `uv sync --all-groups` — read `clone_sync_RECOVERY.txt` (11 packages resolved, greenlet fetched from PyPI, project built EDITABLE from the clone's own `src/`, validated import resolves under `tmp/verify-m004/clone/src`). Fetching pinned deps from PyPI is permitted (only chatgpt.com/openai is forbidden). Confirm from `clone_sync_RECOVERY.txt` that the network-allowed sync succeeded and that the `clone_pytest.txt` green run used this clone venv. FAIL **only** if the clone did not reproduce green, or if the HEADs differ — do NOT FAIL merely because the initial offline attempt failed (note it as an env/harness issue with REWORK-CAUSE env-drift if you wish, but it does not block reproduction).
2. **UC1 artifact consistency:** Open `accept_uc1_results.json`; confirm `overall == pass` AND that the continuity evidence concretely shows a 2nd call with the SAME session identifier returned to the SAME conversation (quote the fields — e.g. conversation ref/turn ids reused, not a fresh chat). FAIL if `overall != pass` or continuity is asserted but not evidenced.
3. **UC2 round-trip diff-match:** Open `accept_uc2_results.json`; confirm `overall == pass` AND the applied-tree evidence shows the modified file changed as expected, the added file present, the deleted file gone (quote the diff-match fields). If the artifact distinguishes download-primary vs fenced-fallback retrieval, confirm BOTH round-tripped. FAIL if the diff does not match expectation in the artifact itself (exit code alone is NOT sufficient).
4. **UC3 artifact consistency:** Open `accept_uc3_results.json`; confirm `overall == pass` and that it evidences (a) prompt→stdout, (b) `--out` file write, (c) `--files … --dry-run` summary WITHOUT mutation. Quote each.
5. **Non-vacuousness (sample ~8 tests):** For each sampled test, state in one line WHAT concrete output it asserts and HOW it would fail if the behavior regressed (e.g. "asserts the applied file bytes equal the patched bytes — would fail if apply were a no-op"). Flag any test that is tautological, asserts nothing meaningful, or mocks away the very behavior it claims to test. FAIL if a load-bearing UC behavior is only "covered" by a vacuous test.

## Deliverable — `orchestration/reports/M-004/lens-correctness.md` (≤200 lines)
- Header `LENS: correctness/reproduction`.
- One `CHECK <n>: PASS|FAIL` section each (1–5), with the raw-evidence quote.
- A NON-VACUOUSNESS table: the ~8 sampled tests → one-line "fails-if-broken" rationale → vacuous? (yes/no).
- A line `T2b-VERDICT: PASS|FAIL` (FAIL if the clone did not reproduce green, any artifact is inconsistent, or a load-bearing behavior is only vacuously tested).
- Telemetry v2: FIRST line `ESTIMATE: T2b <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:`.
- LAST line: `T2b-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything is loopback/local. ZERO new pip deps. You run NOTHING heavy — you READ artifacts + source. Do NOT re-run the full suite or acceptance scripts — T1 is the sole heavy runner.
- This mission MUTATES NOTHING except your one report. NEVER edit or "fix" any source/tests/docs/scripts — REPORT defects instead (independence boundary).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY if strictly needed (you should not need to); never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T2b-STATUS: DONE|BLOCKED` as the LAST line.
