# M11 (verify) — Is the "CLI leaks a browser tab per invocation" bug resolved?

**FIRST read `team/contracts/M-backlog-common.md` in full** (binding safety, environment, READ-ONLY rule, dispatch policy, handoff format). Then execute this mission. This is **read-only verification** — produce a verdict + exact Round-2 fix spec; do NOT edit code.

## The issue under test
`issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md` claims: the CLI handlers construct a `Session` and call `ask`/`scrape`/etc. **without a `with` block and without ever calling `detach()`**, so the managed chatgpt.com tab is left open on every invocation (Playwright pages created over `connect_over_cdp` persist after the client disconnects). A perpetual driver accumulated ~18 tabs in minutes. Suggested fix: wrap each handler in `with _new_session(args) as session:` (or `try/finally: session.detach()`), since `Session.__exit__`→`detach()` already closes managed tabs.

## Lead's ground-truth pointers (verify each — do not trust)
- `src/ask_chatgpt/cli.py`: `_new_session` (~line 183); handlers `_handle_ask` (~188), `_handle_create` (~206), `_handle_scrape` (~224), `_handle_history` (~231), `_handle_fetch` (~238), `_handle_status` (~249), `_handle_loop` (~259). A grep for `with _new_session|\.detach(|close_all|__exit__` in `cli.py` returned **no** handler using context-management — confirm this independently.
- `src/ask_chatgpt/session.py`: `Session.__enter__` (~333), `Session.__exit__` (~336), `Session.detach(*, close_managed_tabs=True)` (~326, calls `self.tab_pool.close_all()`), `TabPool.close_all` (~112), `TabPool.acquire` (~84), `TabPool.release` (~103). So the CM/close machinery EXISTS; the question is whether the CLI handlers USE it.

## What the worker(s) must determine (re-derive from ground truth)
1. **Per handler, on the SUCCESS path:** is the session closed/detached (directly or via `with`)? Cover ALL CDP verbs: `ask`, `create`, `scrape`, `history`, `fetch`, `status`, `loop`. (Note: `history`/`fetch`/`status` may be tab-free local-store reads — if a handler never acquires a tab, it cannot leak one; state that explicitly per handler.)
2. **Per handler, on the ERROR path:** if `session.ask(...)`/`scrape(...)` raises, is the tab still closed? (A bare `try/except` that returns an exit code without `finally: detach()` still leaks.)
3. Does `_new_session` itself open a tab eagerly, or only on first `acquire`? (Determines whether even a no-op invocation leaks.)
4. Confirm `Session.__exit__`/`detach`/`close_all` actually close pages (read their bodies; confirm `close_all` calls the channel's tab-close, not just `release`/marks-unleased).
5. Is there ANY existing test that pins tab-closing on exit (e.g. in `tests/test_cli.py` or `tests/test_session_stubs.py`)? If so, why didn't it catch this (or does it pass because handlers are untested for lifecycle)? Read the relevant tests.

## Verdict (put in handoff + final stdout)
`RESOLVED` (all CDP handlers close/detach their session on both success and error paths) **or** `UNRESOLVED` (one or more leak), with a per-handler table: handler → acquires-tab? → closed-on-success? → closed-on-error?.

## If UNRESOLVED — the exact Round-2 fix spec to include
- The precise edit per handler (e.g. wrap body in `with _new_session(args) as session:` so `__exit__`→`detach(close_managed_tabs=True)` runs on success AND exception; or `try/finally: session.detach()`), preserving current return-code/`--out`/stdout behavior and error-to-exit-code mapping.
- The **falsifiable test** to add (in `tests/test_cli.py`): drive a handler against a stub/mock channel that records `open_tab`/`close` calls (see `tests/test_session_stubs.py` / `tests/mock_scenarios.py` for the existing stub style — READ them), assert the managed tab is closed after the handler returns **and** after the handler raises. State exactly what it asserts and how it FAILS against today's code (pre-fix), so it is provably falsifiable.
- Whether the fix touches only `cli.py` (note: a parallel backlog fix M13 touches `capture.py`/`tests/test_capture.py` — disjoint; M12 is read-only). Flag any overlap.

## Suggested decomposition
A single careful read-only pi worker (tools `read,grep,find,ls,bash`) auditing all 7 handlers + the Session close machinery + existing lifecycle tests, returning the per-handler table and fix spec in its stdout. Then you independently re-derive the verdict from the same `file:line` evidence and write the handoff. (This is a concrete "is X present" audit — best-of-N is optional; one worker + your own re-derivation suffices.)

Handoff: `team/evidence/handoffs/M11-verify-cli-tab-leak.md`.
