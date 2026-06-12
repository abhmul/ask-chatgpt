START_TIMESTAMP: 2026-06-12T00:50:09-05:00
END_TIMESTAMP: 2026-06-12T00:58:21-05:00
ESTIMATE: T5 60m

STEP 0:
- `uv sync --all-groups` completed.
- Inherited tree confirmed green: `uv run pytest -q` -> `27 passed in 9.96s`.

Files created:
- `src/ask_chatgpt/selector_map.py`
- `src/ask_chatgpt/driver.py`
- `src/ask_chatgpt/selector_maps/real.json`
- `tests/test_driver.py`
- `orchestration/reports/M-002/T5-report.md`

Files modified:
- `src/ask_chatgpt/errors.py`: added `RateLimitedError` and `__all__` export.
- `tests/test_errors.py`: included `RateLimitedError` in named-error contract coverage.

Driver public surface:
- `REAL_BASE_URL = "https://chatgpt.com"`.
- `BrowserSession(channel="mock", base_url=...)`: tested loopback-only path using headless Chromium + new context.
- `BrowserSession(channel="real", profile_path=...)`: built persistent-context path using the opaque operator profile directory and `REAL_BASE_URL`; never exercised by tests.
- `.start()`, `.close()`, context-manager `__enter__/__exit__` manage only Playwright resources started by the session.
- `.page` and `.selectors` are exposed for T6.
- `.open_or_create_conversation(conversation_ref)`: raises `SessionNotFoundError` for 404/not-found marker, `LoginRequiredError` for login wall, `SelectorUnavailableError` for missing required UI selectors; returns active conversation ref from selector-map attribute.
- `.select_model(model_settings)`: no-op for empty settings; raises `ModelUnavailableError` for absent/disabled/unselectable requested model and `SelectorUnavailableError` for missing selector-map/UI affordance.
- `.send_prompt(text)`: fills composer and submits; raises `RateLimitedError` for rate-limit marker, `LoginRequiredError`/`SessionNotFoundError` via page markers, and `SelectorUnavailableError` for unavailable composer/send selector.
- `.wait_for_completion(timeout_s=10.0)`: returns the latest assistant-message locator only when the latest assistant turn bears the completion marker; raises `ResponseTruncatedError` for truncation marker or timeout, `RateLimitedError` for rate limit, plus login/session/selector named errors as applicable.

Fail-closed selector loading:
- `load_selector_map(channel, maps_dir=None)` loads exactly `selector_maps/<channel>.json`; it never falls back to another channel.
- `SelectorMap.selector(key)` and `.attribute(key)` raise `SelectorUnavailableError` when the key is absent, non-string, empty, or whitespace-only.
- `real.json` mirrors the `mock.json` key structure with all selector/attribute values set to `""`, so real-channel selector access fails closed until an operator fills values from `docs/runbooks/observe-chatgpt-unknowns.md`.

Completion detector:
- Mock strategy reload-polls `/c/<ref>` while the latest assistant turn is streaming/incomplete, allowing the fixture's scripted stream counter to advance.
- It returns only the latest assistant turn once that turn has the completion marker, avoiding older completed turns during a newer stream.
- Real-channel completion signals remain an operator-runbook unknown; the mock reload-poll behavior is documented as mock-specific and is not asserted as real-site behavior.

Tests:
- TDD red observed first: `tests/test_driver.py` initially failed with `ModuleNotFoundError: No module named 'ask_chatgpt.driver'`.
- Targeted driver tests after implementation: `11 passed in 4.54s`.
- Final full suite: `uv run pytest -q` -> `38 passed in 14.16s`.

Deviations:
- None from the task contract.

Trust notes:
- Tests and implementation work used only the loopback `mock_chatgpt.base_url`; no test instantiates or runs the real channel, and no test navigates to chatgpt.com.
- No new dependencies were added.
- `profile_path` is treated as an opaque directory argument to Playwright; the driver does not open, list, read, store, log, or report profile contents or credentials.
- No credentials, cookies, session tokens, or browser-profile contents were read/stored/logged.
T5-STATUS: DONE
