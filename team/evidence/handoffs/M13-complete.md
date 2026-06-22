# M13-complete handoff — descriptor-header mock test (offline) + attended real leg (scrape --with-attachments over the light path)

**Status: DONE**
**Verdict:** The M13 OFFLINE verdict (`scrape --with-attachments` over the M10 light path needs **NO code change**) is now **LIVE-CONFIRMED**. The falsifiable descriptor-header mock test is added (test-only) and the suite is green at **281 passed**. The attended real leg **PASSED** with **1 send** on a **non-Pro** model. No production code change was made.

Manager: detached Claude Opus (`claude -p`, single-shot), M13-complete. Branch `fix/m10-light-read-scrape` (unchanged — no commit/checkout/stash; LEAD packages later). `stable` untouched. Dispatched two pi workers via `pi-watch.sh` (foreground-blocked to completion in-turn; never the Agent/Task tool).

---

## TASK 1 — descriptor-header mock test (OFFLINE) — DONE, independently verified
- Added `REQUIRED_CAPTURE_HEADERS` to the `ask_chatgpt.capture` import and the test `test_attachment_descriptor_fetch_reuses_conversation_retargeted_headers` to `tests/test_capture.py` (line ~308). **TEST-ONLY — no production change.**
- The test subclasses `MockChannel`, records the descriptor request, drives `capture_conversation(..., with_attachments=True, header_mode="ambient_backend")`, and asserts the descriptor request is `GET /backend-api/files/<id>/download`, carries **all 8** `REQUIRED_CAPTURE_HEADERS` names, `x-openai-target-path == /backend-api/conversation/<conversation_id>`, and `x-openai-target-route` == the harvested route verbatim.
- **`uv run pytest` (project `.venv`) = 281 passed** (280 → 281; the worker's captured pytest output read `281 passed in 1.30s`).
- **Independently re-derived by the manager from ground truth** (not worker self-telemetry):
  - path-scoped `git diff --stat -- tests/test_capture.py src/ask_chatgpt/capture.py` ⇒ **only `tests/test_capture.py` changed (+105)**; `git diff -- src/ask_chatgpt/capture.py` ⇒ **empty** (zero production change).
  - manager re-ran `uv run pytest tests/test_capture.py -k descriptor_fetch_reuses -q` ⇒ **`1 passed, 28 deselected`**.
- **Falsifiability:** the worker reasoned precisely (left `src/` untouched): the new assertions fail if the descriptor header spread is dropped (`capture.py` `_fetch_attachment_descriptor` ≈ L465), if the conversation-path retarget is removed (`capture.py` L343), or if the harvested `x-openai-target-route` is dropped. (This closes the M10-T3-V3 assertion gap.)
- **Worker self-reported PARTIAL — this was a known FALSE flag** ([[worker-overflags-on-unqualified-diff]]): its unqualified `git diff --stat` showed PRE-EXISTING dirty files (`src/ask_chatgpt/cli.py`, `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, `tests/test_cli.py`, an `issues/*.md`) that match this session's opening git-status snapshot exactly and were untouched by the worker. True TASK-1 scope = `tests/test_capture.py` only.

## TASK 2 — attended real leg (ATTENDED REAL SITE) — PASS, 1 send, non-Pro
Own-tab-only; preflight `curl :9222/json/version` = **up, Chrome/149**. **First attempt false-negative + manager fix:** the initial read-only enumeration raised `SelectorNotFoundError` (no challenge, **0 sends**) because the manager's snippet opened the Radix model picker **before** the composer hydrated. Per [[real-discovery-false-negatives]] the manager corrected the snippet to run the production hydration sequence (`s.create()` draft → render=True tab → `wait_for_idle_and_reload_if_needed` → `wait_for_composer`) before `open_radix_menu`, then re-dispatched. The retry succeeded.

**Model gate (read-only enumeration, ZERO send):** picker options (public UI labels) =
- top-level `menuitemradio`: **Instant**, Medium, High, Extra High, Pro Extended
- family submenu `menuitem`: GPT-5.5

Chosen **non-Pro top-level radio: `Instant`**. Pro quota protected by design (`assert_reflected_model` fails closed *before* the send block in `session.py`, so `ask --model` selects-and-sends or raises-and-sends-nothing).

**Fixture:** ONE `ask --selector-channel real --cdp-endpoint :9222 --data-dir /tmp/m13-attach-data --model "Instant" --attach /tmp/m13-attach.txt "<short prompt>"` to a FRESH throwaway conversation (no conv positional; stdout → `/dev/null`). **Real sends used: 1** (one committed user turn; ≤ 2 cap honored). Protected/foreign conversations never touched.

**Observed on the light-path `scrape --with-attachments` (NAMES / PATHS-redacted / STATUS-CLASS / BOOLEAN / COUNT only):**
- `SCRAPE_OK = True`, `RENDERER_CRASH = False`, CLI `scrape` exit `0`.
- **Descriptor request observed = `GET /backend-api/files/<redacted>/download`** carrying **all 8** header names: `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route` (`DESCRIPTOR_HAS_ALL_8 = True`).
- `x-openai-target-path` value **== the conversation path** (`DESCRIPTOR_TARGET_PATH_IS_CONVERSATION = True`; value never printed) — confirms the conversation-path target-path is **tolerated** by `/backend-api/files/<id>/download` on the LIGHT origin (the open question).
- **Byte download landed:** `ATTACHMENT_FILE_COUNT = 1` (non-empty), transcript `download_state` includes `downloaded` with a non-null local path. File landing independently proves the descriptor GET returned 2xx and the byte fetch returned 2xx. The byte fetch carries no explicit auth header (rides same-origin cookies), by design.
- **Manager independent corroboration** (local store only, no real-site touch, leak-safe): `CONV_DIR_COUNT=1`, `ATTACHMENT_FILE_COUNT=1` (non-empty), unique `download_state ∈ {downloaded, pending}` with `ANY_NONNULL_LOCAL_PATH=True`. The `pending` entries are superseded eager-write records (pending@send → downloaded@capture; last-writer-wins per [[transcript-audit-last-writer-wins]]) — expected, not a failure.

**Safety confirmations (worker + manager):** never called `/json/list` (only `/json/version`); browser detached, never quit; no auth/oai/cookie/target-path VALUES, conversation content, file ids, or conversation id/URL printed or persisted; all `ask`/`scrape` stdout redirected to `/dev/null`.

---

## Artifacts & trust
- `tests/test_capture.py` (new test + import) — **verified-independently** (manager path-scoped diff + manager-run targeted pytest `1 passed`; full suite `281 passed`). NOT committed.
- `src/` — **unchanged** (verified: `git diff -- src/ask_chatgpt/capture.py` empty). No production change anywhere for this mission.
- Live real-leg facts — **verified-independently for the shipment** (manager corroborated file-landing from the local store); descriptor header-name/target-path booleans are **worker-observed (producer)**, corroborated by (a) the file successfully downloading, (b) the offline TASK-1 test pinning the 8 names + target-path, and (c) the production code spreading exactly `REQUIRED_CAPTURE_HEADERS`.
- Worker contracts: `team/contracts/M13-complete-task1-editor.md`, `team/contracts/M13-complete-task2-realleg.md`. Worker run dirs: `.pi-workers/M13-complete/task1/...`, `.../task2/...` (false-negative attempt), `.../task2-retry/...` (PASS).
- Throwaway fixture cache: `/tmp/m13-attach-data` (local only, not committed; the chatgpt.com conversation is a throwaway on the operator account).

## Blockers
None. Both items in the M13 analyze handoff are now closed: (1) falsifiable descriptor-header mock test added; (2) attended real leg confirms live.

## Recommended next
1. **No descriptor `x-openai-target-path` retarget is needed** — the live leg confirms the conversation-path target-path is tolerated on the light origin and the byte fetch rides cookies. The Lens-A retarget remains *optional hardening only*, not a correctness fix; do not ship it as a fix.
2. **LEAD to package**: commit `tests/test_capture.py` (test-only, +105) on `fix/m10-light-read-scrape` and fold into the M10 light-read-scrape PR; this mission made no `src/` change. (Pre-existing dirty `cli.py`/`test_cli.py`/`controller.mjs`/`live-state.json`/`issues/*.md` are out of M13 scope — M11/M12 work — and must be packaged separately by their owners.)
3. The light-path attachment flow can fold into the honest re-issue of `VERIFICATION.md` (falsifiability + prompt-quality lens) as a now-live-confirmed capability.

## Complexity / paradigm-shift signals
None. One process note: the model-picker enumeration is only valid AFTER composer hydration (`wait_for_idle_and_reload_if_needed` + `wait_for_composer`); a read-only probe that skips those waits yields a false "no model picker" `SelectorNotFoundError` — re-confirming [[real-discovery-false-negatives]] (real "not found" verdicts are often probe artifacts; re-derive before trusting).
