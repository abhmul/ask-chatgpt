# TASK T1b — channel-engineering lens (MISSION-001)

**Type:** research/engineering analysis (NON-EDITING). **Worker:** pi (GPT 5.5 xhigh). **You inherit nothing — this file is your whole world.**
**Deliverable (write EXACTLY here):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/angle-channels.md`
**Report length cap:** ~300 lines. Dense, comparative, concrete.

## The decision this mission feeds (context — do NOT decide it)

The team is building `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` that must (a) return the assistant's **response text** and (b) retrieve a **patch bundle** (a zip of only changed files) from the chatgpt.com browser UI, driven by **Playwright** (the predecessor's browser layer is Playwright). Your job is the **engineering comparison of the candidate return channels** — mechanism-level, not a final pick (you may rank, but the synthesis + team lead decide).

## Your single problem (narrow — engineering comparison only)

For **EACH of these 4 candidate channels**, produce a structured analysis:

1. **DOM extraction via selector maps** — read the rendered assistant message out of the page DOM (predecessor has selector-map infra but deliberately never used it for reads).
2. **copy-button / clipboard automation** — click the message's copy control, read the clipboard.
3. **file-download capture** — have GPT emit a downloadable file (e.g. the patch bundle as a zip / a code file), capture the browser download.
4. **connector-style callback channel** — the predecessor's MCP-connector approach (GPT calls back out to a tool/tunnel); heavyweight but proven.

For **each channel**, cover (use a consistent sub-structure so they're comparable):
- **Mechanism** — what actually happens, step by step.
- **Playwright implementation sketch** — concrete API surface (e.g. `page.locator(...)`, `page.expect_download()`, clipboard permissions/`navigator.clipboard`, CDP if needed). Ground it in the archive's existing driver patterns where possible (see pointers) rather than inventing.
- **Failure modes** — how it breaks (UI drift, async streaming not-yet-complete, truncation, clipboard permission/focus, download dialog, locale).
- **Server-visible vs purely client-side** — does using this channel produce traffic/signals the chatgpt.com server can see (account-risk relevant), or is it purely local DOM/clipboard reading? Reason explicitly; mark confidence.
- **Robustness under UI drift** — how fragile to chatgpt.com redesigns; what's the blast radius and the repair path (e.g. update a selector-map data file vs rewrite code).
- **Fit for `-> text`** (plain assistant response) and **fit for patch-bundle (zip) retrieval** — rate each separately; a channel can be good for one and bad for the other.
- **Fit for session continuity** (returning to a conversation by `session_identifier`) and **model selection** (`model_settings`) — does the channel interact with these at all?

Then: **rank the channels for (a) text retrieval and (b) bundle retrieval separately, with justification**, and note any **natural layering** (primary + fallback) the engineering suggests. Flag every claim you could NOT ground in the archive as an **empirical unknown** (operator-gated runbooks must resolve it) rather than asserting it.

## Grep-FIRST instruction (do not read whole files)

Search, then read targeted hits. Suggested seeds in the browser dir: `locator`, `selector`, `click`, `download`, `clipboard`, `copy`, `expect_`, `def ` (method names), `seed`, `send`, `wait_for`, `text`. Read `selectors.py` and `driver.py` closely (they define what's already automatable); skim `playwright_driver.py` for the real Playwright calls.

## Archive pointers (READ-ONLY: `/home/abhmul/Documents/weak-simplex-conjecture/`)

- `control-plane/src/control_plane/browser/` — `driver.py` (the `ChatUIDriver` method allowlist — what the driver can already do), `selectors.py` (the selector-map-as-data pattern you'd extend for DOM reads), `seeds.py` (seed-prompt builders), `playwright_driver.py` (the actual Playwright calls — launch/attach, locators, waits), `session.py`, `recovery.py`, `watcher.py`.
- `control-plane/tests/fixtures/phase3_mock_selector_map.json` — the mock-vs-real selector knobs (shows which selectors the system already models).
- `control-plane/DESIGN.md` — Phase-3 browser section (grep `selector`, `download`, `clipboard`, `Level B`) for design intent.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md` — real-site browser behavior notes.

## SAFETY BLOCK (obey verbatim; you inherit nothing else)

- This mission contacts NO network service. NEVER contact chatgpt.com/openai or any tunnel service. Research is file-reading only. (Do NOT run Playwright against any real site; sketch code in prose only.)
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report under `orchestration/reports/M-001/`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY; **never read its `archive/` or `human/` dirs**. Never write `.claude/` or `.agents/`.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock before any major command).
- End your report with a single-token status line: `T1b-STATUS: DONE|BLOCKED` (last line; watchers gate on `tail -1`).

## Telemetry (required in your report)

- FIRST line of your report: `ESTIMATE: T1b <minutes>m` (your up-front wall-clock estimate before starting work).
- Near the end: `ACTUAL: T1b <minutes>m` and an end timestamp from `date -Iseconds`.
- LAST line: `T1b-STATUS: DONE|BLOCKED`.
