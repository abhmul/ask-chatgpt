# M9 · W4 — Real-leg upload SMOKE (≤2 sends) + family re-verify (no send) + DR diagnostic (no send)

You are a **pi worker** running an **ATTENDED real-site CDP leg** for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. This leg performs the mission's **only sends**: the upload smoke. **TOTAL real sends ≤ 2** (1 expected, ≤1 spare). The family + DR legs are **ZERO-send**.

## SAFETY — READ AND OBEY VERBATIM (shared browser; another active agent is using it)
- Browser **`http://127.0.0.1:9222`** is **SHARED with another ACTIVE agent** working on target **`6a316aa8`** (full id `6a316aa8-5dc8-83ea-9014-b8ea38dabc31`).
- **OWN-TAB-ONLY** via the production `Session`/`TabPool` (it opens its own tabs). **NEVER** read/iterate/enumerate/touch any pre-existing/foreign tab **or** the target `6a316aa8`. Do **NOT** call `context.pages`, `/json/list`, or any page enumeration. Keep the `6a316aa8` guard: if any draft/ask resolves to that id → **STOP BLOCKED**, do not send/retry.
- **FRESH throwaway chats ONLY.** Use a **separate fresh draft per sub-leg**. **TOTAL sends ≤ 2** (the upload smoke; never more). Model/tool selection legs = **ZERO sends**.
- **Preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` BEFORE attaching; fail → **STOP `CDP_UNREACHABLE`**.
- **Login wall / Cloudflare / any challenge** → **STOP `HUMAN-ACTION-NEEDED`**, detach, do nothing else. No login attempts. **No stealth, ever.**
- **Never quit the browser** — `session.detach()` only; confirm browser still up with a post-detach `curl … /json/version`.
- **NEVER persist/log** any `authorization`/`oai-*`/`cookie`/`session`/`bearer` value or any conversation content. Use a `_scrub`/redaction helper (copy M7b's `SENSITIVE_KEY_PARTS`/`SENSITIVE_VALUE_PARTS` + `_scrub`). Conversation content goes ONLY into the gitignored `cache/` Store data-dir, never into stdout/reports.
- **NEVER run Deep Research; NEVER send while any tool/DR mode is armed.** Arming DR in the tools menu does NOT run it (running needs a send) — but you must **clear/deselect DR before doing anything else** and ensure the upload-smoke draft has **no** tool armed.
- Redirect any production-CLI stdout to `/dev/null` if you shell out (you'll mostly drive via the library; keep prints scrubbed). Branch `rewrite-v2` only; never move/commit `stable`; never `uv tool install/upgrade/reinstall`; never `git push`; never stage `cache/`, `issues/cdp-send-repro/controller.mjs`, or `human/`.

## WORKER PYTHON GOTCHA
Bare `python`/`python3` → shared agent-python venv WITHOUT playwright/ask_chatgpt. Use **`uv run python scripts/m9_w4_smoke.py`**.

## Template
**Model your driver on `scripts/m7b_t3_verify.py`** (the proven fresh-chat send+capture driver): reuse its `_scrub`, `emit`, `preflight_version`, `git_checks`, the `TARGET_CONVERSATION_ID="6a316aa8"` STOP-guard, `Session(channel="cdp", data_dir=DATA_DIR)`, `session.send_budget.successful_submissions` send accounting, own-tab-only confirmations, and the `finally: session.detach()` + post-detach version check. Set the **send cap = 2** for this run. Write `scripts/m9_w4_smoke.py`; data-dir e.g. `cache/m9-w4-smoke` (gitignored).

Order the legs **no-send first, send last**: (B) family re-verify → (C) DR diagnostic → (A) upload smoke.

### B. GPT-5.5 family re-verify (NO send) — confirms the W3 live fix
On a **fresh draft tab** (`session.create()` → `session.tab_pool.acquire(draft)`), confirm not `6a316aa8`:
1. Read the initial/current model label (sustained ~12s read like M7b's `read_initial_model_label`). Expect `Pro Extended`.
2. `from ask_chatgpt.menus import select_model` → `select_model(tab, session.selector_map, "GPT-5.4")`. Record the `SelectionResult` (verified? reflected?). Then run an **independent ~12s sustained** confirmation that the composer model label reads `GPT-5.4` (reuse M7b's `sustained_model_confirmation`).
3. **Restore**: `select_model(tab, session.selector_map, "<original label, e.g. Pro Extended>")`, confirm reflected. Leave the model as found.
4. Assert this leg added **0 sends**. Release the tab. (If `select_model("GPT-5.4")` fails-closed, record the typed error — that means the W3 JS portal fix didn't work live; report honestly, do NOT retry-spam.)

### C. Deep Research diagnostic (NO send; NEVER run DR) — capture the TRUE reflection signal
On a **fresh draft tab** (confirm not `6a316aa8`):
1. Open the tools menu (`from ask_chatgpt.menus import open_radix_menu, enumerate_radix_options, set_tools`; trigger `session.selector_map["tools_button"]`). Confirm `Deep research` present (label+role).
2. Try `set_tools(tab, session.selector_map, ["Deep research"])`; record verified/reflected or the typed `TOOL_SELECTION_NOT_REFLECTED` error (W2 saw it fail).
3. **Diagnose the real signal** (read-only, own tab): after attempting to select `Deep research`, introspect YOUR OWN composer DOM via `tab.channel.evaluate(tab, "<JS>")` to find any **composer chip/pill** indicating DR is armed — capture its tag, `aria-label`, `data-testid`, and a candidate **stable selector** (e.g. `button[aria-label*="Deep research" i]` or a `[data-testid]`). Also note whether the menu re-open shows the `Deep research` `menuitemradio` `aria-checked` true/false. Goal: determine the authoritative reflection signal for DR (composer chip vs menu aria-checked) and its exact selector — so DR can be cheaply wired or honestly documented.
4. **Clear DR**: deselect / toggle off (open menu, click `Deep research` again) or reload the tab so no tool is armed; confirm cleared. **NO send.** Assert 0 sends this leg. Release the tab.

### A. Upload SMOKE (the send — ≤2 total) — proves the wire end-to-end
On a **fresh, pristine draft** (no tool armed; confirm not `6a316aa8`):
1. Create the throwaway file: `Path("/tmp/m9-upload.txt").write_text("m9 upload smoke canary\n")` (small, self-created; not operator/private data).
2. `before = session.send_budget.successful_submissions`. Run the **production** path:
   `rec = session.ask(None, "Reply with only the word: PONG", attach=[Path("/tmp/m9-upload.txt")], timeout=120)`.
   (Do NOT pass model/tools — keep the smoke about upload only. The wire will `set_input_files` the file input, wait for the attachment chip, then submit; if the chip never appears it raises `AttachmentUploadError` — that is the fail-closed guard, report it if it happens.)
3. `after = ...`; assert `after - before == 1` and `after <= 2`. If a transient error occurs you may retry **at most once** (cap 2); never exceed 2.
4. **Verify the upload actually happened** (re-derive from ground truth, not assumption):
   - No `AttachmentUploadError` was raised (the composer chip appeared → file staged). Record this.
   - Inspect the captured conversation for the attachment on the **user** turn: read the gitignored Store (`session.history(rec.conversation_id)` and/or the `raw-mapping.json` under the data-dir) and check whether the user message carries attachment metadata (M2: user uploads live in `message.metadata.attachments[]` with `name`/`size`/`id`). Report **booleans + counts + a size match** against `/tmp/m9-upload.txt` (e.g. `user_turn_has_attachment: true`, `attachment_count: 1`, `name_matches_m9_upload: true`, `size_matches: true`). **Redact** any file-id; do NOT print file content.
   - Confirm the assistant response was captured (`rec.role=="assistant"`, `rec.status=="complete"`, `capture_source`, `content_nonempty` boolean only).
   - If the backend doesn't surface the user-turn attachment, fall back to the chip-appeared/no-error proof and say so honestly (still proves the upload affordance fired through production code).
5. Record the created conversation id + url; confirm it is NOT `6a316aa8`.

### Teardown
`session.detach()` (NEVER quit). Post-detach `curl … /json/version`; record Browser string. Record final `send_budget.successful_submissions` (must be ≤ 2).

## Acceptance
- **Upload proven**: `ask(attach=...)` ran through production, the chip appeared (no `AttachmentUploadError`), and ideally the backend user-turn shows the attachment (name+size match). Assistant captured.
- **Family**: `select_model("GPT-5.4")` verified + sustained ~12s + restored to original (or honest fail-closed record).
- **DR**: the true reflection signal captured (chip selector or aria-checked finding) + DR cleared; honest verdict on whether DR selection works.
- **Sends ≤ 2**, all fresh throwaway, ZERO to `6a316aa8`/foreign. Own-tab-only. Browser alive post-detach. No leak.
- All numbers re-derived from what the driver printed (scrubbed) → `team/evidence/reports/M9-W4-smoke.txt`.

## Handoff (write, then stop)
Write `team/evidence/handoffs/M9-W4-smoke.md`:
1. **Status** (single token: `DONE`/`PARTIAL`/`BLOCKED`/`HUMAN-ACTION-NEEDED`/`CDP_UNREACHABLE`), top.
2. **A — upload smoke:** exact send count (this leg + total), the created throwaway conversation id+url, no-`AttachmentUploadError` confirmation, the user-turn attachment evidence (booleans/counts/size match) OR the honest chip-only fallback, assistant-captured booleans.
3. **B — family:** `select_model("GPT-5.4")` verified+reflected+sustained? restored? (or the typed fail-closed error → JS portal fix didn't hold live).
4. **C — DR diagnostic:** present? `set_tools` verdict; the **exact** DR reflection signal + candidate selector; your recommendation (cheap wire vs honest "fails-closed/untested-live").
5. **Safety:** total send count (≤2), fresh chats only, `6a316aa8`/foreign untouched, own-tab-only (no `/json/list`), browser alive post-detach, no leak.
6. **Artifacts**(+trust): `scripts/m9_w4_smoke.py`, `team/evidence/reports/M9-W4-smoke.txt`. **Blockers**; **Recommended next**.
Credential-free, content-free; report only what the driver actually produced.
