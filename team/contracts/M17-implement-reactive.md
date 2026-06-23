# M17 mission — implement reactive-traffic fixes C-1 + C-4 + minor (single-editor TDD, OFFLINE)

> Read `team/contracts/M17-common.md` IN FULL first (role, scope, OFFLINE rule, git/leak/TDD discipline, dispatch, handoff), then `team/evidence/handoffs/M16-triage-reactive-traffic.md` IN FULL (the locked design). This file gives the SEQUENCE. The operator greenlit "full reactive fix (TDD): build C-1 + C-4 + minor OFFLINE now; C-2 is gated on a later attended probe and is OUT OF SCOPE."

## Sequence (do in order; gate with `uv run pytest` + commit between)
0. `git switch -c feat/reactive-traffic-m17 main`; confirm branch + green baseline (`uv run pytest`, record the summary line).
1. **EDITOR-A (minor fix)** → blocks to completion → gate → commit.
2. **EDITOR-B (C-1 reload-split)** → blocks to completion → gate → commit.
3. **EDITOR-C (C-4 governor + 429 + jitter)** → blocks to completion → gate → commit.
4. **VERIFICATION PANEL (best-of-N=4, non-editing, parallel)** over ONE authoritative `uv run pytest` + the branch diff → you adjudicate severity → handoff.
Each editor prompt = read `team/contracts/M17-common.md` IN FULL + `team/evidence/handoffs/M16-triage-reactive-traffic.md` (its cited section) + the named source/tests; follow TDD (failing test first, confirm it fails, implement, confirm green); run full `uv run pytest`; report files changed + the summary line + the falsifiability proof. Transcribe leak + OFFLINE + git-branch + header-harvest rules into every prompt (children inherit nothing).

---

## EDITOR-A — MINOR `--max-total-wait` salvage (M16 §7)
- Read `issues/2026-06-22-max-total-wait-skips-out-salvage.md`, `cli.py:14,88-103,334-345`, `errors.py` (the `CompletionTimeoutError`/`MaxTotalWaitExceededError` sibling classes + `exit_code`), `completion.py:156` (`_attach_partials`), and the existing test `tests/test_cli.py:793` (`test_cli_completion_timeout_prints_salvage_to_stdout_and_out_before_error`, fake-session raise at ~`:108-113`).
- **TDD:** first add `tests/test_cli.py::test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error` mirroring the timeout test but raising `MaxTotalWaitExceededError` with an attached partial + `--out FILE`; assert partial on **stdout AND in FILE** + exit **51**. Confirm it **FAILS on current code** (partial dropped today). Then fix: add `MaxTotalWaitExceededError` to the `cli.py:14` import and widen `cli.py:92` to `except (CompletionTimeoutError, MaxTotalWaitExceededError) as exc:` (`exc.exit_code` preserves 50 vs 51). Confirm green.
- **Gotcha (note, don't fix):** salvage fires only for `ask`; `loop` also takes `--max-total-wait` (`cli.py:175`) but only handles `KeyboardInterrupt` partials — flag the asymmetry in your report, leave it out of scope.
- Deliverable: the 2-line fix + 1 passing falsifiable test; report failed-before/passes-after.

## EDITOR-B — C-1 persistent-tab reload-split (M16 §3 C-1 + the header-harvest caveat in M17-common)
- Read M16 §3 C-1 + §5 (the `reload==0` and header-harvest tests), `send.py:48-63` (`wait_for_idle_and_reload_if_needed`), `session.py:387-480` (`_run_send_turn`), `session.py:404,453-456` (the send + draft reload sites), `capture.py:154-190,943-947` (header harvest + conversation matcher), `tests/test_session_draft_loop.py:270-292,511` (existing reload/capture pins + the loop test), and `MockChannel` reload/open_tab counters (`mock.py` ~`:244,285,302`).
- **TDD (tests first, must fail on pre-change code):**
  - *No per-turn reload:* over a ≥2-turn persisted `loop`, assert `open_tab == 1` AND `reload == 0` (steady-state). This FAILS on current code (`session.py:404`→`send.py:54-56` reloads every send). Extend `tests/test_session_draft_loop.py`.
  - *Header-harvest survives:* an offline multi-turn `loop` capture asserting the 8 `REQUIRED_CAPTURE_HEADERS` are still harvested (`capture.py:39-48,154-190`) after the reload-split. Extend `tests/test_session_draft_loop.py`/`tests/test_capture.py`.
- **Implement:** split "wait until idle" from "reload" — reload only when actually mid-generation / on a real staleness signal, NOT unconditionally on every idle send. **Preserve header-harvest** per the M17-common hard caveat: keep a draft/capture-time reload where harvest needs it (do NOT blindly delete `session.py:455`); document exactly which reloads you removed vs kept. Do NOT break the existing draft/new-conversation capture pins (`tests/test_session_draft_loop.py:270-292`).
- Deliverable: the reload-split + both tests green + the full suite green; a precise reload-accounting note (removed vs kept-for-harvest).

## EDITOR-C — C-4 rate governor + 429 fail-soft + jitter (M16 §6)
- Read M16 §6 IN FULL + `session.py:139-230,300-330,387-480` (`AdaptiveSendBudget`, `submission()`, `_run_send_turn`), `store.py:48,371-390` (`resolve_data_dir`, `emit_payload`, the `fcntl.flock` pattern), `errors.py:212-223` + `cli.py:29-49` (`_ERROR_EXIT_BY_CODE`; confirm **52** is free), `completion.py:47,54-58,160-164` (completion fetch + the swallowed-error set), `capture.py:205-216,358-360,936-938` (capture fetch + fallback), and the request chokepoints listed in M16 §6.
- **TDD (tests first, must fail):**
  - *Governor throttles:* fake-clock test asserting the `60/rate` (and `Retry-After`) sleep on a page-load/fetch/send reservation. New `tests/test_rate_governor.py` (or extend `tests/test_send_budget.py`).
  - *429 → distinct exit + Retry-After, no clipboard fallback:* script a 429 (with `retry-after`) at the completion fetch and the capture fetch; assert the new `RateLimitedError` / exit **52** + parsed `retry_after_s` + that it does NOT take the clipboard/fallback path (not exit 21/41). Extend `tests/test_capture.py`, `tests/test_send_completion.py`, `tests/test_cli.py`, `tests/test_errors.py`.
- **Implement (M16 §6):** a **file-lock token-bucket governor** in a shared dir (default under `Store.resolve_data_dir()`, reuse `fcntl.flock`), state = non-secret ops only (tokens, refill epoch, `blocked_until`, last-rate-limited, redacted action/path-kind); `acquire(cost, action, path_kind)` refills/debits/sleeps/raises. Add `RateLimitedError` to `errors.py` (exit 52, `retryable=True`) + the CLI table (plain error path, NO clipboard salvage). Detect 429 BEFORE `BackendCaptureShapeError`/fallback (in `poll_backend_completion` and at the capture fetch boundary; do NOT add it to the swallowed set). Parse only `Retry-After` seconds; never log raw header values. Wire `record_soft_signal('rate_limited')` + shared `blocked_until` from a new `except RateLimitedError` in `_run_send_turn`. Add **jitter** (injectable RNG, one-sided extra delay) to `_required_spacing_s`/`_sleep_until_spacing_allows_submit` (`session.py:220-229`).
- **CEILING IS OPERATOR-OWNED (M16 §6, memory `verify-inherited-resource-claims`):** do NOT hard-code a guessed account rate ceiling as a real limit. Make `C_account`, reserves, per-action token weights, and margin **configurable with conservative, clearly-labeled DEFAULTS** (and a code comment that the real ceiling must be operator-confirmed/measured, not assumed). The governor mechanism is the deliverable; the exact numbers are tunable config, not a hard-coded fact.
- Deliverable: the governor module + 429 path + jitter + tests green + full suite green.

## VERIFICATION PANEL (best-of-N=4, non-editing, parallel) → `team/evidence/handoffs/M17/verify-{correctness,falsifiability,safety,reqcount}.md`
After EDITOR-C's gate, run ONE authoritative `uv run pytest` yourself (record the summary). Then launch 4 parallel non-editing pi lenses (`--tools read,grep,find,ls,bash`, `--wait-seconds 0`, poll) over that output + `git diff main...feat/reactive-traffic-m17`:
- **Correctness:** do C-1/C-4/minor do what M16 §3/§6/§7 specify? Any broken existing behavior (draft capture, completion salvage, send verify)?
- **Falsifiability:** does each NEW test actually fail without its change (re-derive)? Did any editor weaken/delete an existing assertion to go green? Hunt absence-of-assertion (stubs that pass because nothing pins them).
- **Safety/leak-regression:** any secret/header-value/conversation-content logged or hard-coded? Any real-site/CDP/network call introduced? `stable`/`main` untouched, nothing pushed?
- **Request-count-regression:** does the new path provably issue fewer requests than old — `reload==0` over multi-turn, governed rate, 429 fail-soft — asserted OFFLINE? Is the 30 s completion poll correctly LEFT IN (C-2 out of scope) and not accidentally altered?
Then YOU adjudicate severity (re-derive from ground truth; intentional out-of-scope items like the surviving completion poll or the `loop` salvage asymmetry are NOT blocking) and write `team/evidence/handoffs/M17-implement-reactive.md` per the handoff format in `M17-common.md`.
