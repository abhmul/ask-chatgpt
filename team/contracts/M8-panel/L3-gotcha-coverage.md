# M8 Panel Lens L3 — Gotcha-fix coverage (READ-ONLY)

You are a **read-only verification worker** (one lens of a best-of-N panel) for the **ask-chatgpt v2 rewrite**. You inherit NOTHING but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2` (HEAD `5fac7d0`). WRITE your report to the exact path in "Deliverable" and exit.

## HARD RULES
- **READ-ONLY.** Do NOT edit/create/delete any file except your one report file. No `git add/commit/checkout/push/stash`, no branch ops, never touch `stable`, never `uv tool ...`. Offline only (no chatgpt.com/openai).
- **Do NOT run the heavy suite.** Reason over `team/evidence/reports/M8-pytest.txt` (`254 passed`, exit 0). `grep`/`read`/`ls`/`find`/read-only `git show` are fine.
- No leak: cite `file:line`, never reproduce real secret values.
- Ignore `archive/` and `human/`.

## Your lens: the 4 rewrite gotchas are PROVABLY fixed AND tested
The v2 rewrite exists to fix four specific gotchas that bit v1. For EACH, you must show: (a) the FIX is present in the v2 source (cite file:line and explain the mechanism), AND (b) a **non-vacuous test PINS it** (cite the test node-id that appears in `team/evidence/reports/M8-pytest.txt`), AND (c) the prompt/wording (where a GPT-facing string is involved) does not re-introduce the bug.

### Gotcha 1 — Rendered-DOM math corruption
Spec: capture must yield **canonical markdown only; no ambiguous math** — `\widehat`, `\ne`, `\frac{}{}` must round-trip vs the web-UI copy (never the rendered DOM, which corrupts math). 
- FIX location candidates: `src/ask_chatgpt/capture.py` (backend-api canonical markdown primary; copy-button/KaTeX-annotation fallback; DOM is last-resort fail-closed), `src/ask_chatgpt/store.py` (render preserves literal math).
- Test candidates: `tests/test_store_render.py::test_render_markdown_visible_only_literal_math_and_exact_trailing_newline`, `tests/test_capture.py`.
- Verify the capture **asymmetry**: reads go through the page's own authenticated backend endpoint, NOT the rendered DOM, with annotation/DOM as fail-closed fallback. Confirm DOM-scrape is not the primary text path.

### Gotcha 2 — Silent no-op send
Spec: capture latest user-turn `message_id` baseline BEFORE send → require a **NEWER** turn after → else raise `PromptNotSubmittedError`. Wait/retry the transiently-unmounting composer; reload-when-idle to clear SPA staleness; `wait_for_completion` requires a turn newer than baseline.
- FIX location candidates: `src/ask_chatgpt/send.py`, `src/ask_chatgpt/completion.py`, error class in `src/ask_chatgpt/errors.py` (`PromptNotSubmittedError`).
- Test candidates: `tests/test_send_completion.py`, `tests/test_send_budget.py`, `tests/test_store_pending_send.py`, `tests/test_errors.py`.
- Confirm there is genuinely a baseline-then-newer-turn assertion, not just a "we clicked send" assertion.

### Gotcha 3 — Truncation / hidden completion ceiling
Spec: **no hidden completion ceiling** (`timeout` = no-activity window, not a hard cap; backend-api poll for long Pro/DR); **eager-write** the turn + conversation ref at send; **salvage partial** text on error/timeout with `status`/`partial`. (v1 had a hidden 600s ceiling that broke long Pro/DR runs.)
- FIX location candidates: `src/ask_chatgpt/completion.py` (no-activity window semantics; no hard ceiling), `src/ask_chatgpt/store.py` (`record_partial`, eager write), `src/ask_chatgpt/session.py`.
- Test candidates: `tests/test_send_completion.py`, `tests/test_store_partial.py`, `tests/test_store_durability.py`.
- Adversarial check: grep for any literal hard ceiling constant (e.g. `600`, `_CEILING`, `max_total_wait`) in `completion.py`/`session.py` and decide whether it's a NO-ACTIVITY window (OK) or a hidden hard cap on total generation (BUG). Explain which it is.

### Gotcha 4 — `--out` suppresses stdout
Spec: `ask`/`scrape` print to **stdout AND** `--out` (v1 bug: `--out` suppressed stdout). 
- FIX location candidates: `src/ask_chatgpt/store.py` (`emit_payload` writes stdout AND out, identical bytes), `src/ask_chatgpt/cli.py` (wiring for `ask`/`scrape`/`history`/`export`).
- Test candidates: `tests/test_store_payload.py::test_emit_payload_writes_stdout_and_out_with_identical_string_bytes` (+ NUL bytes round-trip, + stdout-before-out-write-failure).
- NOTE (known, document it): this stdout-mirror is a deliberate design; an operator memory notes agent runs must redirect stdout to avoid content landing in logs. Confirm the BEHAVIOR (mirror) is correct + tested; note the operational caveat.

## Prompt-quality cross-check (operator discipline)
Where any gotcha touches a GPT-facing prompt (e.g. a capture or elicitation string), confirm the prompt does not predetermine/circularly satisfy the test. Grep model-facing strings in `src/ask_chatgpt/` and flag any that "ask for the answer" or contain base64/marker directives that would re-introduce a known bug.

## Deliverable (WRITE EXACTLY HERE)
Write `team/evidence/reports/M8-panel/L3-gotcha-coverage.md` containing:
1. Summary line per gotcha: FIXED+TESTED / FIXED-UNTESTED / NOT-FIXED.
2. A table: `gotcha | fix mechanism (file:line) | pinning test (node-id in M8-pytest.txt) | prompt-quality note | verdict`.
3. Any gotcha that is fixed but not pinned by a non-vacuous test, or where the fix looks incomplete — with severity.
4. Final line: `VERDICT: PASS` / `CONCERNS` / `FAIL`, then `CONFIDENCE: <low|med|high> — <one sentence>`.
