# T7e — VERIFICATION SYNTHESIS (best-of-N synthesizer over the 3 lenses + the authoritative run). Independent NON-PRODUCER.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any M-003 code and you were NOT one of the three lens workers. Your job: read the authoritative evidence run (T7a) and the THREE independent lens reports (correctness, spec-conformance, safety), reconcile them into ONE verdict, and emit the mission's final PASS/FAIL. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only: do NOT edit source/tests/scripts; do NOT re-run the heavy suite; do NOT git commit/push.

## Read FIRST (in order)
1. This contract in full.
2. `orchestration/reports/M-003/verify-run.md` (T7a authoritative run; has `V1-VERDICT`).
3. `orchestration/reports/M-003/verify-correctness.md` (T7b; `V-CORRECTNESS-VERDICT`).
4. `orchestration/reports/M-003/verify-spec.md` (T7c; `V-SPEC-VERDICT` + honest-failure-mode table).
5. `orchestration/reports/M-003/verify-safety.md` (T7d; `V-SAFETY-VERDICT`).
6. If ANY lens raises a doubt that hinges on a specific raw artifact or source line, OPEN that artifact (`tmp/verify-m003/...`) or source file yourself and adjudicate from ground truth — do not just average the lenses.

## Method
- FILTER first: if any lens report is missing, empty, or did not emit its verdict line, note it as a dead candidate and either rely on the remaining lenses + your own ground-truth check, or (if a critical dimension is uncovered) declare that dimension UNVERIFIED.
- RECONCILE conflicts: if two lenses disagree, resolve from ground truth (the raw artifact/source), not by majority. Quote what you relied on.
- The mission objective being verified: UC2 (bundle-out → catalogue README → changed-files-only patch bundle → retrieve via download-primary + fenced-fallback → validate-before-mutate → zip-slip-safe apply → round-trip diff matches) and UC3 (`ask-chatgpt` CLI wrapping the public function; no-mutate default), ALL mock-proven on the loopback fixture, ZERO chatgpt.com contact, real-site halves operator-gated only.
- Adjudicate the two carried deviations explicitly: (a) upload `reject_size_type` → `UploadUnsupportedError` (local-cap breach → `OversizedPayloadError`); (b) the T4 mock `server.py` extension is loopback-only + guard-neutral. Each must be conformant/safe for an overall PASS.

## Deliverable — `orchestration/reports/M-003/verify.md` (≤150 lines)
- Header `LENS: synthesis`.
- A PER-DIMENSION table: `correctness | spec-conformance | safety | authoritative-run` → each `PASS|FAIL` with a one-line basis + the source lens report.
- A short RECONCILIATION section: any conflicts found and how you resolved them from ground truth; any dead/empty candidate noted; the adjudication of deviations (a) and (b).
- The single most important evidence quotes: the exact pytest summary (`119 passed...`), the UC2 round-trip diff-match booleans (both retrieval paths), the zip-slip rejection + no-escape proof, the netguard trip, the no-`channel="real"` grep judgment.
- A final `VERDICT: PASS|FAIL`. PASS only if ALL four dimensions pass, both deviations are conformant/safe, and no dimension is left UNVERIFIED. On FAIL: name the offending leg(s) and assign a `REWORK-CAUSE: <spec-gap|env-drift|frozen-file|dependency-rot|other>` per failing leg, plus the precise next action to fix it.
- Telemetry v2: FIRST line `ESTIMATE: T7e <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:`/`END_TIMESTAMP:`.
- LAST line: `T7-STATUS: PASS|FAIL` (mirror the VERDICT; this is the mission verification token the manager greps).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. ZERO new pip deps. You run NOTHING heavy — you READ reports + artifacts + source. Do NOT re-run the full suite or acceptance scripts.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report only). Do NOT edit any source/tests/scripts. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY; never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T7-STATUS: PASS|FAIL` as the LAST line.
