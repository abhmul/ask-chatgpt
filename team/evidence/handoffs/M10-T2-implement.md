STATUS: DONE

## Verification

Final `uv run pytest` summary line: `============================= 275 passed in 1.04s ==============================`. Baseline was 268 passed; this adds 7 tests for 275 total. Targeted pre-full run also passed: `94 passed in 0.84s` for capture/session/draft/completion/CDP coverage.

## Commits

- Implementation source/tests commit: `fe11886` (`Fix scrape light-page backend harvest`).
- Handoff is committed separately on branch `fix/m10-light-read-scrape`; no push/merge performed and `stable` was not touched.

## Files and functions changed

- `src/ask_chatgpt/session.py:57`, `:61`, `:84`, `:516`: added `_LIGHT_READ_URL`, keyed `_ManagedTab` by `(mode, url)`, extended `TabPool.acquire(ref, *, render=True)`, and changed only `Session.scrape` to acquire `render=False` and call `capture_conversation(..., header_mode="ambient_backend")`. `ask` and `loop` remain on default render acquisition.
- `src/ask_chatgpt/capture.py:49`, `:63`, `:82`, `:154`, `:199`, `:329`, `:943`: added `HeaderHarvestMode`, optional `HeaderBundle.for_single_fetch(fetch_path=...)`, `retarget_headers`, default exact vs opt-in ambient header harvest, conversation-fetch header retargeting, `capture_conversation(..., header_mode="conversation")`, and exact/ambient matcher helpers.
- `src/ask_chatgpt/channels/cdp.py:754`: changed `CdpChannel.wait_for_request` to retain header-deficient matching requests as pending and keep scanning for a later all-required-header match until timeout, while still returning the best deficient snapshot on timeout for the existing fail-closed path.
- `tests/test_capture.py:189`, `:215`, `:239`, `:262`: added mock tests for light scrape + generic harvest, ambient skip of deficient requests, default exact harvest ignoring generic backend requests, and target-path retargeting.
- `tests/test_session_stubs.py:57`, `:78`, `:109`: added pool-key collision, tab-free history/fetch, and ask/loop render-tab regression guards.

## New tests and what each falsifies

- `test_scrape_uses_light_root_and_generic_backend_header_harvest`: falsifies any implementation that still opens `/c/<id>` for `scrape` or still requires observing `/backend-api/conversation/<id>` for header harvest.
- `test_ambient_backend_header_harvest_skips_deficient_requests`: falsifies accepting the first same-origin `/backend-api/*` request when it lacks one of the eight required capture headers.
- `test_conversation_harvest_default_ignores_generic_backend_requests`: falsifies changing the default send/completion/draft harvest from exact conversation matching to ambient matching.
- `test_conversation_fetch_retargets_harvested_target_path`: falsifies passing a harvested generic `x-openai-target-path` verbatim into the conversation fetch; also asserts `x-openai-target-route` is preserved verbatim.
- `test_light_and_render_pool_keys_do_not_collide`: falsifies URL-only pool keying by requiring separate light-root and rendered conversation entries for the same conversation ref.
- `test_history_and_fetch_remain_tab_free_local_reads`: falsifies regressions that make local `history` or cached attachment `fetch` open a browser tab.
- `test_ask_and_loop_keep_render_conversation_tabs`: falsifies changing persisted send paths to light-root tabs.

## Route-header handling seam

`retarget_headers(headers, fetch_path)` at `src/ask_chatgpt/capture.py:82` is the explicit seam. It copies the outgoing header dict and sets `x-openai-target-path` to the actual fetch path, e.g. `/backend-api/conversation/<id>`. It intentionally keeps harvested `x-openai-target-route` verbatim, with a TODO for M10-T4 because the route-template rule is real-leg-gated and was not guessed offline.

## Residual risk / verifier notes

- Live root-page reliability remains a real-leg question: mocks prove the mode selection and fail-closed behavior, not that `https://chatgpt.com/` always emits an all-8-header same-origin backend GET for every account/feature state.
- `x-openai-target-route` may be path-specific; this implementation preserves it verbatim pending M10-T4 real evidence.
- Attachment descriptor/byte fetches still reuse the retargeted conversation header dict as before; existing mock attachment tests are green, but a small attended attachment scrape is still prudent before claiming live attachment coverage.
- The unrelated dirty/untracked files present on entry were not staged or modified by this implementation work.
