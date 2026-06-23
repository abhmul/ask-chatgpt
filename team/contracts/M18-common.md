# Common contract — M18 C-2 reactive stream-close completion, team `ask-chatgpt-dev`

> You are the **C-2 IMPLEMENTATION MANAGER** (Opus, `claude -p`, single-shot) for team `ask-chatgpt-dev`, repo `/home/abhmul/dev/ask-chatgpt`. Read THIS file IN FULL, then `team/contracts/M18-c2-reactive-completion.md`, then the design `team/evidence/handoffs/M16-triage-reactive-traffic.md` §4 (reactive-completion feasibility) IN FULL, and the adversarial verifier's §4 analysis in `team/evidence/handoffs/M16/verify-adversarial.md`. C-2 replaces the 30 s completion poll with a native send-stream-close observer. It is **GATED on a phase-1 attended real-site probe**; do phase 1 first and **fail closed**.

## Mission shape — TWO phases, phase 2 gated on phase 1
- **PHASE 1 (real-site PROBE — the gate):** one pi worker runs an attended CDP probe to confirm the SPA send-response stream's close (`Network.loadingFinished`/Playwright `requestfinished`) coincides with turn-end. It writes a verdict: `PASS` / `FAIL` / `BLOCKED`. You BLOCK on it and read the verdict file yourself.
  - `BLOCKED` (login/Cloudflare/rate-limit-modal/browser-down) → **STOP. Do NOT implement.** Write your handoff = "PHASE-1 BLOCKED — operator action needed" with the exact blocker.
  - `FAIL` (stream-close does NOT track turn-end) → **STOP. Do NOT implement.** Write handoff = "C-2 ESCALATES to major rework — stream-close is not a reliable completion signal; re-plan" with the evidence (per M16 §4, this is the documented flip condition).
  - `PASS` → proceed to phase 2.
- **PHASE 2 (offline implementation — only if PASS):** single-editor TDD to add the stream-close observer + wire completion + keep a DOM fallback, then a best-of-N verification panel. **Entirely offline (MockChannel) after the probe.**

## Scope — EXACTLY C-2, nothing else
Replace the 30 s completion poll (full `GET /backend-api/conversation/<id>` every ~30 s, `completion.py:127-206`, called at `session.py:444`) with a **native stream-close primary completion signal**, keeping a DOM-stability fallback. Do NOT touch C-1/C-4 (already merged on `main`), the minor fix, or capture identity semantics. Do NOT implement C-3 (capture-from-stream). Branch for C-2: **`feat/reactive-completion-m18`** off `main`.

## Ground truth & environment
- `main` HEAD `105b456` (now includes C-1 reload-split + C-4 governor + minor salvage — all merged + deployed). `git rev-parse stable` = `105b456` (the tool was just redeployed to this commit). Auditing the working tree = auditing released `main`.
- Acceptance: **`uv run pytest`** (project venv `.venv`, currently **292 passed** baseline). Inspect artifacts, not exit codes.
- **Re-derive every claim from ground truth**, including M16 §4's claims (e.g. `_record_page_request_finished` is a no-op at `cdp.py:917-918`; the binding-stream `StreamState` is tool-fetch-only; `wait_for_request` consumes only request-START events). Confirm before building.
- **NEVER** `uv tool install/upgrade/reinstall` (the tool was just deployed; further redeploy is operator-reserved). **NEVER** push/merge to `main` or move/commit `stable`. Branch + commit on `feat/reactive-completion-m18` only.
- Tooling for the probe: the **PROJECT venv** via `uv run python` (has playwright 1.60.0 + the tool's own `src/ask_chatgpt/channels/cdp.py`). Do NOT use the agent-python venv for this. Do NOT `pip install`.

## REAL-SITE SAFETY for PHASE 1 (transcribe VERBATIM into the probe worker prompt — children inherit nothing; these are LOAD-BEARING, a past violation leaked operator data)
- **Attach only, never launch.** Mirror the tool's proven attach (`src/ask_chatgpt/channels/cdp.py:553,595-599`): preflight `curl -s http://127.0.0.1:9222/json/version` (expect HTTP 200 + a `webSocketDebuggerUrl`); then `playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)`. Playwright-LAUNCHED browsers are Cloudflare-blocked — attach to the operator's already-signed-in Chromium ONLY.
- **OWN-TAB-ONLY.** Open your OWN tab via `context.new_page()` (cdp.py:639 pattern) and interact ONLY with that page object. **NEVER** call `/json/list`, **never** enumerate or read or attach to pre-existing tabs/pages, **never** touch the operator's tabs. The operator and/or another agent may be using this browser concurrently — a loose tab-walker once leaked operator conversation content (memory `inspect-only-own-cdp-tab`). Record Network events ONLY from your own page's `context.new_cdp_session(page)`.
- **Temporary Chat for the send.** Navigate your tab to a **Temporary Chat** (memory-off) so the throwaway probe send does not pollute the operator's account memory (memory `real-continuity-use-temp-chats`): `https://chatgpt.com/?temporary-chat=true` (verify the temp-chat indicator before sending; if not in a temp chat, do NOT send — report BLOCKED).
- **EXACTLY ONE send**, a short throwaway prompt (e.g. `Reply with exactly: pong`). No loops, no retries, no second send. A "Too many requests" lockout happened earlier today (cleared hours ago); 1 human-paced send is minimal — but if you see the rate-limit modal / "Too many requests" at ANY point, **ABORT immediately** (record `BLOCKED:rate_limit`, close your tab, do not add volume).
- **Leak discipline.** Record ONLY: request `requestId`, HTTP method, the URL **path with query string and any id/uuid stripped** (e.g. `/backend-api/conversation` — never the full URL, never conversation ids), `resourceType`, response `status`, the CDP `eventName`, and a monotonic timestamp. **NEVER** capture or log: response bodies, request/response **header values**, cookies, auth tokens, conversation content/text, or message ids. Header NAMES and request PATHS (id-stripped) are OK.
- **Fail-closed STOP conditions** → record `BLOCKED:<reason>`, close ONLY your own tab, detach, exit non-zero, report — do NOT proceed/retry: a login page, a Cloudflare "Just a moment"/challenge, the rate-limit modal, the composer not found, or any ambiguity about whether you are on your own temp-chat tab.
- **Never quit the browser** (detach / close your own tab only). Never persist auth/cookies/headers.

## Dispatch policy (HARD RULES)
- WORKERS → pi via `bash .claude/skills/manager/references/launchers/parent-claude/pi-watch.sh [opts] "<prompt>"`. **NEVER** the Claude `Agent`/`Task` tool. Block to completion (single-shot manager). Phase-1 probe worker: `--tools read,grep,find,ls,edit,write,bash` (it writes+runs a probe script under the scratchpad/`tmp/` and writes one verdict file under `team/evidence/handoffs/M18/`). Phase-2 editor: same tools, on the branch. Verification panel: `--tools read,grep,find,ls,bash` (non-editing).
- **Verify shipment, not liveness.** Read the probe verdict file + the recorded event table yourself; re-derive the PASS/FAIL judgement from the timeline (does stream-close ≈ turn-end?), don't trust the worker's one-word claim. For phase 2, re-run `uv run pytest` yourself + inspect the diff.
- TDD (phase 2): falsifiable test first (confirm it fails pre-change), implement, green. A test that can't fail proves nothing.

## Handoff → `team/evidence/handoffs/M18-c2-reactive-completion.md`
1. **Status:** `DONE` / `PARTIAL` / `BLOCKED` (top, single token).
2. **Phase-1 probe verdict:** `PASS`/`FAIL`/`BLOCKED` + the recorded timeline (t0_send, stream request path[id-stripped], stream `requestfinished` ts, DOM turn-end ts) + your independent judgement.
3. **If implemented (phase 2):** what changed (`file:line`), the new stream-close observer + the kept DOM fallback, the falsifiable tests + proof, the `uv run pytest` summary, the verification panel + your severity adjudication, branch + commit shas.
4. **What was verified**, **Artifacts + trust**, **Blockers** (exact action), **Complexity/paradigm signals**.
Final stdout MUST contain: Status token, the probe verdict, the `uv run pytest` summary (if phase 2 ran), branch + commit shas (if any), and the handoff path.
