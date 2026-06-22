# FOLLOW-UP (from M10): verify `scrape --with-attachments` over the new light-page read path

**Version:** ask-chatgpt 0.2.0 + the M10 fix (branch `fix/m10-light-read-scrape`). **Severity:** medium (correctness gap, not a known break). **Type:** verification gap / TODO.

## Background
M10 (`issues/2026-06-22-read-ops-render-full-conversation-page.md`, RESOLVED) made `scrape` read from the light `https://chatgpt.com/` page using an **ambient backend-header harvest** (match any `GET /backend-api/*` carrying all 8 `REQUIRED_CAPTURE_HEADERS`) and a `retarget_headers(headers, fetch_path)` step that rewrites `x-openai-target-path` to the conversation fetch path. The core transcript read was confirmed end-to-end on a large real conversation (no renderer crash; 5s; faithful data).

**But `scrape --with-attachments` over the light path was NOT exercised on the real site** — the M10 real leg ran a plain `scrape` (no attachments).

## What is unverified
1. **Descriptor fetch headers.** Attachment descriptor fetches (`capture.py` ~`_fetch_attachment_descriptor`) reuse the **retargeted conversation** header dict (`x-openai-target-path` = `/backend-api/conversation/<id>`), NOT a descriptor-specific path. On the real site the descriptor endpoint is `GET /backend-api/files/<id>/download` (M6), so the retargeted `x-openai-target-path` may be wrong for that route. Whether the live descriptor fetch tolerates the conversation-path value (the way it tolerated verbatim `x-openai-target-route` for the conversation fetch) is unconfirmed.
2. **Byte download.** The byte download (the `download_url` follow) currently passes **no** headers (pre-existing behavior; the M10-T2 handoff wording overstated header reuse here). Needs confirmation it still works from the light-page origin.
3. **Ambient harvest sufficiency for the attachment flow** on a real attachment-bearing conversation.

## Suggested work
One attended, own-tab-only, ZERO-send `scrape --with-attachments` of a small attachment-bearing conversation via the light path; confirm descriptor + byte fetches succeed and files land in the cache. Record observed request **paths/route header NAMES only** (never values/bytes/file-ids). If the descriptor fetch needs its own `x-openai-target-path`, extend `retarget_headers` to take the actual descriptor path. Also consider a mock test asserting the descriptor request's `x-openai-target-path` (M10-T3-V3 noted this assertion is currently absent).

## Related
`issues/2026-06-22-read-ops-render-full-conversation-page.md` (M10 — resolved; this is its one deferred sub-check). M10 evidence: `team/evidence/handoffs/M10-*`.
