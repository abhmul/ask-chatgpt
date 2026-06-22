# M14 — Triage the `issues/` backlog (read-only) — handoff

**Status: DONE**

Read-only triage of the 8 backlog issues complete. Every verdict was re-derived from ground truth (current working tree == released `main` @ `837f7aa`), produced by two investigator pi workers (W1a/W1b) and adversarially challenged by a third (W2), then adjudicated by the manager against the source/tests/`git` directly. Three of W2's challenges were re-derived by the manager: two (#1, #8) were over-flags and overturned; one (#3) surfaced a real, narrow residual and is routed to LEAD-DECIDE.

This round made **no repo mutations**. The only writes were this handoff and the pi run dirs under `.pi-workers/`. The actual file moves remain the LEAD's job.

---

## 1. Verdict table

| issue file | verdict | recommend | single strongest ground-truth evidence | reproducible in current `main`? |
|---|---|---|---|---|
| `2026-06-14-capture-renders-dom-not-raw-markdown.md` | RESOLVED | **ARCHIVE** | `capture.py:329-360` default path = backend-API canonical JSON (`capture_source="backend_api"`, `fidelity="canonical"` @ `capture.py:322-323`); falsifiable `tests/test_capture.py:462-466` pins `\widehat`/`\ne`/`\neq`/`\frac` preserved + literal `≠` absent | **no** — DOM textContent only via degraded-marked, fail-closed fallback gated on backend failure (`capture.py:358`) |
| `2026-06-14-out-suppresses-stdout.md` | RESOLVED | **ARCHIVE** | `cli.py:327-331` → `Store.emit_payload` writes stdout **before** optional `--out` file (`store.py:378-381`); `tests/test_cli.py::test_cli_ask_forwards_flags_and_stdout_and_out_are_identical` | **no** — no success path is file-only |
| `2026-06-14-response-truncated-drops-out-file-and-session.md` | JUDGEMENT-CALL | **LEAD-DECIDE** | v1 paths gone (`ResponseTruncatedError`/`driver.py`/`api.py`/`session_registry.py`/exit-7/600s ceiling all absent); `session.py:409-442` persists ref+send pre-wait, `:475-480` records partial on BOTH timeouts — **but** `cli.py:92` auto-emits `--out` partial only for `CompletionTimeoutError`, `:103` lets `MaxTotalWaitExceededError` fall through | **partial** — filed v1 bug: no (obsolete+fixed). Narrow residual: yes (`--max-total-wait` cut-off skips `--out` auto-emit; partial still in store) |
| `2026-06-18-cdp-send-noop-returns-stale-response.md` | RESOLVED | **ARCHIVE** | `session.py:427-434` `verify_prompt_submitted` vs `baseline` (raises `PromptNotSubmittedError`, `errors.py:170`); `completion.py:70,87` ignore baseline assistant id; falsifiable `tests/test_send_completion.py::test_session_no_op_preserves_pending_and_never_calls_completion` (monkeypatches completion to fail if reached) | **no** — a no-op send raises before completion can return stale text |
| `2026-06-20-cli-leaks-browser-tab-per-invocation.md` | RESOLVED | **ARCHIVE** | `cli.py:205-206 / 233-234 / 297-298` `finally: session.detach()` on ask/scrape/loop; create/history/fetch/status acquire no managed tab; `tests/test_cli.py::test_cli_ask_closes_tab_on_error_after_acquire` (+ success/scrape/loop-interrupt) pin open==close==1; commit `791f37a` | **no** — every tab-opening path detaches in `finally` |
| `2026-06-21-chatgpt-rate-limit-too-many-requests.md` | JUDGEMENT-CALL | **LEAD-DECIDE** | tool-side fixes ABSENT (`errors.py` has no `RateLimited`/`429`/`Retry-After` class; `completion.py:54-58` raises generic `BackendCaptureShapeError` on non-2xx; no governor); operator DO-NOT-BUILD + impl sketch recorded in-file; commit `16a05b8` | **yes** — the (declined) tool-side gap is still present by design |
| `2026-06-22-read-ops-render-full-conversation-page.md` | RESOLVED | **ARCHIVE** | `session.py:525` `scrape` → `tab_pool.acquire(ref, render=False)` + `header_mode="ambient_backend"`; ambient harvest `capture.py:165-166`; falsifiable `tests/test_capture.py::test_scrape_uses_light_root_and_generic_backend_header_harvest`; commits `e02e617`/`697c5e4` | **no** — scrape opens light `https://chatgpt.com/` and backend-fetches; history/fetch are local tab-free reads |
| `2026-06-22-scrape-with-attachments-light-path-unverified.md` | RESOLVED | **ARCHIVE** | `capture.py:351` `download_attachments` reuses conversation-retargeted `backend_headers` (M13 live-verified tolerated); falsifiable `tests/test_capture.py::test_attachment_descriptor_fetch_reuses_conversation_retargeted_headers` (`:394-409`) pins descriptor path + 8 header NAMES + `x-openai-target-path` + `download_state=="downloaded"`; commit `4574d74` | **no** — verification gap closed; descriptor retarget is explicitly "optional hardening, not a correctness fix" |

Out of scope (NOT triaged, per contract): `issues/cdp-send-repro/` — a CDP send REFERENCE harness, not a backlog issue. Left untouched; no archive/keep recommendation.

---

## 2. Exact lists

### ARCHIVE (RESOLVED ∪ OBSOLETE) — 6 files
- `issues/2026-06-14-capture-renders-dom-not-raw-markdown.md`
- `issues/2026-06-14-out-suppresses-stdout.md`
- `issues/2026-06-18-cdp-send-noop-returns-stale-response.md`
- `issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md`
- `issues/2026-06-22-read-ops-render-full-conversation-page.md`
- `issues/2026-06-22-scrape-with-attachments-light-path-unverified.md`

### KEEP (STILL-RELEVANT) — 0 files
- (none)

### LEAD-DECIDE (JUDGEMENT-CALL) — 2 files
- `issues/2026-06-14-response-truncated-drops-out-file-and-session.md`
  - **Reading A → ARCHIVE (OBSOLETE+substantively-fixed):** every code path the issue names is v1 and gone — `ResponseTruncatedError` (exit 7), `driver.py`, `api.py`, `session_registry.py`, the always-on `_REAL_COMPLETION_CEILING_S = 600.0` ceiling, `--session`, `--model-settings`. Both filed bugs are addressed in v2: Bug 2 (lost registry) is fixed — `session.py:409-442` persists `put_conversation_ref` + `begin_send` + `commit_send` BEFORE `wait_for_completion`, and `session.py:475-480` records the partial to the store on BOTH timeout classes; Bug 1 (no `--out` on cut-off) is fixed for the default activity-timeout path — `cli.py:92-102` salvages the partial to stdout+`--out`, pinned by `tests/test_cli.py::test_cli_completion_timeout_prints_salvage_to_stdout_and_out_before_error`. The v1 "hidden 600s ceiling" headline blocker is eliminated (`max_total_wait` is caller-controlled, CLI default `None`).
  - **Reading B → KEEP (residual matches issue's promise):** W2 verified a real residual — `CompletionTimeoutError` and `MaxTotalWaitExceededError` are SIBLING classes (`errors.py:212` exit 50 / `errors.py:219` exit 51; neither subclasses the other). `cli.py:92` (`except CompletionTimeoutError`) auto-emits the partial to `--out`/stdout; `MaxTotalWaitExceededError` falls through to `cli.py:103` (`except AskChatGPTError`) with NO `--out`/stdout auto-emit, even though `completion.py:156` attaches the partial to it. So a caller bounding a long Pro-Extended call with `--max-total-wait` (exactly the issue's use case) who hits the cap does NOT get the partial written to their `--out` file (it IS persisted to the store and attached to the exception, so recoverable via `history`/`scrape` — unlike v1's irrecoverable loss).
  - **Manager note for the lead:** if archived, recommend filing a fresh, tightly-scoped issue: "mirror the `CompletionTimeoutError` `--out`/stdout partial salvage to the `MaxTotalWaitExceededError` branch in `cli.py`." This is a separable minor enhancement, not a reproduction of the v1 bug.

- `issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md`
  - **Reading A → ARCHIVE:** a documented incident finding (R-001) + operational guidance + an explicitly-DECLINED enhancement. The operator decided DO-NOT-BUILD and the implementation sketch is recorded in the file (commit `16a05b8`). The three suggested tool-side fixes are confirmed absent — so nothing is "in flight."
  - **Reading B → KEEP:** an open, un-built tool-side enhancement the team may still want to track (429/modal detection + distinct exit code; `Retry-After`/backoff; cross-process governor), all verified ABSENT in current `main` (no `RateLimited`/`429`/`Retry-After` symbol in `src/ask_chatgpt/`; `errors.py` taxonomy has no rate-limit class; `completion.py:54-58` raises generic `BackendCaptureShapeError` on non-2xx). The operational guidance is still accurate because the code still cannot self-identify or throttle rate limits.
  - This is the backlog's designated JUDGEMENT-CALL; disposition depends on operator intent. Manager does NOT pick.

---

## 3. What was verified (files, line refs, commands, per-issue evidence)

### Dispatch / method
- 3 read-only pi workers (`--tools read,grep,find,ls,bash`, no edit/write) launched detached via `pi-watch.sh --wait-seconds 0`, blocked to completion this turn by polling `status` files (all exit 0, ~6 min):
  - **W1a** investigator (older 4: #1/#2/#3/#4) → `.pi-workers/pi-20260622-181125-29007-8595/output.log`
  - **W1b** investigator (newer 4: #5/#6/#7/#8) → `.pi-workers/pi-20260622-181152-29322-1607/output.log`
  - **W2** adversarial verifier (falsify all 7 archive candidates; check #6 absence) → `.pi-workers/pi-20260622-181215-29717-12828/output.log`
- Manager personally re-derived ground truth (Read/Grep) for every contested verdict and spot-checked the agreed ones.

### Per-issue evidence (manager-inspected unless noted)
- **#1 capture-DOM (RESOLVED):** `capture.py:329-367` `capture_conversation` — default path: `acquire_backend_headers` → `stream_backend_conversation` (`GET /backend-api/conversation/<id>`) → `validate_backend_shape` → `iter_current_branch_records`, yielding `content_markdown=_extract_visible_parts(message, …)` from backend JSON `content.parts` with `capture_source="backend_api"`/`fidelity="canonical"` (`:322-323`). DOM fallback (`fallback_capture_ui`) reached ONLY in `except (BackendAuthUnavailableError, BackendCaptureShapeError, StoreError)` (`:358`) with a degraded `reason`. Falsifiable math test `tests/test_capture.py:434-474` asserts `\widehat{x}`/`\ne y`/`\neq z`/`\frac{}{}` present and `≠` absent on the canonical path; degraded-fallback marking pinned by `tests/test_capture.py:853 test_fallback_marks_katex_and_dom_salvage_degraded_and_fails_closed_when_empty`. **W2 CHALLENGE (DOM fallback reachable) overturned** — fallback is the issue's own suggested degraded fallback, gated on backend failure, marked degraded; not the silent-default-corruption bug.
- **#2 --out suppresses stdout (RESOLVED):** `cli.py:327-331` `_emit_payload` → `store.emit_payload(content, out=out)`; W1+W2 both cite `store.py:378-381` writes stdout before optional out. Tests `tests/test_cli.py::test_cli_ask_forwards_flags_and_stdout_and_out_are_identical` + `tests/test_store_payload.py`. Both workers CONFIRMED-RESOLVED; consistent with the intended current design (`--out` mirrors both streams).
- **#3 truncation drops --out+session (JUDGEMENT-CALL):** `errors.py` (full read) — no `ResponseTruncatedError`; `CompletionTimeoutError`(50)/`MaxTotalWaitExceededError`(51) are siblings under `_KnownAskChatGPTError`. `cli.py:90-108` main try/except. `completion.py:127-206` `wait_for_completion` raises `MaxTotalWaitExceededError` (`:152-157`, only when `max_total_wait_s is not None`) and `CompletionTimeoutError` (`:200-205`), both with `_attach_partials`. `session.py:409-481` ask flow (store writes pre-wait; `:475-480` records partial on both). See §2 LEAD-DECIDE for full both-readings.
- **#4 cdp send no-op stale (RESOLVED):** `session.py:409` `baseline = read_turn_baseline(...)`; `:427-434` `verify_prompt_submitted(tab, …, baseline, prompt, …)`; `:439-440` raise `InternalError` if no committed user turn; `errors.py:170` `PromptNotSubmittedError` (exit 30). `completion.py:70,87` `is_new = latest.message_id != baseline.latest_assistant_id` (stale assistant ignored). Falsifiable tests `tests/test_send_completion.py::test_no_op_submit_verification_raises_prompt_not_submitted` + `::test_session_no_op_preserves_pending_and_never_calls_completion`. Both workers CONFIRMED-RESOLVED; manager corroborated from source.
- **#5 tab leak (RESOLVED):** `cli.py` — `_handle_ask` (`:205-206`), `_handle_scrape` (`:233-234`), `_handle_loop` (`:297-298`) each `finally: session.detach()`. `_handle_create`/`_handle_history`/`_handle_fetch`/`_handle_status` (`:209-262`) acquire no managed tab (history/fetch read the local store; create returns a draft ref; status preflights only when `probe_browser`). Lifecycle tests `tests/test_cli.py::test_cli_ask_closes_tab_on_success | _on_error_after_acquire | test_cli_scrape_closes_tab_on_success | test_cli_loop_closes_tab_on_keyboard_interrupt`. Commit `791f37a`. Both workers CONFIRMED-RESOLVED.
- **#6 rate-limit (JUDGEMENT-CALL):** `errors.py` full read — taxonomy exit codes 20-99, none rate-limit-specific. W1b+W2 grep of `src/ask_chatgpt/` found no `429`/`RateLimited`/`RateLimit`/`Retry-After`/`retry_after`/`governor`/"too many requests"; only an in-memory send-budget hook (`session.py:149,157,194,198`) with `record_soft_signal` defined but no callers. `completion.py:54-58` raises generic `BackendCaptureShapeError` on non-2xx. Operator DO-NOT-BUILD + impl sketch in-file (commit `16a05b8`). See §2.
- **#7 read-ops render full page (RESOLVED):** `session.py:525-527` `scrape` calls `tab_pool.acquire(ref, render=False)` + `capture_conversation(..., header_mode="ambient_backend")`; `:534-537` history/fetch stay local. `capture.py:154-196` `acquire_backend_headers` ambient-backend matcher; `:329-357` light backend fetch. Falsifiable `tests/test_capture.py:190 test_scrape_uses_light_root_and_generic_backend_header_harvest` (+ `:304` asserts target path on light origin). Commits `e02e617`/`697c5e4`. Both workers CONFIRMED-RESOLVED.
- **#8 attachments light path (RESOLVED):** `capture.py:351` `download_attachments(tab, conv, backend_headers, records, store)` reuses conversation-retargeted `backend_headers`. Falsifiable `tests/test_capture.py:308-409` records the descriptor request and asserts: exactly 1 descriptor + 1 byte fetch, `download_state=="downloaded"`, descriptor path `/backend-api/files/<id>/download`, `set(REQUIRED_CAPTURE_HEADERS) <= descriptor_headers`, `x-openai-target-path == conversation_path`. Issue file Resolution (M13) records the attended live leg (1 send) that confirmed the conversation-path header is tolerated; descriptor retarget = "optional hardening only, not shipped." Commit `4574d74`. **W2 CHALLENGE (descriptor not retargeted) overturned** — that is precisely the M13-verified, intentionally-tolerated behavior; the issue was a verification gap, now closed + pinned.

### Commands run by the manager (all non-mutating)
- `git log --oneline -20`, `git rev-parse HEAD`, `git rev-parse stable` → HEAD == stable == `837f7aa`.
- Glob `issues/**/*.md`, `src/ask_chatgpt/**/*.py`, `tests/**/*.py` to anchor layout.
- Read: `errors.py` (full), `cli.py:75-340`, `completion.py:40-215`, `session.py:395-545`, `capture.py:140-369`, `tests/test_capture.py:300-475`; Grep `tests/test_capture.py` for the math/descriptor/fallback/light-root test defs.
- No `uv run pytest` was needed for the verdicts (rested on inspected code+tests+git); test falsifiability was confirmed by reading the assertion bodies, per contract.

---

## 4. Artifacts + trust level

| artifact | trust |
|---|---|
| W1a output → `.pi-workers/pi-20260622-181125-29007-8595/output.log` | producer-only (cross-checked by manager) |
| W1b output → `.pi-workers/pi-20260622-181152-29322-1607/output.log` | producer-only (cross-checked by manager) |
| W2 output → `.pi-workers/pi-20260622-181215-29717-12828/output.log` | producer-only (adversarial; manager re-derived all 3 challenges) |
| Verdicts for #1, #8 | **verified-independently** — W2 challenged, manager overturned from `capture.py` + falsifiable `test_capture.py` |
| Verdicts for #2, #4, #5, #7 | **verified-independently** — W1 + W2 both CONFIRMED-RESOLVED; manager spot-checked source |
| Verdict for #3 | **verified-independently** (mechanism) — manager read `errors.py`/`cli.py`/`completion.py`/`session.py` + issue file; disposition routed to LEAD-DECIDE |
| Verdict for #6 | **verified-independently** — absence of tool-side fixes confirmed by W1b+W2 grep and manager `errors.py` read; disposition routed to LEAD-DECIDE |

This handoff is the manager's adjudicated synthesis, not any single worker's table.

---

## 5. Blockers
None for the triage itself (DONE). Two items require the LEAD/operator before the archival executes:
1. **`#3` disposition** — choose Reading A (archive; optionally re-file the narrow `--max-total-wait` `--out`-salvage gap) vs Reading B (keep open until `cli.py` salvages `MaxTotalWaitExceededError` too).
2. **`#6` disposition** — choose archive (declined-enhancement finding) vs keep (tracked un-built enhancement).

The LEAD executes the reversible moves (e.g. into `archive/issues/` or equivalent) + git packaging for the ARCHIVE set; this manager made no moves (read-only round).

---

## 6. Complexity / paradigm-shift signals
- None. The backlog cleanly separated into resolved/obsolete (the v1-rewrite and M10-M13 rounds genuinely closed them) plus two judgement items, matching the mission's prior.
- Worth noting for future triage rigor: adversarial verification earned its keep — W2 produced 3 challenges; 2 were over-flags (intentional degraded-fallback design #1; an already-verified-tolerated design #8) and 1 was a genuine, narrow residual (#3). Over-flagging of sanctioned designs is the expected adversarial-worker failure mode; the manager-level ground-truth re-derivation is what separates a real residual from an over-flag. None of the 6 ARCHIVE verdicts survived only on a worker's say-so.
