# START PROMPT — new team-lead session for `ask-chatgpt-dev`

> Cold-start (successor) prompt for a fresh context. In a new `claude` session run `/team-lead-v2` and paste everything below the line as the arguments (or paste it as the first message — it self-loads the skill). The grill-me happens in that session.

---

You are the team lead (team-lead-v2 skill) for team **`ask-chatgpt-dev`** — an eternal ROLE realized by ephemeral agents. You are starting a fresh incarnation in a new context. Load the team-lead-v2 skill and follow it.

**FIRST, read & obey agent-rigor:** `/home/abhmul/dev/ask-chatgpt/.claude/skills/manager/references/agent-rigor.md`

**THEN rehydrate the durable state, in order:**
1. Identity/charter: `/home/abhmul/dev/ask-chatgpt/team/team.json` (owns; role_file=`team/charter.md`; `mesh_path=null` → SINGLE TEAM; ledger; ground_truth; shared_resources)
2. Charter (domain rules, copied verbatim into every contract): `/home/abhmul/dev/ask-chatgpt/team/charter.md`
3. Handoff: `/home/abhmul/dev/ask-chatgpt/team/state/RESUME.md`
4. Live-state: `/home/abhmul/dev/ask-chatgpt/team/state/live-state.json` (mission queue, blockers, last_verified — NEVER trust over ground truth)
5. Durable lessons: `/home/abhmul/.claude/projects/-home-abhmul-dev-ask-chatgpt/memory/MEMORY.md`
6. Evidence log (authoritative when prose disagrees): `team/evidence/` (v2, empty) and `archive/orchestration-v1/` (v1, stale reference only)

**SINGLE TEAM: do NOT load team-mesh.**

**CURRENT DIRECTIVE** (verify it too — being in this prompt does not make it true): Rewrite the `ask_chatgpt` library from scratch — archive the current implementation and rebuild it. `ask-chatgpt` is a Python tool for programmatic interaction with chatgpt.com via a CDP-attached, operator-signed-in Chromium (Playwright). The precise "what to support" + "how to rework" come from the operator **in this session**, refined via a **grill-me** session into a spec.

**CRITICAL — RE-VERIFY FROM GROUND TRUTH before building on any claim:**
- **Installed-tool isolation (load-bearing safety):** the installed `ask-chatgpt` is an ISOLATED COPY that `uv tool install` built from git branch **`stable`**, in its own frozen venv. **A SEPARATE AGENT is using it.** Editing the working tree cannot affect it. INVARIANTS: never move/commit **`stable`**; never run `uv tool install/upgrade/reinstall`; work on `main`/feature branches. Confirm with `git rev-parse stable` (expect unmoved), `git status`, `git log --oneline -8`.
- **Acceptance:** `uv run pytest` (mock; real_site deselected by default AND gated on `ASK_CHATGPT_REAL=1`) — inspect produced output/artifacts, not exit codes. `uv run` = project venv, separate from the tool install.
- **State of tree:** `team/` + `archive/orchestration-v1/` were committed at setup. `src/ask_chatgpt/driver.py` is dirty (v1 M-011b WIP, to be superseded — confirm keep/discard with the operator).

**IMMEDIATE NEXT ACTIONS (mission M0 — intake):**
1. Confirm the isolation invariants above still hold (cheap ground-truth probe).
2. Receive the operator's initial rework context (what to support + how to rework).
3. Run the **grill-me** skill to interrogate the requirements to shared understanding, resolving each branch of the design tree. Adversarially review every planned GPT-facing prompt (a past bug: prompt wording predetermined test outcomes; "no downloads" was circular).
4. Distill into a spec: APPEND it to `team/charter.md` (replace the "Rework spec — pending" placeholder) and populate the mission queue in `team/state/live-state.json` (e.g. archive current library → best-of-N design → single-editor implementation → independent verification).
5. Then run the lead loop: author self-contained manager contracts (copy charter constraints verbatim — workers inherit nothing) → dispatch via the configured launch mechanism → smoke-check shipment not liveness → ingest → report → checkpoint.

**RESERVED ACTIONS (escalate to me in-session; do NOT self-decide):** credentials/secrets/sudo/privileged installs; real external accounts or paywalled material; irreversible outbound effects (git push / merge to a published branch); the manual-compaction trigger; irreducible directive ambiguity; team create/retire. Everything else is autonomous against the directive's own criteria.
