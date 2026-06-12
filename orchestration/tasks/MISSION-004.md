# MISSION-004 — Independent directive verification (final gate; non-producer; N=5 panel)

**Mission type:** verification ONLY. This mission MUTATES NOTHING except: `orchestration/reports/M-004/`, `VERIFICATION.md` (repo root), `orchestration/state/M-004-state.json`, `orchestration/handoffs/MISSION-004-handoff.json`, and the closeout commit. It fixes NOTHING — defects are reported, with a recommended fix mission, never patched here (independence).
**Dispatched by:** ask-chatgpt team lead, 2026-06-12.
**Wall-clock estimate:** `ESTIMATE: M-004 90m` (flag 2× = 180 min).

## Posture (binding)

You and your workers are NON-PRODUCERS verifying the ENTIRE directive from ground truth. Producer handoffs (`orchestration/handoffs/MISSION-002-handoff.json`, `MISSION-003-handoff.json`) and all reports are CLAIMS to re-derive, never evidence. Ground truth = the committed repo at HEAD + what actually happens when you run it. Best-of-N is the operator-emphasized default; this is the directive's most critical verification → N=5 panel with DISTINCT dimensions over ONE authoritative evidence run.

## The directive being verified (README.md, binding; re-read the file itself)

1. UC1: `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` — session continuity (same identifier → same conversation), model selection where the UI allows, returns assistant response text.
2. UC2: caller passes files/dirs → tool zips a bundle including a catalogue README for GPT (what's inside, how to respond) → GPT asked to return a patch bundle (changed files ONLY) → tool retrieves and can apply locally. Round-trip: bundle out → (mock) GPT edits → patch back → applied → diff matches expectation.
3. UC3: `ask-chatgpt` CLI wrapping the function (prompt, session, file args, output to stdout/file).
4. Acceptance shape: each UC has automated E2E acceptance vs a local mock ChatGPT (loopback; automated tests NEVER contact chatgpt.com/openai) + an operator-gated runbook half for the real site. Honest failure modes named actionably: login required, session not found, upload/download unsupported, response truncated (+ the bundle failure taxonomy).
5. Posture: library-first; operator owns credentials/profile/quota (tool never touches credentials); D-001 (docs/DECISIONS.md) governs channel layering.

## Task plan

- **T1 evidence runner (ONE worker; produces the single authoritative evidence set under `tmp/verify-m004/`):**
  1. `git -C /home/abhmul/dev/ask-chatgpt status --porcelain` (record tree state) + `git log --oneline -15`.
  2. **Clean-clone reproducibility:** `git clone /home/abhmul/dev/ask-chatgpt tmp/verify-m004/clone` (HEAD only) → inside the clone: `uv sync --all-groups`; full `uv run pytest -q` (serialized); `bash scripts/accept_uc1.sh`, `accept_uc2.sh`, `accept_uc3.sh`. This proves the committed state alone reproduces everything (catches dirty-tree dependencies).
  3. Deliberate-violation demos (in the clone): the network-guard violation test path; a zip-slip patch application attempt; `ask-chatgpt` CLI patch apply WITHOUT the apply flag (must not mutate). Capture raw outputs.
  4. Inventory: `ls -laR` of src/, tests/, scripts/, docs/ (sizes); `grep -rn 'chatgpt.com' src/ tests/ scripts/` (each hit catalogued).
  5. Everything captured raw (stdout+exit codes+results.json files) to `tmp/verify-m004/`. NO judgement — capture only. ESTIMATE BEFORE EXECUTE per command.
- **T2a–T2e panel (FIVE workers, PARALLEL, read-only over T1 evidence + the repo; each writes `orchestration/reports/M-004/lens-<name>.md` with per-check verdicts + `<ID>-VERDICT: PASS|FAIL` + `<ID>-STATUS:` last line):**
  - T2a **spec-conformance**: map EVERY obligation sentence above to concrete evidence (file:line, test name, acceptance artifact line). Anything unmapped = FAIL with the gap named.
  - T2b **correctness/reproduction**: did the clean clone actually reproduce green from committed state alone? Are the acceptance artifacts internally consistent (continuity evidence, diff_match_evidence)? Are key tests non-vacuous (sample ~8 tests across UC1/UC2/UC3: would they fail if the behavior broke)?
  - T2c **safety/security**: network guard proven to trip; zero non-loopback contact possible in tests; every `chatgpt.com` occurrence inert (constant/literal/guard); zip-slip matrix (absolute, `..`, symlink, symlink-parent) rejected with validate-before-mutate proven; no credential/cookie/token/profile reads anywhere (grep + driver inspection); CLI no-mutate default + `--apply`/`--dry-run` exclusivity; real channel fail-closed (`selector_maps/real.json` empty template; no test sets channel="real").
  - T2d **honest failure modes**: each named failure (login required, session not found, model unavailable, response truncated, selector unavailable, upload unsupported, download unsupported, patch malformed, hash/byte mismatch, oversized, path-escape) is raisable, actually raised by a test or acceptance step, and its message is actionable + credential-free.
  - T2e **docs/runbooks/decisions/telemetry**: `docs/DECISIONS.md` D-001 layering matches the implementation (DOM-primary default, download-primary + fenced-fallback bundles); `docs/bundle-protocol.md` matches what the code does (sample 5 protocol claims); both runbooks are operator-runnable as written (commands exist, flags real — cross-check `real-site-acceptance.md` §UC3 against the actual CLI surface; prerequisites/consent gates explicit; 1–2 commands per proof); mission telemetry conventions adopted (ESTIMATE/ACTUAL/REWORK-CAUSE present in M-002/M-003 handoffs); mock-proven vs real-unproven labeled honestly everywhere user-facing.
- **T3 synthesis (fresh worker):** read all five lens reports + spot-check 3 load-bearing claims directly against T1 evidence → write **`VERIFICATION.md` (repo root)**: per-obligation evidence table (obligation | evidence | verdict), the five lens verdicts, mock-proven vs real-site-unproven scope (verbatim-honest), operator runbook pointers, and final `VERDICT: PASS|FAIL`. Also `orchestration/reports/M-004/verify.md` summarizing panel mechanics. Conflicts reconciled with justification; any FAIL carries the exact defect + recommended fix mission.
- Manager: handoff + state DONE + closeout commit `M-004:`. If overall FAIL → STATUS PARTIAL, defect list, recommend M-005 fix mission; do NOT fix.

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- NEVER contact chatgpt.com/openai or any external network service; everything runs on loopback/local. The clean clone is from the LOCAL path `/home/abhmul/dev/ask-chatgpt` (file protocol), into `tmp/verify-m004/clone` only.
- This mission mutates NOTHING outside `tmp/verify-m004/`, `orchestration/reports/M-004/`, `VERIFICATION.md`, `orchestration/state/M-004-state.json`, `orchestration/handoffs/MISSION-004-handoff.json`. Never "fix" product code/tests/docs — report defects instead.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS. Serialize pytest. Ephemeral ports only. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report with `T<ID>-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 + worker mechanics (unchanged)

- Workers: `START_TIMESTAMP:`/`END_TIMESTAMP:` via `date -Iseconds` + `ESTIMATE: T<ID> <min>m`; manager derives ACTUAL from run-dir metadata (pi minute self-reports are hallucinated).
- pi via `bash .claude/skills/orchestration/references/pi-worker-watch.sh --wait-seconds 480 "<pointer>"`, FOREGROUND `--wait-seconds 480 --watch` loops per your charter (Bash timeout 600000 ms; you die at turn end; NEVER background a watch). No pi concurrency cap — T2a–T2e run as five parallel workers.
- Worker contracts under `orchestration/tasks/M-004/`, self-contained, report cap ~250 lines.

## Handoff (`orchestration/handoffs/MISSION-004-handoff.json`)

Rigor protocol; STATUS + final VERDICT near top; per-lens verdicts; artifacts + trust; defects (if any) with exact repro + recommended fix mission; bare `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:` lines in your final log message. This is the directive's LAST mission — state plainly whether the automated half of the directive is achieved, and that real-site halves await the operator runbooks.
