# M8 Panel Lens L1 — Correctness + spec-conformance (READ-ONLY)

You are a **read-only verification worker** (one lens of a best-of-N panel) for the **ask-chatgpt v2 rewrite**. You inherit NOTHING but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2` (HEAD `5fac7d0`). Do your work, then WRITE your report to the exact path named in "Deliverable" and exit.

## HARD RULES (violating any is a failed task)
- **READ-ONLY.** Do NOT edit, create, or delete any file except your one report file. Do NOT run `git add/commit/checkout/push`, `git stash`, or any branch operation. Do NOT move/commit/checkout the `stable` branch. NEVER run `uv tool install/upgrade/reinstall`.
- **Do NOT contact the network / chatgpt.com / openai.** Offline only.
- **Do NOT run the heavy test suite.** The authoritative `uv run pytest` was already produced ONCE; reason over it at `team/evidence/reports/M8-pytest.txt` (result: `254 passed in 1.01s`, exit 0). You may `grep`/`read`/`ls`/`find` freely and run *read-only* `git log`/`git show`/`git grep`. You may run `uv run python -c "import ask_chatgpt"` only if you must, but prefer static reading.
- **No leak:** if you encounter any real secret (auth bearer, `oai-*` header value, cookie, `/c/<uuid>` conversation id, account email), cite only `file:line` — NEVER reproduce the secret value in your report.
- Ignore `archive/` and `human/` unless this contract names a file there (it does not).

## Your lens: Correctness + spec-conformance
Independently verify that the v2 library **correctly implements the approved spec** — every public verb and load-bearing behavior — and that each is **backed by a non-vacuous test** in the authoritative 254-pass suite.

### Authoritative inputs to READ FIRST
- `docs/REWRITE-SPEC.md` (the approved rewrite spec) and `team/evidence/reports/M3-detailed-design.md` (790-line detailed design). These are the conformance target. Treat them as provisionally stale until cross-checked against code.
- The code: all of `src/ask_chatgpt/` (modules: `cli.py`, `session.py`, `send.py`, `capture.py`, `completion.py`, `store.py`, `menus.py`, `models.py`, `identity.py`, `allowlist.py`, `errors.py`, `__init__.py`, `channels/{base,mock,cdp}.py`, `selectors/__init__.py`) and `tests/` (33 files).
- `team/evidence/reports/M8-pytest.txt` (authoritative test output; map test node-ids to behaviors).

### Spec obligations to map (verb/behavior → code → test → verdict)
Build a per-obligation evidence table. Cover AT MINIMUM:
1. **CLI verbs present + wired**: `ask · create · scrape · history/export · fetch · loop · status` (spec "CLI verbs"). Map each to `cli.py` (argparse/dispatch) + a test in `tests/test_cli.py`.
2. **ask**: send via real UI + verified send (newer turn required) + prints to stdout AND `--out`; eager-write turn at send.
3. **create**: new conversation (and create-within-a-project if claimed).
4. **scrape / fetch / history / export**: capture via the page's own authenticated backend endpoint (`GET /backend-api/conversation/<id>` → canonical markdown) with copy-button/KaTeX-annotation/DOM fail-closed fallback (spec "Capture/action asymmetry").
5. **loop**: single invocation holding ONE persistent `Session` (attach once, verify each turn).
6. **status**: detailed tool + per-conversation diagnostics; `status` must NOT spawn a browser probe by default if the design says so (see `tests/test_smoke.py::test_status_json_no_browser_probe...`).
7. **Persistence schema** (spec "Persistence"): per-conversation store under `--data-dir` (default XDG/repo cache): `conversations/<id>/{transcript.jsonl (append-only, keyed by message_id), raw-mapping.json, attachments/}` + top-level `index.json`. `model` and `active_tools` SEPARATE fields. `created_at` from backend-api, never agent self-report. Citations ≠ attachments. Linearize current branch; retain raw tree. Map to `store.py` + `tests/test_store_*`.
8. **Identity** (spec "Identity"): canonical = conversation id; stateless URL/id selector; both URL shapes parsed; alias optional; `project_id` metadata. Map to `identity.py` + `tests/test_identity.py`, `tests/test_store_identity_resolution.py`.
9. **Model/tools** (spec "Model/tools"): ONE general label-driven Radix-menu abstraction (open → enumerate portal → select by label, fail-closed); DR is a tool, orthogonal to model; `active_tools` separate from `model`. Map to `menus.py`/`models.py` + `tests/test_menus.py`, `tests/test_models.py`.
10. **Concurrency**: managed tab pool (lazy-open, idle-evict, LRU) + adaptive send-rate (ramp + backoff + politeness floor); reads parallel; Session owns tab pool + account rate budget. Map to `session.py` + `tests/test_session_*`, `tests/test_send_budget.py`.
11. **Channels**: keep `mock` (test substrate) + `cdp` (attended real); the Playwright-launched `real` channel is DROPPED. Fail-closed selector maps, error taxonomy (+`PromptNotSubmittedError`), domain allowlist, atomic writes. Map to `channels/`, `errors.py`, `allowlist.py`, `selectors/`.
12. **Out of scope (must be ABSENT)**: the v1 bundle/patch/apply round-trip should be GONE (spec "Out of scope"). Confirm no bundle/patch verbs in the v2 CLI.

### For each obligation, record:
- `obligation` | `code evidence (file:line)` | `test evidence (test node-id from M8-pytest.txt or test file:line)` | `verdict` (PASS / PARTIAL / FAIL / MISSING-TEST).
- Flag any obligation that is **implemented but untested**, **tested but not implemented**, or where **code contradicts the spec**. Where spec and code diverge, say which is right and why (code is authoritative on what ships).

## Deliverable (WRITE EXACTLY HERE)
Write `team/evidence/reports/M8-panel/L1-correctness-spec.md` containing:
1. One-paragraph summary.
2. The per-obligation evidence table (all 12 areas).
3. A list of concrete gaps/defects (each with file:line + why it matters + severity blocking/non-blocking).
4. Final line: `VERDICT: PASS` or `VERDICT: CONCERNS` or `VERDICT: FAIL`, then `CONFIDENCE: <low|med|high> — <one sentence>`.
Be rigorous and honest; do NOT overclaim. A green suite is necessary, not sufficient — verify the tests actually exercise the spec'd behavior.
