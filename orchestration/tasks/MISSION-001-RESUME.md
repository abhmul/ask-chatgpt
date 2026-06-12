# MISSION-001-RESUME — finish the design-decision mission (predecessor manager died after dispatch)

**You are the relaunched manager for MISSION-001.** The original contract is `orchestration/tasks/MISSION-001.md` — READ IT FIRST; it carries the objective, deliverables, task plan (T2/T3 specs), archive pointers, SAFETY BLOCK, telemetry, and handoff requirements. This file carries only the resume state and deltas.

## What happened (record in handoff as REWORK-CAUSE: spec-gap)

The first manager authored worker contracts, dispatched T1a/T1b/T1c, then **ended its turn expecting to be "notified automatically" — and its headless `claude -p` process exited**. Nothing else went wrong. Your charter now carries the rule: NEVER end your turn while children run; hold FOREGROUND blocking watches. Obey it.

## Ground truth at relaunch (2026-06-11 ~22:55; re-verify, don't trust)

- Mission state (written by predecessor, resume-ready): `orchestration/state/M-001-state.json` — queue, run dirs, original `ESTIMATE: M-001 105m` (clock started 22:43:46).
- Worker contracts already exist: `orchestration/tasks/M-001/T1{a,b,c}-*.md`.
- **T1c DONE:** `orchestration/reports/M-001/angle-specfit.md` (9.7 KB) exists; verify its last line is `T1c-STATUS: DONE`.
- **T1a still running** (archive-fidelity lens): run dir `.pi-workers/pi-worker-20260611-224603-2717866-29152`, tmux `pi-worker-20260611-224603-2717866-29152`.
- **T1b still running** (channel-engineering lens): run dir `.pi-workers/pi-worker-20260611-224605-2718051-12488`, tmux `pi-worker-20260611-224605-2718051-12488`.

## Steps

1. Re-verify ground truth above (`tmux ls`, `ls orchestration/reports/M-001/`, the two run dirs' `status` files).
2. **Foreground-watch T1a and T1b to completion**: `bash .claude/skills/orchestration/references/pi-worker-watch.sh --watch <run-dir>` (check the script's `--help` for wait flags; ESTIMATE BEFORE EXECUTE — both workers are ~10 min into a 15–25 min estimate, so watches should return quickly). Loop until both `orchestration/reports/M-001/angle-archive.md` and `angle-channels.md` exist with `T1{a,b}-STATUS: DONE` as last line.
3. If a worker died WITHOUT its report: re-dispatch that single lens once from its existing contract in `orchestration/tasks/M-001/` (REWORK-CAUSE: env-drift), foreground-watch it.
4. Dispatch **T2 (synthesizer)** per MISSION-001.md §Task plan → `orchestration/reports/M-001/decision-memo.md`. Author its contract under `orchestration/tasks/M-001/` (self-contained; SAFETY BLOCK from MISSION-001.md transcribed VERBATIM; telemetry lines required; memo ≤ ~400 lines; must include the "what the mock fixture must support" section and the empirical-unknowns list). Foreground-watch.
5. Dispatch **T3 (independent verifier — a fresh pi worker, NOT the synthesizer)** per MISSION-001.md → `orchestration/reports/M-001/verify.md` with per-check verdicts and final `VERDICT: PASS|FAIL` line. Foreground-watch. On FAIL: revive T2 once with the findings (REWORK-CAUSE per cause), re-verify.
6. Write `orchestration/handoffs/MISSION-001-handoff.json` per MISSION-001.md §Handoff requirements, including: `REWORK-CAUSE: spec-gap` for the manager-death leg; `ESTIMATE: M-001 105m` and `ACTUAL: M-001 <minutes from 22:43:46 to now>m`; end timestamp (`date -Iseconds`). State plainly the DECISION IS NOT MADE — the memo is team-lead input.
7. Update `orchestration/state/M-001-state.json` as you go (artifacts → produced; queue statuses). Commit everything with prefix `M-001:` (stage only M-001 files + the reports; NEVER `git push`). Then — and only then — end your turn.

## Non-negotiables (from charter + original contract; transcribe into any NEW worker contract)

- NO network contact of any kind in this mission; never chatgpt.com/openai. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY; never its `archive/` or `human/` dirs. Write only inside this repo. No credentials. NEVER `git push`. Max 3 pi workers concurrent. Workers end reports with `T<ID>-STATUS: DONE|BLOCKED` as the last line.
