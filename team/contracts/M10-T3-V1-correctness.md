# M10-T3-V1 — Correctness & spec-conformance verifier (READ-ONLY)

**FIRST read `team/contracts/M10-common.md` (safety + ground truth) and
`team/evidence/handoffs/M10-T2-implement.md` (what was built).** You are an
INDEPENDENT verifier — do NOT trust the implementer's handoff; re-derive every claim
from the code on branch `fix/m10-light-read-scrape` (currently checked out at HEAD).
READ-ONLY: modify NO source/test file; write ONLY your handoff. OFFLINE.

Authoritative artifacts to reason over:
- `git diff main..HEAD -- src tests` (the change set).
- The changed files: `src/ask_chatgpt/{session.py,capture.py,channels/cdp.py}`,
  `tests/{test_capture.py,test_session_stubs.py}`.
- Baseline `uv run pytest` = 268; current = 275 (lead independently confirmed 275).

## Verify each behavior FROM THE CODE (cite file:line), CONFIRM or REFUTE:
1. **Light-tab acquire.** `TabPool.acquire(ref, *, render=True)` opens
   `conversation_url(ref)` when `render=True` and the light constant
   (`https://chatgpt.com/`) when `render=False`; pool entries are keyed by
   `(mode,url)` so a light tab and a `/c/<id>` tab never collide or mis-reuse.
2. **scrape only.** `Session.scrape` is the ONLY caller switched to `render=False`
   + ambient header mode. `ask` (`session.py:366`) and `loop` (`session.py:579`)
   still acquire the rendered `/c/<id>` tab and use the DEFAULT (exact) harvest.
3. **Default harvest unchanged (CRITICAL — M7b).** `acquire_backend_headers`
   default mode is the exact `/backend-api/conversation/<id>` matcher; the
   send/draft/completion path (`completion.py`, `_run_send_turn`) still uses it.
   The M7b draft-branch reload semantics are intact. Confirm nothing on the default
   path changed behavior.
4. **Ambient mode is header-aware.** The `ambient_backend` matcher accepts a
   same-origin `GET /backend-api/*` ONLY if it carries ALL 8
   `REQUIRED_CAPTURE_HEADERS`, and the `cdp.py:wait_for_request` change keeps
   scanning past header-deficient matches (does not return a deficient request
   early) — while STILL failing closed (timeout → `BackendAuthUnavailableError`)
   when no qualifying request appears. Verify the fail-closed path for the DEFAULT
   conversation mode was not weakened by the `wait_for_request` change.
5. **Retarget.** Before the conversation fetch, `x-openai-target-path` is set to the
   actual fetched path (`/backend-api/conversation/<id>`); `x-openai-target-route`
   is kept verbatim behind the documented seam (`retarget_headers`).
6. **Fetch origin.** Confirm the backend fetch still works from a non-`/c/<id>`
   page (same-origin resolution at `channels/cdp.py:327-336`); the light page does
   not break `fetch_in_page`.

## Required output (handoff)
Write **`team/evidence/handoffs/M10-T3-V1-correctness.md`** per the handoff protocol:
STATUS token; per-item CONFIRM/REFUTE with file:line evidence; any correctness
defect with severity (BLOCKING / MAJOR / MINOR) and the exact code location; an
explicit verdict on whether the DEFAULT (send/draft/completion) path is provably
unchanged. Do not run mutation tests (that is V2's job); you may run read-only
`uv run pytest` once if needed, but inspect, don't trust.
