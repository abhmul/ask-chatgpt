=== VERIFY-FALSIFIABILITY REPORT START ===
1. VERDICT: PASS-WITH-CONCERNS

2. Per-test falsifiability table

| Test | Pre-change/main behavior that makes it fail | Falsifiability | Severity |
|---|---|---:|---:|
| tests/test_cli.py::test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error | main cli.py catches only CompletionTimeoutError in the salvage branch; MaxTotalWaitExceededError falls to the generic AskChatGPTError path, so exit 51 is returned but partial stdout and --out emission do not happen. | falsifiable | INFO |
| tests/test_session_draft_loop.py::test_loop_persisted_tab_opens_once_and_does_not_reload_when_already_idle | main send.py reloads whenever wait_for_idle_and_reload_if_needed first sees stop_visible=False; the two already-idle loop iterations therefore record reloads and fail reload == 0. | falsifiable | INFO |
| tests/test_session_draft_loop.py::test_loop_two_iterations_sends_real_turns_and_appends_transcript_without_cap (changed existing test) | same main unconditional already-idle reload path; the newly added reload == 0 assertion fails, while the prior answer/transcript/submission assertions are retained. | falsifiable | INFO |
| tests/test_session_draft_loop.py::test_loop_capture_harvests_required_headers_without_steady_state_reloads | main still performs the already-idle reloads, so reload == 0 fails; separately, if header harvest were starved, the backend_api source, recorded stream-fetch count, target path, and required-header subset assertions would fail before reload accounting. | falsifiable | INFO |
| tests/test_rate_governor.py::test_governor_token_bucket_sleeps_until_refill_when_exhausted | main has no ask_chatgpt.governor module, so collection/import fails; a partial stub without token-bucket waiting would also fail the exact fake-clock sleep and final-token assertions. | falsifiable | INFO |
| tests/test_rate_governor.py::test_governor_retry_after_blocks_next_acquire_for_shared_backoff | main has no ask_chatgpt.governor module, so collection/import fails; a partial stub without shared backoff would fail the exact fake-clock sleep/clock/snapshot assertions. | falsifiable | INFO |
| tests/test_send_completion.py::test_completion_429_raises_rate_limited_with_retry_after_and_is_not_swallowed | main has no RateLimitedError export; behaviorally, main converts a 429 completion fetch into BackendCaptureShapeError and wait_for_completion swallows that class, then continues into DOM polling instead of raising before fallback. | falsifiable | INFO |
| tests/test_capture.py::test_capture_429_raises_rate_limited_and_never_uses_ui_fallback | main has no RateLimitedError export; behaviorally, capture treats the 429 stream fetch as non-2xx BackendCaptureShapeError and enters the UI-fallback path instead of raising a distinct rate-limit error with parsed retry metadata. | falsifiable | INFO |
| tests/test_cli.py::test_cli_rate_limited_429_returns_52_without_stdout_out_or_clipboard_salvage | main swallows the first completion 429 as BackendCaptureShapeError, consumes the later scripted successful backend response, and returns a normal answer/exit 0 with stdout/out instead of RATE_LIMITED exit 52 and no payload. | falsifiable | INFO |
| tests/test_errors.py::test_rate_limited_error_exit_52_retryable_backoff_and_retry_after_preserved | main has no RateLimitedError class/export, so the import fails; a malformed class would be caught by code/exit/retry-action/detail-redaction assertions. | falsifiable | INFO |
| tests/test_send_budget.py::test_send_budget_one_sided_jitter_adds_to_required_spacing_with_injected_rng | main AdaptiveSendBudget does not accept jitter_max_s/jitter_rng, so construction fails; if those args existed without one-sided jitter, the exact base-plus-jitter sleep assertion would fail. | falsifiable | INFO |
| tests/test_send_completion.py::test_session_invokes_governor_for_page_load_send_and_backend_fetches | main Session has no governor attribute; with a non-wired stub governor, the spy action list would lack page_load/send/backend_fetch and the assertions would fail. | falsifiable | INFO |

3. Weakened/deleted-assertion findings

None found. I inspected git diff --unified=0 main...HEAD -- tests plus the C-1 refactor. There are no removed assert or pytest.raises lines. The C-1 helper _loop_two_turn_scenario preserves request_snapshots via _request_snapshots(conversation_id, count=request_count) with the existing call using the prior count 8; the prior test_loop_two_iterations assertions for answer IDs, distinct answers, transcript IDs/order, successful_submissions, and managed_tabs remain, with added open_tab and reload assertions. The removed lines are inline fixture construction moved into the helper, not assertion weakening.

4. Absence-of-assertion findings

- Header-harvest regression: PASS. It is not a trivial pass: green requires backend_api answers, two recorded canonical stream fetches, exact target paths, REQUIRED_CAPTURE_HEADERS cardinality 8, and required-header-name subset membership on each fetch. If harvest is starved or headers are missing, capture fails before recording the stream fetch or the header assertions fail. Concern: the harvest source is still synthetic preseeded MockChannel request_snapshots, so this proves consumption/preservation under the no-steady-state-reload path, not a live production source for those snapshots.
- Governor wiring: PASS with minor depth limits. The test spies on session.governor.acquire, calls the original acquire, executes a real Session.ask over MockChannel, and asserts page_load, send, and backend_fetch actions in the spy list; that proves those acquire calls occurred, not merely that the loop ran. It does not assert exact counts, costs, path_kind values, attachment/reload coverage, or scrape coverage.
- Governor throttle: PASS. The token-bucket test asserts the exact fake-clock sleep amount and final token state; the retry-after/shared-backoff test asserts exact fake-clock sleep, advanced clock, and persisted last-rate-limited epoch. It is not merely “no error was raised.”

5. Offline/synthetic confirmation

Confirmed. The changed tests use MockChannel, ScriptedClock/FakeClock, temporary local Store/Governor state, RecordingSession, and scripted MockBackendResponse statuses. The 429s and retry metadata are scripted inputs consumed by production completion/capture/CLI code; jitter is an injected RNG input to AdaptiveSendBudget; governor wiring uses a spy wrapper that calls the original acquire and does not monkeypatch the answer. I saw no browser/CDP/curl/real-site path in these tests.

Bottom line: No BLOCKING falsifiability failure and no assertion weakening found; all new/changed tests fail on main, with only minor depth concerns around import-level reds and synthetic header/governor coverage.
=== VERIFY-FALSIFIABILITY REPORT END ===
