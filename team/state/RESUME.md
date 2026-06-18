# RESUME — team lead, `ask-chatgpt-dev` (team-lead-v2)

> **⚠️ ACTIVE DEVELOPMENT IS ON BRANCH `rewrite-v2`** (since 2026-06-18). `main` holds the approved spec baseline (`docs/REWRITE-SPEC.md`) + project files. To resume the rewrite: `git checkout rewrite-v2` and rehydrate team-state from there — the branch carries the live mission queue / handoff. `main`'s team-state is the baseline snapshot; the rewrite integrates back to `main` only via an operator-reserved merge after M8 verification.

Resume-ready handoff for a successor incarnation of the eternal team-lead role. You inherit **nothing** but what you read here and the files named below; re-verify every live claim from ground truth before building on it.

## Bring-up

You are the team lead (`team-lead-v2` skill) for team **`ask-chatgpt-dev`**, an eternal ROLE realized by ephemeral agents. Load the `team-lead-v2` skill and follow it. **FIRST read & obey** `.claude/skills/manager/references/agent-rigor.md`.

Then rehydrate, in order:
1. **Identity / charter:** `team/team.json` (owns, role_file=`team/charter.md`, mesh_path=null, ledger, ground_truth, shared_resources).
2. **This handoff:** `team/state/RESUME.md`.
3. **Live-state:** `team/state/live-state.json` (mission queue, blockers, last_verified — NEVER trust over ground truth).
4. **Durable lessons:** `/home/abhmul/.claude/projects/-home-abhmul-dev-ask-chatgpt/memory/MEMORY.md` (CC project memory — the single home; covers no-message-cap, prompt-design-adversarial-review, CDP-tab-isolation, real-paths-are-mock-shaped, etc.).
5. **Evidence log (authoritative when prose disagrees):** `team/evidence/` (v2, currently empty) and `archive/orchestration-v1/` (v1, stale reference).

## Current directive

**Rewrite the `ask_chatgpt` library from scratch** — archive the current implementation and rebuild it. Exact "what to support" + "how to rework" come from the operator and a **grill-me** session, distilled into a spec that is then appended to `team/charter.md`. Until that intake completes, the queue head **M0 (intake)** is blocked on the operator.

## Re-verify from ground truth before acting

The ledgers above are a CACHE and are provisionally stale. Before building on any live claim:
- **Installed-tool isolation (load-bearing safety):** confirm `~/.local/share/uv/tools/ask-chatgpt` is still an isolated copy and that **`stable`** has not moved (`git rev-parse stable`; expect it pinned, not on your work). Invariants: **never move `stable`; never `uv tool install/upgrade/reinstall`.** A second agent uses the installed tool.
- **Repo state:** `git status`, `git log --oneline -8`, current branch (work on `main`/feature branches, never `stable`).
- **Acceptance:** `uv run pytest` (mock; real_site deselected + gated on `ASK_CHATGPT_REAL=1`). Inspect output, not exit codes.
- **CDP (only if a real leg is needed):** `curl -s --max-time 5 http://127.0.0.1:9222/json/version`; the operator must have launched their signed-in Chromium. Inspect only tool-opened tabs.

Then continue the lead loop: maintain the mission queue → author self-contained manager contracts (copy charter constraints verbatim) → dispatch via the configured launch mechanism → smoke-check each handoff (shipment, not liveness) → ingest → report to operator → checkpoint. **Single team: do NOT load team-mesh.**

## Reserved actions (escalate in-session; do not self-decide)

Credentials/sudo/privileged installs; real external accounts/paywalled material; irreversible outbound effects (git push / merge-to-published); manual-compaction trigger; irreducible directive ambiguity; team create/retire. Everything else is autonomous against the directive's criteria.

## Open items at handoff (2026-06-18)

- Team v2 set up and **committed** (`team/` + `archive/orchestration-v1/`). Cold-start prompt for the grill-me session: `team/START-PROMPT.md`.
- `src/ask_chatgpt/driver.py` is dirty (uncommitted v1 M-011b WIP, deliberately NOT committed); to be superseded by the rewrite — operator to confirm keep/discard.
- Baseline `uv run pytest` on the current tree: 1 failed / 213 passed / 4 deselected — **moot** (library being rewritten).
- Awaiting operator's initial rework context in the new session, then grill-me.
