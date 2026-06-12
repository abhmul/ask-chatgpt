# MISSION-001 — Design decision #1 research: response/file return channel vs the archive's Level B rationale

**Mission type:** research + design (NON-EDITING: no product source code is written in this mission).
**Dispatched by:** ask-chatgpt team lead, 2026-06-11.
**Wall-clock estimate:** 90–120 min (flag threshold 2× = 240 min; emit `ESTIMATE:`/`ACTUAL:` lines, see Telemetry).

## Objective

Produce ONE decision memo that lets the team lead deliberately decide **how assistant responses and files come back from the chatgpt.com chat UI** for the new `ask_chatgpt()` tool. The memo recommends; **the team lead decides** — do NOT record the decision as made.

Context of the conflict (transcribe into worker contracts as needed): the predecessor `control-plane` system's **Level B contract** allowed ONLY seeding prompts into the chat UI and **forbade DOM extraction** of responses; results flowed back through an MCP connector (GPT called tools). The new spec (`README.md` of this repo) **requires** `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` and retrieval of a **patch bundle** (a zip of changed files) — i.e. capturing assistant output WITHOUT the connector. The archive's reasoning must be read first, then weighed.

Candidate channels to weigh (from the seed handoff; not necessarily exhaustive — workers may surface others):

1. **DOM extraction via selector maps** (predecessor has selector-map infra but deliberately never used it for reads);
2. **copy-button / clipboard automation**;
3. **file-download capture** (GPT can emit downloadable files; possibly cleaner than DOM text, especially for bundles);
4. **connector-style callback channel** (predecessor's approach — heavyweight but proven; probably overkill here).

## Deliverables (all under this repo)

1. `orchestration/reports/M-001/angle-archive.md` — archive-fidelity/risk lens (see Task plan).
2. `orchestration/reports/M-001/angle-channels.md` — channel-engineering lens.
3. `orchestration/reports/M-001/angle-specfit.md` — spec-fit/simplicity lens.
4. `orchestration/reports/M-001/decision-memo.md` — the synthesis (≤ ~400 lines): the archive's Level B rationale **with citations** (file + section/line), each candidate channel weighed, a recommended primary + fallback layering for (a) plain text responses and (b) patch-bundle retrieval, rejected options with one-line reasons, and the list of **empirical unknowns only operator-gated runbooks can resolve**.
5. `orchestration/reports/M-001/verify.md` — independent verification of the memo (citations real, claims grounded, safety-compatible).
6. `orchestration/handoffs/MISSION-001-handoff.json` — handoff per the rigor handoff protocol (STATUS token first; artifacts + trust levels; recommended next missions).
7. Commit the above at mission close (message prefix `M-001:`). NEVER `git push`.

## Task plan (manager refines; best-of-N is mandatory for this design work, N=3)

- **T1a/T1b/T1c (parallel, 3 pi workers, distinct lenses):**
  - **T1a archive-fidelity/risk lens** → `angle-archive.md`: extract the ACTUAL Level B rationale from the archive with citations — what risks were claimed (selector fragility, account/ToS risk, complexity), what evidence backed each, what was empirically proven on the real site, and what infra already exists per channel (selector maps, download handling, clipboard use, seed-prompt builders). Grep-first: search `Level B`, `DOM`, `extraction`, `selector` in the archive paths below; read targeted sections, not whole files.
  - **T1b channel-engineering lens** → `angle-channels.md`: for EACH of the 4 channels: mechanism, Playwright implementation sketch, failure modes, what is server-visible vs purely client-side (key for account-risk reasoning), robustness under UI drift, fit for BOTH `-> text` and patch-bundle (zip) retrieval, fit for session continuity (returning to a conversation by identifier) and model selection. Rank with justification.
  - **T1c spec-fit/simplicity lens** → `angle-specfit.md`: start from this repo's `README.md` (spec, acceptance shape, library-first posture, honest failure modes) and the operator-UX rule (1–2 commands, inline prompts, honest actionable failures — long runbooks rejected as UX 2026-06-10): derive the MINIMAL design satisfying the three use cases (Occam); which channel(s) minimize moving parts; what a local mock-ChatGPT fixture must support to test each channel with ZERO chatgpt.com contact; what only runbooks can prove.
- **T2 (1 pi worker, after T1*):** best-of-N synthesis → `decision-memo.md`. Reads all three angle reports; strongest elements kept, conflicts reconciled, selection justified. Must include a "what the mock fixture must support" section and the empirical-unknowns list: upload size/type limits for zip attachments; whether/when chatgpt.com offers file downloads from responses; session pinning via URL; model selection UI hooks.
- **T3 (1 pi worker, INDEPENDENT — not the synthesizer):** verify the memo → `verify.md`: every archive citation resolves (spot-check by opening the cited file/section); claims about the spec match `README.md`; the recommendation violates no safety rule below; single-token verdict per check, overall `VERDICT: PASS|FAIL` line. If FAIL → manager revives T2 with the findings.
- Manager writes the handoff JSON, commits, ends.

## Archive pointers (READ-ONLY: `/home/abhmul/Documents/weak-simplex-conjecture/`)

- `control-plane/DESIGN.md` — Phase-3 section; Level B / M-004 design rationale (grep `Level B`).
- `control-plane/src/control_plane/browser/` — Playwright session controller, recovery, `ChatUIDriver` 8-method allowlist, selector-map pattern, seed-prompt builders.
- `control-plane/VERIFICATION.md` — what was independently verified (§1–§10.1) and how.
- `control-plane/docs/runbooks/{phase2-chatgpt-acceptance,phase3-chatgpt-browser,mvp-demo}.md` — what was empirically proven on the REAL site (login, profile, consent flows).
- `control-plane/tests/` — phase3 mock chat fixture + `tests/fixtures/phase3_mock_selector_map.json` (mock-vs-real channel knobs).
- `orchestration/handoffs/MISSION-004-handoff.json` (and neighbors `MISSION-00{1..9}`) — how the browser adapter mission was sliced and what blocked.
- **NEVER write anywhere under `/home/abhmul/Documents/weak-simplex-conjecture/`. NEVER read its `archive/` or `human/` directories.**

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- This mission contacts NO network service. NEVER contact chatgpt.com/openai or any tunnel service. Research is file-reading only.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (reports under `orchestration/reports/M-001/`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY; never read its `archive/` or `human/` dirs. Never write `.claude/` or `.agents/`.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock before any major command).
- End your report with a single-token status line: `T<ID>-STATUS: DONE|BLOCKED` (last line; watchers gate on `tail -1`).

## Worker mechanics (for the manager)

- Spawn pi (GPT 5.5 xhigh) workers with: `bash .claude/skills/orchestration/references/pi-worker-watch.sh "<pointer to task file>"` from the repo root. Detached tmux; returns when done or after 30 min; re-watch with the printed `--watch <run-dir>` command. **Max 3 pi workers concurrent.**
- Worker task contracts: one `.json`/`.md` file per task under `orchestration/tasks/M-001/`, fully self-contained (task, exact deliverable path, archive pointers it needs, the SAFETY BLOCK verbatim, telemetry lines required, report-length cap ~300 lines, grep-first instruction).
- pi errs on broad problems — keep each contract single-problem and narrow.

## Telemetry (charter requirement, day one)

- Manager: emit `ESTIMATE: M-001 <minutes>m` before dispatching the first worker and `ACTUAL: M-001 <minutes>m` + an end timestamp (`date -Iseconds`) in the handoff.
- Every worker contract requires the worker to emit `ESTIMATE: <task-id> <minutes>m` before starting and `ACTUAL: <task-id> <minutes>m` + end timestamp at the end of its report.
- Any rework leg gets `REWORK-CAUSE: <spec-gap|env-drift|frozen-file|dependency-rot|other>`.

## Handoff requirements (`orchestration/handoffs/MISSION-001-handoff.json`)

Per the rigor protocol: `STATUS: DONE|PARTIAL|BLOCKED` near the top; what was verified + evidence (verdict tokens, paths); artifacts + trust level each; blockers (exact action needed); recommended next missions; complexity/paradigm-shift signals. The handoff must state plainly that the DECISION IS NOT MADE — the memo is input to the team lead's decision.
