STATUS: DONE

## Verification

Command run: `uv run pytest`

```text
collected 131 items
============================= 131 passed in 0.15s ==============================
```

## C1-C8 ledger

- C1 DONE: `src/ask_chatgpt/channels/mock.py` provides offline `MockChannel`, channel-bound `TabLease`, redacted call log/counters, injected monotonic/sleeper (`ScriptedClock`), forbidden browser/context/page internals, and `context.pages` fail-closed behavior.
- C2 DONE: backend fixtures require all 8 required header names for `/backend-api/conversation/<id>`; accept-only returns literal 404 JSON `detail`; header canary values are exposed but not recorded in `MockChannel.calls`.
- C3 DONE: `tests/mock_scenarios.py` programmatically generates the ~5k-node out-of-order current-branch mapping, side branches, hidden internals, malformed tree variants, content-part edge cases, and exact math/markdown expected strings.
- C4 DONE: DR/Pro positive and negative same-`turn_exchange_id` raw fixtures are importable, including the lone synthetic `content_type="deep_research"` non-evidence case.
- C5 DONE: mixed attachment/citation raw fixture includes user upload, file reference, generated asset, code execution output, citations, grouped/sources refs, displayed search groups, search queries, raw paths, redaction canaries, and invalid no-fetch/no-open URLs/paths.
- C6 DONE: send/UI scenarios cover required selector missing, composer absent→absent→visible, composer never visible, ignored/truncated fill, disabled send, global Enter misuse, existing generation then idle, no-op submit, wrong new user, successful new user, and baseline ids.
- C7 DONE: completion scenarios cover new assistant growth, active/finalizing/unknown statuses, independently changing progress tokens, same-length hash change, progress through 1200s, explicit total cap, no-progress partial, backend shape error after partial, DOM fallback, counters, and one-use header canary reuse detection.
- C8 DONE: safety scenarios cover clipboard prompt/allowed offline text, login/challenge states, disallowed URL fail-before-side-effect through `MockChannel`, private page canary with enumeration raising, one-use headers, and status fixture with selector `present=null`.

## Falsifiability notes

- RED observed before GREEN: initial `uv run pytest tests/test_mock_channel.py -q` failed with `ModuleNotFoundError: No module named 'ask_chatgpt.channels.mock'`; after adding the first slice it passed, then the expanded fixture tests initially failed on missing `mock_scenarios` before the fixture substrate was implemented.
- `context.pages` falsifiability: `test_importing_mock_channel_is_offline_and_context_pages_raises` asserts no Playwright import, `channel.context.pages` raises `RuntimeError`, and `channel.browser.pages` raises `AttributeError`.
- 404-vs-200 falsifiability: `test_fetch_requires_all_eight_backend_headers_and_redacts_values` asserts the exact 404 body for accept-only/missing headers and exact 200 conversation/current-node values only with all eight canary headers.
- Fake-clock falsifiability: `test_query_turns_and_selector_timelines_follow_fake_clock_without_real_sleep` asserts the literal baseline snapshot at t=0, selector absence, composer visibility after `clock.advance(2.0)`, and `channel.sleep(3.0)` advancing only the injected `ScriptedClock`.

## Commit

Hash: `64a9f9777a001ee36e9ab345ad0d3212b332661e`

`git log -1 --oneline`: `64a9f97 M4 step 3: MockChannel offline fixtures`

`git show --stat HEAD`:

```text
commit 64a9f9777a001ee36e9ab345ad0d3212b332661e
Author: jetm <abhmul@gmail.com>
Date:   Thu Jun 18 16:45:06 2026 -0500

    M4 step 3: MockChannel offline fixtures

 src/ask_chatgpt/channels/mock.py | 564 ++++++++++++++++++++++++++++
 tests/mock_scenarios.py          | 786 +++++++++++++++++++++++++++++++++++++++
 tests/test_mock_channel.py       | 277 ++++++++++++++
 3 files changed, 1627 insertions(+)
```

## Import notes for E4/E5

E4/E5 tests can import the substrate with `from ask_chatgpt.channels.mock import MockChannel, MockScenario, ScriptedClock, REQUIRED_BACKEND_HEADERS, HEADER_CANARIES` and fixtures with `from tests.mock_scenarios import backend_header_scenario, large_mapping_raw, malformed_mapping_variants, attachment_citation_raw, deep_research_scenarios, send_ui_scenarios, completion_scenarios, safety_scenarios, current_branch_ids, CONTENT_PARTS_EXPECTED`.

## Blockers

None. Existing unrelated working-tree changes remain unstaged outside this increment (`issues/cdp-send-repro/controller.mjs`, manager/team state files, `human/`, and pre-existing team contract/handoff files).
