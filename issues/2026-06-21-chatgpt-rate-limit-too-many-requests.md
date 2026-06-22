# FINDING: ChatGPT "Too many requests" rate limit (request-volume burst) masquerades as a conversation stall

**Version:** ask-chatgpt 0.2.0. **Severity:** high for automated/looping + diagnostic use. **Type:** operational finding + tool feature-gap (not a code bug in the tool itself).

## Symptom
chatgpt.com returns a modal: **"Too many requests — You're making requests too quickly. We've temporarily limited access to your conversations to protect your data. Please wait a few minutes before trying again."** (observed 2026-06-21, screenshot from operator). While limited:
- `scrape` fails → the tool exits `INTERNAL_ERROR` (99) / EPIPE.
- `ask` sends do NOT commit: a provisional user turn briefly appears in `count_users` then drops on the next clean backend scrape (see `2026-06-18-cdp-send-noop-returns-stale-response.md` and memory `ask-chatgpt-v020-driving`).

Because reads fail and writes silently don't commit, **this looks exactly like a "stuck"/exhausted conversation** — which tempts more diagnostics (more requests → worse) and can trigger an unnecessary conversation rotation.

## What happened (incident R-001)
The weak-simplex perpetual driver had run for HOURS at its steady cadence (~1 read-only `scrape`/90s ≈ 40/hr + ~1 `ask`/send) with no rate-limit. The limit was hit only after a BURST of *added* requests in a short window, all concurrent with the driver's own polling:
- many manual diagnostic `scrape`s ("is it stuck" probing),
- a rotation (`rotate.sh`: old-conv scrape + fresh-conv seed `ask` + new-conv verify scrape),
- several driver restarts (each restart re-scrapes in `wait_until_idle`).

## Inferred behavior (exact thresholds NOT published — uncertain)
- The limiter appears **burst-sensitive** (many requests within a few minutes): the driver's ~40/hr baseline ran for hours before the first trip. **UPDATE (recurrence, same day):** the limit then RECURRED ~30-60min after a clean restart with NO agent-added requests — so the driver's baseline cadence (1 scrape/90s ≈ 40/hr) ALSO trips it in the account's current state. So it's both burst- AND volume-sensitive once the account is in a throttled state. Likely contributors: a partially-consumed account usage quota (heavy activity earlier the same day), a longer-than-"a-few-minutes" window, and/or CONCURRENT operator usage of the same account. Mitigation applied: lowered `idle_poll_interval_s` 90s→300s (≈12 scrapes/hr). If it still recurs, it's likely an account-level quota (not tunable by cadence) → pause hours, not minutes.
- The danger is **operator/agent-ADDED concurrent requests** on top of the driver's baseline.
- Recovery is short (modal says "a few minutes"); a ~30-min full pause is a safe margin.
- This is a DIFFERENT failure mode from renderer/main-thread saturation on heavy pages (`heavy-chatgpt-gentle-cdp`): that's CPU/eval load; this is request COUNT.

## Guidance / mitigations (consumer side — in place / recommended)
- **Diagnose from local artifacts, not live requests:** read the driver's own `driver.log`, `status.json`, and `ask-data/.../raw-mapping.json` (zero added requests). Do NOT run manual `scrape`s to "check state" while the driver runs.
- Never fire concurrent/back-to-back scrapes; avoid restart bursts (each restart re-scrapes); space out rotations (supervisor `min_rotate_interval_s`=2h anti-thrash already helps).
- On the modal: pause driver+supervisor (STOP file) ~30 min, do nothing against chatgpt.com, then resume. (Done for R-001 + scheduled auto-restart.)
- Distinguish a rate-limit from genuine conversation exhaustion BEFORE rotating.

## Suggested tool-side fixes
1. **Detect the limit and surface a distinct exit code** (e.g. `RATE_LIMITED`) — detect the "Too many requests" modal in the DOM and/or an HTTP 429 on `/backend-api/conversation`. Today it surfaces as `INTERNAL_ERROR`, which is indistinguishable from a crash and misleads consumers.
2. **Honor `Retry-After` / back off** automatically with jittered exponential backoff rather than failing hard.
3. **Optional global rate governor** (min-interval / token-bucket) across invocations so a caller can't accidentally burst — useful since each CLI call is a separate process and the tool can't otherwise self-pace across calls.

## Related
Memory `chatgpt-rate-limit-guidance` (inferred operating discipline). Same incident produced the send-commit-confirm fix in `driver.sh` and the false-positive-sent note in memory `ask-chatgpt-v020-driving`.
