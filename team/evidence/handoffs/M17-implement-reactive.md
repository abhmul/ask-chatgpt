# M17 — Reactive-traffic implementation (C-1 + C-4 + minor) — handoff

## 1. Status
**DONE**

Scope shipped exactly as contracted: the minor `--max-total-wait` salvage fix, C-1 (persistent-tab reload-split preserving header-harvest), and C-4 (cross-process rate governor + 429 fail-soft exit 52 + jitter). C-2 (stream-close completion observer) was held OUT OF SCOPE (probe-gated) — the 30 s completion poll is left intact and unchanged. C-3 (capture-from-stream) deferred.

## 2. What shipped (per component)

### minor — `--max-total-wait` salvage (M16 §7) — commit `694255f`
- `src/ask_chatgpt/cli.py:14` — added `MaxTotalWaitExceededError` to the errors import.
- `src/ask_chatgpt/cli.py:92` — widened the salvage handler to `except (CompletionTimeoutError, MaxTotalWaitExceededError) as exc:`; `exc.exit_code` preserves 50 vs 51; the `command == "ask"` gate is intact; partial reaches stdout + `--out` via the generic `AskChatGPTError` exit path (no behavior change for other errors).
- Test: `tests/test_cli.py::test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error` — asserts the synthetic partial (`PARTIAL-ANSWER-SENTINEL`) on stdout AND in `--out` FILE + exit **51** + the `MAX_TOTAL_WAIT_EXCEEDED` error label.
- Falsifiability proof (editor red-phase, re-derived by panel): on prior code the partial fell through → `assert '' == 'PARTIAL-ANSWER-SENTINEL\n'` (partial dropped).
- Left out of scope (flagged): `loop` also accepts `--max-total-wait` but only handles `KeyboardInterrupt` partials (ask-only salvage asymmetry, M16 §7) — intentionally not changed.

### C-1 — reload-split preserving header-harvest (M16 §3 C-1) — commit `9f9e087`
- `src/ask_chatgpt/send.py:48-64` — `wait_for_idle_and_reload_if_needed` now tracks `observed_inflight_generation`: an **already-idle** send returns WITHOUT reloading; a reload fires only after a real staleness signal (generation observed mid-flight, then cleared). The idle-timeout `PromptNotSubmittedError` is preserved.
- Tests (extend `tests/test_session_draft_loop.py`):
  - `test_loop_persisted_tab_opens_once_and_does_not_reload_when_already_idle` — 2-turn persisted loop asserts `open_tab == 1`, `managed_tabs == 1`, `reload == 0`.
  - `test_loop_capture_harvests_required_headers_without_steady_state_reloads` — a `RecordingChannel` records the header NAMES used for each conversation backend fetch and asserts all **8 `REQUIRED_CAPTURE_HEADERS`** are present per turn AND `capture_source == "backend_api"` AND `reload == 0`.
  - The existing `test_loop_two_iterations_...` was strengthened with `open_tab == 1`/`reload == 0` (no assertions removed).
- Falsifiability: on prior code `wait_for_idle_and_reload_if_needed` reloaded every idle send → `reload == 2` over a 2-turn loop → `assert 2 == 0`.

### C-4 — rate governor + 429 fail-soft + jitter (M16 §6) — commit `fbc3b1a`
- NEW `src/ask_chatgpt/governor.py` — file-lock (`fcntl.flock`, with `if fcntl is not None` guard) token-bucket `Governor` + `GovernorConfig`. State (JSON under `Store.resolve_data_dir()/governor/bucket.json`, dir mode `0700`) holds ONLY non-secret ops data (`tokens`, `refill_epoch`, `blocked_until`, `last_rate_limited_epoch`, redacted coarse `last_action`/`last_path_kind`). `acquire(cost, action, path_kind)` refills/checks-blocked/throttles/debits; `note_rate_limited(retry_after_s)` sets shared `blocked_until`; bucket starts FULL on fresh state; injectable clock+sleeper. Conservative, clearly-labeled, **operator-owned** configurable defaults (cap 120, refill (30−15 reserve)×(1−0.5 margin)/60 ≈ 0.125 tok/s) with a code comment that the real ceiling must be confirmed/measured, never assumed (M16 §6, memory `verify-inherited-resource-claims`).
- `src/ask_chatgpt/errors.py:226` — `RateLimitedError` (`RATE_LIMITED`, exit **52**, `retryable=True`, `retry_action="back_off"`), exported. `src/ask_chatgpt/cli.py:43` — `RATE_LIMITED: 52` table entry; the error takes the plain `AskChatGPTError` exit path (cli.py:103) — **no clipboard salvage**.
- 429 detection via `raise_for_rate_limit(result)` (integer-only `Retry-After` parse, raw value never stored/logged):
  - `src/ask_chatgpt/completion.py:58` — after the completion fetch, BEFORE the `!= 200` `BackendCaptureShapeError`; the swallow set (completion.py:163) still catches only auth/shape, so `RateLimitedError` escapes `wait_for_completion`.
  - `src/ask_chatgpt/capture.py:224` — after the capture fetch, BEFORE `BackendFetchMeta`; `capture.py:371` adds an explicit `except RateLimitedError: ... raise` BEFORE the `→ fallback_capture_ui` tuple → 429 never reaches the clipboard/UI fallback.
- `src/ask_chatgpt/session.py:529` — `except RateLimitedError` placed FIRST (before the generic partial-salvage handler): `record_soft_signal("rate_limited")` + `governor.note_rate_limited(retry_after)` + bare `raise` (exit 52, no partial salvage).
- Jitter: `src/ask_chatgpt/session.py:232` — `_effective_spacing_s = _required_spacing_s() + clamp(rng(),0,1)*jitter_max_s` (injectable RNG); strictly ONE-SIDED (never undercuts the politeness floor).
- Governor wired at chokepoints: page-load/open_tab (`session.py:101`), the conditional pre-send reload (via a transparent `_GovernedReloadChannel` wrapper, `session.py:303`/`454`, charging only when a reload actually occurs — does NOT touch send.py and does NOT reintroduce a steady-state reload), draft capture reload (`session.py:513`), send submit + uploads (`session.py:471/474`), completion/capture/attachment backend fetches.
- Tests: `tests/test_rate_governor.py` (token-bucket sleep-on-exhaust + Retry-After shared backoff, exact fake-clock assertions); `test_completion_429_..._is_not_swallowed`; `test_capture_429_..._never_uses_ui_fallback` (grants clipboard + asserts `read_clipboard == 0` and no UI capture_source); `test_cli_rate_limited_429_returns_52_without_stdout_out_or_clipboard_salvage` (canary: on prior code the 429 was swallowed → exit 0; now exit 52); `test_rate_limited_error_exit_52_...`; `test_send_budget_one_sided_jitter_...`; `test_session_invokes_governor_for_page_load_send_and_backend_fetches`.

### Intentionally left for later
- **C-2** (native stream-close completion observer): NOT implemented — gated on the M16 §4 operator-run attended probe. The 30 s completion poll (`poll_backend_completion` full-conversation GET) is left in place; only 429 detection + a governor charge were added at the existing fetch boundary (verified unchanged via `git show main:.../completion.py`). A clean seam remains (poll is centralized in `wait_for_completion`).
- **C-3** (capture-from-stream): deferred; the single on-completion capture GET is kept.

## 3. Authoritative gate (run by me, the manager)
`============================= 292 passed in 1.33s ==============================`
(Baseline on `main` = 281 passed; +11 net new tests across the three components. No skips/xfails introduced. `real_site` tests remain deselected by default — this mission was entirely offline / MockChannel. Full verbose run saved to `team/evidence/handoffs/M17/authoritative-pytest.txt`.) I ran `uv run pytest` myself after each editor and as the final authoritative gate; verdicts re-derived from the inspected diff + output, never from exit codes alone.

## 4. C-1 reload accounting (removed vs kept-for-harvest)
- **REMOVED:** the unconditional per-turn steady-state reload — `wait_for_idle_and_reload_if_needed` no longer reloads when the page is already idle on the first check. This is the per-send churn that fired every turn in a multi-turn `loop` (`Session.loop` requires a persisted conv, so all its turns are non-draft).
- **KEPT:** (a) the reload after an observed mid-flight generation (a real staleness signal); (b) the draft/new-conversation post-completion reload at `session.py:455` — UNCHANGED — which triggers the observable `/backend-api/*` request the draft path harvests the 8 headers from (the existing pin `test_draft_ask_reloads_learned_chat_before_capture_when_backend_get_requires_reload` still passes).
- **Harvest survives with `reload == 0`** in steady-state loops: proven by `test_loop_capture_harvests_required_headers_without_steady_state_reloads` (all 8 `REQUIRED_CAPTURE_HEADERS` recorded on each turn's backend fetch, `capture_source == backend_api`, `reload == 0`). Steady-state turns harvest from already-observed page-load/open_tab requests; no reload is needed.

## 5. Verification panel (best-of-N=4, non-editing) + my adjudication
One authoritative `uv run pytest` was produced once; 4 parallel read-only pi lenses reasoned over that output + the branch diff (`team/evidence/handoffs/M17/branch.diff`) — they did not re-run the heavy suite.
- **Correctness — PASS.** Minor/C-1/C-4 match the locked M16 design; 429-detection placement, swallow-set/fallback exclusions, `_run_send_turn` except-ordering, one-sided jitter, and chokepoint wiring all verified; no regressions; no import cycle. (`team/evidence/handoffs/M17/verify-correctness.md`)
- **Falsifiability — PASS-WITH-CONCERNS.** All 12 new/changed tests fail on `main` (each with a concrete re-derived reason); no assertion was weakened or deleted; the harvest/wiring/throttle tests genuinely pin behavior (a stub would fail, not just an import). Concerns are MINOR depth-only (some 429/governor tests fail on main partly via import-level reds, but each also pins behavior; harvest source is synthetic preseeded snapshots — correct for an offline test). (`verify-falsifiability.md`)
- **Safety/leak — PASS-WITH-CONCERNS.** No secret/header-value/conversation-content/file-id reaches disk/log/state; Retry-After is integer-only (raw value never stored); error details redaction intact; tests use synthetic values; no real-site/CDP/network/curl introduced; `stable`/`main` untouched, nothing pushed, commits contain only `src/`+`tests/`. (`verify-safety.md`)
- **Request-count — PASS.** `reload == 0` reduction pinned offline + harvest preserved; governor charged at chokepoints + throttle proven; 429 adds zero fallback requests; the 30 s completion poll is left in and unchanged (git-show comparison); no new-request regression (governor only paces, never emits). (`verify-reqcount.md`)

**Adjudication (severity re-derived from ground truth — `verification-panel-severity-adjudication`):**
- The only above-MINOR finding is the safety lens's **MAJOR**: `governor._safe_label` is lexical normalization/truncation, not semantic redaction, so a *future* caller passing a URL-with-id / header value as `action`/`path_kind` could persist it to governor state. **Adjudicated NON-BLOCKING:** there is no current leak — every current caller passes a closed set of coarse literals (`page_load`/`reload`/`send`/`backend_fetch`/`upload`; path_kinds `completion`/`capture`/`composer_submit`/`attachment*`/`pre_send_idle`/`draft_capture`/tab-mode). The lens itself states it "is not an actual leak in the current M17 call graph." Recorded as a hardening recommendation (below), not an M17 blocker.
- All other lens findings are INFO/MINOR depth notes that do not break an acceptance criterion. **No unresolved blocking findings.**

## 6. Branch state
- Branch `feat/reactive-traffic-m17` (off `main` `a98353f`), 3 commits:
  - `fbc3b1a` feat(governor): cross-process rate governor + 429 fail-soft (exit 52) + jitter (C-4)
  - `9f9e087` refactor(send): split idle-wait from reload to kill per-turn page reload (C-1)
  - `694255f` fix(cli): salvage partial on --max-total-wait, not just completion timeout
- **NOT pushed** (no remote ref), **no PR**, **`main` untouched** (`a98353f`), **`stable` untouched** (`837f7aa`). Each commit message carries the `Co-Authored-By: Claude Opus 4.8 (1M context)` trailer. Commits contain only `src/ask_chatgpt/*` + `tests/*`; pre-existing dirty `team/state/RESUME.md` and the `team/contracts|evidence` docs were left unstaged.

## 7. What was verified / artifacts / blockers / signals
**Verified (by me, from ground truth):** path-scoped diffs per commit (`git diff -- <files>`); the new `governor.py` read in full (flock, full-bucket start, integer-only Retry-After, redacted state); 429 placement before swallow/fallback in completion.py/capture.py; one-sided jitter + first-position `except RateLimitedError` in session.py; `send.py` untouched by C-4; C-1 `reload==0` + draft-reload pin (:270) + exact-harvest pin (:295) green; all 5 changed test files are purely additive (0 deletions → no weakened assertions); `uv run pytest` = 292 passed after each gate; refs `stable`/`main` unchanged; branch not pushed.

**Artifacts + trust level:**
- `team/evidence/handoffs/M17/authoritative-pytest.txt` — 292 passed (manager-run) — **verified-independently**.
- `team/evidence/handoffs/M17/branch.diff` — full branch diff — **verified-independently**.
- `team/evidence/handoffs/M17/verify-{correctness,falsifiability,safety,reqcount}.md` — panel lenses — **verified-independently** (manager adjudicated severity).
- `team/evidence/handoffs/M17/editor-{a,b,c}.md` — editor self-reports — **producer-only** (cross-checked against diff + my gate).

**Blockers:** none for this mission. The standing blocker to deploying C-2 remains the M16 §4 operator-run attended stream-close probe (out of scope here).

**Recommended next tasks:**
- (hardening, non-blocking) Constrain governor `action`/`path_kind` to a closed vocabulary (enum/whitelist) or assert membership, so `_safe_label` is a defense-in-depth backstop rather than the sole guard — pre-empts any future caller persisting a URL-with-id.
- (portability, non-blocking) The cross-process `blocked_until`/refill epochs use the channel clock (`time.monotonic` in prod), which is system-wide on Linux (the deployment target) but per-process on some platforms. Document the Linux-`CLOCK_MONOTONIC` assumption or switch the persisted cross-process epoch to `time.time()` in a future pass.
- (completeness, minor) Attachment descriptor/byte fetches are governor-charged but do not call `raise_for_rate_limit` (a 429 there yields an "error" download outcome, not `RateLimitedError`). M16 §6 named completion+capture as the 429 sites; extending 429 classification to attachments is a small follow-up.
- C-2 (after the attended probe passes) and C-3 remain separate missions.
- Operator owns: confirm/measure the real account rate ceiling and tune `GovernorConfig` from conservative defaults; deploy (reinstall is operator-reserved).

**Complexity / paradigm-shift signals:** none forcing a rewrite. C-4's cross-process governor is genuinely new code but slots cleanly onto the existing `fcntl.flock`/data-dir infra. The `_GovernedReloadChannel` wrapper is a small added indirection that keeps C-4 from touching EDITOR-B's `send.py` reload-split — clean separation, no paradigm shift.
