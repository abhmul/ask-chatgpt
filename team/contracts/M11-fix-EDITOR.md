# M11-fix EDITOR — apply the CLI tab-leak fix + add falsifiable lifecycle tests

You are a **single editor worker** (pi) for team `ask-chatgpt-dev`, repo `/home/abhmul/dev/ask-chatgpt`. You inherit NOTHING except this file. Do the work below end-to-end, then print the structured report at the bottom to stdout. Work ONLY in the current working tree. Do **NOT** `git commit`, `git push`, `git checkout`, `git switch`, `git stash`, `git clean`, `git reset`, or switch branches. Do **NOT** `uv tool install/upgrade/reinstall`. Do **NOT** move/commit the `stable` branch. OFFLINE only — no browser/CDP/network/real chatgpt.com. Do **NOT** touch `issues/cdp-send-repro/controller.mjs` or anything under `human/`. Never print or persist secrets/tokens/cookies.

## The bug (verified UNRESOLVED)
`src/ask_chatgpt/cli.py` has three handlers that acquire a chatgpt.com browser tab but never close it, leaking one tab per CLI invocation:
- `_handle_ask` (cli.py:188-203)
- `_handle_scrape` (cli.py:224-228)
- `_handle_loop` (cli.py:259-289)

Each builds `session = _new_session(args)` then calls `session.ask/scrape/loop(...)` and returns with **no** `detach()`/`with`/`finally`. The only tab-close path is `Session.detach()` → `TabPool.close_all()` → `channel.close_tab()`, and no handler calls it.

The other four handlers — `_handle_create`, `_handle_history`, `_handle_fetch`, `_handle_status` — never call `tab_pool.acquire`, so they do NOT leak; leave them unchanged.

## Ground truth (already verified from source — trust these file:line facts)
- `Session.detach(self, *, close_managed_tabs: bool = True)` at `src/ask_chatgpt/session.py:326-331`: calls `self.tab_pool.close_all()` then, `if self._attached`, `channel.detach()`. It is a **SAFE NO-OP when nothing was attached**: `close_all()` (session.py:112-121) iterates an empty pool (nothing to close) and the `_attached` guard skips channel detach. So calling bare `session.detach()` in a `finally` cannot raise on a never-attached session and cannot mask the return value/exception.
- `TabPool.acquire` (session.py:84-101) calls `self._session.attach()` (sets `_attached=True`) then `channel.open_tab(url)` — a real acquire genuinely opens a tab.
- `main()` (cli.py:80-108) maps `CompletionTimeoutError`→50, `AskChatGPTError`→its `exit_code`, any other `Exception`→99. A `finally: session.detach()` runs BEFORE the exception propagates to `main`, so the mapped exit codes are preserved.

## REQUIRED PRODUCTION EDIT — `src/ask_chatgpt/cli.py` ONLY
Wrap the post-`_new_session` body of the three leaking handlers in `try: <existing body> finally: session.detach()`. Use **`try/finally` + `session.detach()`**, NOT `with _new_session(...) as session:` — because `Session.__enter__`→`attach()` (session.py:333-334,320-324) EAGERLY opens a CDP connection; `with` would force a connection the tab-free handlers never make. `session.detach()` is the safe no-op described above. Preserve ALL current behavior: return codes, `--out`/stdout emission via `_emit_payload`, and the `loop` `KeyboardInterrupt`→130 path.

Exact target shapes (match the current bodies; only add the `try:`/`finally:`):

```python
def _handle_ask(args: argparse.Namespace) -> int:
    conv, prompt = _split_ask_positionals(args.args)
    session = _new_session(args)
    try:
        answer = session.ask(
            conv, prompt,
            model=args.model, tools=tuple(args.tool), attach=tuple(args.attach),
            timeout=args.timeout, max_total_wait=args.max_total_wait, out=args.out,
        )
        content = answer.content_markdown if isinstance(answer, TurnRecord) else str(answer)
        _emit_payload(_ask_payload(content), args.out, args.data_dir, session)
        return 0
    finally:
        session.detach()


def _handle_scrape(args: argparse.Namespace) -> int:
    session = _new_session(args)
    try:
        transcript = session.scrape(args.conv, with_attachments=args.with_attachments, out=args.out)
        _emit_payload(_render_transcript(session, transcript), args.out, args.data_dir, session)
        return 0
    finally:
        session.detach()
```

For `_handle_loop`: **keep the negative-`max_iterations` `ValueError` check BEFORE the new `try`** (it runs before any session/tab is created — no leak there), create the session, then wrap from session creation onward. The EXISTING inner `try/except KeyboardInterrupt: ... return 130` must sit INSIDE the new outer `try`, so `finally: session.detach()` runs on the 130 return, the 0 return, and any propagated exception:

```python
def _handle_loop(args: argparse.Namespace) -> int:
    if args.max_iterations < 0:
        raise ValueError("--max-iterations must be non-negative")
    session = _new_session(args)
    try:
        iteration = 0
        last_emitted: TurnRecord | None = None
        try:
            for iteration, turn in enumerate(
                session.loop(
                    args.conv, message=args.message, model=args.model,
                    tools=tuple(args.tool), attach=tuple(args.attach),
                    timeout=args.timeout, max_total_wait=args.max_total_wait,
                    max_iterations=args.max_iterations, out_dir=args.out_dir,
                ),
                start=1,
            ):
                _write_jsonl_stdout(_loop_envelope(iteration, turn))
                last_emitted = turn
        except KeyboardInterrupt as exc:
            partial = getattr(exc, "partial", None)
            if isinstance(partial, TurnRecord) and (
                last_emitted is None or last_emitted.message_id != partial.message_id
            ):
                _write_jsonl_stdout(_loop_envelope(iteration + 1, partial))
            return 130
        return 0
    finally:
        session.detach()
```

Do NOT modify `_handle_create/_handle_history/_handle_fetch/_handle_status`, and do NOT modify `session.py` / `channels/*.py` — the close machinery there is already correct.

## REQUIRED TEST-STUB UPDATE — `tests/test_cli.py` (DO NOT MISS THIS)
`tests/test_cli.py` defines `RecordingSession` (~lines 90-169), monkeypatched over `cli.Session` by EVERY existing CLI test via `_patch_session` (lines 171-177). It has NO `detach` method. Once the handlers call `session.detach()`, every existing CLI test that uses `RecordingSession` will raise `AttributeError` → mapped to exit 99 → those tests FAIL. You MUST add a recording `detach` method to `RecordingSession`:

```python
def detach(self, *, close_managed_tabs: bool = True):
    self.calls.append(("detach", (), {"close_managed_tabs": close_managed_tabs}))
```

Some existing tests assert `RecordingSession.instances[-1].calls == [(...)]` with an EXACT list (e.g. `test_cli_ask_forwards_flags...`, `test_cli_scrape_and_fetch...`, `test_cli_create...`, `test_cli_status...`). Adding `detach` to the call list will APPEND `("detach", (), {"close_managed_tabs": True})` to those `.calls` for the leaking verbs (ask/scrape/loop) — so you MUST update those exact-match assertions to include the trailing `detach` entry where ask/scrape/loop are exercised. (create/history/fetch/status are unchanged and won't call detach, so their exact-match lists stay as-is.) Run the suite to find every assertion that needs updating; update them minimally and correctly so they still pin the real call sequence. Do NOT weaken an assertion to hide a regression — only append the genuinely-expected `detach` call.

## REQUIRED NEW FALSIFIABLE TESTS — `tests/test_cli.py`
Add lifecycle tests that drive a **REAL `Session` + a real `MockChannel`** (NOT `RecordingSession`) so tab open/close are observable, proving the leak is fixed. Mirror the EXISTING test `test_cli_real_session_ask_out_write_failure_keeps_stdout_first` (test_cli.py:233-379) — it already constructs a complete ask scenario, drives a real `Session` via a `session_factory` patched over `cli.Session`, and holds the `mock` `MockChannel` reference. Also study `tests/test_session_stubs.py` and `tests/mock_scenarios.py` for ready-made `MockScenario` builders for `scrape`/`loop`.

`MockChannel` records calls: `mock.method_counts` (dict, e.g. `{"open_tab":1,"close_tab":1,...}`) and `mock.call_order` (tuple of method names in order). Construct: `MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)`. Pass it to `Session(data_dir=tmp_path, channel=mock, selector_map=selectors, ...)`. Patch `cli.Session` (or `cli._new_session`) to return that real Session.

**In EVERY new test, assert `mock.method_counts.get("open_tab", 0) == 1`** — this proves the real `tab_pool.acquire` path actually ran (so the test exercises the genuine leak path, not a trivial no-op that would pass vacuously).

Add these cases:
1. **ASK SUCCESS** — complete ask scenario (reuse the `raw`/`baseline`/`submitted`/`complete`/`scenario` setup from the existing real-session test, WITHOUT the injected `atomic_write_payload` failure). Assert: exit `0`; `mock.method_counts["open_tab"] == 1`; `mock.method_counts["close_tab"] == 1`; and `"close_tab"` appears AFTER `"open_tab"` in `mock.call_order`.
2. **ASK ERROR (post-acquire)** — inject a failure AFTER the tab is acquired. The simplest faithful mechanism: reuse the existing real-session ask scenario and `monkeypatch.setattr(Store, "atomic_write_payload", fail_atomic_write)` (raises `StoreError`) exactly as `test_cli_real_session_ask_out_write_failure_keeps_stdout_first` does — this raises inside `_emit_payload`, i.e. inside the new `try`, after `open_tab`. Assert: exit `70` (mapped `STORE_ERROR`, preserved) AND `mock.method_counts["close_tab"] == 1` AND `open_tab == 1`. (You may simply EXTEND the existing `test_cli_real_session_ask_out_write_failure_keeps_stdout_first` with the two `method_counts` assertions, OR add a dedicated test — your choice, but the error-path close MUST be asserted.)
3. **SCRAPE SUCCESS** — build/borrow a scrape `MockScenario` (see `tests/test_session_stubs.py`) so a real `Session.scrape` reaches `tab_pool.acquire(render=False)`→`open_tab` and returns a transcript. Assert exit `0`; `open_tab == 1`; `close_tab == 1`; close after open in `call_order`.
4. **LOOP INTERRUPT → 130** — drive a real `Session.loop` that opens a tab and yields at least one turn, then trigger `KeyboardInterrupt`. RECOMMENDED honest mechanism: build a loop scenario that yields one turn, then `monkeypatch.setattr(cli, "_write_jsonl_stdout", <fn that raises KeyboardInterrupt>)`. Because `session.loop(...)` must yield its first turn BEFORE `_handle_loop` calls `_write_jsonl_stdout`, and the generator opens the tab (`tab_pool.acquire`) before yielding, `open_tab == 1` is already true when the interrupt fires; `_handle_loop` catches it → `return 130`; `finally: session.detach()` → `close_tab`. Assert: exit `130` AND `mock.method_counts["close_tab"] == 1` AND `open_tab == 1`. (If a real loop scenario is impractical, an acceptable alternative is to monkeypatch a SINGLE internal step of the real `Session.loop` that runs AFTER `tab_pool.acquire` to raise `KeyboardInterrupt`, having first asserted `open_tab == 1` — keep it honest: a real tab must be opened before the interrupt.)

Name the new tests clearly (e.g. `test_cli_ask_closes_tab_on_success`, `..._on_error`, `test_cli_scrape_closes_tab_on_success`, `test_cli_loop_closes_tab_on_keyboard_interrupt`).

## ACCEPTANCE — `uv run pytest` (PROJECT `.venv`, NOT the uv tool)
1. FIRST, before editing, run `uv run pytest -q` once and record the **baseline pass count** (expected ~276).
2. Apply the production edit + stub update + new tests + assertion fixes.
3. Run `uv run pytest -q` again. **ALL must pass.** Expected = baseline + your new tests. Re-derive PASS from the inspected summary line (e.g. `N passed`), not just exit code.

## FALSIFIABILITY PROOF (git stash/checkout FORBIDDEN — use /tmp file copies)
Prove the new tests genuinely catch the leak:
1. `cp src/ask_chatgpt/cli.py /tmp/m11_cli_orig.py` **BEFORE you edit cli.py** (save the original UNFIXED file). (If you already edited, reconstruct the original by removing your try/finally — but easiest is to copy first; if you forgot, you can re-derive the original from `git show HEAD:src/ask_chatgpt/cli.py > /tmp/m11_cli_orig.py`, which is read-only and allowed.)
2. After the full suite passes (fixed), `cp src/ask_chatgpt/cli.py /tmp/m11_cli_fixed.py`.
3. `cp /tmp/m11_cli_orig.py src/ask_chatgpt/cli.py` (revert the FIX only; keep the new tests in test_cli.py).
4. Run `uv run pytest -q tests/test_cli.py` → your NEW lifecycle tests MUST FAIL (the `close_tab == 1` assertions fail because the unfixed handlers never detach → `close_tab == 0`). Capture which tests fail and the assertion message. Confirm the EXISTING tests still pass when reverted (the `detach` stub is unused by unfixed handlers).
5. `cp /tmp/m11_cli_fixed.py src/ask_chatgpt/cli.py` (RESTORE the fix). Re-run `uv run pytest -q` → ALL pass again.
6. `rm -f /tmp/m11_cli_orig.py /tmp/m11_cli_fixed.py`.

Leave the working tree in the FIXED + all-passing state.

## DIFF SCOPE
`git diff --stat` (read-only, allowed) MUST show ONLY `src/ask_chatgpt/cli.py` and `tests/test_cli.py` modified. No other source file. Do not stage/commit.

## REPORT (print to stdout at the very end — this is your deliverable)
Print exactly these lines (fill in real values from INSPECTED output):
```
M11-EDITOR-VERDICT: <DONE|BLOCKED>
BASELINE_PYTEST: <N passed>
FINAL_PYTEST: <N passed>
NEW_TESTS_ADDED: <comma-separated test function names>
FALSIFIABILITY: reverted cli.py -> <list of new tests that FAILED with close_tab==0>; restored -> <N passed>
DIFF_STAT: <paste git diff --stat output: must be only cli.py + test_cli.py>
EDIT_LOCATIONS: <file:line ranges you changed in cli.py>
NOTES: <anything unexpected, or "none">
```
Then stop.
