START_TIMESTAMP: 2026-06-12T20:54:16-05:00
END_TIMESTAMP: 2026-06-12T21:00:08-05:00
ESTIMATE: T2d 5m

CHANGE:
- `src/ask_chatgpt/driver.py:460-463`: added `_optional_selector(key) -> str | None`, returning `None` only when `SelectorMap.selector(key)` raises `SelectorUnavailableError`.
- `src/ask_chatgpt/driver.py:466-473`: changed `_present(key)` to return `False` for an unmapped/empty optional selector and still wrap genuine `PlaywrightError` count/locator failures as `SelectorUnavailableError`.
- `src/ask_chatgpt/driver.py:288-289`: guarded the latest-assistant truncation check with `_optional_selector("truncation_marker")`; unmapped means skipped, mapped behavior unchanged.
- `_require_present` remains hard-fail and unchanged at `src/ask_chatgpt/driver.py:475-483`.

RED->GREEN EVIDENCE:
- RED focused command: `uv sync --all-groups && uv run pytest tests/test_driver_optional_markers.py -q`.
- RED result: `4 failed, 3 passed in 1.37s`; failures were empty optional selectors raising `SelectorUnavailableError` from `selector_map.py`.
- GREEN full default command, run once after implementation: `uv sync --all-groups && uv run pytest`.
- Authoritative summary: `====================== 151 passed, 1 deselected in 53.22s ======================`

TIER PURITY / GUARDED FILES:
- Default pytest config is `-m not real_site`; full run reported `collected 152 items / 1 deselected / 151 selected`, so zero `real_site` tests were selected/executed.
- Socket guard unchanged: `tests/conftest.py` has no diff.
- `mock.json` unchanged; `real.json`, `selector_map.py`, `api.py`, and `cli.py` also have no diff.
- Mock UC1 happy path remained green in full suite: `tests/test_ask_chatgpt_uc1.py ....` and `tests/test_driver.py ...............`.
- ZERO real messages / ZERO real-site contact.

GIT DIFF STAT:
```text
src/ask_chatgpt/driver.py | 14 ++++++++++++--
1 file changed, 12 insertions(+), 2 deletions(-)
/dev/null => tests/test_driver_optional_markers.py | 155 +++++++++++++++++++++
1 file changed, 155 insertions(+)
```
Note: initial status already had unrelated orchestration dirt (`orchestration/state/M-006-state.json`, T3/task files); this leg touched only `src/ask_chatgpt/driver.py`, `tests/test_driver_optional_markers.py`, and this report.

MESSAGES_USED: 0
T2d-STATUS: DONE
