# T1b — CDP-attach channel (single editor, MOCK-TIER, TDD). NO operator dependency.

**Mission:** MISSION-006 (ask-chatgpt). **Leg:** T1b. **Type:** implement (core driver + tests), single editor, test-driven.
**You inherit NOTHING but this file + the files it tells you to read.** Read them; do not assume.
**Real messages this leg: ZERO.** T1b never contacts chatgpt.com/openai. Everything here is mock/loopback/throwaway-browser only.

## Why this leg exists (context you must honor)

The operator chose to enable real-site automation by **attaching Playwright to their OWN already-running, signed-in Chromium over the Chrome DevTools Protocol (CDP)** — NOT by launching an automated browser (Cloudflare blocks those) and NOT by any stealth/evasion (explicitly forbidden). During a real run the operator runs, themselves:
`chromium --profile-directory='Profile 1' --remote-debugging-port=9222`
Your job in T1b is to build + test the `channel="cdp"` attach mechanics **entirely against a throwaway local browser + the existing mock fixture**, so that no real-site contact is needed to prove the plumbing. Real legs (T2/T3) come later, run by the manager, gated on the operator's browser being up.

## Files to READ FIRST (ground truth — verify current contents; line numbers may drift)

- `src/ask_chatgpt/driver.py` — the core. Current shape you must integrate with:
  - `BrowserSession.__init__` (around line 71): params `channel="mock"`, `base_url`, `profile_path`, `executable_path`, `maps_dir`, `grant_clipboard`.
  - `start()` (around 104-128): for `channel=="real"` it calls `_ensure_real_selector_map_ready()` + `_preflight_profile_lock()` BEFORE `sync_playwright().start()`, then dispatches `_start_mock_context` / `_start_real_context` / else `AskChatGPTError("Unsupported channel ...")`, then `_new_or_existing_page()`, then `page.goto(self._base_url, ...)`, then for real `_raise_login_required_for_auth_redirect(page.url)`.
  - `_new_or_existing_page()` (around 352-355): returns `context.pages[0] if context.pages else context.new_page()`. **CRITICAL: for CDP this is WRONG — `pages[0]` is the operator's tab. The cdp path must ALWAYS open a brand-new tab and track it.**
  - `_start_real_context()` (around 331-350): `launch_persistent_context(user_data_dir, headless=False, accept_downloads=True, [executable_path])` then `install_real_allowlist(self._context, on_abort=self.aborted_off_domain_hosts.append)`.
  - `_install_mock_route_guard()` (around 292-302): loopback-only route guard (continue if `_is_loopback_request_url`, else `route.abort`).
  - `_resolve_base_url()` (around 357-): `channel=="real"` -> `REAL_BASE_URL`; else `base_url or ""`.
  - `_raise_login_required_for_auth_redirect()` (around 316-329): raises `LoginRequiredError` on auth/login URL shapes. Reuse for cdp.
  - Note helpers `_is_loopback_http_url` / `_is_loopback_request_url` exist in this module — reuse them.
- `src/ask_chatgpt/errors.py` — existing `LoginRequiredError`, `ProfileLockedError`, `SelectorUnavailableError`, `AskChatGPTError`, `RateLimitedError`, etc. You will ADD new named errors here (below).
- `src/ask_chatgpt/real_allowlist.py` — `install_real_allowlist(context, allowed_domains=DEFAULT_REAL_ALLOWED_DOMAINS, on_abort=None)`; `DEFAULT_REAL_ALLOWED_DOMAINS = (chatgpt.com, openai.com, oaistatic.com, oaiusercontent.com)`.
- `src/ask_chatgpt/selector_maps/real.json` — all-empty fail-closed template. **DO NOT EDIT IT in T1b.** It stays empty/fail-closed (T2/T2b populate it later).
- `tests/conftest.py` — autouse session socket guard (loopback/AF_UNIX only; never weaken it); `pytest_collection_modifyitems` skips `real_site`-marked tests unless `ASK_CHATGPT_REAL=1`; `mock_chatgpt` fixture = `MockChatGPTServer().start().make_handle()`.
- `tests/fixtures/mock_chatgpt/` (package) — `MockChatGPTServer`: `.start()`, `.make_handle()` -> handle with `.base_url`, `.reset()`, `.script_next_response(answer, failure_mode=...)`, `.stop()`. Loopback, ephemeral port. **Reuse this** to serve the fixture for the throwaway-browser CDP test.
- `tests/test_driver.py` — happy-path mock UC1 pattern (see `test_driver_happy_path_returns_latest_completed_turn`, ~line 22; uses `session.open_or_create_conversation(None)` then `send_prompt`/turn read). **Line ~19** defines `REAL_SELECTOR_MAP_PATH = Path("src/ask_chatgpt/selector_maps/real.json")`; **the test at ~line 150** `test_real_selector_template_is_all_empty_and_fails_closed()` reads that LIVE path and asserts every selector/attribute is `""`. THIS IS THE COUPLING TO FIX (below).
- `tests/test_driver_real_preflight.py`, `tests/test_driver_real_failclosed.py`, `tests/test_real_tier_gating.py`, `tests/test_real_allowlist.py` — existing real-tier test patterns to match for style.
- `pyproject.toml` — `real_site` marker + `addopts` deselection; dependency groups. Run `uv sync --all-groups` before testing.

## Deliverables (all REQUIRED)

### D1 — `channel="cdp"` attach in `driver.py`
1. Accept a configurable CDP endpoint. Add a constructor param, e.g. `cdp_endpoint: str | None = None`, defaulting (when channel is cdp and param is None) to `http://127.0.0.1:9222`. The port MUST be overridable (the test uses an ephemeral port).
2. `start()` for `channel=="cdp"`: do NOT launch a browser. Use `self._playwright.chromium.connect_over_cdp(<endpoint>)` to attach to the EXISTING browser. Obtain the existing context (`browser.contexts[0]`, the operator's default context — it already holds the operator's pages).
3. **New-tab discipline (hard invariant):** for ALL tool activity open a BRAND-NEW page via `context.new_page()` and store it as `self.page`. NEVER reuse `context.pages[0]` / any pre-existing page (those are the operator's). Do this by giving cdp its own page-acquisition path — do NOT route cdp through `_new_or_existing_page()` (which returns `pages[0]`).
4. Navigate the new tab to `self._base_url`. `_resolve_base_url` for cdp: if a `base_url` was provided, use it (this is how the test points cdp at the loopback mock fixture); else default to `REAL_BASE_URL` (chatgpt.com — production). 
5. Route guard / domain allowlist:
   - When `self._base_url` is loopback (the test) -> install the loopback guard (same logic as mock; loopback continue, else abort). The loopback fixture MUST load and UC1 MUST work through it.
   - When `self._base_url` is the real site (production cdp) -> `install_real_allowlist(...)` exactly as the real path does.
   (Pick by `_is_loopback_http_url(self._base_url)`. Keep tier purity: a cdp session pointed at loopback must never be able to reach a non-loopback host.)
6. **close()/detach (hard invariant):** closing a cdp session must close ONLY the tab(s) THIS session opened, then DETACH from the browser **without quitting it and without touching the operator's pre-existing tabs**. Do NOT call `browser.close()` on a CDP-attached browser (Playwright would close the whole browser — that would kill the operator's browser). Stop/dispose the playwright object so the connection drops, after closing only your own page. The tab-hygiene test (T-CDP-2) is the proof; implement close() to make it pass.

### D2 — Named preflights / errors in `errors.py` + wired in `driver.py`
- `CDPUnreachableError` (subclass `AskChatGPTError`): raised when `connect_over_cdp` fails / connection refused. Message MUST contain the exact actionable launch command: `chromium --profile-directory='Profile 1' --remote-debugging-port=9222`. (Token `CDP_UNREACHABLE` may appear in the message for log-grep.)
- `ChallengePresentError` (subclass `AskChatGPTError`): raised when, after navigating the real site, a Cloudflare/human-verification challenge is detected (e.g. page `title` is "Just a moment…" or a `#challenge-running` / `iframe[src*=challenges.cloudflare.com]` marker is present and the app/login never renders within a bounded settle). Message token `CHALLENGE_PRESENT`. (The MANAGER/runbook handles the human-pause; the driver just raises the named state. Detection is the driver's job; the pause loop is NOT.)
- Login page -> reuse existing `LoginRequiredError` via `_raise_login_required_for_auth_redirect`.
- Only the cdp path raises these; mock/real paths are unchanged.

### D3 — DECOUPLE the fail-closed test from the live real.json (`test_driver.py:~150`)
Currently `test_real_selector_template_is_all_empty_and_fails_closed()` reads the LIVE `src/ask_chatgpt/selector_maps/real.json` and asserts all-empty. Once T2 populates real.json with discovered selectors this test will FAIL. Fix it WITHOUT weakening the fail-closed guarantee:
- Add a dedicated **empty-map fixture** file (e.g. `tests/fixtures/selector_maps/real_empty.json`) holding the full all-empty fail-closed schema (same channel/selectors/attributes keys, all values `""`).
- Repoint the test to load THAT fixture (via `load_selector_map("real", maps_dir=<fixture dir>)` or equivalent) and assert the fail-closed BEHAVIOR (empty map -> `SelectorUnavailableError` on `.selector()`/`.attribute()`), independent of whatever the live real.json holds.
- It is fine to KEEP a separate, explicit assertion that the live template is *currently* empty IF you want, but the behavior test must not break when real.json is later populated. The cleanest: behavior test uses the fixture; drop/relax the live-file all-empty coupling. Use your judgement; the success criterion is: this suite stays green both now (real.json empty) AND hypothetically if real.json had real selectors.

### D4 — Tests (DEFAULT-TIER; loopback/throwaway only; NOT marked `real_site`)
Put new tests in a new file, e.g. `tests/test_driver_cdp_attach.py`. They MUST run under a clean `uv run pytest` (no `ASK_CHATGPT_REAL`). They use a **throwaway Chromium subprocess** you launch with `--remote-debugging-port=<EPHEMERAL>` and `--user-data-dir=<unique tmp dir>` (headed or headless both fine for the throwaway; `--headless=new` is fine; add `--no-first-run --no-default-browser-check`). Find a FREE ephemeral port at runtime (bind a socket to port 0, read it, close — NEVER hardcode a port; the charter forbids assuming a fixed port is free). Wait for the CDP endpoint to be ready (poll `http://127.0.0.1:<port>/json/version` over loopback until it responds, with a bounded timeout) before attaching. ALWAYS tear down: terminate the throwaway subprocess and remove its tmp user-data-dir in a finally/fixture teardown, even on failure.

Required test scenarios:
- **T-CDP-0 (unreachable preflight):** `BrowserSession(channel="cdp", cdp_endpoint="http://127.0.0.1:<closed-port>")` -> `start()` raises `CDPUnreachableError` whose message contains the launch command. (No throwaway browser needed; just a port with no listener.)
- **T-CDP-1 (attach + UC1 through the real attach path):** start `MockChatGPTServer` (loopback url); launch throwaway chromium (ephemeral debug port); `BrowserSession(channel="cdp", base_url=<mock base_url>, cdp_endpoint="http://127.0.0.1:<ephemeral>")`; attach; assert a NEW tab was opened (not the operator's); drive the mock UC1 happy path (`open_or_create_conversation(None)` + scripted `send_prompt` -> latest completed turn equals the scripted answer) THROUGH the CDP-attached browser. Prove `session.page.url` is the loopback fixture and contains no `chatgpt.com`.
- **T-CDP-2 (tab hygiene — the core safety proof):** in the throwaway browser, open a PRE-EXISTING tab first (e.g. a second loopback page or `about:blank`) and record it; then run a cdp `BrowserSession` (open new tab, do UC1), then `session.close()`. Assert: (a) the throwaway browser is STILL ALIVE; (b) the pre-existing tab is STILL OPEN and was never navigated/closed; (c) the tool's own tab was closed; (d) the cdp close() did NOT quit the browser. (Inspect via a fresh `connect_over_cdp` query of the same throwaway, or via the retained CDP browser handle, depending on what cleanly proves it.) THEN the fixture terminates the throwaway subprocess.
- **T-CDP-3 (optional but encouraged — challenge/login detection without the real site):** serve a tiny loopback page whose `<title>` is "Just a moment…" (or carries a cloudflare challenge marker) and point a cdp session at it -> assert `ChallengePresentError`. Similarly a loopback page that redirects to a `/auth/login`-shaped URL -> `LoginRequiredError`. (If detection is title/URL-based this is straightforward and gives real coverage with zero real-site contact. If you cannot make it deterministic, document why and cover the detection logic with a direct unit test of the predicate instead.)

### D5 — Suite green + tier purity preserved
- `uv sync --all-groups` first. Run the FULL default suite: `uv run pytest` (serialize; do not run two pytest invocations concurrently). It must be GREEN. Capture the exact summary line (e.g. "N passed, M deselected") into your report.
- Default-tier purity: clean `uv run pytest` must still collect ZERO `real_site` tests (your new cdp tests are NOT `real_site` — they are loopback/throwaway). The autouse socket guard must be UNCHANGED and still active. `real.json` must be UNCHANGED (still all-empty).
- Confirm (and state in the report) that `git diff --stat` touches only: `driver.py`, `errors.py`, the new test file, the new empty-map fixture, the edited `test_driver.py`, and (if needed) a tiny loopback challenge/login fixture — and NOT `real.json`, NOT `conftest.py`'s guard logic (you may not need to touch conftest at all), NOT `.claude/`, NOT `.agents/`.

## SAFETY BLOCK — obey verbatim (you inherit nothing)
- Real-site contact is permitted ONLY in T2/T3 legs (NOT this leg). T1b contacts NOTHING real: mock fixture + throwaway local browser only. Default-tier tests stay loopback-only; the autouse socket guard must NEVER be weakened.
- NEVER automate, test, or touch login/logout. NEVER read/copy/store/log credentials, cookies, session tokens, or browser-profile contents. No account identifiers (email, name, org) in any report, artifact, code, or commit.
- Do not kill the operator's browser; do not delete lock files. (In T1b you only ever start/stop YOUR OWN throwaway browser subprocess — never the operator's.)
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive READ-ONLY. Never write `.claude/` / `.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. Use EPHEMERAL ports (never assume a fixed port is free). NEVER `git push`. Do NOT commit (the manager commits the slice after independent verification).
- ESTIMATE BEFORE EXECUTE: before any heavy command (test runs, browser launches), state expected wall-clock + output volume; keep runs bounded.

## Reporting (write to `orchestration/reports/M-006/T1b.md`, cap ~250 lines)
Include, in order:
1. `START_TIMESTAMP:` and `END_TIMESTAMP:` (`date -Iseconds`), and `ESTIMATE: T1b <min>m`.
2. What you changed (files + the key invariants for cdp: new-tab discipline, close()=detach-not-quit, base_url-driven guard, named preflights).
3. The exact authoritative `uv run pytest` summary line + how many cdp tests ran + confirmation ZERO real_site collected by default.
4. `git diff --stat` of your change (prove real.json untouched; no out-of-scope files).
5. Anything you could NOT prove deterministically (e.g. if T-CDP-3 challenge detection had to fall back to a predicate unit test) — be honest.
6. Any design decision where you deviated from this contract and why.
7. `MESSAGES_USED: 0` (mock-only leg).
- LAST LINE of the report MUST be exactly: `T1b-STATUS: DONE` (or `T1b-STATUS: BLOCKED` with the precise blocker).
