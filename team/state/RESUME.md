# RESUME — team lead, `ask-chatgpt-dev` (team-lead-v2)

> **STATUS: REWRITE COMPLETE — verified, merge-ready, PR opened (2026-06-20).** The directive (rewrite `ask_chatgpt` from scratch) is **achieved**. The team is now in **maintenance**. A PR for `rewrite-v2 → main` was opened for the operator to merge. A successor inherits **nothing** but what it reads here + the named files — **re-verify every live claim from ground truth** before acting.

## Bring-up (the eternal role)
You are the team lead (`team-lead-v2` skill) for `ask-chatgpt-dev`. Load `team-lead-v2`; **FIRST read & obey** `.claude/skills/manager/references/agent-rigor.md`. Rehydrate: `team/team.json` (identity), this RESUME, `team/state/live-state.json` (queue — M0–M9 done), durable lessons `/home/abhmul/.claude/projects/-home-abhmul-dev-ask-chatgpt/memory/MEMORY.md`, evidence `team/evidence/`. **Single team — do NOT load team-mesh.**

## ⚠️ Branch: the rewrite lives on `rewrite-v2`
`main` holds the baseline + a signpost; the full v2 rewrite + the cache are on **`rewrite-v2`** (`git checkout rewrite-v2`). The `rewrite-v2 → main` **merge is operator-reserved** (a PR is open; the operator merges).

## What was built (M0–M9)
A Python **library-core + thin CLI** mirroring chatgpt.com via CDP-attach: **acts** through the real UI, **captures/reads** via the page's own authenticated `GET /backend-api/conversation/<id>` (auth/OAI headers harvested from the page's own request, never persisted), per-conversation **cache** store. Arc: M0 intake/spec (`docs/REWRITE-SPEC.md`) → M1 archive v1 + scaffold → M2 ground-truth probe → M3 best-of-N design → M4 offline core (TDD) → M5 backend-api capture+scrape → M6 **target scrape delivered** → M7+M7b model/tool selection + loop + verified send → M8 terminal verification (`VERIFICATION.md`) → M9 finalize (upload wired; DR verified; family-submenu honest limitation).
**Delivered:** scrape, verified send (gotcha-4), attachments in (wired)/out, model tiers + tools (Web search, Deep Research), canonical math-faithful capture, the 4 gotcha fixes. **`uv run pytest` = 268 passed** (mutation-proven falsifiable). `VERIFICATION.md` = honest verdict (PASS offline core; real-proven vs mock-only vs untested-live separated).

## Operator deliverable (DONE)
`/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31` is scraped to the **gitignored repo cache**: `cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/` — `transcript.jsonl` (append-only; **dedupe by `message_id`** → ~515 turns), `transcript.md`, `target-assistant-export.md`, `raw-mapping.json`, `attachments/` (10 files). Re-scrape anytime (`scrape <url> --data-dir cache`) to refresh; read browser-free via `history`/`export`.

## Maintenance backlog (documented, non-blocking — future iterations)
1. **Upload final-capture re-verify** — `ask --attach` is WIRED + fail-closed (silent-no-op CLOSED; send mechanism real-proven, 2 fresh-chat turns). Only the end-to-end *capture* of the attachment-bearing reply wasn't re-run live (≤2 send budget spent; W7 verifier fix offline-proven; backend-api capture proven M5/M6). **One attended `ask --attach <file>` send closes it.**
2. **GPT-5.5 family submenu live selection** — honest documented limitation: offline-correct + **fails closed (no wrong-model risk)**, but live multi-portal Radix submenu reflection unresolved. Low priority.
3. **Mock-only / untested-live boundary** — loop multi-turn, concurrency/TabPool-eviction/adaptive-rate, projects send/create, long-real-generation. Close incrementally via attended legs.

## Re-verify from ground truth (the ledgers are a CACHE)
- **Isolation (load-bearing):** `git rev-parse stable` = `779eb40` (UNMOVED). NEVER move/commit `stable`; NEVER `uv tool install/upgrade/reinstall`. The installed tool is an isolated copy a separate agent uses.
- **Acceptance:** `uv run pytest` (268 passed; mock; real_site deselected + gated on `ASK_CHATGPT_REAL=1`). Inspect artifacts, not exit codes.
- **Real-site:** operator-attended CDP only; the other agent may share the browser (keep-pushing on the target). own-tab-only; inspect only tool-opened tabs.

## Dispatch policy + safety (for any NEW mission)
- **WORKERS → pi** (`parent-claude/pi-watch.sh`); **MANAGERS → Claude Opus** (`parent-claude/claude-watch.sh`, and the manager MUST **block-to-completion** — `claude -p` is single-shot, NO re-invocation; do NOT dispatch-and-yield). **NEVER the Claude Agent tool.** Contracts → `team/contracts/`; handoffs → `team/evidence/handoffs/`. Verify shipment, not exit codes; best-of-N for design/verification.
- **Real-leg safety:** own-tab-only; FRESH chats for any send; NEVER the target/foreign tabs; never quit the browser; preflight `curl :9222`; login/Cloudflare → STOP `HUMAN-ACTION-NEEDED`; redirect `ask`/`scrape` stdout to `/dev/null` (content-leak); never persist/log auth/OAI/cookie values; never commit `cache/` content.
- **Reserved (escalate, don't self-decide):** git push / merge-to-main (operator); credentials/sudo/installs; real-account/paywalled; manual-compaction trigger; irreducible ambiguity; team create/retire.

## Continuity
Durable record: this RESUME + `team/state/live-state.json` + `team/evidence/handoffs/{M0…M9}` + `VERIFICATION.md` + the `rewrite-v2` commits. **The directive is COMPLETE**; absent a new operator directive, the team is idle/maintenance. If the operator opens new work, run the lead loop (queue → self-contained contract → dispatch → smoke-check shipment → ingest → report → checkpoint).
