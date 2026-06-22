# M10-T1-L3 — Minimal-fix design + falsifiability + interactions

**FIRST read `team/contracts/M10-common.md` in full — it is mandatory and part of
these instructions.** Then execute this lens. READ-ONLY, OFFLINE (design only — do
NOT implement).

## Your lens
Assume the diagnosis holds. Design the **smallest correct change** that makes
read/backend-fetch ops O(1) in conversation size, plus the falsifiable tests that
would prove it. Favor the simplest design (Occam); call out unnecessary complexity.

## Required work
1. **Light-acquire API.** Design how a read op gets an authenticated origin
   WITHOUT rendering `/c/<id>`. Evaluate concretely:
   - A `render`/`light` parameter on `TabPool.acquire` and/or `channel.open_tab`
     that navigates to `https://chatgpt.com/` instead of `conversation_url(ref)`.
   - **TabPool keying problem:** `acquire` caches entries keyed by `entry.url`
     (`session.py:85-90`); a light tab and a heavy tab for the same conv would
     collide or mis-reuse. Specify how the pool distinguishes/keys a light tab
     (and whether one shared light tab can serve reads for ANY conversation).
   - Where the absolute backend URL is passed to the fetch when the page is not
     `/c/<id>` (`fetch_in_page` already takes a path — confirm it builds an
     absolute URL against the page origin; see `channels/cdp.py` around the
     `JS_STREAM_FETCH` evaluate at `:834`).
2. **Exact change set.** List every file:line to edit and the shape of each edit
   (signatures, call-site updates in `scrape` and anything L1 flags). Keep
   send/`ask`/`loop` on the heavy `/c/<id>` path (unchanged).
3. **Falsifiable tests (mock tier).** Design tests that FAIL before the fix and
   PASS after, e.g.: scrape acquires a tab whose URL is the light root, NOT
   `/c/<id>`; capture succeeds when the page only issued a generic backend-api
   request (mock the harvest accordingly); a mutation reverting the fix breaks a
   named test. Specify them against the mock channel (`channels/mock.py`) +
   existing tests in `tests/`. Identify which existing tests might need updating
   and why (distinguish legitimate update from masking a regression).
4. **Interactions with the two related issues** (read them):
   `issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md` and
   `issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md`. Does a shared
   light read-tab help or hurt either? Any coupling the implementer must respect?
5. **Risk/regression analysis.** What could the fix break (fidelity, completion
   detection, attachment byte-route in `fetch`, the M7b draft-branch reload, DR/Pro
   capture)? How is each guarded?
6. **Real-leg recommendation.** State whether closing M10 REQUIRES an attended
   real-site confirmation (large-conversation read: no crash + correct data +
   harvest works on light page), and define the minimal such probe.

## Deliverable
Write your handoff to **`team/evidence/handoffs/M10-T1-L3-fixdesign.md`** following
the handoff protocol in the common file. Lead with the recommended change set as a
concise ordered list.
