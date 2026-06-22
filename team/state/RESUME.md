# RESUME — team lead, `ask-chatgpt-dev` (team-lead-v2)

> **STATUS: REWRITE COMPLETE + MERGED to `main`** (PR #1 `be83b3b`; release 0.2.0 `bbbe027`; operator moved `stable` to it). Team in **MAINTENANCE**. Latest: **M10 (2026-06-22) COMPLETE + verified end-to-end** (read-ops light-page fix; see the M10 section below). A successor inherits **nothing** but what it reads here + the named files — **re-verify every live claim from ground truth** before acting.

## M10 (2026-06-22) — read-ops light-page fix: COMPLETE + verified, branch awaiting operator merge
**Problem** (`issues/2026-06-22-read-ops-render-full-conversation-page.md`): `scrape` acquired its tab by navigating to `https://chatgpt.com/c/<id>`, forcing the SPA to render the entire conversation DOM (KaTeX/proof-trees) — crashing the renderer on large conversations — even though capture reads via the authenticated backend-API fetch, not the DOM.
**Re-derived scope** (issue was partly wrong): ONLY `scrape` was an always-heavy read; `history`/`fetch`/`status` already acquire no tab; `ask`/`loop` are sends that legitimately need `/c/<id>`.
**Fix** (branch **`fix/m10-light-read-scrape`**, HEAD `4c36f09`): `TabPool.acquire(ref, *, render=True)` — `render=False` opens the light `https://chatgpt.com/` and the pool is keyed by `(mode,url)`; `scrape` uses `render=False` + an opt-in `ambient_backend` header-harvest mode (matches any `GET /backend-api/*` carrying all 8 `REQUIRED_CAPTURE_HEADERS`; `cdp.py:wait_for_request` made header-aware to skip deficient matches); `retarget_headers` sets `x-openai-target-path` to the fetched path; `x-openai-target-route` kept verbatim (real-leg-confirmed accepted). **Default send/draft/completion harvest UNCHANGED (exact `conversation` mode) — M7b gap-2 behavior preserved.** Touches only `session.py`/`capture.py`/`channels/cdp.py` + tests (NOT `cli.py`/`store.py`).
**Verified:** best-of-N offline panel PASS (V1 correctness / V2 mutation-falsifiability / V3 safety-leak-regression); `uv run pytest` = **276 passed** (mutation-proven; lead re-ran). **Attended real-site leg PASS** on the crash-repro `/c/6a387270-c3b0-83ea-991f-81085a2eeb9b`: exit 0, **5s** (vs prior ~10-min hang/crash), NO renderer crash, 44 turns / 1915 nodes, all `backend_api`+`canonical`, math perfect (`\frac`×355,`\widehat`×25, flattened-frac=0, literal U+2260=0); U1 (ambient root harvest works) + U2 (verbatim route accepted) PASS; safety clean (zero sends, own-tab-only, no `/json/list`, no leak, `stable` unmoved, cache uncommitted). Evidence: `team/evidence/handoffs/M10-*` + `team/contracts/M10-*`.
**Merge `fix/m10-light-read-scrape → main` is OPERATOR-RESERVED** (not yet merged; lead did not auto-commit the team/ M10 evidence either — both await operator). **Note for a real-site `scrape`:** markdown isn't auto-cached — pass `--out <file>` (or use `export`/`history --out`); the cache stores `transcript.jsonl`+`raw-mapping.json` (canonical) and markdown is a stdout/`--out` render.
**Remaining backlog (separate, NOT M10):** CLI tab-leak-per-invocation (`issues/2026-06-20-*`); chatgpt rate-limit (`issues/2026-06-21-*`).

## Bring-up (the eternal role)
You are the team lead (`team-lead-v2` skill) for `ask-chatgpt-dev`. Load `team-lead-v2`; **FIRST read & obey** `.claude/skills/manager/references/agent-rigor.md`. Rehydrate: `team/team.json` (identity), this RESUME, `team/state/live-state.json` (queue — M0–M9 done), durable lessons `/home/abhmul/.claude/projects/-home-abhmul-dev-ask-chatgpt/memory/MEMORY.md`, evidence `team/evidence/`. **Single team — do NOT load team-mesh.**

## ⚠️ Branches
`main` now holds the full v2 rewrite (merged via PR #1 `be83b3b`; release 0.2.0 `bbbe027`). The M10 read-render fix is on **`fix/m10-light-read-scrape`** (HEAD `4c36f09`, off `main`). **Merging `fix/m10-light-read-scrape → main` is operator-reserved** (not yet merged as of 2026-06-22).

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
