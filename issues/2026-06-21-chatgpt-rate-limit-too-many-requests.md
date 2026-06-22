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

## Tool-side implementation sketch (added 2026-06-22 — verified ABSENT in 0.2.0)
A verification pass (M12, handoff `team/evidence/handoffs/M12-verify-rate-limit.md`) confirmed all three tool-side fixes are **absent** from `src/ask_chatgpt/` as of 0.2.0: no 429/modal detection, no `RateLimited*` error class (a rate-limited fetch surfaces as `BackendCaptureShapeError`/exit 41, or falls through `cli.py:106-108` to exit **99 `INTERNAL_ERROR`** — the "looks like a crash" symptom), no `Retry-After`/backoff, and no cross-process governor. `AdaptiveSendBudget` (`session.py:139`) is in-memory, **send-only** pacing and is not 429-aware; notably `AdaptiveSendBudget.record_soft_signal()` (`session.py:194-198`) already exists to halve the rate but is **never wired** to any HTTP/modal signal. Suggested implementations (smallest-first):

### 1. Detect the limit + distinct exit code
- Add `class RateLimitedError(_KnownAskChatGPTError)` in `errors.py` with a new `default_n` (e.g. **52**, after `MaxTotalWaitExceeded=51`; existing codes 20–51, 60–63, 70, 99).
- Detect at the single fetch chokepoint: in `capture.py:937-938` and `completion.py:54-57` branch on `status == 429` **before** the generic non-2xx `BackendCaptureShapeError`, and raise `RateLimitedError` (stash any `Retry-After` in `details`). On the send/UI path, also detect the DOM modal text ("Too many requests" / "temporarily limited") with a selector check after submit and raise the same error. Result: callers get a stable, distinct exit code instead of 99.

### 2. Honor Retry-After / back off
- The in-page fetch already returns response headers (`cdp.py:79`). Parse `Retry-After` (delta-seconds or HTTP-date) from the 429 and sleep it (with a sane cap) for a bounded retry count; otherwise jittered exponential backoff.
- On the send path, route the 429/modal into the existing `AdaptiveSendBudget.record_soft_signal("rate_limited")` so the adaptive send rate halves (`session.py:194-198`) — i.e. finally wire that dormant method.

### 3. Optional global rate governor (cross-process)
- Each CLI call is a separate process, so the per-`Session` in-memory `AdaptiveSendBudget` cannot coordinate across invocations. Persist a minimal pacing record under `data_dir` (a last-request timestamp / token-bucket file, guarded like the existing transcript flock at `store.py:387-390`) and have every read/send honor a shared min-interval.
- Per the shared-resource-ceiling principle: one owner allocates `sum(consumer rates) + reserve ≤ ceiling`; backoff is the safety net, not the primary control. The real ceiling is unpublished and burst+volume-sensitive (see "Inferred behavior" above) — make the governor's rate configurable and conservative by default.

> Operating discipline (already in place) remains the first line of defense — diagnose from local artifacts, avoid request bursts, pause ~30 min on the modal (memory `chatgpt-rate-limit-guidance`). These tool-side fixes harden the tool so a rate-limit becomes *legible* (distinct exit code) and *self-throttling* (backoff/governor) instead of masquerading as a crash. **Building them is a separate operator-approved mission — not yet implemented.**
