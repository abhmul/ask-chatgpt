# MISSION-006-RESUME2 — real-site via CDP attach (operator decision B2: option B)

**You are the second resume manager for MISSION-006.** Read in order: (1) this file; (2) `orchestration/reports/M-006/RESUME-FINDING-cloudflare.md` (why Playwright-launch is dead: Cloudflare interstitial — REFUTED the "logged out" theory); (3) `orchestration/state/M-006-state.json`; (4) the original contract `orchestration/tasks/MISSION-006.md` — its D-002 bounds, SAFETY BLOCK, telemetry, budgets (30 messages TOTAL across all M-006 manager lifetimes; 0 spent so far — verify against both `tmp/real-audit-*/messages.log` ledgers) remain binding. Sibling-manager check + pid recording per RESUME1 precedent. Do NOT redo T1 (done, committed `3693388`).

## The operator's decision (2026-06-12)

Real-site automation proceeds by **attaching to the operator's own running browser over CDP** — NOT by launching an automated browser (Cloudflare blocks those), NOT by stealth/evasion (explicitly rejected; never attempt). The operator launches, during a run window:
`chromium --profile-directory='Profile 1' --remote-debugging-port=9222`
(their "agent" profile, signed into chatgpt.com). The team lead has given the operator this command; it may already be running when you start, or come up mid-mission.

## New leg T1b — CDP channel (single editor, MOCK-TIER, TDD; no operator dependency)

1. Driver gains `channel="cdp"`: `connect_over_cdp("http://127.0.0.1:9222")` (port configurable); attach to the existing browser; **open a NEW tab** for all tool activity; NEVER touch, navigate, or close the operator's existing tabs; NEVER quit/close the attached browser (detach only); close ONLY tabs the tool opened.
2. Preflights (named, actionable): CDP endpoint unreachable → "CDP_UNREACHABLE: launch chromium --profile-directory='Profile 1' --remote-debugging-port=9222"; endpoint up but chatgpt.com renders Cloudflare challenge → CHALLENGE_PRESENT (see pause protocol); renders login page → LoginRequiredError (operator signs in by hand).
3. **Automated tests for the attach mechanics WITHOUT the real site:** launch a throwaway chromium (`--remote-debugging-port=<ephemeral>`, `--user-data-dir=tmp/...`, headed-or-headless is fine for the THROWAWAY) serving the MOCK fixture; attach via the new channel; drive UC1 against the mock through CDP; prove tab hygiene (pre-existing tabs untouched). These tests are default-tier (loopback only).
4. Fix the known coupling (memory + RESUME-FINDING): `tests/test_driver.py:150` depends on `real.json` being empty — repoint it at an explicit empty-map fixture so populating `real.json` in T2 cannot break the suite.
5. Full default suite green before any real leg.

## Real legs (unchanged budgets: T2 ≤12 msgs, T3 ≤15, mission ≤30; serialized; one at a time)

- **Challenge-pause protocol (replaces "headed Playwright launch" rules; everything else from the original SAFETY BLOCK still applies):** if a Cloudflare challenge or any human-verification UI appears at ANY point: STOP all automation actions immediately; print/log `HUMAN-ACTION-NEEDED: clear the challenge in the browser window`; poll read-only (no clicks, no keystrokes) up to 10 minutes for it to clear; cleared → continue; not cleared → end the leg, handoff PARTIAL with that state. NEVER interact with the challenge UI programmatically.
- T2 discovery per original contract, but over the CDP-attached tab (fill `real.json`, answer the 10 unknowns, asset-domain list, ≤12 messages, audit every message). Tab/session pinning notes: conversation URLs opened in the TOOL's tab.
- T3 UC1–3 real acceptance per original contract over CDP (≤15 messages). The CLI/api real path must work with `channel="cdp"` config (document the config knob in the runbook as the supported real mechanism).
- Update `docs/runbooks/real-site-acceptance.md` + `docs/runbooks/observe-chatgpt-unknowns.md` prerequisite sections: the supported real channel is CDP attach (the launch command above); profile-lock guidance is obsolete for CDP (browser RUNS during attach); port open only during run windows.
- **T4 final panel (N=3 + synthesis; non-producers):** combines the deferred T1 verification with T2/T3 evidence audit: (a) tier purity + CDP mock-tests + tab-hygiene proof + test_driver fix; (b) D-002-as-amended conformance (no evasion anywhere — grep for stealth/AutomationControlled patterns and confirm ABSENT; challenge protocol honored per logs; budgets/audit consistent; no account identifiers in artifacts); (c) empirical findings + spec coverage (10 unknowns answered or honestly unknown; UC1–3 real evidence consistent; D-001 revisit verdict). Synthesis → update `VERIFICATION.md` (real-proven vs mock-proven vs unknown) + `orchestration/reports/M-006/verify.md` with final `VERDICT: PASS|FAIL`.
- Handoff: replace the PARTIAL `orchestration/handoffs/MISSION-006-handoff.json`; total MESSAGES_USED across ALL ledgers; telemetry literal JSON fields + bare lines; ACTUAL from first manager start ~09:59. State DONE (or PARTIAL with exact operator action). Closeout commit `M-006:`. NEVER push.

## Operator-coordination rule for YOU (the manager)

T1b needs no operator. Before T2: preflight the CDP endpoint; if unreachable, do NOT idle longer than one 480s watch cycle — write the handoff PARTIAL with `CDP_UNREACHABLE` + the exact launch command and exit cleanly; the team lead will coordinate the window and resume you. If reachable but challenged/logged-out, same pattern with the respective named state.
