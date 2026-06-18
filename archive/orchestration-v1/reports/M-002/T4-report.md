START_TIMESTAMP: 2026-06-12T00:18:11-05:00
ESTIMATE: T4 45m

STEP 0 inherited-tree check: `uv sync --all-groups` succeeded, then `uv run pytest -q` reported `12 passed in 1.09s`.

Files touched:
- `tests/test_fixture_adversarial.py` added Playwright TDD coverage for booby-trap latest-turn targeting, virtualized DOM, streaming flip, six honest-failure states, and copy/clipboard modes.
- `tests/fixtures/mock_chatgpt/server.py` extended the loopback stdlib mock fixture without replacing the T3 core endpoints.
- `src/ask_chatgpt/selector_maps/mock.json` extended selector keys while retaining existing keys.
- `orchestration/reports/M-002/T4-report.md` written.

TDD:
- Red check before implementation: `uv run pytest -q tests/test_fixture_adversarial.py` produced 11 failing tests against the T3 fixture.
- After implementation: `uv run pytest -q tests/test_fixture_adversarial.py` reported `11 passed in 4.89s`.

Scriptable modes/fields added:
- `/__script__` text-only payload remains next-response scripting for existing tests.
- `/__script__` with `turns` seeds a full conversation immediately; each turn supports `role`, `text`, `complete`, `streaming`, `stream_reads`, `truncated`, and optional `turn_id`.
- `layout_variant`: `stable` default; `virtualized` renders older turns as placeholder stubs and latest targetable turn with alternate `mock-message-content` body.
- `copy_mode`: `ok` writes exact latest completed assistant text; `missing` omits the copy button; `wrong` writes an older assistant text; `stale` leaves clipboard unchanged; `truncated` writes the first half of latest text.
- `mode`/`failure_mode`: `login_required`, `session_not_found`, `model_unavailable`, `response_truncated`, `rate_limited`, `selector_unavailable`; `normal`/`none`/`ok`/`clear` clears failure mode.
- `unavailable_model` selects which model option is disabled in `model_unavailable` mode.

Selector keys added:
- `copy_button` -> `[data-testid="mock-copy-button"]`
- `login_wall` -> `[data-testid="login-wall"]`
- `conversation_not_found` -> `[data-testid="conversation-not-found"]`
- `truncation_marker` -> `[data-testid="assistant-truncated"]`
- `rate_limit_marker` -> `[data-testid="rate-limit"]`
- `model_option_disabled` -> `[data-testid="mock-model-option"][data-disabled="true"]`
- `message_body` now also matches the virtualized alternate body via `[data-testid="mock-message-content"]`.

Streaming flip:
- Streaming turns start with `streaming=True`, `complete=False`, and `stream_reads_remaining=N` from `stream_reads` (default 2).
- Each `GET /c/<ref>` advances the counter deterministically: first N reads render `assistant-streaming` and no completion marker; the next read flips to `complete=True`, removes streaming, and renders `assistant-turn-complete` with final text.

Honest-failure rendering:
- `login_required`: `GET /` shows `[data-testid="login-wall"]` and omits the composer.
- `session_not_found`: `GET /c/<ref>` returns a not-found page with `[data-testid="conversation-not-found"]` and HTTP 404.
- `model_unavailable`: requested option is disabled with `data-disabled="true"`.
- `response_truncated`: latest assistant turn shows `[data-testid="assistant-truncated"]` and no completion marker.
- `rate_limited`: send path renders `[data-testid="rate-limit"]` with `data-retry-after-seconds="60"`.
- `selector_unavailable`: ready root renders but required composer selector is absent.

Final verification:
- `uv run pytest -q` reported `23 passed in 5.98s`.

Deviations: none from T4 scope; upload/download/fenced-base64 remain deferred to T4b.

Trust notes:
- Mock server still binds `127.0.0.1` only on an ephemeral port.
- Tests navigated only to the loopback `mock_chatgpt.base_url`; no chatgpt.com/OpenAI/external service access was added.
- Clipboard permissions were granted only to the loopback browser context origin.
- Booby-trap/sentinel strings are synthetic test content, not secrets.
- No new dependencies, no sudo/apt/pip, no git commit/push.

END_TIMESTAMP: 2026-06-12T00:28:56-05:00
T4-STATUS: DONE
