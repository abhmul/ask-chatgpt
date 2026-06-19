# Mission M6 — Deliver the target scrape (with attachments) into the repo cache — IMPLEMENTATION + DELIVERY

You are a detached **Claude Opus MANAGER** for the `ask-chatgpt-dev` team, mission M6. **Load and obey** the `manager` skill, `.claude/skills/manager/references/agent-rigor.md`, and `tdd`. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit nothing but this contract, the files it names, and your appended charter.

## Mission
Deliver the operator's pressing deliverable: scrape the **target** `6a316aa8-5dc8-83ea-9014-b8ea38dabc31` (`https://chatgpt.com/c/6a316aa8…`) **with attachments** into the repo-local **cache**, confirm math fidelity, and hand it to the operator. The capture+scrape path is already **PROVEN** (M5 scraped this target read-only: 481 turns / 2.0M chars / 6,124 nodes / 20MB; `\widehat`/`\ne`/`\frac` intact).

## Operator decision — apply
Scraped conversations live in a **repo-local cache folder, gitignored, acting as a cache**: `<repo>/cache/` is the data-dir. **Make `cache/` the DEFAULT data-dir** (your cleanest implementation — CWD-relative `cache/` or repo-root-anchored), it is **already gitignored** (`.gitignore` has `cache/`). Ensure **cache semantics**: `scrape` populates it; `history`/`export` read from it WITHOUT re-scraping/browser; re-scrape refreshes. Structure (design §3): `cache/conversations/<id>/{transcript.jsonl, raw-mapping.json, attachments/}` + `cache/index.json`. The cache holds the operator's conversation content + attachments → **NEVER commit cache content** (gitignored); commit only CODE/config.

## Authoritative inputs — READ FIRST
- `team/evidence/handoffs/M5-capture-scrape.md` + the M5 code (`CdpChannel`/`capture`/`scrape` PROVEN). `team/evidence/reports/M5-T3-real-leg.md` (target shape, completion vocab, attachment ref shapes).
- `team/evidence/reports/M3-detailed-design.md` (§3 store/layout/linearization, §2.3/§4 capture, §3.7 attachments, §8 CLI). `team/evidence/handoffs/M2-ground-truth-probe.md` (attachment shapes: `metadata.attachments`, `content_references[type=file]`, `content.assets[].asset_pointer`, code `metadata.aggregate_result` — ids/pointers; no literal `/files/` URLs seen).
- `team/charter.md` (appended) — safety.

## Scope (deliver the transcript FIRST, then attachments)
1. **Cache setup**: default data-dir → repo `cache/`; cache semantics (history/export read-from-cache, no browser/re-scrape). Offline-testable (extend the mock suite).
2. **Transcript (primary value) — deliver ASAP**: scrape `6a316aa8` (transcript + markdown export, NO attachments yet) into `cache/` over CDP; **confirm math fidelity** (`\widehat`/`\ne`/`\frac` round-trip on heavy-math + DR turns; no flattened fractions). Commit code + report the cache path + fidelity so the operator has the transcript early.
3. **Attachments**: discover the attachment **byte-download routes** (real-site, READ-ONLY own-tab investigation — how the web app fetches a referenced file/asset: endpoint / `asset_pointer` resolution); implement lazy download into `cache/conversations/<id>/attachments/`; run `scrape --with-attachments` → download the target's artifacts. Report which types downloaded vs unsupported, with route findings.
4. **Verify**: math fidelity + cache acts as a cache (history reads it with no re-scrape) + an independent **pi verify panel** incl. safety/leak audit (no conversation content or header values committed; ZERO sends; own-tab-only).

## SAFETY (real-site, SHARED browser — transcribe verbatim into every real-leg worker contract)
The browser at `127.0.0.1:9222` is SHARED with another ACTIVE agent. **own-tab-only** (never read/iterate foreign tabs — there is a prior leak incident); **READ-ONLY** (scrape + attachment download are reads; **ZERO sends / new turns / model-tool selection**); **never quit** the browser (detach only); **preflight** `curl` first; login/Cloudflare → STOP `HUMAN-ACTION-NEEDED`; no stealth; allowlist; **NEVER persist/log** `authorization`/`oai-*`/`cookie` values; read ONLY the authorized target `6a316aa8`. Cache content stays LOCAL (gitignored) — never committed. Branch `rewrite-v2` only; never move/commit `stable`; never `uv tool install/upgrade/reinstall`; `uv run`/`uv sync` only; never `git push`; stage ONLY code/config (NEVER `cache/` content, `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, or `human/`). NEVER the Claude Agent tool (workers = pi; this manager = Opus).

## Output
- Commit CODE/config increments to `rewrite-v2` (no push, no `Co-Authored-By`): default-data-dir, attachment download, cache semantics, tests. **NEVER commit `cache/` content.**
- **DELIVER to the operator** (in the handoff): the cache path holding the transcript + markdown + attachments (e.g. `cache/conversations/6a316aa8-…/`), counts/sizes, the **fidelity verdict**, and which attachments downloaded.
- Handoff `team/evidence/handoffs/M6-target-scrape.md`: Status; transcript delivered (path/counts/fidelity); attachments (downloaded/unsupported + routes); verify verdict (incl. leak/no-send audit); blockers; recommended next (M7).
- **If session budget runs low**: checkpoint state + commit code + write a PARTIAL handoff (this may be multi-session, like M4/M5).

## Acceptance
Target transcript at `cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/transcript.jsonl` + rendered markdown; **math fidelity confirmed**; attachments downloaded into the gitignored cache (or documented route-findings for unsupported types); cache **acts as a cache** (history reads without re-scrape); **ZERO sends; own-tab-only; NO conversation content or header values committed to git**; code committed; offline suite green; `stable` unmoved; nothing pushed. Independent pi panel confirms (incl. leak/no-send audit). Report honestly; **deliver the transcript even if attachments partially fail**.
