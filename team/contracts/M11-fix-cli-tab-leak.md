# M11-fix — Apply the CLI tab-leak fix (single editor, TDD) + independent verify

You are a MANAGER (Opus, `claude -p`, **SINGLE-SHOT**) for team `ask-chatgpt-dev`, repo `/home/abhmul/dev/ask-chatgpt`. Execute this **mutating** mission end-to-end IN THIS ONE TURN and write a handoff.

## ⚠️ ANTI-YIELD — READ FIRST (Round-1 managers failed exactly here)
You are single-shot: **you will NOT be re-invoked.** Do **NOT** spawn a background task/monitor and yield expecting to be called back. **BLOCK in the FOREGROUND** on every pi worker using `pi-watch.sh --wait-seconds 1800 --poll-seconds 15 ...` (it returns only when the worker writes its `status` file). Run ALL steps (editor → acceptance → independent verify → write handoff) within this single turn. If you yield with work incomplete, the mission FAILS and your handoff is lost. (Two Round-1 managers yielded by spawning a background monitor — do not repeat that.)

## Mission
Fix `issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md`, verified UNRESOLVED in M11 (read `team/evidence/handoffs/M11-verify-cli-tab-leak.md` — it has the full per-handler analysis + exact fix + test spec). The CLI handlers acquire a chatgpt.com tab but never close it (no `with`/`detach`), leaking one tab per invocation.

## Ground truth (verify; do not trust this prose)
- **Leaking handlers** (acquire a tab, never detach): `_handle_ask`, `_handle_scrape`, `_handle_loop` in `src/ask_chatgpt/cli.py`. Each does `session = _new_session(args)` then `session.ask/scrape/loop(...)` and returns without detaching.
- **Tab-free handlers** (never call `tab_pool.acquire`, so they do NOT leak a browser tab): `_handle_create`, `_handle_history`, `_handle_fetch`, `_handle_status`. Leaving them unchanged is correct; uniform cleanup is acceptable but not required.
- **Close machinery already exists & is sufficient if called:** `Session.detach(close_managed_tabs=True)` (`session.py:326-328`) → `TabPool.close_all()` (`session.py:112-118`) → `channel.close_tab()` (real: `cdp.py:653-670`; mock: `mock.py:296-300`). `TabPool.release` only flips `leased=False` (insufficient). `Session.__enter__` (`session.py:333-334`) **EAGERLY attaches**.
- **Error mapping:** top-level `main()` (`cli.py:90-108`) catches exceptions and maps to exit codes; unexpected → 99.

## Required change (single editor; fix in `src/ask_chatgpt/cli.py` ONLY)
Wrap the bodies of `_handle_ask`, `_handle_scrape`, `_handle_loop` in `try: <existing body> finally: session.detach()`.
- Use **`try/finally` + `session.detach()`**, NOT `with _new_session(...)`, because `Session.__enter__` eagerly attaches (avoid forcing an attach/connection; keeps cleanup uniform if you also wrap tab-free handlers).
- `detach()` MUST run on BOTH the success path AND when the body raises (close the tab before the exception propagates to `main()`'s mapping). It must be **safe when no tab was acquired** — read `session.py:326-339`; `close_all` is a no-op on an empty pool, but confirm `detach()` tolerates a never-attached session; if it could raise, guard so it never masks the original return value/exception.
- Preserve ALL current behavior: return codes, `--out`/stdout emission, the `loop` `KeyboardInterrupt`→130 path, and the error-to-exit-code mapping.

## Falsifiable tests (`tests/test_cli.py`)
Add parametrized lifecycle tests for `ask`/`scrape`/`loop` driving a **real `Session` with `MockChannel`** (study `tests/test_session_stubs.py` + `tests/mock_scenarios.py` for the `MockChannel` style; `MockChannel` records `open_tab`/`close_tab` via `method_counts`/`call_order`). Monkeypatch `cli.Session` to return `Session(data_dir=tmp_path, channel=MockChannel(...), selector_map=SELECTORS)`; monkeypatch heavy internals so each handler reaches `tab_pool.acquire` then returns or raises.
- **SUCCESS:** assert exit 0 AND `method_counts["open_tab"]==1` AND `["close_tab"]==1` AND `close_tab` occurs after `open_tab` in `call_order`.
- **ERROR:** inject a post-acquire exception; assert the existing mapped exit code is preserved AND `open_tab==close_tab==1`.
- **LOOP INTERRUPT:** `KeyboardInterrupt` → assert return 130 AND `close_tab==1`.
Prove falsifiability empirically: revert the fix in a scratch copy (or `git stash` is FORBIDDEN here — instead copy the file aside), show the new tests FAIL (`close_tab==0`), restore, show they PASS. Document this in the handoff.

## Acceptance + independent verify
1. Run `uv run pytest` (PROJECT venv `.venv`); ALL must pass (baseline was **276**; expect 276 + your new tests). Re-derive PASS from inspected output, not the exit code alone.
2. Then dispatch a SECOND pi worker (independent verifier; tools `read,grep,find,ls,bash`) to: (a) re-run `uv run pytest` and confirm the count, (b) confirm the new tests are genuinely falsifiable (precise reasoning or a scratch-copy mutation), (c) confirm the diff touches ONLY `src/ask_chatgpt/cli.py` + `tests/test_cli.py`, contains no secret/leak, `stable`=`bbbe027` unmoved, and `issues/cdp-send-repro/controller.mjs` + `human/` are untouched.

## Safety / constraints (transcribe into worker prompts — children inherit nothing)
- Work in the CURRENT working tree (branch `fix/m10-light-read-scrape`, content == merged `main`). Do **NOT** switch branches. Do **NOT** `git commit`/`git push`/`git checkout`/`git stash`/`git clean` (the LEAD commits at packaging time). Do **NOT** move/commit `stable`. Do **NOT** `uv tool install/upgrade/reinstall`.
- WORKERS → pi via `bash .claude/skills/manager/references/launchers/parent-claude/pi-watch.sh`; **NEVER** the Agent/Task tool. **Single editor** for the source change (no parallel editors on the tree).
- Do NOT touch `issues/cdp-send-repro/controller.mjs` or `human/`. OFFLINE only (no browser/CDP/real site). Never print/persist secrets.

## Handoff
Write `team/evidence/handoffs/M11-fix-cli-tab-leak.md`: Status (`DONE`/`PARTIAL`/`BLOCKED`); exact change with `file:line`; `uv run pytest` count before/after; the falsifiability proof; the independent verifier's verdict; diff scope; blockers. End your FINAL message with three lines: `Status: ...`, `Pytest: <N passed>`, `Handoff: team/evidence/handoffs/M11-fix-cli-tab-leak.md`.
