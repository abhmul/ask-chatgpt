# T9·V3 — INDEPENDENT completeness lens: deliverables + memo §6 fixture + README spec (no heavy re-run)

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any of this code. Re-derive every verdict by READING the source/tests/docs yourself + reasoning over the authoritative-run output. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Do NOT run the full `pytest` suite (another lens produced the authoritative run). Quick read-only `grep`/file reads only. Do NOT edit anything.

## Read FIRST
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/tasks/MISSION-002.md` — the Deliverables list (the checklist you verify is COMPLETE).
3. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/decision-memo.md` §6 — the BINDING fixture-affordance checklist; §7 — the runbook unknowns.
4. `/home/abhmul/dev/ask-chatgpt/README.md` — UC1 + acceptance shape.
5. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-002/verify-run.md` — the authoritative-run output (use its acceptance-artifact inspection as evidence).
6. To inspect: `src/ask_chatgpt/` (all modules), `src/ask_chatgpt/selector_maps/{mock,real}.json`, `tests/` (fixture + test files), `scripts/accept_uc1.{sh,py}`, `docs/runbooks/observe-chatgpt-unknowns.md`.

## Completeness checks (READ; record PASS/FAIL + evidence for each)
1. **Mission deliverables present:** (a) `pyproject.toml` + `src/ask_chatgpt/` package with: browser session controller (mock/real channel), selector-map loader (maps as JSON data), completion detector, ResponseReader interface + DomReader + CopyButtonReader, session registry (JSON, overridable path), model_settings selection, the named error types, public `ask_chatgpt()`. (b) `tests/` with the mock fixture. (c) network guard. (d) `scripts/accept_uc1.sh`. (e) `docs/runbooks/observe-chatgpt-unknowns.md`. List each with its path → PASS/FAIL.
2. **memo §6 fixture affordances ALL present** — map each to fixture code (`tests/fixtures/mock_chatgpt/server.py`) + a test: loopback+ephemeral+reset/inspect; conversations by stable ref + session reuse-vs-new; selector-map-compatible UI (ready root, chat list/items, new-chat, composer, send, model menu/options, upload); adversarial booby-trap/echo + latest-turn-only; copy button + clipboard (+ permission-denied/stale/wrong/missing/truncated variants); DOM fallback stable AND virtualized variants + completion/end markers; download artifact card serving a real zip w/ Content-Disposition (+ missing/delayed/wrong/corrupt/truncated/collision/unsupported); fenced base64 (BEGIN/END+manifest+bytecount+SHA256 + missing-end/bad-hash/changed+unchanged/oversized); upload `<input type=file>` (+ unsupported/size-type-reject/corrupt); honest failures (login/session-not-found/model-unavailable/upload-unsupported/download-unsupported/truncated/rate-limit/selector-unavailable). For EACH affordance: PRESENT/MISSING + evidence (selector key, mode name, or test). Flag any silent gap.
3. **Named error taxonomy complete:** `errors.py` has login/session-not-found/model-unavailable/response-truncated/selector-unavailable/upload-unsupported/download-unsupported (+rate-limit), each actionable. PASS/FAIL.
4. **Acceptance proves UC1:** from `verify-run.md`'s inspected `results.json`, continuity (same id → same conversation, both prompts) + model_settings + a honest-failure are demonstrated. PASS/FAIL.
5. **Observation runbook covers all 10 memo §7 unknowns**, operator-run/consent-gated, credential-safe, with an M-003-consumable results template. Count the sections. PASS/FAIL.
6. **Honest gaps / intended-incompleteness:** note anything deferred-by-design (e.g. `real.json` all-empty = INTENDED fail-closed template; bundle retrieval CODE is M-003, fixture affordances exist now). Distinguish INTENDED from accidental gaps. Flag any accidental gap as FAIL.

## Deliverable — `orchestration/reports/M-002/verify-completeness.md`
- Header `LENS: completeness-spec`.
- One block per check (1–6): `CHECK <n>: PASS|FAIL` + the evidence/mapping. For check 2, an explicit PRESENT/MISSING table of the memo §6 affordances.
- `V3-VERDICT: PASS|FAIL` (FAIL if any deliverable/affordance is accidentally missing).
- Telemetry v2: `START_TIMESTAMP:`/`END_TIMESTAMP:`; `ESTIMATE: T9V3 <min>m`.
- End with `V3-STATUS: DONE` (or `BLOCKED`) LAST. ≤170 lines.

## SAFETY BLOCK (verbatim)
- NEVER contact chatgpt.com/openai/any external service; do not run the real channel; download nothing; no new deps; no sudo/apt.
- Read-only: do NOT edit/format any source/test/doc. Never read/store/log credentials/cookies/tokens/profile contents.
- Write ONLY your report inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. `uv run` only if needed; never bare `python`; never the shared agent venv. NEVER `git push`/`git commit`.
