# M-008b · E4-fix (pi, single editor) — Make the truncation sentinel markdown-inert (real-site root-cause fix)

You are the SINGLE EDITOR. OFFLINE only (no real site, no network, do not touch `127.0.0.1:9222`). NEVER `git push`.

## Why (real ground truth — verified by the manager on chatgpt.com over CDP)
The M-008b real T3 run captured a COMPLETE 180-line response (all `LINE-1 <tok>` … `LINE-180 <tok>`, 7287 bytes — NO client truncation), but the terminal sentinel `__ELICIT_COMPLETE__` came back as `ELICIT_COMPLETE` in the `.markdown` DOM read. Root cause: **`__text__` is markdown BOLD**, so ChatGPT renders the sentinel as bold and the rendered `inner_text` strips the surrounding `__`. The body lines are hyphenated (markdown-inert) and round-tripped perfectly; only the sentinel was markdown-sensitive. This caused a FALSE `CLIP_SUSPECT`. Fix the sentinel so it is markdown-inert and round-trips verbatim through real markdown rendering.

## The change (tests only)
1. In `tests/test_continuity_mock.py`, change the constant:
   - FROM: `LONG_SENTINEL = "__ELICIT_COMPLETE__"`
   - TO:   `LONG_SENTINEL = "ELICIT-COMPLETE-SENTINEL"`
   Add a short comment above it: `# markdown-inert (no _ * \` # ~ [] |): __..__ renders as bold and .markdown inner_text strips it on the real site (M-008b T3 finding).`
2. Confirm NOTHING else hardcodes the old literal: `grep -rn "ELICIT_COMPLETE" tests/ src/ orchestration/reports/M-008b/ | grep -v real-audit-log` — the real test (`tests/test_truncation_real.py`) and its classifier import `LONG_SENTINEL` (so they update automatically); if any test/src file hardcodes `__ELICIT_COMPLETE__`, update it to use the constant or the new value. (Do NOT edit `orchestration/` reports/artifacts — those record history.)
3. Verify the new sentinel is markdown-inert: it must contain none of `_ * \` # ~ [ ] | <` and not start with `-`/`#`/`>`/digits-with-dot. `ELICIT-COMPLETE-SENTINEL` satisfies this.

## RED/justification
This is a test-fixture constant fix, not a product-behavior change, so a dedicated RED test is not required. BUT you MUST prove no regression:
- The mock completeness test `test_mock_long_response_completeness_via_public_api` rebuilds its body from `LONG_SENTINEL` and asserts exact lines — it must still PASS with the new value.
- `_truncation_elicitation_prompt` interpolates `LONG_SENTINEL` into the GPT-facing prompt — confirm the new prompt instructs the model to output `ELICIT-COMPLETE-SENTINEL` verbatim.

## Verify (capture artifacts)
- `uv sync --all-groups` then `uv run pytest -q` → MUST be `207 passed, 4 deselected, 0 real_site` (ASK_CHATGPT_REAL unset). Save the summary line + exit code to `orchestration/reports/M-008b/E4-pytest.txt`.
- `uv run pytest --collect-only -q tests/test_truncation_real.py tests/test_continuity_real.py` → still 3 real_site collected.
- Record the grep result from step 2 in your report.

## Report `orchestration/reports/M-008b/E4-worker-report.md`
STATUS; the exact diff (old→new constant); the grep result (no stale `__ELICIT_COMPLETE__` literals remain); the full-suite summary (207 passed / 4 deselected); confirmation no `src/` product code changed (tests-only); commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:` lines (REWORK-CAUSE for this leg = `spec-gap` — the M-008a sentinel choice was markdown-sensitive).

Commit the slice. NEVER `git push`. OFFLINE only.
