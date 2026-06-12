# T9·V1 — Authoritative INDEPENDENT verification run (reproduction + spec + acceptance-artifact inspection)

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any of this code. Re-derive every verdict from GROUND TRUTH (run it / inspect the produced files) — NEVER trust a prior report, a log line, or an exit code alone. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). This is the heavy-run lens; two other read-only lenses will reason over the output you produce.

## Read FIRST
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/tasks/MISSION-002.md` — the deliverables + acceptance you are checking against.
3. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` D-001 (for the conformance checks below).

## Checks (run each; record a PASS/FAIL verdict + the EVIDENCE for each)
1. **Fresh sync:** `uv sync --all-groups` (NOTE: `--all-groups` is mandatory). PASS if it completes without error. Record any warning.
2. **Full suite:** `uv run pytest -q` (estimate ~30s wall; state it). Capture the EXACT summary line and the count. PASS only if the run reports all-passed with ZERO failures/errors. If anything fails, record the failing test ids verbatim → FAIL.
3. **Acceptance script + ARTIFACT INSPECTION (not exit code alone):** run `bash scripts/accept_uc1.sh`. Then find the newest `tmp/accept-uc1-*/` it produced and OPEN `results.json` + `stdout.log`. Verify by INSPECTION: `overall` == `pass`; the two same-`session_identifier` steps used the SAME conversation ref and the conversation holds BOTH user prompts (continuity); a `model_settings` step succeeded; the honest-failure step raised a NAMED error (`LoginRequiredError`) with an actionable, credential-free message. QUOTE the inspected `overall` + the continuity evidence (conversation ref + the two prompts) + the error type/message in your report. PASS only if the artifacts themselves show this (do not rely on the shell exit code).
4. **Network guard trips on a deliberate violation:** `uv run pytest tests/test_network_guard.py -q` → PASS if green. Then OPEN `tests/test_network_guard.py` and confirm by reading that the violation-demo test genuinely attempts a NON-loopback TCP connect (e.g. to `93.184.216.34`) and asserts the guard raises `RuntimeError`/`NETWORK BLOCKED`. Record the test name + the asserted behavior. (Optionally also confirm the autouse socket guard is in `tests/conftest.py`.)
5. **Zero chatgpt.com contact in tests/scripts:** `grep -rn "chatgpt.com\|openai" tests/ scripts/` (ignore `.pyc`). Confirm every hit is a NON-navigation use (a constant assertion, a stored-URL string in a registry test, or a deliberate-block target) — NO test/script performs `page.goto`/HTTP to chatgpt.com, and NO test/script runs `channel="real"` / `launch_persistent_context`. Record the hits + your judgment → PASS/FAIL.
6. **D-001 default order (quick source check):** open `src/ask_chatgpt/readers.py`; confirm the default reader order is DOM-primary (DomReader before CopyButtonReader). PASS/FAIL.

## Deliverable — `orchestration/reports/M-002/verify-run.md`
- A header line `LENS: authoritative-run`.
- One section per check (1–6) with `CHECK <n>: PASS|FAIL` and the evidence (exact pytest summary line; the quoted acceptance `overall`+continuity+error; the network-guard test name; the grep judgment).
- A line `V1-VERDICT: PASS|FAIL` (FAIL if ANY check failed).
- Telemetry v2: `date -Iseconds` at START+END → literal `START_TIMESTAMP:`/`END_TIMESTAMP:` lines; `ESTIMATE: T9V1 <min>m`.
- End with `V1-STATUS: DONE` (or `BLOCKED` + reason) as the LAST line. ≤180 lines.

## SAFETY BLOCK (verbatim)
- NEVER contact chatgpt.com/openai/any external service. Everything you run is loopback-only (the suite + the acceptance script use channel="mock"). The ONLY permitted external download is chromium — ALREADY CACHED; download nothing; no sudo/apt/install/new deps.
- Never read/store/log credentials/cookies/tokens/profile contents. The acceptance `results.json` contains only synthetic prompts/outcomes.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report + the acceptance script's `tmp/` artifacts). Do NOT edit any source/tests. Archive READ-ONLY. Never write `.claude/`/`.agents/`.
- `uv run` from repo root ONLY; never bare `python`/`pip`; never the shared agent venv. NEVER `git push`/`git commit`.
