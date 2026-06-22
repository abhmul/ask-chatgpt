# M10-T3b — Harden the send/draft exact-harvest guard (one test, OFFLINE)

**FIRST read `team/contracts/M10-common.md` (safety + ground truth) and
`team/evidence/handoffs/M10-T2-implement.md` (what was built).** You are on branch
`fix/m10-light-read-scrape` (HEAD `8f42496`). OFFLINE, single editor.

## Why
The M10 fix added an opt-in `ambient_backend` header-harvest mode used ONLY by
`scrape`; the send/draft/completion path MUST keep the exact `conversation` harvest
(this is the load-bearing M7b property — a fresh/draft chat needs the exact
`/backend-api/conversation/<id>` request observed). The existing test
`test_conversation_harvest_default_ignores_generic_backend_requests` only pins this
at the `acquire_backend_headers` UNIT level. A regression that instead changed
`capture_conversation`'s default, or made `_run_send_turn` pass
`header_mode="ambient_backend"`, would EVADE that unit test (flagged MEDIUM by the
M10-T3-V2 falsifiability verifier).

## Task — add ONE integration-level guard test (TDD)
Add a test (in `tests/test_session_stubs.py` or `tests/test_capture.py`, wherever
the send/draft mock harness already lives — match existing patterns) that drives the
SEND/DRAFT capture path end-to-end through the mock channel and proves it uses the
EXACT conversation harvest, NOT ambient. Design it so it FAILS if `_run_send_turn`
(or the send-final `capture_conversation` call) were switched to
`header_mode="ambient_backend"` or if `capture_conversation`'s default mode changed.

Recommended shape (adapt to the real mock API): configure the mock so the page
exposes BOTH (a) a generic `GET /backend-api/*` request carrying all 8 required
headers with a DISTINGUISHABLE auth value (e.g. `Bearer MOCK_GENERIC`), and (b) the
exact `GET /backend-api/conversation/<id>` request with a DIFFERENT auth value
(e.g. `Bearer MOCK_EXACT`). Drive a send (`session.ask(...)`) and assert the
harvested/used auth came from the EXACT conversation request — so an ambient switch
(which would pick the generic request) fails the test.

**Verify it is genuinely falsifiable yourself:** temporarily switch the send path to
ambient, confirm your new test FAILS, then restore. Do not leave that mutation.

## Constraints
- Change ONLY test files (no production change is needed — the code is already
  correct; this is test hardening). If you believe a production change is required,
  STOP and write a BLOCKED handoff explaining why instead of editing source.
- End with full `uv run pytest` green: expect **276 passed** (275 + your 1 test).
  Inspect the summary line, not the exit code.
- Commit ONLY your test change + handoff to the branch (`git add tests
  team/evidence/handoffs/M10-T3b-harden-sendpath-guard.md`; never `git add -A`). Do
  NOT stage the unrelated dirty/untracked files (`issues/…`, `human/`,
  `controller.mjs`, `uv.lock`, `team/state/…`, other `team/contracts/…`). Do NOT
  push/merge, do NOT touch `stable`, do NOT `uv tool install/upgrade/reinstall`.

## Deliverable + handoff
Write **`team/evidence/handoffs/M10-T3b-harden-sendpath-guard.md`**: STATUS token;
the new test name + what it falsifies; your own falsifiability check result
(mutation → FAILED-as-expected → restored); the final `uv run pytest` summary line;
the commit hash.
