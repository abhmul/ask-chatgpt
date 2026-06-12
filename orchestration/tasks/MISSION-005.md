# MISSION-005 — Fix M-004 defects D1–D3 + independent re-verification → final VERDICT

**Mission type:** implement (small, single-editor legs, TDD/RED-first) + independent re-verification panel (N=3 + synthesis).
**Dispatched by:** ask-chatgpt team lead, 2026-06-12.
**Wall-clock estimate:** `ESTIMATE: M-005 75m` (flag 2× = 150 min).

## Context (binding inputs; read first)

1. `VERIFICATION.md` (repo root) + `orchestration/handoffs/MISSION-004-handoff.json` + `orchestration/reports/M-004/lens-{docs,safety,spec}.md` — the defects being fixed, with evidence pointers.
2. `docs/DECISIONS.md` D-001 — fail-closed posture is binding (D2 is a violation of it).
3. `orchestration/state/M-005-state.json` — create, keep resume-ready.

## Defects to fix (transcribed from M-004; re-verify each claim against the files before editing)

- **D1 (material):** `docs/runbooks/real-site-acceptance.md` references NON-EXISTENT CLI flags (`--profile`, `--patch-out`, `apply-patch`, `--bundle`) and wrong error class names (e.g. `PatchBundleMalformedError`) vs committed `cli.py`/`errors.py`. FIX: regenerate every command/flag/error-name in the runbook FROM GROUND TRUTH — `uv run ask-chatgpt --help` output (capture it into the worker report) + `src/ask_chatgpt/cli.py` + `src/ask_chatgpt/errors.py`. Cross-check ALL THREE UC sections + prerequisites against the real surface. The runbook must be operator-runnable as written (1–2 commands per proof, typed-consent gates, honest-failure interpretations preserved).
- **D2 (material):** `src/ask_chatgpt/driver.py` `start()` calls `page.goto(<chatgpt.com>)` BEFORE selector-map readiness is enforced when `channel="real"` + `profile_path` is set. FIX RED-FIRST: write the failing test FIRST — `channel="real"` with the all-empty `selector_maps/real.json` must raise the named fail-closed error BEFORE any navigation (assert via a goto-recording fake/monkeypatched page or driver hook that NO navigation was attempted; must not require network — the socket guard stays active). Then reorder `start()` so selector-map readiness is checked before navigation on the real channel. Mock channel behavior must be unchanged (full suite green). No other driver redesign (Occam).
- **D3 (minor):** CLI `--session` flag exercised by no test or acceptance. FIX: add a CLI test (subprocess or main(argv) call) proving `--session <id>` twice reaches the same conversation (continuity evidence, mirroring the library UC1 proof), and add a `--session` step to `scripts/accept_uc3.{sh,py}` with its evidence recorded in results.json.
- **D4 (minor, process — fix forward only):** in YOUR OWN handoff, carry `ESTIMATE`/`ACTUAL`/`REWORK-CAUSE` as literal top-level JSON fields AND bare `ESTIMATE:`/`ACTUAL:` lines in your final log message. Do NOT edit historical handoffs.

## Task plan

- T1 (single editor): fix D1. Conformance evidence in the report: paste `--help` output + a table runbook-command → exists-in-CLI yes/no, all yes.
- T2 (single editor, RED-first): fix D2. Report shows the RED run (test failing against pre-fix driver), then GREEN (full `uv run pytest` — all tests, not just the new one).
- T3 (single editor): fix D3. Report shows the new test + updated accept_uc3 results.json continuity evidence.
- T1/T2/T3 SERIALIZE (shared tree). Commit per leg or as one coherent slice, prefix `M-005:`.
- **T4 re-verification panel (independent — fresh workers, none of T1–T3; N=3 + synthesis):**
  - T4a evidence runner: fresh clean clone of HEAD into `tmp/verify-m005/clone` (same recipe as M-004 T1, including its greenlet/offline recovery note: if offline `uv sync` fails in the clone, rebuild the clone venv with network allowed for packages only and RECORD it); full `uv run pytest`; `accept_uc1/2/3.sh`; D2 regression demo (the new RED-test now green + grep that `goto` is post-check on the real path); capture raw to `tmp/verify-m005/`.
  - T4b docs-lens: D1 re-check from ground truth (every runbook command exists; error names match errors.py; operator-runnable); spot-re-check M-004 docs-lens PASS items still hold (D-001 conformance, bundle-protocol sampling).
  - T4c safety+spec lens: D2 re-check (fail-closed BEFORE navigation, evidenced); D3 re-check (--session test exists, non-vacuous, acceptance evidence); zip-slip + network-guard + credential greps re-confirmed on the new HEAD; spot-re-check 3 spec obligations from M-004 lens-spec.
  - T4d synthesis: update **`VERIFICATION.md`**: append an M-005 re-verification section (defect → fix commit → re-check evidence → verdict per defect), update the overall final `VERDICT:` line (PASS only if ALL defects verified fixed AND no regression in re-run evidence; else FAIL with exact remaining defects). Also `orchestration/reports/M-005/verify.md`. (T4b and T4c run PARALLEL after T4a; T4d after both.)
- Manager: handoff `orchestration/handoffs/MISSION-005-handoff.json` (STATUS; per-defect verdicts; telemetry per D4-fixed convention), state DONE, closeout commit. If final VERDICT is FAIL → STATUS PARTIAL + exact remaining defects + recommended next; fix nothing further without a new mission.

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; loopback/local only. Exception (T4a clone venv ONLY): if offline `uv sync --all-groups` fails in the fresh clone, package downloads from the standard Python index are permitted for the clone's venv rebuild — record it; NO other network use.
- The D2 test must prove fail-closed WITHOUT real navigation (fake/monkeypatched page; socket guard active). No test or script sets channel="real" against the real site; `selector_maps/real.json` stays the all-empty fail-closed template.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS. Serialize pytest. Ephemeral ports. Kill only your own processes. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End report with `T<ID>-STATUS: DONE|BLOCKED` last line.

## Telemetry + worker mechanics (unchanged from M-004 contract)

- Workers: `START_TIMESTAMP:`/`END_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T<ID> <min>m`; manager derives ACTUAL from run-dir metadata.
- pi via `bash .claude/skills/orchestration/references/pi-worker-watch.sh --wait-seconds 480 "<pointer>"`; FOREGROUND `--wait-seconds 480 --watch` loops (Bash timeout 600000 ms; you die at turn end; NEVER background a watch). Worker contracts under `orchestration/tasks/M-005/`, self-contained, report cap ~200 lines.
