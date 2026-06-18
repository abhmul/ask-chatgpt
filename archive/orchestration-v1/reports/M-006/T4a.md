# T4a — independent verification: default-tier purity + CDP attach safety

Scope/actions: read `orchestration/tasks/M-006/T4a-tier-purity.md` and `tmp/verify-m006/T4-evidence.txt`; inspected committed `driver.py`, `readers.py`, `patch.py`, `tests/conftest.py`, `real.json`, and `tests/test_driver_cdp_attach.py` plus directly relevant tests/config. I did not run the full pytest suite, edit source, contact the real site, or send messages.

## Claim 1 — PASS: default tier is loopback-mock-only

- Authoritative default-suite evidence is `tmp/verify-m006/T4-evidence.txt:8`: `169 passed, 1 deselected in 73.73s`; I cite this run instead of rerunning full pytest.
- Default collection excludes real-site tests through `pyproject.toml:20` (`addopts = ["-m", "not real_site"]`) and documents the `real_site` marker as default-deselected/gated at `pyproject.toml:21`.
- The real tier is double-gated: `tests/test_real_tier_gating.py:9-11` marks the sample as `real_site` and asserts `ASK_CHATGPT_REAL == "1"`; `tests/conftest.py:14-20` additionally skips `real_site` items unless `ASK_CHATGPT_REAL=1`.
- The autouse socket guard is present: `tests/conftest.py:23-31` allows only non-TCP/AF_UNIX shapes or loopback hosts; `tests/conftest.py:37-60` autouse-patches `connect`, `connect_ex`, and `create_connection`; `tests/conftest.py:66-68` restores originals.
- I spot-checked `git diff 3693388^..HEAD -- tests/conftest.py`: only the `os` import and `pytest_collection_modifyitems` gating were added; the `_allowed`/`_network_guard` guard logic was not weakened.

## Claim 2 — PASS: CDP attach safety mechanics

- `channel="cdp"` uses the CDP path in `driver.py:120-123`; `_start_cdp_context()` calls `connect_over_cdp` at `src/ask_chatgpt/driver.py:468-477`. Browser launch calls are confined to non-CDP helpers (`driver.py:376` mock launch, `driver.py:459` real persistent launch).
- CDP opens a brand-new tool page: `driver.py:120-122` calls `_new_cdp_page()`, and `driver.py:484-488` uses `context.new_page()` and records it in `_cdp_owned_pages`. The `context.pages[0]` reuse helper is `_new_or_existing_page()` at `driver.py:479-482`, but start uses it only for mock/real at `driver.py:115-119`, not for CDP.
- CDP close does not close operator browser/context: `driver.py:153-161` closes only owned/opened pages for `is_cdp`; `context.close()` and `browser.close()` are inside the non-CDP `else` branch at `driver.py:161-174`. `playwright.stop()` at `driver.py:177-180` detaches the client.
- Attach-time login/challenge checks run after navigation: `driver.py:129-133` calls `_raise_login_required_for_auth_redirect` for real/CDP and `_raise_challenge_present_if_detected` for CDP; implementations are at `driver.py:414-427` and `driver.py:429-444`.
- Tab-hygiene tests prove the intended behavior locally: `tests/test_driver_cdp_attach.py:257-281` asserts a new target whose id was absent before attach; `tests/test_driver_cdp_attach.py:285-317` proves the browser remains alive, a preexisting tab remains, and tool tab ids disappear after `session.close()`; `tests/test_driver_cdp_attach.py:320-335` verifies challenge/login detection on loopback.

## Claim 3 — PASS: `real.json` fail-closed schema and optional/required behavior are preserved

- Current schema count is 20 selector keys and 2 attribute keys (`jq` spot-check: `selectors=20 attributes=2`), also asserted in `tests/test_driver_real_failclosed.py:17-19`.
- Current filled values are only the real map’s required/proven path: `real.json:6-11`, `real.json:15-19`, `real.json:21`, and `real.json:29`. Current intentionally empty values match the task list: model keys at `real.json:12-14`, `download_artifact` at `real.json:20`, presence markers at `real.json:22-25`, and `conversation_ref` at `real.json:28`.
- `SelectorMap` remains fail-closed on empty values: `selector()` raises on absent/non-string/blank at `selector_map.py:29-32`; `attribute()` does the same at `selector_map.py:35-38`.
- Required real selectors/attributes still fail closed before real launch: `_REAL_REQUIRED_SELECTOR_KEYS`/`_REAL_REQUIRED_ATTRIBUTE_KEYS` are `driver.py:46-60`, and `_ensure_real_selector_map_ready()` calls `selector()`/`attribute()` at `driver.py:402-406`; `_require_present()` still hard-fails on missing DOM matches at `driver.py:541-549`.
- Optional markers degrade gracefully: `_optional_selector()` catches empty/unavailable selectors at `driver.py:526-530`; `_present()` returns `False` when absent at `driver.py:532-535`; truncation and conversation-ref optional paths are guarded/fallback at `driver.py:330-338` and `driver.py:576-589`; rate-limit visibility uses `_present()` at `driver.py:634-635`.
- Readers/patch preserve required-vs-optional behavior: `readers.py:32-33` requires assistant/body selectors, while `readers.py:35-45` tolerates an unmapped truncation marker; `readers.py:70-75` keeps copy-button fail-closed. `patch.py:303-310` requires `turn_id`, while `patch.py:313-315` treats empty `download_artifact` as no candidate so fenced fallback can proceed.
- Supporting tests cover the optional paths: `tests/test_driver_optional_markers.py:77-100` checks empty optional markers do not query/raise; `tests/test_readers.py:99-112` covers unmapped vs mapped truncation; `tests/test_patch.py:172-185` covers unmapped `download_artifact` falling back to fenced bundle.

## Claim 4 — PASS: fail-closed test is decoupled from populated `real.json`

- The critical fail-closed start test uses an independent empty-map fixture, not the committed real selector map: `tests/test_driver_real_failclosed.py:11` defines `EMPTY_REAL_SELECTOR_MAPS_DIR`, and `tests/test_driver_real_failclosed.py:70-76` passes it to `BrowserSession` and asserts `SelectorUnavailableError` before navigation/playwright start.
- The empty fixture is all-empty at `tests/fixtures/selector_maps/empty/real.json:6-29`, so populating `src/ask_chatgpt/selector_maps/real.json` cannot weaken that test.

Could not verify live empirical correctness of filled real-site selectors because this task explicitly forbids real-site contact; I verified the committed provenance/current fail-closed state and cite the authoritative manager evidence instead.

T4a-VERDICT: PASS — committed code/tests plus the authoritative 169-pass evidence support default-tier purity, CDP attach safety, fail-closed real map semantics, and decoupled fail-closed coverage.
MESSAGES_USED: 0
T4a-STATUS: DONE
