# T4c — Safety+spec lens: independent re-verification of D2 & D3 (+ security & spec spot-rechecks)

You are a FRESH, INDEPENDENT verification worker. You did NOT write any of the code under test. You inherit NOTHING except this file. Reason from GROUND TRUTH (committed files) + the authoritative evidence under `tmp/verify-m005/` (captured by the evidence runner). Do NOT re-run the heavy test suite — reason over the already-captured authoritative output. Lightweight read-only greps / single targeted test reruns are fine.

## Defect D2 re-check (safety — fail-closed before navigation)

Previously, `BrowserSession.start()` navigated to `https://chatgpt.com` (real channel) BEFORE enforcing the empty selector map. Fixed in commit `2f0b8de`. Independently confirm ALL of:
1. In `src/ask_chatgpt/driver.py`, `start()` calls `self._ensure_real_selector_map_ready()` for the real channel BEFORE `sync_playwright().start()` AND before any `launch_persistent_context` / `page.goto`. (Cross-check with `tmp/verify-m005/d2_demo.txt` which shows the grep: readiness at line 102, `sync_playwright().start()` at 103, `page.goto` at 115.)
2. `_ensure_real_selector_map_ready()` actually fails closed for the all-empty template: it probes selector/attribute keys via the fail-closed accessors `SelectorMap.selector()/attribute()` (`src/ask_chatgpt/selector_map.py:29-39`, which raise `SelectorUnavailableError` on empty/whitespace). So with `src/ask_chatgpt/selector_maps/real.json` all-empty, the FIRST probed key raises `SelectorUnavailableError`.
3. `selector_maps/real.json` is STILL the all-empty fail-closed template (every selector value `""`).
4. The new test `tests/test_driver_real_failclosed.py` is NON-VACUOUS and network-free: it constructs `channel="real"` + a profile_path, asserts `SelectorUnavailableError` is raised, asserts NO chatgpt.com navigation was attempted (goto-recording fake / monkeypatched playwright), requires no network (autouse socket guard stays active), and would have FAILED against the pre-fix driver. Read the test and confirm. `tmp/verify-m005/d2_demo.txt` shows it green (`1 passed`).
   -> Decide `D2-VERDICT: PASS|FAIL`. PASS only if readiness is enforced before navigation AND the test genuinely proves it.

## Defect D3 re-check (spec — CLI --session exercised)

Previously `--session` was implemented but exercised by no test/acceptance. Fixed in commit `261a16b`. Independently confirm ALL of:
1. `tests/test_cli.py` has a `--session` continuity test that: isolates the registry via `ASK_CHATGPT_STATE_DIR` (so it doesn't write `~/.local/state` and is deterministic), invokes the CLI twice with the SAME `--session` id, and asserts (NON-VACUOUSLY) that exactly ONE conversation was reused holding BOTH user prompts (via `mock_chatgpt.inspect()`), ideally with a contrasting different-session case proving sensitivity.
2. `scripts/accept_uc3.py` has a registered `session-continuity` step that drives the installed CLI (`uv run ask-chatgpt`) twice with the same `--session` (subprocess, isolated `ASK_CHATGPT_STATE_DIR`) and proves the same reuse; and `tmp/verify-m005/accept_uc3_results.json` shows that step with `status: "pass"` and `user_turns` of the two scripted prompts, with overall `pass`.
   -> Decide `D3-VERDICT: PASS|FAIL`. PASS only if the test is non-vacuous AND the acceptance evidence is present and pass.

## Security spot-rechecks (re-confirm on the NEW HEAD — these must not have regressed)

- Zip-slip: the changed-files patch/bundle path defenses still reject the 4 vectors (absolute path, `..` traversal, symlink-final, symlink-parent) with `PathEscapeError`. Confirm via the tests (`tests/test_patch.py` / `tests/test_bundle_out.py` / `tests/test_fixture_*`) and/or `tmp/verify-m005/` — and note that the M-005 commits (`0179400` docs, `2f0b8de` driver, `261a16b` cli-test+accept) did NOT touch `patch.py`/`bundle.py`, so the defense is unchanged (verify the diff scope: `git show --stat` of each commit).
- Network guard: the autouse loopback-only socket guard in `tests/conftest.py` is present and `tests/test_network_guard.py` passes (in the authoritative `tmp/verify-m005/clone_pytest.txt`). No test sets `channel="real"` against the real site.
- Credentials: grep `src/` to confirm no code reads/stores/logs credentials, cookies, session tokens, or browser-profile contents (the profile path is passed opaquely to Playwright; `--profile-path` help says "passed through without inspection").

## Spec spot-rechecks (3 obligations from the M-004 spec lens still hold on new HEAD)

Using the authoritative acceptance artifacts in `tmp/verify-m005/` + the code, re-confirm 3 representative obligations:
- UC1: `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` returns latest assistant text + continuity (see `accept_uc1_results.json`, `src/ask_chatgpt/api.py`).
- UC2: files/dirs -> zip bundle, and changed-files-only patch round-trip via download-primary + fenced-fallback, validate-before-mutate, round-trip diff matches (see `accept_uc2_results.json`).
- UC3: installed `ask-chatgpt` CLI wraps the function (prompt/stdout/`--out`/file args/dry-run-no-mutate/apply guardrails) (see `accept_uc3_results.json`).

## Constraints / SAFETY (obey exactly)

- Loopback/local only; NEVER contact chatgpt.com/openai. Do NOT set `channel="real"` against the real site. PyPI for `uv sync` permitted.
- Do NOT modify ANY file under test. Write ONLY your report `orchestration/reports/M-005/T4c.md` (and read `tmp/verify-m005/`). Do NOT write `.claude/`/`.agents/`; do NOT touch the shared agent venv. Do NOT commit. NEVER `git push`.

## Report (`orchestration/reports/M-005/T4c.md`, cap ~200 lines)

- First lines: `START_TIMESTAMP:` + `ESTIMATE: T4c <minutes>m`.
- The D2 and D3 findings with file:line / artifact-line evidence; the security spot-recheck results (zip-slip, network guard, credentials); the 3 spec spot-rechecks.
- Explicit lines: `D2-VERDICT: PASS|FAIL` and `D3-VERDICT: PASS|FAIL` (with exact remaining defects if FAIL).
- Last two lines: `END_TIMESTAMP:` + `T4c-STATUS: DONE` (or BLOCKED). Also include an overall `T4c-VERDICT: PASS|FAIL` line.
