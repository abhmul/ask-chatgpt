# M19 — C-2 reactive completion via websocket-frame-idle observer (handoff)

> Lead-orchestrated (the first M19 detached manager hit the dispatch-and-yield trap; recovered by running the probe + editor + panel as lead-blocked workers). This consolidates the C-2 work for the durable record.

## 1. Status
**DONE — MERGED (PR #7) + DEPLOYED.**

## 2. Outcome
C-2 replaces the 30 s full-conversation completion poll with a **websocket-frame-idle** completion signal: completion = (no WS frame for ≥ **N=8 s**) **AND** DOM-stable. Merged via PR #7 (`64a1e72`) and deployed (installed tool reinstalled to `@64a1e72`). The full reactive set (C-1 + C-2 + C-4 + minor) is now live.

## 3. Phase 1 — calibration (real-site attended probe)
- Lead-blocked pi probe (`pi-20260623-165813`) ran 4 varied prompts in a Temporary Chat (own-tab-only, ≤4 human-paced sends, no rate modal). Recorded WS frame arrival **timing/direction/byte-length only — never payloads**.
- **max mid-answer inter-frame gap = 4.989 s** (python-fn prompt; frames arrive in bursts with multi-second pauses). → **N = ⌈4.989⌉ + 3 margin = 8 s**.
- Rule "no WS frame ≥ 8 s AND DOM-stable" validated on all 4 prompts: fires at/after every real turn-end (**no clip**), never during a mid-answer gap (**no false-early**). Worst-case added latency ~5.4 s (negligible vs multi-minute Pro responses).
- Verdict re-derived by the lead from the recorded gaps. Evidence: `team/evidence/handoffs/M19/calibration.md` (+ `calibration-raw.json`).
- **Why this approach:** M18 proved ChatGPT delivers answers over a websocket, not the HTTP send-stream (which closes ~12 s early) — see `team/evidence/handoffs/M18-c2-reactive-completion.md` + memory `chatgpt-answer-delivered-over-websocket`. WS-idle is the reactive signal.

## 4. Phase 2 — implementation (offline TDD, branch `feat/reactive-completion-ws-m19`)
2 commits: `0c8c712`/`e1ba9bf` (impl) + `64a1e72`/`a49a88a` (test-quality fix). (Local pre-merge shas `e1ba9bf`/`a49a88a`; rebased to `0c8c712`/`64a1e72` on merge.)
- **WS-idle observer** (`channels/base.py` seam, `channels/cdp.py` `_CdpWebSocketIdleObserver`, `channels/mock.py` scripted): armed before the send (`session.py:490`), subscribes to `Network.webSocketFrameReceived`/`webSocketFrameSent`, stores **only** `armed_monotonic_s` + `last_frame_monotonic_s` — **never `payloadData`** (leak-guard test pins this).
- **Wiring** (`completion.py`, `session.py`): completion = WS-idle(≥N) AND DOM-stable when armed; DOM-stable alone (fallback) when no observer. 30 s periodic full-conversation GET REMOVED; an optional **one-time** backend rescue remains (off by default, `backend_check_interval_s=None`). N configurable via `Session.websocket_idle_timeout_s` (default `DEFAULT_WEBSOCKET_IDLE_TIMEOUT_S=8.0`). C-4 governor wiring + partial-salvage preserved.
- **`uv run pytest` = 297 passed** (+5 falsifiable tests; lead re-ran). Tests: ws-idle-primary (no periodic GET), **no-false-early** (mid-gap < N must not complete), DOM-fallback, timeout-salvage-without-backend-poll, **leak-guard** (seam carries only timestamps/counts).

## 5. Verification
- **Lead smoke-check:** 297 passed (independent re-run); observer never reads `payloadData` (diff-verified); wiring correct; N configurable; salvage preserved; diff scoped; refs untouched.
- **3-lens parallel panel** (`.pi-workers/pi-20260623-173130-*`): L1 correctness/architecture **PASS**, L3 safety/leak **PASS**, L2 falsifiability **CONCERN** (CLI 429 test mislabeled "capture" — actually hits the completion-rescue path — + lost the swallow sentinel). Lead adjudicated **NON-BLOCKING** (the 429→exit-52-no-salvage behavior is still tested; capture-fetch 429 covered separately in `test_capture.py`), then **FIXED** in `a49a88a` (accurate name `test_cli_completion_rescue_429_before_later_200_...` + restored swallow sentinel).

## 6. Deploy
PR #7 MERGED 2026-06-23T23:00Z → `origin/main`=`64a1e72`. Redeploy (operator-authorized): `stable` `105b456`→`64a1e72`; `uv tool install --reinstall git+file://…` (uv confirmed `@105b456 → @64a1e72`); installed venv verified to contain C-2 (base.py WebSocketIdle, cdp.py observer, completion.py WS-idle timeout) + C-4 (governor.py) + C-1 (send.py reload-split). `main`=`stable`=`64a1e72`.

## 7. Artifacts + trust
- `team/evidence/handoffs/M19/calibration.md` (+`calibration-raw.json`) — probe data + N — **verified-independently** (lead re-derived).
- `team/evidence/handoffs/M19/authoritative-pytest.txt`, `branch.diff` — the gated suite + diff.
- Contracts `team/contracts/M19-{common,c2-ws-idle}.md`.

## 8. Blockers / signals
- None. Safety: 3 reserved real-site sends total across M18+M19, all Temporary Chat / human-paced / leak-clean, no rate modal.
- **Process lesson (recorded in RESUME + memory `claude-p-managers-block-to-completion`):** detached `claude -p` managers recurrently yield (dispatch-and-exit expecting re-invocation). For safety-critical/real-site single-leaf work, dispatch pi workers DIRECTLY from the lead (block via `pi-watch --wait-seconds`); the lead-orchestrated probe→editor→panel pattern worked cleanly.
