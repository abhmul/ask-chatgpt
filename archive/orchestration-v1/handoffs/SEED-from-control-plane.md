# SEED handoff — from the control-plane team (2026-06-11)

Written by the predecessor team lead at spawn. This is the pre-loaded context the operator asked to carry over. Treat every claim as re-verifiable from the archive; nothing here is a substitute for reading ground truth.

## Why this repo exists

The predecessor (`control-plane`) built a full research control plane: SQLite orchestrator daemon, 23-tool MCP surface exposed to ChatGPT via connector + tunnel, Level B Playwright browser adapter, quickstart UX. It was **built and independently verified end-to-end (mock-harness scope)** — see `VERIFICATION.md` §1–§10.1 in the archive — but the operator is archiving it in favor of a smaller, tool-shaped product: `ask_chatgpt()` + zip-bundle file exchange + CLI (this repo's `README.md`). The archive is prior art, not a template.

## Archive pointers (READ-ONLY: `/home/abhmul/Documents/weak-simplex-conjecture/`)

| Asset | Where | Why it matters here |
|---|---|---|
| Browser adapter (Playwright session controller, recovery, `ChatUIDriver` 8-method allowlist, selector-map pattern, seed-prompt builders) | `control-plane/src/control_plane/browser/` (+ `DESIGN.md` Phase-3 section) | The hard-won chatgpt.com automation layer: launch/attach to operator browser profile, mock-vs-real channel knobs, selector maps as data |
| Mock-ChatGPT loopback fixture | `control-plane/tests/` (phase3 mock chat fixture; `tests/fixtures/phase3_mock_selector_map.json`) | The pattern for E2E acceptance with ZERO chatgpt.com contact — reuse the idea, likely simplify |
| Real-ChatGPT operator runbooks (incl. connector/login research) | `control-plane/docs/runbooks/{phase2-chatgpt-acceptance,phase3-chatgpt-browser,mvp-demo}.md` | The operator-gated halves: real login, profile, consent flows; what was empirically proven on the real site |
| Quickstart UX (wizard, typed consent, preflight reason ordering, idempotent reruns, tunnel ownership) | `control-plane/src/control_plane/quickstart/` + `QUICKSTART.md` | Operator-UX bar: 1–2 commands with inline prompts, honest actionable failure messages — a standing operator rule (long runbooks were rejected as UX, 2026-06-10) |
| Verification record + acceptance-script pattern (artifacts + safety scans + raw-exit-code evidence) | `control-plane/VERIFICATION.md`, `control-plane/scripts/accept_*.sh` | The evidence discipline this operator expects |
| Mission history, handoffs, profiling | `orchestration/handoffs/MISSION-00{1..9}-handoff.json`, `orchestration/reports/PROFILING/mission-time-breakdown.md` | How problems were sliced, what blocked, where time went |

## DESIGN DECISION #1 (do this deliberately, first)

The predecessor's **Level B contract** allowed ONLY seeding prompts into the chat UI and **forbade DOM extraction** of responses — results flowed back through the MCP connector (GPT called tools). The new spec **requires** `ask_chatgpt(...) -> text` and retrieving a patch bundle, i.e. capturing assistant output. Options the new team must weigh (read the archive's Level B rationale in `DESIGN.md` / M-004 design first — fragility and account-risk reasoning):

1. DOM extraction via selector maps (predecessor has the selector-map infra but deliberately never used it for reads);
2. copy-button / clipboard automation;
3. file-download capture (for bundles, GPT can emit downloadable files; possibly cleaner than DOM text);
4. a connector-style callback channel (predecessor's approach — heavyweight, but proven; probably overkill here).

Empirical unknowns to verify operator-gated, never assumed: upload size/type limits for zip attachments; whether/when chatgpt.com offers file downloads from responses; session pinning via URL; model selection UI hooks.

## Environment gotchas (all bitten us; carried verbatim where general)

- `uv sync --all-groups` ALWAYS (bare `uv sync` silently uninstalls non-default dependency groups → collection-time `ModuleNotFoundError` that looks like a code regression).
- Serialize pytest runs in one tree; never assume any fixed port is free (the operator runs long-lived local daemons — use ephemeral ports); clean up only processes your tests start.
- Arch host: Playwright uses the ubuntu24.04 fallback chromium; keep channel/executable-path knobs.
- Acceptance scripts must never depend on another repo/team's mutable files — vendor provenance-recorded snapshots (predecessor's phase1/2 acceptance rotted when a peer team's backlog advanced).
- Read `~/Documents/vaults/agent-vault/agent-python/README` before bare `python`; the shared agent venv is read-only infra.
- Worker reports end with a single-token status line (`XXX-STATUS: DONE|BLOCKED`) — ops-runners gate on `tail -1`.

## Apparatus learnings (M-010 profiling, quantified)

- Orchestration latency dominates: predecessor's last mission was 7.44 h wall = 4.19 h active agents + 3.25 h nobody-running gaps. Keep chains alive (ops-runners with long-blocking watches, prompt lead ingest) before optimizing workers.
- Verification is deliberately ~33–41% of agent time — budget for it; every directive ends with independent non-producer verification.
- Rework was 33% of legs but only 23% of leg-time; its wall-cost is the gaps it creates. Classify rework causes (`REWORK-CAUSE:` codes, see charter).
- Estimate discipline works (last mission 1.49× its upper estimate; 2× is the flag threshold). Emit machine-readable `ESTIMATE:`/`ACTUAL:` lines (charter requires).
- Economics: pi (GPT 5.5 xhigh) workers carry token-heavy low-level work (operator has more GPT than Claude quota); focused single-problem contracts (pi errs on broad ones); Sonnet ops-runners for mechanical watch; `orchestration/bin/claude-orchestrator-watch.sh` exists if an Opus manager tier is ever warranted.

## Safety rules (transcribe into every worker contract — workers inherit nothing)

- Automated tests NEVER contact chatgpt.com/openai or any real tunnel service; local fakes + loopback only. Real-site interaction: operator-consented, operator-gated, on the operator's account, never in CI/tests.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents; none appear in code/commits/reports.
- Write only inside this repo (+ `tmp/`); the WSC repo is READ-ONLY archive (never its `archive/`/`human/`); never write `.claude/`/`.agents/`.
- NEVER `git push` (operator pushes). Commit only working slices. ESTIMATE BEFORE EXECUTE.

## Mesh

This team is registered `active` in `/home/abhmul/dev/wsc-mesh/teams.json` (inbox `inbox/ask-chatgpt/`); the `control-plane` team is `dormant`. Mesh protocol per the `team-lead` skill; message schema in the mesh root.
