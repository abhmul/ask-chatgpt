# Contract M7-T3 — REAL legs (attended, OWN-TAB-ONLY, FRESH throwaway chats, ≤4 sends)

You are a **pi REAL-LEG worker** for `ask-chatgpt-dev`, task **M7-T3**. Repo `/home/abhmul/dev/ask-chatgpt` (cwd set), branch **`rewrite-v2`**. You inherit **nothing** but this contract and the files it names. **First read and obey** `.claude/skills/manager/references/agent-rigor.md`. This task drives the **LIVE chatgpt.com** through the rewrite over CDP. The offline core is committed + green (`uv run pytest` = 246 passed) and hardened (sustained model-label read; submit settle).

## ⚠️ SAFETY — read twice, transcribed verbatim; violation is mission-ending
- The Chromium at `http://127.0.0.1:9222` is **SHARED with another ACTIVE agent** that is keep-pushing on the conversation id **`6a316aa8`** (and the operator may be present). **OWN-TAB-ONLY:** only ever act on tabs the **tool itself opens** via the `Session`/`TabPool` API. **NEVER** read, iterate, enumerate, screenshot, or touch any foreign tab, the target `6a316aa8`, or ANY pre-existing conversation. **NEVER** call `/json/list`, `browser.contexts`, `pages()`, or any tab/page enumeration; **do not write ad-hoc CDP/Playwright tab-walking code** — a loose tab-walker previously leaked the operator's conversation. Use ONLY `session.create()` → `session.tab_pool.acquire()` / `session.ask()` / `session.loop()` (own-tab by construction).
- **NEVER quit/close the browser** (detach only: `session.detach()` closes only the tool's OWN managed tabs). 
- **Preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` (version endpoint ONLY — never `/json/list`) before any leg. If it fails → STOP, write status `BLOCKED` reason `CDP_UNREACHABLE`, do nothing else.
- **Login / Cloudflare "Just a moment…" / any `HumanActionNeededError`** → STOP immediately, write status `BLOCKED` reason `HUMAN-ACTION-NEEDED`, **do NOT retry-spam**, detach, stop. (The tool fails closed on challenges — honor it.)
- **No stealth / no anti-detection** ever. Domain is chatgpt.com only.
- **TOTAL real sends this task ≤ 4**, all to **FRESH throwaway chats you create**. **ZERO** sends to the target `6a316aa8` or any existing conversation. Human-paced: the `AdaptiveSendBudget` enforces a politeness floor + spacing — **do not disable or bypass it**; let it pace you. Do NOT run any long/extra push loop.
- **NEVER persist or log** auth/OAI/cookie/bearer values or any header VALUES. **NEVER print conversation content** (`content_markdown`) to stdout, your log, or your report — emit only safe metadata (ids, roles, char-counts, status, counts, booleans). Conversation content goes ONLY to the gitignored store.
- Branch `rewrite-v2` only. **NEVER** move/commit/merge `stable`; **NEVER** `uv tool install/upgrade/reinstall` (use `uv run`); **NEVER** `git push`; **NEVER** `git add` `cache/`, `.pi-workers/`, `human/`, or stage `issues/cdp-send-repro/controller.mjs`. **NEVER commit cache/conversation content.**

## READ FIRST (verify signatures against ACTUAL source — do not trust this skeleton blindly)
- `src/ask_chatgpt/session.py` — `Session(channel="cdp", data_dir=..., cdp_endpoint=...)`, `.create(project=None) -> ConversationRef`, `.tab_pool.acquire(ref) -> TabLease`, `.ask(conv_or_url, prompt, ...) -> TurnRecord` (draft when `conv_or_url=None`), `.loop(conv_or_url, message=..., max_iterations=..., timeout=...) -> Iterator[TurnRecord]`, `.attach()/.detach()`, `.send_budget.successful_submissions`, `.selector_map`, `.history(conv_or_url)`.
- `src/ask_chatgpt/menus.py` — `select_model(tab, selectors, label) -> SelectionResult` (`.verified` bool), `set_tools(tab, selectors, labels) -> tuple[SelectionResult, ...]`.
- `src/ask_chatgpt/models.py` — `TurnRecord` fields (`message_id`, `role`, `content_markdown`, `status`, `conversation_id`, `conversation_url`, `capture_source`, `fidelity`, `partial`).
- `src/ask_chatgpt/errors.py` — `HumanActionNeededError`, `PromptNotSubmittedError`, `CompletionTimeoutError`.

## Procedure — write ONE Python driver script (`scripts/m7_t3_real.py`, you may commit the SCRIPT but never its output/data), run via `uv run python scripts/m7_t3_real.py`. Use `data_dir="cache/m7-t3-real"` (gitignored — NEVER git add it). The script must emit ONLY safe metadata as JSON lines to stdout (no content). Drive these legs **in order**, stopping on any STOP condition:

**Leg 0 — preflight:** curl `/json/version` (shell, before launching the script). Abort on failure.

**Leg 1 — model/tool selection, NO SEND (0 sends):** `s = Session(channel="cdp", data_dir="cache/m7-t3-real"); s.attach()`. `ref = s.create()` (fresh draft, url `https://chatgpt.com/`). `tab = s.tab_pool.acquire(ref)`. Call `select_model(tab, s.selector_map, "Instant")` (a low-cost tier; if absent on the live menu, pick the lowest tier actually enumerated and say which) and `set_tools(tab, s.selector_map, ["Web search"])`. Assert each `SelectionResult.verified is True` (the **sustained ~12s read** must confirm reflection, tolerating the transient `Extra High`). **Send nothing.** Record `s.send_budget.successful_submissions` (must still be 0). If `select_model`/`set_tools` raises `…NotReflectedError`, that is a real finding — record it (model/tool selection FAILED), do not crash silently. Then proceed (selection failure does not by itself block the send legs).

**Leg 2 — FIRST REAL SEND, the PONG smoke (1 send):** `rec = s.ask(None, "Reply with only the word: PONG", timeout=90)`. This drafts a FRESH throwaway chat, runs gotcha-4 (a NEW user turn carrying the prompt, else `PromptNotSubmittedError`), learns the server `/c/<id>`, eager-writes, waits completion, captures. **Verify (do not assume):** `rec.role == "assistant"`, `rec.conversation_id` is a real id (not None), `rec.status == "complete"` (or record `partial`), `len(rec.content_markdown) > 0`. Load `s.history(rec.conversation_id)` and assert the transcript has **a user turn carrying the prompt AND the assistant turn** (check by role/count/ids — never print content). Record `successful_submissions` (must be 1) and the new `conversation_id`/`conversation_url`.

**Leg 3 — loop-verify (2 sends, total 3):** `for i, t in enumerate(s.loop(rec.conversation_url, message="continue", max_iterations=2, timeout=90)): …`. Collect the 2 yielded `TurnRecord`s. **Verify:** exactly 2 iterations, **2 distinct assistant `message_id`s** (and distinct from leg 2's), each appended to the transcript (re-load `s.history`, assert turn count grew by the expected amount). Record `successful_submissions` after (must be 3). This stresses SHORT multi-turn completion — record each turn's `status`/`partial`/`content` **char-count**/`capture_source`/`fidelity` (NOT content) so completion fidelity can be judged.

**Teardown:** `s.detach()` (closes only OWN tabs; never quits browser). 

If any leg raises `HumanActionNeededError`/Cloudflare/login → STOP per SAFETY, status `BLOCKED` `HUMAN-ACTION-NEEDED`. If `PromptNotSubmittedError` on a send → that is a real gotcha-4 finding; record it (status `PARTIAL`/`BLOCKED` with which leg), detach, stop.

## Output — write `team/evidence/reports/M7-T3.md` (NO conversation content, NO secrets)
- Status token (`DONE`/`PARTIAL`/`BLOCKED`) at top.
- CDP preflight result (browser version string).
- **EXACT real send count** = final `send_budget.successful_submissions` (authoritative counter, not your memory) — must be ≤4; break down per leg (Leg1=0, Leg2=1, Leg3=2).
- **Which throwaway conversation ids/urls were created** (the `/c/<id>`s — these are NEW throwaway chats you made; list them so the audit can confirm none is the target `6a316aa8` or pre-existing).
- Leg 1: did `select_model("Instant")` + `set_tools(["Web search"])` verify `True` via the sustained read? Exact tier/tool used; any `…NotReflectedError`.
- Leg 2: gotcha-4 real-proven? assistant turn `message_id`, `status`, content **char-count**, `capture_source`, `fidelity`; transcript user+assistant present.
- Leg 3: 2 distinct assistant `message_id`s? per-turn `status`/`partial`/char-count/`fidelity`; transcript grew; any completion clipping observed.
- Confirmation: own-tab-only (no foreign/target tab touched; no `/json/list`/page enumeration in your script); browser NOT quit; no auth/OAI/cookie values logged; `cache/` NOT staged; `controller.mjs`/`human/` unstaged; `stable` unmoved.
- Blockers (exact action needed); complexity/paradigm signals.
- If you commit, commit ONLY `scripts/m7_t3_real.py` (explicit path, no `Co-Authored-By`) and your report — **NEVER** `cache/`. If low on budget or blocked, write a resume-ready report and stop.
