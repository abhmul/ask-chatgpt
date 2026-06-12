# T7a — AUTHORITATIVE verification evidence run (independent NON-PRODUCER). Produce the ONE evidence set the panel reasons over.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any M-003 code. Re-derive every verdict from GROUND TRUTH — run it / inspect produced files — NEVER trust a prior report, a log line, or an exit code alone. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). This is the heavy-run lens; three read-only lenses (T7b/c/d) will reason over the evidence you produce, so capture EVERYTHING to `tmp/verify-m003/`.

## Read FIRST
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/tasks/MISSION-003.md` — the deliverables + acceptance you check against (UC2 round-trip diff-matches; UC3 CLI; honest failure modes).
3. `/home/abhmul/dev/ask-chatgpt/docs/bundle-protocol.md` — the binding spec (esp. §5 validate-before-mutate, §6 zip-slip-safe apply, §9 adversarial matrix, §11 CLI no-mutate default).
4. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` D-001.

## Setup
`mkdir -p tmp/verify-m003`. Run each check below; tee ALL raw stdout+stderr into `tmp/verify-m003/<check>.txt`. Estimate ~2–3 min wall for the suite; state estimates before long runs.

## Checks (run each; record PASS/FAIL + the evidence path)
1. **Fresh sync:** `uv sync --all-groups` (MANDATORY `--all-groups`) → `tmp/verify-m003/sync.txt`. PASS if no error.
2. **FULL suite (UC1 regression INCLUDED):** `uv run pytest -q` → tee `tmp/verify-m003/pytest.txt`. Capture the EXACT summary line + count. PASS only if all-passed, ZERO failures/errors. Any failure → record the failing test ids verbatim → FAIL.
3. **UC1 acceptance + ARTIFACT INSPECTION:** `bash scripts/accept_uc1.sh` → tee `tmp/verify-m003/accept_uc1.txt`. Find the newest `tmp/accept-uc1-*/` and OPEN its `results.json`; verify by INSPECTION `overall == pass`. Quote it.
4. **UC2 acceptance + ROUND-TRIP DIFF INSPECTION:** `bash scripts/accept_uc2.sh` → tee `tmp/verify-m003/accept_uc2.txt`. Find the newest `tmp/accept-uc2-*/`, OPEN `results.json`; verify `overall == pass` AND that the recorded evidence shows the **applied tree diff MATCHES expectation** (modified file changed, added file present, deleted file gone). Quote the diff-match evidence. PASS only if the artifacts themselves show it (not the exit code alone).
5. **UC3 acceptance + INSPECTION:** `bash scripts/accept_uc3.sh` → tee `tmp/verify-m003/accept_uc3.txt`. Find the newest `tmp/accept-uc3-*/`, OPEN `results.json`; verify `overall == pass` (a prompt→stdout call, an `--out` file write, and a `--files … --dry-run` diff-summary-without-mutation step). Quote it.
6. **DELIBERATE zip-slip attempt MUST fail safely (adversarial safety probe — you author it):** write `tmp/verify-m003/zipslip_probe.py` that constructs malicious patch bundles — one with an ABSOLUTE path entry, one with a `..` traversal entry, one with a SYMLINK-escape entry — and calls the library's `apply_patch(...)` against a throwaway root under `tmp/verify-m003/slip-root/`. It MUST raise `PathEscapeError` (or the §8 path-escape error) for EACH, and you MUST assert that NO file was created/modified OUTSIDE the root (check a canary path outside root does NOT exist, and the root is unchanged). Run via `uv run python tmp/verify-m003/zipslip_probe.py` → tee `tmp/verify-m003/zipslip.txt`. PASS only if all three are rejected AND nothing escaped. (If the public API names differ, read `src/ask_chatgpt/__init__.py` + `patch.py` to find the apply entry point — do not guess.)
7. **DELIBERATE network-guard violation MUST trip:** `uv run pytest tests/test_network_guard.py -q` → tee `tmp/verify-m003/netguard.txt`; PASS if green. Then OPEN `tests/test_network_guard.py` and confirm by reading that it genuinely attempts a NON-loopback TCP connect and asserts the guard raises `RuntimeError`/`NETWORK BLOCKED`. Record the test name + asserted behavior.
8. **Zero chatgpt.com contact in tests/scripts (quick grep):** `grep -rn "chatgpt.com\|openai" tests/ scripts/ src/` (ignore `.pyc`). Confirm every hit is a NON-navigation use (constant/assertion/blocked-target), and NO test/script runs `channel="real"`/`launch_persistent_context`. Tee to `tmp/verify-m003/grep_realsite.txt`. Record judgment.

## Deliverable — `orchestration/reports/M-003/verify-run.md`
- Header line `LENS: authoritative-run`.
- One section per check (1–8): `CHECK <n>: PASS|FAIL` + the evidence (exact pytest summary; quoted `overall`s; the UC2 diff-match quote; the zip-slip rejection + no-escape proof; the netguard test name + behavior; the grep judgment) + the `tmp/verify-m003/<check>.txt` path.
- A line `V1-VERDICT: PASS|FAIL` (FAIL if ANY check failed).
- Telemetry v2: FIRST line `ESTIMATE: T7a <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:`/`END_TIMESTAMP:`.
- End with `T7a-STATUS: DONE` (or `BLOCKED` + reason) as the LAST line. ≤200 lines.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). Everything you run is loopback-only. ZERO new pip deps.
- PATCH APPLY SAFETY: your zip-slip probe applies ONLY to a throwaway root under `tmp/verify-m003/`; it proves the library rejects escapes and writes nothing outside. Never call `ZipFile.extract`/`extractall` yourself.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report + the `tmp/verify-m003/` + acceptance scripts' `tmp/` artifacts). Do NOT edit any source/tests. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY; never bare `python`/`pip`; `uv sync --all-groups` ALWAYS. Serialize the runs (you are the only heavy runner; T7b/c/d do NOT re-run). Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T7a-STATUS: DONE|BLOCKED` as the LAST line.
