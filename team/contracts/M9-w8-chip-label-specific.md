# M9 · W8 — Make `set_tools` composer-chip reflection LABEL-SPECIFIC (OFFLINE)

You are a **pi worker** (single source editor) for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **OFFLINE — do NOT touch the browser/CDP.** No real-leg budget remains.

## Why (independent verifier finding)
An independent correctness audit (`team/evidence/reports/M9-panel/LC-correctness-honesty.md`) found: `menus.py:set_tools` reflects a tool via `_reflected_tool_by_chip`, which currently treats **any** visible `active_tool_chip` (`button[aria-label*="click to remove" i]`) as confirmation of the **just-selected** tool — it does NOT check the chip actually corresponds to that tool. A stale/other tool chip could **false-positive**. Make it **label-specific** (strictly safer: a non-matching chip → fail-closed, not a false success).

## Ground truth (re-derive)
- Live DR chip aria-label (W6-captured, `team/evidence/reports/M9-W6-reverify.txt:24`): **`"Deep research, click to remove"`** — it **contains** the selected tool label `"Deep research"`. So a label-specific check `aria-label contains "<selected label>"` matches the DR chip live. (Web-search's chip is `"Search, click to remove"` — note it does NOT contain "Web search"; but Web search reflects via the **menu aria-checked** path, which stays primary, so this is fine.)
- Current code: `menus.py` `set_tools` → after select, `_reflected_tool_by_reopen` (menu aria-checked) then `_reflected_tool_by_chip` (generic `active_tool_chip` presence). The W5 test `test_set_tools_verifies_menu_unchecked_tool_by_composer_chip` uses the generic chip.

## WORKER PYTHON GOTCHA
Bare `python`/`python3` → shared agent-python venv WITHOUT playwright/ask_chatgpt. Use **`uv run`** (`uv run pytest`).

## What to implement
- Make the composer-chip reflection in `set_tools` **label-specific**: it counts as reflection only if a **removable composer tool-chip whose aria-label CONTAINS the selected tool label** is visible. Keep the menu-reopen `aria-checked` path as the **primary** signal (unchanged), the label-specific chip as the **fallback**, and **fail-closed** (`ToolSelectionNotReflectedError`) if neither confirms.
- Implementation is your choice, but keep it clean and general (no literal "Deep research" hardcode). Two reasonable options:
  - Construct a label-scoped selector, e.g. `button[aria-label*="<label>" i][aria-label*="click to remove" i]` (two attribute-substring matches on the same element), and check its visible presence; **or**
  - Query the `active_tool_chip` elements and confirm at least one has an `aria-label` that contains the normalized selected label.
- Keep the `active_tool_chip` selector key (it encodes the removable-pill marker). Do NOT change the send/upload/family code.

## Falsifiability tests (must flip RED on revert)
Update/extend `tests/test_menus.py`:
1. **Matching-label chip → verified:** selecting `Deep research` with the menu re-open unchecked but a chip whose aria-label contains `Deep research` present → `set_tools` returns verified. (Model the chip via the label-scoped selector the code queries, using `MockScenario.selector_presence`.)
2. **Non-matching chip → fail-closed:** selecting `Deep research` with the menu unchecked and ONLY a **different** tool's chip present (aria-label does NOT contain `Deep research`) → `set_tools` raises `ToolSelectionNotReflectedError` (NO false-positive). **Revert** the label-specificity (accept generic chip) → this test goes **RED** (it would wrongly verify). Paste the RED output.
3. Keep the existing Web-search (aria-checked) and fail-closed-no-signal tests passing.

## Acceptance
- `uv run pytest` → all green (incoming **267**; count may shift slightly). Capture tail to `team/evidence/reports/M9-W8-pytest.txt`.
- Falsifiability demonstrated for the non-matching-chip test (RED on revert to generic).
- No existing test weakened (upload, send-enable, verify-substring, family, Web-search).
- `git status --porcelain` shows ONLY intended `src/`+`tests/` changes (+ your report). Do NOT commit. Do NOT touch `cache/`, `archive/`, `human/`, `issues/cdp-send-repro/controller.mjs`.

## Safety / isolation
OFFLINE. Branch `rewrite-v2`. NEVER move/commit/checkout `stable`; NEVER `uv tool …`; NEVER `git push`; do not `git commit`. No secrets/content anywhere.

## Handoff (write, then stop)
Write `team/evidence/handoffs/M9-W8-chip-label-specific.md`: Status (token, top); what changed (files+lines); falsifiability RED output on revert + green suite tail (count+exit) from `M9-W8-pytest.txt`; artifacts(+trust); blockers; recommended next. Credential-free, re-derived from captured output.
