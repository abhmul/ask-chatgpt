# T4c — REWORK: copy permission-denied simulation + proof (closes memo §6 gap caught by T9 panel). TDD.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). This is a small REWORK leg. T1–T7 are DONE/committed; an independent verification panel found ONE binding-spec gap: memo §6 requires the copy channel to **"simulate permission denial"**, but no test exercises a denied-clipboard scenario and the driver always grants clipboard permissions on the mock context. Close that gap. Do NOT regress the 56 passing tests.

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be green (56 passed). If not, STOP, report BLOCKED with output.

## Read FIRST
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/decision-memo.md` §6 "Copy channel" — the binding requirement: "tests must grant/read real browser clipboard permissions where possible, **simulate permission denial**, stale clipboard, wrong-message copy, missing button, and truncated copied text." (stale/wrong/missing/truncated already exist; permission-denial is the gap.)
3. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/readers.py` — `CopyButtonReader.read(...)` ALREADY maps a clipboard failure to a named error: it catches `PlaywrightError` from `page.evaluate("() => navigator.clipboard.readText()")` and re-raises `SelectorUnavailableError`. (So a denied clipboard read already fails closed with a named error — you just need to ENABLE simulating denial + PROVE it.)
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/driver.py` — `_start_mock_context` currently grants `clipboard-read`/`clipboard-write` UNCONDITIONALLY for the mock context (`grant_permissions(["clipboard-read","clipboard-write"], origin=self._base_url)`). Real channel does NOT grant (unchanged).
5. `/home/abhmul/dev/ask-chatgpt/tests/test_readers.py` — the existing copy/reader tests + the `BrowserSession` usage pattern to mirror.

## Why context-level, not a fixture mode (rationale — implement accordingly)
Permission denial is a BROWSER-CONTEXT condition: `navigator.clipboard.readText()` rejects (NotAllowedError) when the context lacks the clipboard grant — surfacing through `page.evaluate` as a `PlaywrightError`. So the faithful simulation is to create the mock context WITHOUT the clipboard grant (NOT a fake fixture "denied" string). The fixture/copy button stay as-is.

## Scope (small, focused)
1. **Driver option** (`driver.py`): add a constructor parameter to `BrowserSession`, e.g. `grant_clipboard: bool = True`. For the MOCK channel, grant clipboard permissions ONLY when `grant_clipboard` is True (preserve current default behavior). When False, do NOT grant → a clipboard read will be denied. Do NOT change real-channel behavior. Keep the default True so all existing tests/behavior are unchanged.
2. **Tests** (add to `tests/test_readers.py`, or a new `tests/test_copy_permission_denied.py`), channel="mock" only:
   - **Permission denied → named error (graceful, not a raw exception):** with `BrowserSession(channel="mock", base_url=..., grant_clipboard=False)`, script `copy_mode="ok"`, drive to a completed turn, call `CopyButtonReader().read(turn, session.page, session.selectors)` and assert it raises `SelectorUnavailableError` (the named, fail-closed error — NOT a bare `PlaywrightError`/unhandled exception). This is the memo §6 "simulate permission denial" case.
   - **DOM-primary unaffected by denied clipboard:** with `grant_clipboard=False`, `read_response(turn, page, selectors)` (DEFAULT DOM-primary order) STILL returns the correct latest-turn text (DOM extraction needs no clipboard) — proving the default reader is robust to a denied copy affordance.
   - **Copy-first order under denial falls through / fails closed:** `read_response(..., order=(CopyButtonReader(), DomReader()))` with `grant_clipboard=False` falls through copy (denied) to DOM and returns the correct text; and a copy-ONLY order raises `SelectorUnavailableError` (fail-closed, named).
   - Keep a positive control: with `grant_clipboard=True` (default), `copy_mode="ok"` still returns the clipboard text (existing behavior intact).
3. Run `uv run pytest -q`: ALL green (56 existing + new). Bound waits.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Tests and ALL work NEVER contact chatgpt.com/openai or any external service. channel="mock" + loopback ONLY. Clipboard grants (or their absence) apply ONLY to the loopback mock context. Real channel untouched. Do not weaken the conftest socket guard.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Sentinels/test data are synthetic.
- The ONLY ever-permitted external download is chromium — ALREADY CACHED. ZERO new pip deps. Never sudo/apt/install.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY. NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Tear down browsers you start. NEVER `git push`. Do NOT `git commit`. Do NOT regress the 56 existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-002/T4c-report.md`)
- `date -Iseconds` at START + END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- `ESTIMATE: T4c <min>m`.
- Report ≤120 lines: the driver param added, the new tests + what each proves, confirmation the existing 56 stay green, the exact `uv run pytest -q` summary, deviations, trust notes.
- End with `T4c-STATUS: DONE` (or `BLOCKED` + exact error + next action) LAST.

## Success criteria (all must hold)
- `BrowserSession(grant_clipboard=False)` (mock) creates a context WITHOUT clipboard grant; default stays True (no regression).
- A test simulates permission denial and asserts `CopyButtonReader` raises `SelectorUnavailableError` (named, graceful); DOM-primary `read_response` still returns correct text under denial; copy-first falls through / copy-only fails closed.
- Full `uv run pytest -q` green (56 existing pass + new); zero new deps; real channel unchanged.
- Report with telemetry + `T4c-STATUS:` last.
