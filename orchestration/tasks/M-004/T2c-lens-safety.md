# T2c — VERIFY LENS: safety / security (independent NON-PRODUCER, read-only). Best-of-N panel member 3 of 5.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any ask-chatgpt code, and you are NOT the evidence runner (T1) nor any other lens. You reason OVER the authoritative evidence set produced by T1 — you do **NOT** re-run the heavy suite or acceptance scripts. Re-derive every judgment from GROUND TRUTH = the RAW T1 artifacts + the source code. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only.

## Your dimension: SAFETY / SECURITY (adversarial)
Assume an adversarial GPT response and an adversarial caller. Prove each of these is CLOSED from ground truth (code + T1 evidence): (a) no write outside the caller root; (b) no mutation before full validation; (c) no non-loopback contact possible in tests; (d) no credential/cookie/token/profile read anywhere; (e) CLI does not mutate by default; (f) the real channel cannot be silently driven by automation (fail-closed).

## Read FIRST (in order)
1. This contract in full.
2. T1 evidence: `tmp/verify-m004/zipslip.txt` (4-vector probe: absolute / `..` / symlink / symlink-parent), `tmp/verify-m004/netguard.txt`, `tmp/verify-m004/grep_chatgptcom.txt` (every `chatgpt.com` hit), `tmp/verify-m004/grep_realchannel.txt`, `tmp/verify-m004/cli_exclusive.txt` + `cli_tests.txt`, and `orchestration/reports/M-004/verify-run.md`.
3. Apply/validation source: `src/ask_chatgpt/patch.py` — read `apply_patch` + helpers END TO END: validate-EVERYTHING-before-mutate ordering; zip-slip containment via RESOLVED path + `commonpath` (NOT string-prefix); absolute/`..`/symlink/symlink-parent rejection; staged-transaction / journal / rollback; that it never calls `ZipFile.extract`/`extractall`.
4. Network posture: `tests/conftest.py` (autouse socket guard + any Playwright route interception — confirm it is in force for EVERY test), `tests/test_network_guard.py`, `src/ask_chatgpt/driver.py` (real vs mock channel; real stays fail-closed).
5. CLI posture: `src/ask_chatgpt/cli.py` + `tests/test_cli.py`.
6. Real-channel gating: `src/ask_chatgpt/selector_map.py` + `src/ask_chatgpt/selector_maps/real.json` (all-empty template) + `mock.json`. Fixture: `tests/fixtures/mock_chatgpt/server.py`.

## CRITICAL FACT TO ADJUDICATE (do not miss)
The CLI flag `--channel` DEFAULTS to `"real"` (see `cli.py`). A raw `ask-chatgpt` invocation is NOT protected by the pytest autouse socket guard (that guard only exists inside pytest). So you MUST verify the real channel is **fail-closed by construction**: with `real.json` selectors all empty, the driver/selector layer must raise a NAMED error (e.g. `SelectorUnavailableError`) BEFORE any non-loopback navigation — i.e. the default real channel cannot reach chatgpt.com without operator-provided selectors. Confirm this from `driver.py` + `selector_map.py` + `real.json`. Also confirm NO automated test or acceptance script invokes the CLI/driver with `channel="real"` against a live target (every test passes `channel="mock"` + a loopback `--base-url`). State PASS/FAIL explicitly.

## Checks (each: PASS|FAIL + cite the raw-evidence quote AND the source mechanism)
1. **Zip-slip closed (code + probe):** From `zipslip.txt`, quote the per-vector outcome for ALL FOUR vectors (exception type + canary-absent + root-unchanged). THEN read the containment in `patch.py` and confirm it uses resolved-path + `commonpath` (not string-prefix) and never `extract`/`extractall`. BOTH must hold (a probe that only tried easy cases is insufficient — confirm the CODE closes them generally).
2. **Validate-before-mutate proven:** Read `apply_patch` ordering; confirm NO filesystem write before manifest + per-file SHA/byte + path validation completes; `dry_run=True` writes nothing; a LATE failure (e.g. 2nd-file mismatch) leaves the root byte-for-byte unchanged. Cross-cite the relevant `tests/test_patch.py` id. Quote the ordering.
3. **No credential/cookie/token/profile reads:** Grep `src/` for `cookie`, `token`, `credential`, `password`, `profile`, `storage_state`, `auth`, `secret` and read each hit IN CONTEXT. Confirm none READ/STORE/LOG a credential/cookie/session-token/profile-content; the real channel takes a `--profile-path` but passes it through WITHOUT inspecting its contents. Record judgment + the file:line hits you cleared (quote file:line, NEVER any would-be secret value).
4. **Loopback-only + network guard intact:** From `netguard.txt`, confirm the guard genuinely attempts a NON-loopback connect and raises a block (`NETWORK BLOCKED` / `RuntimeError` / `PlaywrightError`). Read `conftest.py`: confirm the autouse guard applies to EVERY test and any route interception blocks non-loopback navigation. Quote the guard mechanism.
5. **Every `chatgpt.com` occurrence inert:** From `grep_chatgptcom.txt`, classify EACH hit (constant / literal / assertion / blocked-target / comment) and confirm NONE is a live navigation in code that automated tests reach. List each file:line + classification.
6. **CLI no-mutate default + flag exclusivity:** From `cli.py` + `test_cli.py` + `cli_exclusive.txt` + `cli_tests.txt`: default (no `--apply`) mutates NOTHING; `--dry-run` writes nothing; `--apply` requires explicit `--root`; `--apply`/`--dry-run` mutually exclusive; apply ONLY ever goes through the validated `apply_patch`. Quote the two CLI guardrail exit codes from `cli_exclusive.txt` and the governing test ids.
7. **Real channel fail-closed (THE critical fact above):** Confirm `real.json` selectors are all empty and that empty selectors force a named pre-navigation failure; confirm no `channel="real"` live invocation exists in tests/scripts (from `grep_realchannel.txt`). State how the real channel is gated.

## Deliverable — `orchestration/reports/M-004/lens-safety.md` (≤200 lines)
- Header `LENS: safety/security`.
- One `CHECK <n>: PASS|FAIL` section each (1–7), with the raw-evidence quote AND the source mechanism.
- A line `T2c-VERDICT: PASS|FAIL` (FAIL if ANY escape / pre-validation-mutation / credential-read / non-loopback / default-mutation / real-not-fail-closed path is open; explain precisely).
- Telemetry v2: FIRST line `ESTIMATE: T2c <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:`.
- LAST line: `T2c-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- NEVER contact chatgpt.com/openai or any external network service; everything is loopback/local. The mock fixture binds loopback (127.0.0.1) ONLY. ZERO new pip deps. You run NOTHING heavy — you READ artifacts + source. Do NOT re-run the full suite or acceptance scripts — T1 is the sole heavy runner. Do NOT invoke the `ask-chatgpt` CLI yourself (its default channel is real and you are NOT under the pytest guard).
- This mission MUTATES NOTHING except your one report. NEVER edit or "fix" any source/tests/docs/scripts — REPORT defects instead (independence boundary).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents (you AUDIT for these — quote file:line, NEVER the would-be secret values). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY if strictly needed (you should not need to); never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T2c-STATUS: DONE|BLOCKED` as the LAST line.
