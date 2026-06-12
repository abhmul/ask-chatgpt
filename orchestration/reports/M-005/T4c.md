START_TIMESTAMP: 2026-06-12T11:52:08Z
ESTIMATE: T4c 25m

# T4c independent safety/spec verification

Ground truth checked at HEAD `261a16b33e3240b4d629e72c0ae8a1fd318ff538`; `tmp/verify-m005/clone_head.txt:8-19` shows the evidence clone is the same HEAD and contains commits `0179400`, `2f0b8de`, and `261a16b`. I did not re-run the heavy suite; I used committed files plus `tmp/verify-m005/` artifacts.

## D2 — fail-closed before real navigation

PASS. In `src/ask_chatgpt/driver.py`, `start()` checks `self.channel == "real"` and calls `self._ensure_real_selector_map_ready()` at `driver.py:101-102`, before `sync_playwright().start()` at `driver.py:103` and before the initial `page.goto(self._base_url, ...)` at `driver.py:115`; `tmp/verify-m005/d2_demo.txt:8-25` independently records the same order.

The readiness helper is genuinely fail-closed: `driver.py:295-299` probes all required real selector and attribute keys through `SelectorMap.selector()` and `SelectorMap.attribute()`. Those accessors raise `SelectorUnavailableError` for absent, non-string, empty, or whitespace-only values at `src/ask_chatgpt/selector_map.py:29-39`; with the current template, the first probed key `ready_root` fails before Playwright starts.

`src/ask_chatgpt/selector_maps/real.json:6-29` remains the all-empty template: all 20 selector values and both attribute values are `""`. `tmp/verify-m005/d2_demo.txt:45-72` records the same grep/count check.

`tests/test_driver_real_failclosed.py:7-57` is non-vacuous and network-free: it constructs `BrowserSession(channel="real", profile_path=...)`, monkeypatches `driver.sync_playwright`, records fake `goto()` calls and fake Playwright starts, asserts `SelectorUnavailableError`, and asserts both `navigations == []` and `playwright_starts == []`. This would fail against the pre-fix order because Playwright start and/or `https://chatgpt.com` navigation would be recorded before selector failure. `tmp/verify-m005/d2_demo.txt:1-5` shows the targeted test green.

D2-VERDICT: PASS

## D3 — `--session` non-vacuous test and acceptance

PASS. `tests/test_cli.py:140-213` isolates `ASK_CHATGPT_STATE_DIR`, invokes `cli.main()` twice with the same `--session sess-A`, asserts stdout/stderr and then `mock_chatgpt.inspect()` has exactly one conversation with user prompts `["first prompt", "second prompt"]`; it then invokes a contrasting `--session sess-B` and asserts two conversations, distinct stored conversation refs, and only `"different prompt"` in the second conversation. This is non-vacuous for session continuity.

`scripts/accept_uc3.py:224-349` registers and runs `session-continuity`; it creates an isolated `ASK_CHATGPT_STATE_DIR` at `accept_uc3.py:226-228`, drives `uv run ask-chatgpt` twice through `_run_cli()` with the same `--session accept-uc3-sess` at `accept_uc3.py:234-272`, then uses `handle.inspect()` to assert exactly one conversation and exact user turns at `accept_uc3.py:281-291`. `tmp/verify-m005/accept_uc3_results.json:2` is overall pass; `accept_uc3_results.json:158-204` shows the two subprocess commands/stdouts and `user_turns`; `accept_uc3_results.json:210-211` shows `session-continuity` status pass.

D3-VERDICT: PASS

## Security spot rechecks

Zip-slip/path safety: PASS. `git show --stat` confirms the M-005 commits touched only docs, `driver.py`, `tests/test_driver_real_failclosed.py`, `tests/test_cli.py`, and `scripts/accept_uc3.py`; they did not touch `src/ask_chatgpt/patch.py` or `src/ask_chatgpt/bundle.py`. Ground-truth defenses remain: lexical absolute/drive and `..` rejection is centralized in `src/ask_chatgpt/bundle.py:407-437`; patch ZIP symlink entries raise `PathEscapeError` at `src/ask_chatgpt/patch.py:674-679`; patch parent symlink and final symlink targets raise at `patch.py:850-890` and are rechecked during mutation at `patch.py:1112-1132`. Tests cover absolute/traversal/symlink-parent/symlink-entry rejections in `tests/test_patch.py:222-274`, upload bundle absolute/traversal build-time rejection in `tests/test_bundle_out.py:85-99`, and the authoritative full-suite artifact shows `121 passed` at `tmp/verify-m005/clone_pytest.txt:6-7`.

Network guard: PASS. The autouse socket guard is present in `tests/conftest.py:10-47` and blocks non-loopback TCP while allowing AF_UNIX/loopback. `tests/test_network_guard.py:8-20` asserts the guard blocks `93.184.216.34` and that the mock browser route blocks non-loopback navigation. `tmp/verify-m005/clone_pytest.txt:6-7` shows the full suite passed. Grep of tests found no real-site exercise: the only `channel="real"` construction is `tests/test_driver_real_failclosed.py:52`, which is monkeypatched and fails before Playwright start; `tests/test_driver.py:140-147` asserts tests use the loopback mock while the real constant exists.

Credentials/profile safety: PASS. `grep -i` of `src/` for credential/password/cookie/token/auth/secret/profile found only opaque `profile_path` plumbing, session registry conversation refs, and explicit non-credential messaging. `src/ask_chatgpt/driver.py:80` stores `Path(profile_path)` but `_start_real_context()` only passes `user_data_dir=str(self._profile_path)` to Playwright at `driver.py:301-307`; no browser profile contents are read. `src/ask_chatgpt/cli.py:113` documents `--profile-path` as "passed through without inspection". `src/ask_chatgpt/errors.py:19-22` states the tool never reads or stores credentials; `src/ask_chatgpt/session_registry.py:15-20` stores only `conversation_ref`, optional `url`, and optional `model_settings`.

## Spec spot rechecks

UC1: PASS. `src/ask_chatgpt/api.py:51-76` resolves stored conversation refs, opens/reuses the conversation, selects model settings, sends the prompt, reads the latest assistant response, stores the active ref, and returns the text. `tmp/verify-m005/accept_uc1_results.json:2` is overall pass; `accept_uc1_results.json:6-26` shows same-session continuity on `conv-1` with both prompts and returned text; `accept_uc1_results.json:30-39` shows model settings acceptance; `accept_uc1_results.json:48-49` shows the login-required honest failure step pass.

UC2: PASS. `src/ask_chatgpt/api.py:107-125` builds/uploads a bundle, sends prompt instructions, reads response text, and retrieves the patch bundle; `src/ask_chatgpt/patch.py:258-276` validates the patch bundle and prepares the apply plan before dry-run/apply mutation. `tmp/verify-m005/accept_uc2_results.json:2` is overall pass; download-primary has upload ok, patch `source: "download"`, dry-run/apply summaries, and `overall_diff_matches: true` at `accept_uc2_results.json:62-132`; fenced fallback has `source: "fenced"` and the same round-trip diff match at `accept_uc2_results.json:192-262`.

UC3: PASS. `src/ask_chatgpt/cli.py:61-71` wraps the public `ask_chatgpt()` function with prompt/session/model/channel/file args; `cli.py:76-87` handles stdout/`--out`/dry-run/apply; `cli.py:102-130` exposes and validates `--session`, `--files`, `--dirs`, `--root`, `--apply`, `--dry-run`, and `--profile-path`. `tmp/verify-m005/accept_uc3_results.json:2` is overall pass; prompt stdout passes at `accept_uc3_results.json:31-32`, `--out` passes at `accept_uc3_results.json:65-66`, dry-run no-mutation passes at `accept_uc3_results.json:149-150`, and session continuity passes at `accept_uc3_results.json:210-211`.

T4c-VERDICT: PASS
END_TIMESTAMP: 2026-06-12T11:54:36Z
T4c-STATUS: DONE
