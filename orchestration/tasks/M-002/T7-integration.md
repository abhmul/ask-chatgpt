# T7 — ask_chatgpt() integration + UC1 E2E + scripts/accept_uc1.sh + network-guard completion. TDD.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1–T6 DONE/committed. The package `ask_chatgpt` has: `errors.py`, `session_registry.py` (`SessionRegistry` + `ConversationRef`, overridable store path), `selector_map.py` (fail-closed), `driver.py` (`BrowserSession` channel mock/real; `open_or_create_conversation`, `select_model`, `send_prompt`, `wait_for_completion`), `readers.py` (`read_response`, DOM-primary). The mock fixture is complete; `tests/conftest.py` has the `mock_chatgpt` fixture + an autouse socket guard blocking non-loopback. 50 tests green.

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be green (50 passed). If not, STOP, report BLOCKED with output.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/README.md` §Specification UC1 + §Acceptance shape — the BINDING product intent: `ask_chatgpt(prompt, session_identifier, model_settings...) -> text`; same identifier returns to the same conversation (continuity); model_settings selects model where the UI allows; honest failures named actionably. Automated acceptance vs the LOCAL MOCK; NEVER chatgpt.com.
3. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/driver.py`, `readers.py`, `session_registry.py`, `errors.py` — the pieces you wire. Note `BrowserSession(channel=..., base_url=..., profile_path=...)`, its context-manager lifecycle, `wait_for_completion() -> Locator`, and `read_response(turn, page, selectors, order=None)`.
4. `/home/abhmul/dev/ask-chatgpt/tests/conftest.py` — the `mock_chatgpt` fixture (`.base_url`, `.reset()`, `.script_next_response(...)`, `.inspect()`) and the autouse socket guard (you EXTEND the guard story; do not weaken it).
5. `/home/abhmul/dev/ask-chatgpt/tests/test_driver.py` + `tests/test_readers.py` — how the pieces are driven against the mock; mirror that style.

## Scope
### 1. Public function `ask_chatgpt(...)` in `src/ask_chatgpt/__init__.py` (or `src/ask_chatgpt/api.py` re-exported from `__init__`)
Signature (refine names sensibly, keep these semantics):
```python
def ask_chatgpt(prompt, *, session_identifier=None, model_settings=None,
                channel="real", base_url=None, profile_path=None,
                registry=None, reader_order=None, timeout_s=30.0) -> str
```
Wiring: resolve `registry` (default `SessionRegistry()`); if `session_identifier` maps to a stored `ConversationRef`, reuse its `conversation_ref`, else None (new). Open a `BrowserSession(channel, base_url, profile_path)` (context-managed); `open_or_create_conversation(ref)`; `select_model(model_settings)`; `send_prompt(prompt)`; `turn = wait_for_completion(timeout_s)`; `text = read_response(turn, session.page, session.selectors, order=reader_order)`. On success, if `session_identifier` given, `registry.set(session_identifier, ConversationRef(conversation_ref=active_ref, url=<conversation url>, model_settings=model_settings))` so the NEXT call with the same identifier returns to the SAME conversation. Named errors propagate (login/session/model/truncated/selector/rate-limit). `channel="real"` is the PRODUCT default but is NEVER exercised by any test (real needs `profile_path`; tests always pass `channel="mock", base_url=mock_chatgpt.base_url`). Export `ask_chatgpt` (and the error types) from the package top level.

### 2. UC1 E2E tests — `tests/test_ask_chatgpt_uc1.py` (write FIRST, watch fail, implement), channel="mock" only
- **Continuity (CORE UC1):** call `ask_chatgpt(prompt1, session_identifier="s1", channel="mock", base_url=..., registry=<tmp registry>)`, then `ask_chatgpt(prompt2, session_identifier="s1", ...)` with the SAME registry → assert BOTH prompts landed in the SAME conversation (via `mock_chatgpt.inspect()`), and the registry stored the mapping. A DIFFERENT `session_identifier` → a DIFFERENT conversation.
- **Returns text:** the returned string equals the scripted assistant text; a booby-trap older turn's sentinel is NOT in it.
- **model_settings:** a call selecting an AVAILABLE model succeeds; an UNAVAILABLE model → `ModelUnavailableError`.
- **Honest failure (≥1):** script `login_required` → `ask_chatgpt(...)` raises `LoginRequiredError` with an actionable message; (optionally also session_not_found/truncated).
- Use a `SessionRegistry(store_path=tmp_path/...)` so nothing writes to the real user-state dir.

### 3. `scripts/accept_uc1.sh` — scripted UC1 acceptance producing RAW artifacts
A bash script (executable) that runs a Python acceptance driver via `uv run` and writes raw artifacts to `tmp/accept-uc1-<timestamp>/`:
- Create `scripts/accept_uc1.py` (the driver) + `scripts/accept_uc1.sh` (the wrapper). The `.sh`: compute `OUT=tmp/accept-uc1-$(date +%Y%m%d-%H%M%S)`, `mkdir -p "$OUT"`, run `uv run python scripts/accept_uc1.py --out "$OUT" | tee "$OUT/stdout.log"`, propagate a NON-ZERO exit if the python driver fails (use `set -o pipefail`), print the artifact dir.
- `accept_uc1.py`: starts the mock server on an EPHEMERAL loopback port (import the fixture server module — make it importable from a script, e.g. add repo `tests` to `sys.path` or expose a `start()` helper). Uses a `SessionRegistry(store_path=<OUT>/sessions.json)`. Performs, capturing each step's outcome:
  1. `ask_chatgpt(channel="mock", base_url=..., session_identifier="accept-s1")` → record returned text.
  2. a SECOND call with the SAME `session_identifier` → record + assert continuity (same conversation via the server's `/__inspect__`).
  3. a `model_settings` call selecting an available model → record success.
  4. at least ONE honest-failure case (script `login_required`, expect `LoginRequiredError`) → record that the named error was raised with its message.
  Write `results.json` (a list of steps each with name/status/detail + an `overall` pass/fail), `stdout.log`, and the per-step data into `$OUT/`. EXIT NON-ZERO if ANY step fails. Tear down the server. channel="mock" ONLY; loopback ONLY; NEVER real/chatgpt.com.
- Run it once yourself: `bash scripts/accept_uc1.sh`; confirm exit 0 and that `tmp/accept-uc1-*/results.json` + `stdout.log` exist with `overall: pass`. (tmp/ is gitignored — the SCRIPT is committed, the artifacts are not.)

### 4. Network-guard completion — `tests/test_network_guard.py` + Playwright route interception
- **Deliberate-violation demo (REQUIRED):** a test that ATTEMPTS a non-loopback TCP connect (e.g. `socket.create_connection(("93.184.216.34", 80), timeout=1)`) and asserts the autouse guard TRIPS (raises `RuntimeError` matching `NETWORK BLOCKED`). This proves the guard actually blocks egress (the verify leg T9 will rely on this).
- **Playwright route interception:** in the MOCK browser context (extend `BrowserSession`'s mock context creation in `driver.py`, OR a test helper), add `context.route("**/*", handler)` that ABORTS any request whose URL host is NOT loopback (127.0.0.1/localhost/::1). For the mock all traffic is loopback (no-op), but it is belt-and-suspenders browser-level egress blocking. Add a test asserting a `page.goto` to a non-loopback URL is blocked (by the socket guard and/or the route). Keep real-channel behavior unchanged.
- Full `uv run pytest -q` GREEN (50 existing + new).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Tests, the acceptance script, and ALL work NEVER contact chatgpt.com/openai or any external service. Everything uses channel="mock" + the loopback fixture on EPHEMERAL ports. `channel="real"` is the product default but NO test/script invokes it. The socket guard must remain autouse and STRICTER-or-equal; the violation-demo test proves it trips.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. `profile_path` stays opaque. The acceptance `results.json`/logs contain only synthetic prompts + outcomes — no secrets.
- The ONLY ever-permitted external download is chromium — ALREADY CACHED. ZERO new pip deps (existing `playwright`). Never sudo/apt/install.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/` for acceptance artifacts). Archive READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY. NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Tear down servers/browsers you start. NEVER `git push`. Do NOT `git commit`. Do not break the 50 existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-002/T7-report.md`)
- `date -Iseconds` at START + END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- `ESTIMATE: T7 <min>m`.
- Report ≤200 lines: files created/modified, the `ask_chatgpt` signature + wiring, how continuity is proven, the acceptance-script artifact layout + the exact path of the run you produced (`tmp/accept-uc1-*/`) + its `overall` verdict, how the network-guard violation-demo trips, the exact `uv run pytest -q` summary, deviations, trust notes.
- End with `T7-STATUS: DONE` (or `BLOCKED` + exact error + next action) LAST.

## Success criteria (all must hold)
- `ask_chatgpt(...)` wired (registry→driver→reader), continuity via `session_identifier`, model_settings, named-error propagation; exported from package top-level; `channel="real"` default but never tested.
- `tests/test_ask_chatgpt_uc1.py` proves continuity (same id → same conversation; different id → different), returns scripted text (no sentinel), model_settings success+unavailable, ≥1 honest failure.
- `scripts/accept_uc1.sh` + `scripts/accept_uc1.py`: run once, exit 0, produced `tmp/accept-uc1-*/results.json` (`overall: pass`) + `stdout.log`; exits NON-ZERO on any failure; ephemeral loopback port; channel="mock" only.
- `tests/test_network_guard.py` violation-demo proves the guard trips on a deliberate non-loopback attempt; Playwright route interception added for mock browser tests.
- Full `uv run pytest -q` green (50 existing pass); zero new deps.
- Report with telemetry + `T7-STATUS:` last.
