# MISSION-003-RESUME — finish bundles+CLI mission (manager headless-death #2, mid-T3)

**You are the relaunched manager for MISSION-003.** Read in order: (1) this file; (2) `orchestration/state/M-003-state.json` (the predecessor's resume-ready state + next-steps breadcrumb); (3) the original contract `orchestration/tasks/MISSION-003.md` (objective, task specs T4/T5/T7, SAFETY BLOCK, telemetry — all still binding). Your charter's **detached-session discipline** section was updated with the exact watch recipe — follow it literally (`--wait-seconds 480` foreground loops; NEVER background a watch; you are never re-invoked).

## What happened (record in handoff as REWORK-CAUSE: spec-gap, manager-death #2)

The first M-003 manager completed T1 (design, committed `5c30130`), T6 (real-site runbook, same commit), T2 (bundle-out, committed `f83c17e`), dispatched T3 (patch retrieval + apply), then backgrounded its watches and ended its turn expecting re-invocation — headless `claude -p` exits at turn end. Root cause: `pi-worker-watch.sh` default `--wait-seconds 1800` exceeds the manager Bash 600 s cap; the fix recipe is now in your charter.

## Ground truth at relaunch (2026-06-12; RE-VERIFY, don't trust)

- DONE + committed: `docs/bundle-protocol.md` (T1), `docs/runbooks/real-site-acceptance.md` (T6), `src/ask_chatgpt/bundle.py` + `tests/test_bundle_out.py` + errors extension (T2).
- **T3 RUNNING (or finished by now):** run dir `.pi-workers/pi-worker-20260612-024443-2923448-18983` (tmux session of the same name). Watch it to completion with the charter recipe; if its `status` file already exists, ingest its report immediately.
- PENDING: T4 (UC2 round-trip E2E + `scripts/accept_uc2.sh`), T5 (CLI + `[project.scripts]` entry + UC3 acceptance + `scripts/accept_uc3.sh`), T7a–e (verification panel per original contract), handoff, closeout commit.
- If T3 died without its deliverables/report: re-dispatch T3 once from its existing contract under `orchestration/tasks/M-003/` (REWORK-CAUSE: env-drift), watching per the recipe.

## Steps

1. Re-verify ground truth (`git log --oneline -5`, `tmux ls`, T3 run-dir `status`, `ls src/ask_chatgpt/ tests/ scripts/`).
2. Finish T3 (watch/ingest; verify its deliverables exist and its report ends `T3-STATUS: DONE`).
3. Execute T4, T5 (single-editor, serialized), then the T7 best-of-N panel (T7a evidence runner; T7b/c/d parallel lenses; T7e synthesis → `orchestration/reports/M-003/verify.md` with final `VERDICT:` line) — specs verbatim in the original contract.
4. Write `orchestration/handoffs/MISSION-003-handoff.json` per the original contract's handoff section, including BOTH rework legs if T3 needed re-dispatch, `ESTIMATE: M-003 120m` and derived `ACTUAL` from 2026-06-12T01:56:28 (first manager start) to your end, plus bare `ESTIMATE:`/`ACTUAL:` lines in your final log message.
5. Update `orchestration/state/M-003-state.json` to DONE; closeout commit `M-003:` prefix; NEVER push. Only then end your turn.
