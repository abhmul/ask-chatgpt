# M7b-T3 — Real-leg combined verify: gap-1 model/tool selection (NO send) + gap-2 fresh-chat send→capture (≤3 sends)

You are a **pi real-leg worker** for team `ask-chatgpt-dev`, task **M7b-T3**. You inherit **nothing** but this file. Read it in full and execute exactly. Repo: `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. The offline fixes for both gaps are already committed (HEAD `1ea867a`); your job is to **verify them on the live site** and **honestly report** whether each gap is truly closed.

## What you are verifying
- **Gap-1 (NO send):** with the updated `src/ask_chatgpt/selectors/real.json` (`model_picker_trigger_candidates` = `form button[aria-haspopup="menu"]:not([data-testid])`) and the new Radix **pointer-activation** menu-open path, the production model picker AND tools menu now actually open and selection **reflects** on the live composer, with a **sustained (~12s) read** and fail-closed behavior. Opening menus + selecting a model/tool creates **no conversation turn → ZERO sends for this leg.**
- **Gap-2 (≤3 sends, fresh throwaway chats):** a fresh-chat send now captures end-to-end. The fix reloads `/c/<id>` after the id is learned + the turn completes, so the SPA issues the authenticated `GET /backend-api/conversation/<id>` and headers are harvested (the M7-T3c `BACKEND_AUTH_UNAVAILABLE` is resolved). Verify capture succeeds via `capture_source == "backend_api"` / `fidelity == "canonical"`.

## SAFETY — read and obey every line (the browser is SHARED with another ACTIVE agent)
- CDP browser `http://127.0.0.1:9222` is **SHARED** with another active agent keep-pushing on conversation **`6a316aa8`**. 
- **OWN-TAB-ONLY.** Operate only on tabs YOU open via `Session`/`CdpChannel`. **NEVER** call `/json/list`, **never** enumerate `browser.contexts`/`context.pages`, **never** read/click/navigate any tab you did not open, **never** touch conversation `6a316aa8` or any foreign tab. If any `ask(None,...)` ever resolves to conversation id `6a316aa8`, STOP immediately (`TARGET_CONVERSATION_MATCH`).
- **FRESH throwaway chats ONLY** for sends. Use `session.ask(None, ...)` (a brand-new draft). Never send into an existing/foreign conversation.
- **TOTAL real sends ≤ 3**, all to fresh throwaway chats; **ZERO** to the target/foreign. Gap-1 leg = **0 sends**. Gap-2 = 1 PONG smoke (required) + at most 2 loop iters (optional, only if PONG fully proved). Track `session.send_budget.successful_submissions` and STOP if it would exceed 3.
- **Never quit the browser.** `Session.detach()` only (closes only your managed tabs). Confirm with a post-detach `/json/version` curl.
- **Preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` before attaching. Fail → `BLOCKED/CDP_UNREACHABLE`, no attach.
- **Login / Cloudflare challenge** (no composer, "Just a moment...", login wall) → STOP, `BLOCKED/HUMAN-ACTION-NEEDED`, no retries, no stealth/anti-detection ever.
- **NEVER persist or log** any authorization/bearer token, `oai-*` header, cookie, or session value — not to stdout, not to any file. Do NOT print conversation content. Conversation text goes ONLY into the gitignored `--data-dir` Store. Model/tool **feature labels** ("High", "Pro Extended", "Web search", "Deep research") are product names and are safe.
- **Redirect** any stdout that could carry payload to `/dev/null`; emit only safe metadata (ids, roles, counts, capture_source/fidelity, verified booleans). Reuse the `_scrub()` redaction from `scripts/m7_t3c_real.py`.
- **model-label SUSTAINED read:** never conclude a model mismatch from a single read; require a sustained read (~12s; the production `select_model` already does 6×2s — additionally do your own ~12s confirmation poll).
- **Human-paced:** rely on the built-in `AdaptiveSendBudget` politeness/backoff; do not loosen it beyond what the smoke needs; no programmatic spamming.
- Repo isolation: branch **`rewrite-v2`** only. **NEVER** move/commit **`stable`**; **NEVER** `uv tool install/upgrade/reinstall`; **NEVER** `git push`; **do NOT `git commit`** (the manager commits). Never stage `cache/`, `issues/cdp-send-repro/controller.mjs`, or `human/`.

## Read first
- `scripts/m7_t3c_real.py` — **reuse its scaffolding**: `_scrub`, `git_checks`, `preflight_version`, `turn_meta`, `transcript_meta`, target-id guard (`TARGET_CONVERSATION_ID="6a316aa8"`), send-budget tracking, detach-only teardown, safe `emit`.
- `src/ask_chatgpt/menus.py` (`select_model`, `set_tools`, `assert_reflected_model`, `assert_reflected_tools` — these open the menu via the new pointer-activation path, select by label, and verify reflection with a sustained read; they fail closed with `ModelSelectionNotReflectedError`/`ToolSelectionNotReflectedError`).
- `src/ask_chatgpt/session.py` (`Session.create`, `Session.ask`, `TabPool.acquire/release`, the draft-branch reload-before-capture).
- `team/evidence/reports/M7b-T1-selectors.md` (the live menu shape: tiers Instant/Medium/High/Extra High/Pro Extended are direct `menuitemradio`; GPT-5.5 is a family submenu; tools Web search/Deep research/Create image are direct).

## Procedure — write `scripts/m7b_t3_verify.py`, run `uv run python scripts/m7b_t3_verify.py`
1. **Preflight** + branch/stable checks (abort cleanly on failure). `DATA_DIR = Path("cache/m7b-t3-verify")`.
2. `session = Session(channel="cdp", data_dir=DATA_DIR); session.attach()`.
3. **Leg 1 — gap-1 model + tool selection, ZERO sends:**
   - `draft = session.create()`; `tab = session.tab_pool.acquire(draft)` (opens YOUR fresh new-chat tab). Wait for `#prompt-textarea`. If absent/challenge → STOP `HUMAN-ACTION-NEEDED`.
   - Read the initial model label `L0` from `tab.channel.query_turns(tab, session.selector_map).model_labels` (sustained: poll a few times). 
   - Pick a target tier `T` from `["High","Medium","Extra High","Instant"]` with `T != L0` (direct `menuitemradio` tiers; avoid the GPT-5.5 family submenu).
   - `from ask_chatgpt.menus import select_model, set_tools` → `mres = select_model(tab, session.selector_map, T)`. Record `mres.verified`, `mres.reflected`. Then do your OWN **~12s sustained confirmation**: poll `query_turns(...).model_labels` for ≥12s and confirm it stays `== T` (record sustained_ok bool).
   - `tres = set_tools(tab, session.selector_map, ["Web search"])` → record `tres[0].verified`, `tres[0].reflected`.
   - **Restore** the original model: `select_model(tab, session.selector_map, L0)` (leave the UI's model default as you found it). If restore fails, record it as a signal (non-fatal) but do not retry-spam.
   - Wrap each selection in try/except and record the typed error code on failure (fail-closed is the correct behavior to verify; a fail-closed error with a wrong selector would mean gap-1 is NOT closed). `session.send_budget.successful_submissions` MUST still be 0 after this leg — assert it.
   - `session.tab_pool.release(tab)`.
4. **Leg 2 — gap-2 fresh-chat PONG smoke (1 send):**
   - `rec = session.ask(None, "Reply with only the word: PONG", timeout=90)`.
   - Guard: if `rec.conversation_id == "6a316aa8"` → STOP `TARGET_CONVERSATION_MATCH`.
   - Record `turn_meta(rec)`: role, message_id, status, partial, char_count, **capture_source**, **fidelity**, conversation_id, conversation_url.
   - `hist = session.history(rec.conversation_id)`; compute checks like m7_t3c: role==assistant, conversation_id present + not target, `/c/<id>` in url, status==complete, partial False, content non-empty, user PONG prompt present, assistant turn present by id, transcript has ≥1 user + ≥1 assistant, **capture_source == "backend_api"**, **fidelity == "canonical"**. `all_proven` = all true.
   - The KEY gap-2 verdict: `capture_source == "backend_api"` (NOT a clipboard/dom fallback) → the reload→GET→header-harvest path worked. If it fell back, gap-2 is NOT resolved — record the exact path/error.
   - Record the created throwaway `/c/<id>`.
5. **Leg 3 — OPTIONAL 2-iter loop (≤2 sends), only if Leg 2 `all_proven`:** `session.loop(rec.conversation_url, message="continue", max_iterations=2, timeout=90)`; verify 2 distinct assistant ids (distinct from Leg 2), transcript grew, no clipping, all `backend_api`. Skip if Leg 2 failed or to stay frugal; record SKIPPED + reason. Keep total sends ≤ 3.
6. **Detach** (`session.detach()`); post-detach `/json/version` curl confirms browser still up.
7. Write the report.

## Output (both required)
1. **Driver**: `scripts/m7b_t3_verify.py` (safe-emit, own-tab-only, ≤3 sends).
2. **Report**: `team/evidence/reports/M7b-T3-verify.md`, in this order:
   - `Status:` (`DONE` if gap-1 model+tool verified AND gap-2 PONG `all_proven` with `backend_api` capture; `PARTIAL` if one closed; `BLOCKED` for preflight/challenge).
   - CDP preflight (browser version, ws present).
   - **Exact send count** this run (`send_budget.successful_submissions`) + per-leg; confirm `≤ 3` and Leg-1 == 0.
   - **NEW throwaway conversations created** (`/c/<id>`); confirm `6a316aa8` NOT touched.
   - **Gap-1 results:** initial L0, target T, `select_model` verified + reflected, your independent ~12s sustained_ok, `set_tools` verified + reflected, restore outcome; the old-vs-new selector note; fail-closed behavior observed. Verdict: gap-1 CLOSED / NOT.
   - **Gap-2 results:** PONG assistant meta (role/id/status/partial/char_count/**capture_source**/**fidelity**), the checks + `all_proven`, and explicitly whether `capture_source == "backend_api"` (the reload-fix worked) or it fell back (with the exact error/source). Verdict: gap-2 CLOSED / NOT. If NOT, give the exact failure (e.g., backend GET still not observed post-reload, or headers missing) as an M8 blocker.
   - Loop leg (if run) or SKIPPED + reason.
   - **Confirmations** (copy m7_t3c's): own-tab-only (no `/json/list`, no page enumeration); browser not quit (post-detach version ok); no auth/oai/cookie value logged; no conversation content printed/reported; `cache/` not staged; `controller.mjs`/`human/` unstaged; `stable` rev unchanged start/end; branch `rewrite-v2`.
   - **Blockers** (exact action) + **Signals**.

## Acceptance
- Gap-1 model + tool selection **real-verified** on the live composer (sustained read, fail-closed, original model restored). Gap-2 **fresh-chat send→capture verified** with `capture_source == "backend_api"`. ≤3 real sends, all fresh throwaway, ZERO to target/foreign. Own-tab-only, browser still up, no leak, `stable` unmoved, nothing committed/staged (the manager commits).
- **Report honestly.** A fail-closed result that reveals a still-open gap is a valid, valuable outcome — document the exact blocker for M8. Never fabricate a "verified" you did not observe. The report file is your deliverable; ensure it is written before you finish.
