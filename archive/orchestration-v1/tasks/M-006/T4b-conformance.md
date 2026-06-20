# T4b — VERIFY (independent, non-producer): D-002-as-amended conformance + NO stealth + budget/audit + no identifier leakage

You are an INDEPENDENT verifier. You did NOT produce this work. **You inherit NOTHING but this file.** ZERO real-site contact, ZERO messages. Read-only + light greps. Do NOT re-run the full suite. Do NOT edit source.

## Read
- `docs/DECISIONS.md` (D-002 + the CDP addendum — the binding charter; note: stealth/anti-detection was EXPLICITLY REJECTED).
- `tmp/verify-m006/T4-evidence.txt` (stealth grep, identifier grep, ledger counts, commits).
- `orchestration/reports/M-006/T3.md`, `discovery.md`, `T1b.md` (CDP mechanics), and the real-message ledgers `tmp/real-audit-*/messages.log`.

## Verify these claims from ground truth (PASS/FAIL each)
1. **NO stealth / anti-detection ANYWHERE.** Independently grep `src/` + `tests/` for `automationcontrolled|navigator.webdriver|playwright.?extra|undetected|stealth|disable-blink-features`. Expect ABSENT (or only safety-comment denials). Confirm the real channel is plain `connect_over_cdp` to the operator's own browser — no fingerprint/UA spoofing.
2. **Real-site posture:** CDP attach to the operator's running signed-in Chromium (headed, human-launched), login/logout NEVER automated (driver raises `LoginRequiredError`, never types into login), Cloudflare/human-verification handled by a challenge-pause (driver raises `ChallengePresentError`; the manager/runbook pauses for the human — never circumvented). Verify the driver + T3 report honor this; no browser launched/quit by the tool; operator tabs untouched (tab-hygiene).
3. **Budget + audit discipline:** mission HARD cap 30 real messages; every send logged to a `tmp/real-audit-*/messages.log` ledger BEFORE sending. Sum the ledger data lines (expect 24/30, NEVER exceeded). T2 ≤12 (used 7), T3 ≤15. Note the log-before-send conservatism (some logged lines were pre-send failures, so ACTUAL quota < ledger). Confirm 30 was never exceeded.
4. **No account-identifier / credential leakage in COMMITTED artifacts.** Independently grep `orchestration/reports/M-006/` + the git log for emails / cookies / tokens / `Bearer` / un-redacted `/c/<uuid>` conversation ids. Confirm conversation URLs are recorded only as path-shape (`/c/<redacted-uuid>`). Confirm `tmp/` artifacts (which MAY hold real refs in the local session registry repair files) are NOT committed (`git status` shows no `tmp/`; tmp is gitignored).

## Output → `orchestration/reports/M-006/T4b.md` (cap ~120 lines)
Per-claim PASS/FAIL + evidence; `T4b-VERDICT: PASS|FAIL|PARTIAL` + justification. `MESSAGES_USED: 0`. Last line: `T4b-STATUS: DONE`.
