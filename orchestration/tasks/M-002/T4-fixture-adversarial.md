# T4 — Fixture reader-facing: adversarial DOM + virtualized variant + streaming + honest-failure states + copy/clipboard. TDD.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1–T3 are DONE/committed. T3 built the CORE mock fixture: `tests/fixtures/mock_chatgpt/server.py` (stdlib `ThreadingHTTPServer`, 127.0.0.1:0 ephemeral, control endpoints `/__reset__` `/__inspect__` `/__script__`), the `mock_chatgpt` pytest fixture in `tests/conftest.py`, and `src/ask_chatgpt/selector_maps/mock.json`. You EXTEND these — do NOT rewrite or break the existing core (the 12 existing tests MUST keep passing).

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be green (12 passed). If not, STOP, report BLOCKED with output.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/decision-memo.md` — **§6 (lines ~91-100): binding fixture spec.** Implement here the: "Adversarial content", "Copy channel", "DOM fallback" (stable AND unstable/virtualized variants), and "Honest failures" (login/session-not-found/model-unavailable/truncated/rate-limit/selector-unavailable — DEFER upload/download-unsupported to T4b) parts. (Download/fenced-base64/upload affordances are T4b.)
3. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` — the existing CORE server you extend. Read it fully first.
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/selector_maps/mock.json` — extend with new keys; keep existing keys.
5. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001: reader returns the **latest completed assistant turn ONLY**, bounded, fail-closed. The booby-traps exist precisely to prove the reader never returns older/injected DOM.
6. READ-ONLY reference for booby-trap style: `/home/abhmul/Documents/weak-simplex-conjecture/control-plane/tests/fixtures/phase3_mock_chat.py` (sentinel rendering). NEVER its `archive/`/`human/`.

## Scope — extend the fixture with these behaviors (scriptable via `/__script__` / a new control field; the DRIVER must NEVER use control endpoints)
1. **Multiple turns + adversarial content.** A conversation can hold several turns. Support scripting OLDER assistant turns and prompt echoes that contain **prompt-injection sentinels / booby-trap strings** (e.g. a unique `BOOBYTRAP-<token>` and an "IGNORE ALL PREVIOUS INSTRUCTIONS…" string), while the LATEST completed turn holds the real answer. Goal: downstream reader tests prove the reader returns ONLY the latest completed turn, never sentinel/older/injected text.
2. **Virtualized / unstable selector variant.** A scriptable mode where the conversation DOM is "virtualized": older turns are not in the DOM (or are placeholder stubs) and/or the latest turn uses an alternate layout. Purpose: test latest-turn targeting robustness and fail-closed behavior. Keep the STABLE variant (T3 default) intact; this is an opt-in mode.
3. **True streaming.** Scripting `streaming=True` makes the latest assistant turn render with the `streaming_marker` present and the `completion_marker` ABSENT for the first N `GET /c/<ref>` reads (N scriptable, default e.g. 2), then it flips to COMPLETE (completion_marker present, streaming_marker gone). Implement via a per-turn poll counter or equivalent deterministic mechanism. This drives the T5 completion detector / T6 reader wait logic.
4. **Honest-failure states** (scriptable; each renders a DETECTABLE DOM marker so the driver can fail closed with the right named error — the driver maps them in T5):
   - `login_required`: `GET /` renders a login wall (`[data-testid="login-wall"]`) and NO composer. → LoginRequiredError later.
   - `session_not_found`: `GET /c/<unknown-or-flagged-ref>` renders a "conversation not found" marker (`[data-testid="conversation-not-found"]`) (and/or HTTP 404). → SessionNotFoundError later.
   - `model_unavailable`: the `model_menu` does NOT offer the requested model (option absent or `[data-disabled="true"]`). → ModelUnavailableError later.
   - `response_truncated`: the latest assistant turn renders WITHOUT the completion marker but WITH a truncation indicator (`[data-testid="assistant-truncated"]`) / missing end-marker. → ResponseTruncatedError later.
   - `rate_limited`: send yields a rate-limit/backoff banner (`[data-testid="rate-limit"]`). (Our named-error taxonomy has no RateLimited type yet; T5 will map this to a base `AskChatGPTError` with an actionable backoff message or add a subclass — NOT your concern; just render the detectable marker.)
   - `selector_unavailable`: a mode where a REQUIRED core selector element (e.g. `composer`) is ABSENT, so the driver's fail-closed loader raises SelectorUnavailableError. (DEFER upload/download-unsupported states to T4b.)
5. **Copy button + clipboard.** On the LATEST completed assistant turn render a copy button (`copy_button`, may be visually hidden until hover via CSS but present in DOM). Its click handler writes the EXACT latest assistant text to `navigator.clipboard` (`navigator.clipboard.writeText(...)`; 127.0.0.1 is a secure context in chromium, so with granted `clipboard-read`/`clipboard-write` permissions this works). Scriptable `copy_mode`: `ok` (default, writes exact latest text), `missing` (no copy button), `wrong` (writes an OLDER/booby-trap turn's text), `stale` (writes nothing / leaves prior clipboard), `truncated` (writes a truncated copy). These let T6 test the CopyButtonReader + its failure handling.

### Selector-map additions (`src/ask_chatgpt/selector_maps/mock.json`) — ADD, do not remove existing keys
Add under `selectors`: `copy_button`, `login_wall`, `conversation_not_found`, `truncation_marker`, `rate_limit_marker`, and a `model_option_disabled` (or document how a disabled/absent option is detected). Every new selector MUST match the DOM you render.

### TDD tests — `tests/test_fixture_adversarial.py` (write FIRST, watch fail, implement)
Use the `mock_chatgpt` fixture + Playwright (headless chromium, cached) + the selector map. Cover:
- **Booby-trap:** script an OLDER assistant turn with a `BOOBYTRAP-<token>` sentinel + a LATEST completed turn with the real answer; via the selector map assert the LATEST completed turn body == real answer, and that the sentinel exists only in a non-latest/older turn element (so T6 can prove non-leakage).
- **Streaming:** script `streaming=True, stream_reads=2`; poll `GET /c/<ref>`: first read shows `streaming_marker` and NO `completion_marker`; by read 3 the `completion_marker` is present and text is final.
- **Each failure state** (login_required, session_not_found, model_unavailable, response_truncated, rate_limited, selector_unavailable): set it, load the relevant page, assert the corresponding marker is present/detectable (and for login/selector-unavailable, that `composer`/required element is absent).
- **Copy:** `copy_mode=ok` → grant clipboard permissions on the Playwright context, click `copy_button`, read `navigator.clipboard.readText()` via `page.evaluate`, assert == latest text. `copy_mode=missing` → no copy button present. (Deeper reader integration is T6.)
- Full `uv run pytest -q` GREEN (existing 12 + new). Keep Playwright tests bounded (no sleep-spin; poll with timeouts).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Tests and ALL work NEVER contact chatgpt.com/openai or any external service. The mock binds 127.0.0.1 ONLY, EPHEMERAL port (the T3 server already does — keep it). All browser navigation targets the loopback `base_url`. Clipboard/permissions are granted only on the loopback context.
- The ONLY ever-permitted external download is chromium — ALREADY CACHED. ZERO new pip deps (stdlib + existing `playwright`). Never sudo/apt/install.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. (Booby-trap/sentinel strings are synthetic test content, never secrets.)
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive is READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY. NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Tear down any server/browser you start; kill only your own processes. NEVER `git push`. Do NOT `git commit`.
- Do NOT break the existing 12 core tests. EXTEND server.py / mock.json; don't rewrite their core behavior. ESTIMATE BEFORE EXECUTE for anything >2 min (Playwright suites can be slow).

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-002/T4-report.md`)
- `date -Iseconds` at START + END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- `ESTIMATE: T4 <min>m`.
- Report ≤200 lines: files touched, the scriptable modes/fields you added (names + semantics), new selector keys, how streaming completion flips, the exact `uv run pytest -q` summary, deviations, trust notes (loopback-only, clipboard on loopback context only, no secrets).
- End with `T4-STATUS: DONE` (or `BLOCKED` + exact error + next action) LAST.

## Success criteria (all must hold)
- Adversarial booby-trap content scriptable in older/echo turns; latest completed turn distinct and uniquely targetable. Virtualized/unstable variant exists (stable variant intact).
- True streaming flips streaming→complete deterministically. Six failure states render detectable markers (login/session-not-found/model-unavailable/truncated/rate-limited/selector-unavailable).
- Copy button writes exact latest text to clipboard on loopback; `copy_mode` variants (ok/missing/wrong/stale/truncated) implemented.
- `src/ask_chatgpt/selector_maps/mock.json` extended (new keys match DOM; old keys intact).
- `tests/test_fixture_adversarial.py` green; full `uv run pytest -q` green (12 existing still pass); zero new deps.
- Report with telemetry + `T4-STATUS:` last.
