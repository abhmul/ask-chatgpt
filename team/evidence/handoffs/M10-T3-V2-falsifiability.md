STATUS: DONE

## Mutation results

All seven requested tests were run individually under a minimal production mutation and failed as expected. After each mutation I restored the touched file with `git checkout -- <path>` and verified no diff/status on the mutated source/test paths before proceeding.

| # | Test | Mutation applied | Only-test command | Observed result | Restored? |
|---:|---|---|---|---|---|
| 1 | `tests/test_capture.py::test_scrape_uses_light_root_and_generic_backend_header_harvest` | `src/ask_chatgpt/session.py`: changed `Session.scrape` acquisition from `render=False` to default render. | `uv run pytest tests/test_capture.py::test_scrape_uses_light_root_and_generic_backend_header_harvest -q` | FAILED-as-expected: `open_urls` was `https://chatgpt.com/c/conv_mock_light_scrape`, not `https://chatgpt.com/`. | yes |
| 2 | `tests/test_capture.py::test_ambient_backend_header_harvest_skips_deficient_requests` | `src/ask_chatgpt/capture.py`: changed ambient backend matcher to accept the first same-origin `/backend-api/*` request regardless of headers. | `uv run pytest tests/test_capture.py::test_ambient_backend_header_harvest_skips_deficient_requests -q` | FAILED-as-expected: first deficient request was accepted and `BackendAuthUnavailableError` was raised for missing required headers. | yes |
| 3 | `tests/test_capture.py::test_conversation_harvest_default_ignores_generic_backend_requests` | `src/ask_chatgpt/capture.py`: changed `acquire_backend_headers` default mode from `conversation` to `ambient_backend`. | `uv run pytest tests/test_capture.py::test_conversation_harvest_default_ignores_generic_backend_requests -q` | FAILED-as-expected: harvested authorization was `Bearer MOCK_GENERIC_REQUEST` instead of `Bearer MOCK_EXACT_CONVERSATION_REQUEST`. | yes |
| 4 | `tests/test_capture.py::test_conversation_fetch_retargets_harvested_target_path` | `src/ask_chatgpt/capture.py`: made `retarget_headers` return harvested headers verbatim instead of overwriting `x-openai-target-path`. | `uv run pytest tests/test_capture.py::test_conversation_fetch_retargets_harvested_target_path -q` | FAILED-as-expected: recorded fetch header kept `/backend-api/accounts/check` instead of `/backend-api/conversation/conv_mock_retarget_path`. | yes |
| 5 | `tests/test_session_stubs.py::test_light_and_render_pool_keys_do_not_collide` | `src/ask_chatgpt/session.py`: changed pool key to old conversation-URL-only key, ignoring light/render mode. | `uv run pytest tests/test_session_stubs.py::test_light_and_render_pool_keys_do_not_collide -q` | FAILED-as-expected: rendered acquire reused the light root tab (`light_tab is render_tab`). | yes |
| 6 | `tests/test_session_stubs.py::test_history_and_fetch_remain_tab_free_local_reads` | `src/ask_chatgpt/session.py`: added a tab acquisition to `Session.fetch` after local transcript load. | `uv run pytest tests/test_session_stubs.py::test_history_and_fetch_remain_tab_free_local_reads -q` | FAILED-as-expected: `NoOpenTabChannel.open_tab` raised `AssertionError: tab-free read unexpectedly opened https://chatgpt.com/c/conv_repeated_123`. | yes |
| 7 | `tests/test_session_stubs.py::test_ask_and_loop_keep_render_conversation_tabs` | `src/ask_chatgpt/session.py`: changed both `ask` and `loop` acquires to `render=False`. | `uv run pytest tests/test_session_stubs.py::test_ask_and_loop_keep_render_conversation_tabs -q` | FAILED-as-expected: fake send asserted tab URL was conversation URL, but got `https://chatgpt.com/`. | yes |

## Circularity / absence-of-assertion audit

- No test appeared circular in the strong sense: each assertion reads actual calls/headers returned by the production path under a mock scenario with distinguishable negative and positive observations.
- Severity MEDIUM coverage gap for test #3: it proves `acquire_backend_headers(...)` defaults to exact conversation harvest, but it is not an end-to-end send/draft/completion-path assertion. A regression that leaves `acquire_backend_headers` default exact but changes `capture_conversation` default or makes `_run_send_turn` pass `header_mode="ambient_backend"` could evade this specific test.
- Severity LOW wording caveat for test #5: the failing mutation used the historical/buggy conversation-URL-only key. Removing the `mode` dimension while keying by the actual opened URL would not collide for current root-vs-conversation URLs, so the test falsifies collision behavior rather than every possible "URL-only" implementation.
- Test #6 was empirically mutated on `fetch`; `history` is guarded by the same `NoOpenTabChannel` and would fail before `fetch` if it acquired a tab.

## Full suite

Final full-suite command: `uv run pytest`

Exact summary line: `============================= 275 passed in 1.01s ==============================`

## Restoration / git state

Entry HEAD and final pre-handoff HEAD were unchanged: `8f42496afb0e416efba579c400bd1c821f99f409`.

Mutation paths restored clean; this command produced no output before writing this handoff: `git status --porcelain=v1 -- src/ask_chatgpt/session.py src/ask_chatgpt/capture.py src/ask_chatgpt/channels/cdp.py tests/test_capture.py tests/test_session_stubs.py`.

Repo-wide `git status --porcelain=v1` was not empty before this verifier started and remained not empty before writing this handoff; I did not touch or clean unrelated/human files. Pre-handoff repo-wide output was:

```text
 M issues/cdp-send-repro/controller.mjs
 M team/state/live-state.json
 M uv.lock
?? human/
?? issues/2026-06-20-cli-leaks-browser-tab-per-invocation.md
?? issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md
?? issues/2026-06-22-read-ops-render-full-conversation-page.md
?? team/contracts/M10-T1-L1-readpath.md
?? team/contracts/M10-T1-L2-authharvest.md
?? team/contracts/M10-T1-L3-fixdesign.md
?? team/contracts/M10-T2-implement.md
?? team/contracts/M10-T3-V1-correctness.md
?? team/contracts/M10-T3-V2-falsifiability.md
?? team/contracts/M10-T3-V3-safety-regression.md
?? team/contracts/M10-common.md
?? team/evidence/handoffs/M10-T1-L1-readpath.md
?? team/evidence/handoffs/M10-T1-L2-authharvest.md
?? team/evidence/handoffs/M10-T1-L3-fixdesign.md
?? team/evidence/handoffs/M10-T3-V1-correctness.md
?? team/evidence/handoffs/M10-T3-V3-safety-regression.md
```

No mutation was committed, no mutation was left in source/tests, and nothing was pushed.
