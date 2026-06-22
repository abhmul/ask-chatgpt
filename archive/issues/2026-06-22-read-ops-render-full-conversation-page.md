# INEFFICIENCY: read ops (scrape/history/fetch) render the FULL conversation page, though they only need a backend-API fetch — crashes the renderer on large conversations

**Version:** ask-chatgpt 0.2.0. **Severity:** high for large conversations + any looping/perpetual use. **Type:** root inefficiency (drives renderer crashes, excess memory/CPU, and premature conversation rotation).

## Symptom
On a large conversation, `scrape` (and any read) makes Chromium **crash/hang the renderer** — surfaced as `INTERNAL_ERROR` (exit 99) / `EPIPE`. Observed 2026-06-22 on conv `6a387270…`: repeated scrapes produced **no clean read in 10 min while the system had ~9.9 GB free RAM and Chromium was only ~1.5 GB** — i.e. it is NOT system-RAM exhaustion; it's a single renderer choking on a huge DOM. (Separately, the same conversation rendered as an interactive Firefox tab reached ~9 GB.)

## Root cause
Every conversation operation acquires a tab via `TabPool.acquire(ref)` →
- `session.py:83` `url = conversation_url(ref)` → `https://chatgpt.com/c/<id>` (identity.py:124)
- `session.py:94` `channel.open_tab(url)` → `cdp.py:650` `page.goto(url, wait_until="domcontentloaded", timeout=30000)`

So the tab **navigates to the full conversation page**, and ChatGPT's SPA then renders the entire conversation DOM (hundreds of turns, long proof-trees, KaTeX, etc.) into that renderer. For a big conversation this is enormous.

**But the read ops don't need that render.** `scrape` (`session.py:512` → `capture_conversation`, `:523`), `history` (`:530`), and `fetch` (`:533`) obtain their data via an authenticated **backend API fetch**, not by reading the DOM:
- `capture.py:178` builds `/backend-api/conversation/<id>`, fetched via `JS_STREAM_FETCH` (`cdp.py:834` `page.evaluate(JS_STREAM_FETCH, …)`).

The auth context (cookies/session) is **domain-wide**, so that fetch works from *any* chatgpt.com page. Loading `/c/<id>` is only being used to get an authenticated origin — and it pays the full heavy-render cost to do so. The tool already demonstrates the lighter pattern elsewhere: `session.py:341` navigates to `https://chatgpt.com/` (light) for project flows.

## Impact
- **Renderer crashes** on large conversations (the dominant failure mode for a perpetual driver that scrapes every poll) — independent of system RAM.
- **Excess memory/CPU per read** even when it doesn't crash (rendering a multi-MB DOM just to make one API call).
- **Forces premature conversation rotation:** because reads crash on heavy conversations, the consumer must rotate to a fresh/light conversation far sooner than the conversation's actual usefulness warrants. Fixing this would let conversations grow much larger before any rotation is needed.

## Suggested fix
For **read / backend-fetch operations** (`scrape`, `history`, `fetch`, and the completion-poll path), acquire the tab on a **light page** (`https://chatgpt.com/`) and run `JS_STREAM_FETCH` from there, instead of `goto(/c/<id>)`. This makes reads ~O(1) in conversation size and eliminates the heavy-render renderer crashes. Concretely: give `TabPool.acquire` (or `open_tab`) a "light/no-render" mode for fetch-only flows, or navigate to `https://chatgpt.com/` and pass the absolute backend URL to the fetch.

`ask`/send (`session.py:349`) still needs `/c/<id>` to fill the composer — that heavy render is unavoidable there, but sends are infrequent (one per response) vs the frequent read/poll, so fixing reads removes the bulk of the cost and crashes.

## Related
`issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md` (each op also leaks a tab), `issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md`. Together these make driving a long-lived heavy conversation fragile; the light-page-read fix is the highest-leverage of the three for perpetual use.

## Resolution (2026-06-22) — FIXED on branch `fix/m10-light-read-scrape`
Resolved by M10. The diagnosis was confirmed with two corrections: (a) **only `scrape`** was an always-heavy read — `history`/`fetch`/`status` already acquire no tab; (b) the naive "open the light page" fix alone breaks the auth-header harvest (`acquire_backend_headers` waits for the page's own `GET /backend-api/conversation/<id>`, which only `/c/<id>` fires — the M7b gap-2 failure), so the fix also adds an **ambient harvest** (match any `GET /backend-api/*` carrying all 8 `REQUIRED_CAPTURE_HEADERS`) + retargets `x-openai-target-path`.

`scrape` now acquires a light `https://chatgpt.com/` tab (`TabPool.acquire(ref, render=False)`, pool keyed by `(mode,url)`); sends (`ask`/`loop`) keep `/c/<id>`; send/draft/completion harvest is unchanged (exact mode). Touches only `session.py`/`capture.py`/`channels/cdp.py` + tests.

**Verified:** best-of-N offline panel PASS; `uv run pytest` = 276 (mutation-proven). **Attended real-site leg PASS** on the crash-repro `/c/6a387270-…`: **exit 0 in 5s** (vs prior ~10-min hang/`INTERNAL_ERROR`), no renderer crash, 44 turns / 1915 nodes captured faithfully (math fidelity perfect). Evidence: `team/evidence/handoffs/M10-*`. One deferred sub-check: `scrape --with-attachments` over the light path → `issues/2026-06-22-scrape-with-attachments-light-path-unverified.md`.
