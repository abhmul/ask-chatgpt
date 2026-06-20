# M9 change map (manager's CLAIMED changes — VERIFY each against ground truth; do NOT trust this file)

> This is a navigation map for the M9 verify panel. Every claim here is the manager's assertion; **re-derive each from the actual code/tests/diff** (`git diff main -- src/ tests/`, read the files). Where this map and the code disagree, the code wins — and flag the discrepancy.

## Mission
Finalize the v2 rewrite for merge-readiness per M8 `VERIFICATION.md`: (1) wire outgoing upload (kill the `send.py` silent-no-op stub) + real-verify; (2) verify GPT-5.5 family submenu selection live (no send); (3) verify Deep Research tool selection live (no send).

## Claimed code changes (verify in `src/`)
1. **Upload wire** — `send.py:upload_attachments` now calls `tab.channel.upload_files(tab, selectors["file_input"], paths)` then `_wait_for_attachment_chip` (selectors `attachment_chip`); raises `AttachmentUploadError` (new, `errors.py`) if no chip appears (fail-closed; no silent no-op). `CdpChannel.upload_files`/`MockChannel.upload_files` pre-existed.
2. **Selectors** — `file_input="form input[type=\"file\"]"`, `attachment_chip="button[aria-label*=\"Remove file\" i]"`, `active_tool_chip="button[aria-label*=\"click to remove\" i]"` added to ALL of `REQUIRED_SELECTOR_KEYS` (`selectors/__init__.py`), `SelectorMap` TypedDict (`models.py`), `selectors/real.json` (else the strict loader drops them).
3. **Send-enable-after-attach** — `submit_composer(settle_timeout_s=...)`; `send_prompt` + `Session._run_send_turn` pass `_SEND_BUTTON_ATTACHMENT_SETTLE_TIMEOUT_S` (60s) only when attachments present (live: the attachment uploads async, send button enables late).
4. **Verify tolerates attachment turns** — `verify_prompt_submitted(has_attachments=...)`: substring-contains match when attachments present, exact-equality otherwise (the no-attachment gotcha-#2 guard is unchanged). Callers in `send_prompt` + `session._run_send_turn` pass `has_attachments=bool(attach)`.
5. **GPT-5.5 family** — `menus.py:_select_model_from_family_submenus` (general, label-driven; opens non-forbidden top-level `menuitem` families, never `Recent files`/`Projects`; fail-closed); `cdp.py` `JS_MENU_ENUMERATE`/`JS_MENU_CLICK_LABEL` enumerate/click across ALL open Radix portals (deepest-portal preference). Offline-falsifiable.
6. **Deep Research reflection** — `menus.py:set_tools` reflects a tool via the composer `active_tool_chip` pill OR the menu re-open `aria-checked` (fail-closed if neither).

## Claimed test state
- `uv run pytest` → **267 passed** (M8 baseline was 254). New/changed falsifiable tests: upload-happens-in-production-path, fail-closed-no-chip-raises-AttachmentUploadError, send-enable-waits-past-2s-for-attachments, set_tools-verifies-via-chip + fail-closed-no-signal, select_model-finds-differently-named-GPT-5.4, verify-substring-for-attachment-turns. Selector fixtures updated across test files for the 3 new required keys.

## Claimed live results (attended CDP, `team/evidence/handoffs/M9-W2/W4/W6` + reports)
- **Upload — LIVE staging proven** (W4: `set_input_files` on `form input[type=file]` → chip `button[aria-label*="Remove file" i]` appears, no AttachmentUploadError). **LIVE send proven** (W6: with the 60s settle, `ask(attach=...)` created REAL new user turns — `baseline_user_count 0 → last_seen_user_count 1`, real msg-ids). The library then raised `PromptNotSubmittedError` because verify was exact-match → **fixed in change #4**; final library CAPTURE of the attachment turn is **NOT re-verified live** (real-send budget spent). 
- **TRUE real send count = 2** (W6's two created user turns) — NOTE `send_budget.successful_submissions` shows **0** because verify raised post-submit; the honest count is **2** (at the ≤2 cap). W2/W4 = 0 sends.
- **DR — LIVE VERIFIED** (W6: `set_tools(["Deep research"])` → `verified=True`, reflected via chip `button[aria-label*="Deep research" i]`; cleared).
- **Family — LIVE FAILS-CLOSED** (W4 `TimeoutError`; W6 `MODEL_SELECTION_NOT_REFLECTED` "selected but not reflected") → honest documented limitation (offline code is general+fail-closed; live Radix-submenu timing/reflection unresolved).
- **Safety:** own-tab-only (no `/json/list`/page enumeration in drivers), fresh throwaway chats only, target `6a316aa8`/foreign untouched, browser never quit (detach only; alive post-detach), `_scrub` redaction in drivers, no auth/OAI/cookie/content logged, `stable` unmoved (`779eb40…`), nothing pushed, no `uv tool`, `cache/`/`controller.mjs`/`human/` unstaged.

## Files to read
- Code: `git diff main -- src/ tests/`; `src/ask_chatgpt/{send.py,session.py,menus.py,errors.py,models.py,selectors/__init__.py,selectors/real.json,channels/cdp.py,channels/mock.py}`.
- Evidence: `team/evidence/handoffs/M9-W{1..7}-*.md`; `team/evidence/reports/M9-W{2,4,6}-*.txt`, `M9-W{1,3,5,7}-pytest.txt`; drivers `scripts/m9_w{2,4,6}_*.py`.
