# T2f — Real SPA readiness wait + send-button-after-fill (MOCK-TIER, single editor, TDD)

You are a fresh worker. **You inherit NOTHING except this file + the files it tells you to read.** ZERO real contact: mock/loopback/unit only. **ZERO real messages.** TDD/RED-first. Read the SAFETY BLOCK. Use `git stash push -u` for any revert; never `git checkout`/`git clean`. Do NOT `git commit` (manager commits).

## Why this leg exists (a 0-message real diagnostic measured these; manager-confirmed)

The real chatgpt.com is a React SPA. A read-only CDP diagnostic (`orchestration/reports/M-006/T3-diag.md`) measured:
- `main:has(#prompt-textarea)` (the `ready_root` selector) and `#prompt-textarea` appear **~1 s AFTER** `page.goto(wait_until="load")` — the page hydrates after load. The page is the real app (title "ChatGPT", url "/", NO login, NO Cloudflare, NO blocking overlay; `#prompt-textarea` present and not covered).
- `button[data-testid="send-button"]` matches **0 elements on an EMPTY composer** (it appears only after text is typed). (T2 discovery's sends worked precisely because it typed first.)

The driver currently (a) checks `ready_root` immediately after `goto` with no element wait, and (b) in `send_prompt` requires `send_button` BEFORE filling the composer. Both fail on the real site:
- **GAP-9:** `open_or_create_conversation` → `_require_present("ready_root")` (driver.py ~line 202, 208/213) runs before hydration → `SelectorUnavailableError: selector 'ready_root' unavailable for channel 'cdp'`.
- **GAP-10:** `send_prompt` (driver.py ~256-261) does `send_button = self._require_present("send_button")` (line ~258) BEFORE `composer.fill(text)` (line ~260) → on the real empty composer the send button is absent → `SelectorUnavailableError`.

## Files to READ FIRST (ground truth; verify line numbers)
- `src/ask_chatgpt/driver.py`:
  - `start()` (~103-134): `page.goto(self._base_url, wait_until="load", ...)` at ~126; then for real/cdp `_raise_login_required_for_auth_redirect` (~128) and cdp `_raise_challenge_present_if_detected` (~130). This is the natural place to add the initial readiness wait.
  - `open_or_create_conversation` (~180-216): existing-branch `goto(/c/<ref>)` then `_require_present("ready_root")` (~202); new-branch clicks `new_chat_button` (~210), `_wait_for_load_state()` (~211), then `_require_present("ready_root")` (~213). Each `ready_root` require needs a preceding readiness wait on real/cdp.
  - `send_prompt` (~253-268): currently `composer = self._require_present("composer")`; `send_button = self._require_present("send_button")`; then `composer.fill(text)`; `send_button.click()`. REORDER for real correctness.
  - `_require_present`/`_present`/`_optional_selector` (~453-475), `_wait_for_load_state` (find it), `_DEFAULT_NAVIGATION_TIMEOUT_MS`/`_POLL_INTERVAL_S` constants (top of file). `self.channel` ∈ {mock, real, cdp}.
- `tests/test_driver.py` + `tests/fixtures/mock_chatgpt/` (the `MockChatGPTServer` — see what it serves; whether you can add a delayed-render or empty-composer-no-send-button variant) + existing cdp/real tests. `mock.json` (send_button + ready_root populated → mock currently renders both immediately).

## Deliverables (TDD/RED-first)

### D1 — GAP-9: bounded readiness wait for `ready_root` on real/cdp
- Add a helper, e.g. `_wait_for_ready_root(self, timeout_ms=_READY_ROOT_TIMEOUT_MS)`: for `self.channel in {"real","cdp"}`, wait for the `ready_root` selector to be ATTACHED (e.g. `self._require_page().wait_for_selector(self.selectors.selector("ready_root"), timeout=timeout_ms, state="attached")`); on timeout raise a clear, actionable error (reuse `SelectorUnavailableError` or `AskChatGPTError`) whose message notes the app did not become ready (include `page.title()` and the URL PATH-SHAPE only — NEVER full URL/query/account text). For `channel=="mock"` it is a no-op (or instant) — mock behavior MUST stay byte-identical.
- Call `_wait_for_ready_root()` before each `_require_present("ready_root")` in `open_or_create_conversation` (both branches) — and/or once in `start()` after the initial `goto` + login/challenge checks. Pick the minimal set that guarantees: after initial load, after opening an existing `/c/<ref>`, and after clicking New chat, the app is awaited before `ready_root` is required.
- Add a constant `_READY_ROOT_TIMEOUT_MS` (generous, e.g. 30000). Hydration measured ~1 s; allow for slow loads.

### D2 — GAP-10: fill the composer BEFORE requiring/clicking `send_button`
- In `send_prompt`, reorder: require `composer`; `composer.fill(text)` FIRST; THEN wait (bounded, e.g. `page.wait_for_selector(send_button_selector, timeout=...)` or a short poll) for `send_button` and click it. Keep the existing `PlaywrightError -> SelectorUnavailableError('composer'...)` mapping semantics for fill failures. Net effect: on the real site the send button appears after fill and is clicked; on the mock (send button always present) behavior is unchanged.
- Keep the post-send logic (`_wait_for_load_state(ignore_timeout=True)`, rate-limit check, forgiving conversation-ref read) intact.

### D3 — Preserve everything else
- Do NOT change `_require_present` (required selectors still fail closed), `selector_map.py`, `real.json`, `mock.json`, `conftest.py`, `api.py`, `cli.py`. Do NOT weaken any fail-closed behavior. The model fail-closed path stays as is.

### D4 — Tests (DEFAULT-TIER; mock/loopback/unit; NOT real_site; RED-first)
Prove both fixes deterministically without real contact. Acceptable approaches (choose what is cleanest and say which):
- A mock-fixture variant or a fake page that (i) exposes `ready_root` only after a short delay → assert `_wait_for_ready_root`/`open_or_create_conversation` waits and succeeds instead of raising; and (ii) exposes `send_button` only AFTER the composer is filled → assert `send_prompt` succeeds (and that the OLD order would have raised). If extending `MockChatGPTServer` is too invasive, focused unit tests with fake Locators/Page that emulate "appears after delay / after fill" are acceptable.
- Keep an assertion that a genuinely-never-ready page (ready_root never appears) raises the clear actionable error within the timeout (use a short timeout in the test).
- The existing mock UC1/UC2 happy paths + all current tests MUST stay green (mock renders ready_root + send_button immediately, so the wait returns instantly and the reorder is a no-op for mock).

### D5 — Suite green + tier purity + scope
- `uv sync --all-groups`; full default suite ONCE (serialize): `uv run pytest`. GREEN; expect >= prior 154 passed. Capture the summary line.
- Clean run collects ZERO `real_site`; socket guard + `mock.json` + `real.json` UNCHANGED.
- `git diff --stat` touches ONLY `src/ask_chatgpt/driver.py` + your new/edited test files (and, if you added a mock-fixture variant, the test fixtures under `tests/`). NOT real.json/mock.json/conftest/selector_map/api/cli.

## SAFETY BLOCK — obey verbatim (you inherit nothing)
- ZERO real-site contact. Mock/loopback/unit only. Socket guard NEVER weakened. Required-selector fail-closed preserved.
- Never read/copy/store/log credentials/cookies/tokens/profile contents. No account identifiers anywhere. If your error messages include page state, use title + URL PATH-SHAPE only.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. NEVER `git push`. Do NOT `git commit`.
- ESTIMATE BEFORE EXECUTE.

## Reporting (write to `orchestration/reports/M-006/T2f.md`, cap ~250 lines)
1. `START_TIMESTAMP:`/`END_TIMESTAMP:` + `ESTIMATE: T2f <min>m`.
2. The GAP-9 + GAP-10 changes (final line numbers) + RED→GREEN evidence (the failing test first, then passing).
3. Authoritative `uv run pytest` summary + ZERO real_site + socket guard/mock.json/real.json unchanged + mock UC1/UC2 happy paths green.
4. `git diff --stat` (prove scope).
5. `MESSAGES_USED: 0`.
- LAST LINE: `T2f-STATUS: DONE` (or `T2f-STATUS: BLOCKED` + precise blocker).
