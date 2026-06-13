START_TIMESTAMP: 2026-06-12T21:34:00-05:00
END_TIMESTAMP: 2026-06-12T21:48:08-05:00
ESTIMATE: T2f 45m

## Changes
- GAP-9: added `_READY_ROOT_TIMEOUT_MS = 30_000` and real/cdp-only `_wait_for_ready_root()`; mock returns immediately. Calls now precede each `ready_root` require in `open_or_create_conversation`: existing conversation, initial new-chat page, and post-New-chat load. Timeout errors include title plus sanitized URL path-shape only.
- GAP-10: `send_prompt()` now fills `composer` before waiting for attached `send_button`, then requires/clicks it. Composer fill `PlaywrightError` still maps to `SelectorUnavailableError('composer')`; post-send load/rate-limit/ref logic is unchanged.
- Focused fake-page tests were used; no mock fixture or selector-map edits.

## Final line references
- `src/ask_chatgpt/driver.py:42`: `_READY_ROOT_TIMEOUT_MS = 30_000`.
- `src/ask_chatgpt/driver.py:195,202,208`: readiness waits before `ready_root` requires in `open_or_create_conversation`.
- `src/ask_chatgpt/driver.py:255,259-265`: composer fill before send-button wait/require/click.
- `src/ask_chatgpt/driver.py:489-508`: `_wait_for_ready_root()`.
- `src/ask_chatgpt/driver.py:579-599`: safe title/path-shape helpers.
- `tests/test_driver.py:299,311,325,341`: delayed-ready, never-ready, and send-after-fill tests.

## RED -> GREEN evidence
- RED first, before driver changes: `uv run pytest tests/test_driver.py::test_open_existing_conversation_waits_for_delayed_real_ready_root_before_requiring_it tests/test_driver.py::test_open_new_conversation_waits_for_initial_and_post_click_real_ready_root tests/test_driver.py::test_wait_for_ready_root_timeout_reports_title_and_url_path_shape_only tests/test_driver.py::test_send_prompt_fills_composer_before_waiting_for_send_button_after_fill -q` -> `4 failed` (`ready_root`/`send_button` unavailable and missing `_wait_for_ready_root`).
- GREEN targeted after driver changes: same command -> `4 passed in 0.08s`.

## Authoritative suite
- `uv sync --all-groups` completed: `Resolved 11 packages`; `Audited 10 packages`.
- `uv run pytest` completed once after sync: `158 passed, 1 deselected in 73.84s (0:01:13)`.
- Collection stayed default-tier: `collected 159 items / 1 deselected / 158 selected`; the deselected item is `real_site`.
- Socket guard tests passed (`tests/test_network_guard.py ..`); mock UC1 and UC2 happy paths passed (`tests/test_ask_chatgpt_uc1.py ....`, `tests/test_uc2_roundtrip.py ..`).
- `git diff --name-only -- src/ask_chatgpt/selector_maps/mock.json src/ask_chatgpt/selector_maps/real.json tests/conftest.py src/ask_chatgpt/selector_map.py src/ask_chatgpt/api.py src/ask_chatgpt/cli.py` produced no output.

## git diff --stat
Overall `git diff --stat` for tracked files (includes pre-existing non-T2f orchestration changes):
```text
orchestration/reports/M-006/T3.md    |  60 +++++-----
orchestration/state/M-006-state.json |   4 +-
src/ask_chatgpt/driver.py            |  58 +++++++++-
tests/test_driver.py                 | 205 ++++++++++++++++++++++++++++++++++-
4 files changed, 294 insertions(+), 33 deletions(-)
```
T2f-scoped tracked diff:
```text
src/ask_chatgpt/driver.py |  58 ++++++++++++-
tests/test_driver.py      | 205 +++++++++++++++++++++++++++++++++++++++++++++-
2 files changed, 260 insertions(+), 3 deletions(-)
```
Pre-existing non-T2f orchestration changes were present before this leg (`orchestration/reports/M-006/T3.md`, `orchestration/state/M-006-state.json`, plus untracked T3/task docs); I did not edit or revert them. This report is new and untracked until the manager stages it.

MESSAGES_USED: 0
T2f-STATUS: DONE
