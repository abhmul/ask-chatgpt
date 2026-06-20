# M9 · W6 — Real-leg RE-VERIFY: upload smoke end-to-end (≤2 sends) + DR live + family retry

You are a **pi worker** running an **ATTENDED real-site CDP leg** for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. This leg confirms the W5 offline fixes against the live site. **TOTAL real sends ≤ 2** (the upload smoke; 0 consumed so far this mission).

## SAFETY — READ AND OBEY VERBATIM (shared browser; another active agent is using it)
- Browser **`http://127.0.0.1:9222`** is **SHARED with another ACTIVE agent** on target **`6a316aa8`** (`6a316aa8-5dc8-83ea-9014-b8ea38dabc31`).
- **OWN-TAB-ONLY** via production `Session`/`TabPool`. **NEVER** read/iterate/enumerate/touch any foreign/pre-existing tab **or** `6a316aa8`. No `context.pages`, no `/json/list`, no page enumeration. If any draft/ask resolves to `6a316aa8` → **STOP BLOCKED** (no send/retry).
- **FRESH throwaway chats ONLY**, a separate fresh draft per sub-leg. **TOTAL sends ≤ 2** (upload smoke only). Menu/DR/family legs = **ZERO sends**.
- **Preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` first; fail → **STOP `CDP_UNREACHABLE`**.
- **Login wall / Cloudflare / challenge** → **STOP `HUMAN-ACTION-NEEDED`**, detach, stop. No login attempts. **No stealth.**
- **Never quit the browser** — `session.detach()` only; post-detach `curl … /json/version` to confirm alive.
- **NEVER persist/log** any `authorization`/`oai-*`/`cookie`/`session`/`bearer` value or conversation content. Reuse the `_scrub` redaction from `scripts/m9_w4_smoke.py` / `scripts/m7b_t3_verify.py`. Content goes only to the gitignored `cache/` Store data-dir.
- **NEVER run Deep Research; NEVER send while a tool/DR is armed.** Clear DR before anything else; the upload-smoke draft must have NO tool armed.
- Branch `rewrite-v2` only; never move/commit `stable`; never `uv tool …`; never `git push`; never stage `cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`.

## WORKER PYTHON GOTCHA
Bare `python`/`python3` → shared agent-python venv WITHOUT playwright/ask_chatgpt. Use **`uv run python scripts/m9_w6_reverify.py`**.

## What W5 fixed (re-derive from `team/evidence/handoffs/M9-W5-send-enable-dr-chip.md`)
- **Upload send-enable:** with attachments, the send path now waits up to **60s** for the send button to enable (the attachment uploads async; send stays disabled until done). So `ask(attach=[...])` should now **complete the send**.
- **DR reflection:** `set_tools` now treats a **composer tool-chip** (`active_tool_chip = button[aria-label*="click to remove" i]`) as authoritative reflection (menu `aria-checked` was unreliable for DR). So `set_tools(["Deep research"])` should now return **verified**.

## Template
Adapt **`scripts/m9_w4_smoke.py`** (your team's prior leg) — it already has preflight, `_scrub`, the `6a316aa8` STOP-guard, `Session(channel="cdp")`, send-budget accounting, own-tab-only confirmations, detach + post-detach check. Set **send cap = 2**. Write `scripts/m9_w6_reverify.py`; data-dir `cache/m9-w6-reverify`. Order: **(C) DR → (B) family → (A) upload smoke** (no-send legs first; the one send last).

### C. Deep Research live re-verify (NO send; NEVER run DR)
On a fresh draft tab (not `6a316aa8`):
1. `from ask_chatgpt.menus import set_tools` → `set_tools(tab, session.selector_map, ["Deep research"])`. Record the `SelectionResult` — **expect `verified=True`** now (reflected via the composer chip `button[aria-label*="Deep research" i]`). Record reflected value.
2. Confirm via own-tab DOM read that the DR composer chip is present (the `active_tool_chip` signal).
3. **Clear DR** (toggle off / reload tab); confirm cleared. **NO send.** Assert 0 sends this leg. Release tab.
4. If `set_tools` still fails closed, record the typed error honestly (the W5 chip fix didn't hold live) — do NOT retry-spam.

### B. GPT-5.5 family retry (NO send; best-effort)
On a fresh draft tab (not `6a316aa8`):
1. Read current model label (sustained ~12s). `from ask_chatgpt.menus import select_model` → `select_model(tab, session.selector_map, "GPT-5.4")`. Record result.
2. If verified: independent ~12s sustained confirm reflected `GPT-5.4`, then **restore** to the original label. If it fails closed (e.g. `TimeoutError` as in W4): record the typed error honestly — this confirms the **documented live limitation** (family submenu selection times out live). **Do NOT retry-spam**; one attempt is enough. Assert 0 sends this leg. Release tab.

### A. Upload SMOKE end-to-end (the send — ≤2 total)
On a fresh, pristine draft (no tool armed; not `6a316aa8`):
1. `Path("/tmp/m9-upload.txt").write_text("m9 upload smoke canary\n")`.
2. `before = session.send_budget.successful_submissions`; run **production**: `rec = session.ask(None, "Reply with only the word: PONG", attach=[Path("/tmp/m9-upload.txt")], timeout=180)` (timeout generous to allow the ~60s send-enable + generation). Do NOT pass model/tools.
3. `after = ...`; assert `after - before == 1`, `after <= 2`. At most ONE retry on a transient error; never exceed 2.
4. **Verify the upload happened end-to-end** (re-derive from ground truth):
   - No `AttachmentUploadError`; the send **completed** (a new user turn was created).
   - Inspect the captured Store (`session.history(rec.conversation_id)` and/or `raw-mapping.json` under the data-dir): does the **user** turn carry attachment metadata (M2: `message.metadata.attachments[]` with `name`/`size`)? Report **booleans + counts + size match** vs `/tmp/m9-upload.txt` (`user_turn_has_attachment`, `attachment_count`, `name_matches_m9_upload`, `size_matches`). **Redact** any file-id; no file content.
   - Assistant captured: `rec.role=="assistant"`, `rec.status=="complete"`, `capture_source`, `content_nonempty` (boolean only).
   - If backend doesn't surface the user-turn attachment but the send completed, report that honestly (send+capture proven; attachment-metadata-in-backend not surfaced).
5. Record the created conversation id+url (NOT `6a316aa8`).

### Teardown
`session.detach()` (NEVER quit). Post-detach `curl … /json/version`; record Browser string. Final `send_budget.successful_submissions` ≤ 2.

## Acceptance
- **Upload end-to-end proven**: `ask(attach=...)` SENT and captured; ideally the user turn shows the attachment (name+size). This closes the M8 upload stub at the real level.
- **DR**: `set_tools(["Deep research"])` verified live via the chip (or honest fail-closed record).
- **Family**: GPT-5.4 verified+restored, OR the honest documented `TimeoutError` limitation.
- **Sends ≤ 2**, fresh throwaway, ZERO to `6a316aa8`/foreign; own-tab-only; browser alive post-detach; no leak.
- Numbers re-derived from the scrubbed driver output → `team/evidence/reports/M9-W6-reverify.txt`.

## Handoff (write, then stop)
Write `team/evidence/handoffs/M9-W6-reverify.md`:
1. **Status** (single token, top).
2. **A — upload end-to-end:** exact send count (leg+total), created conv id+url, send completed (bool), user-turn attachment evidence (booleans/counts/size) OR honest send-only fallback, assistant captured booleans.
3. **B — family:** verified+restored, or the typed `TimeoutError`/fail-closed (documented limitation).
4. **C — DR:** `set_tools(["Deep research"])` verified via chip? reflected value? cleared? honest verdict.
5. **Safety:** total sends (≤2), fresh chats only, `6a316aa8`/foreign untouched, own-tab-only, browser alive post-detach, no leak.
6. **Artifacts**(+trust); **Blockers**; **Recommended next**.
Credential-free, content-free; report only what the driver produced.
