START_TIMESTAMP: 2026-06-12T21:00:30-05:00
END_TIMESTAMP: 2026-06-12T21:15:05-05:00
ESTIMATE: T2e 45m

CHANGE SUMMARY:
- GAP-7 fixed in `src/ask_chatgpt/readers.py:32-45`: `assistant_message` and `message_body` remain required; `truncation_marker` is resolved with `try/except SelectorUnavailableError` and the truncation check now runs only when mapped.
- GAP-8 fixed in `src/ask_chatgpt/patch.py:303-319`: `turn_id` remains required; unmapped `download_artifact` returns `_DownloadScan(candidate=None, stale_artifact_seen=False, delayed=False, unsupported=False)` so `retrieve_patch_bundle` reaches fenced fallback. Mapped selector Playwright failures still raise `DownloadUnsupportedError`; mapped metadata `PatchMalformedError` checks are unchanged.
- D3 audit found one additional genuine driver preflight gap: `_ensure_real_selector_map_ready` was still requiring real-empty optional selectors/attribute. `src/ask_chatgpt/driver.py:43-57` now preflights only required real selectors and `turn_id`; model selectors remain fail-closed only when `select_model` is actually asked to select a model, and `conversation_ref` remains URL-fallback tolerant at `driver.py:486-493`.

RED->GREEN EVIDENCE:
- RED GAP-7/GAP-8 focused command: `uv run pytest tests/test_readers.py::test_dom_reader_reads_body_when_truncation_marker_is_unmapped tests/test_patch.py::test_unmapped_download_artifact_selector_falls_back_to_valid_fenced_bundle`.
- RED result: `2 failed in 1.30s` (`truncation_marker` raised `SelectorUnavailableError`; `download_artifact` raised `DownloadUnsupportedError` before fenced fallback).
- GREEN focused command after fixes: `uv run pytest tests/test_readers.py::test_dom_reader_reads_body_when_truncation_marker_is_unmapped tests/test_readers.py::test_dom_reader_truncation_marker_raises_response_truncated tests/test_patch.py::test_unmapped_download_artifact_selector_falls_back_to_valid_fenced_bundle tests/test_patch.py::test_download_missing_falls_back_to_valid_fenced_bundle`.
- GREEN focused result: `4 passed in 2.47s`.
- RED driver-audit command before driver fix: `uv run pytest tests/test_driver_real_preflight.py::test_sparse_real_selector_map_preflight_tolerates_unmapped_optional_keys tests/test_driver_real_failclosed.py::test_real_start_fails_closed_on_missing_required_selector_before_playwright_start_and_navigation tests/test_driver_real_preflight.py::test_empty_real_selector_map_still_fails_before_profile_lock_and_launch`.
- RED driver-audit result: `1 failed, 2 passed in 0.07s` (`model_menu` was still preflight-required).
- GREEN driver-audit result after fix: `3 passed in 0.06s`.

D3 AUDIT TABLE:
| Access | Key(s) | Classification | UC1-3 reachable? | Action |
|---|---|---|---|---|
| `readers.py:32` | `assistant_message` | REQUIRED, real populated | read | Unchanged fail-closed |
| `readers.py:33` | `message_body` | REQUIRED, real populated | read | Unchanged fail-closed |
| `readers.py:35` | `truncation_marker` | OPTIONAL, real empty | read | Changed: unmapped -> skip truncation check |
| `readers.py:70` | `copy_button` | REQUIRED fallback selector, real populated | fallback read only | Unchanged fail-closed |
| `patch.py:303` | attr `turn_id` | REQUIRED, real populated | retrieve_patch_bundle | Unchanged fail-closed |
| `patch.py:313` | `download_artifact` | OPTIONAL, real empty | retrieve_patch_bundle | Changed: unmapped -> no candidate/fenced fallback |
| `bundle.py:318` | `upload_input` | REQUIRED, real populated | UC2 upload | Unchanged fail-closed/UploadUnsupported |
| `driver.py:224` | `model_option_disabled` | OPTIONAL/model-specific, real empty | only `select_model(model_settings)`; not `select_model(None)` | Unchanged fail-closed |
| `driver.py:283` | `completion_marker` | REQUIRED, real populated | wait_for_completion | Unchanged fail-closed |
| `driver.py:285` | `streaming_marker` | REQUIRED, real populated | wait_for_completion | Unchanged fail-closed |
| `driver.py:333` | dynamic `_REAL_REQUIRED_SELECTOR_KEYS` | REQUIRED preflight set | real start/preflight | Changed set to required-only; removed real-empty optional/model/download markers |
| `driver.py:335` | dynamic `_REAL_REQUIRED_ATTRIBUTE_KEYS` | REQUIRED preflight attr set | real start/preflight | Changed set to `turn_id` only; removed optional `conversation_ref` |
| `driver.py:450` | dynamic `_locator(key)` | helper for required selectors plus model/rate paths | caller-dependent | Unchanged; optional paths are gated (`select_model` request or prior rate marker visibility) |
| `driver.py:454` | dynamic `_optional_selector(key)` | optional helper | optional marker checks | Already tolerant; unchanged |
| `driver.py:519` | `assistant_message` | REQUIRED, real populated | wait_for_completion | Unchanged fail-closed |
| `driver.py:486` | attr `conversation_ref` | OPTIONAL, real empty | open/read active ref | Already tolerant with URL fallback; unchanged |

AUTHORITATIVE FULL DEFAULT SUITE:
- Command: `uv sync --all-groups && uv run pytest`.
- Summary: `====================== 154 passed, 1 deselected in 53.23s ======================`.
- Collection: `collected 155 items / 1 deselected / 154 selected`; default `-m not real_site` selected/executed zero `real_site` tests.
- Guard/maps check: `git diff --exit-code -- tests/conftest.py src/ask_chatgpt/selector_maps/mock.json src/ask_chatgpt/selector_maps/real.json` passed (`guard-and-maps-unchanged`).
- ZERO real messages / ZERO real-site contact.

GIT DIFF STAT:
```text
src/ask_chatgpt/driver.py            | 10 +---------
src/ask_chatgpt/patch.py             | 13 +++++++++++--
src/ask_chatgpt/readers.py           |  7 +++++--
tests/test_driver_real_failclosed.py |  9 +++++++--
tests/test_driver_real_preflight.py  | 12 +++++++++++-
tests/test_patch.py                  | 31 +++++++++++++++++++++++++++++++
tests/test_readers.py                | 24 ++++++++++++++++++++++++
7 files changed, 90 insertions(+), 16 deletions(-)
```
Note: `git diff --stat` also reports pre-existing `orchestration/state/M-006-state.json` dirt that was present before this leg and was not edited by this worker; `git status` also still shows the pre-existing untracked task file plus this new report.

MESSAGES_USED: 0
T2e-STATUS: DONE
