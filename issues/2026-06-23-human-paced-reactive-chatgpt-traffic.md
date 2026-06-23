# Issue: ask-chatgpt generates non-human, polling-heavy chatgpt.com traffic → rate-limit lockouts. Redesign toward human-paced, reactive interaction.

- **Filed:** 2026-06-23 (team-lead-v2 session, after a live "Too many requests" lockout during unattended driving)
- **Severity:** HIGH — caused a real ChatGPT rate-limit ("Too many requests") that blocked driving for ~30–50 min and corrupted capture; this is the main blocker to *reliable long-running / unattended* operation.
- **Status:** OPEN — design + implementation needed. **Another agent picks this up.** This file is self-contained (inherits nothing): code paths, measured intervals, evidence, constraints, and acceptance are all transcribed below.
- **Primary area (the tool):** `src/ask_chatgpt/completion.py` (completion detection), `src/ask_chatgpt/session.py` (session/tab lifecycle), `src/ask_chatgpt/capture.py` (capture), `src/ask_chatgpt/channels/cdp.py` (CDP/streaming seam).
- **Secondary area (the external driver rig, operator's experimental harness, gitignored):** `tmp/weak-simplex-push/driver/driver.sh` (+ `supervisor.sh`, `rotate.sh`).

---

## 1. Problem statement
When driving a ChatGPT Pro conversation for a long time, `ask-chatgpt` (and the driver rig built on it) emit **far more chatgpt.com traffic than a human would**, in a **polling, page-reload pattern** that does not resemble a person using ChatGPT. This tripped ChatGPT's **"Too many requests"** limit. The goal: **reshape our request/interaction pattern to look like a human using the web UI** — one open tab, occasional sends, reactive (event-driven) completion detection, human pacing — and add a request-rate ceiling so we never trip the limit.

**Litmus test for "done":** if OpenAI inspected our traffic, it should look like *a person using ChatGPT in a browser*, not a bot.

---

## 2. Motivating incident (evidence)
- Overnight 2026-06-23, the driver drove conv `6a387270-c3b0-83ea-991f-81085a2eeb9b` (grew undriveable at ~4500 nodes) → **rotated** to `6a3a6268-da78-83ea-9b23-7dc1731976ac` (light) and kept pushing.
- ~10:15 & ~10:55: driver hit **exit 21 HUMAN-ACTION-NEEDED**. Root cause (from `ask.err`): backend-api **capture failed (`INTERNAL_ERROR`)** → tool fell back to clipboard capture → `clipboard fallback requires explicit permission`. The backend failures were the rate-limiter biting.
- ~11:20: operator independently saw **"Too many requests"** on `6a3a6268` (in the ChatGPT app). Driver was **paused** (`touch STOP`) at ~11:38 to stop adding request volume.
- ~12:13: after ~30–50 min of **full silence** (no driver, no supervision scrapes), a single scrape **succeeded (exit 0)** → limit had **cleared**. Operator confirmed the chat was functional again once polling stopped.
- Operator conclusion (correct): *"our scraping and API calls were causing the issue… ideally we don't poll; our scraping/API calls should be reactive… if we must poll, make it large (300 s scrape, 120 s completion)."*

Contributors to the cumulative volume over ~8.5 h of driving: ~36 send turns + per-poll scrapes + ~5 driver bounces (each restarts the scrape loop) + 1 rotation + (early) lead supervision/diagnostic scrapes. Each scrape/ask **navigates a page**, which makes ChatGPT's SPA fire its **own** `/backend-api/*` burst.

---

## 3. Findings — where the requests come from (grounded in code)

| # | Source | Where | Rate | Notes |
|---|--------|-------|------|-------|
| 1 | **Per-turn fresh tabs** (page reloads) | `session.py:TabPool.acquire` (`:84`); `ask` acquires a tab **per call** (`:370`); driver spawns a **new `ask` process per turn** + **new `scrape` process per poll** (`driver.sh:run_ask :188`, `run_scrape :106`) | every turn + every poll | **Dominant non-human signal.** Each `acquire` navigates a page → ChatGPT SPA fires its full `/backend-api/*` load-burst, then the tab is closed (`detach`/`close_all`). Repeated page-loads ≠ human. |
| 2 | **`/stream_status` completion polling** | `completion.py:poll_backend_completion` (`:37`, path `:46`), driven by `wait_for_completion`/`poll_until_complete` (`:127`); interval `_backend_interval = max(progress_poll×2, 30) = 30 s` (`:470`) | **every 30 s** for the whole response (~80 calls per 40-min response) | A human/SPA never polls status — the **SSE stream closing** is the completion signal. |
| 3 | **DOM progress poll** | `completion.py` `progress_poll_interval_s = 2.0` | every 2 s | This is a **CDP `Runtime.evaluate`** (reads the already-loaded page), **not** a chatgpt API HTTP request — so it's not API volume, but it is extra interaction. |
| 4 | **Driver `wait_until_idle` scrape-poll** | `driver.sh` `wait_until_idle` (`run_scrape` every `idle_poll_interval_s`) | every 90 s (now 300 s) | Extra **page-loads** purely to detect "is Pro done" — redundant with `ask`'s own completion detection. |
| 5 | (Now mitigated) lead **supervision/diagnostic scrapes** | manual | sporadic | Each a page-load. Lead now monitors via the driver's **local output files only** (zero chatgpt requests). |

A *single* `scrape` itself makes only ~1 explicit API fetch (`capture.py:stream_backend_conversation :199` → one `GET /backend-api/conversation/<id>`; +2 per attachment in `download_attachments :378`). The volume is **not** per-call thrash — it's (a) **how often we load a page** (each triggers an SPA burst) and (b) the **30 s `/stream_status` polling** during every response.

---

## 4. Target: what human (SPA) traffic looks like
- **One page-load per session** (SPA boot → one `/backend-api/*` burst: `me`, `conversations`, `models`, the conversation), then **the tab stays open**.
- **Per turn:** one `POST` (send) → **one long-lived SSE stream** delivers the response; when the **stream closes**, the turn is done. No status polling, no reloads.
- **Human pacing:** seconds-to-minutes of reading/thinking between turns; never instant machine-gun sends.

---

## 5. Redesign (3 layers)

### Layer A — Lead (the human-interface agent): already reactive
Monitor only via the driver's **local output files** (`status.json`, `driver.log`, the driver's own `../ask-data` raw-mapping) — **never scrape chatgpt to monitor**. No timed self-wakeup polling. (Already in place; documented in `team/state/RESUME.md`.) **No code change.**

### Layer B — Driver: hold ONE persistent session instead of per-turn processes
The "fresh `ask` + `scrape` process per turn/poll" model is the main page-load amplifier (Finding #1, #4). Replace it with **one long-lived session that keeps a single tab open across turns**. The tool's **`loop` command already does this** — `session.loop` (`session.py:563`) calls `acquire` **once** (`:583`) and reuses the tab across iterations (vs `ask` re-acquiring per call). So:
- Drive via a **persistent `loop`** (or a long-lived library session), not repeated `ask`/`scrape` CLI processes. This **eliminates per-turn page-loads and the `wait_until_idle` scrape-poll**.
- The driver becomes a thin supervisor reading the loop's output (model-guard, milestone→compaction, rotation), not a process-spawner.
- **Caveat:** `loop` still polls completion (`wait_for_completion`) and currently lacks the driver's guards (model-check, `[[MILESTONE-REACHED]]`→compaction send, rotation, falsifiable send-verify). It needs feature parity (Layer C + driver-side guards moved into/around the loop).

### Layer C — ask-chatgpt itself: the root reactive fixes
1. **Persistent tab / session reuse** (Finding #1). Keep one tab open per conversation across turns; only idle-evict after long inactivity. `TabPool` already supports leases — the per-CLI-process lifecycle is what defeats it. **Biggest single win.**
2. **Reactive completion — observe the response stream's close, don't poll `/stream_status`** (Finding #2). When we submit, the SPA opens an SSE/streaming response; watch **that** stream (via CDP Network events / the existing streaming seam) and treat **stream-close as "done."** Feasible with existing infra: `cdp.py` already has **binding-based chunk-streaming** (`StreamState`, `consume_stream_event`, `{kind:"chunk"|"done"}`, ~`:478–513`; streaming fetch ~`:51–78`) and a Network-observation seam (used today for auth-header harvest in `capture.py:acquire_backend_headers :154`). Zero extra requests — we watch the stream the SPA already produces. **Design verification needed:** confirm the send's SSE/stream completion is observable via the existing CDP seam (Network `loadingFinished` on the streaming request, or the binding stream's `done`).
3. **Capture-from-stream** (optional, Finding #2-adjacent). As the response streams in (already observed for completion), capture it directly instead of a separate post-completion `GET /conversation/<id>`. Removes the re-fetch. (Harder; one on-completion fetch is still roughly human-like since the SPA fetches the conversation on load.)
4. **Human pacing + request-rate governor** (Finding #2/#4). A politeness delay **with jitter** between sends (a floor already exists: `session.py:_sleep_until_spacing_allows_submit :223` / `AdaptiveSendBudget`), plus a **global request-rate ceiling** that throttles ALL chatgpt requests (sends + fetches + page-loads) under a human-plausible cap, with backoff on 429/modal. **This is the deferred `issues/2026-06-21-*` rate-limit feature — now clearly worth building**, and should also add **429/"Too many requests" detection + a distinct exit code + Retry-After honoring** so the tool fails soft (and the driver backs off) instead of falling back to clipboard → exit 21.

---

## 6. Priority (highest human-like impact first)
1. **Persistent single tab** (stop reloading pages): Layer C-1 + drive via `loop` (Layer B). Kills the per-turn/per-poll SPA bursts — the dominant signal.
2. **Reactive completion via stream-close** (kill the 30 s `/stream_status` poll): Layer C-2.
3. **Drop driver `wait_until_idle` scrape-polling**: falls out of #1.
4. **429 detection + rate governor + human pacing/jitter**: Layer C-4.

---

## 7. Feasibility signals (already in the codebase)
- `loop` keeps one tab (`session.py:583`) → persistent-tab model exists; just unused by the driver.
- `cdp.py` streaming primitives (`StreamState`/`consume_stream_event`/`{kind:"done"}`) → reactive stream observation is buildable.
- CDP Network-observation seam exists (`capture.py:acquire_backend_headers` uses `wait_for_request`) → can be extended to observe the response stream's completion.
- Send spacing exists (`_sleep_until_spacing_allows_submit`) → pacing layer is partly there.
- M10 light-read path (reads avoid the heavy `/c/<id>` render) is in place for `scrape` (keep using it for any read).

---

## 8. Execution plan (team model)
1. **Best-of-N design mission** (NON-editing, zero-risk): design the human-paced/reactive session model (persistent tab + reactive stream-completion + capture strategy + rate governor). Lock the architecture before code. Verify the SSE-observation feasibility on a real attended leg.
2. **Single-editor implementation (TDD)** on a feature branch off `main`: implement Layer C in `completion.py`/`session.py`/`cdp.py`; add falsifiable tests (mock the stream-close event; assert no `/stream_status` polling occurs; assert one page-load per session).
3. **Best-of-N verification** (correctness / falsifiability / safety-leak / request-count regression — assert the new path issues ≪ the old path's requests).
4. **Attended real-site leg**: measure the live request profile (e.g., count `/backend-api/*` over N turns) and confirm it ≈ human + does **not** trip "Too many requests" over a long run.
5. **Deploy:** operator reinstalls (see constraints).

---

## 9. Constraints & safety (MUST honor — transcribed for the picking-up agent)
- **NEVER `uv tool install/upgrade/reinstall` the tool yourself** — the installed `ask-chatgpt` is a **shared, version-pinned isolated copy** another agent may use; reinstall is **operator-reserved**. Do all work on `main`/feature branches; the operator deploys.
- **Real-site = attended CDP only** (`http://127.0.0.1:9222`, profile "agent"); Playwright-launched browsers are Cloudflare-blocked. Preflight `curl :9222/json/version`. Login/Cloudflare → STOP, `HUMAN-ACTION-NEEDED`.
- **Own-tab-only / never touch operator tabs.** Do NOT close tabs by conversation-URL — the driver/rotate `reap_tabs` did exactly that and closed the operator's own tab (→ a renderer OOM that looked like a crash); both are now disabled. (Memory: `driver-reap-closes-operator-tab`.)
- **Heavy conversations OOM the renderer on full `/c/<id>` render.** A *persistent tab* on a heavy conv re-introduces this → pair persistent-tab with **rotate-before-heavy** (the rig already rotates when a conv grows undriveable). Reads use the M10 light path.
- **Backend-capture auth-header harvest must keep working** (the 8 `REQUIRED_CAPTURE_HEADERS`; M2/M7b gap-2 — a naive light-page change once broke harvest). Any completion/capture change must preserve header harvest or replace it with a working reactive equivalent.
- **Don't scrape/curl chatgpt while rate-limited.** On "Too many requests," back off ~30 min of silence.
- **Leak discipline:** never commit conversation content; redirect `ask`/`scrape` stdout to `/dev/null`; the `cache/` store is gitignored.
- The driver rig (`tmp/weak-simplex-push/`) is the **operator's experimental harness** (gitignored). The *tool* fixes (Layer C) are the durable deliverable; the driver (Layer B) is rig-specific.

---

## 10. Acceptance criteria
- **No completion polling:** the live path issues **no `/stream_status` polling**; completion is detected from the response stream closing. (Falsifiable test + real-leg request capture.)
- **One page-load per session:** a multi-turn run produces **one** SPA load-burst, not one per turn/poll. (Measured over N turns.)
- **Request rate under a human-plausible ceiling**, enforced by a governor; **429/"Too many requests" detected** → distinct exit code + Retry-After backoff (no clipboard-fallback exit 21).
- **A long unattended run (hours, many turns) does NOT trip "Too many requests."** (The real proof.)
- All existing falsifiable tests still pass (`uv run pytest`); new tests cover the reactive path; honest `VERIFICATION.md` update.

---

## 11. References
- **Incident & state:** `team/state/RESUME.md` (sections "⏸ PAUSED … RATE LIMIT", "UPDATE 12:13", "M15 inventory"); rotation log `tmp/weak-simplex-push/driver/rotation-log.jsonl`; store inventory handoff `team/evidence/handoffs/M15-store-inventory.md`.
- **Code:** `completion.py` (`poll_backend_completion :37`, `/stream_status :46`, `wait_for_completion :127`, `_backend_interval :470`); `session.py` (`TabPool.acquire :84`, `ask :353`/`:370`, `loop :563`/`:583`, `_sleep_until_spacing_allows_submit :223`, `wait_for_completion call :444`); `send.py` (`send_prompt :259`, `submit_composer :178`, `verify_prompt_submitted :212`); `capture.py` (`acquire_backend_headers :154`, `stream_backend_conversation :199`, `download_attachments :378`, `capture_conversation :329`); `channels/cdp.py` (streaming `:478–513`, fetch-stream binding `:51–78`).
- **Driver rig:** `tmp/weak-simplex-push/driver/driver.sh` (`run_ask :188`, `run_scrape :106`, `wait_until_idle`).
- **Related issues:** `issues/2026-06-21-*` (rate-limit tool-side handling — deferred; fold into Layer C-4); archived `archive/issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md` (tab-leak — fixed; relevant to tab lifecycle); the M10 read-ops light-path fix.
- **Memory (durable lessons):** `chatgpt-rate-limit-guidance`, `driver-reap-closes-operator-tab`, `read-via-light-page-not-render`, `heavy-chatgpt-gentle-cdp`, `cdp-renderer-hang-recovery`, `ask-chatgpt-v020-driving` (under `~/.claude/projects/-home-abhmul-dev-ask-chatgpt/memory/`).
