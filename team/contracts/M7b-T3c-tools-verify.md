# M7b-T3c — Live re-verify: tool selection now reflects (real-leg, ZERO sends)

You are a **pi real-leg worker** for team `ask-chatgpt-dev`, task **M7b-T3c**. You inherit **nothing** but this file. Read in full, execute exactly. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`** (HEAD `90281f3`). **ZERO sends.**

## What you verify
M7b-T2b changed `menus.set_tools` to verify tool reflection by **re-opening** the tools menu after select (the live Radix tools menu closes on select). Confirm on the live composer that `set_tools(["Web search"])` now **verifies True** (no `TOOL_SELECTION_NOT_REFLECTED`), fail-closed otherwise. Opening menus + toggling a tool creates **no conversation turn → ZERO sends.** This closes the remaining half of gap-1 (model selection was already verified in M7b-T3).

## SAFETY (shared browser, another active agent on `6a316aa8`) — obey every line
- CDP `http://127.0.0.1:9222` SHARED. **OWN-TAB-ONLY**: only the tab YOU open; **never** `/json/list`, never enumerate `context.pages`/`browser.contexts`, never touch foreign tabs or conversation `6a316aa8`.
- **ZERO sends.** No composer fill+submit, no `Session.ask/loop`. Only menus/tool-toggle/DOM reads.
- **Never quit** the browser (detach only). **Preflight** curl `/json/version`; fail → `BLOCKED/CDP_UNREACHABLE`. **Login/Cloudflare** → `BLOCKED/HUMAN-ACTION-NEEDED`; no stealth.
- **NEVER persist/log** auth/bearer/`oai-*`/cookie/session values. No conversation content. Tool labels are safe product names. Redirect payload stdout to `/dev/null`; emit safe metadata only (`_scrub` from `scripts/m7_t3c_real.py`).
- Branch `rewrite-v2`; never move/commit `stable`; never `uv tool …`; never `git push`; **do NOT commit** (manager commits); never stage `cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`.

## Procedure — write `scripts/m7b_t3c_tools_verify.py`, run `uv run python scripts/m7b_t3c_tools_verify.py`
1. Preflight + branch/stable checks.
2. `session = Session(channel="cdp", data_dir=Path("cache/m7b-t3c-verify")); session.attach()`. `draft = session.create(); tab = session.tab_pool.acquire(draft)` (your fresh new-chat tab). Wait for `#prompt-textarea` (else STOP HUMAN-ACTION-NEEDED).
3. **Verify tool selection (NO send):** `from ask_chatgpt.menus import set_tools`; `res = set_tools(tab, session.selector_map, ["Web search"])`. Record `res[0].verified`, `res[0].reflected`. On exception, record the typed error code (a `TOOL_SELECTION_NOT_REFLECTED` here would mean gap-1 tools is STILL not closed → report it as the M8 blocker).
4. (Optional, polite) toggle Web search back OFF by another `set_tools`/`select_radix_label` so the UI is left as found; non-fatal if it fails; do not retry-spam.
5. Assert `session.send_budget.successful_submissions == 0` (this leg sends nothing).
6. `session.tab_pool.release(tab); session.detach()`; post-detach `/json/version` curl.
7. Write the report.

## Output (both)
1. `scripts/m7b_t3c_tools_verify.py` (own-tab, ZERO sends).
2. `team/evidence/reports/M7b-T3c-tools-verify.md`: `Status:` (`DONE` if tool selection verified True; `PARTIAL`/`BLOCKED` otherwise); CDP preflight; **send count == 0** (assert); the `set_tools` verified/reflected result OR the exact typed error; verdict gap-1 tools CLOSED/NOT; confirmations (own-tab-only/no `/json/list`; ZERO sends; browser not quit/post-detach ok; no auth/oai/cookie logged; no conversation content; branch `rewrite-v2`; `stable` unchanged start/end; nothing staged; `6a316aa8` untouched); blockers + signals.

## Acceptance
- `set_tools(["Web search"])` **verifies True** on the live composer; ZERO sends; own-tab-only; browser up; no leak; `stable` unmoved; nothing committed. Report honestly — if it still fails, give the exact error as the M8 blocker. The report file is your deliverable.
