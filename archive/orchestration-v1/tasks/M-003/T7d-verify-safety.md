# T7d — VERIFY LENS: safety (independent NON-PRODUCER, read-only). Best-of-N panel member #3 of 3.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any M-003 code. You reason OVER the authoritative evidence set produced by T7a — you do **NOT** re-run the heavy suite or acceptance scripts (a second concurrent heavy runner would contend on the shared workspace). Re-derive every judgment from GROUND TRUTH = the RAW artifact files + the source code. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only: do NOT edit any source/tests/scripts; do NOT git commit/push.

## Your dimension: SAFETY (is the patch-apply + network + credential posture actually safe, adversarially?)
Assume an adversarial GPT response. Your job is to find any way the code could (a) write outside the caller root, (b) mutate before full validation, (c) contact a non-loopback host, (d) read/log a credential, or (e) mutate by default without `--apply`. Prove each is CLOSED from ground truth.

## Read FIRST (in order)
1. This contract in full.
2. Evidence: `tmp/verify-m003/zipslip.txt` (the adversarial probe), `tmp/verify-m003/netguard.txt`, `tmp/verify-m003/grep_realsite.txt` (+ `grep_tests_scripts_forbidden.txt`), `orchestration/reports/M-003/verify-run.md` (provisional summary).
3. Apply/validation source: `src/ask_chatgpt/patch.py` — read `apply_patch` and its helpers END TO END: the validate-EVERYTHING-before-mutate ordering, the zip-slip containment (`realpath`/`commonpath`, no `extract`/`extractall`), symlink/`..`/absolute rejection, the staged-transaction + journal + rollback.
4. Network posture: `tests/conftest.py` (the autouse socket guard + Playwright route interception), `tests/test_network_guard.py`, `src/ask_chatgpt/driver.py` (real vs mock channel; that real stays fail-closed).
5. CLI posture: `src/ask_chatgpt/cli.py` + `tests/test_cli.py` (no-mutation default; `--apply` requires `--root`; `--apply`/`--dry-run` mutually exclusive).
6. Fixture: `tests/fixtures/mock_chatgpt/server.py`.

## REALIZED FACTS / DEVIATIONS to adjudicate
- **DEVIATION (b):** T4 EXTENDED `tests/fixtures/mock_chatgpt/server.py` to allow scripted custom changed/deleted patch bundles for the UC2 round-trip evidence. RULE whether this extension is loopback-ONLY and does NOT weaken the network guard or introduce any real-channel / non-loopback path. Read the actual server.py changes. State PASS/FAIL.
- T7a's probe already rejected absolute, `..`, zip-symlink, AND symlink-parent escapes with `PathEscapeError`, root/outside/canary unchanged. Re-derive this from `zipslip.txt` yourself (quote it) AND corroborate by reading the containment logic in `patch.py` — confirm the CODE (not just the probe) closes these (e.g. a probe that only tried easy cases would be insufficient; check the code handles them generally).

## Checks (each: PASS|FAIL + cite the raw evidence quote AND the source mechanism)
1. **Zip-slip closed (code + probe):** From `zipslip.txt`, quote the rejection of absolute / `..` / symlink-zip / symlink-parent and the `root_unchanged/outside_unchanged/canary_absent` proof. THEN read the containment in `patch.py` and confirm it uses resolved-path + `commonpath` (not string-prefix) and never calls `extract`/`extractall`. Both must hold.
2. **Validate-before-mutate proven:** Read `apply_patch` ordering. Confirm NO filesystem write happens before manifest+per-file SHA+byte+path validation completes; `dry_run=True` writes nothing; a LATE failure (2nd-file SHA mismatch) leaves the root byte-for-byte unchanged (cross-cite `test_patch.py::test_late_validation_failure...`). Quote the ordering.
3. **No credential/cookie/token/profile reads:** Grep `src/` for `cookie`, `token`, `credential`, `password`, `profile`, `storage_state`, `auth` and read each hit in context. Confirm none READ/STORE/LOG a credential/cookie/session-token/profile-content; the real channel uses a user profile path WITHOUT reading its contents. Record judgment + the hits you cleared.
4. **Loopback-only + network guard intact:** From `netguard.txt`, confirm the guard genuinely attempts a NON-loopback connect and raises `NETWORK BLOCKED`/`PlaywrightError`. Read `conftest.py` and confirm the autouse guard is in force for EVERY test and the route interception blocks non-loopback navigation. Confirm no test/script sets `channel="real"` (from `grep_tests_scripts_forbidden.txt`). 
5. **DEVIATION (b) adjudication:** Rule the mock server.py extension loopback-only + guard-neutral (quote the relevant server.py lines).
6. **CLI no-mutate default:** From `cli.py` + `test_cli.py`, confirm: default `--files` (no `--apply`) mutates NOTHING; `--dry-run` writes nothing; `--apply` requires explicit `--root`; `--apply`/`--dry-run` mutually exclusive; apply only ever goes through the validated `apply_patch`. Cite the test ids.
7. **Real channel fail-closed:** Confirm the real channel cannot be silently driven by any automated test/script (no `channel="real"` anywhere; selector_maps/real.json gating). Record how it is gated.

## Deliverable — `orchestration/reports/M-003/verify-safety.md` (≤180 lines)
- Header `LENS: safety`.
- One `CHECK <n>: PASS|FAIL` section each, with the raw-evidence quote AND the source mechanism.
- A line `V-SAFETY-VERDICT: PASS|FAIL` (FAIL if ANY escape/mutation/credential/non-loopback path is open OR deviation (b) weakens safety; explain).
- Telemetry v2: FIRST line `ESTIMATE: T7d <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:`/`END_TIMESTAMP:`.
- LAST line: `T7d-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. ZERO new pip deps. You run NOTHING heavy — you READ artifacts + source. Do NOT re-run the full suite or acceptance scripts — T7a is the sole heavy runner.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents (you are AUDITING for these, not collecting them — quote file:line references, never the would-be secret values).
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report only). Do NOT edit any source/tests/scripts. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY; never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T7d-STATUS: DONE|BLOCKED` as the LAST line.
