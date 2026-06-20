STATUS: DONE

Verified with `uv run pytest` after commit:

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/abhmul/dev/ask-chatgpt
configfile: pyproject.toml
testpaths: tests
collected 96 items

tests/test_allowlist.py .......................                          [ 23%]
tests/test_channels_base.py ...                                          [ 27%]
tests/test_errors.py ....................                                [ 47%]
tests/test_identity.py ..............                                    [ 62%]
tests/test_models.py ..............                                      [ 77%]
tests/test_selectors.py ..................                               [ 95%]
tests/test_smoke.py ....                                                 [100%]

============================== 96 passed in 0.06s ==============================
```

Falsifiability / RED notes:
- Observed RED before implementation for the new module slices: `tests/test_errors.py` failed with `ModuleNotFoundError: No module named 'ask_chatgpt.errors'`; identity/models/allowlist/selectors/channel-session slices likewise failed on missing public imports before their minimal implementations.
- `tests/test_allowlist.py::test_allowlist_rejects_suffix_confusion_relative_and_unsafe_schemes` flips if host matching is changed to naive substring matching (`chatgpt.com.evil.example` becomes accepted).
- `tests/test_selectors.py::test_missing_any_required_key_raises_selector_not_found` flips if selector validation only checks `composer` or silently fills missing `model_picker_trigger_candidates`.
- `tests/test_models.py::test_turn_record_rejects_inconsistent_status_and_identity` flips if `TurnRecord(status="complete", partial=True)` or a complete `local:` id is accepted.

Commit:

```text
7c1cdf3 M4 step 1: scaffold offline core seam
```

`git show --stat HEAD`:

```text
commit 7c1cdf3ff3239d8cb6033adab33fa269616671f5
Author: jetm <abhmul@gmail.com>
Date:   Thu Jun 18 16:02:58 2026 -0500

    M4 step 1: scaffold offline core seam

 src/ask_chatgpt/__init__.py           | 100 ++++++++++++
 src/ask_chatgpt/allowlist.py          | 102 ++++++++++++
 src/ask_chatgpt/channels/__init__.py  |  19 +++
 src/ask_chatgpt/channels/base.py      | 110 +++++++++++++
 src/ask_chatgpt/errors.py             | 286 ++++++++++++++++++++++++++++++++++
 src/ask_chatgpt/identity.py           | 156 +++++++++++++++++++
 src/ask_chatgpt/models.py             | 273 ++++++++++++++++++++++++++++++++
 src/ask_chatgpt/selectors/__init__.py |  91 +++++++++++
 src/ask_chatgpt/selectors/real.json   |  12 ++
 src/ask_chatgpt/session.py            | 118 ++++++++++++++
 tests/test_allowlist.py               |  90 +++++++++++
 tests/test_channels_base.py           | 116 ++++++++++++++
 tests/test_errors.py                  |  95 +++++++++++
 tests/test_identity.py                |  80 ++++++++++
 tests/test_models.py                  | 219 ++++++++++++++++++++++++++
 tests/test_selectors.py               |  76 +++++++++
 16 files changed, 1943 insertions(+)
```

Blockers: none.

Deliberately deferred to E2+: `resolve_conv_or_alias` store/index resolution, JSONL/store serialization and warning handling, mock/cdp channel implementations, capture/send/completion logic, attachment fetching, and real CLI behavior beyond the existing smoke scaffold. `Session` is intentionally an importable facade with documented signatures and `NotImplementedError` bodies.
