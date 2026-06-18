START_TIMESTAMP: 2026-06-12T00:05:27-05:00
ESTIMATE: T3 45m
END_TIMESTAMP: 2026-06-12T00:12:22-05:00

STEP 0: `uv sync --all-groups` completed, then inherited `uv run pytest -q` was green: `9 passed in 0.39s`.

Files created:
- `tests/test_fixture_core.py`
- `tests/fixtures/__init__.py`
- `tests/fixtures/mock_chatgpt/__init__.py`
- `tests/fixtures/mock_chatgpt/server.py`
- `src/ask_chatgpt/selector_maps/__init__.py`
- `src/ask_chatgpt/selector_maps/mock.json`

Files modified:
- `tests/conftest.py` adds the `mock_chatgpt` pytest fixture.

Fixture handle API: `mock_chatgpt.base_url: str`, `.host`, `.port`, `.requested_port`, `.reset() -> None`, `.script_next_response(text, *, conversation_ref=None, streaming=False, complete=True, **failure_fields) -> None`, and `.inspect() -> dict`.

Implemented server behavior: stdlib `ThreadingHTTPServer` binds `127.0.0.1` with requested port `0`, exposes `GET /`, `GET /c/<conversation_ref>`, form POST send/new-chat routes, and control endpoints `POST /__reset__`, `GET /__inspect__`, `POST /__script__`. State is in-memory conversations keyed by stable refs such as `conv-1`, with ordered user/assistant turns and deterministic default responses.

Selector-map keys: `ready_root`, `chat_list`, `chat_item`, `new_chat_button`, `composer`, `send_button`, `model_menu`, `model_option`, `assistant_message`, `message_body`, `streaming_marker`, `completion_marker`; attributes: `conversation_ref`, `turn_id`. The Playwright test loads `src/ask_chatgpt/selector_maps/mock.json` and drives/asserts against those selectors, proving the map matches the rendered DOM for the core happy path.

Completion detection: completed assistant turns are `[data-message-author-role="assistant"]` elements with `data-turn-id`, `data-conversation-ref`, a `[data-testid="mock-message-body"]` child, and a `[data-testid="assistant-turn-complete"]` child. CORE renders completion immediately and no `[data-testid="assistant-streaming"]` child is present.

TDD: wrote `tests/test_fixture_core.py` first and observed expected failure (`fixture 'mock_chatgpt' not found`), then implemented the fixture/server/selector map and reran tests.

Final test command: `uv run pytest -q`.

Final test summary: `12 passed in 1.14s`.

Deviations: none for CORE scope. True streaming, adversarial/failure states, copy/download/upload/file affordances are intentionally deferred to T4; `POST /__script__` accepts and stores streaming/complete/failure fields while pending, but CORE consumes responses as completed turns.

Trust notes: browser navigation targets only the loopback `base_url`; no chatgpt.com/OpenAI/external service contacted; no downloads or new dependencies added; control handle uses stdlib `urllib`; teardown calls `shutdown()`, `server_close()`, and `thread.join(timeout=5)` for only the server this fixture starts. `uv` emitted the ambient `VIRTUAL_ENV` mismatch warning but used the repo `.venv`; no agent Python environment was touched.
T3-STATUS: DONE
