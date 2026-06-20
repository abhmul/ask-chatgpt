# M9 · W5 — Offline fixes from the W4 live leg: (1) send-enable-after-attach, (2) DR composer-chip reflection

You are a **pi worker** (single source editor) for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **OFFLINE — do NOT touch the browser/CDP/chatgpt.com.** A real-leg worker (W6) live-verifies your fixes afterward.

## Ground truth from the W4 live leg (re-derive by reading `team/evidence/handoffs/M9-W4-smoke.md`)
- **Upload STAGING works live**: `ask(attach=[file])` stages the file (`set_input_files` on `form input[type="file"]`), the attachment chip `button[aria-label*="Remove file" i]` appears, and **no `AttachmentUploadError`** is raised. ✅ The W1/W3 upload wire is correct up to staging.
- **BUG (the send fails):** after staging + typing the prompt, **the send button stays VISIBLE but DISABLED**; `submit_composer` timed out (its `_SEND_BUTTON_SETTLE_TIMEOUT_S = 2.0` enable-wait) and raised `SelectorNotFoundError` **twice**. Root cause: a freshly-attached file **uploads to the server asynchronously**; the send button only becomes **enabled once the upload completes** (a few seconds), which is **longer than the 2s enable-wait**. So with attachments, the send path gives up before the button enables.
- **DR reflection signal CONFIRMED:** selecting `Deep research` (a `menuitemradio`) **does** arm it — a **composer chip** appears: `button[aria-label="Deep research, click to remove"]` (stable: `button[aria-label*="Deep research" i]`). But the tools-menu **re-open `aria-checked` stays false**, so `_reflected_tool_by_reopen` (menu aria-checked) is **NOT authoritative** for DR → `set_tools(["Deep research"])` wrongly raised `TOOL_SELECTION_NOT_REFLECTED`. (For reference, M7b saw the Web-search chip as `button[aria-label="Search, click to remove"]`.) The **general** tool-pill signal is `button[aria-label*="click to remove" i]` (matches DR + Web-search chips; does NOT match the attachment `Remove file …` chip).

## WORKER PYTHON GOTCHA
Bare `python`/`python3` → shared agent-python venv WITHOUT playwright/ask_chatgpt. Use **`uv run`** for everything (`uv run pytest`).

## Fix 1 (PRIMARY) — wait for the send button to enable when attachments are present
Make the send path tolerate the async attachment-upload delay:
- In `src/ask_chatgpt/send.py`, add a longer bounded constant, e.g. `_SEND_BUTTON_ATTACHMENT_SETTLE_TIMEOUT_S = 60.0` (poll on the existing `_SEND_BUTTON_POLL_INTERVAL_S`).
- In `send_prompt` (the function that calls `upload_attachments` → `fill_composer` → `submit_composer`): when `attach` is non-empty, **after `fill_composer`** wait for the send button to become **visible+enabled** using the longer timeout **before** `submit_composer` (reuse `_wait_for_enabled_send_button` with the longer timeout, or thread the longer timeout into `submit_composer`). When there are no attachments, keep the existing 2s behavior. Keep it **fail-closed**: if the button never enables within the longer window, raise the existing `SelectorNotFoundError`/`PromptNotSubmittedError` (NOT a silent skip).
- Note the same call sequence is used from `session._run_send_turn` via `upload_attachments`/`fill_composer`/`submit_composer`; ensure the production path benefits (the simplest is to put the wait inside `send_prompt`, and/or have `_run_send_turn` pass the longer settle timeout when `attach` is non-empty — match whichever the code structure makes clean, but the **behavior** must be: attachments → tolerate a long send-enable delay).
- **Falsifiable test:** drive the production send path (e.g. extend the upload test in `tests/test_session_draft_loop.py`, or a `send_prompt` test in `tests/test_send_completion.py`) with a `MockScenario` whose **send button is disabled past 2s then becomes enabled** before 60s — model this with `MockScenario.selector_enabled_sequence={<send_button_selector>: (False, False, …, True)}` plus the `ScriptedClock` so the disabled window exceeds 2s. Assert the send **succeeds** with attachments. Then **revert** Fix 1 (use the 2s wait for attachments too) → the test must go **RED** (send fails because the button is still disabled at 2s). Paste the RED output in your handoff.

## Fix 2 (CONFIRMED, general) — reflect tool selection via the composer chip, not only menu aria-checked
- Add a new selector key `active_tool_chip` = **`button[aria-label*="click to remove" i]`** to **all three**: `REQUIRED_SELECTOR_KEYS` (`selectors/__init__.py`), the `SelectorMap` TypedDict (`models.py`), and `selectors/real.json`. (This is the general armed-tool pill; it is distinct from the attachment `Remove file …` chip.)
- In `src/ask_chatgpt/menus.py`, make `set_tools` treat the tool as reflected if **EITHER** the existing menu-reopen `aria-checked` path **OR** an armed-tool **composer chip** is present after selection. Concretely: after `select_radix_label(label)`, consider it reflected if `_reflected_tool_by_reopen(...)` returns the label **or** a composer tool-chip (`selectors["active_tool_chip"]`) is visible (`tab.channel.wait_for_selector(..., state="visible", timeout_s=<small>)` or a presence check). Keep it **fail-closed**: if neither signal is present, still raise `ToolSelectionNotReflectedError`. Preserve the existing Web-search behavior (its aria-checked path must keep passing).
- Keep the abstraction **general** (operator preference): do not special-case the literal string "Deep research" — use the general `active_tool_chip` pill signal so any tool that arms a removable composer chip reflects.
- **Falsifiable test (in `tests/test_menus.py`):** a DR-like scenario where the menu re-open shows the tool **unchecked** (`aria-checked=false`) but the composer tool-chip **is present** (`MockScenario.selector_presence={<active_tool_chip>: True}`, plus `menu_closes_on_select=True` as the live menu does) → `set_tools([...])` returns **verified**. Then **revert** the chip fallback → the test must go **RED** (`TOOL_SELECTION_NOT_REFLECTED`). Also add/keep a test that with **neither** signal present, `set_tools` **fails closed**. Paste the RED output.

## Do NOT change
- The W3 GPT-5.5 family code (`menus.py` `_select_model_from_family_submenus`, the `cdp.py` portal JS). Leave it as-is — its live timing is a documented limitation handled by the manager, NOT your scope. Do not touch `select_model`'s family branch.

## Acceptance (verify, don't assume)
- `uv run pytest` → all green. Capture tail to `team/evidence/reports/M9-W5-pytest.txt`.
- Both fixes demonstrated falsifiable (RED on revert; paste the `uv run pytest -k` output for each).
- New `active_tool_chip` key is projected by `load_selector_map("real")` (don't let the strict loader drop it — it's why it must be in `REQUIRED_SELECTOR_KEYS` + the TypedDict).
- No existing test weakened (Web-search reflection, upload-happens, fail-closed-no-chip, family tests all still pass).
- `git status --porcelain` shows ONLY your intended `src/`+`tests/` changes (+ your report). Do NOT commit. Do NOT touch `cache/`, `archive/`, `human/`, `issues/cdp-send-repro/controller.mjs`.

## Safety / isolation
OFFLINE only. Branch `rewrite-v2`. NEVER move/commit/checkout `stable`; NEVER `uv tool …`; NEVER `git push`; do not `git commit` (manager commits). No secrets/content anywhere.

## Handoff (write, then stop)
Write `team/evidence/handoffs/M9-W5-send-enable-dr-chip.md`:
1. **Status** (single token, top).
2. **What changed** — exact files + line ranges for Fix 1 (send-enable-after-attach) and Fix 2 (`active_tool_chip` + `set_tools` chip reflection).
3. **Falsifiability evidence** — the RED `uv run pytest -k` output for BOTH fixes on revert; green full-suite tail (count+exit) from `M9-W5-pytest.txt`.
4. **W6 live-verify notes** — exact things W6 must confirm live: (a) `ask(attach=[/tmp/m9-upload.txt])` now SENDS end-to-end (send button enables after upload, new user turn carries the attachment, assistant captured); (b) `set_tools(["Deep research"])` now returns verified via the composer chip.
5. **Selector values** now in real.json. **Artifacts**(+trust); **Blockers**; **Recommended next**.
Credential-free, factual, re-derived from the captured pytest output.
