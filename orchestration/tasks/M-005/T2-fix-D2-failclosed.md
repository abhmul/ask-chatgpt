# T2 — Fix D2: real channel must fail closed BEFORE navigation (RED-first, single editor)

You are a fresh worker. You inherit NOTHING except this file and the files it tells you to read. Everything you need is below.

## The defect (re-verify against the file before changing anything)

In `src/ask_chatgpt/driver.py`, `BrowserSession.start()` (around lines 75-91) does, for `channel="real"`:
1. `self._playwright = sync_playwright().start()`
2. `self._start_real_context()` -> `launch_persistent_context(user_data_dir=profile_path, headless=False)` (around line 275)
3. `page = self._new_or_existing_page()`
4. `page.goto(self._base_url, ...)` where for the real channel `self._base_url == REAL_BASE_URL == "https://chatgpt.com"` (lines 34, 290).

There is NO selector-map readiness check before that navigation. The selector map for the real channel (`src/ask_chatgpt/selector_maps/real.json`) is the all-empty fail-closed TEMPLATE (every selector value is `""`). Emptiness is only enforced LATER, on first selector access: `src/ask_chatgpt/selector_map.py` `SelectorMap.selector(key)` (lines 29-33) raises `SelectorUnavailableError` when the value is not a non-empty string. So today, `channel="real"` + a `profile_path` LAUNCHES A REAL BROWSER and NAVIGATES TO chatgpt.com BEFORE the empty selectors ever fail closed. That is the safety hole.

## The fix (Occam — minimal; NO other driver redesign)

Make the real channel fail closed BEFORE any browser launch or navigation. Add a real-channel selector-map readiness check at the TOP of `start()` (BEFORE `sync_playwright().start()`), so that for the all-empty `real.json` template, `start()` raises `SelectorUnavailableError` with ZERO Playwright/browser/navigation side effects.

- Use the existing exception `SelectorUnavailableError` (already imported in driver.py). Do NOT invent a new error class.
- Readiness predicate: for `channel == "real"`, verify the selector map is populated by probing the selectors the real flow actually needs — at minimum the navigation-critical keys, but checking the full required-key set is preferred and equally simple. The existing `self.selectors.selector(key)` accessor already raises `SelectorUnavailableError` on an empty/whitespace value, so a small helper that calls it for the required keys (and lets the first raise propagate) is the cleanest implementation. The all-empty template must trip it.
- Do NOT change the `mock` channel path in any way. Do NOT change selector_map.py's existing semantics (you MAY add a helper there if cleaner, but the minimal change is in driver.py). Do NOT touch `real.json` — it MUST stay the all-empty template.
- Keep the change surgical: this is a reorder + a guard, not a redesign.

## RED-FIRST discipline (MANDATORY — do this in order, capture both runs in your report)

1. FIRST write the failing test, BEFORE editing driver.py. Put it in `tests/` (new file e.g. `tests/test_driver_real_failclosed.py`, or add to `tests/test_driver.py` — read `tests/test_driver.py` first to match existing style/fixtures).
2. The test must prove fail-closed WITHOUT real navigation and WITHOUT network:
   - Construct `BrowserSession(channel="real", profile_path=<a tmp dir>)` and call `.start()`.
   - Assert it raises `SelectorUnavailableError`.
   - Assert NO navigation to chatgpt.com was attempted. Do this with a network-free fake: monkeypatch `ask_chatgpt.driver.sync_playwright` with a fake whose `launch_persistent_context(...)` returns a fake context/page, and whose page `.goto(url)` APPENDS `url` to a list the test can inspect. After `.start()` raises, assert that list is EMPTY (no `https://chatgpt.com` recorded), i.e. `goto` was never reached. (Equivalently/additionally you may assert the fake `sync_playwright` was never `.start()`-ed, since the fix checks readiness before that — but the goto-recording assertion is the load-bearing one.)
   - The test must require NO network: the fake Playwright guarantees this; the autouse socket guard in `tests/conftest.py` must stay active (do not disable it).
3. RUN the new test against the PRE-FIX driver and capture the output: it MUST FAIL (pre-fix, `start()` proceeds to the fake `goto`, so either `SelectorUnavailableError` is NOT raised or the recorded-goto list is non-empty -> assertion fails). Paste this RED run in your report.
4. THEN apply the driver fix.
5. RUN the new test again: it MUST PASS (GREEN). Paste it.
6. RUN THE FULL SUITE: `uv sync --all-groups` then `uv run pytest` (ALL tests, serialized — not just your new test). It MUST be fully green, proving the mock channel and everything else is unchanged. Paste the final summary line (e.g. `N passed in Xs`) and the exit code.

## Constraints / SAFETY (transcribed verbatim — obey exactly)

- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; loopback/local only. Your D2 test MUST prove fail-closed WITHOUT real navigation (fake/monkeypatched playwright; socket guard stays active). No test or script may set `channel="real"` against the real site. `selector_maps/real.json` stays the all-empty fail-closed template.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Do NOT write `.claude/` or `.agents/`. Do NOT touch the shared agent venv (`~/.local/share/agent-python/.venv`); use `uv run`/`uv sync` from the repo root (targets the project `.venv`).
- `uv sync --all-groups` ALWAYS before any `uv run`. Serialize pytest (no `-n`/xdist parallelism). Ephemeral ports only. Kill only processes your own run starts. NEVER `git push`.
- ESTIMATE BEFORE EXECUTE: state expected wall-clock before running the suite.

## Commit

Commit the new test + the driver fix together with a message starting `M-005: ` (e.g. `M-005: fix D2 — real channel fails closed (SelectorUnavailableError) before navigation; RED-first test`). Commit ONLY these files (the new test + driver.py, and selector_map.py only if you added a helper there). Report the commit SHA.

## Telemetry + report (write to `orchestration/reports/M-005/T2.md`, cap ~200 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T2 <minutes>m`.
- Body, in order: (a) the RED run output (new test failing pre-fix), (b) a short description of the driver change, (c) the GREEN run of the new test, (d) the FULL-suite green summary + exit code, (e) the commit SHA.
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T2-STATUS: DONE` (or `T2-STATUS: BLOCKED` with the exact blocker).
