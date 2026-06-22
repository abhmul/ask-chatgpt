# M12 handoff — VERIFY ChatGPT rate-limit ("Too many requests") tool-side handling

**Status:** DONE
**Verdict:** UNRESOLVED (tool-side gap remains) — (1) ABSENT, (2) ABSENT, (3) ABSENT.

> Provenance: the M12 manager (claude-watch.sh) dispatched two read-only pi auditors (`.pi-workers/M12-a`, `.pi-workers/M12-b`, both exit 0) but then **dispatched-and-yielded** without writing this handoff (the documented `claude -p` single-shot yield trap). This handoff is **lead-synthesized** from the two completed worker outputs + the lead's own ground-truth grep; trust = verified-independently (two workers agree + lead cross-check from `file:line`).

## What was verified (re-derived from ground truth)
Audited `src/ask_chatgpt/` for the three tool-side fixes the issue proposes. Both workers + lead agree on every point.

### (1) Detect the limit + distinct exit code — ABSENT
- HTTP status is only handled **generically**: `capture.py:937-938` raises `BackendCaptureShapeError` on any non-2xx (`status<200 or >=300`); `completion.py:54-57` raises `BackendCaptureShapeError` on `status != 200`. No `429`-specific branch, no "Too many requests"/"temporarily limited" modal-text branch anywhere (`rg` for `429|too many requests|temporarily limited|rate.?limit|RATE_LIMITED` over `src/` → no hits).
- `errors.py` has **no** `RateLimited*` class. Full taxonomy + exit codes: CDPUnreachable=20, HumanActionNeeded=21, DomainNotAllowed=22, ConversationNotFound=23, SelectorNotFound=24, PromptNotSubmitted=30, ModelSelectionNotReflected=31, ToolSelectionNotReflected=32, BackendAuthUnavailable=40, BackendCaptureShape=41, CaptureFailedClosed=42, CompletionTimeout=50, MaxTotalWaitExceeded=51, AttachmentNotFound=60, AttachmentFetch=61, TabPoolExhausted=62, AttachmentUpload=63, Store=70, Internal=99.
- A rate-limited fetch therefore surfaces as `BackendCaptureShapeError` (41) or, on the send path / unexpected, falls through to `cli.py:106-108` → exit **99 (INTERNAL_ERROR)** — exactly the "indistinguishable from a crash" symptom the issue reports.

### (2) Honor Retry-After / back off — ABSENT
- No `Retry-After` parsing, no 429-triggered backoff (`rg` for `retry.?after|429` → no hits).
- The only `backoff` symbol is `AdaptiveSendBudget.backoff_factor` (`session.py:149,157,198`) — soft-signal **send-pacing** reduction, NOT wired to any HTTP-429/modal trigger. Completion-poll waits (`completion.py:206,473`) are unrelated.

### (3) Global rate governor — ABSENT
- `AdaptiveSendBudget` (`session.py:139`) is **per-Session, in-memory, send-only** pacing (`current_rate_per_min`, politeness floor 5s, AIMD increase/`backoff_factor`). It is **not persisted** to `data_dir` (Store persists only conversations/index/transcripts; `store.py:84-88,705`), so it does **not** coordinate across CLI processes (each `cli._new_session` builds a fresh budget — `session.py:302`). It governs **sends only** — the read/scrape path (`session.py:525-527`) makes no budget call. No token-bucket/governor (`rg token.?bucket|governor` → no hits).
- NOTE (useful for a fix): `AdaptiveSendBudget.record_soft_signal(kind)` (`session.py:194-198`) already exists to halve the rate — but it is **never called** from any HTTP/modal handler. Wiring a 429/modal detection to `record_soft_signal` is the cheapest first increment.

## Operator decision (recorded)
Operator (2026-06-22): do **NOT** build the fixes now — **confirm absent (done above) and AUGMENT the issue file** `issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md` with suggested implementation approaches. (The operational guidance is already in memory `chatgpt-rate-limit-guidance`; this is the tool-side feature-gap.)

## Recommended next (Round 2 — doc only, no code)
Lead augments `issues/2026-06-21-*.md` with concrete implementation sketches for the 3 fixes:
- **(1)** Add `RateLimitedError(_KnownAskChatGPTError)` with a new `default_n` (e.g. 52, after MaxTotalWaitExceeded=51). At the single fetch seam (`capture.py` non-2xx branch + `completion.py` status branch) detect `status == 429` (and optionally the DOM modal text on the send path) and raise it instead of `BackendCaptureShapeError`/falling to 99.
- **(2)** Parse `Retry-After` from the 429 response headers (the in-page fetch already returns headers — `cdp.py:79`) and apply jittered exponential backoff; on the send path, route the 429/modal into the existing `AdaptiveSendBudget.record_soft_signal("rate_limited")` so the adaptive rate halves.
- **(3)** For cross-process pacing, persist a minimal last-request timestamp / token-bucket file under `data_dir` so independent CLI invocations honor a shared min-interval (per the shared-resource ceiling principle); document that backoff is the safety net, not the primary control.

## Complexity / paradigm-shift signals
None. Clean feature-gap; the seams (single fetch chokepoint, existing `record_soft_signal`, error taxonomy) make the future fix low-risk. Building it is a separate operator-approved mission, not done here.
