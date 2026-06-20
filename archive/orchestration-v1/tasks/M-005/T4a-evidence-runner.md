# T4a — Authoritative evidence runner (fresh INDEPENDENT verifier; clean clone)

You are a FRESH, INDEPENDENT verification worker. You did NOT produce any of the code under test. You inherit NOTHING except this file. Your job is to produce ONE authoritative evidence set that later lens workers will reason over — so capture RAW outputs, do not paraphrase.

## What you produce

A clean-clone reproduction of the committed HEAD plus raw evidence files under `tmp/verify-m005/`, and an INDEX report at `orchestration/reports/M-005/T4a.md` that quotes the load-bearing lines (exit codes, `N passed`, `overall=pass`) and points to each raw file.

## NETWORK SCOPE — read carefully (a prior mission's clean clone was broken by getting this wrong)

- The ONLY network prohibition is the PRODUCT's real site: NEVER contact `chatgpt.com` / `openai` / any real ChatGPT endpoint. The acceptance scripts and tests use a LOOPBACK (`127.0.0.1`) mock server only.
- Building the clone's venv MAY fetch packages from the standard Python index (PyPI). DO NOT set `UV_OFFLINE`. DO NOT interpret "no external network" as "no PyPI": that conflation broke the M-004 clean clone on a greenlet cache miss. If an offline `uv sync --all-groups` fails in the clone, rebuild the clone venv with network allowed FOR PACKAGES ONLY and RECORD that you did (write a note file `tmp/verify-m005/clone_sync_RECOVERY.txt`).

## Steps (capture raw output of EACH into tmp/verify-m005/)

1. Clean clone of the local committed HEAD:
   - Expected HEAD: `261a16b33e3240b4d629e72c0ae8a1fd318ff538` (the three M-005 fixes 0179400 D1, 2f0b8de D2, 261a16b D3 are committed on `main`).
   - `mkdir -p tmp/verify-m005`
   - `git clone /home/abhmul/dev/ask-chatgpt tmp/verify-m005/clone`
   - In the clone: confirm `git rev-parse HEAD` == the main HEAD `git -C /home/abhmul/dev/ask-chatgpt rev-parse HEAD`, and `git status --porcelain` is empty. Write both to `tmp/verify-m005/clone_head.txt`. (If main HEAD has advanced past 261a16b, record the actual SHA — it must still contain the three fix commits.)
2. Build the clone venv and install editable FROM THE CLONE'S OWN src:
   - From inside `tmp/verify-m005/clone`: `uv sync --all-groups` (network-allowed for packages). Confirm the install points at the clone's `src/` (editable), not the parent repo.
3. Full test suite in the clone (authoritative): `uv run pytest -q` -> `tmp/verify-m005/clone_pytest.txt`, ending with the `N passed` summary and a literal `EXIT_CODE: <code>` line you append. (Baseline before M-005 was 119 passed; after M-005 expect 121 passed — 2 new tests. Report the actual number; serialize, no xdist.)
4. UC acceptance in the clone (each spins up its OWN loopback mock; no real network): run `bash scripts/accept_uc1.sh`, `bash scripts/accept_uc2.sh`, `bash scripts/accept_uc3.sh`. For EACH, capture the script stdout (it prints `overall=` and `results_json=`) and COPY the produced `results.json` into `tmp/verify-m005/` as `accept_uc1_results.json`, `accept_uc2_results.json`, `accept_uc3_results.json`. The UC3 results MUST contain a `session-continuity` step with `status: "pass"` and `user_turns` of the two scripted prompts (this is the D3 evidence).
5. D2 regression demo (raw -> `tmp/verify-m005/d2_demo.txt`):
   - Run ONLY the new fail-closed test in the clone: `uv run pytest tests/test_driver_real_failclosed.py -q` -> must be green. Capture output.
   - Static proof that navigation is gated behind the selector check on the real path: `grep -n "_ensure_real_selector_map_ready\|sync_playwright().start()\|page.goto" src/ask_chatgpt/driver.py` (in the clone) and show that `_ensure_real_selector_map_ready()` is CALLED (in `start()`) BEFORE `sync_playwright().start()` and before `page.goto`. Also show `_ensure_real_selector_map_ready` probes selectors/attributes via the fail-closed accessors. Capture the grep + the relevant ~20 lines of `start()` and the helper.
   - Confirm `src/ask_chatgpt/selector_maps/real.json` in the clone is still the ALL-EMPTY template (every selector value `""`). Capture a grep/quote.

## Constraints / SAFETY (obey exactly)

- Loopback/local only for the product; NEVER contact chatgpt.com/openai. PyPI package fetch for the clone venv is permitted (see NETWORK SCOPE).
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` — specifically `tmp/verify-m005/` for raw evidence and `orchestration/reports/M-005/T4a.md` for your index. Do NOT write `.claude/`/`.agents/`. Do NOT touch the shared agent venv (`~/.local/share/agent-python/.venv`).
- Do NOT modify any source/test/script/runbook file. Do NOT commit anything (`tmp/` is git-ignored; your report will be committed by the manager). NEVER `git push`.
- Serialize pytest. Ephemeral ports (the mock picks its own). Kill only processes your own run starts. ESTIMATE BEFORE EXECUTE (state expected wall-clock for clone+venv+suite+acceptance before running).

## Report (`orchestration/reports/M-005/T4a.md`, cap ~200 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T4a <minutes>m`.
- An INDEX table: artifact path -> the key quoted line(s) (`EXIT_CODE`, `N passed`, `overall=pass`, the UC3 `session-continuity` verdict, the D2 grep showing readiness-before-goto, real.json all-empty). Quote, don't paraphrase.
- Note any recovery you performed (offline->network clone venv rebuild).
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T4a-STATUS: DONE` (or `T4a-STATUS: BLOCKED` with the exact blocker + what you DID capture).
