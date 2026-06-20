# M7b-T3b — Live tools-selection reflection discovery + fix-recipe validation (real-leg, ZERO sends)

You are a **pi real-leg worker** for team `ask-chatgpt-dev`, task **M7b-T3b**. You inherit **nothing** but this file. Read it in full, execute exactly. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. **ZERO sends** — opening menus and toggling a tool creates no conversation turn.

## Why this task exists
M7b-T3 verified that model selection works on the live composer, but **tool selection fails**: `set_tools(["Web search"])` clicks "Web search" successfully, then `_reflected_tool` re-enumerates the Radix portal and finds nothing checked → `TOOL_SELECTION_NOT_REFLECTED`. Hypothesis: the live Radix **tools menu closes (or the item detaches) on selection**, so re-enumerating the portal is empty — unlike the model picker, whose reflection is read from the persistent composer pill. Your job: **pin down exactly how a selected tool reflects on the live composer**, and **validate a robust verification recipe** the editor will implement. NO edits to `src/`, NO sends.

## SAFETY (shared browser, another active agent on conversation `6a316aa8`) — obey every line
- CDP `http://127.0.0.1:9222` SHARED. **OWN-TAB-ONLY**: only the tab YOU open; **never** `/json/list`, **never** enumerate `context.pages`/`browser.contexts`, **never** touch foreign tabs or conversation `6a316aa8`.
- **ZERO sends.** Do NOT fill+submit the composer, do NOT call `Session.ask/loop`. Only open menus / toggle a tool / read the DOM.
- **Never quit** the browser (detach only). **Preflight** `curl -s --max-time 5 .../json/version`; fail → `BLOCKED/CDP_UNREACHABLE`. **Login/Cloudflare** (no composer) → `BLOCKED/HUMAN-ACTION-NEEDED`; no stealth.
- **NEVER persist/log** auth/bearer/`oai-*`/cookie/session values. No conversation content (there is none on a fresh chat). Tool/model **labels** ("Web search", "Deep research") are safe product names. Redirect payload-bearing stdout to `/dev/null`; emit only safe metadata. Reuse `_scrub()` from `scripts/m7_t3c_real.py`.
- Branch `rewrite-v2` only; **never** move/commit `stable`; **never** `uv tool …`; **never** `git push`; **do NOT commit** (manager commits); never stage `cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`.

## Read first
- `src/ask_chatgpt/menus.py` — `open_radix_menu`, `enumerate_radix_options`, `select_radix_label`, and the failing `_reflected_tool` (it calls `enumerate_radix_options` and requires `option.checked is True`). `set_tools` opens `selectors["tools_button"]`, clicks the label, then `_reflected_tool`.
- `src/ask_chatgpt/channels/cdp.py` — `JS_MENU_ENUMERATE` (portal items + aria-checked), `JS_OPEN_RADIX_TRIGGER` (pointer-activation open), `evaluate` dispatch keys.
- `team/evidence/reports/M7b-T1-selectors.md` — tools_button `button[data-testid="composer-plus-btn"]` opens a portal with direct `menuitemradio` items incl. "Web search" (initial aria-checked "false").
- `scripts/m7b_t1_discover.py` and `scripts/m7_t3c_real.py` — scaffolding to reuse (preflight, git_checks, _scrub, emit, own-tab CdpChannel usage).

## Procedure — write `scripts/m7b_t3b_tools.py`, run `uv run python scripts/m7b_t3b_tools.py`
Use `CdpChannel` directly (own-tab), and the production `ask_chatgpt.menus` helpers where useful. NO `Session.ask`.
1. Preflight + branch/stable checks.
2. `channel = CdpChannel(...); channel.attach(); tab = channel.open_tab("https://chatgpt.com/")`; wait for `#prompt-textarea` (else STOP HUMAN-ACTION-NEEDED).
3. **Open tools menu** via the production path: `from ask_chatgpt.menus import open_radix_menu, enumerate_radix_options, select_radix_label`; `open_radix_menu(tab, "button[data-testid=\"composer-plus-btn\"]")`. Enumerate; record "Web search" presence + initial `aria-checked`/`checked`/`role`.
4. **Select the tool**: `select_radix_label(tab, "Web search")` (production click path, pointer-activated). Catch+record any error.
5. **Observe immediately after selection** (custom JS via `channel.evaluate`):
   - Is the portal `[data-radix-popper-content-wrapper]` still present AND visible? (record `portal_present_after_select`, `portal_visible_after_select`).
   - If present: enumerate and record "Web search" `aria-checked` now.
   - Dump **composer-area** indicators: scan buttons/elements near `#prompt-textarea` (and the `composer-plus-btn` area) for any element whose text/aria-label indicates an ACTIVE "Web search" tool (a chip/pill/badge), recording candidate selectors + `aria-pressed`/`data-state`/text (structural only, no conversation content).
6. **Validate the RE-OPEN recipe** (the likely fix): call `open_radix_menu(tab, "button[data-testid=\"composer-plus-btn\"]")` again, enumerate, and record whether "Web search" is now `aria-checked == "true"` / `checked is True`. This tells the editor whether "re-open the menu and read aria-checked" is a sound reflection check.
7. **Restore**: if "Web search" ended up toggled ON, toggle it OFF (open menu, `select_radix_label(tab, "Web search")` again) so the UI is left as found. Record restore outcome (non-fatal if it fails; do not retry-spam).
8. Detach (close your tab, `channel.detach()`); post-detach `/json/version` curl.
9. Write the report.

## Output (both)
1. `scripts/m7b_t3b_tools.py` (own-tab, no sends).
2. `team/evidence/reports/M7b-T3b-tools.md`, in order:
   - `Status:` (`DONE` if the reflection mechanism is characterized AND a working verification recipe is identified; `PARTIAL`/`BLOCKED` otherwise).
   - CDP preflight.
   - **Reflection mechanism:** does the tools menu **close** on tool-select (portal absent after select)? If it stays open, does aria-checked flip to true in place? 
   - **Re-open recipe result:** after re-opening the tools menu, is "Web search" `aria-checked == true`? (YES → editor verifies tool reflection by re-opening + reading aria-checked.)
   - **Composer-chip alternative:** any composer-level "Web search active" indicator + its exact selector (fallback reflection signal), or "none found".
   - **Recommended fix recipe** for the editor (concrete: e.g. "in set_tools, after select_radix_label, re-open tools_button menu via open_radix_menu and assert the option.checked is True for the requested label; then close/restore"). Note any caveat (e.g., whether re-open toggles state).
   - **Evidence**: initial vs post-select vs post-reopen aria-checked for "Web search"; portal-present booleans; composer-chip dump.
   - **Confirmations** (own-tab-only/no /json/list; ZERO sends; browser not quit/post-detach ok; no auth/oai/cookie logged; no conversation content; branch rewrite-v2; stable unchanged start/end; nothing staged).
   - Blockers (exact action) + Signals.

## Acceptance
- The report states **definitively** whether the tools menu closes on select and **whether re-opening shows aria-checked==true** (the fix recipe), plus any composer-chip selector. ZERO sends; own-tab-only; browser up; no leak; `stable` unmoved; nothing committed. Report honestly; the report file is your deliverable.
