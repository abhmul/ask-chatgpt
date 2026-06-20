START_TIMESTAMP: 2026-06-12T16:11:38-05:00
END_TIMESTAMP: 2026-06-12T16:24:41-05:00
ESTIMATE: T1b 35m

## Changes
- `src/ask_chatgpt/driver.py`: added `channel="cdp"` with configurable `cdp_endpoint` defaulting to `http://127.0.0.1:9222`; it uses `chromium.connect_over_cdp(...)`, takes `browser.contexts[0]`, always opens `context.new_page()`, and never routes CDP through `_new_or_existing_page()`.
- CDP tab invariant: `BrowserSession` tracks pages it opened; `close()` closes only those pages and then stops Playwright to detach, without `context.close()` or `browser.close()` on the attached browser.
- CDP navigation/guards: `base_url` controls mock-vs-real behavior; loopback CDP uses the same loopback-only abort guard as mock, while non-loopback CDP applies the real allowlist guard logic. I intentionally install these guards page-scoped for CDP so operator pre-existing tabs are not routed or disturbed.
- `src/ask_chatgpt/errors.py`: added `CDPUnreachableError` and `ChallengePresentError`; unreachable errors contain `chromium --profile-directory='Profile 1' --remote-debugging-port=9222`, and challenge errors contain `CHALLENGE_PRESENT`.
- `tests/test_driver.py` + `tests/fixtures/selector_maps/empty/real.json`: decoupled the empty-map fail-closed behavior test from live `src/ask_chatgpt/selector_maps/real.json`.
- `tests/test_driver_cdp_attach.py`: added loopback-only throwaway Chromium CDP tests with ephemeral debug ports, unique tmp user-data-dir teardown, CDP unreachable coverage, mock UC1 through CDP, tab-hygiene proof, and loopback challenge/login detection.

## Validation
- Ran `uv sync --all-groups` before testing.
- Authoritative full default suite summary: `====================== 136 passed, 1 deselected in 56.92s ======================`
- CDP tests ran: 4 in `tests/test_driver_cdp_attach.py`.
- Default tier: final full suite selected/ran 0 real_site tests (`1 deselected`); collect-only under default addopts listed 136 selected nodeids and did not list `tests/test_real_tier_gating.py::test_real_site_sample_requires_env`.
- `src/ask_chatgpt/selector_maps/real.json`: unchanged; `git diff -- src/ask_chatgpt/selector_maps/real.json --stat` produced no output and the file remains the all-empty template.

## Diff stat
Working-tree note: `orchestration/state/M-006-state.json` and `orchestration/prompts/` were already dirty/out-of-scope orchestration artifacts; I did not modify or revert them. Scoped code/test diff for this leg:

```text
 src/ask_chatgpt/driver.py | 122 +++++++++++++++++++++++++++++++++++++---------
 src/ask_chatgpt/errors.py |  17 +++++++
 tests/test_driver.py      |   9 ++--
 3 files changed, 121 insertions(+), 27 deletions(-)
 /dev/null => tests/test_driver_cdp_attach.py | 335 +++++++++++++++++++++++++++
 1 file changed, 335 insertions(+)
 .../fixtures/selector_maps/empty/real.json         | 31 ++++++++++++++++++++++
 1 file changed, 31 insertions(+)
```

## Limits / deviations
- No real-site behavior was exercised or proven; all CDP coverage used the mock fixture or tiny loopback pages plus a throwaway local Chromium.
- Challenge detection is deterministically covered by loopback title/marker fixtures; real Cloudflare settling was not tested because T1b forbids real-site contact.
- Design deviation for safety: CDP route guards are page-scoped rather than context-scoped, while reusing the same loopback/real allowlist logic, to avoid impacting operator pre-existing tabs in the attached context.

MESSAGES_USED: 0
T1b-STATUS: DONE
