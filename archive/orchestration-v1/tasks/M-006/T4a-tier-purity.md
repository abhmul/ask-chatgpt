# T4a — VERIFY (independent, non-producer): default-tier purity + CDP attach safety mechanics

You are an INDEPENDENT verifier. You did NOT produce this code. **You inherit NOTHING but this file.** ZERO real-site contact, ZERO messages. Read-only analysis + light local checks. Do NOT re-run the full pytest suite (an authoritative run already exists — cite it); you may run targeted greps/`--collect-only` if needed. Do NOT edit source. Write only your report.

## Authoritative evidence to reason over (produced once by the manager)
- `tmp/verify-m006/T4-evidence.txt` — clean `uv run pytest` = `169 passed, 1 deselected`; socket-guard + real_site-gating grep; HEAD; M-006 commits; diff stat; ledger counts. CITE it; re-derive spot-checks from ground truth where cheap.

## Verify these claims from ground truth (PASS/FAIL each, with file:line / evidence)
1. **Default tier is loopback-mock-only.** Clean `uv run pytest` collects ZERO `real_site` tests (the `1 deselected` is the real_site marker). The autouse session socket guard in `tests/conftest.py` (loopback/AF_UNIX only) is present and UNCHANGED vs the mission baseline; `git diff 3693388^..HEAD -- tests/conftest.py` shows the guard logic not weakened. Real tier is double-gated (`real_site` marker + `ASK_CHATGPT_REAL=1`).
2. **CDP attach safety in `src/ask_chatgpt/driver.py`:** `channel="cdp"` uses `connect_over_cdp` (NEVER launches a browser); opens a brand-NEW page via its own cdp page path (never `context.pages[0]` / operator tabs); `close()` for cdp closes ONLY tool-opened pages and DETACHES (never `browser.close()`/`context.close()` on cdp); login + Cloudflare-challenge detection run on attach (`_raise_login_required_for_auth_redirect`, `_raise_challenge_present_if_detected`). Confirm via the cdp tests `tests/test_driver_cdp_attach.py` (tab-hygiene proof) and the driver code.
3. **`real.json` fail-closed schema preserved:** 20 selector + 2 attribute keys; only empirically-verified selectors filled; intentionally-unverified keys empty (`model_menu`/`model_option`/`model_option_disabled`/`login_wall`/`conversation_not_found`/`truncation_marker`/`rate_limit_marker`/`download_artifact`/`conversation_ref`). `SelectorMap.selector()/attribute()` still raise on empty (fail-closed primitive unchanged). Optional markers are tolerated (not hard-fail) in the driver/readers/patch real paths — verify that REQUIRED selectors still fail closed (`_require_present` unchanged) while OPTIONAL markers degrade gracefully.
4. **The previously-coupled fail-closed test is decoupled** (uses an empty-map fixture), so populating `real.json` did not weaken it.

## Output → `orchestration/reports/M-006/T4a.md` (cap ~120 lines)
Per-claim PASS/FAIL + evidence; then `T4a-VERDICT: PASS|FAIL|PARTIAL` with a one-line justification. Note anything you could NOT verify. `MESSAGES_USED: 0`. Last line: `T4a-STATUS: DONE`.
