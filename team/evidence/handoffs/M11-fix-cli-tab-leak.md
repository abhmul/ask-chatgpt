# M11 (fix) — Apply the CLI tab-leak fix + falsifiable tests + independent verify

**Status:** DONE
**Mission:** Fix `issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md` (verified UNRESOLVED in `team/evidence/handoffs/M11-verify-cli-tab-leak.md`). The CLI handlers `_handle_ask`/`_handle_scrape`/`_handle_loop` acquired a chatgpt.com tab but never closed it (no `detach`/`with`/`finally`), leaking one tab per invocation.

Round: Round-2 mutating fix. Branch `fix/m10-light-read-scrape` (content == merged `main`). Single editor → acceptance → independent read-only verifier → this handoff, all in one manager turn. OFFLINE only; no commit/push (the lead commits at packaging time).

---

## 1. Exact change (re-derived from the actual diff, not prose)

### `src/ask_chatgpt/cli.py` — production fix (the ONLY production change)
Wrapped the post-`_new_session` body of the three leaking handlers in `try: <existing body> finally: session.detach()`:
- `_handle_ask` — now `cli.py:188-206`
- `_handle_scrape` — now `cli.py:227-234`
- `_handle_loop` — now `cli.py:265-298`; the `--max-iterations < 0` `ValueError` guard is kept **before** the new outer `try` (no `Session` exists yet → no leak), and the existing inner `try/except KeyboardInterrupt: … return 130` sits **inside** the new outer `try`, so `finally: session.detach()` runs on the `130` return, the `0` return, and any propagated exception.

`detach()` was chosen over `with _new_session(...) as session:` deliberately: `Session.__enter__`→`attach()` (session.py:333-334,320-324) eagerly opens a CDP connection; `with` would force a connection the tab-free handlers never make. `session.detach()` (session.py:326-331) is a **safe no-op when nothing was attached** — `close_all()` (session.py:112-121) iterates an empty pool and the `if self._attached` guard skips channel detach. The four tab-free handlers (`create`/`history`/`fetch`/`status`) were correctly left unchanged. `session.py`/`channels/*.py` untouched (close machinery there already correct).

### `tests/test_cli.py` — test changes
- Added a recording `detach(self, *, close_managed_tabs=True)` to the `RecordingSession` stub (else every existing CLI test using the stub would `AttributeError`→99 once handlers call `detach`).
- Updated the exact-match `.calls` assertions for the ask/scrape/loop verbs to include the now-expected trailing `detach` entry (create/history/fetch/status assertions unchanged — they never detach).
- Added **4 new falsifiable lifecycle tests** driving a **real `Session` + real `MockChannel`** (not the stub), each asserting `method_counts["open_tab"]==1` (proves the real `tab_pool.acquire` path ran) **and** `method_counts["close_tab"]==1` (the leak-fix assertion):
  - `test_cli_ask_closes_tab_on_success` — exit 0; open=1; close=1; close after open in `call_order`.
  - `test_cli_ask_closes_tab_on_error_after_acquire` — post-acquire `StoreError`; mapped exit 70 preserved; close=1.
  - `test_cli_scrape_closes_tab_on_success` — exit 0; open=1; close=1.
  - `test_cli_loop_closes_tab_on_keyboard_interrupt` — `KeyboardInterrupt` mid-loop; exit 130; close=1.

---

## 2. What was verified + evidence

### Acceptance — `uv run pytest` (PROJECT `.venv`)
| run | result | source |
|---|---|---|
| baseline (pre-edit) | **276 passed** | editor (`BASELINE_PYTEST: 276 passed`) |
| editor post-fix | **280 passed** | editor (`FINAL_PYTEST: 280 passed`) |
| **manager independent** | **`280 passed in 1.02s`** | I ran `uv run pytest -q` myself and inspected the summary |
| **independent verifier** | **`280 passed in 1.08s`** | verifier `PYTEST:` line |

280 = 276 baseline + 4 new tests. (The `VIRTUAL_ENV … will be ignored` warning is EXPECTED — `uv run` correctly used the project `.venv`, not the ambient agent-python venv, not the uv tool install.)

### Production fix correctness — manager inspected the actual diff
I read `git diff -- src/ask_chatgpt/cli.py` directly: the change is exactly the three `try/finally: session.detach()` wraps described above and nothing else; `_handle_create` and the other tab-free handlers are untouched. Cross-checked against `session.py:326-331` (`detach` is a safe no-op when unattached) and `session.py:84-101` (`acquire`→`open_tab`).

### Falsifiability proof (git stash/checkout FORBIDDEN — used /tmp file copies)
- **Empirical (editor):** copied original cli.py aside, applied fix, ran full suite (280 pass), saved fixed copy, reverted cli.py to original (keeping the new tests), re-ran → **all 4 new lifecycle tests FAILED with `close_tab==0`** (and 2 of the updated exact-match `.calls` tests also failed, since the reverted handlers no longer call `detach` — consistent), restored fix → **280 passed**, cleaned up /tmp copies. Tree left in fixed all-passing state.
- **Static (independent verifier):** confirmed by reasoning — each new test opens a real tab and requires `close_tab==1`; pre-fix the handlers never call `detach()` and `TabPool.release` (session.py:103-109) only flips `leased=False`, so the only close path (`Session.detach`→`close_all`→`close_tab`) never fires → `close_tab` would be `0` → assertions fail. Two independent methods (empirical + static) agree.

### Independent verifier verdict — CONFIRMED (read-only worker, no edit/write tools)
Run dir `.pi-workers/pi-20260622-111207-3097821-25930` (exit 0). `M11-VERIFIER-VERDICT: CONFIRMED`. All sub-checks CONFIRMED: pytest 280; falsifiability; 4 new tests present with `open_tab==1` AND `close_tab==1`; diff scope cli.py+test_cli.py only; invariants; no secret leak.

### Diff scope + invariants (manager re-derived from mtimes; verifier corroborated)
- `git diff --stat -- src/ask_chatgpt/cli.py tests/test_cli.py` → ONLY those two files (cli.py 93 lines, test_cli.py 363 lines).
- Editor run started `2026-06-22T11:02:16-05:00`. mtimes: `cli.py` 11:07:44 and `test_cli.py` 11:07:07 (AFTER run start → touched); `issues/cdp-send-repro/controller.mjs` **2026-06-19 01:05:50** (3 days old → untouched), rate-limit issue `.md` 10:55:33 and `team/state/live-state.json` 10:51:55 (BEFORE run start → pre-existing dirty, not this fix).
- `human/` contains only the pre-existing `prompt- buffer.md` (Jun 18) — untouched.
- `git rev-parse stable` = `bbbe02762deed1fa909e7354b1d6e4d89c119f63` (`bbbe027`, unmoved); branch = `fix/m10-light-read-scrape` (unchanged).
- No real secret leaked: the `SECRET_TOKEN`/`SECRET_PROMPT_BODY`/`SECRET_COOKIE`/`HEADER_CANARIES` strings in `tests/test_cli.py` are intentional SYNTHETIC test fixtures asserting redaction — not real credentials.

---

## 3. Artifacts + trust level

| artifact | trust |
|---|---|
| `src/ask_chatgpt/cli.py` (the fix) | **verified-independently** — manager read the diff; verifier reasoned from source; 3× pytest (manager + editor + verifier) all 280 |
| `tests/test_cli.py` (stub `detach` + 4 new tests + assertion updates) | **verified-independently** — verifier confirmed the assertions + falsifiability; falsifiability shown empirically (editor) AND statically (verifier) |
| `team/evidence/handoffs/M11-fix-cli-tab-leak.md` (this file) | manager-authored from inspected evidence |
| `.pi-workers/pi-20260622-111207-3097821-25930/output.log` (verifier) | **verified-independently** — independent read-only verifier, CONFIRMED |
| `.pi-workers/pi-20260622-110216-3093459-17418/output.log` (editor) | **producer-only** — corroborated by manager + verifier; its self-verdict `BLOCKED` was a FALSE ALARM (see §5) |
| `team/contracts/M11-fix-EDITOR.md`, `team/contracts/M11-fix-VERIFIER.md` | manager-authored worker contracts |

---

## 4. Blockers
None. The fix is complete and verified. Per mission constraints I did NOT commit/push/checkout/stash — the **LEAD commits at packaging time**. The working tree is in the fixed, all-passing (280) state.

---

## 5. Note — editor's BLOCKED self-verdict was a false alarm (severity re-adjudicated)
The editor printed `M11-EDITOR-VERDICT: BLOCKED` because it ran an UNQUALIFIED `git diff --stat` (no path filter), which lists ALL dirty files — including `issues/cdp-send-repro/controller.mjs`, the rate-limit issue `.md`, and `team/state/live-state.json` — and it got nervous that "forbidden controller.mjs" appeared. Ground-truth re-derivation (file mtimes vs the run-start timestamp; the session-start `git status` snapshot already showing those three as `M`) proves the editor touched ONLY `cli.py` + `test_cli.py`; controller.mjs is 3 days old and untouched. The editor mis-scored severity for lack of inherited context (it didn't know those files were already dirty pre-run). Manager + independent verifier both re-derived the true scope → **actual status DONE**. (Lesson: workers self-flag on unqualified diffs; the manager must scope the diff to the worker's own files and reconcile pre-existing dirt from mtimes.)

---

## 6. Recommended next missions / tasks
1. **LEAD: commit** `src/ask_chatgpt/cli.py` + `tests/test_cli.py` (scope is clean and isolated; do NOT sweep the pre-existing dirty files into this commit). Do not push (operator-reserved).
2. Once landed, the consumer-side mitigation `reap_our_tabs()` in the weak-simplex driver can be **retired** (it was only working around this leak).
3. **Optional future (design signal, from M11-verify §6):** a more robust paradigm than three per-handler `try/finally` blocks is a **single cleanup site in `main()`** (wrap `args.handler(args)` so every verb detaches uniformly) or hand handlers an already-managed session — this would structurally enforce the REWRITE-SPEC "atomic ops attach→act→detach" intent. Not required for this bounded fix; a separate refactor item.
4. **M13** (capture.py / tests/test_capture.py) is disjoint — no conflict. **M12** is read-only — no conflict.

---

## 7. Complexity / paradigm-shift signals
- **Low complexity, high confidence** — exactly as M11-verify predicted. Localized to 3 handlers; the underlying close machinery (`Session.detach`→`close_all`→`close_tab`) was already correct and unchanged. No paradigm shift needed.
- The fast mock suite (280 tests in ~1s) makes the falsifiability mutate/restore cheap and the acceptance gate trivially re-runnable.
