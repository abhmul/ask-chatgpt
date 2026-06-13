START_TIMESTAMP: 2026-06-12T20:28:00-05:00
END_TIMESTAMP: 2026-06-12T20:36:43-05:00
ESTIMATE: T2c 20m

## Changes

- D1/GAP-1: `src/ask_chatgpt/api.py` now accepts `cdp_endpoint: str | None = None` in `ask_chatgpt()` at line 38, forwards it into the UC1 `BrowserSession(...)` call at line 56, forwards it into `_ask_chatgpt_with_bundle(...)` at line 84, accepts it in `_ask_chatgpt_with_bundle()` at line 102, and forwards it into the UC2 `BrowserSession(...)` call at line 117. `channel="real"` remains the public default.
- D1/GAP-1: `src/ask_chatgpt/cli.py` now threads `cdp_endpoint=args.cdp_endpoint` into `ask_chatgpt(...)` at line 68, accepts `--channel cdp` at line 112, and adds `--cdp-endpoint URL` defaulting to `http://127.0.0.1:9222` with help `CDP endpoint for channel=cdp` at line 114.
- D2/GAP-2: `src/ask_chatgpt/driver.py` imports `unquote` at line 10, makes the create-new-conversation branch use the forgiving `self._try_read_active_conversation_ref() or ""` at line 215, adds `_conversation_ref_from_url()` at lines 450-454, and rewrites `_read_active_conversation_ref()` at lines 481-494 to preserve DOM-attribute priority while URL-deriving `/c/<id>` when the attribute is empty/unavailable. The open-existing branch remains a hard read.
- D3/GAP-3: `src/ask_chatgpt/selector_maps/real.json` sets `selectors.download_artifact` to `""` at line 20. Rationale: T2 discovery proved the real site fires no Playwright `Download` event; blanking this selector fail-closes download-primary and forces the proven checksummed fenced-base64 fallback for UC2 instead of clicking a metadata-less button.

## Tests and RED to GREEN

- Added `tests/test_api_cdp_public_path.py`: API cdp endpoint forwarding for plain and bundle paths at line 37, CLI cdp endpoint forwarding at line 63, and CLI default endpoint parsing at line 92.
- Added focused driver unit coverage in `tests/test_driver.py`: URL helper at line 87, DOM-attribute priority at line 96, URL fallback when the attribute is empty at line 111, and no-ref-yet create-new tolerance at line 126. This is a focused fake page/selectors unit test rather than a real-site integration to keep the tier mock/loopback only.
- Added `tests/test_driver_real_failclosed.py` line 13 asserting `real.json` fail-closes `download_artifact` while retaining 20 selector keys and 2 attribute keys.
- RED evidence: initial targeted run of the newly added tests failed as expected with `7 failed in 0.20s`: `ask_chatgpt()` rejected `cdp_endpoint`, CLI rejected `--channel cdp`, `_conversation_ref_from_url` was absent, URL fallback/create-new raised `SelectorUnavailableError`, and `real.json` still had `button[aria-label*="Download"]`.
- GREEN evidence: final full default suite summary was `================= 144 passed, 1 deselected in 63.14s (0:01:03) =================`.
- Note: the first full post-implementation run exposed a test-fixture bug in the new API bundle test (`PathEscapeError` from passing an absolute bundle path); I corrected the test to pass the repo-root-relative `input.txt` under `bundle_root` and reran the full suite to obtain the authoritative green summary above.

## Tier purity and guards

- ZERO real messages; `MESSAGES_USED: 0`.
- Default pytest output: `collected 145 items / 1 deselected / 144 selected`; selected default tier therefore ran zero `real_site` tests, with the existing real-site sentinel deselected.
- Socket guard unchanged: `git diff -- tests/conftest.py src/ask_chatgpt/selector_maps/mock.json --stat` produced no output; `tests/conftest.py` autouse socket guard remains intact and `mock.json` is unchanged.
- Mock UC1 happy path remains green as part of the full suite: `tests/test_driver.py::test_driver_happy_path_returns_latest_completed_turn` passed in the 144-pass run.

## Diff stat / scope

Tracked `git diff --stat` at report time included a pre-existing manager orchestration-state dispatch diff plus the T2c code/test changes:

```text
 orchestration/state/M-006-state.json    |   3 +-
 src/ask_chatgpt/api.py                  |   7 ++-
 src/ask_chatgpt/cli.py                  |   4 +-
 src/ask_chatgpt/driver.py               |  27 ++++++---
 src/ask_chatgpt/selector_maps/real.json |   2 +-
 tests/test_driver.py                    | 104 +++++++++++++++++++++++++++++++-
 tests/test_driver_real_failclosed.py    |  14 +++++
 7 files changed, 148 insertions(+), 13 deletions(-)
```

T2c deliverable tracked diff excluding the inherited orchestration-state file:

```text
 src/ask_chatgpt/api.py                  |   7 ++-
 src/ask_chatgpt/cli.py                  |   4 +-
 src/ask_chatgpt/driver.py               |  27 ++++++---
 src/ask_chatgpt/selector_maps/real.json |   2 +-
 tests/test_driver.py                    | 104 +++++++++++++++++++++++++++++++-
 tests/test_driver_real_failclosed.py    |  14 +++++
 6 files changed, 146 insertions(+), 12 deletions(-)
```

Untracked new deliverables: `tests/test_api_cdp_public_path.py` (96 lines) and this report. I did not edit `.claude/`, `.agents/`, `tests/conftest.py`, or `src/ask_chatgpt/selector_maps/mock.json`. No git commit was made.

## Design judgments / limits

- `_read_active_conversation_ref()` still requires `ready_root` before reading either DOM or URL so existing fail-closed page readiness behavior is preserved; only the conversation-ref source falls back from DOM to URL.
- The create-new branch returns `""` only for the pre-send no-ref-yet state; `send_prompt()` still captures a later URL-derived ref through the existing forgiving read.
- I could not prove real-site behavior deterministically in this leg because the contract forbids real contact; proof is limited to mock/loopback/unit tests.

MESSAGES_USED: 0
T2c-STATUS: DONE
