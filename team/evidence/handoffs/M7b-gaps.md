# M7b handoff — Close the 2 M7 real-site gaps (model/tool selector rediscovery + fresh-chat capture-auth)

Status: **DONE** — both deferred gaps closed and independently verified (offline falsifiable + live real-leg + independent best-of-N audit). Mission used **1 real send** (cap ≤4), all safety invariants held.

Manager: detached Claude Opus, M7b. Branch `rewrite-v2`. Commits: `1ea867a`, `90281f3`, `cc14d91` (on top of M7 `724a308`). `stable` = `779eb40b196e1a458a820248b2dbbca22411b0d3` (unmoved). Offline acceptance: `uv run pytest` = **254 passed** (baseline was 247).

## Gap-1 — live model/tool composer selection — CLOSED
Two distinct live defects, both fixed and real-verified:
1. **Model trigger selector was stale.** Old `composer-footer button[aria-haspopup="menu"]` matched 0 live elements (no more `composer-footer` ancestor). New live selector (T1 DOM-verified, matches exactly 1): `form button[aria-haspopup="menu"]:not([data-testid])` — the model "pill", whose own text is the current-model readout (so no new selector key needed). `tools_button` = `button[data-testid="composer-plus-btn"]` was already correct.
2. **Radix menus do not open on a bare `el.click()` (they open on pointerdown).** This — not the selector — is why the M7-T3 *tools* menu (correct selector!) timed out. Fix: menu-open now dispatches a real pointer sequence (pointerdown→mousedown→pointerup→mouseup→click) via a dedicated `ask_chatgpt_open_radix_trigger` evaluate key (`cdp.JS_OPEN_RADIX_TRIGGER`; `menus.open_radix_menu` routes through it, fail-closed). The send/submit `click` path is untouched. Menu-item select is pointer-activated too.
3. **Tools reflection: the live Radix tools menu CLOSES on tool-select**, so the old `_reflected_tool` (immediate portal re-enumerate) saw an empty portal. Fix (T3b live-validated): `menus.set_tools` re-opens the tools menu after select and reads `aria-checked` (re-opening does NOT toggle the tool), then closes the menu; the tool stays ON. Model selection was unaffected because it reads the persistent composer pill.

Real-verify (`team/evidence/reports/M7b-T3-verify.md`, `M7b-T3c-tools-verify.md`, 0 sends): model `Pro Extended → High` `verified=True` with an independent **12.003s sustained** read, then restored to `Pro Extended`; tools `set_tools(["Web search"])` `verified=True`, `reflected="Web search"`, restored.

## Gap-2 — fresh-chat capture-auth (`BACKEND_AUTH_UNAVAILABLE`) — CLOSED
Root cause: `capture` harvests the web-app auth/OAI headers from the page's own `GET /backend-api/conversation/<id>`. A fresh, client-navigated chat **never issues that GET** (the SPA already holds the conversation from the send/SSE), so `acquire_backend_headers` times out → fallback → `HUMAN-ACTION-NEEDED`. Fix: `session._run_send_turn` draft branch reloads `/c/<id>` after id-learn + completion and **before** `capture_conversation`, so the SPA issues the authenticated GET (the same mechanism M6 proved for existing conversations). Real-verify (`M7b-T3-verify.md`): a fresh throwaway `ask(None,"Reply with only the word: PONG")` captured end-to-end via `capture_source == "backend_api"` / `fidelity == "canonical"`, new assistant turn, `all_proven=true`.

## Verified evidence (re-derived from artifacts, not worker self-telemetry)
- **Offline suite** `uv run pytest` = 254 passed (manager re-ran authoritatively after every edit; final run clean, `src/` diff empty).
- **Falsifiability EMPIRICALLY proven** (manager + independent L2 auditor each reverted the fix and observed the guard fail):
  - gap-2 reload removed → `test_draft_ask_reloads_learned_chat_before_capture_when_backend_get_requires_reload` fails via `BACKEND_AUTH_UNAVAILABLE`→`HUMAN-ACTION-NEEDED` (reproduces the real bug).
  - gap-1 tools re-open removed → `test_set_tools_reopens_tools_menu_after_select_when_menu_closes` fails `TOOL_SELECTION_NOT_REFLECTED`.
  - gap-1 menu activation reverted to `click` → `test_open_radix_menu_uses_pointer_activation_evaluate_not_click` fails (click count 1≠0); selector revert fails the real.json lock; CDP pointer-token removal fails the cdp guards.
- **Manager-applied correction (transparent):** the editor's first gap-2 test was a **false-green** — the pre-send idle reload (`wait_for_idle_and_reload_if_needed`) set the mock's coarse `_reloaded` bit, opening the gate regardless of the fix. Manager re-modeled the mock faithfully: the GET unlocks only on a reload while the tab is on a `/c/<id>` URL (`_reloaded_on_conversation`), and `_current_url` updates the tab URL on observed client-nav. Re-proven falsifiable. Independent L2 audit confirmed this correction is sound (the pre-send root reload cannot satisfy the gate).
- **Exact send count: 1** (the T3 PONG smoke). T1, T3b, T3c = 0 sends. Mission total ≤ 4 (3 to spare). Fresh throwaway chat created: `/c/6a3591ae-d330-83ea-8a18-543701a8c33f`. Protected conversation `6a316aa8`: **not touched** (only ever a `!=` guard).
- **Leak/safety audit (independent L1, PASS):** 0 secret-value matches across the M7b diff + scripts/reports; no auth/OAI/cookie/session value or conversation content committed (PONG prompt only in driver source; the reply text never committed); `cache/` untracked; drivers own-tab-only (no `/json/list`, no page enumeration); `stable` unmoved; no `uv tool`; `controller.mjs`/`human/`/`cache/` not committed; redaction (`_scrub`) present in every driver.
- **Browser:** post-detach `/json/version` returned Chrome/149 after every real leg (never quit).

## Artifacts (trust)
- `src/ask_chatgpt/selectors/real.json`, `channels/cdp.py`, `channels/mock.py`, `menus.py`, `session.py` — **verified-independently** (offline 254 + live real-legs + L1/L2 audit).
- Falsifiable tests: `tests/test_selectors.py`, `test_menus.py`, `test_cdp_channel.py`, `test_session_draft_loop.py`, `test_capture.py` — **verified-independently** (proven to fail when each fix is reverted).
- Real-leg drivers: `scripts/m7b_t1_discover.py`, `m7b_t3_verify.py`, `m7b_t3b_tools.py`, `m7b_t3c_tools_verify.py` — producer + L1 safety-audited.
- Reports: `team/evidence/reports/M7b-T1-selectors.md`, `M7b-T2-editor.md`, `M7b-T3-verify.md`, `M7b-T3b-tools.md`, `M7b-T2b-tools-fix.md`, `M7b-T3c-tools-verify.md`, `M7b-T4-L1-leak-safety.md`, `M7b-T4-L2-correctness.md`.

## Blockers
- None. Both gaps closed.

## Recommended next (M8 — terminal verification + re-issue VERIFICATION.md)
- Both gaps are now closed; M8 (independent best-of-N verification + honest re-issue of `VERIFICATION.md` with a falsifiability + prompt-quality lens) is unblocked.
- Carry these **non-blocking** notes from the L2 audit into M8's lens:
  1. The offline gap-2 gate uses a substring `/c/` URL check (not a full path-parse) and primarily guards that a conversation-page reload precedes capture; the *source* proves the ordering relative to `wait_for_completion`, and the broken-code probe proves the test isn't passing on the pre-send reload — but M8 could add an explicit ordering assertion for extra rigor.
  2. Live coverage validated single model tier + single tool (Web search). M8/future work could exercise the GPT-5.5 **family submenu** path and additional tools (Deep research) on the live composer.
  3. Composer-chip `button[aria-label="Search, click to remove"]` exists as an alternative tool-reflection signal (fallback) if the re-open approach ever regresses.
- Real legs remain operator-attended CDP only; offline suite is the gate, real legs the live proof.

## Complexity / paradigm-shift signals
- No paradigm shift. The two gaps were narrow live-DOM/SPA-behavior mismatches the mock could not surface — confirming (again) the "real paths are mock-shaped" lesson: offline green proves logic, not live selectors/activation/SPA-timing. The fix pattern (discover live → fix → make the mock model the live behavior so the test is falsifiable → real-verify) held.
