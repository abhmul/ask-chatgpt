# M7 handoff — Model/tool selection + keep-pushing loop + tab-pool/rate + FIRST REAL SEND

**Status: PARTIAL** — Offline implementation is COMPLETE, mock-proven, independently verified, and hardened. Real legs PROVED the send mechanics (gotcha-4) on the live site but are BLOCKED on two real-site gaps (fresh-chat capture auth; live model/tool selectors) that are precisely characterized for M8. Mission used **2 of ≤4** real sends. `stable` unmoved; nothing pushed; no leak; no cache content committed.

## 1. What was verified (evidence)

### Offline core (DONE, independently verified by the manager + a 3-lens panel)
- `uv run pytest` = **247 passed in ~1.0s**, offline (manager-run; baseline was 212 at M7 start → +35 tests). Re-derived independently at each step, not trusted from worker self-report.
- **menus.py** executable label-driven Radix selection: open→enumerate→select (tier `menuitemradio` or family `menuitem`→radio)→**reflected-verify**; fail-closed (`ModelSelectionNotReflectedError`/`ToolSelectionNotReflectedError`) on absent/ambiguous/not-reflected; **never opens `Recent files`/`Projects`** (operator privacy, mock-proven via recorded `menu_clicks`). Commits `ad8f5fb`, `953da27`, `365d6fa`, `a5f26b4`.
- **Draft-conversation send**: `Session.ask(None,…)` opens a fresh chat, runs gotcha-4 (`verify_prompt_submitted` → new user turn else `PromptNotSubmittedError`), **learns the server `/c/<id>`** (now POLLED — see fix below), eager-writes, completes, captures. Shared private `_run_send_turn` used by ask/draft/loop (gotcha-4 + eager-write + salvage identical). Commits `9e6f1c1`, `d9437d7`.
- **Real `loop`** over a persistent `Session`: mock-only guard removed (mock+cdp), per-iteration gotcha-4, no hidden message cap, SIGINT salvage, CLI emits JSONL + returns 130. Commit `0f850e0`.
- **TabPool** (lazy-open, LRU evict, own-tabs-only) + **AdaptiveSendBudget** (politeness floor + AIMD + backoff + hard-pause, no hard cap) — committed in T1a (`9ee0897`, `a0d33b5`), exercised by the real legs.
- **Hardening from the verify panel** (commits `953da27`/`365d6fa`/`a5f26b4`/`511f47e`/`d9437d7`): sustained model-label read (`_sustained_model_labels` polls 6×2s via the channel clock — faithful to `controller.mjs confirmViolation`, tolerates the transient `Extra High`); settle-before-send-click (wait for visible+enabled send button); `aria-label="Send prompt"` selector fallback; **draft URL-poll** (poll `ask_chatgpt_current_url` until `/c/<id>` to tolerate SPA navigation latency). All offline waits use the channel clock — **no real `time.sleep`** added; suite stays <3s.

### Real legs (attended, own-tab-only, fresh throwaway chats) — what is REAL-PROVEN
- **CDP attach/detach over the shared browser is safe**: own-tab-only (no `/json/list`/page-walk), browser never quit (post-detach `/json/version` still served), target `6a316aa8` **never touched**, no auth/OAI/cookie values logged, no conversation content emitted.
- **The first real SENDS by the rewrite submitted successfully**: gotcha-4 passed on the live site in **both** real attempts (a new user turn carrying the prompt appeared after submit). The send mechanics (execCommand insertText + InputEvent fill, visible+enabled send-click) work against live chatgpt.com.
- **The draft URL-poll fix advanced the pipeline**: attempt 2 (T3c) reached the **capture** stage (which requires a learned `/c/<id>`), confirming id-learning now works on the real SPA.

## 2. Blockers (exact action required — these are the M8 work)
1. **Fresh-chat capture auth (`BACKEND_AUTH_UNAVAILABLE`) + clipboard fallback permission.** On a *freshly-created* chat, the in-page backend-api capture could not harvest the web-app auth/OAI headers (unlike M6's scrape of an *existing* conversation whose page had already issued authenticated requests), and the copy-button fallback fails closed on `clipboard_permission` ("clipboard fallback requires explicit permission"). **Action (M8):** investigate header-harvest timing on fresh/just-sent chats (hook the page's own backend request that streams the new turn), and/or grant clipboard read via CDP `Browser.grantPermissions` for the tool's own tab as a fallback. Evidence: `team/evidence/reports/M7-T3c.md:36`.
2. **Live model/tool selectors don't match the real composer.** `query_turns().model_labels` returned 0 (selector `composer-footer button[aria-haspopup="menu"]` matched nothing), and the tools menu (`button[data-testid="composer-plus-btn"]`) enumeration timed out. The offline menus.py impl is correct + mock-proven; only the **live selector map** needs rediscovery. **Action (M8):** read-only DOM probe of a fresh-chat composer (own tab, structural attributes only) → update `selectors/real.json` model-trigger + tools-button + portal selectors → re-validate (no-send). Evidence: `team/evidence/reports/M7-T3.md:24,28`.

## 3. Artifacts + trust
- Code (commits `9ee0897`→`3ac5575` on `rewrite-v2`): **verified-independently** (manager re-derivation + 3-lens offline panel T2 + T2b hardening).
- `team/evidence/reports/M7-T1b.md`, `M7-T2-L{1,2,3}.md`, `M7-T2b.md`, `M7-T3.md`, `M7-T3b.md`, `M7-T3c.md`: producer reports, key claims re-derived by the manager.
- `team/evidence/reports/M7-T4-audit.md`: independent audit; verdict `FAIL` is an **over-broad-scope false positive** (flagged pre-existing M0 archive + M6 target artifacts, not M7) — see the appended **MANAGER RECONCILIATION**; **M7-scope verdict = PASS** (corroborated by the manager audit: cache untracked, 2 sends, own-tab, stable unmoved, no push/uv-tool).
- `scripts/m7_t3_real.py`, `scripts/m7_t3c_real.py`: real-leg drivers; leak-clean (scrub-list + sentinel prompts only; both attempts failed at/before capture so **no assistant content was ever captured**, nothing to leak). Reusable for M8.
- Real send count: **2** (T3 leg2 = 1, T3c legA = 1; loops never reached, no retries). `cache/m7-t3*-real/` holds whatever eager-written user-turn data exists — **gitignored, never committed**.

## 4. Recommended next (M8)
- **M8-A:** fix fresh-chat capture auth + clipboard fallback (blocker 1), then re-validate the PONG smoke end-to-end and the 2-iteration loop (budget: ≤2 mission-respecting sends remain conceptually, but M8 sets its own attended budget). This completes the headline "first real send + loop, captured."
- **M8-B:** rediscover live model/tool selectors (blocker 2) and re-validate selection (no-send).
- Both are attended CDP legs; reuse `scripts/m7_t3c_real.py`. Deferred from spec (not regressions): marker-vs-exact-prompt submit verification (fine for short prompts), fuller 60s reload hydration, `TabPool` time-based idle-TTL (currently LRU-only — T1a drift, non-blocking).

## 5. Complexity / paradigm signals
- **Real-vs-mock shape gaps recurred** (the [[real-paths-are-mock-shaped]] pattern): three single-read-vs-poll/real-DOM gaps surfaced only on the live site (model-label transient, draft URL latency, fresh-chat capture auth) despite a green mock suite. Two were fixed (sustained read, URL poll); the third (capture auth) is M8. Lesson reinforced: each new real entrypoint must be probed live, not assumed from the mock.
- No paradigm shift needed; the architecture (library-core + Session + channel seam) held. The capture asymmetry (actions via UI, reads via backend-api with fail-closed fallback) is sound but its **auth-header harvest must be made fresh-chat-aware**.
- **Escalation to team lead (non-M7):** pre-existing `archive/orchestration-v1/reports/M-008b/*.txt` contain old real-response content committed to git; operator/team-lead to decide on scrubbing (charter marks `archive/` read-only, so M7 did not touch it).
