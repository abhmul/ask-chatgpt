# Contract M7-T1a — CDP action path + AdaptiveSendBudget + TabPool idle-TTL (OFFLINE editor)

You are a **single pi editor worker** for `ask-chatgpt-dev`, task **M7-T1a**. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. You inherit **nothing** but this contract and the files it names. **First read and obey** `.claude/skills/manager/references/agent-rigor.md` and the `tdd` skill (`.claude/skills/tdd/SKILL.md`). This is **OFFLINE** work — **no browser, no network, no real sends** — mock/unit-proven only.

## Mission
Implement three offline pieces of the M7 build, **TDD (red→green per behavior, vertical slices — NOT all-tests-then-all-code)**, mock/unit-proven:
1. **CdpChannel action path** — `fill` / `insert_text` / `click` / `hover` / `press` / `upload_files` (today they all `raise HumanActionNeededError("CDP action/send path deferred to M7; M5 is read-only")`). Mirror the **real-proven** `issues/cdp-send-repro/controller.mjs`.
2. **AdaptiveSendBudget** — politeness floor + AIMD + multiplicative backoff + hard-pause; **NO hard message cap**.
3. **TabPool idle-TTL eviction** — keep existing lazy-open/LRU/own-tabs-only; add idle-TTL eviction.

`uv run pytest` MUST stay green (baseline **212 passed**, offline, <1s) and the **whole suite must remain offline and fast (target < 3s)** — do not introduce real `time.sleep`.

## READ FIRST (authoritative inputs)
- `.claude/skills/manager/references/agent-rigor.md` and `.claude/skills/tdd/SKILL.md` — obey both.
- `issues/cdp-send-repro/controller.mjs` — the **REAL-PROVEN** CDP send reference. **Read-only; do NOT edit it** (another agent is actively using it; it is intentionally dirty in git). Key blocks: `stateExpr` (lines ~108–128), `sendOnce` fill+click (lines ~239–258), `confirmViolation` (lines ~145–153).
- `src/ask_chatgpt/channels/cdp.py` — the `CdpChannel` you will extend (action stubs at lines ~518–536 and `upload_files` ~661–663; `evaluate` at ~491–505; `JS_QUERY_TURNS` ~115–141; the `playwright_factory`/fake-page injection seam).
- `src/ask_chatgpt/channels/base.py` — the `BrowserChannel` Protocol (signatures you must match) + `TabLease`.
- `src/ask_chatgpt/channels/mock.py` — the `MockChannel` (already implements fill/click/press/etc.) + `ScriptedClock` (fake monotonic/sleeper) you use for deterministic timing tests.
- `src/ask_chatgpt/session.py` — `TabPool` (lines ~59–123), `AdaptiveSendBudget` (lines ~126–161), and how `Session.__init__` constructs them (~197–198). `Session.ask` uses `self.send_budget.submission()` (~278) and `self.tab_pool.acquire/release`.
- `src/ask_chatgpt/send.py` — how the channel actions are CALLED: `fill_composer`→`channel.fill` then reads back via `channel.evaluate(tab, "ask_chatgpt_send_read_composer_text", arg={"selector":...})` (lines ~112–121, ~207–214); `submit_composer`→`channel.click(tab, selectors["send_button_unverified_no_input"])` (~124–126). **Your CdpChannel must make that readback evaluate work** (see Part 1).
- `src/ask_chatgpt/errors.py` — exception taxonomy: `HumanActionNeededError`, `SelectorNotFoundError`, `PromptNotSubmittedError`, `AskChatGPTError`.
- `tests/test_cdp_channel.py` — the existing **fake-Playwright** test pattern (how a stub page/context is injected via `playwright_factory` and `attach()`/`open_tab()`); follow it for your action tests.
- `tests/test_session_stubs.py`, `tests/mock_scenarios.py`, `tests/conftest.py` — existing Session/mock test patterns.

## Part 1 — CdpChannel action path (mirror controller.mjs)
Replace the six `raise HumanActionNeededError(...)` action stubs with real Playwright-over-CDP implementations that act **only on the passed `TabLease`'s own page** (validate via `self._validate_tab_state(tab)`), **never** enumerate `context.pages`, **never** open/quit the browser, **no stealth**. Keep import-safety (Playwright is only obtained in `attach()`; these methods use `state.page` which already exists).

- **`fill(tab, selector, text)`** — mirror controller.mjs `sendOnce` fill: focus the element, `document.execCommand('selectAll'); document.execCommand('delete'); document.execCommand('insertText', false, <text>)`, then dispatch `new InputEvent('input', {bubbles:true, inputType:'insertText', data:<text>})`. Run it via `state.page.evaluate(<js>, {selector, text})`. Pass `text` as a JS arg (do NOT string-interpolate into the JS source). Do not assert success here — `send.fill_composer` verifies the readback.
- **`evaluate` readback** — add a branch in `CdpChannel.evaluate`: when `js == "ask_chatgpt_send_read_composer_text"`, run real JS `(a) => { const c = document.querySelector(a.selector); return c ? (c.innerText || c.textContent || c.value || '') : ''; }` with `arg`. (Today CDP would try to eval the literal string as JS and throw — `send.fill_composer`'s verify depends on this working.)
- **`insert_text(tab, selector, text)`** — like `fill` but append (no selectAll/delete): focus, `execCommand('insertText', ...)`, dispatch InputEvent.
- **`click(tab, selector)`** — mirror controller.mjs send-click: in-page, query `selector` (it may be a comma-list e.g. `button[data-testid="send-button"], #composer-submit-button`), filter to **visible** (`getComputedStyle.display!=='none' && visibility!=='hidden' && getBoundingClientRect().width>0 && height>0`) **and enabled** (`!disabled && aria-disabled!=='true' && !hasAttribute('disabled')`), click the first such element. If none visible+enabled → raise `SelectorNotFoundError(details={"selector": selector})` (so a no-op send surfaces as `PromptNotSubmittedError` upstream). Keep `click` general — it is also used by menus in T1b.
- **`hover(tab, selector)`** — `state.page.hover(selector)` (Playwright), first match.
- **`press(tab, selector, key)`** — `state.page.press(selector, key)` (used as an Enter fallback only while the composer is focused; the primary submit path is `click`).
- **`upload_files(tab, selector, paths)`** — `state.page.set_input_files(selector, [str(p) for p in paths])` against the (hidden) file input. Structural only; not exercised by real legs.

**Offline tests (no browser):** follow `tests/test_cdp_channel.py`'s fake-Playwright injection. Add a fake page that records `evaluate`/`hover`/`press`/`set_input_files` calls and returns scripted values. Assert (these MUST be able to fail):
- `fill` calls `page.evaluate` with JS containing `execCommand` + `insertText` and passes `text` as the **arg**, not interpolated.
- `evaluate("ask_chatgpt_send_read_composer_text", {selector})` returns the fake composer text (round-trips through a real JS function string).
- `click` evaluates JS that filters visible+enabled and clicks; when the fake reports no enabled match, `click` raises `SelectorNotFoundError`.
- none of the six methods raises `HumanActionNeededError` anymore (the M5 "deferred" guard is gone).
- own-tab-only preserved: calling an action with a `TabLease` from a different/closed tab still raises `ValueError` via `_validate_tab_state`; no method touches `context.pages`.

## Part 2 — AdaptiveSendBudget (politeness floor + AIMD + backoff + hard-pause; NO hard cap)
Rewrite `AdaptiveSendBudget` (keep the class name, the `submission()` contextmanager, `successful_submissions`, `snapshot()`, and the `PromptBudgetBusyError` so `Session.ask` keeps working). Make it the **single owner** of the account send-rate budget on the persistent `Session`. Per M3 §7 (transcribed):
- Constructor knobs (defaults are **unmeasured assumptions**, not an account ceiling): `politeness_floor_s=5.0`, `initial_rate_per_min=3.0`, `max_rate_per_min=12.0`, `additive_increase_per_min=1.0`, `backoff_factor=0.5`, `min_rate_per_min=0.5`. Inject `monotonic` + `sleeper` callables (default `time.monotonic`/`time.sleep`).
- **Spacing**: required spacing before a submission = `max(politeness_floor_s, 60.0/current_rate_per_min)`. In `submission()`, sleep (via the injected sleeper) until `last_submission_monotonic + spacing` before yielding. **Non-bursting**: bucket capacity 1 — never allow a burst; serialize one submission at a time (keep the busy guard raising `PromptBudgetBusyError`).
- **AIMD**: on each verified success (the `yield` returns without exception), `current_rate_per_min = min(max_rate_per_min, current_rate_per_min + additive_increase_per_min)`, increment `successful_submissions`, record `last_submission_monotonic`. The politeness floor is a **hard floor** — effective spacing never drops below `politeness_floor_s` regardless of rate.
- **`record_soft_signal(kind: str)`**: multiplicative backoff `current_rate_per_min = max(min_rate_per_min, current_rate_per_min * backoff_factor)`; store the **sanitized** `kind` only (e.g. `"http_429"`, `"rate_limit_toast"`, `"prompt_not_submitted"`) — never prompts/tokens/bodies. Backoff signals (documented for callers): own-tab HTTP 429 / Retry-After, rate-limit/toast/account-limit classifiers, repeated `PromptNotSubmittedError`.
- **`hard_pause(reason: str)`** / **`resume()`**: hard pause sets a flag so the next `submission()` raises `HumanActionNeededError("send budget hard-paused", details={"reason": <sanitized>})` and submits NOTHING; `resume()` clears it (after human action). Login/Cloudflare → hard pause.
- **NO hard message cap**: never refuse a submission based on a count. `snapshot()` returns `hard_message_cap: None` plus `successful_submissions`, `active_submission`, `current_rate_per_min`, `politeness_floor_s`, `hard_paused`, `last_signal` (sanitized or null).

**Falsifiable unit tests** (construct `AdaptiveSendBudget(monotonic=clock.monotonic, sleeper=clock.sleep)` with `ScriptedClock`; each MUST be able to fail):
- two successive submissions: the second sleeps `>= max(politeness_floor_s, 60/rate)` (assert via `clock.sleeps`).
- politeness floor is hard: drive rate high (many successes), effective spacing never `< politeness_floor_s`.
- AIMD increase: `current_rate_per_min` rises by `additive_increase_per_min` per success, capped at `max_rate_per_min`.
- `record_soft_signal` halves the rate (multiplicative), floored at `min_rate_per_min`; subsequent spacing grows.
- `hard_pause` → `submission()` raises `HumanActionNeededError` and yields no body; `resume()` restores sending.
- **no hard cap**: 50 successful submissions all proceed; `snapshot()["hard_message_cap"] is None`.
- busy guard: a nested `submission()` raises `PromptBudgetBusyError`.

## Part 3 — TabPool idle-TTL eviction
Extend `TabPool` (keep lazy-open, same-conversation lease reuse, LRU eviction at capacity, own-tabs-only, `close_all` own-tabs-only). Add `idle_ttl_s` (default `900.0`) and an injected `monotonic` (default `time.monotonic`). Track `last_used` as a **monotonic timestamp** (keep deterministic LRU). On `acquire()`, **before** reusing/opening, evict every **unleased** managed tab whose `now - last_used > idle_ttl_s` (close its own page via `channel.close_tab`). Keep LRU eviction (oldest `last_used`) when at `max_tabs` capacity. Never evict a **leased** tab.

**Falsifiable unit tests** (`ScriptedClock`):
- idle eviction: acquire conv1, release; advance clock `> idle_ttl_s`; acquire conv2 → conv1's tab is closed (assert `close_tab` happened / no longer managed). Must be able to fail.
- leased tab survives TTL: acquire conv1 (leave leased), advance `> idle_ttl_s`, acquire conv2 (under capacity) → conv1 still managed+leased.
- LRU at capacity: `max_tabs=2`, acquire+release conv1 then conv2, acquire conv3 → the older (`conv1`) is LRU-closed.
- own-tabs-only preserved: pool never accesses `context.pages` (MockChannel's context raises on `.pages`).

## Wiring (critical for a fast offline suite)
`Session.__init__` must wire the **channel's clock** into both `AdaptiveSendBudget` and `TabPool` so a `MockChannel(monotonic=clock.monotonic, sleeper=clock.sleep)` drives spacing/TTL deterministically. When a concrete channel instance was passed to `Session(channel=...)`, use its `monotonic`/`sleep`; for string channels (`"mock"`/`"cdp"`) default to real `time.monotonic`/`time.sleep` (real legs use real time). **Update any existing test whose timing would otherwise sleep real wall-clock** — notably `tests/test_session_stubs.py::test_repeated_successful_mock_sends_in_one_session_have_no_hidden_message_cap` (15 sends would now block on the 5s floor): construct its `MockChannel` with a `ScriptedClock` so the budget's spacing sleeps are fake. Preserve its behavioral assertions (15 sends succeed, `successful_submissions == 15`, no cap). Keep the whole suite offline and < 3s.

## Safety / isolation (HARD RULES — obey exactly)
- Branch **`rewrite-v2`** only. **NEVER** checkout/commit/merge/move **`stable`**. **NEVER** `uv tool install/upgrade/reinstall`. Use `uv run`/`uv sync` only. **NEVER** `git push`.
- This task is OFFLINE: do **NOT** open a browser, touch CDP/`127.0.0.1:9222`, or hit any network. No real sends.
- **NEVER** edit `issues/cdp-send-repro/controller.mjs` (read-only reference; another agent is using it). **NEVER** stage `controller.mjs`, the untracked `human/` dir, `cache/`, `.pi-workers/`, or `team/state/*-manager-state.json`.
- Redact discipline: no auth/OAI/cookie/bearer values, no prompts/tokens/response bodies in code, tests, fixtures, or logs (mock canaries in `mock.py` are the only allowed sentinel strings).

## Commit policy (you commit your own TDD increments)
You ARE the sole editor during this run. Commit each green increment **locally** to `rewrite-v2` with explicit paths only — **never** `git add -A`. Suggested increments: (1) CdpChannel action path + tests; (2) AdaptiveSendBudget + tests + Session wiring + test_session_stubs clock update; (3) TabPool idle-TTL + tests. After each: `uv run pytest` green, then `git add <explicit files>` and `git commit -m "M7-T1a: <area>"` (no `Co-Authored-By`, no push). Stage ONLY: `src/ask_chatgpt/channels/cdp.py`, `src/ask_chatgpt/session.py`, `tests/<new+changed test files>`. Confirm `git status` shows `controller.mjs` and `human/` still UNstaged.

## Success criteria
- All six `CdpChannel` action methods implemented (no `HumanActionNeededError` deferral), mirroring controller.mjs; the `ask_chatgpt_send_read_composer_text` readback works; fake-Playwright tests cover fill/click/readback and can fail.
- `AdaptiveSendBudget` enforces politeness floor + AIMD + backoff + hard-pause, with **no hard cap**; falsifiable `ScriptedClock` tests.
- `TabPool` idle-TTL eviction + LRU + own-tabs-only; falsifiable `ScriptedClock` tests.
- `uv run pytest` green (>212; suite offline + < 3s). Increments committed locally to `rewrite-v2` (explicit paths). `stable` unmoved.

## Handoff (write `team/evidence/reports/M7-T1a.md`)
Status `DONE`/`PARTIAL`/`BLOCKED` (single token, top). Then: exact `uv run pytest` tail (N passed); list of commits (hashes + one-line); files changed; which behaviors each new test covers + one sentence on **how each could fail** (falsifiability); confirmation `controller.mjs`/`human/` not staged and `git status` is clean of them; any blockers; complexity signals. Do NOT paste auth/OAI/cookie values or conversation content. If you run low on budget: commit what's green, write a resume-ready PARTIAL report, stop.
