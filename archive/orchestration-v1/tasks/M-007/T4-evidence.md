# T4-evidence — authoritative verification evidence runner (non-producer)

**Type:** verify-evidence (produce ONE authoritative output the 3 lenses will reason over — do NOT have lenses re-run heavy build/test concurrently). MOCK-TIER only. cwd = repo root `/home/abhmul/dev/ask-chatgpt`. `ESTIMATE: T4-evidence 15m`. You did NOT produce the code under test (independent).

## Do exactly this, capturing raw output to `tmp/verify-m007/`
1. `mkdir -p tmp/verify-m007`. Record `START_TIMESTAMP:`.
2. **Fresh deps:** `uv sync --all-groups` (capture to `tmp/verify-m007/sync.txt`).
3. **Full suite (authoritative):** `uv run pytest` serialized (no xdist), tee full output to `tmp/verify-m007/pytest-full.txt`. Capture the final summary line and exit code verbatim.
4. **Tier purity:** `uv run pytest -m "not real_site" --collect-only -q | tail -3` → `tmp/verify-m007/collect-not-real.txt` (confirm the default tier deselects the `real_site` test, i.e. collects ZERO real_site). Also `uv run pytest -m real_site --collect-only -q | tail -5` → `tmp/verify-m007/collect-real.txt` (confirm the real_site marker exists and is the only thing gated).
5. **No-stealth grep (must be clean):** grep `src/` + `tests/` for any anti-detection/fingerprint-spoofing/stealth tokens (e.g. `stealth`, `navigator.webdriver`, `playwright-stealth`, UA spoof, `--disable-blink-features=AutomationControlled`, fingerprint patching) → `tmp/verify-m007/grep-stealth.txt`. Expect ABSENT.
6. **Socket guard intact:** locate the autouse socket guard in the default-tier conftest/fixtures and confirm it is unchanged/active for the default tier → note the file:line in your report.
7. **CDP safety:** grep that `connect_over_cdp` is used (never a browser launch on the cdp channel) and that the cdp `close()` path DETACHES (does not call `browser.close()`/`context.close()` on the attached browser) → `tmp/verify-m007/grep-cdp.txt`.
8. **Git provenance:** `git log --oneline -8` and `git status --porcelain` → confirm the M-007 commits (5c26977 T1, 90e4f86 T2, plus any T3 drift commit) and that no secrets/venvs/`*.db`/account-identifiers are staged. Grep the M-007 commits' messages + the committed reports for any leaked real conversation id (`/c/<hexish>` not `<redacted>`) or email → `tmp/verify-m007/grep-leak.txt` (expect clean).
9. **T3 real artifacts:** list `tmp/real-accept-m007-*/` and `tmp/real-audit-*/messages.log`; summarize (REDACTED — never copy a real conversation id) what UC2/continuity evidence is present and whether `UC2_DIFF_OK`/`GAP15_CONTINUITY_OK` appear in the T3 report `orchestration/reports/M-007/T3.md`. Record `MESSAGES_USED` from the T3 report.

## Report
Write a CONCISE evidence summary to `orchestration/reports/M-007/T4-evidence.md` (≤120 lines): the pytest summary line + exit, the tier-purity counts, the no-stealth/socket-guard/CDP-safety/leak results (each PASS/FAIL with the file pointer), the git provenance, and a redacted summary of the T3 real artifacts + verdicts. Point to the raw files under `tmp/verify-m007/`. End with `END_TIMESTAMP:` and, as the LAST line, exactly `T4-EVIDENCE-STATUS: DONE` or `T4-EVIDENCE-STATUS: BLOCKED`.

## SAFETY BLOCK (verbatim)
- MOCK-TIER ONLY — do NOT contact chatgpt.com/openai or any browser/CDP (you only READ the T3 artifacts already on disk). Default-tier tests stay loopback-only; do not weaken the socket guard or the double-gate.
- Never read/store/log credentials, cookies, tokens, profile contents; REDACT any real conversation id / account identifier — never reproduce one in your report.
- Write ONLY inside the repo (+ `tmp/`). `uv sync --all-groups` ALWAYS. Serialize pytest. `uv run` from repo root; never touch the shared agent venv. Kill only your own processes. NEVER `git push`. Revert via `git stash push -u`.
- Do NOT edit any source/test file (you are a verifier, not a producer). If you find a defect, REPORT it; do not fix it.
