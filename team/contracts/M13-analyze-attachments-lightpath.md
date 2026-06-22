# M13 (analyze) — Does `scrape --with-attachments` work over the new light-page read path? (offline analysis)

**FIRST read `team/contracts/M-backlog-common.md` in full** (binding safety, environment, READ-ONLY rule, dispatch policy, handoff format). Then execute this mission. This is **read-only offline analysis** — produce a verdict + an exact Round-2 implementation spec + an attended-real-leg test plan; do NOT edit code and do NOT touch the real site/browser.

## Background (the M10 change this scrutinizes)
M10 (`issues/2026-06-22-read-ops-render-full-conversation-page.md`, RESOLVED) made `scrape` read from the light `https://chatgpt.com/` page using an **ambient backend-header harvest** (match any `GET /backend-api/*` carrying all 8 `REQUIRED_CAPTURE_HEADERS`) + `retarget_headers(headers, fetch_path)` which rewrites `x-openai-target-path` to the conversation fetch path (keeping `x-openai-target-route` verbatim). The plain-transcript read was confirmed live (no renderer crash; 5 s; faithful). **But `scrape --with-attachments` over the light path was NOT exercised on the real site** — the M10 real leg ran a plain `scrape`.

The follow-up issue is `issues/2026-06-22-scrape-with-attachments-light-path-unverified.md`. Read it.

## Lead's ground-truth pointers (verify each — do not trust)
In `src/ask_chatgpt/capture.py`:
- `retarget_headers(headers, fetch_path)` (~line 82): deletes `x-openai-target-path`, sets it to `fetch_path`; **keeps `x-openai-target-route` verbatim** (TODO(M10-T4) comment ~line 90).
- `capture_conversation` / scrape flow: `backend_headers = headers.for_single_fetch(fetch_path=fetch_path)` (~line 203) where `fetch_path` is the **conversation** path `/backend-api/conversation/<id>`. With `--with-attachments`, `download_attachments(tab, conv, backend_headers, records, store)` (~line 350) is called with those **conversation-retargeted** headers.
- `download_attachments` (~378) → `_download_one_attachment` (~422) → `_fetch_attachment_descriptor(tab, headers, file_id)` (~459): builds `descriptor_url = /backend-api/files/<file_id>/download` and fetches it **using the passed-in (conversation-retargeted) headers** — it does NOT re-retarget `x-openai-target-path` to `descriptor_url`.
- The byte download (~446): `tab.channel.fetch_in_page(tab, download_url, method="GET", stream_to=target, timeout_s=None)` — passes **no** headers (follows the descriptor's `download_url`).

## Historical fact to weigh (verify against evidence/handoffs)
In **M6** (pre-M10), `scrape --with-attachments` of the target conversation downloaded **10 attachment files successfully** — and at that time headers were harvested from the rendered `/c/<id>` page with `x-openai-target-path` already = `/backend-api/conversation/<id>`, and the descriptor fetch reused them. So the descriptor endpoint `/backend-api/files/<id>/download` **historically tolerated** the conversation-path value of `x-openai-target-path`. Read `team/evidence/handoffs/M6-target-scrape.md` (and any M6-T3 evidence) to confirm this. The open question is only whether the **M10 ambient-harvested** headers (from the light page) behave the same for the descriptor + byte fetches.

## What the analysis must determine (re-derive from ground truth)
1. **Descriptor fetch correctness.** Does `_fetch_attachment_descriptor` send `x-openai-target-path` = the conversation path (not the descriptor path)? Given M6 tolerated that, is a code change *needed* for correctness, or only *advisable* for robustness? Specify both the minimal "leave as-is" and the "retarget to `descriptor_url`" options. If recommending retarget, give the exact change (extend `retarget_headers`/the call site to retarget to `descriptor_url`; preserve `x-openai-target-route` handling).
2. **Byte download.** Confirm `fetch_in_page` for the `download_url` passes no headers, and reason about whether that works from the light-page origin (same-origin? the `download_url` is typically a pre-signed blob URL — does it need auth headers at all?). State the risk and how the real leg will confirm it.
3. **Ambient-harvest sufficiency.** On an attachment-bearing conversation, does the ambient harvest (any `GET /backend-api/*` with all 8 headers) reliably fire on the light page? Any reason the attachment flow would need a different harvest than the transcript read?
4. **Test gap.** Is there a mock test asserting the descriptor request's `x-openai-target-path`? (M10-T3-V3 noted this assertion is absent.) Read `tests/test_capture.py` to confirm. Spec a falsifiable mock test that pins the descriptor request's `x-openai-target-path` to whatever the chosen design dictates, and that FAILS if the retarget is wrong/missing.

## Verdict (put in handoff + final stdout)
- `OFFLINE-VERDICT: CODE-CHANGE-NEEDED` **or** `OFFLINE-VERDICT: NO-CODE-CHANGE-NEEDED (real-leg still required)`, with justification grounded in the M6 history + the code.
- The exact **Round-2 implementation spec** (the retarget change if any + the falsifiable mock test, with what it asserts and how it fails pre-fix). Note: this touches `src/ask_chatgpt/capture.py` + `tests/test_capture.py` — DISJOINT from M11 (`cli.py`) and from M12 (read-only); flag any overlap.
- The **attended-real-leg test plan** (operator-gated, NOT executed by you): exact steps for one own-tab-only, ZERO-send `scrape --with-attachments` of a SMALL attachment-bearing conversation via the light path; what to observe (descriptor request path + which header NAMES present, byte fetch success, files land in cache); explicit rule to record **paths/route header NAMES only — never values/bytes/file-ids**; redirect stdout to `/dev/null` (content-leak). State preflight `curl -s --max-time 5 127.0.0.1:9222/json/version` and STOP-on-Cloudflare/login.

## Suggested decomposition (best-of-N — this is genuinely multi-faceted)
Launch **3 parallel read-only pi lenses** (tools `read,grep,find,ls,bash`), each returning findings via stdout:
- **Lens A — header-flow correctness:** trace headers from harvest → `retarget_headers` → descriptor fetch → byte fetch; decide if descriptor retarget is needed vs advisable (weigh the M6 tolerance fact).
- **Lens B — test/falsifiability:** audit `tests/test_capture.py` for descriptor-path assertions; design the falsifiable mock test.
- **Lens C — real-leg plan + ambient-harvest sufficiency:** specify the exact attended ZERO-send leg + leak rules, and assess ambient-harvest reliability for the attachment flow.
Then YOU synthesize one verdict + spec + plan, re-deriving from the cited `file:line`, and write the handoff.

Handoff: `team/evidence/handoffs/M13-analyze-attachments-lightpath.md`.
