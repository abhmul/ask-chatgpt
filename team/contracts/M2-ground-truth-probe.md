# Mission M2 — Attended ground-truth CDP probe (READ-ONLY, OWN-TAB-ONLY)

You are a **pi WORKER** for the `ask-chatgpt-dev` team. Execute this mission exactly. You inherit nothing but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`.

## Mission
Verify the load-bearing ground-truth assumptions behind the `ask-chatgpt` rewrite design (`docs/REWRITE-SPEC.md` §5, §7, §11, §16 — read them) against the LIVE chatgpt.com, attached over CDP to the operator's signed-in Chromium at `http://127.0.0.1:9222`. The single most important question: **is the in-page authenticated backend endpoint a viable, faithful capture source?** Plus: discover the live UI selectors. This is RECONNAISSANCE — read-only, no source changes, no commits.

## ⚠️ CRITICAL SAFETY — the browser is SHARED with another active agent (read twice)
- The Chromium at `:9222` is the operator's, and **ANOTHER AGENT IS USING IT RIGHT NOW**. A prior probe LEAKED another agent's private conversation into a committed artifact by walking all tabs. DO NOT repeat it.
- **Operate ONLY on a tab/page YOU create** (`context.new_page()`). NEVER call/iterate `context.pages` to touch existing tabs. NEVER read, navigate, click, screenshot, or dump any page you did not open. If you cannot create your own page, STOP and report BLOCKED — do NOT touch an existing tab.
- The ONLY conversation you may read is the operator's authorized scrape target: conversation id **`6a316aa8-5dc8-83ea-9014-b8ea38dabc31`**. Do NOT read or reference any other conversation.
- **NEVER quit/close the browser** (detach only). You MAY close YOUR OWN tab when done.
- **No sends, no new turns, no message submission.** The probe is pure reads + opening menus in your own tab. Do not consume the account or disturb the other agent.
- **No stealth/anti-detection.** Allowlist domains only (`chatgpt.com`, `openai.com`). If a login wall / Cloudflare "Just a moment" challenge appears → STOP, report `HUMAN-ACTION-NEEDED`.
- Preflight: `curl -s --max-time 5 http://127.0.0.1:9222/json/version`. If it fails → STOP, report `CDP_UNREACHABLE`.
- In findings, report STRUCTURE + tiny redacted samples only — NEVER paste large conversation content. Math-presence checks: report booleans/counts (e.g. "content contains `\\widehat`: true"), not the math itself beyond a token or two.

## Environment
- Use Playwright (Python) via `uv run --with playwright python <script>` — this guarantees playwright is available regardless of the freshly-scaffolded pyproject. Attach with `playwright.sync_api.sync_playwright().chromium.connect_over_cdp("http://127.0.0.1:9222")`. connect_over_cdp does NOT launch a browser — it attaches to the running one.
- Write your throwaway probe script under `tmp/m2-probe/` (gitignored). Do NOT add it to git. Do NOT modify any tracked source file. Do NOT commit anything.

## Probe objectives (record findings for each)
1. **Backend-api capture (THE load-bearing test).** In your own chatgpt.com tab, run an in-page authenticated fetch for the scrape conversation:
   `await fetch('/backend-api/conversation/6a316aa8-5dc8-83ea-9014-b8ea38dabc31', {headers:{accept:'application/json'}})`.
   Report: HTTP status; whether it returns JSON; the top-level keys; the message-tree shape (`mapping`, `current_node`, per-node `message.content.content_type` + `content.parts`); whether assistant `content.parts` is **canonical markdown** (look for markdown/LaTeX: does it contain `\widehat`, `\frac`, `\ne`/`\neq`, `$`/`\(` math delimiters?). Confirm CONFIRMED/REFUTED: "the endpoint returns faithful canonical markdown including math." If the path 404s, try the path the web app actually uses (observe via DevTools-style: you may read your OWN tab's network if Playwright exposes it) and report the real path. Note pagination if the conversation is large (is the whole tree in one response?).
2. **Deep Research turn representation.** Find a DR turn in that conversation's JSON (the conversation is known to contain Deep Research). Report how it differs: `content_type`, where the report body lives, how citations + search metadata are represented, any artifact/file references.
3. **Attachments/files.** How are downloadable artifacts (generated images, code-interpreter files, the "download" links) referenced in the JSON (file ids, `/backend-api/files/...` URLs)? Report the reference shape (not the bytes).
4. **Live UI selectors (open a fresh new chat in YOUR tab — chatgpt.com root — do NOT send anything).** Record ACTUAL current selectors for: composer (`#prompt-textarea`?), send button, the new-user-turn markers (`data-message-id`, `data-message-author-role`), the assistant streaming/stop button, the per-turn copy button. Then OPEN (click) the model-picker menu and enumerate options in the Radix portal (`[data-radix-popper-content-wrapper] [role=menuitemradio]` tiers + any `menuitem` family submenu) — list the model labels you see (e.g. Pro Extended, GPT-5.5, Instant…). Then OPEN the tools/"+" menu and enumerate its items (Deep Research, Web search, Agent mode, connectors…). Opening menus is read-only; do NOT select/submit. Close menus when done.
5. **Clipboard fallback viability.** Report whether `navigator.clipboard.readText()` is reachable from the page context over CDP (it may need a permission grant) — feasibility only; we won't depend on it.
6. **Project mechanics (best-effort, no guessing).** If you can confirm anything about project-chat URL handling (`/g/g-p-<projid>/c/<chatid>`) without reading another agent's tabs, report it; otherwise note "deferred — needs an operator-provided project URL." Do NOT hunt through existing tabs.

## Output — write findings to `team/evidence/handoffs/M2-ground-truth-probe.md`
Structure: (1) **Status** `DONE`/`PARTIAL`/`BLOCKED` on line 1; (2) **Preflight** (curl result); (3) **Backend-api verdict** — CONFIRMED/REFUTED with the exact working endpoint, response shape, and the math-faithfulness booleans (this is the headline result the design depends on); (4) **DR representation**; (5) **Attachments reference shape**; (6) **Selectors** — a clean, machine-usable list (selector name → CSS) that M5 can drop into the new `real.json`, plus the enumerated model + tool labels; (7) **Clipboard viability**; (8) **Project notes**; (9) **Blockers**; (10) **Recommended design adjustments** (especially if the backend-api hypothesis is REFUTED — then the capture path falls back to copy-button/annotation and the design changes). Do NOT commit; the team lead ingests + commits your findings.

## Acceptance bar
A clear CONFIRMED/REFUTED verdict on the backend-api capture hypothesis, backed by the actual observed response shape (structure + redacted samples) and math-faithfulness booleans; a clean selectors list; zero interaction with any tab you did not open; zero sends; browser left running (detached). Report honestly — PARTIAL/BLOCKED with specifics if you couldn't safely complete a step. NEVER overclaim, and NEVER leak another tab's content.
