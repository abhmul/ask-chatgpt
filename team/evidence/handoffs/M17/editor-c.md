DONE

## Files changed/created
- `src/ask_chatgpt/governor.py:29` added the operator-owned default warning; `src/ask_chatgpt/governor.py:42` added `GovernorConfig`; `src/ask_chatgpt/governor.py:68` added the file-lock token-bucket `Governor`; `src/ask_chatgpt/governor.py:94` added `acquire`; `src/ask_chatgpt/governor.py:121` added `note_rate_limited`; `src/ask_chatgpt/governor.py:223` added `raise_for_rate_limit` with integer-only `Retry-After` parsing.
- `src/ask_chatgpt/errors.py:226` added `RateLimitedError` (`RATE_LIMITED`, exit 52, retryable/back_off); `src/ask_chatgpt/errors.py:296` exported it.
- `src/ask_chatgpt/cli.py:43` added `RATE_LIMITED: 52`; existing generic `AskChatGPTError` path at `src/ask_chatgpt/cli.py:104` remains the non-salvage path.
- `src/ask_chatgpt/completion.py:38` accepts an optional governor; `src/ask_chatgpt/completion.py:50` charges completion backend fetches; `src/ask_chatgpt/completion.py:58` raises 429 before shape handling; `src/ask_chatgpt/completion.py:169` still swallows only auth/shape, not `RateLimitedError`.
- `src/ask_chatgpt/capture.py:201` accepts an optional governor on capture fetch; `src/ask_chatgpt/capture.py:215` charges capture backend fetches; `src/ask_chatgpt/capture.py:224` raises 429 before `BackendFetchMeta`; `src/ask_chatgpt/capture.py:371` explicitly re-raises `RateLimitedError` before UI fallback; `src/ask_chatgpt/capture.py:394`, `src/ask_chatgpt/capture.py:466`, and `src/ask_chatgpt/capture.py:489` charge attachment descriptor/byte fetches.
- `src/ask_chatgpt/session.py:101` charges page-load/open-tab; `src/ask_chatgpt/session.py:155`/`src/ask_chatgpt/session.py:232` add one-sided jitter; `src/ask_chatgpt/session.py:278` and `src/ask_chatgpt/session.py:455` govern the pre-send reload path without editing `send.py`; `src/ask_chatgpt/session.py:350` constructs one governor per Session with the data dir and channel timing; `src/ask_chatgpt/session.py:471` charges uploads; `src/ask_chatgpt/session.py:474` charges send submit; `src/ask_chatgpt/session.py:501`/`src/ask_chatgpt/session.py:516` pass the governor to completion/capture; `src/ask_chatgpt/session.py:513` charges the draft capture reload; `src/ask_chatgpt/session.py:529` handles `RateLimitedError` by soft-signal + shared backoff and re-raises without partial salvage; `src/ask_chatgpt/session.py:592` passes the governor on scrape capture.
- Tests: `tests/test_rate_governor.py:21`/`:42`, `tests/test_send_completion.py:915`/`:951`, `tests/test_capture.py:822`, `tests/test_cli.py:481`, `tests/test_errors.py:100`, `tests/test_send_budget.py:25`.

## CHOKEPOINT ACCOUNTING
- Wired for Session/CLI production paths: page-load/open-tab (`TabPool.acquire`), pre-send reload triggered by `wait_for_idle_and_reload_if_needed`, draft/capture reload, SPA send submit, backend completion fetch, backend capture fetch, attachment descriptor fetch, attachment byte fetch, and uploads.
- Deferred: direct raw `BrowserChannel`/`CdpChannel` calls made outside `Session` are not wrapped because the governor is Session-owned and no governor context exists at the low-level channel API; no current CLI/Session chokepoint is deferred.
- `channels/mock.py` and `channels/cdp.py` were not changed; mock responses already carry headers, and CDP `FetchResult.headers` already preserves safe response headers including `retry-after`.

## FALSIFIABILITY PROOF
- Governor throttle red: `uv run pytest tests/test_rate_governor.py` failed pre-change with `ModuleNotFoundError: No module named 'ask_chatgpt.governor'`. Green: included in the combined targeted run, `8 passed`.
- 429/error/CLI red: `uv run pytest tests/test_send_completion.py::test_completion_429_raises_rate_limited_with_retry_after_and_is_not_swallowed tests/test_capture.py::test_capture_429_raises_rate_limited_and_never_uses_ui_fallback tests/test_cli.py::test_cli_rate_limited_429_returns_52_without_stdout_out_or_clipboard_salvage tests/test_errors.py::test_rate_limited_error_exit_52_retryable_backoff_and_retry_after_preserved` failed pre-change with `ImportError: cannot import name 'RateLimitedError'` and the CLI assertion `assert 0 == 52`. Green: included in the combined targeted run, `8 passed`.
- Jitter red: `uv run pytest tests/test_send_budget.py::test_send_budget_one_sided_jitter_adds_to_required_spacing_with_injected_rng` failed pre-change with `TypeError: AdaptiveSendBudget.__init__() got an unexpected keyword argument 'jitter_max_s'`. Green: included in the combined targeted run, `8 passed`.
- Wiring red: `uv run pytest tests/test_send_completion.py::test_session_invokes_governor_for_page_load_send_and_backend_fetches` failed pre-change with `AttributeError: 'Session' object has no attribute 'governor'`. Green: included in the combined targeted run, `8 passed`.

## FULL-suite summary
`============================= 292 passed in 1.33s ==============================`

## CONFIG NOTE
- Confirmed account-ceiling defaults are conservative/configurable/operator-owned. Code comment quote: “THE REAL ACCOUNT RATE CEILING IS OPERATOR-OWNED — these defaults are conservative placeholders to be confirmed/measured with the operator, NEVER assumed as fact (see M16 §6, memory verify-inherited-resource-claims).”
- C-2 was left intact: no stream-close observer was added, and the existing completion poll cadence/30s sparse backend behavior was not replaced; only 429 detection/governor charging was added at existing fetch boundaries.
