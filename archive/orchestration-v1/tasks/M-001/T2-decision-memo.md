# T2 — best-of-N synthesis: decision-memo.md (MISSION-001)

**You are a pi (GPT 5.5 xhigh) worker. This contract is self-contained — you inherit NOTHING beyond what is written here and the files it names. Read only what this contract points you to.**

## Task type
best-of-N synthesis (N=3). You read three independent "angle" reports plus the authoritative spec and archive, and produce ONE decision memo. You are NOT the verifier — a separate independent worker (T3) will check your memo afterward. Do your own confirmation of citations regardless.

## ESTIMATE BEFORE EXECUTE
Before doing heavy work, emit a line `ESTIMATE: T2 <minutes>m` (your honest wall-clock estimate). At the end emit `ACTUAL: T2 <minutes>m` and an end timestamp from `date -Iseconds`. These are charter telemetry requirements — do not skip them.

## Exact deliverable (write ONLY this file)
`orchestration/reports/M-001/decision-memo.md` — the synthesis memo, **≤ ~400 lines**. Markdown. Last line MUST be a single-token status: `T2-STATUS: DONE` (or `T2-STATUS: BLOCKED` with reason on the line above if you cannot proceed). A watcher gates on `tail -1`, so the status line MUST be last.

## Objective of the memo
Let the ask-chatgpt **team lead deliberately decide how assistant responses and files come back from the chatgpt.com chat UI** for a new `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` tool that must also retrieve a **patch bundle** (a zip of changed files). The memo **RECOMMENDS**; the team lead **DECIDES**. **Do NOT record the decision as made.** Frame everything as input to a human decision.

### The conflict you are resolving
The predecessor `control-plane` system's **Level B contract** allowed ONLY seeding prompts into the chat UI and **forbade DOM extraction** of responses; results flowed back through an MCP connector (GPT called tools). The new spec (`/home/abhmul/dev/ask-chatgpt/README.md`) **requires** capturing assistant output (`-> text`) and a patch-bundle zip **without** that connector. You must surface the archive's Level B reasoning faithfully (with citations), weigh it against the new spec's needs, and recommend a channel design.

### Candidate channels to weigh (not necessarily exhaustive — the angle reports may surface more)
1. **DOM extraction via selector maps** (predecessor has selector-map infra but deliberately never used it for reads);
2. **copy-button / clipboard automation**;
3. **file-download capture** (GPT can emit downloadable files; possibly cleaner for bundles);
4. **connector-style callback channel** (predecessor's approach — heavyweight but proven; probably overkill here).

## Inputs you MUST read (in this order)
1. `/home/abhmul/dev/ask-chatgpt/README.md` — the authoritative spec (the three use cases, acceptance shape, library-first posture, honest failure modes, operator-UX rule). Ground every spec claim in this file.
2. `orchestration/reports/M-001/angle-archive.md` — archive-fidelity / risk lens: the ACTUAL Level B rationale with citations, risk claims + evidence strength, what was empirically proven on the real site vs only mocked, and existing infra per channel.
3. `orchestration/reports/M-001/angle-channels.md` — channel-engineering lens: per-channel mechanism, Playwright sketch, failure modes, server-visible-vs-client-only, robustness under UI drift, fit for both `-> text` and zip retrieval, fit for session continuity + model selection, with rankings.
4. `orchestration/reports/M-001/angle-specfit.md` — spec-fit / simplicity lens: the three use cases as testable obligations, the minimal design by moving parts, mock-fixture requirements, and operator-gated unknowns.

## Citation discipline (CRITICAL — T3 will independently re-check this)
The memo must present the archive's Level B rationale **with citations (file + section heading or line range)**. **Confirm each archive citation you include by opening the cited file/section yourself — grep-first.** Do NOT copy a citation from `angle-archive.md` that you have not personally resolved. A citation that does not resolve will fail T3 verification. Archive is READ-ONLY (see SAFETY BLOCK).

### Archive pointers (READ-ONLY; grep-first, read targeted sections, NOT whole files)
Root: `/home/abhmul/Documents/weak-simplex-conjecture/`
- `control-plane/DESIGN.md` — Phase-3 / Level B / M-004 rationale (grep `Level B`, `DOM`, `extraction`, `selector`).
- `control-plane/src/control_plane/browser/` — `driver.py` (ChatUIDriver 8-method allowlist), `selectors.py` (selector-map pattern), `seeds.py` (seed-prompt builders), `recovery.py`, `session.py`.
- `control-plane/VERIFICATION.md` — what was independently verified (§1–§10.1) and how.
- `control-plane/docs/runbooks/{phase2-chatgpt-acceptance,phase3-chatgpt-browser,mvp-demo}.md` — what was empirically proven on the REAL site (login, profile, consent flows).
- `control-plane/tests/` + `control-plane/tests/fixtures/phase3_mock_selector_map.json` — phase3 mock chat fixture and the mock-vs-real channel knobs.
- `control-plane/orchestration/handoffs/MISSION-004-handoff.json` (and neighbors `MISSION-00{1..9}`) — how the browser adapter mission was sliced and what blocked.

## Required memo structure (cover every item; keep it tight, ≤ ~400 lines)
1. **TL;DR / recommendation up front** (≤ 12 lines): primary + fallback channel for (a) plain text responses and (b) patch-bundle (zip) retrieval, one sentence each. State explicitly: "Recommendation only — the team lead decides; the decision is NOT made."
2. **The archive's Level B rationale, with citations.** What the Level B contract actually said; each risk it claimed for forbidding DOM extraction (selector fragility, account/ToS risk, complexity, …); the **evidence strength** behind each (empirically proven on real site? only asserted? only mocked?). Every claim carries a resolved `file:section-or-line` citation.
3. **Each candidate channel weighed** (the 4 above + any the angle reports surface). For each: mechanism; fit for `-> text`; fit for zip-bundle retrieval; server-visible vs client-only (account-risk relevance); robustness under UI drift; fit for session continuity (returning by `session_identifier`) and model selection; existing predecessor infra it could reuse.
4. **Recommended layering.** Primary + fallback for (a) text and (b) bundle, with the justification for the selection and how conflicts between the three lenses were reconciled (best-of-N: keep strongest elements, reconcile conflicts, justify the pick). Note where the recommendation honors vs deliberately departs from Level B, and why the departure is justified under the new spec.
5. **Rejected options** — each with a one-line reason.
6. **What the local mock-ChatGPT fixture must support** — so each recommended channel can be tested with **ZERO chatgpt.com contact** (synthesize from `angle-specfit.md` §mock-fixture and the archive's phase3 mock fixture). Be concrete: what DOM/affordances/download/clipboard behaviors the mock must expose per channel.
7. **Empirical unknowns — resolvable ONLY by operator-gated runbooks** (must explicitly include, at minimum): upload size/type limits for zip attachments; whether/when chatgpt.com offers file **downloads** from responses; session pinning via URL (returning to a conversation by identifier); model-selection UI hooks. Add any others the lenses surface. For each, name what a runbook would have to observe to resolve it.
8. **Telemetry footer**: `ESTIMATE: T2 <minutes>m`, `ACTUAL: T2 <minutes>m`, end timestamp.

## Non-goals
- Do NOT write product source code. NON-EDITING mission.
- Do NOT make or record the decision. Recommend only.
- Do NOT contact any network service to "check" current chatgpt.com behavior — those go in the empirical-unknowns list instead.
- Do NOT exceed ~400 lines; be dense, not verbose.

## SAFETY BLOCK — obey VERBATIM
- This mission contacts NO network service. NEVER contact chatgpt.com/openai or any tunnel service. Research is file-reading only.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your single output is `orchestration/reports/M-001/decision-memo.md`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY; never read its `archive/` or `human/` dirs. Never write `.claude/` or `.agents/`.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock before any major command).
- End your report with a single-token status line: `T2-STATUS: DONE|BLOCKED` (last line; watchers gate on `tail -1`).
