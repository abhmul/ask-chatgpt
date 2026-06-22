STATUS: DONE

## Findings

1. CONFIRM — Light-tab acquire. `src/ask_chatgpt/session.py:57` defines `_LIGHT_READ_URL = "https://chatgpt.com/"`; `src/ask_chatgpt/session.py:84-87` makes `render=True` the default, sets `url = conversation_url(ref) if render else _LIGHT_READ_URL`, and keys entries as `(mode, url)`. Reuse checks `entry.key == key` (`src/ask_chatgpt/session.py:90`) and new entries store that key (`src/ask_chatgpt/session.py:100`), so a light root tab and a rendered `/c/<id>` tab cannot collide. `conversation_url` returns `https://chatgpt.com/c/<id>` for non-project refs (`src/ask_chatgpt/identity.py:113-124`).

2. CONFIRM — `scrape` is the only source call site switched to light + ambient. Source call sites are `ask` (`src/ask_chatgpt/session.py:370`, default `render=True`), `scrape` (`src/ask_chatgpt/session.py:525`, `render=False`; `src/ask_chatgpt/session.py:527`, `header_mode="ambient_backend"`), and `loop` (`src/ask_chatgpt/session.py:583`, default `render=True`). `history` and `fetch` remain local-store reads with no tab acquisition (`src/ask_chatgpt/session.py:534-538`).

3. CONFIRM, with one narrow caveat — Default harvest remains exact/default on send/draft/completion. `acquire_backend_headers` defaults to `mode="conversation"` (`src/ask_chatgpt/capture.py:154-164`), and the conversation matcher is exactly `GET` plus `_request_path(request.url) == target_path` (`src/ask_chatgpt/capture.py:943-946`). `_run_send_turn` still reloads draft chats before capture (`src/ask_chatgpt/session.py:454-456`) and calls `capture_conversation` without `header_mode`, so it uses the default (`src/ask_chatgpt/session.py:457-461`; default declared at `src/ask_chatgpt/capture.py:329-336`). Completion polling still calls `acquire_backend_headers(tab, conv)` with no mode override (`src/ask_chatgpt/completion.py:45`). Caveat: the shared CDP `wait_for_request` implementation changed globally (`src/ask_chatgpt/channels/cdp.py:754-795`), so I would not claim the default path is byte-for-byte untouched; I do confirm it remains exact, all-required-header gated, and fail-closed.

4. CONFIRM end-to-end header-aware/fail-closed behavior; REFUTE the literal matcher-only wording. Ambient mode selects same-origin `GET /backend-api/*` (`src/ask_chatgpt/capture.py:950-956`) and, for non-empty observed headers, requires all eight `REQUIRED_CAPTURE_HEADERS` (`src/ask_chatgpt/capture.py:40-47`, `src/ask_chatgpt/capture.py:958-959`). Literal caveat: `src/ask_chatgpt/capture.py:959` also returns true for empty header snapshots (`not headers`), which is needed because CDP first probes predicates with an empty redacted header map (`src/ask_chatgpt/channels/cdp.py:772-773`). The CDP wait then does not return deficient requests early: it computes missing required headers (`src/ask_chatgpt/channels/cdp.py:777`, `:786`), returns only when none are missing (`src/ask_chatgpt/channels/cdp.py:778-779`, `:787-788`), otherwise keeps them pending (`src/ask_chatgpt/channels/cdp.py:781-791`) until timeout. On timeout it may return the best deficient snapshot (`src/ask_chatgpt/channels/cdp.py:792-794`), and `acquire_backend_headers` converts missing headers to `BackendAuthUnavailableError` (`src/ask_chatgpt/capture.py:181-195`). The default conversation mode is not weakened: missing headers in `mode == "conversation"` raise immediately after the returned deficient snapshot (`src/ask_chatgpt/capture.py:192-195`).

5. CONFIRM — Retargeting. `retarget_headers` copies headers, removes any existing `x-openai-target-path`, and sets it to the actual fetch path (`src/ask_chatgpt/capture.py:82-89`). It intentionally does not rewrite `x-openai-target-route` (`src/ask_chatgpt/capture.py:90`). The conversation fetch path is derived as `/backend-api/conversation/<id>` and used for both retargeting and the actual fetch (`src/ask_chatgpt/capture.py:199-209`; pre-retarget in `capture_conversation` at `src/ask_chatgpt/capture.py:342-344`).

6. CONFIRM — Fetch origin survives light root. `stream_backend_conversation` passes the relative backend path to `fetch_in_page` (`src/ask_chatgpt/capture.py:201-207`). CDP resolves relative paths for allowlisting against `tab.url` (`src/ask_chatgpt/channels/cdp.py:327-336`, used at `src/ask_chatgpt/channels/cdp.py:809-810`), and the browser-side JS fetches `url` in page context with credentials included (`src/ask_chatgpt/channels/cdp.py:63-66`). From a `https://chatgpt.com/` light tab, `/backend-api/conversation/<id>` is therefore same-origin.

## Correctness defects / severity

- No BLOCKING or MAJOR correctness defect found.
- MINOR spec-boundary caveat: `_ambient_backend_header_request_matcher` is not literally “only all-8 headers” because it accepts empty header snapshots at `src/ask_chatgpt/capture.py:959`. End-to-end behavior remains fail-closed via `CdpChannel.wait_for_request` and `acquire_backend_headers`, so I do not treat this as a source correctness blocker.

## Default-path verdict

The DEFAULT send/draft/completion path is provably unchanged in the properties that matter for M7b: rendered `/c/<id>` tab acquisition, exact `/backend-api/conversation/<id>` harvest, required-header validation, and draft reload-before-capture are intact. It is not literally dependency-unchanged because `CdpChannel.wait_for_request` changed globally; that change does not weaken default fail-closed behavior.

## Risks / unknowns

- Offline code inspection cannot prove the live root page always emits a same-origin backend GET with all eight required headers.
- `x-openai-target-route` remains a live-site seam; code preserves it verbatim pending M10-T4 evidence.
- I did not run `uv run pytest`; this handoff is from code/diff inspection only.

## Recommended next steps

- Add/keep a CDP-level regression proving a deficient matching request is skipped when a later complete matching request appears.
- Real-site M10-T4 should verify root-page ambient header availability and the route-template rule before any route retargeting.
