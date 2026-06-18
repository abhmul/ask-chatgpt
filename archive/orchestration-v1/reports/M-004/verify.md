ESTIMATE: T3 20m
START_TIMESTAMP: 2026-06-12T05:56:42-05:00
END_TIMESTAMP: 2026-06-12T05:58:50-05:00
LENS: synthesis

## Per-dimension panel table

| dimension | verdict | basis | source |
|---|---|---|---|
| spec | FAIL | UC1/UC2 and most UC3 map to evidence, but CLI `--session` is not exercised and the real-site runbook is stale against the actual CLI. | `orchestration/reports/M-004/lens-spec.md:40` |
| correctness | PASS | Clean clone full suite and UC1/UC2/UC3 acceptance artifacts are green and internally consistent. | `orchestration/reports/M-004/lens-correctness.md:40`; `orchestration/reports/M-004/verify-run.md` |
| safety | FAIL | Zip-slip, network guard, no-mutate default, and mock-only tests pass, but real channel can navigate to `chatgpt.com` before empty selector enforcement when a profile path is supplied. | `orchestration/reports/M-004/lens-safety.md:35` |
| failure-modes | PASS | The named failure taxonomy is implemented, exercised by T1-backed tests/artifacts, actionable, and credential-free. | `orchestration/reports/M-004/lens-failures.md:25` |
| docs | FAIL | D-001 and bundle protocol align, but real-site runbook commands/error names are stale and prior handoffs lack literal telemetry lines. | `orchestration/reports/M-004/lens-docs.md:32` |
| authoritative-run | PASS | T1 captured `119 passed`, UC1/UC2/UC3 `overall=pass`, network guard `2 passed`, zip-slip four-vector rejection, and CLI guardrails. | `orchestration/reports/M-004/verify-run.md` |

## Reconciliation

All five lens reports were present, non-empty, and had verdict tokens; no dead candidate. The apparent conflict is scope, not factual disagreement: correctness/failure-modes prove the mock functional core is green, while spec/safety/docs identify uncovered or stale obligations. Ground truth confirms final FAIL: `src/ask_chatgpt/cli.py:63,102` implements `--session` but `tests/`, `scripts/`, and `tmp/verify-m004/accept_uc3_results.json` do not exercise it; `docs/runbooks/real-site-acceptance.md:166,171,180-188,241,263` uses CLI flags/subcommands absent from `src/ask_chatgpt/cli.py:100-114`; `src/ask_chatgpt/driver.py:75-90,270-276,289-291` can reach `page.goto(REAL_BASE_URL)` before an empty `real.json` selector lookup; exact-token grep found no `ESTIMATE:`, `ACTUAL:`, or `REWORK-CAUSE:` lines in the M-002/M-003 handoffs. Automated proof remains mock-only; real-site behavior is unproven until repaired operator runbooks are run with consent.

## Three spot-check quotes

1. `tmp/verify-m004/clone_pytest.txt:4-5`: `119 passed in 43.60s` and `EXIT_CODE: 0` — confirms clean-clone full-suite green.
2. `tmp/verify-m004/accept_uc2_results.json:54-62,114-120,184-192,244-250`: `"source": "download"`, `"source": "fenced"`, `"modified_matches": true`, `"added_matches": true`, `"deleted_absent": true`, `"overall_diff_matches": true` — confirms both UC2 mock round trips and expected diff.
3. `tmp/verify-m004/zipslip.txt:24-28`: `VECTOR absolute_path | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`; `VECTOR dotdot_traversal | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`; `VECTOR symlink_final | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`; `VECTOR symlink_parent | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`; `EXIT_CODE: 0` — confirms zip-slip closed for the four-vector probe.

## Final defects for M-005

- Real-site runbook stale vs CLI/error names. REWORK-CAUSE: env-drift. Fix: update runbook commands/error names or implement the documented CLI surface.
- Real channel not pre-navigation fail-closed with empty selectors plus profile path. REWORK-CAUSE: spec-gap. Fix: preflight real selector-map readiness before launch/goto and test no navigation attempt.
- UC3 `--session` not tested or accepted through CLI. REWORK-CAUSE: spec-gap. Fix: add CLI test and UC3 acceptance step proving continuity through `--session`.
- Telemetry literal lines missing from prior handoffs. REWORK-CAUSE: frozen-file. Fix: backfill/adopt grep-visible `ESTIMATE:`, `ACTUAL:`, `REWORK-CAUSE:` lines.

M-004-VERDICT: FAIL