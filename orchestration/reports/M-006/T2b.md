START_TIMESTAMP: 2026-06-12T20:10:30-05:00
END_TIMESTAMP: 2026-06-12T20:15:48-05:00
ESTIMATE: T2b 5m

Changes:
- Installed verified selector values from `orchestration/reports/M-006/real-selectors-proposed.json` into `src/ask_chatgpt/selector_maps/real.json` for: `ready_root`, `chat_list`, `chat_item`, `new_chat_button`, `composer`, `send_button`, `assistant_message`, `message_body`, `streaming_marker`, `completion_marker`, `copy_button`, `download_artifact`, `upload_input`.
- Installed verified attribute value `turn_id = data-message-id`.
- Kept fail-closed empty values for: `model_menu`, `model_option`, `model_option_disabled`, `login_wall`, `conversation_not_found`, `truncation_marker`, `rate_limit_marker`, `conversation_ref`.
- Kept `channel: real`, `version: 1`, and updated the note to the allowed M-006 T2 wording.
- Added only `cdn.auth0.com` to `DEFAULT_REAL_ALLOWED_DOMAINS`, with a one-line M-006 T2 discovery comment. Quick check passed: `host_allowed("cdn.auth0.com", DEFAULT_REAL_ALLOWED_DOMAINS)` true and `host_allowed("evil.com", DEFAULT_REAL_ALLOWED_DOMAINS)` false.

Test run:
- `uv sync --all-groups`: completed successfully.
- `uv run pytest`: `====================== 136 passed, 1 deselected in 52.10s ======================`
- Default run selected/ran ZERO `real_site` tests; the single `real_site`-marked item was deselected by the default `-m not real_site` addopts.
- Autouse socket guard in `tests/conftest.py` unchanged (`git diff --quiet -- tests/conftest.py tests/test_driver.py tests/test_real_allowlist.py` passed).
- Decoupled fail-closed selector-map test stayed green in `tests/test_driver.py`.

Focused T2b git diff --stat:
```text
 src/ask_chatgpt/real_allowlist.py       |  2 ++
 src/ask_chatgpt/selector_maps/real.json | 30 +++++++++++++++---------------
 2 files changed, 17 insertions(+), 15 deletions(-)
```

MESSAGES_USED: 0
T2b-STATUS: DONE
