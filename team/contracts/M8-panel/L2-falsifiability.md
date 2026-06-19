# M8 Panel Lens L2 — Falsifiability / non-vacuous tests (MUTATE-AND-RESTORE, ISOLATED)

You are a **falsifiability verification worker** (one lens of a best-of-N panel) for the **ask-chatgpt v2 rewrite**. You inherit NOTHING but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2` (HEAD `5fac7d0`). You are running ALONE in the working tree (no other worker is reading it concurrently) precisely so your temporary source mutations are safe. WRITE your report to the exact path in "Deliverable" and exit.

## Why you exist
A green suite proves nothing if its load-bearing tests **cannot fail**. Operator lesson (verbatim): *"a real-site/LLM test that hands the model the answer proves nothing; panels must check a test CAN fail."* Your job: take the load-bearing tests, **break the SOURCE they protect (one at a time), run the targeted test, and confirm it goes RED.** Any test that stays GREEN when its protected behavior is broken is **vacuous/green-by-triviality** — flag it loudly.

## HARD RULES
- You MAY temporarily edit `src/ask_chatgpt/*.py` ONLY to inject a mutation, but you **MUST restore byte-for-byte** immediately after each check. **Use cp-backup/restore, NOT git:**
  - Before mutating file F: `cp F F.m8bak`
  - Mutate F (minimal change that breaks the behavior), run the targeted test, observe.
  - Restore: `cp F.m8bak F && rm F.m8bak`
  - Do NOT use `git checkout`, `git restore`, or `git stash` (a destructive-guard hook may block them and leave you stuck).
- NEVER edit any test file. NEVER touch `stable`. NEVER `uv tool install/upgrade/reinstall`. NEVER `git add/commit/push`. NEVER contact chatgpt.com/openai.
- Run ONLY **targeted** tests per mutation: `uv run pytest <nodeid-or-file> -q` (the full suite is ~1s but run targeted to be precise). Do NOT run the whole suite repeatedly.
- **At the very end, prove the tree is pristine:** run `git status --porcelain src/ tests/` and confirm EMPTY, and `ls src/ask_chatgpt/*.m8bak` returns nothing. Paste both into your report. If anything is dirty, RESTORE it and re-check before writing your verdict.
- No leak: cite `file:line`, never reproduce real secret values.

## Authoritative inputs
- `team/evidence/reports/M8-pytest.txt` — the authoritative baseline (`254 passed`, exit 0). Confirm your environment reproduces green for any test BEFORE you mutate (sanity), then mutate.
- The 4 load-bearing "gotcha" behaviors the rewrite exists to protect (your mutations should target these + a few core-store invariants):
  1. **Math fidelity (no rendered-DOM corruption):** canonical markdown only; `\widehat`, `\ne`, `\frac{}{}` round-trip literally. Tests: `tests/test_store_render.py::test_render_markdown_visible_only_literal_math_and_exact_trailing_newline`, plus capture fidelity in `tests/test_capture.py`. Mutation idea: make the renderer normalize/rewrite a math token, or strip the literal — the test must go RED.
  2. **Verified send (no silent no-op):** baseline latest user-turn message_id → require a NEWER turn after send, else `PromptNotSubmittedError`. Tests: `tests/test_send_completion.py`, `tests/test_send_budget.py`, `tests/test_store_pending_send.py`. Mutation idea: in `src/ask_chatgpt/send.py` make the "newer turn" check always pass / drop the baseline compare — a test must go RED.
  3. **No hidden completion ceiling / salvage partial:** `timeout` = no-activity window (not a hard cap); eager-write turn at send; salvage partial text on error/timeout with status/partial. Tests: `tests/test_send_completion.py`, `tests/test_store_partial.py`, `tests/test_store_durability.py`. Mutation idea: in `src/ask_chatgpt/completion.py` reintroduce a hard wall-clock ceiling, or make `record_partial` drop salvage — a test must go RED.
  4. **`--out` mirrors stdout (no suppression):** `ask`/`scrape` print to stdout AND `--out`. Tests: `tests/test_store_payload.py::test_emit_payload_writes_stdout_and_out_with_identical_string_bytes` (+ `_bytes_with_nul...`, `_prints_stdout_before_out_write_failure`). Mutation idea: in `src/ask_chatgpt/store.py` make emit write ONLY to out (skip stdout) — the test must go RED.
- Also spot-check **core-store invariants** (these underpin honesty of the transcript):
  - last-writer-wins dedupe by message_id: `tests/test_store_read_semantics.py`. Mutation: break dedupe → RED.
  - atomic raw-mapping never persists auth/oai keys: `tests/test_store_atomic_raw.py::...never_persists_auth_oai_keys`. Mutation: let a forbidden key through → RED.
  - menu fail-closed: `tests/test_menus.py`. Mutation: make an absent label silently succeed → RED.

### Method (do at least 8 distinct mutation spot-checks across the files above)
For each: (a) name the test + the SOURCE line you broke; (b) the exact minimal mutation; (c) targeted pytest result BEFORE (green) and AFTER mutation (expected RED — paste the failing assertion / the `1 failed` line); (d) confirm restore. If a mutation leaves the test GREEN → that test is **vacuous** → flag it with severity. Prefer mutating SOURCE; mutating a test to see it fail proves nothing.

## Deliverable (WRITE EXACTLY HERE)
Write `team/evidence/reports/M8-panel/L2-falsifiability.md` containing:
1. Summary: how many load-bearing tests you mutation-tested, how many were confirmed falsifiable (went RED), how many vacuous.
2. A table: `behavior | test node-id | source file:line mutated | before | after(RED?) | falsifiable? (Y/N)`.
3. Any vacuous/green-by-triviality tests, with severity.
4. The pasted `git status --porcelain src/ tests/` (must be empty) + `.m8bak` check, proving the tree is pristine.
5. Final line: `VERDICT: PASS` (suite is falsifiable) / `CONCERNS` / `FAIL`, then `CONFIDENCE: <low|med|high> — <one sentence>`.
