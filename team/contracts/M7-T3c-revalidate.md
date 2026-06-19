# Contract M7-T3c — REAL re-validate the HEADLINE (draft PONG send + loop) after the URL-poll fix

You are a **pi REAL-LEG worker** for `ask-chatgpt-dev`, task **M7-T3c**. Repo `/home/abhmul/dev/ask-chatgpt` (cwd set), branch **`rewrite-v2`**. You inherit **nothing** but this contract and the files it names. **First read and obey** `.claude/skills/manager/references/agent-rigor.md`. This drives LIVE chatgpt.com over CDP to re-validate the first real send + loop after a fix.

## What changed since the last attempt
The draft post-submit conversation-id learning now **polls** the URL until `/c/<id>` appears (fix `M7-T3b`, commit on `rewrite-v2`; `uv run pytest` = 247). The previous attempt PROVED the send mechanics work (gotcha-4 passed on the real site) but failed to capture because it read the URL once, too early. This run re-validates end-to-end.

## ⚠️ SAFETY — transcribed verbatim; violation is mission-ending
- Chromium at `http://127.0.0.1:9222` is **SHARED with another ACTIVE agent** keep-pushing on conversation id **`6a316aa8`** (operator may be present). **OWN-TAB-ONLY:** act only on tabs the tool itself opens via `Session`/`ask`/`loop`. **NEVER** read/iterate/enumerate/touch any foreign tab, `6a316aa8`, or any pre-existing conversation. **NEVER** call `/json/list`, `browser.pages()`, `contexts()`, or write ad-hoc tab-walking code.
- **NEVER quit/close the browser** (detach only).
- **Preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` (version endpoint ONLY) first; fail → STOP `BLOCKED` `CDP_UNREACHABLE`.
- Login/Cloudflare/`HumanActionNeededError` → STOP `BLOCKED` `HUMAN-ACTION-NEEDED`, **no retry-spam**, detach, stop.
- No stealth. chatgpt.com only.
- **SEND BUDGET (HARD):** A prior attempt this mission already used **1 real send** (mission cap is ≤4 total). You may use **AT MOST 3 sends this run** (your Session's `send_budget.successful_submissions` ≤ 3): **1** for the PONG smoke, **2** for the loop. **NO send retries.** If the PONG smoke fails at any point, **STOP — do NOT run the loop** (that keeps the mission total at 2). Let `AdaptiveSendBudget` pace you (politeness floor); do not bypass it. All sends go to **FRESH throwaway chats you create**; **ZERO** to `6a316aa8` or any existing conversation.
- **NEVER print conversation content** (`content_markdown`) anywhere — only safe metadata (ids, roles, char-counts, status, counts, booleans). **NEVER log** auth/OAI/cookie/bearer values. Content → only the gitignored store (`data_dir="cache/m7-t3c-real"`; NEVER `git add cache/`).
- Branch `rewrite-v2` only; never move/commit/merge `stable`; never `uv tool ...`; never `git push`; never stage `cache/`, `controller.mjs`, `human/`.

## READ FIRST (verify signatures against actual source)
`src/ask_chatgpt/session.py` (`Session(channel="cdp", data_dir=...)`, `.attach()`, `.ask(None, prompt, timeout=...)`, `.loop(conv_or_url, message=..., max_iterations=..., timeout=...)`, `.detach()`, `.send_budget.successful_submissions`, `.history(...)`), `src/ask_chatgpt/models.py` (`TurnRecord` fields). You may reuse/adapt the prior driver `scripts/m7_t3_real.py` but write a fresh `scripts/m7_t3c_real.py` (commit the SCRIPT only, never output).

## Procedure (`uv run python scripts/m7_t3c_real.py`, emit only safe metadata JSON)
**Leg 0 — preflight** curl `/json/version`. Abort on failure.

**Leg A — PONG smoke (the FIRST fully-validated real send; 1 send):** `s = Session(channel="cdp", data_dir="cache/m7-t3c-real"); s.attach()`. `rec = s.ask(None, "Reply with only the word: PONG", timeout=90)`. **Verify (do not assume):** `rec.role == "assistant"`; `rec.conversation_id` is a real id (a `/c/<id>` was learned via the new poll); `rec.status == "complete"` (else record `partial` + stop); `len(rec.content_markdown) > 0`. Re-load `s.history(rec.conversation_id)` and assert the transcript has **a user turn carrying the prompt AND the assistant turn** (by role/count/ids — never print content). Record `successful_submissions` (must be 1) and the new `conversation_id`/`conversation_url`. **If anything here fails → STOP (do NOT run Leg B); report PARTIAL with the exact safe error.**

**Leg B — loop keep-pushing (2 sends; only if Leg A fully succeeded):** iterate `s.loop(rec.conversation_url, message="continue", max_iterations=2, timeout=90)`. Verify: exactly 2 iterations; **2 distinct assistant `message_id`s**, distinct from Leg A's; transcript grew (re-load `s.history`, assert the expected count increase). Record per-turn `status`/`partial`/content **char-count**/`capture_source`/`fidelity` (NOT content) to judge SHORT-multi-turn completion fidelity. `successful_submissions` after must be 3.

**Leg C — OPTIONAL M8 hint (no send; only if Legs A+B succeeded and budget/time allow):** on your OWN already-open tab, a single read-only `tab.channel.evaluate(...)` may list the composer toolbar's BUTTON structural attributes only — `data-testid`, `aria-label`, `aria-haspopup`, `role`, `type`, `disabled` of `button` elements within the composer form — to help M8 fix the live model/tool selector gap (last attempt: `composer-footer button[aria-haspopup="menu"]` matched 0; tools menu timed out). **Structural attributes ONLY — NO innerText of arbitrary nodes, NO conversation content, NO foreign tabs.** If unsure, SKIP this leg. Append the attribute list to your report under "M8 leg-1 selector hints".

**Teardown:** `s.detach()` (own tabs only; never quit browser).

## Output — write `team/evidence/reports/M7-T3c.md` (NO content, NO secrets)
Status token; preflight version; **EXACT this-run send count** = final `send_budget.successful_submissions` (per-leg), and a note that the mission total = 1 (prior T3) + this run; the NEW throwaway `/c/<id>`s created (so audit confirms none is `6a316aa8`); Leg A: gotcha-4 + id-learned + completion + capture all proven? assistant `message_id`/`status`/char-count/`capture_source`/`fidelity`; transcript user+assistant present; Leg B: 2 distinct assistant ids? per-turn status/partial/char-count/fidelity, transcript grew, any completion clipping; Leg C hints (if run); confirmations (own-tab-only, no `/json/list`, browser not quit, no secrets logged, `cache/` not staged, `controller.mjs`/`human/` unstaged, `stable` unmoved); blockers; signals. Commit ONLY `scripts/m7_t3c_real.py` + the report (explicit paths, no `Co-Authored-By`); NEVER `cache/`. If blocked/low budget: resume-ready report, stop.
