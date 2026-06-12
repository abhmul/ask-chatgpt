# T9·V2 — INDEPENDENT conformance lens: D-001 + safety + adversarial (SOURCE review, no heavy re-run)

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any of this code. Re-derive every verdict by READING the source/tests yourself. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Do NOT run the full `pytest` suite (another lens already produced the authoritative run); you reason over that output + the source. You MAY run quick read-only `grep` and open files. Do NOT edit anything.

## Read FIRST
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001 (THE spec you check conformance against).
3. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-002/verify-run.md` — the authoritative-run lens output (the pytest result + acceptance inspection). Treat its numeric results as the build state; your job is the CONFORMANCE/SAFETY judgment by reading source.
4. Source to inspect: `src/ask_chatgpt/readers.py`, `driver.py`, `selector_map.py`, `errors.py`, `selector_maps/mock.json`, `selector_maps/real.json`, `tests/conftest.py`, `tests/test_readers.py`, `tests/test_network_guard.py`, `tests/test_driver.py`.

## Conformance checks (READ source; record PASS/FAIL + the exact file:line evidence for each)
1. **DOM-primary default (D-001 #1):** `readers.py` default order is `(DomReader(), CopyButtonReader())` (DOM first), and order is configurable. Evidence: the default-order constant.
2. **One ResponseReader interface, both behind it:** `DomReader` and `CopyButtonReader` both implement the same `ResponseReader.read(...)`.
3. **Bounded latest-turn only / NO history sweep:** `DomReader` reads `message_body` WITHIN the supplied turn locator only; no transcript-wide scrape. Confirm there is no scan of all assistant turns for text extraction.
4. **Fail-closed selectors:** `selector_map.py` raises `SelectorUnavailableError` for absent/empty/whitespace keys and NEVER falls back to another channel; `real.json` is all-empty so the real channel fails closed. Evidence: the `selector()`/`attribute()` guards + a spot-check that `real.json` values are `""`.
5. **Adversarial: booby-trap never returned:** `tests/test_readers.py` asserts the sentinel is NOT in the returned text, across stable AND virtualized layouts, for BOTH readers, AND for the default composite with `copy_mode=wrong`. Quote the asserting lines.
6. **Real channel built but NEVER tested:** `chatgpt.com`/`launch_persistent_context`/`user_data_dir` appear only in `src/` (driver), never invoked by any test; `profile_path` is treated as an OPAQUE directory — the driver never opens/reads/lists/logs its contents. Grep + read to confirm.
7. **No credential/cookie/token/profile reads anywhere:** grep `src/` + `tests/` for any reading of cookies/tokens/credentials/profile contents → none. The tool never stores or logs such material.
8. **Loopback-only enforcement:** `tests/conftest.py` has an AUTOUSE socket guard blocking non-loopback; the mock server binds 127.0.0.1 ephemeral; `BrowserSession` mock path guards that `base_url` is loopback. Evidence: the guard + the loopback assertion.
9. **Fail-closed not masked:** `read_response` falls through to the fallback ONLY on `SelectorUnavailableError` and PROPAGATES other named errors (e.g. `ResponseTruncatedError`). Evidence: the composite's except clause.

## Deliverable — `orchestration/reports/M-002/verify-d001-safety.md`
- Header `LENS: d001-safety-adversarial`.
- One line per check (1–9): `CHECK <n>: PASS|FAIL` + `file:line` evidence (quote the key line).
- `V2-VERDICT: PASS|FAIL` (FAIL if any conformance/safety check fails).
- Telemetry v2: `START_TIMESTAMP:`/`END_TIMESTAMP:` (from `date -Iseconds`); `ESTIMATE: T9V2 <min>m`.
- End with `V2-STATUS: DONE` (or `BLOCKED`) LAST. ≤150 lines.

## SAFETY BLOCK (verbatim)
- NEVER contact chatgpt.com/openai/any external service; do not run the real channel; download nothing; no new deps; no sudo/apt.
- Read-only review: do NOT edit/format any source or test. Never read/store/log credentials/cookies/tokens/profile contents.
- Write ONLY your report inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. `uv run` only if needed; never bare `python`; never the shared agent venv. NEVER `git push`/`git commit`.
