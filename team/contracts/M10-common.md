# M10 — COMMON CONTEXT (mandatory shared reading for every M10 worker)

You are a worker on the `ask-chatgpt-dev` team. You inherit **nothing** except this
file and your lens contract. Read **this entire file** first, then your lens
contract, then execute. Everything you need is written here explicitly; there are
no implied links.

## The mission (M10)
Investigate and debug the inefficiency filed in
`issues/2026-06-22-read-ops-render-full-conversation-page.md` (READ IT IN FULL):
read operations navigate the browser tab to the **full conversation page**
`https://chatgpt.com/c/<id>`, forcing ChatGPT's SPA to render the entire
conversation DOM — which crashes/hangs the renderer on large conversations — even
though the read data is obtained via an authenticated **backend-API fetch**, not by
reading the DOM. The proposed fix is to do read/backend-fetch ops from a **light
page** (`https://chatgpt.com/`) instead.

This phase (T1) is **investigation only — NO code edits.** Your job is to
independently re-derive the diagnosis from ground truth (the code), confirm or
**refute** the lead's pre-verified findings below, and (per your lens) design the
fix. A later phase implements it.

## Repository ground truth (verify; do not assume)
- Branch `main`, version `0.2.0`. Source under `src/ask_chatgpt/`.
- **`cdp.py` lives at `src/ask_chatgpt/channels/cdp.py`** (NOT `src/ask_chatgpt/cdp.py`).
  The issue's "cdp.py:NNN" line numbers refer to `channels/cdp.py`.
- Key files: `session.py`, `channels/cdp.py`, `capture.py`, `identity.py`,
  `completion.py`, `cli.py`, `store.py`.

## Lead's PRE-VERIFIED findings — treat as HYPOTHESES to independently confirm/refute (cite file:line)
The lead already traced this. Re-derive each from the code yourself; if any is
wrong, say so loudly with evidence — falsifiability is the point.

1. **Tab acquisition is the heavy step.** `TabPool.acquire(ref)` (`session.py:82`)
   always computes `url = conversation_url(ref)` → `https://chatgpt.com/c/<id>`
   (`identity.py:113`,`:124`) and calls `channel.open_tab(url)` (`session.py:94`)
   → `page.goto(url, wait_until="domcontentloaded", timeout=30000)`
   (`channels/cdp.py:650`). The pool caches entries keyed by that exact URL.
2. **Only FOUR call sites acquire a pool tab:** `ask` (`session.py:366`, a SEND —
   needs `/c/<id>` to fill the composer), `scrape` (`session.py:521`, a READ),
   `loop` (`session.py:579`, a SEND loop). (Plus the internal `open_tab` at
   `:94`.) **HYPOTHESIS H1: `scrape` is the ONLY always-heavy READ op.**
3. **HYPOTHESIS H2: `history` (`session.py:530`) and `fetch` (`session.py:533`)
   acquire NO tab** — they are pure local-store reads
   (`self.store.load_transcript(...)`). If true, the issue is WRONG that
   history/fetch render the page. CONFIRM OR REFUTE with code.
4. **The capture data path is backend-API, not DOM.** `capture_conversation`
   (`capture.py:300`) → `acquire_backend_headers` (`capture.py:140`) +
   `stream_backend_conversation` (`capture.py:171`) → `tab.channel.fetch_in_page`
   runs `JS_STREAM_FETCH` (`channels/cdp.py:50`, evaluated at `:834`) against
   `/backend-api/conversation/<id>`.
5. **THE CRUX (why the naive fix is incomplete).** `acquire_backend_headers`
   waits (`wait_for_request`, `capture.py:149`) for the page to ITSELF issue a
   GET whose path **exactly equals** `/backend-api/conversation/<id>`
   (`matches()`, `capture.py:144-146`), then harvests the 8
   `REQUIRED_CAPTURE_HEADERS` from it. The SPA only issues that request because
   the tab navigated to `/c/<id>`. So navigating to the light root page and
   reusing this harvest verbatim would **fail with `BackendAuthUnavailableError`**
   — this is exactly the historical **M7b gap-2** failure (read
   `team/evidence/handoffs/M7b-gaps.md`). The fix must therefore ALSO change the
   harvest to work on a light page.
6. **`REQUIRED_CAPTURE_HEADERS` (`capture.py:39`)** = `authorization`,
   `oai-client-build-number`, `oai-client-version`, `oai-device-id`,
   `oai-language`, `oai-session-id`, `x-openai-target-path`,
   `x-openai-target-route`. **Open subtlety:** `x-openai-target-path` /
   `x-openai-target-route` may be **request-specific** (edge-routing headers tied
   to the request's path), unlike the others which look domain/session-global.
   `stream_backend_conversation` (`capture.py:171-187`) reuses the harvested
   bundle via `HeaderBundle.for_single_fetch()` — check whether that recomputes
   `x-openai-target-path` for the fetched URL or passes the harvested value
   verbatim.

## Acceptance / verification baseline
- Acceptance command: **`uv run pytest`** (uses the PROJECT venv `.venv` via uv —
  separate from the uv tool install and from the agent-python venv). Mock suite is
  the default tier; `real_site` tests are deselected by default
  (pyproject `addopts -m "not real_site"`) AND gated on env `ASK_CHATGPT_REAL=1`.
- **Re-derive verdicts from inspected output/artifacts, NEVER from exit codes
  alone** (a wrapper exit 0 once masked a pytest failure).

## Hard safety rules (NON-NEGOTIABLE — this is an attended real account)
- **READ-ONLY this phase: modify NO source or test file.** Write ONLY your single
  handoff file (path in your lens contract). Do not `git add`/commit/stash/checkout.
- **OFFLINE ONLY: no browser, no network to chatgpt.com / openai.com.** Do NOT run
  `ask`, `scrape`, `history`, `export`, or any real-site leg. Pure code analysis.
- **Do NOT read `cache/` conversation content, `archive/`, or `human/`** (per
  `AGENTS.md`) — they are not needed for this analysis.
- Never move/commit the git `stable` ref; never run `uv tool install/upgrade/reinstall`.
- If you run ad-hoc Python you MUST first read
  `~/Documents/vaults/agent-vault/agent-python/README` and use that venv — but this
  investigation needs none; prefer `grep`/`read`.
- Never print/log auth tokens, cookies, OAI header VALUES, or conversation content.

## Handoff protocol (write your lens's handoff file; this is your only output)
Structure, in order:
1. **STATUS:** `DONE` / `PARTIAL` / `BLOCKED` (single token, top of file).
2. **Findings**, each with **file:line evidence** and a CONFIRM/REFUTE verdict on
   the relevant hypotheses above. Quote the decisive code lines.
3. **Answers to your lens's required questions** (in your lens contract).
4. **Risks / unknowns**, especially anything only a real-site probe can settle.
5. **Recommended next steps** for implementation + verification.
Keep it tight and evidence-dense. No source edits. Verify, don't trust.
