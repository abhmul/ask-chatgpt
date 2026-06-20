# M9 · W2 — Real-leg discovery + NO-SEND menu verify (file-input/chip; GPT-5.5 family; Deep Research)

You are a **pi worker** running an **ATTENDED real-site CDP leg** for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **ZERO sends in this task.** Discovery + menu **selection** only.

## SAFETY — READ AND OBEY VERBATIM (shared browser; another active agent is using it)
- The browser at **`http://127.0.0.1:9222`** is **SHARED with another ACTIVE agent** working on conversation/target **`6a316aa8`** (full id `6a316aa8-5dc8-83ea-9014-b8ea38dabc31`).
- **OWN-TAB-ONLY.** Operate **only** on tabs **your driver opens** via the production `CdpChannel.open_tab`. **NEVER** read, iterate, enumerate, or touch any pre-existing/foreign tab **or** the target `6a316aa8`. Do **NOT** call `context.pages`, `/json/list`, `browser.contexts[...].pages`, or any page-enumeration. The production `CdpChannel` already attaches without enumerating — keep it that way.
- **FRESH throwaway tab ONLY** (a brand-new `https://chatgpt.com/` new-chat tab you open). **ZERO sends** — never click send/submit, never press Enter to submit, never create a conversation.
- **Preflight:** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` BEFORE attaching. If it fails → **STOP**, write `CDP_UNREACHABLE` in your handoff, do nothing else.
- **Login wall / Cloudflare "Just a moment…" / any challenge** → **STOP immediately**, write `HUMAN-ACTION-NEEDED` in your handoff, detach, do nothing else. Do **NOT** attempt to log in or bypass. **No stealth/anti-detection, ever.**
- **Never quit the browser.** Use `channel.detach()` only (client disconnect; browser stays alive). After detach, confirm the browser is still up with another `curl … /json/version`.
- **NEVER persist or log** any `authorization`/`oai-*`/`cookie`/`session` value or any conversation content. Redact. Your driver/report/logs must be credential-free and content-free.
- Domain allowlist applies (only chatgpt.com). Human-paced; no rapid loops.
- **Model/tool selection = NO send.** Switching the model or toggling a tool on your OWN fresh tab is per-composer state, affects no other tab, and creates no conversation — but you MUST **restore** the original model and toggle every tool back OFF before detaching.

## WORKER PYTHON GOTCHA (or you will waste the leg)
Bare `python`/`python3` here resolves to a **shared agent-python venv WITHOUT playwright or ask_chatgpt**. Run your driver with **`uv run python scripts/m9_w2_discover.py`** (the repo's own venv has playwright + the library). Never bare `python`.

## Drive via the PRODUCTION library API (not a bespoke DOM probe — avoid false-negatives)
Write `scripts/m9_w2_discover.py` using the production code, own-tab-only:
```python
from pathlib import Path
from ask_chatgpt.channels.cdp import CdpChannel
from ask_chatgpt.selectors import load_selector_map
from ask_chatgpt import menus
sel = load_selector_map("real")                  # includes file_input + attachment_chip (W1 added them)
ch = CdpChannel(cdp_endpoint="http://127.0.0.1:9222")
ch.attach()
tab = ch.open_tab("https://chatgpt.com/")        # YOUR OWN fresh new-chat tab
ch.wait_for_load_state(tab, timeout_s=30)
# ... checks below ...
ch.detach()
```
If `open_tab`/load raises or you see a login/challenge page → STOP HUMAN-ACTION-NEEDED.

## Checks (all NO-SEND). Record exact results for each.
### A. Upload affordance: confirm `file_input` + discover the real `attachment_chip`
1. Create a small throwaway file: `Path("/tmp/m9-upload.txt").write_text("m9 upload probe\n")`.
2. Confirm the composer **file input** selector. W1 wired `file_input = 'input[type="file"]'`. Verify it matches the composer's hidden file input on the live page (count, and that `set_input_files` accepts it). Record the exact working selector (correct it if `input[type="file"]` is wrong/ambiguous — e.g. multiple inputs; prefer the composer-scoped one).
3. **Stage (NOT send)** the file: `ch.upload_files(tab, sel["file_input"], [Path("/tmp/m9-upload.txt")])`. This attaches the file to the composer; it does **not** send.
4. Observe the **attachment chip/preview** that appears in the composer. Discover its **real selector**. W1 hypothesized `attachment_chip = '[data-testid="composer-attachment"], div[data-testid*="attachment"], button[aria-label*="Remove" i]'`. Confirm whether the production `ch.wait_for_selector(tab, sel["attachment_chip"], state="visible", timeout_s=10)` finds the staged chip. If NOT, introspect your OWN tab's composer (read-only `ch.evaluate(tab, "<JS returning candidate selectors of the new chip element>")`) and report the **correct** chip selector (data-testid / aria-label / class). This is critical — W4's real upload smoke + the offline fail-closed guard depend on it.
5. **Discard** the staged file without sending: `ch.reload(tab)` (reloads the new-chat tab, dropping the staged attachment). Confirm composer is empty. NO send.

### B. GPT-5.5 family submenu model selection (NO send) — EMPIRICAL
Per the M2 live probe, the model picker (trigger `sel["model_picker_trigger_candidates"]` = `form button[aria-haspopup="menu"]:not([data-testid])`) has top-level `menuitemradio` tiers (Instant/Medium/High/Extra High/Pro Extended) **and** a `GPT-5.5` **family `menuitem`** whose submenu holds sub-radios (M2 saw `5.5`, `5.4`, `5.3`, `4.5 …`, `o3`). The offline `select_model` family branch is **mock-shaped** and may not handle live sub-entries.
1. `menus.open_radix_menu(tab, sel["model_picker_trigger_candidates"])` then `menus.enumerate_radix_options(tab)`. Record **every** top-level option (label, role, checked) and the **current/checked** model label. Close the menu.
2. Open the **GPT-5.5 family submenu** and enumerate its sub-entries: record each sub-radio (label, role, checked). (Record the EXACT labels — W3 needs them to build a falsifiable test against the real shape.)
3. **Empirically test the production path**: pick a family sub-entry that is NOT currently active, and call `menus.select_model(tab, sel, "<that exact sub-label>")`. Record the result: does it return `verified=True` with a sustained reflected label, or raise `MODEL_SELECTION_NOT_REFLECTED` (fails-closed)? ALSO try `menus.select_model(tab, sel, "GPT-5.5")` (the family label) and record what happens. This determines whether `select_model` already supports live family selection or needs a W3 fix.
4. If any selection succeeded, **restore** the original model: `menus.select_model(tab, sel, "<original label>")` and confirm reflected. Leave the model as you found it. NO send.

### C. Deep Research tool selection (NO send; NEVER run DR)
The tools menu (trigger `sel["tools_button"]` = `button[data-testid="composer-plus-btn"]`) has `Deep research` + `Web search` (M2). `set_tools(["Web search"])` was real-verified in M7b; DR is expected to work the same.
1. `menus.open_radix_menu(tab, sel["tools_button"])`, enumerate, confirm a `Deep research` option is present (label + role). Close.
2. **Test the production path**: `menus.set_tools(tab, sel, ["Deep research"])`. Record whether it returns `verified=True` and `reflected == "Deep research"` (it re-opens the menu and reads `aria-checked`). **NEVER run Deep Research; NEVER send; never click any "start/run" affordance — only toggle the tool selection.**
3. **DESELECT** to restore: open the tools menu and click `Deep research` again to toggle it OFF, then confirm via re-open that its `aria-checked` is false (or the chip is gone). Leave tools cleared. NO send.

### D. Teardown
`ch.detach()` (NEVER quit). Then `curl -s --max-time 5 http://127.0.0.1:9222/json/version` and confirm the browser is still alive (record the Browser string, e.g. `Chrome/149...`).

## Acceptance
- ZERO sends (no conversation created; verify you never called submit/send/Enter-to-submit). Own-tab-only (no page enumeration). Browser still alive post-detach.
- Concrete, ground-truth answers for A/B/C: the real `file_input` + `attachment_chip` selectors; the exact live model top-level + GPT-5.5 sub-entry labels and whether `select_model` selects a family sub-entry (verified or fails-closed + which error); whether `set_tools(["Deep research"])` reflects + deselects.
- All findings re-derived from what the driver actually printed (capture stdout to `team/evidence/reports/M9-W2-discover.txt`), not from memory. **Scrub** any accidental auth/content before writing.

## Handoff (write this, then stop)
Write `team/evidence/handoffs/M9-W2-discovery.md`:
1. **Status:** `DONE` / `PARTIAL` / `BLOCKED` (or `HUMAN-ACTION-NEEDED` / `CDP_UNREACHABLE`) — single token, top.
2. **A — upload affordance:** confirmed `file_input` selector (and correction if any); the **real** `attachment_chip` selector (with evidence the chip appeared on staging); whether W1's hypotheses were correct.
3. **B — GPT-5.5 family:** the live top-level options + current label; the GPT-5.5 sub-entry labels (exact); the empirical verdict on `select_model` for a family sub-entry (verified OR fails-closed + the error code) and for the `"GPT-5.5"` label; your recommendation on whether W3 must implement a family-submenu fix and, if so, the exact label-shape it must support.
4. **C — Deep Research:** present? `set_tools(["Deep research"])` verified+reflected? deselected cleanly? any code gap?
5. **Send count: 0** (state it explicitly) and confirmation you touched only your own fresh tab and never `6a316aa8`/foreign tabs; browser alive post-detach.
6. **Artifacts** (+trust): `scripts/m9_w2_discover.py`, `team/evidence/reports/M9-W2-discover.txt`. **Blockers** (exact action). **Recommended next.**
Keep it credential-free and conversation-content-free. Report only what the driver actually produced.
