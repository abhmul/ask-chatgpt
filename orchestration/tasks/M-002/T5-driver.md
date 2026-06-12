# T5 — Driver core: Playwright session controller (mock/real channels), fail-closed selector loader, completion detector, session+model handling. TDD vs fixture.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1–T4b DONE/committed: package `ask_chatgpt` has `errors.py` (8 named errors) + `session_registry.py`; the mock fixture (`tests/fixtures/mock_chatgpt/`, `mock_chatgpt` pytest fixture) is COMPLETE with scriptable adversarial/failure/streaming/copy/download/fenced/upload modes; `src/ask_chatgpt/selector_maps/mock.json` has all selector keys. 27 tests green.

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be green (27 passed). If not, STOP, report BLOCKED with output.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001: bounded latest-completed-turn reading; **fail-closed on stale/missing selectors (STOP, never guess/broaden)**; operator-owned profile (tool never reads/stores/logs credentials/profile contents); real channel gated on operator runbook.
3. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/selector_maps/mock.json` — the selector keys + attributes your loader consumes (selectors: ready_root, chat_list, chat_item, new_chat_button, composer, send_button, model_menu, model_option, model_option_disabled, assistant_message, message_body, streaming_marker, completion_marker, copy_button, login_wall, conversation_not_found, truncation_marker, rate_limit_marker, download_artifact, upload_input; attributes: conversation_ref, turn_id).
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` — the named errors to raise. You MAY add a `RateLimitedError(AskChatGPTError)` subclass here (rate-limit is a real honest-failure the fixture renders but T2 didn't name) — actionable backoff message.
5. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` (skim) + `/home/abhmul/dev/ask-chatgpt/tests/conftest.py` (the `mock_chatgpt` fixture + its `.base_url`, `.reset()`, `.script_next_response(...)`, `.inspect()`) + `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_adversarial.py` (how failure modes / streaming / `/__script__` are driven) — to write driver tests against the real fixture behaviors.

## Scope — build the driver (navigation/session/model/completion/error-mapping + infra; NOT text extraction, that is T6)
Create `src/ask_chatgpt/selector_map.py` and `src/ask_chatgpt/driver.py` (you may split further). 

1. **Selector-map loader** (`selector_map.py`): `load_selector_map(channel: str, *, maps_dir: Path | None = None) -> SelectorMap` loading `src/ask_chatgpt/selector_maps/<channel>.json`. `SelectorMap.selector(key) -> str` and `SelectorMap.attribute(key) -> str` **FAIL CLOSED**: if the key is absent OR its value is empty/None → raise `SelectorUnavailableError(f"selector '{key}' unavailable for channel '{channel}'")`. NEVER guess, broaden, or fall back to a different selector. This is the core D-001 safety property.
2. **Channel knobs + session controller** (`driver.py`): a class (e.g. `BrowserSession`) that owns a Playwright browser/context/page and a loaded `SelectorMap`:
   - `channel="mock"`: `chromium.launch(headless=True)` + `new_context()`, navigate to a provided loopback `base_url`. This is the ONLY channel tests exercise.
   - `channel="real"`: build the code path — `chromium.launch_persistent_context(user_data_dir=<profile_path>, headless=False)` and a `REAL_BASE_URL = "https://chatgpt.com"` constant — but it is **NEVER exercised by any test**. `profile_path` is a DIRECTORY PATH config value; the driver NEVER reads/inspects/logs its contents. No test may navigate to chatgpt.com.
   - Lifecycle: a context manager (`__enter__`/`__exit__`) or `start()`/`close()` that launches and cleanly tears down Playwright (sync or async API — your choice; match the fixture tests' style). Kill only what you start.
   - `open_or_create_conversation(conversation_ref: str | None) -> str`: if `conversation_ref` given, navigate to it and if the `conversation_not_found` marker shows (or 404) raise `SessionNotFoundError`; if None, click `new_chat_button` to create one. Detect the `login_wall` (or absent composer) → `LoginRequiredError`. Return the active conversation ref (read via the `conversation_ref` attribute).
   - `select_model(model_settings: dict | None) -> None`: if a model is requested, open `model_menu` and click the matching `model_option`; if the option is absent or matches `model_option_disabled` → `ModelUnavailableError`. No-op if `model_settings` is None/empty.
   - `send_prompt(text: str) -> None`: fill `composer`, click `send_button`. (If `rate_limit_marker` appears → `RateLimitedError`.)
   - `wait_for_completion(timeout_s: float = 10.0) -> Locator`: the **completion detector**. Returns the locator of the LATEST COMPLETED assistant turn (an `assistant_message` element bearing the `completion_marker`). Strategy for the mock: poll for `completion_marker`; while only `streaming_marker` is present, RELOAD `/c/<ref>` (the mock advances its stream counter per read) and re-check, until complete or `timeout_s` → `ResponseTruncatedError`. If a `truncation_marker` is present → `ResponseTruncatedError`. (NOTE in a docstring: the real-channel completion signal is an operator-runbook unknown — memo §7 item 6 — so the reload-poll strategy is mock-specific; do not hardcode real-site behavior.) Expose `.page` and `.selectors` so the T6 reader can extract text from the returned locator.
3. **Real selector-map TEMPLATE** at `src/ask_chatgpt/selector_maps/real.json`: SAME key structure as `mock.json` but values are EMPTY strings (`""`) with a top-level note that they are resolved by the operator observation runbook (`docs/runbooks/observe-chatgpt-unknowns.md`). Because the loader fails closed on empty values, any real-channel use raises `SelectorUnavailableError` until the operator fills them — which is the correct honest posture (real channel unproven). Do NOT fabricate real chatgpt.com selectors.

### TDD tests — `tests/test_driver.py` (write FIRST, watch fail, implement) — channel="mock" ONLY
Drive the `mock_chatgpt` fixture (headless chromium, cached). Cover:
- Happy path: open/create conversation, `select_model` an available model, `send_prompt`, `wait_for_completion` returns the latest completed turn locator (whose `message_body` text == scripted text — you may read it to assert, even though formal extraction is T6).
- Streaming: script `streaming=True, stream_reads=2`; `wait_for_completion` polls/reloads and returns only once complete.
- Fail-closed selector: a `SelectorMap` missing/empty key → `SelectorUnavailableError` (unit test, no browser needed); and the `selector_unavailable` fixture mode (absent composer) → driver raises `SelectorUnavailableError`.
- Honest failures: `login_required` → `LoginRequiredError`; `session_not_found` (bad ref) → `SessionNotFoundError`; `model_unavailable` → `ModelUnavailableError`; `response_truncated` → `ResponseTruncatedError`; `rate_limited` → `RateLimitedError`.
- A test asserting NO test navigates to chatgpt.com (e.g. assert the real channel constant is `https://chatgpt.com` but is never used; the network guard in conftest already blocks non-loopback — keep all navigation on `base_url`).
- `real.json` loads and every key is empty → `SelectorUnavailableError` on `.selector(...)` (proves fail-closed real template).
- Full `uv run pytest -q` GREEN (27 existing + new). Bound waits.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Tests and ALL work NEVER contact chatgpt.com/openai or any external service. Every test navigates ONLY to the loopback `mock_chatgpt.base_url`. The real channel (chatgpt.com + persistent profile) is BUILT but NEVER run by any test. The conftest socket guard blocks non-loopback — do not weaken it.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. `profile_path` is an opaque directory path passed to Playwright; the driver NEVER opens/reads/lists its contents, and it never appears in logs/errors/reports.
- The ONLY ever-permitted external download is chromium — ALREADY CACHED. ZERO new pip deps (existing `playwright` only). Never sudo/apt/install.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY. NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Tear down browsers/contexts you start. NEVER `git push`. Do NOT `git commit`. Do not break the 27 existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-002/T5-report.md`)
- `date -Iseconds` at START + END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- `ESTIMATE: T5 <min>m`.
- Report ≤200 lines: files created, the driver public surface (methods + which errors each raises), how fail-closed selector loading works, the completion-detector strategy (+ the real-channel note), confirmation the real channel is never tested, the exact `uv run pytest -q` summary, deviations, trust notes (loopback-only, profile-path never inspected, no credentials).
- End with `T5-STATUS: DONE` (or `BLOCKED` + exact error + next action) LAST.

## Success criteria (all must hold)
- `selector_map.py` loader FAILS CLOSED (missing/empty key → `SelectorUnavailableError`); `real.json` template (all-empty) proves it.
- `driver.py` `BrowserSession` with channel="mock" (tested) + channel="real" (built, NEVER tested), open_or_create_conversation, select_model, send_prompt, wait_for_completion (completion detector w/ streaming reload-poll + truncation→ResponseTruncatedError), exposing `.page`/`.selectors`.
- Honest-failure mapping: login→LoginRequiredError, session→SessionNotFoundError, model→ModelUnavailableError, truncated→ResponseTruncatedError, rate-limit→RateLimitedError, selector→SelectorUnavailableError.
- `profile_path` contents never read/logged; no test touches chatgpt.com.
- `tests/test_driver.py` green; full `uv run pytest -q` green (27 existing pass); zero new deps.
- Report with telemetry + `T5-STATUS:` last.
