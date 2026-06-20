# M9-W8 chip label-specific handoff

Status: COMPLETE (M9-W8). Top: offline-only change; no browser/CDP/chatgpt.com touched.

## What changed

- `src/ask_chatgpt/menus.py:350-373`: `_reflected_tool_by_chip` now fail-closes unless a visible label-scoped removable chip selector matches the selected label: `:is(<active_tool_chip>)[aria-label*=<selected label> i]`. The existing menu reopen/`aria-checked` path remains primary at `src/ask_chatgpt/menus.py:194-198`.
- `tests/test_menus.py:9-14,338-411`: updated the unchecked Deep Research chip test to use a matching label-scoped selector; added the non-matching-chip fail-closed falsifier; kept no-signal and Web-search fail-closed tests explicit about absent label-specific chips.
- `team/evidence/reports/M9-W8-pytest.txt`: captured full green `uv run pytest` output.

## Falsifiability RED on revert

Temporary revert used generic `selectors["active_tool_chip"]` in `_reflected_tool_by_chip`, then ran `uv run pytest tests/test_menus.py::test_set_tools_fails_closed_when_only_nonmatching_composer_chip_present -q`; exit 1:

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_set_tools_fails_closed_when_only_nonmatching_composer_chip_present ____

>       with pytest.raises(ToolSelectionNotReflectedError) as excinfo:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE <class 'ask_chatgpt.errors.ToolSelectionNotReflectedError'>

tests/test_menus.py:375: Failed
=========================== short test summary info ============================
FAILED tests/test_menus.py::test_set_tools_fails_closed_when_only_nonmatching_composer_chip_present
1 failed in 0.04s

Command exited with code 1
```

## Green suite

`uv run pytest > team/evidence/reports/M9-W8-pytest.txt 2>&1`; exit 0. Tail/count:

```text
collected 268 items
...
tests/test_store_torn_line.py ...                                        [100%]

============================= 268 passed in 1.02s ==============================
```

## Artifacts and trust

- Trusted: `team/evidence/reports/M9-W8-pytest.txt` from offline `uv run pytest`, no browser/CDP.
- Ground truth rechecked: `team/evidence/reports/M9-W6-reverify.txt` records live DR chip aria-label `Deep research, click to remove`, which contains selected label `Deep research`.
- Correctness concern addressed: `team/evidence/reports/M9-panel/LC-correctness-honesty.md` identified the former generic chip false-positive risk.

## Blockers / caveats

- `git status --porcelain` was already dirty before this work with many unrelated tracked/untracked M9 files, including protected-looking paths such as `issues/cdp-send-repro/controller.mjs`, `human/`, `scripts/m9_*`, prior contracts/reports/handoffs, and other `src/`/`tests/` files. I did not clean or commit. Intended W8 touches are `src/ask_chatgpt/menus.py`, `tests/test_menus.py`, `team/evidence/reports/M9-W8-pytest.txt`, and this handoff.

## Recommended next

- Review only the W8 hunks in `src/ask_chatgpt/menus.py` and `tests/test_menus.py`; preserve the label-specific chip fallback and the non-matching-chip falsifier.
