# M3 Verify — Dimension 2: gotcha-fix + safety-invariant coverage (DESIGN ONLY, independent verification)

**Read first, in full:** `team/contracts/M3-common-constraints.md`, then the design under verification `team/evidence/reports/M3-detailed-design.md`, then cross-check `docs/REWRITE-SPEC.md` (§5–§8 gotchas, §13 safety, §17 traceability) and `team/charter.md` (safety invariants).

**You are an INDEPENDENT verifier.** You did NOT produce this design. Your single dimension: **does the design implement ALL four gotcha fixes AND honor EVERY safety invariant?** Be adversarial — a plausible-sounding mention is not the same as a correct, fail-closed mechanism. For each item, quote the design's mechanism and mark `COVERED | WEAK | GAP`.

**Write your verdict to:** `team/evidence/reports/M3-work/verify-2-gotcha-safety.md` (begin with `STATUS:` then `VERDICT: PASS | PASS-WITH-NOTES | FAIL`).

## Part A — the four gotcha fixes (each MUST be a concrete, falsifiable mechanism, not a slogan)
1. **Math-corruption (capture-renders-dom-not-raw-markdown):** backend-api canonical markdown primary; fail-closed fallback copy-button → KaTeX annotation → DOM textContent; fidelity bar `\widehat`/`\ne`/`\frac{}{}` round-trip vs web-UI **copy**, **verified not assumed**. Is the fallback genuinely fail-closed (flags/raises, never silently emits ambiguous math)?
2. **Silent no-op send (cdp-send-noop-returns-stale-response):** baseline latest user-turn `message_id`/count → submit → poll for a NEW user turn → else `PromptNotSubmittedError` (loud + retryable); wait/retry the transiently-unmounting composer; reload-when-idle; `wait_for_completion` requires a turn **newer** than baseline. Is the baseline→new-turn check actually load-bearing (could a stale reply still slip through)?
3. **Truncation + hidden 600s ceiling (response-truncated-...):** **no hidden ceiling** — `timeout` = no-activity window (resets on progress), `max_total_wait` default unbounded; long Pro/DR never silently killed; completion via backend-api poll. Is there any place a hard cap could sneak back in?
4. **`--out` suppresses stdout:** `ask`/`scrape` ALWAYS print to stdout AND additionally write `--out`. Confirm no path where `--out` suppresses stdout.
5. **Lose-nothing write discipline:** eager-write stub at/before send → update on completion → salvage partial visible text with `status`+`partial=true`; conversation ref persisted before send (resumable). Is a failed/truncated call always recoverable?

## Part B — every safety invariant (charter §"Shared-resource ceilings" + REWRITE-SPEC §13)
For each, confirm the design encodes it (mark COVERED/WEAK/GAP):
- CDP-attach ONLY; **no Playwright-launched browser**.
- **No stealth / anti-detection, ever.**
- **Domain allowlist** (chatgpt.com/openai.com/auth/oaiusercontent) enforced (`allowlist.py`).
- **Inspect ONLY tabs the tool opens**; never iterate `context.pages`; never read operator/other tabs (leak risk).
- **Never quit the browser** (detach only; close own tabs only).
- **Preflight CDP** (`curl -s --max-time 5 .../json/version`) before any real leg → `CDP_UNREACHABLE` + escalate if down.
- **Login/Cloudflare challenge → STOP, log `HUMAN-ACTION-NEEDED`, poll read-only**; login NEVER automated.
- **Real-site legs operator-attended**, never CI/cron/unattended.
- **Account: human-paced, no programmatic spamming, NO hard message cap** (no arbitrary low cap baked in); backoff + politeness floor are safety nets, not low ceilings.
- **The `authorization` token + OAI headers are NEVER persisted or logged** (not in transcript, raw-mapping, logs, or error text).
- **Never `git push`; never move/commit `stable`; never `uv tool install/upgrade/reinstall`.**

End with: counts (COVERED/WEAK/GAP for Part A and Part B), the **most serious gap** (if any), and your `VERDICT`. Any GAP on a gotcha fix or a safety invariant blocks `PASS`. Re-derive each from the charter/spec; do not trust the design's self-claim.
