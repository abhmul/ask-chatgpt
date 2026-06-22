# M10-T3-V2 — Falsifiability / mutation verifier (mutates THEN restores)

**FIRST read `team/contracts/M10-common.md` and
`team/evidence/handoffs/M10-T2-implement.md`.** You are an INDEPENDENT verifier on
branch `fix/m10-light-read-scrape` (HEAD). Your job: prove the 7 new tests are
genuinely FALSIFIABLE (they fail when the behavior they assert is broken) and not
circular/self-fulfilling. OFFLINE. You run alone — no other worker is editing now.

## Method — mutation testing (do this carefully and RESTORE every time)
For EACH new test, identify the specific production line(s) it targets, apply a
MINIMAL mutation that reverts/breaks that behavior, run ONLY that test, and confirm
it FAILS. Then immediately restore the pristine file with
`git checkout -- <path>` (verify `git status` is clean before the next mutation).
NEVER commit a mutation; NEVER leave the tree dirty; NEVER push.

The 7 tests (in `tests/test_capture.py` and `tests/test_session_stubs.py`):
1. `test_scrape_uses_light_root_and_generic_backend_header_harvest` — mutate
   `scrape` back to `render=True` (or default harvest) → must fail.
2. `test_ambient_backend_header_harvest_skips_deficient_requests` — mutate the
   ambient matcher to accept the first match regardless of headers → must fail.
3. `test_conversation_harvest_default_ignores_generic_backend_requests` — mutate the
   default mode to ambient → must fail. (This guards the M7b/send/draft path.)
4. `test_conversation_fetch_retargets_harvested_target_path` — mutate
   `retarget_headers` to pass `x-openai-target-path` verbatim → must fail.
5. `test_light_and_render_pool_keys_do_not_collide` — mutate pool keying back to
   URL-only → must fail.
6. `test_history_and_fetch_remain_tab_free_local_reads` — confirm it would fail if
   history/fetch acquired a tab (reason about it; mutate if feasible).
7. `test_ask_and_loop_keep_render_conversation_tabs` — mutate `ask`/`loop` to
   `render=False` → must fail.

## Also check (per the falsifiability + absence-of-assertion lessons)
- Is any test CIRCULAR (asserts something the test setup itself guarantees, e.g.
  the mock is configured so the assertion can't fail)? Inspect the mock scenarios.
- Does test #3 genuinely pin that the DEFAULT (send/draft/completion) harvest still
  requires the exact `/backend-api/conversation/<id>` request end-to-end — or only a
  shallow surface? Hunt for an ABSENCE of assertion (an M8 lesson: a stub once
  passed because nothing pinned it).
- Independently run the FULL `uv run pytest` and report the exact summary line.

## Required output (handoff) — restore the tree FIRST
Before writing your handoff, ensure `git status` shows a clean tree (no leftover
mutations) and `git rev-parse HEAD` is unchanged. Write
**`team/evidence/handoffs/M10-T3-V2-falsifiability.md`** per the handoff protocol:
STATUS token; a table of each test → mutation applied → observed result
(FAILED-as-expected / DID-NOT-FAIL) → restored? (yes); any non-falsifiable/circular
test flagged with severity; the final full-suite summary line; and an explicit
"tree restored clean" confirmation with `git status --porcelain` output.
