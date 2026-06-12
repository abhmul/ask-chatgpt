# T1 — Real test-tier plumbing (single editor, mock-only, TDD/RED-first)

You are a fresh pi worker. You inherit NOTHING except this file and the files it names. Everything you need is below. Do the parts IN ORDER. Each behavioral part is RED-first: write the failing test, run it RED, then implement, then run it GREEN. End with a full-suite green gate.

This entire task is MOCK-ONLY / NETWORK-FREE. You must NEVER contact chatgpt.com, openai.com, or any external network. No real browser launch against the real site. Every new test must pass with the autouse loopback socket guard active and use fakes/monkeypatched Playwright — never a real network or real profile.

## Repo orientation (read these first, in this order)

1. `pyproject.toml` — currently has NO `[tool.pytest.ini_options]` section at all.
2. `tests/conftest.py` — autouse session-scoped loopback-only socket guard (`_network_guard`, lines 26-58) and fixtures (`socket_guard_active`, `mock_chatgpt`). DO NOT weaken the guard.
3. `src/ask_chatgpt/errors.py` — named exception hierarchy. `AskChatGPTError` is the base; `LoginRequiredError` and `SelectorUnavailableError` already exist. There is NO profile-lock error class yet.
4. `src/ask_chatgpt/driver.py` — `BrowserSession`. Read it fully. Key facts you MUST preserve:
   - `start()` (lines 98-119): for `channel=="real"` it calls `self._ensure_real_selector_map_ready()` (line 102) BEFORE `sync_playwright().start()`. This is the D2 fail-closed safety property: an all-empty `real.json` must raise `SelectorUnavailableError` with ZERO browser/navigation side effects. DO NOT BREAK THIS. Your new real-channel preflight steps must compose around it, not remove it.
   - `_start_real_context()` (lines 301-312): calls `launch_persistent_context(user_data_dir=str(self._profile_path), headless=False, accept_downloads=True)`. It has NO `executable_path`. Its `except Exception` currently swallows everything into a generic `AskChatGPTError`.
   - `_install_mock_route_guard()` (lines 283-293): the mock-channel loopback-only route guard (allow loopback, `route.abort("blockedbyclient")` otherwise). Your real-tier allowlist is the analogue for the real channel.
   - `_resolve_base_url` forces real channel base to `REAL_BASE_URL == "https://chatgpt.com"`.
5. `src/ask_chatgpt/selector_maps/real.json` — all-empty fail-closed template. DO NOT POPULATE IT (a later task does). It must stay all-empty so D2 fail-closed and the default suite stay correct.

## Part A — `real_site` pytest marker + default deselection (pyproject.toml)

Add a `[tool.pytest.ini_options]` section to `pyproject.toml`:
- Register the marker: `markers = ["real_site: real chatgpt.com tests; deselected by default and gated on ASK_CHATGPT_REAL=1"]`.
- Default-deselect it: `addopts = "-m 'not real_site'"` (use the TOML form that yields pytest deselecting `real_site` on a bare `uv run pytest`). If you prefer a list form, `addopts = ["-m", "not real_site"]` is acceptable. Confirm `--strict-markers` is NOT introduced in a way that breaks existing unmarked tests; keep it minimal.
- Keep `testpaths`/rootdir behavior consistent with the current implicit layout (tests live in `tests/`). Do not relocate tests.

## Part B — `ASK_CHATGPT_REAL=1` double-gate + guard tests (conftest + tests)

The real tier must require BOTH conditions: the `real_site` marker is deselected by default (Part A) AND, even if explicitly selected, real_site tests SKIP unless `ASK_CHATGPT_REAL=1`.

1. In `tests/conftest.py`, add a `pytest_collection_modifyitems(config, items)` hook: for every item carrying the `real_site` marker, if `os.environ.get("ASK_CHATGPT_REAL") != "1"`, attach `pytest.mark.skip(reason="real_site requires ASK_CHATGPT_REAL=1 (opt-in real tier, D-002)")`. (Import `os`/`pytest` as needed; do not disturb the socket guard.)
2. Add a tiny sample real_site test so the gating is real, e.g. `tests/test_real_tier_gating.py` containing one `@pytest.mark.real_site` test that would FAIL if it ever ran without the env (e.g. `assert os.environ.get("ASK_CHATGPT_REAL") == "1"`), proving it is skipped, not executed, by default.
3. Add the GUARD test (NOT marked real_site) that proves the default run collects/keeps ZERO real_site tests. Robust mechanism: run pytest collection in a SUBPROCESS from the repo root with a clean env and assert no real_site node is selected. Concretely, in the guard test:
   - `import subprocess, sys`
   - Run `subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=<repo root>, env={**os.environ minus ASK_CHATGPT_REAL}, capture_output=True, text=True)`.
   - Assert the sample real_site test's nodeid (e.g. `test_real_tier_gating.py`) does NOT appear in stdout, i.e. it was deselected by the default `-m 'not real_site'` addopts.
   - Also assert a known ordinary test (e.g. something in `tests/test_driver.py`) IS present, so the guard can't pass vacuously by collecting nothing.
   - To avoid recursion/timeouts, this subprocess inherits the project's addopts (that is the point — it proves the default config deselects). Keep a generous but bounded timeout (e.g. 120s) and serialize (no xdist).
   - The subprocess must run loopback-only; `--collect-only` does not execute tests so it will not contact the network. Do not pass `-m real_site`.

RED-first: write B's guard + sample tests FIRST. Before adding the marker/addopts/hook, the guard assertion (real_site nodeid absent from default collection) will FAIL because without Part A the sample test is collected (and without the marker registered pytest may warn/error). Capture that RED. Then implement Parts A+B and capture GREEN.

## Part C — real-tier browser-level domain allowlist (route interception, abort + log off-domain)

The default tier keeps the socket guard. The real tier instead needs a browser-level domain ALLOWLIST so a real session cannot wander off-domain. Build the MECHANISM now with a sensible default allowlist; a later task extends the asset-domain list from empirical discovery.

1. New module `src/ask_chatgpt/real_allowlist.py`:
   - `DEFAULT_REAL_ALLOWED_DOMAINS`: a tuple of base domains. Seed it with the obvious ones: `"chatgpt.com"`, `"openai.com"`, `"oaistatic.com"`, `"oaiusercontent.com"`. (These are starting values; a discovery task will append verified asset/CDN domains. Do NOT claim these are exhaustive.)
   - `host_allowed(host: str | None, allowed_domains) -> bool`: True iff `host` equals an allowed domain OR is a subdomain of one (suffix match on a dot boundary, case-insensitive). `None`/empty host -> False.
   - A route-guard installer `install_real_allowlist(context, allowed_domains=DEFAULT_REAL_ALLOWED_DOMAINS, on_abort=None) -> None` that registers `context.route("**/*", guard)` where `guard` continues allowed-host requests and `route.abort("blockedbyclient")` for the rest.
   - SAFETY: when logging/recording an aborted request, record the HOST ONLY (and at most the URL scheme) — NEVER the full URL or query string (query params can carry auth tokens/secrets). Use stdlib `logging` (logger `"ask_chatgpt.real_allowlist"`, level WARNING) for the abort, and also invoke the optional `on_abort(host)` callback so callers/tests can collect aborted hosts. Non-http(s)/ws(s) schemes (e.g. `data:`, `blob:`) should be allowed (they are not network egress) — mirror the spirit of the mock guard's scheme handling.
2. Wire it into the real channel: in `_start_real_context()` (or right after the context is created in `start()` for the real channel, BEFORE `page.goto`), call `install_real_allowlist(self._context, ...)`. Store aborted hosts on the session (e.g. `self.aborted_off_domain_hosts: list[str]`) via the `on_abort` callback so they are inspectable. Do NOT install this on the mock channel (mock keeps its loopback guard).

RED-first: unit-test `real_allowlist.py` directly with a FAKE route/request object (no real browser):
- `host_allowed` truth table: `chatgpt.com` allowed; `cdn.oaistatic.com` allowed (subdomain); `evil.com` denied; `notchatgpt.com` denied (must not match via naive substring); `None` denied.
- A fake `route` whose `request.url` is an off-domain `https://evil.example/x?token=SECRET` is `.abort()`-ed and the recorded host is exactly `evil.example` with NO `token`/query captured anywhere; an on-domain `https://chatgpt.com/...` is `.continue_()`-ed.
Write these RED (module doesn't exist yet) -> implement -> GREEN.

## Part D — profile-lock preflight -> named error (errors.py + driver.py)

1. In `errors.py`, add `class ProfileLockedError(AskChatGPTError)` with an actionable default_message like: "ChatGPT browser profile appears to be in use by a running browser (profile lock held). Operator action: close the running Chromium using this profile, then re-run; this tool never deletes lock files or kills your browser." Add it to `__all__`.
2. In `driver.py`, add a profile-lock preflight for the real channel that raises `ProfileLockedError`:
   - A small helper, e.g. `_preflight_profile_lock(self)`: if a `SingletonLock` entry exists in `self._profile_path` (hint that a browser holds the profile), raise `ProfileLockedError`. (Detect via `Path(self._profile_path) / "SingletonLock"` existing as a path/symlink — use `.exists()` OR `.is_symlink()`; a broken symlink still indicates a lock attempt, so prefer `os.path.lexists`.) Do NOT delete it. Do NOT kill any process.
   - Call this preflight in `start()` for `channel=="real"` AFTER `_ensure_real_selector_map_ready()` (keep D2 first) and BEFORE `sync_playwright().start()`, so a locked profile fails with ZERO browser side effects.
   - ALSO map the authoritative launch failure: in `_start_real_context()`, if `launch_persistent_context` raises an error whose message indicates the profile is already in use / singleton lock (case-insensitive match on tokens like "singleton", "already in use", "ProcessSingleton", "profile" + "lock"), re-raise as `ProfileLockedError` instead of the generic `AskChatGPTError`. Other launch failures keep the existing generic error.

RED-first (network-free):
- Helper test: create a tmp dir, `touch <tmp>/SingletonLock`, call the preflight (or `start()` with a POPULATED fake selector map so D2 passes — see note below) and assert `ProfileLockedError`. With NO SingletonLock, the preflight does not raise.
- Note on D2 ordering: to exercise the lock path through `start()`, you need the real selector map readiness to PASS first. Do this WITHOUT touching the committed `real.json`: pass a `maps_dir` pointing at a tmp dir containing a fully-populated `real.json` (all 20 selectors + 2 attributes non-empty dummy strings) so `_ensure_real_selector_map_ready()` passes, then the locked profile trips `ProfileLockedError`. Combine with a fake `sync_playwright` so no real browser is launched, and assert no `goto` occurred. Alternatively test `_preflight_profile_lock` in isolation — but ALSO add at least one ordering test proving lock is detected before any browser launch.

## Part E — logged-out URL/redirect heuristic -> LoginRequiredError (driver.py)

After the initial navigation in `start()` for the real channel, add a SELECTOR-INDEPENDENT logged-out check: inspect the resulting `page.url`; if it indicates an auth/login redirect, raise `LoginRequiredError`. This complements the existing selector-based `_raise_open_failures()` login_wall check (which needs a populated selector).

- Heuristic: parse `page.url`; if the host or path matches known login/auth shapes — host containing `auth.openai.com` or `auth0` or `accounts.`, OR path starting with `/auth/login`, `/auth`, `/login`, or containing `/api/auth/` — raise `LoginRequiredError`. Keep the match conservative to avoid false positives on normal `chatgpt.com/` or `chatgpt.com/c/<ref>` URLs.
- SAFETY: inspect only URL host/path; never read cookies/storage/credentials. When logging, log only host + path-shape, never the full URL with query.
- Placement: in `start()`, for `channel=="real"`, immediately after the `page.goto(self._base_url, ...)` succeeds. (Do not add this to the mock channel.)

RED-first (network-free): fake `sync_playwright` whose page `.goto()` sets `page.url` to `https://auth.openai.com/authorize?...` -> assert `start()` raises `LoginRequiredError`; a fake whose page `.url` is `https://chatgpt.com/` -> assert NO `LoginRequiredError` from this check (it may proceed/return). Use a populated fake `maps_dir` so D2 passes and you reach navigation. No network.

## Part F — `executable_path` knob for the real channel (driver.py)

The env has a Playwright-bundled-chromium vs system-Chromium profile mismatch risk; a later real-site task will need to launch the SYSTEM binary (`/usr/bin/chromium`) against the system profile. Thread an optional knob now.

- Add `executable_path: str | Path | None = None` to `BrowserSession.__init__`, store it.
- In `_start_real_context()`, pass `executable_path=str(self._executable_path)` to `launch_persistent_context(...)` ONLY when it is not None; when None, call as today (no `executable_path` kwarg, or pass `executable_path=None` if Playwright treats that as default — verify Playwright 1.60.0 accepts `executable_path=None`; if unsure, branch to omit it).
- Do NOT change the mock channel.

RED-first (network-free): a fake `sync_playwright` recording the kwargs passed to `launch_persistent_context`. Assert: when `executable_path="/usr/bin/chromium"` is set, the recorded kwargs include `executable_path == "/usr/bin/chromium"`; when unset, `executable_path` is absent or None. No real browser.

## FULL-SUITE GREEN GATE (mandatory, last)

After all parts: `uv sync --all-groups` then `uv run pytest` (ALL tests, serialized — no `-n`/xdist). It MUST be fully green. The suite was 121 passed at baseline; with your new tests it should be >121 passed, 0 failed, and the sample real_site test must show as DESELECTED/skipped (not run, not failed) in the default run. Paste the final summary line and exit code. Also run `uv run pytest -q 2>&1 | tail -5` style capture for the report.

## Constraints / SAFETY (transcribed verbatim — obey exactly)

- MOCK-ONLY / NETWORK-FREE. Automated tests + ALL of this task NEVER contact chatgpt.com/openai or any external network; loopback/local only. Every new test runs with the autouse socket guard active and uses fakes/monkeypatched Playwright. No test/script sets `channel="real"` against the real site. `selector_maps/real.json` STAYS the all-empty template — do not populate it.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The profile path is opaque config. Aborted-request and login logging must record HOST + path-shape ONLY, never full URLs/query strings (they can carry tokens). No account identifiers anywhere.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Do NOT write `.claude/` or `.agents/`. Do NOT touch the shared agent venv (`~/.local/share/agent-python/.venv`); use `uv run`/`uv sync` from the repo root. `uv sync --all-groups` ALWAYS before any `uv run`. Serialize pytest. Ephemeral ports only. Kill only processes your own run starts. NEVER `git push`.
- Preserve the D2 property: empty `real.json` + `channel="real"` still raises `SelectorUnavailableError` before ANY browser/navigation side effect. Add an explicit test asserting your new code did not regress this (start() on the committed empty real.json raises SelectorUnavailableError and never launches/navigates).
- Occam: minimal surgical changes. No driver redesign. Reuse existing patterns (the mock route guard is your template for the real allowlist).
- ESTIMATE BEFORE EXECUTE: state expected wall-clock before running the full suite.

## Commit

Commit all T1 changes together with a message starting `M-006: ` (e.g. `M-006: T1 real test-tier plumbing — real_site marker+double-gate, real allowlist, profile-lock + logged-out preflight, executable_path knob`). Commit ONLY: `pyproject.toml`, `tests/conftest.py`, the new/changed test files under `tests/`, `src/ask_chatgpt/errors.py`, `src/ask_chatgpt/driver.py`, and the new `src/ask_chatgpt/real_allowlist.py`. Do NOT commit `.pi-workers/`, `tmp/`, venvs, or `real.json`. Report the commit SHA.

## Telemetry + report (write to `orchestration/reports/M-006/T1.md`, cap ~250 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T1 <minutes>m`.
- Body, in order, for EACH of Parts A-F: the RED run output (failing pre-implementation), a 1-2 line description of the change, the GREEN run. Then: the FULL-suite green summary + exit code, confirmation the sample real_site test was DESELECTED by default, confirmation the D2 empty-real.json fail-closed regression test passes, and the commit SHA.
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T1-STATUS: DONE` (or `T1-STATUS: BLOCKED` with the exact blocker).
