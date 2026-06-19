# Mission M7 — Model/tool selection + keep-pushing loop + tab pool/rate — IMPLEMENTATION + first real SEND

You are a detached **Claude Opus MANAGER** for `ask-chatgpt-dev`, mission M7. **Load and obey** the `manager` skill, `.claude/skills/manager/references/agent-rigor.md`, and `tdd`. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit nothing but this contract, the files it names, and your appended charter.

## Mission
Complete the tool's functionality: implement + verify (1) general **label-driven model/tool selection** (Radix menus), (2) the **keep-pushing loop** (persistent `Session`, verify each turn), (3) the **tab pool + adaptive send-rate budget**. Per M3 design §10 M7, §2.6 menus, §6 send, §7 concurrency, §11 model/tools. **This mission contains the FIRST REAL SEND** by the rewrite — kept MINIMAL, human-paced, to FRESH throwaway conversations ONLY.

## Authoritative inputs — READ FIRST
- `team/evidence/reports/M3-detailed-design.md` (§2.6 menus, §6 send, §7 concurrency, §11). `team/evidence/handoffs/M2-ground-truth-probe.md` + `team/evidence/reports/M5-T3-real-leg.md` (live selectors; model picker has NO stable test-id → label-driven Radix; model labels Instant/Medium/High/Extra High/Pro Extended/GPT-5.5; tools menu Deep research/Web search/etc.). M4 code (`menus.py` fail-closed stub, `send.py`/`completion.py`, `session.py`, `TabPool`/`AdaptiveSendBudget` stubs). `team/charter.md` (appended) — safety.

## Build OFFLINE first (the bulk — mock-proven, NO real legs, no approval needed)
- `menus.py`: executable Radix enumeration + select-by-label + **reflected-label verification** (fail-closed if absent/ambiguous; **NEVER open `Recent files`/`Projects` submenus** — operator privacy).
- `TabPool`: lazy-open, idle-evict, LRU, own-tabs-only, close own tabs only.
- `AdaptiveSendBudget`: politeness floor + AIMD/backoff on rate/429/Cloudflare signals + hard pause on login; **NO hard message cap**; single owner on the persistent `Session`.
- `loop`: over one persistent `Session` — attach once → send → **verify-new-turn** → capture → append transcript → repeat; SIGINT salvage; emits JSONL.
Mock-prove ALL of it (`uv run pytest` green, falsifiable tests).

## Real verification (attended, own-tab, MINIMAL sends, FRESH throwaway chats ONLY)
SAFETY (transcribe verbatim into every real-leg worker contract): the browser at `127.0.0.1:9222` is SHARED with another ACTIVE agent (it is keep-pushing on the target `6a316aa8`). **own-tab-only** — never read/iterate/touch foreign tabs OR the target conversation; **never quit** the browser; **preflight** curl; login/Cloudflare → STOP `HUMAN-ACTION-NEEDED`; no stealth; allowlist; **redirect `ask`/`scrape` stdout to `/dev/null`** (content-leak lesson); **NEVER persist/log** auth/OAI/cookie values. **Model-label is TRANSIENT on reload** (briefly shows "Extra High" before settling) → verify selection with a **SUSTAINED (~12s) read**, never halt on a single mismatch. **Human-paced**: minimal sends + politeness floor + backoff — the other agent shares this account; do NOT spam.
1. **Real model/tool selection (NO send):** on a FRESH conversation (tool-created own tab), open the model picker + select a low-cost model (e.g. the current default or `Instant`); open the tools menu + toggle a tool (e.g. `Web search`); verify the reflected label via SUSTAINED read. No message sent.
2. **Send-smoke — THE FIRST REAL SEND (ONE trivial message):** create a FRESH throwaway conversation and send exactly: `Reply with only the word: PONG` (trivial plumbing probe — content irrelevant; stresses SHORT-response completion). Verify: a NEW user turn carrying the prompt appeared (gotcha-4: else `PromptNotSubmittedError`), a NEWER assistant turn completed, the response captured, transcript written to cache. **ONE send only.**
3. **Loop-verify (MINIMAL):** on a FRESH throwaway chat, run `loop` for **2 iterations** of a trivial prompt (e.g. `continue`), verifying each iteration adds a new verified turn. **≤3 sends total.** Then stop.
**Do NOT touch the target `6a316aa8` or any operator/other-agent tab. Do NOT run a long real push loop.** Total real sends this mission ≤ 4, all to fresh throwaway chats.

## Dispatch policy
Opus manager; **single pi editor** for offline src (surrounded by non-editing best-of-N); **pi real-leg workers** (own-tab, full safety block transcribed); **pi verify panel** incl. a **send-count + leak audit** (confirm ONLY the minimal smoke/loop sends occurred, all to fresh throwaway chats; no conversation content / headers committed; cache content not tracked). **NEVER the Claude Agent tool.**

## Output
Commit CODE to `rewrite-v2` (no push, no `Co-Authored-By`; **NEVER commit cache content**). Handoff `team/evidence/handoffs/M7-model-tools-loop.md`: status; what was real-verified (model/tool selection sustained-read result; **send-smoke result + EXACT send count + which throwaway chats were created**; gotcha-4 real-proven); offline suite count; leak/safety/send-count audit; blockers; recommended next (M8). If session budget runs low: checkpoint + commit code + PARTIAL handoff (multi-session-sized, like M4/M5/M6).

## Acceptance
Model/tool selection real-verified (sustained-read, fail-closed); **real SEND proven** (gotcha-4: new-turn-verified on a fresh chat; ONE smoke send + ≤3 loop sends, all throwaway, response captured); tab pool + adaptive budget work (mock + minimal real); offline `uv run pytest` green with falsifiable tests; **ZERO sends to the target or any existing operator conversation**; own-tab-only; no leak; `stable` unmoved; no `uv tool`; nothing pushed; cache content never committed. Independent pi panel confirms (incl. send-count + leak audit). Report honestly.
