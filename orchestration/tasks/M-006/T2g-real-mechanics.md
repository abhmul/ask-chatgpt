# T2g — Port T2's PROVEN real-site mechanics into the driver/bundle (MOCK-TIER, single editor, TDD)

You are a fresh worker. **You inherit NOTHING except this file + the files it tells you to read.** ZERO real contact: mock/loopback/unit only. **ZERO real messages.** TDD/RED-first. Read the SAFETY BLOCK. Use `git stash push -u` for any revert; never `git checkout`/`git clean`. Do NOT `git commit` (manager commits).

## Why (real runs measured these; a PROVEN-WORKING reference script exists)

The real CDP acceptance leg (T3) reached real sends but UC1-3 still failed because the driver's real-path mechanics differ from what actually works on chatgpt.com. A discovery worker (T2) ALREADY sent 7 real prompts successfully; its proven script is `tmp/m006_t2_cdp_discovery.py` (READ IT — it is the ground-truth reference for what works). Port its proven mechanics into the production driver/bundle, **scoped to real/cdp so the mock path stays byte-identical**. Four gaps:

- **GAP-11 (nav timeout):** `driver.py` `start()` does `page.goto(self._base_url, wait_until="load", timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)` where `_DEFAULT_NAVIGATION_TIMEOUT_MS=5000`. Real chatgpt.com often needs >5 s to fire load (observed Page.goto TimeoutError at 5000 ms). T2 used `timeout=60000`.
- **GAP-10b (send):** `send_prompt` fills then waits for/clicks `send_button`, but the real send button is absent until text is entered AND a plain `fill()` may not register. T2's working method (`fill_composer` + `send_prompt` in the reference): (1) **click the composer to focus it**, (2) `fill(text)` with a **`keyboard.insert_text` fallback** (Control+A then insert_text) for the contenteditable, (3) click `send_button` if present **else press Enter** to submit.
- **GAP-13 (completion):** `wait_for_completion` returns ONLY when `completion_marker` (the copy button) is present, but the real copy button is hover-hidden → never detected → `ResponseTruncatedError`. T2's working completion signal: **(assistant turn present) AND (stop/streaming button GONE) AND (completion_marker present OR latest body text stable for ≥ ~2 s)**.
- **GAP-12 (upload confirm):** `bundle.py` `_wait_for_upload_status` waits for the mock-only `_UPLOAD_STATUS_SELECTOR` (`data-upload-status`), absent on real → "upload did not confirm before timeout". T2 confirmed upload by waiting (up to ~90 s) for the **filename chip** (the uploaded filename text becoming visible).

## Files to READ FIRST (ground truth)
- `tmp/m006_t2_cdp_discovery.py` — THE reference. Study `fill_composer` (~496-507), `send_prompt` (~510-528), `wait_for_completion` (~531-602), `discover_upload`'s chip wait (~1064-1073). Port the proven behavior; you do NOT need its discovery scaffolding.
- `src/ask_chatgpt/driver.py`: `start()` goto (~126), constants (~top: `_DEFAULT_NAVIGATION_TIMEOUT_MS`, `_POLL_INTERVAL_S`, `_READY_ROOT_TIMEOUT_MS`), `send_prompt` (~253-275), `wait_for_completion` (~274-310), `_present`/`_optional_selector`/`_require_present`, `_latest_assistant_turn`, `self.channel`.
- `src/ask_chatgpt/bundle.py`: `upload_bundle` (~297-353), `_wait_for_upload_status` (~642-660), `_UPLOAD_STATUS_SELECTOR` definition.
- `src/ask_chatgpt/selector_maps/real.json` (composer `#prompt-textarea`, send_button `button[data-testid="send-button"]`, streaming_marker `button[data-testid="stop-button"]`, completion_marker/copy_button `button[data-testid="copy-turn-action-button"]`, message_body `[data-message-author-role="assistant"] .markdown`, upload_input `input[type="file"]`) and `mock.json` (all populated incl. a `data-upload-status` status element + mock send/completion markers — mock behavior must NOT change).
- Existing tests: `tests/test_driver*.py`, `tests/test_bundle*.py`, the mock fixture under `tests/fixtures/mock_chatgpt/`.

## Deliverables (TDD/RED-first; mock byte-identical)

### D1 — GAP-11: longer real/cdp navigation timeout
- Add `_REAL_NAV_TIMEOUT_MS = 60_000`. In `start()`, use it for the `page.goto(...)` when `self.channel in {"real","cdp"}`; keep `_DEFAULT_NAVIGATION_TIMEOUT_MS` for mock. (If `open_or_create_conversation`'s existing-conversation `goto` also uses the short timeout, give it the same real/cdp treatment.)

### D2 — GAP-10b: focus-fill-then-submit in `send_prompt`
Rework `send_prompt` to match the proven mechanics:
1. `composer = self._require_present("composer")`; **click it to focus** (`composer.click(timeout=...)`); small settle is fine.
2. Fill: try `composer.fill(text, ...)`; on `PlaywrightError`, fallback to `page.keyboard.press("Control+A")` then `page.keyboard.insert_text(text)` (contenteditable path). Keep mapping a hard fill failure to `SelectorUnavailableError('composer'...)` only if BOTH fail.
3. Submit: if `send_button` is present (use the existing optional/bounded check — `_optional_selector`/`wait_for_selector` with a short timeout), click it; **ELSE press `page.keyboard.press("Enter")`**. Either way this is the single submit. Preserve the post-send logic (`_wait_for_load_state(ignore_timeout=True)`, rate-limit check, forgiving conversation-ref read).
- Mock: composer present + send_button present → clicks send_button as before (Enter fallback never triggers); behavior unchanged.

### D3 — GAP-13: robust completion for real/cdp in `wait_for_completion`
Keep the existing mock path (completion_marker present → return; the mock-only reload-poll stays gated to `channel=="mock"`). ADD, for `self.channel in {"real","cdp"}`, a completion path that returns the latest assistant turn when: the latest assistant turn exists AND the `streaming_marker` (stop button) is NOT present (gone) AND (`completion_marker` present OR the latest body text has been STABLE across polls for ≥ a stability window, e.g. `_REAL_COMPLETION_STABLE_S = 2.0`). Track `last_text`/`stable_since` across loop iterations (read the latest `message_body` text best-effort, like the reference). Keep the truncation/rate-limit guards (now optional-tolerant). Keep raising `ResponseTruncatedError` on real timeout. Use the caller's `timeout_s` (the API/CLI pass 90-150 s).
- Mock: completion_marker appears in the mock fixture → the existing path returns first; the new real/cdp branch does not run for mock. Mock behavior unchanged.

### D4 — GAP-12: real upload confirmation via filename chip in `bundle.py`
In `upload_bundle`/`_wait_for_upload_status`: keep the mock `data-upload-status` confirmation for mock. For the real/cdp path (when the mock status element is absent), confirm the upload by waiting (generous, e.g. up to ~90 s) for the **uploaded filename to become visible** (a filename chip), e.g. `page.get_by_text(upload_name)` / `page.locator('text=...')` visible. Determine the channel via the session (e.g. `getattr(session, "channel", None)`), or detect "no status element present" and fall back to the chip wait. On chip seen → `status="ok"`. On neither status nor chip within timeout → keep raising `UploadUnsupportedError("upload did not confirm before timeout")`. Do NOT weaken the mock's rejected/corrupt/unsupported handling. (You may add a small real upload-confirmation timeout constant.)
- This needs no new real.json selector (the filename is known from `upload_name`). If you find it cleaner to add an optional `upload_file_chip` selector key, do NOT — keep real.json unchanged; use the known filename text.

### D5 — Suite green + tier purity + scope
- `uv sync --all-groups`; full default suite ONCE (serialize): `uv run pytest`. GREEN; expect >= prior 158 passed. Capture the summary line. The mock UC1 (text) and UC2 (bundle upload+retrieve) happy paths MUST stay green — they prove mock is unchanged.
- Clean run ZERO `real_site`; socket guard + `real.json` + `mock.json` UNCHANGED.
- `git diff --stat` touches ONLY `src/ask_chatgpt/driver.py`, `src/ask_chatgpt/bundle.py`, and your new/edited test files (+ a test fixture variant if you add one under `tests/`). NOT real.json/mock.json/conftest/selector_map/api/cli.

## Tests (DEFAULT-TIER; mock/loopback/unit; RED-first)
Prove each fix deterministically with fakes/fixtures (no real contact). Suggested:
- GAP-10b: a fake page where `send_button` is absent → assert `send_prompt` falls back to `keyboard.press("Enter")` (and clicks send_button when present). Assert composer is clicked/focused before fill and the keyboard fallback triggers when `fill` raises.
- GAP-13: a fake/fixture turn where `completion_marker` never appears but the stop button disappears and text goes stable → assert real/cdp `wait_for_completion` returns; and where text keeps changing past timeout → assert `ResponseTruncatedError`. Assert mock still returns via completion_marker.
- GAP-12: a fake page with no `data-upload-status` but a visible filename chip → assert `upload_bundle` confirms ok for real/cdp; no status + no chip → `UploadUnsupportedError`. Mock status path unchanged.
- GAP-11: assert the real/cdp goto uses the 60 s timeout (e.g. via a captured kwarg / fake page) and mock uses the short one.
- Keep ALL existing tests green.

## SAFETY BLOCK — obey verbatim
- ZERO real-site contact. Mock/loopback/unit only. Socket guard NEVER weakened. Required-selector fail-closed preserved; do not weaken `_require_present`.
- Never read/copy/store/log credentials/cookies/tokens/profile contents. No account identifiers. Sanitize any page-state in errors (title + url path-shape only).
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. NEVER `git push`. Do NOT `git commit`.
- ESTIMATE BEFORE EXECUTE.

## Reporting (write to `orchestration/reports/M-006/T2g.md`, cap ~250 lines)
1. `START_TIMESTAMP:`/`END_TIMESTAMP:` + `ESTIMATE: T2g <min>m`.
2. The four changes (final line numbers) + how each mirrors the T2 reference + RED→GREEN evidence.
3. Authoritative `uv run pytest` summary + ZERO real_site + real.json/mock.json/conftest/selector_map unchanged + mock UC1/UC2 happy paths green.
4. `git diff --stat` (prove scope).
5. `MESSAGES_USED: 0`.
- LAST LINE: `T2g-STATUS: DONE` (or `T2g-STATUS: BLOCKED` + precise blocker).
