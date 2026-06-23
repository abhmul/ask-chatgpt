# M18 C-2 — reactive stream-close completion (handoff)

## 1. Status
**BLOCKED** — phase-1 PASS-gate **FAILED**. **C-2 ESCALATES to major rework — HTTP send-response stream-close is NOT a reliable completion signal; re-plan required.** The documented M16 §4 flip condition has fired. Phase 2 (implementation) was correctly **not started** (gated). Branch `feat/reactive-completion-m18` was **not** created; `main` is untouched at `105b456`; `src/` is clean.

## 2. Phase-1 probe verdict: **FAIL** (re-derived independently from the recorded timelines, not trusted on the workers' word)

### 2.1 Why two probes
Probe 1 (throwaway send `Reply with exactly: pong`) was **inconclusive on inspection**: the HTTP send-response stream `POST /backend-api/f/conversation` closed at **+3.984 s** while the probe's DOM completion gate fired at **+18.336 s**, and `t_first_token`=+1.157 s was recorded *before* the HTTP stream's `responseReceived`=+1.933 s (physically impossible if the answer rode that HTTP stream). That pattern is the signature of a confounded reference, not a clean result — and memories `real-discovery-false-negatives` / `real-completion-clips-short-multiturn` warn that short-answer DOM completion gates mismeasure. A one-word "FAIL" from a confounded probe is **not** sufficient evidence to escalate a whole milestone. So I ran a second, disambiguating probe (one human-paced send, ~13 min later) with: a **longer streaming answer** (`Count from 1 to 60, one number per line`), **websocket/eventSource instrumentation**, and **last-text-growth** (`t_lastgrowth`) as the turn-end reference instead of the flaky 3 s-stability gate.

### 2.2 Probe 2 — the definitive evidence (delivery is over a WEBSOCKET)
Raw timeline (relative to `t0_send`; full id-stripped event table in `team/evidence/handoffs/M18/probe-streamclose-2.md`):

| signal | time (s rel t0) | source |
|---|---:|---|
| `webSocketCreated` (req `…555`) | −0.121 | CDP `Network.webSocketCreated` |
| HTTP `POST /backend-api/f/conversation` opens (`responseReceived`) | +2.379 | the M16 §4 / C-2 target stream |
| **HTTP `POST /backend-api/f/conversation` CLOSES (`loadingFinished`)** | **+4.237** | the primitive C-2 was specified to use |
| WS frames received (req `…555`) | +0.443, +3.185, +4.08, +4.24, +4.36, **+9.195, +9.304, +14.341, +14.455, +16.277, +16.357, +16.421, +16.899, +17.052, +17.107** | `Network.webSocketFrameReceived` (counts/ts only; no payloads) |
| DOM answer first grows (`t_firstgrowth`) | +1.210 | DOM text length |
| **DOM answer LAST grows (`t_lastgrowth`)** | **+16.428** | DOM text length (corroborated by WS frames to +17.1) |
| DOM 3 s-stability gate (`t_domdone_stable`) | +20.007 | old heuristic (kept for comparison) |

**Independent re-derivation.** The HTTP `POST /backend-api/f/conversation` carries the message *submission* and closes at **+4.237 s**. The visible answer keeps growing until **+16.428 s**. For the answer to grow after +4.237 s, tokens must arrive on some channel open in (+4.237, +16.428]; the **only** content-bearing channel active in that window is the **websocket** `…555` (frames at +9.195 … +17.107). No other fetch/SSE stream is open carrying content (the rest are `sentinel/ping`, conversations-list, `lat/r`, `textdocs`→404, and a post-turn `f/conversation/prepare`). Two **independent** signals — DOM text growth and WS frame arrivals — agree the turn ends ~+16.4–17.1 s, while the HTTP POST closed ~12 s earlier. **Therefore `Network.loadingFinished`/`requestfinished` on the conversation HTTP request fires ~12 s before turn-end and would clip every non-trivial answer.** This is a genuine FAIL of the specified primitive, not a DOM-gate artifact.

*(Note on the probe-2 worker's own `STATUS: FAIL`: it reached FAIL but via a noisy candidate-picker that mislabeled the post-turn `f/conversation/prepare` (close +17.198) as "the stream" and called it "ambiguous." Its conclusion direction is right; my re-derivation above replaces its stream-identity reasoning with the websocket finding, which is the real cause.)*

### 2.3 Reconciliation with probe 1
With the WS finding, probe 1 is explained: `pong` was also delivered over the websocket; the HTTP `f/conversation` close (+3.984) happened to be near the tiny answer's end *by coincidence of brevity*, and the DOM gate (+18.336) over-waited on post-turn churn. The longer answer in probe 2 removed the coincidence and exposed the ~12 s gap. Probe 1 alone could not distinguish "stream-close premature" from "DOM gate late"; **probe 2 settles it: stream-close (HTTP) is premature because the answer is on the websocket.**

## 3. Phase 2 — NOT performed (correctly gated)
No code written, no tests, no `uv run pytest` run for C-2, no branch, no commits. Nothing in `src/` changed.

## 4. What was verified (from ground truth)
- **CDP environment up:** `curl /json/version` → HTTP 200 + `webSocketDebuggerUrl` (probe preflights passed both times).
- **Ground-truth anchors (re-derived from source before dispatch):** `main`=`stable`=`HEAD`=`105b456`; `completion.py` 30 s poll = full `GET /backend-api/conversation/<id>` (`completion.py:42,46,159-162`, called `session.py:444`); `_record_page_request_finished` is a literal no-op (`cdp.py:917-918` `del tab_id, request`); `_install_cdp_observers` registers only `Network.requestWillBeSent`/`requestWillBeSentExtraInfo` then `Network.enable` (`cdp.py:889-903`) — no finish/response/WS listener today; attach pattern `connect_over_cdp`+`contexts[0]` (`cdp.py:595-599`), own tab via `context.new_page()` (`cdp.py:639`). All M16 §4 claims confirmed.
- **The probe's core claim (re-derived by me, twice):** the assistant response on the operator's account is delivered via a **websocket**; the conversation HTTP POST closes ~12 s before turn-end → the C-2 primitive (`loadingFinished`/`requestfinished` on the HTTP stream) is **disproven** as a completion signal.

## 5. Artifacts + trust
- `team/evidence/handoffs/M18/probe-streamclose.md` — probe 1 (pong); full id-stripped event table + timeline — **verified-independently** (re-derived; inconclusive-alone, see §2.1).
- `team/evidence/handoffs/M18/probe-streamclose-2.md` — probe 2 (count-to-60, WS-instrumented); full id-stripped event table + timeline — **verified-independently** (the load-bearing evidence; WS-delivery re-derived from raw events by me).
- Scratch probe scripts under `/tmp/m18-probe/` (out of repo). No `src/` changes.

## 6. Blocker — exact action required (level above / operator decision: RE-PLAN C-2)
The C-2 approach as scoped (replace the 30 s poll with HTTP send-response stream-close) **cannot ship** — it would silently clip answers. A re-plan must choose a completion signal that works under **websocket delivery** (the operator's account's mode). Candidate directions, with open questions, for a fresh design+probe mission:

1. **Websocket-frame observer (most promising, but a different and harder design than C-2-as-specified).** Watch CDP `Network.webSocketFrameReceived` on the answer WS; define turn-end as **WS frames idle for ≥ N s** and/or a detectable terminal frame. Open questions the re-plan MUST resolve with its own attended probe: (a) is "frames idle ≥ N s" reliable, and what is N? (this reintroduces a stability-window heuristic, partially the very thing C-2 meant to eliminate); (b) can the terminal/"done" frame be detected **without reading frame payloads** (payloads carry answer text — a leak risk; an observer that parses them needs the same leak discipline as capture); (c) Playwright exposes WS frames via `page.on("websocket")`/`ws.on("framereceived")` or the CDP `Network.webSocket*` events — a **new** channel seam, not the `wait_for_request`/`loadingFinished` seam M16 §4 sketched.
2. **`/backend-api/conversation/:id/stream_status` as a lighter rescue poll.** Observed at +2.559 s (GET, 200). M16 §4 established the current poll uses the **full** conversation GET and the `stream_status` branch is **dead code** (`prefer_lightweight` never set). A re-plan could **revive `stream_status`** as a low-rate, lightweight completion check (far cheaper than the full conversation GET) even if a pure reactive signal proves unreliable — a meaningful traffic win short of full reactivity.
3. **Keep the DOM-stability fallback regardless** (the M16 §4 plan already required this) — but note probe data shows the DOM gate over-waits on short answers; pair it with the WS-idle signal rather than relying on it alone.
4. **Interim:** the existing 30 s full-conversation poll (`completion.py:127-206`) remains the only currently-reliable completion mechanism across delivery modes; do **not** remove it until a replacement is probe-validated. (C-1 reload-split and C-4 governor on `main` are unaffected by this finding.)

The HTTP-finish wiring M16 §4 proposed (turning the `cdp.py:917-918` no-op into a finish recorder) may still be useful for **header-harvest/observation**, but is **not** a completion signal — record this so the next mission doesn't re-attempt it as one.

## 7. Complexity / paradigm-shift signal
**Paradigm shift confirmed by ground truth:** the assistant stream is **websocket-delivered** on the operator's account, not SSE-over-fetch. This invalidates the M16 §4 assumption that a single HTTP request's `loadingFinished` marks turn-end. Reactive completion is **still plausible** but via a websocket-frame observer — a materially more complex seam (new WS observation surface; a frames-idle stability heuristic; payload-leak considerations) than the "wire the existing finish event" surgical change C-2 assumed. This is the "moderate → major" completion-model escalation M16 §4 named as the flip risk. Recommend the re-plan run a dedicated **WS-idle turn-end probe** (attended, one send, longer answer) to fix N and confirm reliability before any implementation. Delivery mode *may* vary by account/feature-flag; the design must handle WS delivery because that is what the deployment target uses.

## 8. Real-site safety attestation (phase 1)
Two attended probes, **exactly one throwaway send each** (`pong` at ~16:02, `count to 60` at ~16:15 — human-paced, hours after the earlier cleared lockout; both completed, **no rate-limit modal**). Both: attach-only (`connect_over_cdp`), **own tab only** (`context.new_page()`; never enumerated/touched other tabs; no `/json/list`), **Temporary Chat** verified before sending, **fail-closed** handlers in place. **Leak discipline honored:** event tables contain only id-stripped paths, CDP `requestId`s, methods, resource types, statuses, event names, monotonic timestamps; **no bodies, no header values, no cookies, no conversation text, no message/conversation ids, and (critically) no websocket/SSE frame payloads** (WS/SSE rows record only `eventName|requestId|ts`). Browser never quit (own page closed + `pw.stop()` only).
