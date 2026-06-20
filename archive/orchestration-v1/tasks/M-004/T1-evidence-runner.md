# T1 — AUTHORITATIVE verification evidence run (independent NON-PRODUCER). Produce the ONE evidence set the N=5 panel reasons over. CAPTURE ONLY — NO JUDGEMENT.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code. This is the FINAL directive-verification mission (M-004) — it verifies the ENTIRE README.md spec, not one slice. You are the SINGLE heavy runner; five read-only lenses (T2a–T2e) and a synthesizer (T3) reason OVER the evidence you produce, so capture EVERYTHING raw to `tmp/verify-m004/`. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd).

Your job is to RUN commands and CAPTURE raw outputs (stdout+stderr+exit codes+produced artifacts) — **NOT to judge PASS/FAIL.** Record exactly what happened (exit codes, exact summary lines, exception types, file states). The panel renders verdicts. Do NOT fix anything.

## Read FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/README.md` — the directive being verified (UC1/UC2/UC3 + acceptance shape + posture).
3. `/home/abhmul/dev/ask-chatgpt/orchestration/tasks/MISSION-004.md` — the mission (your T1 task = its "T1 evidence runner" bullet).
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/__init__.py` + `patch.py` (to find the exact apply entry point — `apply_patch`, `PatchBundle` — for the zip-slip probe; do NOT guess) and `cli.py` (to confirm the CLI flag surface for the no-apply demo).

## Setup
`mkdir -p tmp/verify-m004`. ESTIMATE BEFORE EXECUTE per heavy command. Tee ALL raw stdout+stderr into `tmp/verify-m004/<check>.txt`. The clean clone + a fresh `uv sync` + full pytest + 3 acceptance scripts is the heavy part — estimate ~10–25 min wall (fresh venv build + browser-less mock suite); state your estimate before running and DETACH nothing (you are already detached). Serialize all heavy runs (you are the only heavy runner).

## Checks — run each; record the COMMAND, EXIT CODE, the evidence file path, and a one-line RAW observation (a quoted summary line / exception type / file-state fact). NO PASS/FAIL.

### 1. Record tree state (main repo)
- `git -C /home/abhmul/dev/ask-chatgpt status --porcelain` and `git -C /home/abhmul/dev/ask-chatgpt log --oneline -15` → `tmp/verify-m004/git_state.txt`. Record whether the tree is clean (empty porcelain) and the HEAD commit hash.

### 2. CLEAN-CLONE REPRODUCIBILITY (the core new dimension — proves committed state alone reproduces, catching dirty-tree dependencies)
- Clone HEAD from the LOCAL path (file protocol) into the sandbox:
  `git clone /home/abhmul/dev/ask-chatgpt tmp/verify-m004/clone` → `tmp/verify-m004/clone_setup.txt`. (Local clone; `tmp/` is git-ignored so the clone is pristine HEAD. Record the cloned HEAD hash and confirm it equals the main-repo HEAD from check 1.)
- **All remaining heavy runs happen INSIDE the clone** (`cd tmp/verify-m004/clone` for those commands, or `uv run --project tmp/verify-m004/clone`; prefer running with the clone as cwd). The clone gets its OWN fresh `.venv`.
- `uv sync --all-groups` inside the clone (MANDATORY `--all-groups`; bare `uv sync` drops groups) → `tmp/verify-m004/clone_sync.txt`. Record success/fail + whether any external download occurred (none expected; chromium already installed user-wide).
- **FULL suite, serialized:** `uv run pytest -q` inside the clone → tee `tmp/verify-m004/clone_pytest.txt`. Record the EXACT final summary line verbatim (e.g. `NNN passed in M.MMs`) and the total count. If ANY test fails/errors, record every failing test id verbatim (do not judge — just capture).
- **UC1 acceptance:** `bash scripts/accept_uc1.sh` inside the clone → tee `tmp/verify-m004/clone_accept_uc1.txt`. Locate the newest `tmp/accept-uc1-*/results.json` (this will be UNDER the clone, i.e. `tmp/verify-m004/clone/tmp/accept-uc1-*/`); COPY it to `tmp/verify-m004/accept_uc1_results.json` and record its `overall` value + the session-continuity evidence fields verbatim.
- **UC2 acceptance (round-trip):** `bash scripts/accept_uc2.sh` inside the clone → tee `tmp/verify-m004/clone_accept_uc2.txt`. Copy the newest `tmp/accept-uc2-*/results.json` to `tmp/verify-m004/accept_uc2_results.json`; record `overall` AND the round-trip diff-match evidence verbatim (modified file changed / added file present / deleted file gone — whatever fields the artifact carries). Record both retrieval paths if the artifact distinguishes download-primary vs fenced-fallback.
- **UC3 acceptance:** `bash scripts/accept_uc3.sh` inside the clone → tee `tmp/verify-m004/clone_accept_uc3.txt`. Copy the newest `tmp/accept-uc3-*/results.json` to `tmp/verify-m004/accept_uc3_results.json`; record `overall` + the steps it exercised (prompt→stdout, `--out` file write, `--files … --dry-run` summary-without-mutation) verbatim.

### 3. DELIBERATE-VIOLATION DEMOS (all loopback/offline-safe; capture raw outcomes — the panel judges whether they are "closed")
- **(a) Network-guard trip:** `uv run pytest tests/test_network_guard.py -q` inside the clone → tee `tmp/verify-m004/netguard.txt`. Record the result line + the test ids. (The autouse socket guard is active under pytest.)
- **(b) Zip-slip apply attempt — you author the probe:** write `tmp/verify-m004/zipslip_probe.py` that builds malicious patch bundles exercising FOUR escape vectors — (i) ABSOLUTE path entry, (ii) `..` traversal entry, (iii) SYMLINK-escape entry, (iv) SYMLINK-PARENT escape entry — and calls the library apply entry point (`apply_patch` / `PatchBundle` — read `src/ask_chatgpt/patch.py` + `__init__.py` for the exact signature; do NOT guess) against a throwaway root `tmp/verify-m004/slip-root/`, with a canary path `tmp/verify-m004/slip-canary-OUTSIDE` that must NOT be created. For EACH vector PRINT raw observations: the exception type+message raised (or "NO EXCEPTION" if none), whether the canary exists, and whether `slip-root` is unchanged. Run `uv run python tmp/verify-m004/zipslip_probe.py` inside the clone → tee `tmp/verify-m004/zipslip.txt`. NEVER call `ZipFile.extract`/`extractall` yourself. (Capture the raw observations only — do not assert PASS.)
- **(c) CLI patch-apply WITHOUT the apply flag / guardrails (must not mutate) — OFFLINE-SAFE ONLY:**
  - **CRITICAL SAFETY:** the CLI default is `--channel real`, and a raw `ask-chatgpt` invocation is NOT protected by the pytest socket guard. NEVER invoke the CLI with the default channel. Only run: (i) pure argparse-error cases that exit before any channel action, and (ii) any invocation that could proceed MUST pass `--channel mock --base-url http://127.0.0.1:9` (port 9 = discard, nothing listening → loopback-only, cannot reach the real site).
  - Run `uv run ask-chatgpt --apply --dry-run --files /tmp/none` inside the clone → tee `tmp/verify-m004/cli_exclusive.txt`. Record exit code + stderr (expect an argparse mutual-exclusivity error, exit 2 — parse-time, no network).
  - Run `uv run ask-chatgpt --apply --files /tmp/none` (no `--root`) inside the clone → append to `tmp/verify-m004/cli_exclusive.txt`. Record exit code + stderr (expect an early "--apply requires --root"-style error before any channel action).
  - No-mutate default: create `tmp/verify-m004/cli-noapply-root/` with a canary file `canary.txt`; run `uv run pytest tests/test_cli.py -q` inside the clone → tee `tmp/verify-m004/cli_tests.txt` and record the result line + the test ids that concern no-mutation-default / `--apply` requires `--root` / `--apply`+`--dry-run` exclusivity. (These run under the pytest guard; they are the authoritative no-mutate evidence. Do NOT run the CLI default-mode against any non-loopback target.)

### 4. INVENTORY (capture-only)
- `ls -laR src tests scripts docs` (from the MAIN repo root) → `tmp/verify-m004/inventory.txt` (sizes + structure).
- `grep -rn 'chatgpt.com' src tests scripts` (from MAIN repo) → `tmp/verify-m004/grep_chatgptcom.txt`. Catalogue EACH hit (file:line + the line text) — do NOT judge; just list every occurrence so T2c can rule each inert.
- Also `grep -rn 'channel="real"\|channel=.real.\|launch_persistent_context\|storage_state' src tests scripts` → `tmp/verify-m004/grep_realchannel.txt` (list every hit; capture-only).

## Deliverable — `orchestration/reports/M-004/verify-run.md` (an EVIDENCE INDEX, ≤200 lines, NO PASS/FAIL judgement)
- Header line `LENS: authoritative-run (capture-only)`.
- A table / list: for EACH check above → `command | exit code | evidence file path | one-line RAW observation (quoted summary line / exception type / file-state fact)`.
- Quote verbatim: the clone HEAD hash (vs main HEAD), the exact `clone_pytest.txt` summary line + count, the three `overall` values, the UC2 diff-match evidence fields, the four zip-slip per-vector observations (exception type + canary-absent + root-unchanged), the netguard result, the two CLI guardrail exit codes + stderr, and the full list of `chatgpt.com` grep hits.
- An "EVIDENCE MANIFEST" section listing every file you wrote under `tmp/verify-m004/` with a one-line description, so the panel knows where to read.
- If a heavy command FAILED (non-zero / suite red), record it FACTUALLY with the verbatim failing ids — that is valid captured evidence, not your verdict.
- Telemetry v2: FIRST line `ESTIMATE: T1 <min>m`; `date -Iseconds` at START and END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- LAST line: `T1-STATUS: DONE` (all evidence captured) or `BLOCKED: <reason>`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything runs on loopback/local. The mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. The clean clone is from the LOCAL path `/home/abhmul/dev/ask-chatgpt` (file protocol) into `tmp/verify-m004/clone` ONLY. ZERO new pip deps. Chromium already installed — expect NO new external downloads.
- CLI HAZARD: `ask-chatgpt` defaults to `--channel real` and a non-pytest invocation has NO socket guard. NEVER invoke the CLI with the default channel. Use only argparse-error cases or `--channel mock --base-url http://127.0.0.1:9`.
- This mission MUTATES NOTHING outside `tmp/verify-m004/` and your one report `orchestration/reports/M-004/verify-run.md`. NEVER edit or "fix" any source/tests/docs/scripts — REPORT, never patch (independence boundary). Your zip-slip probe applies ONLY to a throwaway root under `tmp/verify-m004/`; never call `ZipFile.extract`/`extractall` yourself.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv (`~/.local/share/agent-python/.venv`).
- `uv run` from the relevant project root ONLY; never bare `python`/`pip`; `uv sync --all-groups` ALWAYS. Serialize pytest (you are the only heavy runner; T2a–T2e do NOT re-run). Ephemeral/discard ports only. Kill only processes your own run started. NEVER `git push`/`git commit`. ESTIMATE BEFORE EXECUTE.
- End your report with `T1-STATUS: DONE|BLOCKED` as the LAST line.
