# Common contract — M19 C-2 via websocket-frame-idle completion observer, team `ask-chatgpt-dev`

> You are the **C-2 (re-planned) IMPLEMENTATION MANAGER** (Opus, `claude -p`, single-shot) for team `ask-chatgpt-dev`, repo `/home/abhmul/dev/ask-chatgpt`. Read THIS file IN FULL, then `team/contracts/M19-c2-ws-idle.md`, then the M18 finding `team/evidence/handoffs/M18-c2-reactive-completion.md` + `team/evidence/handoffs/M18/probe-streamclose-2.md` IN FULL (they established that ChatGPT delivers the answer over a **websocket**, the HTTP stream closes ~12 s early, and mid-answer WS frame gaps reached ~5 s). The operator chose the **full websocket-frame-idle observer** approach for C-2.

## The approach (what M18 proved + the operator chose)
Reactive completion = **observe the websocket frames** (`Network.webSocketFrameReceived`/`webSocketFrameSent`) and treat the turn as done when **WS frames have been idle ≥ N seconds AND the DOM is stable**. N must be **calibrated above the worst mid-answer inter-frame gap** (M18 saw ~5 s gaps mid-answer in one sample) or the observer fires early and clips. So: **PHASE 1 calibrates N on the real site; PHASE 2 implements** with N as configurable. Do phase 1 first and **fail closed**.

## Mission shape — TWO phases, phase 2 gated on phase 1
- **PHASE 1 (real-site CALIBRATION probe — the gate):** one pi worker runs an attended CDP probe over a SMALL set (≤4) of varied prompts, records the WS-frame **arrival timeline (timestamps + direction only — NEVER payloads)** and DOM turn-end per prompt, computes the **max mid-answer inter-frame gap**, recommends **N = max_mid_gap + margin**, and validates that the rule "WS idle ≥ N AND DOM-stable ⇒ done" detects turn-end on every sample with **no clip and no false-early**. Verdict: `PASS` (a reliable N exists + rule validated) / `FAIL` (mid-answer gaps too large/unbounded — no safe N) / `BLOCKED`. You BLOCK on it and **re-derive the verdict + N yourself** from the recorded gaps.
  - `BLOCKED` → STOP, handoff "operator action needed".
  - `FAIL` (no safe N — WS-idle can't separate mid-answer pause from turn-end) → STOP, handoff "WS-idle not viable; recommend the lightweight-`stream_status`-poll fallback or keep the governed 30 s poll" (do NOT implement).
  - `PASS` → phase 2 with the calibrated N.
- **PHASE 2 (offline implementation — only if PASS):** single-editor TDD adds the WS-frame-idle observer + wires completion + keeps a DOM fallback, then a best-of-N verification panel. **Entirely offline (MockChannel) after the probe.**

## Scope — EXACTLY C-2 (WS-idle), nothing else
Replace the 30 s full-conversation completion poll (`completion.py:127-206`, called `session.py:444`) with a **websocket-frame-idle primary completion signal** (idle ≥ N + DOM-stable), keeping a DOM-stability fallback (and optionally ONE low-rate backend rescue, not a periodic poll). Do NOT touch C-1/C-4/minor (merged + deployed on `main`). Do NOT implement C-3. Branch: **`feat/reactive-completion-ws-m19`** off `main`.

## Ground truth & environment
- `main` HEAD `105b456` = `git rev-parse stable` (C-1 reload-split + C-4 governor + minor salvage are merged AND deployed; the installed tool runs this). Acceptance **`uv run pytest`** (project venv, **292 passed** baseline). Inspect artifacts, not exit codes.
- **Re-derive every claim from ground truth.** Confirm the M18 finding from its evidence files; confirm `_record_page_request_finished` is a no-op (`cdp.py:917-918`), the CDP session/Network seam (`cdp.py:892-902`), and how `wait_for_completion` is called (`session.py:444`).
- **NEVER** `uv tool install/upgrade/reinstall` (redeploy is operator-reserved). **NEVER** push/merge to `main` or move/commit `stable`. Branch + commit on `feat/reactive-completion-ws-m19` only. Never touch `human/`/`archive/`/`issues/cdp-send-repro/controller.mjs`.
- Probe tooling: PROJECT venv via `uv run python` (playwright 1.60.0 + `src/ask_chatgpt/channels/cdp.py`). NOT the agent-python venv. No `pip install`.

## REAL-SITE SAFETY for PHASE 1 (transcribe VERBATIM into the probe worker prompt — children inherit nothing; LOAD-BEARING)
- **Attach only, never launch.** Preflight `curl -s http://127.0.0.1:9222/json/version` (expect 200 + `webSocketDebuggerUrl`); then `playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)` (mirror `cdp.py:553,595-599`). Playwright-launched browsers are Cloudflare-blocked — attach to the operator's signed-in Chromium only.
- **OWN-TAB-ONLY.** Open your OWN tab via `context.new_page()` and interact ONLY with it. NEVER call `/json/list`, never enumerate/read/attach to other tabs, never touch operator tabs (a past tab-walker leaked operator conversation — memory `inspect-only-own-cdp-tab`). Network/WS events ONLY from your own page's `context.new_cdp_session(page)`.
- **Temporary Chat** for all sends (`https://chatgpt.com/?temporary-chat=true`; verify the temp-chat indicator before sending — memory `real-continuity-use-temp-chats`).
- **≤4 sends total, human-paced** (≥5 s between sends), short/medium prompts only (each answer should finish in seconds–~30 s). No loops beyond the ≤4 calibration prompts. If you EVER see "Too many requests"/a rate modal → `BLOCKED:rate_limit`, close your tab, STOP, do not add volume.
- **WS-PAYLOAD-LEAK RULE (critical):** `Network.webSocketFrameReceived`/`webSocketFrameSent` carry the **answer content** in `response.payloadData`. Record ONLY: `{eventName, direction, monotonic_ts, opcode, payload_LENGTH_in_bytes}`. **NEVER read, log, store, or echo `payloadData` / frame text.** For HTTP requests record only id-stripped path/method/status/resourceType/ts (as in M18). NEVER bodies, header values, cookies, conversation text, or message ids.
- **Fail-closed STOP** (record `BLOCKED:<reason>`, close own tab, detach, report) on: login page, Cloudflare challenge, rate modal, composer not found, or any ambiguity about being on your own temp-chat tab. Never quit the browser; never persist auth/cookies.

## Dispatch policy (HARD RULES)
- WORKERS → pi via `pi-watch.sh`; NEVER the Agent/Task tool; block to completion (single-shot manager). Probe worker + phase-2 editor: `--tools read,grep,find,ls,edit,write,bash`. Verification panel: `--tools read,grep,find,ls,bash` (non-editing).
- **Verify shipment, not liveness:** read the probe's recorded gap data + verdict yourself; re-derive N + the PASS/FAIL from the gaps. For phase 2, re-run `uv run pytest` + inspect the diff. TDD: falsifiable test first (confirm it fails pre-change), implement, green.

## Handoff → `team/evidence/handoffs/M19-c2-ws-idle.md`
1. **Status:** `DONE`/`PARTIAL`/`BLOCKED` (top, single token).
2. **Phase-1 calibration:** verdict + the recorded per-prompt gap data (max mid-answer gap, turn-end deltas), the chosen **N + margin**, and your independent validation that idle≥N + DOM-stable detects turn-end with no clip/false-early.
3. **If implemented (phase 2):** the WS-idle observer (`file:line`), the DOM fallback kept, the **leak-safe** frame observation (timing/length only — show the code never touches `payloadData`), the falsifiable tests + proof, the `uv run pytest` summary, the verification panel + your severity adjudication, branch + commit shas.
4. **What was verified**, **Artifacts + trust**, **Blockers**, **Complexity/paradigm signals**.
Final stdout MUST contain: Status, the calibration verdict + N, the `uv run pytest` summary (if phase 2), branch + commit shas, and the handoff path.
