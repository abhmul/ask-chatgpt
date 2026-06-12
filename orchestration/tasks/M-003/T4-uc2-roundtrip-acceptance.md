# T4 — WIRE the public UC2 surface + UC2 round-trip E2E (bundle out → mock edits → patch back → apply → diff matches) + `scripts/accept_uc2.sh`. SINGLE EDITOR.

You are an INDEPENDENT pi worker and the ONLY editor of this repo right now. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). M-002 (UC1) + M-003 T2 (bundle-out, `bundle.py`) + T3 (`patch.py` retrieve/validate/`apply_patch`) are DONE/committed. `docs/bundle-protocol.md` is the BINDING spec.

**Your slice: WIRE the public API per §10 (extend `ask_chatgpt(...)` for files + export `apply_patch`), prove the full UC2 ROUND-TRIP end-to-end against the mock, and write the `accept_uc2` acceptance script. Do NOT build the CLI (that is T5).**

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be all-green, ZERO failures (now includes T2 + T3 tests). If not, STOP and report BLOCKED with exact output — do not edit.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/docs/bundle-protocol.md` — BINDING. Implement **§10 (Public API surface)** EXACTLY: the `ask_chatgpt(...)` extended signature (UC1 `-> text` with NO files MUST be byte-for-byte behavior-preserved), the returned result/patch-handle type, the `apply_patch(bundle, root, *, dry_run=...) -> DiffSummary` export, and the `__init__` exports. Also re-read **§1 (lifecycle)** and **§3** (so the round-trip exercises BOTH the download-primary and fenced-fallback retrieval paths).
3. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/api.py` — the CURRENT `ask_chatgpt(...)` (UC1). Extend it; keep the no-files path identical. Reuse the driver/session/readers wiring already there.
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/bundle.py` (T2) + `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/patch.py` (T3) — the building blocks you compose. Do NOT reimplement; call them.
5. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/__init__.py` — the public export surface to extend per §10.
6. `/home/abhmul/dev/ask-chatgpt/scripts/accept_uc1.sh` + `/home/abhmul/dev/ask-chatgpt/scripts/accept_uc1.py` — the MODEL for your acceptance script (ephemeral port; raw artifacts to `tmp/accept-uc1-<ts>/`; `results.json`; nonzero exit on failure). Mirror its structure for UC2.
7. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` + `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_files.py` + `/home/abhmul/dev/ask-chatgpt/tests/conftest.py` — how to script the fixture to (a) accept the uploaded bundle and (b) RETURN a patch bundle via download_artifact AND via the fenced fallback, then assert.

## Scope
1. **Wire `api.py` (§10).** Extend `ask_chatgpt(...)` so a caller can pass files/dirs (per §10's exact param names) and get back the §10 result object (response text + a patch-bundle handle when GPT returned one). Compose: build bundle (T2) → upload (T2) → send the accompanying prompt → detect completion → retrieve patch bundle (T3) → return the handle. The UC1 no-files path is unchanged. Export `apply_patch` + the result/`DiffSummary` types from `__init__.py` per §10. Add no logic that belongs in `bundle.py`/`patch.py` — compose them.
2. **UC2 round-trip E2E test — `tests/test_uc2_roundtrip.py`** (TDD; write FIRST). The acceptance-defining test, channel="mock" / loopback ONLY, apply under `tmp/` ONLY:
   - Seed a small project tree (in `tmp/`). Call the public API to bundle it out to the mock.
   - Script the mock to "edit" and RETURN a patch bundle (changed-files-only: ≥1 modified + ≥1 added + ≥1 deleted). Do this for BOTH retrieval paths: one test via download-capture primary, one via fenced base64url fallback.
   - Retrieve → validate → `apply_patch(..., dry_run=False)` under the `tmp/` root.
   - **Assert the applied tree DIFF MATCHES the expected edit** (the modified file has new content, the added file exists with expected bytes, the deleted file is gone, untouched files unchanged). Also assert a `dry_run=True` pass writes nothing but reports the same DiffSummary.
3. **`scripts/accept_uc2.sh` + `scripts/accept_uc2.py`** (mirror accept_uc1): boots the mock on an EPHEMERAL port, runs the round-trip end-to-end, writes raw artifacts to `tmp/accept-uc2-<ts>/` (incl. a `results.json` with `overall` + per-step outcomes + the diff-match evidence), and EXITS NONZERO on any failure. It must inspect the applied tree (not just exit codes) to confirm diff-matches.
4. Full `uv run pytest -q` GREEN (all existing + new). Bound waits.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). ZERO new pip deps.
- PATCH APPLY SAFETY: validate the ENTIRE bundle before mutating ANY file; reject absolute paths, `..`, symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); the apply in tests targets `tmp/` ONLY. The round-trip must use `apply_patch`'s validated path (never `extract`/`extractall`).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real". Every test/script navigates ONLY to the loopback mock base_url.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- Python: `uv run <cmd>` from repo root ONLY; NEVER bare `python`/`pip`. `uv sync --all-groups` ALWAYS. Serialize pytest. Kill only processes your own run started. NEVER `git push`. Do NOT `git commit` (the manager commits). Do not break existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.
- End your report with `T4-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-003/T4-report.md`, ≤200 lines)
- FIRST content line: `ESTIMATE: T4 <minutes>m`.
- `date -Iseconds` at START and END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- Report: the extended `ask_chatgpt(...)` signature + result type + new exports; how the round-trip composes T2+T3; that BOTH retrieval paths (download + fenced) are covered; the exact `accept_uc2.sh` behavior + the `results.json` shape + how it proves diff-matches by inspection; the EXACT `uv run pytest -q` summary line; the `bash scripts/accept_uc2.sh` outcome + the `tmp/accept-uc2-<ts>/` path it produced; deviations; trust notes.
- LAST line: `T4-STATUS: DONE` (or `BLOCKED` + exact error + next action).

## Success criteria (all must hold)
- `ask_chatgpt(...)` extended per §10 with UC1 path preserved; `apply_patch`/result/`DiffSummary` exported per §10.
- `tests/test_uc2_roundtrip.py` proves bundle-out → patch-back → apply → **diff matches**, via BOTH download-primary and fenced-fallback; dry_run writes nothing.
- `scripts/accept_uc2.{sh,py}` exits 0 on success / nonzero on failure, writes raw artifacts to `tmp/accept-uc2-<ts>/`, and proves diff-matches by inspecting the applied tree.
- Full `uv run pytest -q` green; zero new deps; no credential/profile reads; no chatgpt.com contact.
- Report with telemetry + `T4-STATUS:` last. You did NOT git commit.
