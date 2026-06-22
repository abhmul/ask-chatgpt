# M10-T1-L2 — Auth-harvest mechanism (THE CRUX: will a light page work?)

**FIRST read `team/contracts/M10-common.md` in full — it is mandatory and part of
these instructions.** Then execute this lens. READ-ONLY, OFFLINE.

## Your lens
The entire fix hinges on one question: **if `scrape` opens the light page
`https://chatgpt.com/` instead of `/c/<id>`, can it still harvest the auth/OAI
headers needed for the backend-API fetch, and will that fetch return correct
data?** You own this question. Be rigorous and adversarial — the issue assumes
"auth is domain-wide so it just works"; the M7b gap-2 history says otherwise.

## Required work — answer each definitively, with file:line evidence
1. **Harvest predicate.** Read `acquire_backend_headers` (`capture.py:140`),
   `matches()` (`:144-146`), and `wait_for_request` (find its impl in
   `channels/cdp.py` and `channels/base.py`). State EXACTLY what request it waits
   for and why the SPA issues it only on `/c/<id>`.
2. **Header conversation-agnosticism.** For each of the 8 `REQUIRED_CAPTURE_HEADERS`,
   classify it as (a) session/device/app-global (same on every backend-api request)
   or (b) request/path-specific. Pay special attention to **`x-openai-target-path`**
   and **`x-openai-target-route`**. Use the code + `team/evidence/handoffs/M2-ground-truth-probe.md`
   + `team/evidence/handoffs/M7b-gaps.md` as evidence. (Do NOT hit the real site.)
3. **for_single_fetch.** Read `HeaderBundle.for_single_fetch()` (grep it in
   `capture.py`) and how `stream_backend_conversation` (`capture.py:171-187`)
   builds `fetch_headers`. Does it recompute `x-openai-target-path`/`-route` for
   the fetched `/backend-api/conversation/<id>` URL, or pass the harvested values
   verbatim? This determines whether harvesting from a NON-conversation request is
   safe.
4. **Light-page request inventory.** From code + M2/M7b evidence, what
   `/backend-api/*` GET requests does the SPA issue on the bare
   `https://chatgpt.com/` root (e.g. `/backend-api/me`, `/backend-api/models`,
   `/backend-api/conversations`, `/backend-api/accounts/...`)? Would at least one
   reliably carry ALL 8 required headers? Mark clearly which parts are
   code-certain vs. **only confirmable by an attended real-site probe.**
5. **Minimal harvest change.** Specify the smallest change to the harvest so it
   works on a light page while keeping the conversation fetch correct. Options to
   evaluate: (a) match ANY `GET /backend-api/*` carrying all 8 headers and
   recompute `x-openai-target-path`/`-route` for the conversation URL in
   `for_single_fetch`; (b) navigate light, then actively trigger a harvestable
   request; (c) other. Recommend one.

## Verdict (put near top of handoff)
One of: **FEASIBLE** (light page works with no harvest change),
**FEASIBLE-WITH-CHANGES** (works given the specified harvest change),
**NEEDS-REAL-PROBE** (cannot be settled offline — name the exact probe), or
**INFEASIBLE** (with reason). Justify from code.

## Deliverable
Write your handoff to **`team/evidence/handoffs/M10-T1-L2-authharvest.md`**
following the handoff protocol in the common file. Lead with the verdict.
