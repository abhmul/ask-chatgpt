# T2d — Optional presence-markers must not hard-fail when fail-closed-empty (MOCK-TIER, single editor, TDD)

You are a fresh worker. **You inherit NOTHING except this file + the files it tells you to read.** ZERO real contact: mock/loopback/unit only. **ZERO real messages.** TDD/RED-first. Read the SAFETY BLOCK and obey it literally. The repo destructive-guard hook blocks command text containing certain destructive substrings — use `git stash push -u` for any revert, never `git checkout`/`git clean`. Do NOT `git commit` (the manager commits after independent verification).

## Why this leg exists (a real-site run surfaced GAP-6; manager-confirmed from ground truth)

The real CDP acceptance leg (T3) failed CLOSED before sending a prompt. Exact observed error: `SelectorUnavailableError: selector 'conversation_not_found' unavailable for channel 'real'`. Root cause: the driver's OPTIONAL presence-check markers are EMPTY in the fail-closed `real.json` (`conversation_not_found`, `login_wall`, `truncation_marker`, `rate_limit_marker` are all `""`), and `_present(key)` resolves the selector via `SelectorMap.selector(key)` which RAISES `SelectorUnavailableError` on an empty value. So `_raise_open_failures()` (and `wait_for_completion`, `_rate_limit_visible`) hard-error on EVERY real call.

The fix: an UNMAPPED optional presence marker means "this condition cannot be detected by a DOM marker → treat it as ABSENT and proceed", NOT "hard error". REQUIRED selectors must STILL fail closed.

### Manager-verified facts (transcribe-accurate; verify, line numbers may drift)
- `src/ask_chatgpt/driver.py`:
  - `_present(self, key)` (~line 459): `try: return self._locator(key).count() > 0 except PlaywrightError as exc: raise SelectorUnavailableError(...)`. `_locator(key)` calls `self.selectors.selector(key)` which raises `SelectorUnavailableError` (NOT PlaywrightError) for an empty value — so `_present` does NOT catch it and the error propagates.
  - `_present` callers — ALL are OPTIONAL markers: line 476 `_present("conversation_not_found")` + line 478 `_present("login_wall")` (in `_raise_open_failures`, ~475-478); line 282 `_present("truncation_marker")` and line 298 `_present("streaming_marker")` (in `wait_for_completion`); line 528 `_present("rate_limit_marker")` (in `_rate_limit_visible`). (`streaming_marker` is populated in real.json; the others are empty.)
  - DIRECT (non-`_present`) optional-selector use: line 288 `latest_assistant.locator(self.selectors.selector("truncation_marker")).count() > 0` — also raises on empty `truncation_marker`; needs the same guard.
  - REQUIRED selectors use `_require_present(...)` (ready_root, composer, send_button, new_chat_button, model_menu, assistant_message) and MUST keep hard-failing — DO NOT change `_require_present`.
- `src/ask_chatgpt/selector_map.py` (~29-39): `selector()`/`attribute()` raise `SelectorUnavailableError` on empty/whitespace. Do NOT change this (it is the correct fail-closed primitive).
- `src/ask_chatgpt/selector_maps/real.json`: `conversation_not_found`, `login_wall`, `truncation_marker`, `rate_limit_marker` are `""` (intentional fail-closed). `mock.json`: these ARE populated, so the mock path must stay byte-for-byte identical.

## Deliverables (TDD/RED-first)

### D1 — Make `_present` soft for unmapped optional markers
Modify `_present(key)` so a missing/empty selector (i.e. `SelectorMap.selector(key)` raising `SelectorUnavailableError`) returns `False` (marker treated as absent), while a genuine Playwright runtime error still raises. Concretely: also catch `SelectorUnavailableError` from the selector lookup and return `False`. Keep the existing `PlaywrightError → raise SelectorUnavailableError` behavior for real DOM/timeouts. (Because EVERY `_present` caller is an optional marker, this is the correct scope; `_require_present` is untouched and required selectors still fail closed.)

### D2 — Guard the direct truncation check (line ~288)
In `wait_for_completion`, the per-turn check `latest_assistant.locator(self.selectors.selector("truncation_marker")).count() > 0` must NOT raise when `truncation_marker` is unmapped. Add a small helper (e.g. `_optional_selector(self, key) -> str | None` returning `None` when `selector(key)` raises `SelectorUnavailableError`) and skip the truncation check when it returns `None`; when mapped, behavior is unchanged. (Do not weaken truncation detection when the marker IS configured, e.g. in the mock.)

### D3 — Preserve all other semantics
- `_raise_open_failures`, `_rate_limit_visible` need NO direct change once `_present` is soft — verify they now no-op for unmapped markers and still raise `SessionNotFoundError`/`LoginRequiredError`/`RateLimitedError` when the marker IS present (mock).
- The open-existing 404 path (`response.status == 404 → SessionNotFoundError`, ~line 199) and the cdp URL-based login/challenge guards are unaffected — leave them.
- Do NOT populate any empty real.json selector. Do NOT touch `mock.json`, `conftest.py`, `_require_present`, or `selector_map.py`.

### D4 — Tests (DEFAULT-TIER; mock/loopback/unit; NOT real_site; RED-first)
Add tests proving the soft behavior WITHOUT real contact. Construct a `BrowserSession`/`SelectorMap` (or a focused fake page + an empty-optional-markers map mirroring real.json's empty keys) such that:
- `_present("conversation_not_found")` / `_present("login_wall")` / `_present("truncation_marker")` / `_present("rate_limit_marker")` return `False` (no raise) when the selector is `""`.
- `_raise_open_failures()` does NOT raise when those markers are empty; but STILL raises `SessionNotFoundError` (conversation_not_found present) / `LoginRequiredError` (login_wall present) when the marker IS configured and matches (use a mock/loopback page).
- `wait_for_completion` does not raise on an unmapped truncation_marker (focused test acceptable if full integration is awkward — state which).
- `_rate_limit_visible()` returns `False` when rate_limit_marker is empty.
- The existing mock UC1 happy path + all current tests stay green (the mock has these markers populated → behavior unchanged).

### D5 — Suite green + tier purity
- `uv sync --all-groups`, then run the FULL default suite ONCE (serialize): `uv run pytest`. MUST be GREEN; expect >= the prior 144 passed (you are adding tests). Capture the exact summary line.
- Clean run still collects ZERO `real_site` tests; socket guard + `mock.json` UNCHANGED.
- `git diff --stat` touches ONLY: `src/ask_chatgpt/driver.py` and your new/edited test file(s). NOT real.json, NOT mock.json, NOT conftest, NOT selector_map.py, NOT api.py/cli.py.

## SAFETY BLOCK — obey verbatim (you inherit nothing)
- ZERO real-site contact. Mock/loopback/unit only. The autouse socket guard must NEVER be weakened; preserve fail-closed for REQUIRED selectors (do not soften `_require_present`).
- Never read/copy/store/log credentials, cookies, tokens, profile contents. No account identifiers anywhere.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. NEVER `git push`. Do NOT `git commit`.
- ESTIMATE BEFORE EXECUTE: state expected wall-clock + output volume before the test run.

## Reporting (write to `orchestration/reports/M-006/T2d.md`, cap ~250 lines)
1. `START_TIMESTAMP:`/`END_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T2d <min>m`.
2. The exact change to `_present` + the truncation guard (final line numbers) + RED→GREEN evidence.
3. Authoritative `uv run pytest` summary line + ZERO real_site collected + socket guard/mock.json unchanged + mock UC1 happy path still green.
4. `git diff --stat` (prove scope: only driver.py + tests).
5. `MESSAGES_USED: 0`.
- LAST LINE must be exactly: `T2d-STATUS: DONE` (or `T2d-STATUS: BLOCKED` with the precise blocker).
