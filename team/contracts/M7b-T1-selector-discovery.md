# M7b-T1 — Live model/tool composer selector rediscovery (real-leg, ZERO sends)

You are a **pi worker** for team `ask-chatgpt-dev`, task **M7b-T1**. You inherit **nothing** but this file. Read it in full and execute it exactly. Repo: `/home/abhmul/dev/ask-chatgpt`. Branch: **`rewrite-v2`** (do not switch branches).

## Why this task exists (ground truth)
The library's offline selector map `src/ask_chatgpt/selectors/real.json` has model/tool composer selectors that **do not match the live chatgpt.com composer**. A prior real leg (M7-T3) found:
- `model_picker_trigger_candidates` = `composer-footer button[aria-haspopup="menu"]` → matched **0** elements (`model_trigger_count=0`) → model selection fails `MODEL_SELECTION_NOT_REFLECTED`.
- `tools_button` = `button[data-testid="composer-plus-btn"]` → opening the tools menu raised a **`TimeoutError`** → tool selection fails `TOOL_SELECTION_NOT_REFLECTED`.

Your job: **empirically rediscover the ACTUAL live selectors** by opening each menu on a fresh throwaway chat and dumping the live DOM, then **report exact, verified candidate selectors** for the editor to apply. **You make NO source edits and send NO messages.** Opening a menu and reading the DOM creates no conversation turn — this task needs **ZERO sends**.

## SAFETY — read and obey every line (the browser is SHARED with another ACTIVE agent)
- The CDP browser at `http://127.0.0.1:9222` is **SHARED** with another active agent that is keep-pushing on conversation id **`6a316aa8`**. 
- **OWN-TAB-ONLY.** Operate exclusively on the single tab **you** open via `CdpChannel.open_tab(...)`. **NEVER** call `/json/list`, **never** enumerate `browser.contexts`/`context.pages`, **never** read, click, navigate, or touch any tab you did not open, and **never** touch conversation `6a316aa8` or any foreign tab. A loose tab-walker previously leaked the operator's conversation — do not enumerate tabs.
- **ZERO sends.** Do not fill+submit the composer. Do not call `Session.ask/loop`. Do not create any conversation. You only **open menus and read the DOM**.
- **Never quit the browser.** Detach only (close the tab you opened, then `channel.detach()`); never call `browser.close()` on a context you didn't create beyond Playwright's CDP-client disconnect, never kill Chrome.
- **Preflight** before attaching: `curl -s --max-time 5 http://127.0.0.1:9222/json/version`. If it fails → STOP, write report with status `BLOCKED`, code `CDP_UNREACHABLE`, do nothing else.
- **Login / Cloudflare challenge** ("Just a moment...", a login wall, or no composer after load) → **STOP immediately**, status `BLOCKED`, code `HUMAN-ACTION-NEEDED`. Do NOT attempt to log in, solve a challenge, or use any stealth/anti-detection. No retries-spam.
- **NEVER persist or log** any authorization/bearer token, `oai-*` header, cookie, or session value — not to stdout, not to any file. You will not be reading network headers in this task at all; if you incidentally encounter any, never emit them.
- **No conversation content** in any output. On a fresh new-chat tab there is none; keep it that way. Model/tool **feature labels** ("GPT-5.1 Thinking", "Web search", "Deep research", "Create image", etc.) are product names and are safe to record.
- **Redirect** any stdout that could carry payload to `/dev/null`; emit only safe structural metadata (selectors, counts, roles, labels).
- Repo isolation: branch **`rewrite-v2`** only. **NEVER** `git checkout`/move/commit the **`stable`** branch. **NEVER** run `uv tool install/upgrade/reinstall`. **NEVER** `git push`. Do not stage `cache/`, `issues/cdp-send-repro/controller.mjs`, or `human/`. You will not commit at all — the manager commits.
- `uv run …` (project `.venv`) is safe and isolated; use it for Python. Playwright is installed in the project venv (prior real legs used it).

## Inputs to read first
- `src/ask_chatgpt/selectors/real.json` — the current (wrong) selectors.
- `src/ask_chatgpt/channels/cdp.py` — the production `CdpChannel`. Note `open_tab(url)` (own-tab), `evaluate(tab, js, arg=...)` (runs raw JS via `page.evaluate`), `wait_for_selector`, `click`, `reload`, `detach`. The Radix-portal enumerate JS is `JS_MENU_ENUMERATE` (selects `[role="menuitem"],[role="menuitemradio"],[role="menuitemcheckbox"]` inside `[data-radix-popper-content-wrapper]`).
- `src/ask_chatgpt/menus.py` — how selectors are used: `select_model` clicks `selectors["model_picker_trigger_candidates"]` then enumerates the portal; the **current model label** is read from `query_turns(...).model_labels`, which (see `cdp.py` `JS_QUERY_TURNS`) maps the `model_picker_trigger_candidates` selector's element text. `set_tools` clicks `selectors["tools_button"]` then enumerates the portal.
- `scripts/m7_t3c_real.py` — **reuse its safety scaffolding**: `_scrub()`, `git_checks()`, `preflight_version()`, safe `emit()`. Copy that style.
- Durable facts: ChatGPT model picker + tools "+" menu are **Radix dropdowns**; their options render in a portal `[data-radix-popper-content-wrapper]` **only AFTER** the trigger is clicked (enumerate after opening). Model tiers are `menuitemradio`; a model family is a `menuitem` submenu. There is **no stable test-id** on the model picker (label-driven).

## Procedure (write a driver `scripts/m7b_t1_discover.py`, run with `uv run python scripts/m7b_t1_discover.py`)
Build the driver on `CdpChannel` directly (NOT `Session.ask`), own-tab-only. Steps:

1. **Preflight** curl `/json/version`. Abort `BLOCKED/CDP_UNREACHABLE` on failure.
2. Confirm branch is `rewrite-v2` (`git rev-parse --abbrev-ref HEAD`); record `stable` rev (do not move it).
3. `channel = CdpChannel(cdp_endpoint="http://127.0.0.1:9222")`; `channel.attach()`. Open **one** fresh tab: `tab = channel.open_tab("https://chatgpt.com/")`. Wait for the composer `#prompt-textarea` (`channel.wait_for_selector(tab, "#prompt-textarea", state="visible", timeout_s=20)`). If it never appears or a challenge/login is present → STOP `HUMAN-ACTION-NEEDED`.
4. **Gap-1a — model picker trigger + label readout.** Via `channel.evaluate(tab, "<raw JS>")`, dump structural candidates **without** any conversation content. Concretely, enumerate every `button`/`[role=button]` near the composer and report for each: `tagName`, `data-testid`, `aria-haspopup`, `aria-label`, `type`, a short `class` hint, and trimmed `innerText` (≤40 chars). Identify the button that **shows/opens the model picker** (its text is usually the current model name, e.g. "GPT-5.1"). Then:
   - Determine a **precise, unique** CSS selector that matches **exactly one** element and is the model trigger. Verify `document.querySelectorAll(sel).length === 1`.
   - **Click it** (use `channel.click(tab, sel)` or dispatch a real click in JS), wait up to 5s for `[data-radix-popper-content-wrapper]` to be visible, then dump the portal's menu items (role + label + aria-checked) so we confirm the tiers/families render. Record the item count and a few labels.
   - Identify the **current-model-label readout** selector — the element whose text is the active model name (often the trigger button itself, or a `span` inside it). This is what the sustained ~12s read will poll. Confirm it returns exactly one non-empty label.
   - Close the menu (press `Escape` on the page, or click the trigger again) so the next step starts clean.
5. **Gap-1b — tools ("+") button + tools menu.** Similarly dump candidate buttons; the offline guess is `button[data-testid="composer-plus-btn"]`. Confirm whether it exists/matches; if not, find the real "+"/tools trigger. Click it, wait for the portal, dump the menu items (labels + roles + aria-checked). Determine whether tools (e.g. "Web search", "Deep research", "Create image", "Study"...) are **direct** `menuitem`s in this menu or live behind a **submenu** (e.g. "More"). Record the exact `tools_button` selector and the submenu path (if any) needed to reach a tool like "Web search". Close the menu.
6. **Detach**: close your tab, `channel.detach()`. Confirm via a second `/json/version` curl that the browser is still up (you did not quit it).
7. Write findings.

If any click/enumeration fails, **fail closed**: record what you observed (the candidate dumps are the valuable output even on partial failure) and continue to the next sub-step where safe.

## Output (both required)
1. **Driver**: `scripts/m7b_t1_discover.py` (safe-emit, own-tab-only, no sends).
2. **Findings report**: `team/evidence/reports/M7b-T1-selectors.md`. Include, in this order:
   - `Status:` line (`DONE` if both model + tools selectors found and verified `length===1` and menus opened; `PARTIAL` if only one found; `BLOCKED` if preflight/login/challenge).
   - **CDP preflight**: browser version, ws present.
   - **Recommended real.json selectors** — a fenced code block giving the EXACT string for each key the editor should set:
     - `model_picker_trigger_candidates`: `<exact selector>` (must match exactly 1, must open the model portal)
     - `tools_button`: `<exact selector>` (must match exactly 1, must open the tools portal)
     - If the **current-model-label readout** needs a **different** selector than the trigger, propose a NEW key `model_label_readout`: `<exact selector>` and **explicitly flag** that the editor must add it to `REQUIRED_SELECTOR_KEYS` in `src/ask_chatgpt/selectors/__init__.py` AND the mock/tests — otherwise omit and confirm the trigger's own text is the readout.
     - Tools menu shape: whether `set_tools` can select e.g. "Web search" directly or needs a `submenu_path` (give it).
   - **Evidence**: for each chosen selector, the `querySelectorAll(...).length`, the opened-portal item count, and 3–5 sample menuitem labels (product names only).
   - **Button dumps**: the structural candidate dumps (attributes only) for model + tools areas, so the editor/manager can see alternatives.
   - **Confirmations**: own-tab-only (no `/json/list`, no page enumeration); ZERO sends (`successful_submissions` not applicable — you never used Session/send); browser not quit (post-detach `/json/version` ok); no auth/cookie/oai value logged; no conversation content; branch `rewrite-v2`; `stable` rev unchanged start vs end; nothing staged.
   - **Blockers** (exact action needed) and **signals** (e.g. live UI differs from M2 in a specific way).

## Acceptance for this task
- `team/evidence/reports/M7b-T1-selectors.md` exists with EXACT, DOM-verified (`length===1`, portal-opens) selectors for the model trigger and tools button (and the label readout decision), plus the tools submenu path if any.
- ZERO sends; own-tab-only; browser still up; no leak; `stable` unmoved; nothing staged/committed (the manager commits).
- Report honestly. If the live UI blocks discovery (challenge/login), `BLOCKED/HUMAN-ACTION-NEEDED` with the exact operator action is the correct, acceptable outcome — never fabricate a selector you did not verify against the live DOM.

When finished, ensure the report file is written (it is your deliverable; the manager verifies the file, not your stdout).
