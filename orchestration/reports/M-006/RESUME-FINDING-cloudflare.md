# M-006 RESUME FINDING (manager-2) — chatgpt.com is Cloudflare-blocked for the automated browser

**Date:** 2026-06-12 (resume manager pid 3390129). **Real messages spent: 0 of 30 (budget fully intact).** No login automated, no profile contents read, no account identifiers captured, no bot-challenge bypass attempted.

## Bottom line

Automated real-site discovery/acceptance (M-006 tasks T2 / T3) is **INFEASIBLE as designed.** When a Playwright-driven headed Chromium (system binary `/usr/bin/chromium`, the operator's real profile) navigates to `https://chatgpt.com`, Cloudflare serves a **"Just a moment…" bot-detection interstitial that never clears** — the automated browser never reaches the ChatGPT app *or* its login page. This is a different and more fundamental blocker than the prior manager's "logged out" diagnosis, which is now **REFUTED**: we cannot observe auth state at all because Cloudflare blocks *before* the auth layer.

## Evidence (3 independent ZERO-message render probes — pure observation, no prompts sent)

| Probe | Method | Result |
|---|---|---|
| T2-pre v1 (`T2-pre.md`) | 3 s settle, narrow markers | `Profile 1` → login/signup affordance + no composer (read as "logged-out"); `Default` → nothing rendered ("ambiguous"). Inconsistent — a timing/interstitial smell. |
| T2-pre v2 (`T2-pre-v2.md`) | networkidle + 20 s poll, rich markers | BOTH `Profile 1` and `Default` → after 20 s: no composer, no login, no signup, no history, no account chrome; host `chatgpt.com/`; **title 16 chars, ≠ "ChatGPT"**. |
| T2-pre v3 (`T2-pre-v3.md`) | 45 s poll, capture title + Cloudflare markers, **diagnose-only (no bypass)** | Title pinned to **"Just a moment…"** from sec 2 → 44 on host `chatgpt.com`; **never** reached composer or login. `INTERSTITIAL_CONFIRMED: cloudflare`, `CLEARED_TO_APP_OR_LOGIN: no`. |

The v3 poll timeline (every 2 s for 45 s) shows the Cloudflare title continuously and `composer=0, login_ctl=0` throughout — a hard, non-transient block for the automated browser. (The specific `iframe[challenges.cloudflare.com]`/`#challenge-running` DOM markers read 0, but the canonical Cloudflare challenge **title** "Just a moment…" on chatgpt.com is unambiguous; OpenAI fronts chatgpt.com with Cloudflare.)

## Why this is not something the agent can or should "fix"

- **Not an auth problem.** The operator's claim that Profile 1 ("agent") is signed in is *not contradicted* — their real, human-launched browser passes Cloudflare and shows them signed in. Our automated browser simply can't reach the auth layer to confirm it. So "sign in again" would NOT unblock automation.
- **Passing Cloudflare would require bot-detection evasion** (stealth flags such as `--disable-blink-features=AutomationControlled`, webdriver patching, `playwright-stealth`, etc.). That is **outward-facing, not authorized under D-002, plausibly contrary to OpenAI's ToS for the operator's account, and disallowed by the team charter.** The agent did not attempt it and should not without an explicit, separate operator decision.

## This vindicates the team charter's own ground-truth anchor

The charter states verbatim: *"Real-chatgpt.com proof is operator-run from runbooks, never automated."* M-006's attempt to make real-site discovery/acceptance **agent-driven** conflicts with that anchor, and the Cloudflare block is the concrete reason the anchor exists. The runbooks already present as the manual alternative — `docs/runbooks/observe-chatgpt-unknowns.md` (the 10 unknowns) and `docs/runbooks/real-site-acceptance.md` (UC1–3 real proofs).

## Recommended decision (operator / team-lead) — DEFAULT is charter-aligned and needs no new code

1. **DEFAULT (recommended): revert real-site proof to operator-run.** Accept that the **mock tier is the authoritative automated acceptance** (132 passing tests; the README spec acceptance runs against the local mock-ChatGPT fixture per the charter anchor). The operator resolves the 10 unknowns and runs UC1–3 manually from the runbooks, recording findings. Keep **T1 (tier plumbing — `real_site` marker + `ASK_CHATGPT_REAL` double-gate + domain allowlist + profile preflight, committed `3693388`, mock suite green) as the standing automated deliverable.** `src/.../real.json` stays empty/fail-closed.
2. **OPTIONAL middle path — CDP attach to the operator's OWN browser.** If automation is still desired: the operator launches their normal Chromium themselves (it passes Cloudflare as a real browser, already signed in) with `--remote-debugging-port=9222`, then a worker `connect_over_cdp()`s to that *human-established* session instead of launching a fresh automated one. This is *not* bot evasion (it drives a genuine human browser), but (a) needs operator consent + the debug-port launch, (b) may still re-challenge on navigation/actions, (c) is more complex. Offer only if the operator wants it; do not adopt unilaterally.
3. **NOT recommended without explicit operator sign-off: stealth/anti-detection.** Flagged for completeness; outward-facing + ToS/charter risk. Do not pursue absent a new, explicit operator decision that owns those risks.

## State of the mission at this finding

- **Budget:** 0 of 30 real messages spent (intact). **No** account data, credentials, cookies, or identifiers were read or stored in any probe.
- **T1:** DONE + manager-gate-verified + committed (`3693388`); unaffected. Independent best-of-N verification of T1 remains the recommended next *unblocked* task if the mission proceeds under option 1.
- **T2 / T2b / T3 / T4:** BLOCKED on the decision above (T2/T3 are the automated real-site legs that Cloudflare prevents).
- **Default tier purity:** intact — clean `uv run pytest` still collects zero `real_site` tests; `real.json` untouched (0 non-empty selectors).
