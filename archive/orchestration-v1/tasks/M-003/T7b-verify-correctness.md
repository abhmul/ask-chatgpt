# T7b — VERIFY LENS: correctness / reproduction (independent NON-PRODUCER, read-only). Best-of-N panel member #1 of 3.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any M-003 code. You reason OVER the authoritative evidence set produced by T7a — you do **NOT** re-run the heavy suite or acceptance scripts (a second concurrent heavy runner would contend on the shared workspace). Re-derive every judgment from GROUND TRUTH = the RAW artifact files + the source code, NEVER a prior report's claim or an exit code alone. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only: do NOT edit any source/tests/scripts; do NOT git commit/push.

## Your dimension: CORRECTNESS & REPRODUCTION
Two questions only:
1. **Reproduction:** Do T7a's PASS verdicts actually follow from the RAW evidence files? Open the raw files yourself and confirm — do not trust `verify-run.md`'s summary.
2. **Correctness:** Does the implementation logic actually do what the tests claim, and do the tests assert something MEANINGFUL (not vacuous/tautological)? Spot logic errors the green suite could still hide.

## Read FIRST (in order)
1. This contract in full.
2. `orchestration/reports/M-003/verify-run.md` — T7a's summary (provisional; you must re-derive its verdicts from the raw files below).
3. The RAW evidence in `tmp/verify-m003/`: `pytest.txt` (the FULL suite output), `accept_uc1.txt`, `accept_uc2.txt`, `accept_uc3.txt`, `zipslip.txt`, `netguard.txt`, `grep_realsite.txt`, `sync.txt`. Also open the newest `tmp/accept-uc2-*/results.json` and `tmp/accept-uc3-*/results.json` directly.
4. The code under test: `src/ask_chatgpt/patch.py` (retrieval decision tree + `apply_patch` validation order + `DiffSummary`), `src/ask_chatgpt/bundle.py` (build/upload), `src/ask_chatgpt/api.py` (`ask_chatgpt` wiring → `AskChatGPTResult`), `src/ask_chatgpt/cli.py`.
5. The tests: `tests/test_patch.py`, `tests/test_uc2_roundtrip.py`, `tests/test_cli.py`, `tests/test_bundle_out.py`.

## REALIZED FACTS (verify these against ground truth — do not assume)
- Full suite expected: `119 passed` (T2..T5 + UC1 regression). If `pytest.txt` shows any other count or ANY failure/error, that is a FAIL — record the exact summary line and failing ids.
- Public surface: `ask_chatgpt(prompt, *, session_identifier, model_settings, channel, base_url, profile_path, registry, reader_order, timeout_s, files=None, dirs=None, bundle_root=None) -> str | AskChatGPTResult{text, patch_bundle}`; `apply_patch(bundle, root, *, dry_run=True) -> DiffSummary`; retrieval `retrieve_patch_bundle(...)` (download-primary + fenced-fallback).

## Checks (each: PASS|FAIL + cite the exact file + line/quote you derived it from)
1. **Suite reproduction:** Open `tmp/verify-m003/pytest.txt`. Quote the EXACT summary line. Confirm zero failures/errors and the count. FAIL on any discrepancy with `verify-run.md`.
2. **Round-trip diff-match reproduction:** Open the newest `tmp/accept-uc2-*/results.json`. Confirm `overall=="pass"` AND that `diff_match_evidence` shows, per file, a MODIFIED file with changed content, an ADDED file present, a DELETED file gone, and an untouched file unchanged — for BOTH the download-primary and fenced-fallback steps. Quote the evidence. A green exit without this evidence = FAIL.
3. **UC3 reproduction:** Open the newest `tmp/accept-uc3-*/results.json`. Confirm `overall=="pass"` with a prompt→stdout step, an `--out` file-write step, and a `--files … --dry-run` diff-summary-WITHOUT-mutation step. Quote it.
4. **Retrieval logic correctness:** Read `retrieve_patch_bundle` in `patch.py`. Confirm: download-primary is chosen ONLY for a single current-turn artifact with matching turn id, valid byte-count/SHA, safe basename; ambiguous/stale/missing → the documented fallback or named error (not a silent wrong choice); fenced fallback requires exactly one complete BEGIN/END block and validates byte-count+SHA before decode. Flag any path that could pick a WRONG or STALE bundle.
5. **Apply ordering correctness:** Read `apply_patch` in `patch.py`. Confirm validate-EVERYTHING-before-mutate: all manifest/hash/byte/path checks happen BEFORE any filesystem write, `dry_run=True` returns a `DiffSummary` without writing, and a LATE validation failure (e.g. 2nd file SHA mismatch) leaves the root byte-for-byte unchanged. Cross-check against `tests/test_patch.py::test_late_validation_failure...`.
6. **Tests are meaningful (anti-vacuous):** Sample ≥4 critical tests (round-trip diff-match, late-validation-failure, dry-run-writes-nothing, a CLI no-mutate test). Confirm each asserts a SUBSTANTIVE post-condition (real content/absence/exception), not a tautology or an assertion that would pass even if the feature were broken. Name any weak/vacuous test you find.

## Deliverable — `orchestration/reports/M-003/verify-correctness.md` (≤180 lines)
- Header `LENS: correctness-reproduction`.
- One `CHECK <n>: PASS|FAIL` section each, with the exact quote/cite you derived it from.
- A line `V-CORRECTNESS-VERDICT: PASS|FAIL` (FAIL if ANY check failed or any non-trivial correctness doubt remains; explain).
- Telemetry v2: FIRST line `ESTIMATE: T7b <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:`/`END_TIMESTAMP:`.
- LAST line: `T7b-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. ZERO new pip deps. You run NOTHING heavy — you READ artifacts + source. (If you must spot-run one tiny check, it is loopback-only; but do NOT re-run the full suite or the acceptance scripts — T7a is the sole heavy runner.)
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report only). Do NOT edit any source/tests/scripts. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY; never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T7b-STATUS: DONE|BLOCKED` as the LAST line.
