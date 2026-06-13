# M-008a / T3 worker report

STATUS: DONE

## Files changed

- `tests/fixtures/mock_chatgpt/server.py`: added opt-in `recall_mode="planted_token"` support. When present on the next scripted response, the mock derives assistant text by applying `recall_pattern` to prior turns in the current conversation and returns the recovered token or `NO_TOKEN_RECALLED`; scripts without `recall_mode` keep returning fixed `text` unchanged.
- `tests/test_continuity_mock.py`: added mock-only continuity/falsifiability tests, a cross-process CLI continuity/control test over shared `ASK_CHATGPT_STATE_DIR`, shared nonce/control/completeness assertion helpers for M-008b, and a streaming long-response completeness test through `ask_chatgpt()`.

## GPT-facing prompts

Turn-1 plant template, with a fresh runtime nonce substituted for `{nonce}`:

```text
Remember this token for later: {nonce}. Reply with ACK only.
```

Turn-2 recall prompt:

```text
What was the token I asked you to remember? Reply with only the token.
```

Control prompt, intentionally identical to turn-2 recall:

```text
What was the token I asked you to remember? Reply with only the token.
```

Truncation-elicitation template, with runtime `line_count=180` and fresh `{token}` substituted:

````text
Output exactly {line_count} numbered lines, then exactly one completion marker line. For k=1 through {line_count}, line k must be exactly `LINE-<k> {token}` with <k> replaced by decimal k and no zero padding. After line {line_count}, output exactly `__ELICIT_COMPLETE__` on its own line and nothing after it.
````

Confirmed in tests: the recall/control prompt does not contain the full nonce, the random hex suffix, or the `ASKCG-NONCE-` prefix.

## Adversarial self-review

- Turn-1 plant: A chatbot could disobey and echo the nonce instead of `ACK`, but the wording explicitly predetermines only an `ACK` reply while placing the nonce solely in turn 1. The later continuity test can fail if session history is not reused or the mock cannot recover from history.
- Turn-2 recall: A chatbot could answer with prose or say it does not know, but the wording requests only the remembered token and contains no nonce material. It does not predetermine the answer; without prior history, the exact nonce is unrecoverable.
- Control: The prompt is byte-identical to turn 2 but is sent to a fresh session. A chatbot could hallucinate a token-shaped string, but it cannot know the exact fresh nonce unless the test leaks it or the harness incorrectly shares history; the mock returns `NO_TOKEN_RECALLED`, proving the control genuinely fails to produce the nonce.
- Truncation-elicitation: A chatbot could miscount, add zero padding, omit the terminal sentinel, add trailing text, or be clipped. The wording predetermines a deterministic structure, and the verifier fails on any missing/reordered line or missing/nonterminal `__ELICIT_COMPLETE__`, so a truncated response cannot pass.

## Evidence / success criteria

1. Mock recall mode is opt-in and history-derived: `append_exchange()` now calls `_recall_text_from_history(script.extra, conversation.turns[:-1])`; without `recall_mode`, it falls back to `script.text`. The mock is given only `recall_pattern = \b(?P<token>ASKCG-NONCE-[0-9a-f]{32})\b`, not the generated nonce value.
2. In-process continuity/control are green in `tests/test_continuity_mock.py::test_mock_recall_mode_continuity_is_falsifiable_in_process`: same session returns the exact nonce; fresh control returns literal `NO_TOKEN_RECALLED`, and `_assert_nonce_absent(control, nonce)` verifies the nonce is absent.
3. Falsifiability guard is present: `_assert_recall_prompt_does_not_leak_nonce()` asserts the recall/control prompt lacks the full nonce, random suffix, and nonce prefix.
4. Cross-process continuity/control are green in `tests/test_continuity_mock.py::test_mock_recall_mode_continuity_survives_cli_subprocesses`: subprocess 1 plants via CLI, subprocess 2 recalls with the same `--session` and shared `ASK_CHATGPT_STATE_DIR`; the test reads `sessions.json` and asserts the stored conversation has `[plant_prompt, recall_prompt]`. The cross-process control uses a different session, gets `NO_TOKEN_RECALLED`, has a distinct conversation ref, and nonce absence is asserted.
5. Long-response completeness is green in `tests/test_continuity_mock.py::test_mock_long_response_completeness_via_public_api`: the mock scripts a streaming 180-line body plus `__ELICIT_COMPLETE__`; `_assert_complete_long_response()` checks UTF-8 length ≥ 4096, every `LINE-k <token>` in order, exact line list, and terminal sentinel.
6. Nonces are full-length and per-run: `_new_nonce()` uses `ASKCG-NONCE-` + `secrets.token_hex(16)` and asserts `len(nonce) >= 32`.
7. Test evidence:

```text
$ uv run pytest -q tests/test_continuity_mock.py
3 passed in 4.88s

$ uv run pytest -q
206 passed, 1 deselected in 68.28s (0:01:08)
```

No `ASK_CHATGPT_REAL` was set; all new tests use `channel="mock"` with the loopback mock fixture only.

## Telemetry

ESTIMATE: T3 60m
ACTUAL: T3 25m
REWORK-CAUSE: None
END: 2026-06-13T10:39:02-05:00
