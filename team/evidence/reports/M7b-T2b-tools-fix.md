# M7b-T2b tools fix

Status: complete.

Files changed by this task:
- `src/ask_chatgpt/menus.py`
- `src/ask_chatgpt/channels/mock.py`
- `tests/test_menus.py`
- `team/evidence/reports/M7b-T2b-tools-fix.md`

`set_tools` recipe: for each requested tool label, open the tools Radix menu, select the label, re-open the tools menu, verify exactly one enabled normalized matching option is `checked is True`, then best-effort close the menu with `Escape` without toggling the tool off.

Mock model: `MockScenario.menu_closes_on_select` defaults to `False`; when true, `_menu_click_label` persists the selected option's checked state and clears `_active_menu_key`, so immediate enumeration sees an empty portal and a re-open exposes the checked option. The mock also clears the active menu on `Escape`.

New test: `test_set_tools_reopens_tools_menu_after_select_when_menu_closes`. It succeeds with `menu_closes_on_select=True`, verifies `reflected == "Web search"` and `verified is True`, and asserts two `ask_chatgpt_open_radix_trigger` calls. Reverting the re-open would break because the old immediate enumerate sees no active portal and raises `TOOL_SELECTION_NOT_REFLECTED`; verified with an old single-enumerate probe (`open_count=1`, error code `TOOL_SELECTION_NOT_REFLECTED`).

Final pytest: `uv run pytest` collected 254 items and passed `254 passed in 0.99s`.

Confirmations: no browser, no CDP, no sends; no commit; branch `rewrite-v2`; `stable` observed at `779eb40b196e1a458a820248b2dbbca22411b0d3` and not moved; no `uv tool`; nothing staged.
