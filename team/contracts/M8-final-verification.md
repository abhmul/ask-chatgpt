# Mission M8 — Terminal: independent best-of-N verification of the COMPLETE rewrite + re-issue VERIFICATION.md

You are a detached **Claude Opus MANAGER** for `ask-chatgpt-dev`, the TERMINAL mission M8. **Load and obey** the `manager` skill, `.claude/skills/manager/references/agent-rigor.md`, and `tdd`. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit nothing but this contract, the files it names, and your appended charter.

## Mission
Independently verify the **complete ask-chatgpt v2 rewrite** (M1–M7b) and **re-issue `VERIFICATION.md`** honestly. The old `VERIFICATION.md` verifies the v1 library and is STALE — re-write it for v2 with a **falsifiability + prompt-quality lens, NOT a green-exit claim**, with **real-site-proven vs mock-only clearly separated** and **known limitations documented honestly**.

## CRITICAL EXECUTION RULE
You are `claude -p`, SINGLE-SHOT, NO re-invocation. Run the WHOLE mission to completion **in ONE turn** by **BLOCKING** on each worker (`pi-watch.sh --wait-seconds` large, e.g. 3000, blocks until the worker status file), collect + proceed. **Do NOT dispatch-and-yield.** If budget runs low, checkpoint + commit + PARTIAL handoff.

## Authoritative inputs — READ FIRST
- `docs/REWRITE-SPEC.md` + `team/evidence/reports/M3-detailed-design.md` (the spec + design to conform to).
- All handoffs: `team/evidence/handoffs/{M1-archive-scaffold, M2-ground-truth-probe, M4-offline-core, M5-capture-scrape, M6-target-scrape, M7-model-tools-loop, M7b-gaps}.md` + reports under `team/evidence/reports/`.
- The code: all of `src/ask_chatgpt/` + `tests/`. The old `VERIFICATION.md` (to replace).
- `team/charter.md` (appended) — safety + the falsifiability/prompt-quality discipline.

## Scope — best-of-N verification (distinct dimensions, reason over ONE authoritative output)
Produce the authoritative `uv run pytest` output ONCE, then dispatch a best-of-N **offline** panel of distinct lenses (do NOT have N workers each re-run heavy suites concurrently):
1. **Correctness + spec-conformance** to REWRITE-SPEC + M3 design (every public verb/behavior).
2. **Falsifiability** — confirm the suite's load-bearing tests CAN fail (mutation/revert spot-checks); flag any green-by-triviality.
3. **Gotcha-fix coverage** — all 4 gotchas (rendered-DOM math corruption; silent no-op send; truncation/hidden-ceiling; --out suppresses stdout) provably fixed + tested.
4. **Safety/leak + isolation** — no auth/OAI/cookie/conversation-content committed; cache gitignored/untracked; own-tab-only; `stable` unmoved; no `uv tool`; nothing pushed.
5. **Real-vs-mock honesty** — what is REAL-site-proven (from M2/M5/M6/M7/M7b committed evidence: scrape+fidelity, send gotcha-4 ×4, model/tool selection live, fresh-chat capture) vs mock-only vs untested-live (document gaps).
Synthesize into the re-issued `VERIFICATION.md`. Carry the M7b non-blocking notes into the lens: (a) gap-2 ordering assertion could be made explicit; (b) live coverage validated a single model tier + single tool — the **GPT-5.5 family submenu** + **Deep research** were NOT live-exercised; (c) composer-chip tool-reflection fallback exists.

## Optional light real-leg (only if cheap + attended; NO sends)
If useful, a single attended OWN-TAB real leg may exercise the **GPT-5.5 family submenu** selection + a second tool (e.g. **Deep research**) selection to round out gap-1 live coverage — **NO sends** (selection only; do NOT run Deep Research). Otherwise document these as known untested-live items. SAFETY (if any real leg): shared browser, own-tab-only, never the target/foreign, never quit, preflight, login→STOP, no leak, no persist headers. Default: prefer offline verification over the optional real leg.

## Dispatch / output / acceptance
Opus manager; **pi verify-panel workers** (read-only lenses) + at most one attended own-tab pi worker for the optional no-send real leg; NEVER the Claude Agent tool; block-collect each. Commit to `rewrite-v2` (no push, no `Co-Authored-By`; never cache content): the re-issued `VERIFICATION.md` + `team/evidence/reports/M8-verification.md` + handoff `team/evidence/handoffs/M8-final.md`.
**Acceptance:** `VERIFICATION.md` re-issued honestly — falsifiability + prompt-quality lens, real-vs-mock-vs-untested-live clearly separated, the 4 gotcha fixes + the 2 closed gaps documented, **known limitations stated plainly** (e.g. GPT-5.5 family submenu + Deep research not live-exercised; code_execution attachments unsupported; transcript.jsonl append-only/compaction nicety); best-of-N panel confirms the whole tool with evidence; offline `uv run pytest` green; safety/leak audit PASS; `stable` unmoved; nothing pushed. The directive's terminal task is independent verification — be rigorous and honest; do NOT overclaim. Recommend to the lead whether the rewrite is ready for the operator-reserved `rewrite-v2 → main` merge.
