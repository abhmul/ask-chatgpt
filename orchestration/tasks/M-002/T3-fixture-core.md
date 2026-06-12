# T3 — Mock-ChatGPT fixture CORE (loopback server, conversations, composer/send, latest-turn render + completion marker, control endpoints, mock selector map). TDD.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1+T2 are DONE and committed: package `ask_chatgpt` with `errors.py` (named errors) + `session_registry.py`; `tests/conftest.py` has an autouse socket guard; `tests/test_smoke.py` proves real headless-chromium-vs-127.0.0.1 works.

## STEP 0 — Confirm you inherit a GREEN tree
Run `uv sync --all-groups` then `uv run pytest -q`. MUST be green (9 passed). If not, STOP, report BLOCKED with output.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/decision-memo.md` — **§6 (lines ~91-100) is the BINDING mock-fixture requirements spec.** You implement the CORE subset here; T4 (a later leg) adds adversarial/failure/file affordances. Read §6 fully so your DOM/selector structure anticipates T4.
3. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001: the tool reads the **latest completed assistant turn only**, bounded, selector-map-scoped, with explicit completion detection. Your fixture must make that drivable and testable (and later, T4, adversarially testable).
4. READ-ONLY reuse reference (do NOT copy wholesale; adapt — it served the predecessor's Level-B seed-only model, ours must render assistant turns for READING): `/home/abhmul/Documents/weak-simplex-conjecture/control-plane/tests/fixtures/phase3_mock_chat.py` and `.../phase3_mock_selector_map.json`. (NEVER read that archive's `archive/` or `human/` dirs.)
5. `/home/abhmul/dev/ask-chatgpt/tests/conftest.py` — the existing socket guard (your server binds 127.0.0.1, so it works under the guard).

## Scope (CORE only — happy path + control plane; T4 does adversarial/failures/files)
Build a loopback HTTP mock of the ChatGPT web UI that Playwright can drive: open app → (new or existing conversation) → type into composer → send → assistant turn renders → completion marker appears → latest assistant turn is readable from the DOM. Plus control endpoints to reset/inspect/script it. Plus the mock selector map the driver will load.

### Deliverables (exact paths)
1. **Fixture package** under `tests/fixtures/` (suggested: `tests/fixtures/mock_chatgpt/` with `server.py` rendering HTML in Python via stdlib `http.server.ThreadingHTTPServer`; you choose internal file names). ZERO new dependencies — stdlib only (the project's only dep is `playwright`). The server:
   - Binds **127.0.0.1 on an EPHEMERAL port (port 0; read back the assigned port)**. NEVER a fixed port. Exposes `base_url` like `http://127.0.0.1:<port>`.
   - In-memory state: multiple **conversations keyed by stable conversation refs** (e.g. `conv-<slug>`), each holding an ordered list of turns (`user` and `assistant`). Supports reusing an existing ref vs creating a new conversation.
   - **UI routes** (server-rendered HTML; NO JavaScript required for the core happy path):
     - `GET /` — ready app shell: a chat list (`chat_list` containing `chat_item`s linking to each conversation), a `new_chat_button`, a `composer` (a `<textarea>`/`contenteditable`), a `send_button`, and a `model_menu` with selectable `model_option`s. Include a stable readiness marker element (`ready_root`).
     - `GET /c/<conversation_ref>` — renders that conversation's turns in order. Each assistant turn element carries `data-message-author-role="assistant"`, a unique `data-turn-id`, the conversation ref via `data-conversation-ref`, a message body element, and — when COMPLETE — a **completion marker** element (e.g. `[data-testid="assistant-turn-complete"]`). (A `streaming_marker` element, e.g. `[data-testid="assistant-streaming"]`, is the DONE-vs-streaming opposite; in CORE responses render COMPLETE immediately so the completion marker is present and the streaming marker absent. T4 adds true streaming.)
     - Sending: the `composer`+`send_button` submit (a plain `<form>` POST is fine, no JS) to a route that appends the user turn, generates the assistant turn (see scripting below), then `303`-redirects to `/c/<ref>` so the conversation page re-renders with the new completed assistant turn. New-chat creates a fresh ref and lands on its `/c/<ref>`.
   - **CONTROL routes** (these are the test/inspection plane — the DRIVER must NEVER use them; only tests/fixtures do). Per memo §6 "expose reset/failure/inspection endpoints":
     - `POST /__reset__` — clear all state.
     - `GET /__inspect__` — return JSON of current state (conversations, each turn's role+text, the last prompt received). Lets tests assert what the driver actually sent/created WITHOUT reading assistant text through the UI.
     - `POST /__script__` — set the assistant's NEXT response: JSON body `{ "text": "...", "conversation_ref": "...|null", "streaming": false, "complete": true }`. CORE: honor `text` (the next send yields exactly this assistant text, completed). Accept and store `streaming`/`complete`/failure-mode fields even if CORE always renders complete — T4 will consume them. Default (no script set) = a deterministic response (e.g. `"[mock] you said: <prompt>"`).
2. **Python handle + pytest fixture**: a pytest fixture named `mock_chatgpt` (put it where tests can import it — e.g. `tests/conftest.py` or `tests/fixtures/__init__.py`) that starts the server on an ephemeral port and `yield`s a handle object exposing at least: `.base_url: str`, `.reset() -> None`, `.script_next_response(text, *, conversation_ref=None, streaming=False, complete=True) -> None`, `.inspect() -> dict`. The handle wraps the CONTROL endpoints over HTTP (use stdlib `urllib`/`http.client` to localhost). Teardown MUST shut the server down and join its thread (no leaked threads/ports). Killing only what this fixture started.
3. **Mock selector map** at `src/ask_chatgpt/selector_maps/mock.json` — JSON the driver (T5) will load. Shape:
   ```json
   {"channel": "mock", "version": 1,
    "selectors": {"ready_root": "...", "chat_list": "...", "chat_item": "...", "new_chat_button": "...", "composer": "...", "send_button": "...", "model_menu": "...", "model_option": "...", "assistant_message": "...", "message_body": "...", "streaming_marker": "...", "completion_marker": "..."},
    "attributes": {"conversation_ref": "data-conversation-ref", "turn_id": "data-turn-id"}}
   ```
   Every selector value MUST actually match the DOM your server renders. (T4 will ADD keys: `copy_button`, `upload_input`, `download_artifact`, plus failure-state markers. Leave the structure extensible; do not remove core keys.) Also create `src/ask_chatgpt/selector_maps/__init__.py` if you want it importable, but keep maps as DATA (JSON), not code.

### TDD tests (write tests FIRST, watch fail, then implement) — `tests/test_fixture_core.py`
- **Control-plane (HTTP-level, fast):** start the `mock_chatgpt` fixture; `reset()`; `inspect()` returns empty; `script_next_response("hello-123")`; assert state via `inspect()`.
- **Drive-via-browser (Playwright, headless chromium — already cached):** load `base_url`; assert `ready_root` present; click `new_chat_button` (or navigate), locate `composer` via the SELECTOR-MAP value (load `src/ask_chatgpt/selector_maps/mock.json` and use its selectors — this proves the map matches the DOM), fill a prompt, click `send_button`; **wait for the `completion_marker`** on the latest assistant turn; read the latest assistant `message_body` text and assert it equals the scripted text. Assert exactly ONE latest completed assistant turn is identifiable. Tear down browser.
- A test asserting the server bound `127.0.0.1` and a NON-fixed port (port from `base_url` is ephemeral / not a hardcoded constant).
- Run `uv run pytest -q`; ALL tests green (prior 9 + new). Keep Playwright tests minimal and robust (generous but bounded waits for the completion marker; no `sleep`-spinning).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL work NEVER contact chatgpt.com/openai or any external network service. Your mock server binds **127.0.0.1 ONLY, EPHEMERAL port (bind 0, read back)** — NEVER a fixed port (the operator runs long-lived daemons). All browser navigation targets your loopback `base_url`.
- The ONLY ever-permitted external download is Playwright chromium — ALREADY CACHED at `~/.cache/ms-playwright`. Download nothing. ZERO new pip dependencies (stdlib + existing `playwright` only). Never sudo/apt/install.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents anywhere.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY (this repo's uv venv). NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest (do not spawn parallel pytest). Kill only processes/servers your run started; always tear down the server + thread. NEVER `git push`. Do NOT `git commit` (the manager commits verified slices).
- ESTIMATE BEFORE EXECUTE: state expected wall-clock + output volume before any command expected to exceed ~2 min (Playwright tests can be slow — note your estimate).

## Telemetry v2 (REQUIRED — write report to `orchestration/reports/M-002/T3-report.md`)
- Run `date -Iseconds` at START and END; write literal `START_TIMESTAMP:` and `END_TIMESTAMP:` lines.
- Emit `ESTIMATE: T3 <min>m` (your own estimate).
- Report ≤200 lines: files created (paths), the fixture handle API, the selector-map keys + that they match the DOM, the exact `uv run pytest -q` summary, how completion detection works in the DOM (which element/attribute), deviations, trust notes (confirm loopback-only + ephemeral port + thread teardown).
- End with `T3-STATUS: DONE` (or `BLOCKED` + exact error + next action) as the LAST line.

## Success criteria (all must hold)
- Loopback (127.0.0.1) ephemeral-port mock server; conversations by stable ref; composer/send creates a completed assistant turn; latest completed assistant turn is uniquely identifiable in the DOM with a completion marker.
- `POST /__reset__`, `GET /__inspect__`, `POST /__script__` control endpoints exist; `mock_chatgpt` pytest fixture yields a handle wrapping them; clean teardown.
- `src/ask_chatgpt/selector_maps/mock.json` exists and every selector matches the rendered DOM (proven by the Playwright test using the map's selectors).
- `tests/test_fixture_core.py` green; full `uv run pytest -q` green; zero new deps.
- Report written with telemetry lines and `T3-STATUS:` last.
