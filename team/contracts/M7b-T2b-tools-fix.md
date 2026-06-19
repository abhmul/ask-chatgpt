# M7b-T2b — Fix tool-selection reflection (menu closes on select → verify by re-open), OFFLINE

You are the **single pi source editor** for team `ask-chatgpt-dev`, task **M7b-T2b**. You inherit **nothing** but this file. Read in full, execute exactly. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**, HEAD `1ea867a`. **OFFLINE** — no browser/CDP, no sends. You are the only `src/` editor; make all edits here.

## The bug (live-confirmed by M7b-T3 + M7b-T3b)
Model selection now works live, but `menus.set_tools(["Web search"])` fails `TOOL_SELECTION_NOT_REFLECTED`. Root cause, confirmed on the live composer: **the Radix tools menu CLOSES/detaches when a tool is selected.** Current `set_tools` opens the tools menu once, then for each label calls `select_radix_label` (clicks → menu closes) and immediately `_reflected_tool` (which `enumerate_radix_options` on the now-absent portal → empty → `None` → error). The model picker doesn't hit this because `_reflected_model` reads the **persistent** composer pill, not the portal.

**Live-validated fix recipe (M7b-T3b):** after selecting a tool, **re-open** the tools menu (`open_radix_menu(tab, selectors["tools_button"])`) and enumerate — the tool then shows `checked is True` (`aria-checked="true"`). Re-opening to verify does **not** toggle the tool. Evidence: initial enumerate had Web search `checked:false`; after select + re-open it was `checked:true`.

## Required edits
1. **`src/ask_chatgpt/menus.py` — make `set_tools` verify reflection by re-opening the menu (handle close-on-select per label):**
   - Restructure so each requested label is: (a) ensure the tools menu is open (`open_radix_menu(tab, selectors["tools_button"])`); (b) `select_radix_label(tab, label)` (clicks; the live menu closes); (c) **re-open** the tools menu and `enumerate_radix_options`; (d) require **exactly one** enabled option whose normalized label == the requested label has `checked is True` (reuse the `_enabled_matches`/`checked` logic) → that is the reflected confirmation; (e) **close the menu** afterward (so the composer is clean for a subsequent send — e.g. `tab.channel.press(tab, "body", "Escape")`, tolerate failure). On no-reflection → raise `ToolSelectionNotReflectedError` (fail-closed, unchanged error type/details shape).
   - IMPORTANT: do **not** toggle the tool off — a requested tool must stay ON after `set_tools` (only the menu is closed). The per-label loop must tolerate the menu being closed between labels (re-open before each select). Keep the forbidden-submenu guard and the existing fail-closed `except` structure.
   - You may add a small private helper (e.g. `_reflected_tool_by_reopen(tab, selectors, label)` and `_close_radix_menu(tab)`). Keep `_reflected_tool` or replace it — your call — but keep the public `set_tools`/`assert_reflected_tools` signatures unchanged.
   - (Reference only — a composer-level active-tool chip `button[aria-label="Search, click to remove"]` also exists as a fallback signal; the re-open recipe is the validated primary. Do not depend on the chip.)

2. **`src/ask_chatgpt/channels/mock.py` — model menu-close-on-tool-select so the offline test is falsifiable:**
   - Add `MockScenario.menu_closes_on_select: bool = False`. In `_menu_click_label`, when `action == "select"` and `self.scenario.menu_closes_on_select` is true, after recording the click and setting the matched option's `checked = True`, set `self._active_menu_key = None` (model the menu closing). The checked state persists in `self._menu_options_by_key`, so a later re-open (`ask_chatgpt_open_radix_trigger` / `click` → sets `_active_menu_key` again) re-exposes the option with `checked: True`.
   - This makes the new `set_tools` (re-open) succeed while the OLD behavior (immediate re-enumerate) would see an empty portal.

3. **Falsifiable offline test(s)** (`tests/test_menus.py`):
   - Add a test with `menu_closes_on_select=True` where `set_tools(tab, SELECTORS, ("Web search",))` **succeeds** (`verified is True`, `reflected == "Web search"`), and assert the tools trigger was opened **twice** (select + verify re-open) — e.g. via the recorded `ask_chatgpt_open_radix_trigger` evaluate calls (`call.details.get("js_key")`) or a menu-open counter. Comment what reverting the re-open would break.
   - **Prove it yourself:** confirm that with `menu_closes_on_select=True`, the OLD single-enumerate behavior would fail — i.e. your new test must FAIL if `set_tools` is reverted to verify without re-opening. State this in a comment.
   - Keep all existing menu tests green (the default `menu_closes_on_select=False` preserves current behavior).

## Constraints
- `uv run pytest` must be **green** (current baseline 253 passed; your additions should raise it). Use `uv run`; never `uv tool`. Offline only — no browser.
- Branch `rewrite-v2`; never move/commit `stable`; never `git push`; **do NOT `git commit`** (manager inspects + commits). Never stage `cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`.
- Minimal, correct change (Occam). Do not touch the model-selection path (it works live) or the send/submit path.

## Output
- Edits in the working tree (NOT committed). Report `team/evidence/reports/M7b-T2b-tools-fix.md`: `Status:`, files changed, the `set_tools` re-open recipe summary, the mock `menu_closes_on_select` model, the new test name + what reverting the re-open breaks (and that you verified it fails when reverted), final `uv run pytest` count, and confirmation: no browser, no commit, branch `rewrite-v2`, `stable` unmoved, no `uv tool`, nothing staged.
- The manager re-runs `uv run pytest`, independently proves falsifiability, and commits.
