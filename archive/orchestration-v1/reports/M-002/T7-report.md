START_TIMESTAMP: 2026-06-12T01:13:36-05:00
END_TIMESTAMP: 2026-06-12T01:19:23-05:00
ESTIMATE: T7 45m

## Inherited-tree check
- Ran `uv sync --all-groups` successfully.
- Ran `uv run pytest -q` before changes: `50 passed in 24.51s`.

## Files created/modified
- Created `src/ask_chatgpt/api.py`.
- Modified `src/ask_chatgpt/__init__.py`.
- Modified `src/ask_chatgpt/driver.py`.
- Created `tests/test_ask_chatgpt_uc1.py`.
- Created `tests/test_network_guard.py`.
- Created executable `scripts/accept_uc1.py` and `scripts/accept_uc1.sh`.
- Created this report.

## Public API
- Implemented `ask_chatgpt(prompt, *, session_identifier=None, model_settings=None, channel="real", base_url=None, profile_path=None, registry=None, reader_order=None, timeout_s=30.0) -> str`.
- Wiring: `SessionRegistry` lookup -> `BrowserSession(channel, base_url, profile_path)` context -> `open_or_create_conversation` -> `select_model` -> `send_prompt` -> `wait_for_completion` -> `read_response`.
- On success with `session_identifier`, stores `ConversationRef(conversation_ref=<active_ref>, url=<page.url>, model_settings=<model_settings>)` for continuity.
- Exported `ask_chatgpt` and named error types from package top-level.

## UC1 proof
- `tests/test_ask_chatgpt_uc1.py` uses only `channel="mock"` with the loopback fixture and tmp `SessionRegistry` paths.
- Continuity is proven by calling the same `session_identifier` twice, then asserting `mock_chatgpt.inspect()` shows both user prompts in the same conversation; a different identifier is asserted to create a different conversation.
- Return text is asserted equal to scripted latest text, with an older sentinel absent.
- Model settings test covers available `mock-default` success and unavailable `mock-reasoning` raising `ModelUnavailableError`.
- Honest failure test scripts `login_required` and asserts `LoginRequiredError` with actionable sign-in language.

## Acceptance script
- `scripts/accept_uc1.sh` creates `tmp/accept-uc1-<timestamp>/`, runs `uv run python scripts/accept_uc1.py --out "$OUT"`, tees `stdout.log`, and exits nonzero on driver failure.
- `scripts/accept_uc1.py` starts `MockChatGPTServer` on an ephemeral loopback port, uses `SessionRegistry(store_path=<OUT>/sessions.json)`, exercises same-session continuity, model settings, and a login-required honest failure.
- Produced run: `tmp/accept-uc1-20260612-011815/`.
- Acceptance verdict: `overall: pass` in `tmp/accept-uc1-20260612-011815/results.json`; `stdout.log` exists in the same directory.

## Network guard
- `tests/test_network_guard.py` deliberately calls `socket.create_connection(("93.184.216.34", 80), timeout=1)` and asserts the autouse guard raises `RuntimeError` matching `NETWORK BLOCKED`.
- Added mock-browser context route interception in `BrowserSession._start_mock_context`; non-loopback HTTP(S)/WS(S) browser requests are aborted, real-channel behavior unchanged.
- Added a Playwright test proving `page.goto("http://93.184.216.34/")` is blocked in the mock context.

## Final verification
- Ran acceptance once: `bash scripts/accept_uc1.sh` -> exit 0.
- Ran final full test suite: `uv run pytest -q` -> `56 passed in 24.59s`.

## Deviations
- None.

## Trust notes
- No new dependencies.
- Tests and acceptance script invoke only `channel="mock"` and loopback mock URLs; no real channel or external service is exercised.
- No credentials, cookies, tokens, browser profile contents, or secret material are read, stored, or logged.

T7-STATUS: DONE
