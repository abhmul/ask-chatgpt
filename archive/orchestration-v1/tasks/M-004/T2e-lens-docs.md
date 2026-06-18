# T2e — VERIFY LENS: docs / runbooks / decisions / telemetry (independent NON-PRODUCER, read-only). Best-of-N panel member 5 of 5.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code, and you are NOT the evidence runner (T1) nor any other lens. You reason OVER the committed source + docs + the authoritative T1 evidence — you do **NOT** re-run the heavy suite or acceptance scripts. Re-derive every judgment from GROUND TRUTH. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only.

## Your dimension: DOCS / RUNBOOKS / DECISIONS / TELEMETRY (does the documentation match what the code actually does, and are the operator-gated halves runnable as written?)

## Read FIRST (in order)
1. This contract in full.
2. `docs/DECISIONS.md` — esp. **D-001** (the channel-layering decision: DOM-primary default; bundles via download-primary + fenced-fallback). Read the full D-001 statement.
3. `docs/bundle-protocol.md` — the binding bundle/patch spec.
4. `docs/runbooks/real-site-acceptance.md` AND `docs/runbooks/observe-chatgpt-unknowns.md` — the operator-gated halves.
5. Code to cross-check against the docs: `src/ask_chatgpt/driver.py` (channel layering: DOM-primary default), `patch.py` (retrieval: download-primary + fenced-fallback; validate-before-mutate; zip-slip), `bundle.py` (catalogue), `cli.py` (the CLI surface the runbook's §UC3 must match — flags: positional `prompt`, `--prompt`, `--session`, `--model-settings`, `--files`, `--dirs`, `--out`, `--apply`, `--dry-run`, `--root`, `--channel {real,mock}` default real, `--base-url`, `--profile-path`, `--timeout`).
6. Telemetry: `orchestration/handoffs/MISSION-002-handoff.json` and `MISSION-003-handoff.json` (check for ESTIMATE/ACTUAL/REWORK-CAUSE conventions).

## Checks (each: PASS|FAIL + the quoted doc claim AND the source it must match)
1. **D-001 matches implementation:** State D-001's channel-layering decision verbatim, then confirm the code implements it: DOM-primary default for `-> text` (read `driver.py`); bundles use download-primary retrieval with a fenced-code fallback (read `patch.py`). FAIL if the decision and the code diverge.
2. **bundle-protocol.md matches code (sample 5 concrete claims):** Pick 5 falsifiable claims from `bundle-protocol.md` (e.g. catalogue README contents, changed-files-only patch shape, validate-before-mutate ordering, zip-slip rejection, the size/oversized cap, CLI no-mutate default). For EACH, quote the doc claim and confirm/deny against the actual code (file:line). FAIL if any sampled claim is contradicted by the code.
3. **Runbooks operator-runnable as written:** For BOTH runbooks, confirm every command referenced exists and every flag is real (cross-check `real-site-acceptance.md` §UC3 against the ACTUAL `cli.py` flag surface above — e.g. does it use real flags like `--channel real`, `--session`, `--files`, `--apply`, `--root`?). Confirm: prerequisites + explicit operator-consent gates are present; the operator account/credential ownership is stated; each proof is ~1–2 commands. FAIL if a runbook command/flag does not exist in the code, or a consent/prereq gate is missing.
4. **Telemetry conventions adopted:** Confirm the M-002 and M-003 handoffs carry the mission telemetry conventions (`ESTIMATE:` / `ACTUAL:` / `REWORK-CAUSE:` lines — REWORK-CAUSE only where rework occurred). Quote the lines you find. FAIL if the convention is absent.
5. **Mock-proven vs real-unproven labeled honestly everywhere user-facing:** Scan `README.md`, the runbooks, and any user-facing doc/CLI help: is it stated HONESTLY that the automated acceptance is mock-only (loopback) and the real-site proof is operator-gated and NOT yet automated? Flag ANY place that overclaims real-site verification. FAIL if anything implies the real site is automatically proven.

## Deliverable — `orchestration/reports/M-004/lens-docs.md` (≤200 lines)
- Header `LENS: docs/runbooks/decisions/telemetry`.
- One `CHECK <n>: PASS|FAIL` section each (1–5), with the quoted doc claim AND the source it must match.
- A line `T2e-VERDICT: PASS|FAIL` (FAIL if a doc/runbook claim is contradicted by code, a runbook is not runnable as written, the telemetry convention is absent, or anything overclaims real-site proof).
- Telemetry v2: FIRST line `ESTIMATE: T2e <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:`.
- LAST line: `T2e-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything is loopback/local. ZERO new pip deps. You run NOTHING heavy — you READ docs + source + handoffs. Do NOT re-run the full suite or acceptance scripts — T1 is the sole heavy runner. Do NOT invoke the `ask-chatgpt` CLI yourself (its default channel is real and you are NOT under the pytest guard) — read its flag surface from `cli.py`.
- This mission MUTATES NOTHING except your one report. NEVER edit or "fix" any source/tests/docs/scripts — REPORT defects instead (independence boundary).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY if strictly needed (you should not need to); never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T2e-STATUS: DONE|BLOCKED` as the LAST line.
