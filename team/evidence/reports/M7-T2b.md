DONE

## Verification
- `uv run pytest -q` -> `246 passed in 0.99s`.
- Branch verified: `rewrite-v2`.
- `git diff --cached --name-only` was empty after commits.
- No direct `time.sleep`/`from time import sleep` was added in the M7-T2b source diff (`git diff HEAD~4..HEAD -G'time\.sleep|from time import sleep' -- src/ask_chatgpt` produced no output).

## Commits
- `953da275dd0fd935d8856b8d87a3b756f3788d64` — M7-T2b: sustain model label verification
- `365d6fad7d7f554c2cc206a3c49476ba2c98fc21` — M7-T2b: settle send button before submit
- `a5f26b44f16ba137990df00a0ac7dcf3b28649f1` — M7-T2b: add selector fallback and falsifiability tests
- `511f47e99799966cdea388d3e452f5b19104e5ef` — M7-T2b: keep submit settle on channel poll

## Files changed
- `src/ask_chatgpt/menus.py`
- `src/ask_chatgpt/send.py`
- `src/ask_chatgpt/channels/mock.py`
- `src/ask_chatgpt/channels/cdp.py`
- `src/ask_chatgpt/selectors/real.json`
- `tests/test_menus.py`
- `tests/test_send_completion.py`
- `tests/test_selectors.py`
- `tests/test_session_draft_loop.py`
- `tests/test_cli.py`
- `tests/test_session_stubs.py`
- `tests/mock_scenarios.py`

## New/strengthened tests and falsifiability
- `tests/test_menus.py::test_select_model_sustained_tolerates_transient_model_label`: pins that model verification tolerates transient `Extra High` and succeeds once the requested label appears. It fails if `_reflected_model` only samples once or never uses the channel clock polling window.
- `tests/test_menus.py::test_select_model_sustained_absence_fails_closed_after_multiple_samples`: pins sustained absence fail-closed behavior and asserts multiple DOM samples. It fails if wrong labels are accepted, if absence is silently treated as verified, or if a degenerate one-shot implementation raises without polling.
- `tests/test_menus.py::test_select_model_trigger_tolerates_transient_then_unambiguous_label`: pins that the model trigger can be temporarily absent/ambiguous and only needs to settle to exactly one normalized label before menu open. It fails if `_require_unambiguous_model_trigger` remains single-read or accepts ambiguity instead of waiting for one label.
- `tests/test_send_completion.py::test_submit_waits_for_enabled_send_button`: pins that `submit_composer` waits until the send button is visible+enabled before clicking. It fails if submit clicks immediately while the mock button is disabled, or if the poll never observes the enabled state.
- `tests/test_send_completion.py::test_submit_fails_closed_if_send_button_never_enables`: pins bounded fail-closed behavior with no click when the send button never enables. It fails if submit silently no-ops, clicks a disabled button, or does not poll more than once.
- `tests/test_menus.py::test_set_tools_clicked_tool_must_reflect_checked_state`: pins that a clicked tool must later reflect `checked=True`. It fails if `set_tools` trusts click success and returns verified without checked-state reflection; the test also asserts the click was recorded.
- `tests/test_selectors.py::test_packaged_real_selector_map_loads_with_exact_required_keys` was strengthened to pin the `button[aria-label="Send prompt"]` fallback. It fails if the fallback is removed from `src/ask_chatgpt/selectors/real.json`.
- `tests/test_session_draft_loop.py::test_draft_ask_fails_closed_when_post_submit_url_has_no_conversation_id` was strengthened to assert no `conversations/` dir and no `transcript.jsonl` anywhere under the temp data dir. It fails if any bogus post-submit ID path writes a transcript, not only `learned-123`.

## Timing and offline safety
- OFFLINE/mock-only work; no browser/CDP/network/real sends were run.
- New sustained model waits use `_sleep_until` with `tab.channel.monotonic/sleep`.
- New submit settle waits poll the channel state seam and use `_sleep_until` with `tab.channel.monotonic/sleep`; no direct real `time.sleep` was added.
- `MockChannel` now scripts model-label sequences and selector-enabled sequences for deterministic offline falsification.

## Staging / forbidden paths
- `issues/cdp-send-repro/controller.mjs` was not edited by this worker and is not staged; it remains a pre-existing unstaged modification.
- `human/` is not staged; it remains pre-existing untracked content.
- `team/state/live-state.json` and other pre-existing untracked team files are not staged.

## Blockers
- None.

## Complexity signals
- Low-to-moderate: the only notable design choice was keeping submit settle as an immediate channel-state poll plus channel-clock sleep, rather than relying on Playwright selector timeouts, to preserve bounded offline/mock timing and avoid adding direct real sleeps.
