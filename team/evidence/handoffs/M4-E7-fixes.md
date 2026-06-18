STATUS: DONE

Mission M4-E7 fixes are committed on `rewrite-v2` as `6742cc1741aaf874ee2231953d0cd2946c6f0d28`.

## Final verification

```text
$ uv run pytest
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/abhmul/dev/ask-chatgpt
configfile: pyproject.toml
testpaths: tests
collected 188 items

tests/test_allowlist.py .......................                          [ 12%]
tests/test_capture.py ..................                                 [ 21%]
tests/test_channels_base.py ...                                          [ 23%]
tests/test_cli.py ..........                                             [ 28%]
tests/test_errors.py ....................                                [ 39%]
tests/test_identity.py ..............                                    [ 46%]
tests/test_mock_channel.py ........                                      [ 51%]
tests/test_models.py ................                                    [ 59%]
tests/test_selectors.py ..................                               [ 69%]
tests/test_send_completion.py .....................                      [ 80%]
tests/test_session_stubs.py ..                                           [ 81%]
tests/test_smoke.py ......                                               [ 84%]
tests/test_store_atomic_raw.py ...                                       [ 86%]
tests/test_store_attachment_path.py ...                                  [ 87%]
tests/test_store_durability.py ..                                        [ 88%]
tests/test_store_identity_resolution.py ..                               [ 89%]
tests/test_store_index.py ..                                             [ 90%]
tests/test_store_jsonl.py ..                                             [ 92%]
tests/test_store_layout.py ..                                            [ 93%]
tests/test_store_partial.py ...                                          [ 94%]
tests/test_store_payload.py ...                                          [ 96%]
tests/test_store_pending_send.py ..                                      [ 97%]
tests/test_store_read_semantics.py .                                     [ 97%]
tests/test_store_render.py .                                             [ 98%]
tests/test_store_torn_line.py ...                                        [100%]

============================= 188 passed in 0.43s ==============================
```

## Per-finding fixes and falsifiable tests

- D-A: Removed internal `Session.ask`/`Session.scrape` `--out` writes; CLI remains the stdout-first/out owner through `Store.emit_payload`. New test: `tests/test_cli.py::test_cli_real_session_ask_out_write_failure_keeps_stdout_first`. RED-on-revert evidence: reintroducing a pre-return `Session.ask` out write made the test fail with `assert '' == 'REAL SESSION STDOUT SURVIVES OUT FAILURE\n'`, proving gotcha #4 now holds on the REAL `Session.ask(channel=mock)` CLI path when `--out` write raises.
- D-B: `salvage_partial` now defaults to backend partial then DOM, with clipboard only behind explicit `allow_clipboard=True` and not wired in M4. New test: `tests/test_send_completion.py::test_salvage_partial_skips_clipboard_by_default_even_when_granted_and_uses_dom`. RED-on-revert evidence: forcing default clipboard read made the test fail with `partial:copy-button != assistant-dom-partial`.
- D-C: `_select_new_assistant` now fails closed when a verified `assistant_message_id` is absent from captured assistants; stale `assistants[-1]` fallback remains only for `assistant_message_id is None`. New test: `tests/test_send_completion.py::test_session_completion_id_absent_does_not_return_stale_assistant_and_salvages`. RED-on-revert evidence: removing the absent-id raise made the test fail with `Failed: DID NOT RAISE <class 'ask_chatgpt.errors.InternalError'>`.
- N1: `poll_backend_completion` default is now conservative (`prefer_lightweight=False`), so `/stream_status` is opt-in rather than the default; cadence tests were updated to assert full conversation checks by default. New test: `tests/test_send_completion.py::test_poll_backend_completion_default_uses_full_conversation_endpoint_not_stream_status`. RED-on-revert evidence: reverting the default to `True` made the test fail with `stream status answer != full raw default answer`.
- N2: Capture now prefers per-message `metadata.model_slug` over top-level `default_model_slug`, falling back to top-level when absent. New test: `tests/test_capture.py::test_message_level_model_slug_overrides_top_level_default`. RED-on-revert evidence: using only `default_model` made the test fail with `top-level-default != message-level-model`.

N3 (`completion` node-id fallback) remains deferred to M5 per contract.

## Commit evidence

```text
$ git log -1 --oneline
6742cc1 M4: fix verification-panel findings
```

```text
$ git show --stat HEAD
commit 6742cc1741aaf874ee2231953d0cd2946c6f0d28
Author: jetm <abhmul@gmail.com>
Date:   Thu Jun 18 18:02:14 2026 -0500

    M4: fix verification-panel findings

 src/ask_chatgpt/capture.py    |  10 ++-
 src/ask_chatgpt/completion.py |  35 +++++----
 src/ask_chatgpt/session.py    |  19 +----
 tests/test_capture.py         |  16 ++++
 tests/test_cli.py             | 146 +++++++++++++++++++++++++++++++++++++
 tests/test_send_completion.py | 165 ++++++++++++++++++++++++++++++++++++++++--
 6 files changed, 352 insertions(+), 39 deletions(-)
```

## Blockers / notes

No blockers. I did not stage or commit `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, `team/state/M4-manager-state.json`, `human/`, or the untracked manager contract/report files.
