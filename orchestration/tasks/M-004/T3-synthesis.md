# T3 — VERIFICATION SYNTHESIS (best-of-N synthesizer over the 5 lenses + the authoritative T1 run). Independent NON-PRODUCER. FINAL GATE.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code, you were NOT the evidence runner (T1), and you were NOT any of the five lens workers. Your job: read the authoritative evidence run (T1) and the FIVE independent lens reports, SPOT-CHECK 3 load-bearing claims directly against the raw T1 evidence, reconcile everything into ONE verdict, and emit the directive's final PASS/FAIL. This is the LAST mission verifying the ENTIRE README.md directive. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only: do NOT edit source/tests/scripts/docs; do NOT re-run the heavy suite; do NOT git commit/push.

## Read FIRST (in order)
1. This contract in full.
2. `README.md` (the directive) + `orchestration/tasks/MISSION-004.md` (the obligations + acceptance shape).
3. T1 authoritative evidence INDEX: `orchestration/reports/M-004/verify-run.md` (capture-only; points at `tmp/verify-m004/` raw artifacts).
4. The FIVE lens reports + their verdict tokens:
   - `orchestration/reports/M-004/lens-spec.md` — `T2a-VERDICT`
   - `orchestration/reports/M-004/lens-correctness.md` — `T2b-VERDICT`
   - `orchestration/reports/M-004/lens-safety.md` — `T2c-VERDICT`
   - `orchestration/reports/M-004/lens-failures.md` — `T2d-VERDICT`
   - `orchestration/reports/M-004/lens-docs.md` — `T2e-VERDICT`
5. For your spot-checks, OPEN the raw artifacts yourself (`tmp/verify-m004/clone_pytest.txt`, `accept_uc1_results.json`, `accept_uc2_results.json`, `accept_uc3_results.json`, `zipslip.txt`, `netguard.txt`) and/or the cited source lines — do NOT just average the lenses.

## Method
- FILTER first: if any lens report is missing, empty, or did not emit its `T2x-VERDICT` line, note it as a dead candidate and either rely on the remaining lenses + your own ground-truth check, or (if a critical dimension is left uncovered) declare that dimension UNVERIFIED (which blocks an overall PASS).
- RECONCILE conflicts from GROUND TRUTH, not by majority: if two lenses disagree, open the raw artifact / source line and adjudicate. Quote what you relied on.
- SPOT-CHECK exactly 3 load-bearing claims directly against T1 raw evidence (pick the 3 most consequential — e.g. the clean-clone pytest summary line; the UC2 round-trip diff-match fields; the zip-slip 4-vector rejection + no-escape). For each, quote the raw artifact and state whether it confirms the lens claim.
- The directive being verified (all of it): UC1 (`ask_chatgpt -> text`, session continuity, model selection where UI allows), UC2 (files/dirs → bundle with catalogue README → changed-files-only patch bundle → retrieve → validate-before-mutate → zip-slip-safe apply → round-trip diff matches), UC3 (`ask-chatgpt` CLI wrapping the function, no-mutate default), acceptance shape (automated E2E vs loopback mock + operator-gated real-site runbooks; tests NEVER contact chatgpt.com/openai), posture (library-first; operator owns credentials/profile/quota; D-001 channel layering; honest failure taxonomy). ALL automated proof is mock-only on the loopback fixture; the real-site halves are operator-gated runbooks, NOT automated.

## Deliverables (TWO files)

### A. `VERIFICATION.md` (repo ROOT) — the durable mission verdict
- Title + date + "independent non-producer verification of the full README.md directive (M-004)".
- **Per-obligation evidence table:** `obligation | evidence (file:line / test id / artifact line) | verdict (PASS|FAIL)`. Cover UC1, UC2, UC3, acceptance shape, posture.
- **The five lens verdicts** (one line each: lens → PASS|FAIL → one-line basis → source report).
- **Mock-proven vs real-site-unproven scope** — stated VERBATIM-honestly: exactly what the automated loopback suite proves, and that the real chatgpt.com behavior is NOT automatically verified and awaits the operator runbooks.
- **Operator runbook pointers:** where the operator runs the real-site halves (`docs/runbooks/real-site-acceptance.md`, `observe-chatgpt-unknowns.md`).
- **Your 3 spot-check quotes** (raw artifact → confirms/contradicts).
- A final `VERDICT: PASS|FAIL`. PASS only if all five lenses pass, every obligation is mapped to real evidence, no dimension is UNVERIFIED. On FAIL: list each exact defect, assign a `REWORK-CAUSE: <spec-gap|env-drift|frozen-file|dependency-rot|other>` per defect, and recommend a concrete fix mission (e.g. M-005) with the precise next action. Do NOT fix anything yourself.

### B. `orchestration/reports/M-004/verify.md` (≤150 lines) — panel mechanics summary
- Header `LENS: synthesis`.
- A PER-DIMENSION table: `spec | correctness | safety | failure-modes | docs | authoritative-run` → each PASS|FAIL with a one-line basis + the source lens report.
- A short RECONCILIATION section: conflicts found + how you resolved them from ground truth; any dead/empty candidate noted.
- The 3 spot-check quotes.
- Telemetry v2: FIRST line `ESTIMATE: T3 <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:`.
- LAST line: `M-004-VERDICT: PASS|FAIL` (mirror the VERIFICATION.md VERDICT; this is the mission token the manager greps).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything is loopback/local. ZERO new pip deps. You run NOTHING heavy — you READ reports + raw artifacts + source. Do NOT re-run the full suite or acceptance scripts — T1 was the sole heavy runner.
- This mission MUTATES NOTHING except your two report files (`VERIFICATION.md` at repo root + `orchestration/reports/M-004/verify.md`). NEVER edit or "fix" any source/tests/docs/scripts — on FAIL, REPORT the defect + recommend a fix mission (independence boundary).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY if strictly needed (you should not need to); never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End `orchestration/reports/M-004/verify.md` with `M-004-VERDICT: PASS|FAIL` as the LAST line.
