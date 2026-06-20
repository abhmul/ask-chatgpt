# M5-E1 CDP channel report

Status: DONE.

Files created/modified by this editor: `src/ask_chatgpt/channels/cdp.py`, `tests/test_cdp_channel.py`, `scripts/m5_capture_measure.py`, `src/ask_chatgpt/session.py`, `src/ask_chatgpt/capture.py`, `team/evidence/reports/M5-E1-cdp-channel.md`.

Branch/safety: work was performed on `rewrite-v2`; `stable` remains `779eb40b196e1a458a820248b2dbbca22411b0d3`; no git add/commit/push was run; no browser/CDP/network leg was run; I did not touch `issues/cdp-send-repro/controller.mjs` or `team/state/live-state.json`.

Authoritative `uv run pytest` tail:

```text
tests/test_store_payload.py ...                                          [ 96%]
tests/test_store_pending_send.py ..                                      [ 97%]
tests/test_store_read_semantics.py .                                     [ 98%]
tests/test_store_render.py .                                             [ 98%]
tests/test_store_torn_line.py ...                                        [100%]

============================= 205 passed in 0.41s ==============================
```

Additional offline checks: `uv run python -c "import ast; ast.parse(open('scripts/m5_capture_measure.py', encoding='utf-8').read())"` passed; `uv run python scripts/m5_capture_measure.py --help` printed help without connecting; `uv run python -c "import sys, ask_chatgpt, ask_chatgpt.channels.cdp; ask_chatgpt.channels.cdp.CdpChannel(); print(any(n == 'playwright' or n.startswith('playwright.') for n in sys.modules))"` printed `False`.

Offline test list mapped to tests: lazy import is covered by `test_cdp_channel_import_and_construction_are_playwright_lazy`; preflight mapping is covered by `test_preflight_maps_http_failures_to_redacted_cdp_unreachable`, `test_preflight_maps_version_json_without_leaking_websocket_url`, and `test_preflight_missing_websocket_is_cdp_unreachable`; allowlist-before-Playwright is covered by `test_open_tab_and_fetch_reject_disallowed_urls_before_playwright_factory`; own-tabs-only lifecycle is covered by `test_attach_open_close_detach_own_pages_without_context_page_enumeration`; Protocol shapes/read DOM/fetch are covered by `test_fetch_in_page_returns_protocol_shapes_and_filters_sensitive_response_headers` and `test_dom_read_methods_delegate_to_owned_page_and_return_protocol_dataclasses`; request observation/CDP ExtraInfo fallback/deficient snapshot is covered by `test_wait_for_request_uses_cheap_predicate_projects_headers_and_cdp_fallback`; stream decoding is covered by `test_consume_stream_event_reassembles_bytes_and_rejects_bad_events`; redaction canaries are covered across wait/fetch/vocab plus `test_fetch_in_page_sanitizes_page_evaluate_exceptions`; completion vocabulary is covered by `test_catalogue_completion_status_vocab_redacts_progress_payloads`; action-method zero-send safety is covered by `test_cdp_action_methods_are_read_only_deferred`; measurement script import safety is covered by `test_m5_capture_measure_script_imports_without_running_cdp`.

Real-leg-verified-only and not proven offline: successful `sync_playwright().start()` and `chromium.connect_over_cdp`; whether `browser.contexts[0]` is the operator signed-in context; live `context.new_page()` auth inheritance; live `page.goto` timing and target request observation; whether live `Request.all_headers()` exposes all eight required headers; whether same-page CDP `Network.requestWillBeSentExtraInfo` is needed and correlates by request id; live in-page exposed-binding streaming on smoke/~17MB conversations; RSS/tracemalloc budgets; `browser.close()` after CDP attach leaving Chromium/foreign tabs alive.

Redaction proof: `RequestSnapshot.headers` uses a redacted-repr mapping, CDP ExtraInfo stores only required header names/values and never full maps/cookies, `FetchResult` contains response headers only after dropping `authorization`/`cookie`/`set-cookie`/`oai-*`, fake canary header values are absent from snapshot/fetch/vocab reprs and sanitized fetch exceptions, and `catalogue_completion_status_vocab` hashes/summarizes `pro_progress` payloads without content.

Deviations/notes: `detach()` follows the contract and lens A by calling `browser.close()` once for a CDP-connected browser, then `playwright.stop()`; this intentionally resolves the lens C wording conflict in favor of the contract acceptance test. CDP fallback currently requires a matching `requestId` rather than URL/method fallback, to avoid accidentally reusing stale required-header values from an older same-URL request; the attended leg must confirm request-id availability or that `all_headers()` is sufficient. Fetch exceptions from `page.evaluate` are deliberately sanitized with suppressed context to prevent header-value leaks, at the cost of less detailed local diagnostics.

Blockers: none for offline acceptance; all remaining uncertainty is real-leg-only.
