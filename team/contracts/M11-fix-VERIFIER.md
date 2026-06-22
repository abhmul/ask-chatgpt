# M11-fix VERIFIER — independent verification of the CLI tab-leak fix (READ-ONLY)

You are an **independent verifier worker** (pi) for team `ask-chatgpt-dev`, repo `/home/abhmul/dev/ask-chatgpt`. You inherit NOTHING except this file. You are **READ-ONLY**: you may run `read,grep,find,ls,bash`, but you have NO `edit`/`write` tools and you MUST NOT modify any tracked source file, even temporarily. Do **NOT** `git commit`/`push`/`checkout`/`switch`/`stash`/`clean`/`reset`, do NOT switch branches, do NOT move `stable`, do NOT `uv tool install/upgrade/reinstall`. OFFLINE only. Do NOT touch `issues/cdp-send-repro/controller.mjs` or `human/`. Never print/persist real secrets.

## What was changed (the thing you are verifying — DO NOT trust this prose; re-derive from ground truth)
A prior editor fixed a tab-leak bug: the CLI handlers `_handle_ask`, `_handle_scrape`, `_handle_loop` in `src/ask_chatgpt/cli.py` acquired a browser tab but never closed it. The fix wraps each handler's post-session body in `try: <body> finally: session.detach()`. Tests were added to `tests/test_cli.py`. The producer reported: baseline `276 passed` → final `280 passed` (4 new tests). You must independently confirm or refute every part below.

## Required checks — produce a verdict for EACH, re-derived from ground truth

### (a) Acceptance: re-run the suite
Run `uv run pytest -q` (this uses the PROJECT `.venv`; a `VIRTUAL_ENV ... does not match ... will be ignored` warning is EXPECTED and correct — it means uv used the project `.venv`, not the ambient one). Confirm from the INSPECTED summary line that it reports **`280 passed`** (0 failed/errors). Record the exact summary line.

### (b) Falsifiability of the 4 new tests
The 4 new tests are (find them in `tests/test_cli.py`): `test_cli_ask_closes_tab_on_success`, `test_cli_ask_closes_tab_on_error_after_acquire`, `test_cli_scrape_closes_tab_on_success`, `test_cli_loop_closes_tab_on_keyboard_interrupt`. Confirm each is genuinely falsifiable — i.e. it would FAIL if the fix were absent. Do this by PRECISE STATIC REASONING (preferred, since you are read-only):
- Read each new test. Confirm each drives a **real `Session` + real `MockChannel`** (not the `RecordingSession` stub) and asserts BOTH `mock.method_counts.get("open_tab",0) == 1` (proves the real tab-acquire path actually ran — not a vacuous no-op) AND `mock.method_counts.get("close_tab",0) == 1` (the leak-fix assertion). For the success cases, confirm it also asserts `"close_tab"` follows `"open_tab"` in `call_order`. For the error case, confirm it asserts the mapped exit code (e.g. 70) is preserved AND `close_tab==1`. For the loop case, confirm it asserts exit `130` AND `close_tab==1`.
- Read `src/ask_chatgpt/cli.py` and `src/ask_chatgpt/session.py` and reason: pre-fix, the handlers never call `session.detach()`, and the only close path is `Session.detach()`→`TabPool.close_all()`→`channel.close_tab()` (session.py:326-331, 112-121). `TabPool.release` (session.py:103-109) only flips `leased=False` — it never closes. Therefore pre-fix `close_tab` would be `0` and each new test's `close_tab==1` assertion would FAIL. State this reasoning explicitly.
- You MAY also inspect the prior editor's empirical proof in `.pi-workers/pi-20260622-110216-3093459-17418/output.log` (it reported reverting cli.py made all 4 new tests fail with `close_tab==0`), but treat that as corroboration only — your independent reasoning/inspection is the authority.
- If (and only if) you choose to ALSO empirically mutate, you must use a scratch copy and you are FORBIDDEN from leaving `src/ask_chatgpt/cli.py` modified. Strongly prefer pure static reasoning to avoid any mutation. (If you do mutate-and-restore, you MUST end by proving `git diff -- src/ask_chatgpt/cli.py` is byte-identical to before, i.e. only the legitimate fix remains.)

### (c) Diff scope, no leak, invariants
- Run `git diff --stat -- src/ask_chatgpt/cli.py tests/test_cli.py` and confirm the production+test change is confined to EXACTLY those two files.
- Run an UNQUALIFIED `git status --short`. You will ALSO see these THREE pre-existing dirty files: `issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md`, `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, plus untracked `human/` and `team/contracts/`+`team/evidence/` files. These are NOT part of this fix. PROVE the fix did not touch them: the M11-fix editor run STARTED at `2026-06-22T11:02:16-05:00`. Run `ls -la --time-style=full-iso` on `issues/cdp-send-repro/controller.mjs`, `issues/2026-06-21-chatgpt-rate-limit-too-many-requests.md`, `team/state/live-state.json` and confirm each mtime is BEFORE 11:02:16 (i.e. they were already dirty pre-run) while `src/ask_chatgpt/cli.py` and `tests/test_cli.py` mtimes are AFTER 11:02:16. Confirm `controller.mjs` mtime is `2026-06-19` (3 days old) — definitively untouched. Confirm `human/` contains only the pre-existing `prompt- buffer.md` (mtime Jun 18) and no new/modified files.
- Confirm `git rev-parse stable` == `bbbe02762deed1fa909e7354b1d6e4d89c119f63` (i.e. `bbbe027`, unmoved) and `git rev-parse --abbrev-ref HEAD` == `fix/m10-light-read-scrape` (branch unchanged).
- Scan the diff of `tests/test_cli.py` (`git diff -- tests/test_cli.py`) for any REAL leaked secret. NOTE: strings like `SECRET_TOKEN`, `SECRET_PROMPT_BODY`, `SECRET_COOKIE`, `Bearer SECRET_TOKEN`, and `HEADER_CANARIES`-derived canaries are INTENTIONAL SYNTHETIC TEST FIXTURES (they assert redaction works) — they are NOT real secrets and are pre-existing in the test style. Only flag a genuine real credential (a real bearer token, real cookie value, real `oai-*` header value harvested from a live session). Confirm there is none.

## REPORT (print to stdout at the very end — your deliverable)
Print exactly these lines with real inspected values:
```
M11-VERIFIER-VERDICT: <CONFIRMED|REFUTED>
PYTEST: <exact summary line, e.g. "280 passed in 1.02s">
FALSIFIABILITY: <CONFIRMED|REFUTED> - <one-line reasoning: why each new test fails without the fix>
NEW_TESTS_PRESENT: <yes/no - list the 4 test names you found, with the open_tab==1 AND close_tab==1 assertions confirmed>
DIFF_SCOPE: <CONFIRMED only cli.py+test_cli.py | REFUTED - list extra files>
UNTOUCHED_INVARIANTS: <controller.mjs mtime=...; human/ unchanged; pre-existing dirty files mtime-before-run: yes/no>
STABLE_BRANCH: <stable=<sha7> unmoved? yes/no; branch=<name>>
NO_SECRET_LEAK: <CONFIRMED - only synthetic test fixtures | REFUTED - describe WITHOUT reprinting the secret>
NOTES: <any discrepancy, or "none">
```
Then stop.
