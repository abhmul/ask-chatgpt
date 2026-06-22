# M13-complete — descriptor-header mock test (offline) + attended real leg (scrape --with-attachments over light path)

You are a MANAGER (Opus, `claude -p`, **SINGLE-SHOT**) for team `ask-chatgpt-dev`, repo `/home/abhmul/dev/ask-chatgpt`. Execute end-to-end IN THIS ONE TURN; write a handoff.

## ⚠️ ANTI-YIELD — READ FIRST (Round-1 managers failed here)
Single-shot: **you will NOT be re-invoked.** FOREGROUND-BLOCK on every pi worker via `pi-watch.sh --wait-seconds 2400 --poll-seconds 15 ...` (returns only when the worker writes its `status` file). **NEVER spawn a background task/monitor. NEVER yield.** Run TASK 1 → TASK 2 → handoff all in this turn.

## Context (read these)
- `team/evidence/handoffs/M13-analyze-attachments-lightpath.md` — M13 verified OFFLINE that `scrape --with-attachments` over the M10 light path needs **NO code change** (M6 proved the descriptor endpoint tolerates the conversation-path `x-openai-target-path`; byte download rides same-origin cookies). Two items remain: (1) a falsifiable descriptor-header mock test; (2) one ATTENDED real leg confirming live.
- Operator (2026-06-22) authorized creating a fixture conversation (sends OK; **lower/non-Pro model to avoid Pro usage**).

---

## TASK 1 (OFFLINE, single pi editor — block foreground) — descriptor-header mock test
The complete drop-in test is in `.pi-workers/M13/lensB/pi-20260622-103506-3077813-19261/output.log` section **(c)** (test `test_attachment_descriptor_fetch_reuses_conversation_retargeted_headers`). If that file is gone, reconstruct from the M13 handoff + the existing analog `test_conversation_fetch_retargets_harvested_target_path` (`tests/test_capture.py:262-304`, same `RecordingChannel(MockChannel)` override-`fetch_in_page` pattern).
- Add the test to `tests/test_capture.py` (add `REQUIRED_CAPTURE_HEADERS` to the `ask_chatgpt.capture` import). It subclasses `MockChannel`, records the descriptor request, drives `capture_conversation(..., with_attachments=True, header_mode="ambient_backend")` over a mock attachment scenario, and asserts: the descriptor request is `GET /backend-api/files/<id>/download`, carries **all 8** `REQUIRED_CAPTURE_HEADERS` names, `x-openai-target-path == /backend-api/conversation/<conversation_id>`, and `x-openai-target-route` == the harvested route verbatim.
- **NO production change.** Run `uv run pytest` (PROJECT `.venv`): expect **280 → 281 passed**. Prove the test is falsifiable (reason precisely or scratch-copy mutate the descriptor header spread). Do NOT commit.

---

## TASK 2 (ATTENDED real leg, single pi worker, tools `read,grep,find,ls,bash` — block foreground) — confirm live
Own-tab-only. Do, IN ORDER:
1. **Preflight:** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` (record "up/down" + browser NAME only; expect Chrome/149). If the tool's own ChatGPT tab ever shows Cloudflare "Just a moment"/login/account-picker/any challenge → **STOP, log `HUMAN-ACTION-NEEDED`.**
2. **MODEL GATE (avoid Pro usage):** enumerate the live model picker **read-only, NO send** (study `src/ask_chatgpt/session.py` model selection + `src/ask_chatgpt/menus.py` + `team/evidence/handoffs/M7b-gaps.md` for the live selector mechanism; the CLI uses `ask --model "<label>"`). Identify a **non-Pro** model that is **reliably selectable + verifiable**. If yes → use it. **If a non-Pro model canNOT be reliably selected (e.g. the M9 GPT-5.5 family-submenu limitation), STOP — do NOT send — write a PARTIAL/BLOCKED handoff listing the available model labels (NAMES only)** so the lead/operator can choose. Do NOT burn Pro quota.
3. **Create the fixture (≤2 sends TOTAL, FRESH throwaway conversation):**
   - `printf 'M13 attachment download test\nline two\n' > /tmp/m13-attach.txt`
   - ONE send (stdout REDIRECTED): `uv run ask-chatgpt ask --selector-channel real --cdp-endpoint http://127.0.0.1:9222 --data-dir /tmp/m13-attach-data --model "<NON_PRO_LABEL>" --attach /tmp/m13-attach.txt "Acknowledge the attached file in one short sentence." > /dev/null`
   - (Positionals AFTER all options; SHORT single-line prompt — long/multiline → exit 30.) Learn the NEW conversation id from the store/index under `/tmp/m13-attach-data` (do NOT print it). Confirm a real send committed (a new user turn id appeared).
4. **Scrape over the light path (stdout REDIRECTED):** `uv run ask-chatgpt scrape --selector-channel real --cdp-endpoint http://127.0.0.1:9222 --data-dir /tmp/m13-attach-data --with-attachments --out /tmp/m13-attach-data/scrape.md "<CONV>" > /dev/null`
5. **Verify — record PATHS / METHODS / HEADER NAMES / STATUS CLASS ONLY (never values/bytes/ids/content):**
   - `scrape` exits 0, no renderer crash.
   - the **descriptor** request observed = `GET /backend-api/files/<redacted>/download` carrying all 8 header names (`authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route`).
   - the **byte** fetch returns 2xx (record whether any of the 8 harvested header names were present; expected: none — pre-signed/cookie-bound).
   - the uploaded attachment LANDED: a file exists under `/tmp/m13-attach-data/conversations/<id>/attachments/` AND the transcript JSONL shows `download_state == "downloaded"` with a non-null local path. (Count files; do NOT print names/ids/content.)
   - **PASS** = all the above. **FAIL** modes → recommendation: descriptor 4xx with all 8 names present ⇒ conversation-path `x-openai-target-path` NOT tolerated on the light path ⇒ recommend the Lens-A retarget (a Round-2b code change). Byte 401/403 with no harvested names ⇒ `download_url` not self-authenticating.
   - How to observe requests without leaking: prefer reading the produced store artifacts (transcript JSONL `download_state`, attachment files) + the tool's own debug/log output; do NOT call `/json/list`.

---

## Safety / constraints (transcribe into BOTH worker prompts — children inherit nothing)
- TASK 2 is ATTENDED REAL SITE. **own-tab-only:** inspect ONLY tabs the tool opens; NEVER read/touch operator/foreign tabs; **NEVER `/json/list`** (only `/json/version`); NEVER quit the browser (detach only).
- **≤2 real sends TOTAL**, FRESH throwaway conversation ONLY; NEVER the target `6a316aa8` or any foreign conversation. Human-paced, no bursts. Shared paid account.
- **Redirect ALL `ask`/`scrape` stdout to `/dev/null`** (content leak). NEVER print/log/persist: auth tokens, OAI/`Authorization` header VALUES, cookies, conversation content, file ids, attachment bytes, or the conversation id/URL. Header NAMES + request PATHS + status classes are OK.
- Use `uv run ask-chatgpt` (PROJECT `.venv` = current code incl. the just-applied tab-leak fix). NEVER the bare installed `ask-chatgpt`. NEVER `uv tool install/upgrade/reinstall`. NEVER move/commit `stable` (=`bbbe027`). Do NOT `git commit/push/checkout/stash` (the LEAD packages later). Do NOT switch branches. Do NOT touch `issues/cdp-send-repro/controller.mjs` or `human/`.
- WORKERS → pi via `bash .claude/skills/manager/references/launchers/parent-claude/pi-watch.sh`; **NEVER** the Agent/Task tool. Single editor for TASK 1.

## Handoff
Write `team/evidence/handoffs/M13-complete.md`: Status (`DONE`/`PARTIAL`/`BLOCKED`); TASK 1 result + `uv run pytest` count; TASK 2 real-leg PASS/FAIL with the observed paths/header-NAMES/status-classes ONLY + which model was used + send count; any retarget recommendation. End your FINAL message with: `Status: ...`, `Pytest: <N passed>`, `Real-leg: <PASS|FAIL|BLOCKED-model-gate>`, `Handoff: team/evidence/handoffs/M13-complete.md`.
