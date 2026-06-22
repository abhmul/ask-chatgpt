# M12 (verify) — Is the ChatGPT "Too many requests" rate-limit handling resolved (tool-side)?

**FIRST read `team/contracts/M-backlog-common.md` in full** (binding safety, environment, READ-ONLY rule, dispatch policy, handoff format). Then execute this mission. This is **read-only verification** — produce a per-fix verdict + a scope recommendation; do NOT edit code.

## The issue under test
`issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md`. chatgpt.com returns a modal **"Too many requests — … We've temporarily limited access … Please wait a few minutes …"** (and/or HTTP 429 on `/backend-api/conversation`). Today this surfaces as `INTERNAL_ERROR` (exit 99) / EPIPE — indistinguishable from a crash — and `ask` sends silently don't commit. The issue labels itself **"operational finding + tool feature-gap (not a code bug in the tool itself)"** and proposes three **tool-side** fixes:
1. **Detect the limit + a distinct exit code** (e.g. `RATE_LIMITED`): detect the "Too many requests" modal in the DOM and/or an HTTP 429 on the backend fetch, instead of mislabeling it `INTERNAL_ERROR`.
2. **Honor `Retry-After` / back off** automatically (jittered exponential backoff) rather than failing hard.
3. **Optional global rate governor** (min-interval / token-bucket) across invocations so a caller can't accidentally burst.

## What "resolved" means here
The OPERATIONAL guidance (diagnose from local artifacts, space out requests, ~30-min pause on the modal) is already captured in operator memory and is NOT what you're checking. You are checking whether the **three tool-side code fixes** above exist in the codebase.

## Lead's ground-truth pointers (verify each — do not trust)
- A repo-wide grep for `too many requests|rate.?limit|RATE_LIMITED|\b429\b|retry.?after|backoff|token.?bucket|governor|temporarily limited` (case-insensitive) over `src/ask_chatgpt/` returned only `n_factor` / `current_rate_per_min` in `session.py` — i.e. the **AdaptiveSendBudget** send-pacing knobs. Confirm this independently and characterize what AdaptiveSendBudget actually does.
- Error taxonomy lives in `src/ask_chatgpt/errors.py` (classes with `default_n` exit codes 20–40; `InternalError` ~line 261). A grep showed **no** `RateLimited*` class. Confirm.
- The exit-code mapping is in `src/ask_chatgpt/cli.py` (maps known errors → `exc.n`; unexpected → 99 `INTERNAL_ERROR`). Confirm there's no 429/modal branch.
- The backend fetch path: `src/ask_chatgpt/channels/cdp.py` (`fetch_in_page` / `JS_STREAM_FETCH` / `wait_for_request`) and `src/ask_chatgpt/capture.py`. Check whether any of these inspect HTTP status for 429 or detect the modal.

## What the worker(s) must determine (re-derive from ground truth)
For EACH of the three tool-side fixes, a present/absent verdict with `file:line` evidence:
- (1) Is there any "Too many requests" modal detection (DOM) and/or HTTP-429 detection on `/backend-api/conversation`? Is there a distinct `RateLimitedError`/exit code, or does it fall through to `InternalError`/99?
- (2) Is there any `Retry-After` parsing or jittered exponential backoff on rate-limit/429? (Distinguish from the completion-poll waits and from AdaptiveSendBudget's politeness pacing — neither is 429-aware backoff.)
- (3) Is there a cross-invocation global rate governor (min-interval / token-bucket persisted across CLI processes)? Characterize AdaptiveSendBudget precisely: what does it govern (send rate within one session? persisted across processes?), and does it react to 429s?

## Verdict (put in handoff + final stdout)
A 3-line verdict: `(1) PRESENT|ABSENT`, `(2) PRESENT|ABSENT`, `(3) PRESENT|ABSENT`, plus an overall `RESOLVED` / `UNRESOLVED (tool-side gap remains)` token. Then a **scope recommendation**: for any ABSENT fix, sketch the minimal correct implementation (e.g. a `RateLimitedError(default_n=…)` + a 429/modal detector at the fetch seam + jittered backoff honoring `Retry-After`; AdaptiveSendBudget extension vs a new governor), its blast radius (which files), and a rough effort/risk estimate — but DO NOT implement. Note: building these is a feature the operator must approve; your job is to make that decision well-informed.

## Suggested decomposition
A single careful read-only pi worker (tools `read,grep,find,ls,bash`) is sufficient for this concrete present/absent audit; you (manager) then independently re-derive each verdict from the cited `file:line` and write the handoff. (Optionally a second lens specifically on AdaptiveSendBudget semantics if its behavior is non-obvious.)

Handoff: `team/evidence/handoffs/M12-verify-rate-limit.md`.
