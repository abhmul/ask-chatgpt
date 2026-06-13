# T3-diag — Real-site readiness diagnostic (raw CDP attach, ZERO messages, observe-only)

You are a fresh real-site worker. **You inherit NOTHING except this file.** This is a REAL chatgpt.com attach, but **ZERO prompt sends (ZERO messages, ZERO quota)** — pure DOM observation to diagnose why the driver's `ready_root` check fails. Read the SAFETY BLOCK and obey it literally. Use `git stash push -u` for any revert; never `git checkout`/`git clean`. NEVER `git commit`.

## ⛔ SAFETY BLOCK (you inherit nothing; the whole law)
- Attach to the operator's running Chromium via `connect_over_cdp("http://127.0.0.1:9222")` — NEVER launch a browser, NO stealth/anti-detection.
- Open exactly ONE brand-new tab via `context.new_page()`; act ONLY on it. NEVER touch/navigate/close the operator's pre-existing tabs (record `preexisting = list(ctx.pages)` and leave them).
- NEVER call `browser.close()` or `context.close()` (would quit the operator's browser). Teardown = close only YOUR tab, then exit the `with sync_playwright()` block to detach. The browser must stay alive with operator tabs intact.
- **ZERO prompt sends.** Do NOT click any send/submit control. Do NOT type into the composer. Pure read-only observation (title, url, element counts). Do NOT log in/out. If a Cloudflare/login UI is present, just RECORD it and stop (no interaction).
- NEVER read/store/log credentials/cookies/tokens/profile contents. NO account identifiers; record URLs as path-shape only (`/`, `/c/<redacted>`).
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). NEVER `git push`/`git commit`.

## What to measure (write a `uv run python` script; raw Playwright)
Attach (raw `connect_over_cdp`), open a new tab, `page.goto("https://chatgpt.com", wait_until="load", timeout=60000)`. Then, WITHOUT sending anything, observe and record a timeline:
1. **Readiness timing:** at t ≈ 0, 1, 2, 3, 5, 8, 12 s after load, record the match count for EACH of: `#prompt-textarea`, `main:has(#prompt-textarea)` (this is the driver's `ready_root`), `main`, `button[data-testid="send-button"]`, `a[aria-label="New chat"]`. Report the FIRST time (seconds) each becomes present. (Use `page.locator(sel).count()`; small sleeps between samples.)
2. **Page state:** `page.title()` (record verbatim — it is not account-private), `page.url` PATH-SHAPE only (e.g. `/`, `/c/<redacted>`, `/auth/...`). Whether the URL is an auth/login shape. Whether a Cloudflare challenge marker is present (`iframe[src*='challenges.cloudflare.com']`, `#challenge-running`, title "just a moment").
3. **Overlays/interstitials:** any modal/overlay that could block the composer — cookie-consent banner, "Stay logged out"/onboarding/welcome modal, region/age gate. Record a stable selector or accessible name for any such overlay (NO account text). Note whether `#prompt-textarea` is present-but-covered vs absent.
4. **new-chat behavior (0 send):** if the app is ready, click `a[aria-label="New chat"]` (this is navigation, NOT a send) and record whether `#prompt-textarea` stays present and the url shape. (If clicking New chat is risky/ambiguous, skip and say so.)
5. **Tab hygiene self-check:** confirm `preexisting` tabs are all still present at the end; you closed only your own tab; you never called browser.close()/context.close().

## Output
- Report `orchestration/reports/M-006/T3-diag.md` (cap ~150 lines): the readiness timeline table, the page-state facts, any overlay finding, the new-chat observation, the tab-hygiene result, and a one-line DIAGNOSIS: is the driver's `ready_root` failure (a) SPA hydration timing (ready_root appears after N s) — give N; (b) an overlay/interstitial covering/blocking the app; (c) a logged-out/challenge state; or (d) selector drift (`#prompt-textarea` never appears at all)? `MESSAGES_USED: 0`. Last line: `T3-diag-STATUS: DONE` (or `BLOCKED` with the named precondition).
- If a Cloudflare/login UI is present (state c), run the challenge-pause logging (`HUMAN-ACTION-NEEDED: ...`) but do NOT poll long — just record and finish DONE-with-finding; the manager decides next steps.
