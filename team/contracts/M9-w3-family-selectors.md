# M9 · W3 — GPT-5.5 family-submenu selection fix + tighten upload selectors (OFFLINE)

You are a **pi worker** (single source editor) for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **OFFLINE — do NOT touch the browser/CDP/chatgpt.com.** A real-leg worker (W4) will live-verify your menu fix afterward.

## Ground truth from the W2 live probe (re-derive by reading `team/evidence/handoffs/M9-W2-discovery.md`)
- **Live model picker** (trigger selector `model_picker_trigger_candidates = form button[aria-haspopup="menu"]:not([data-testid])`): top-level `menuitemradio` tiers `Instant/Medium/High/Extra High/Pro Extended(checked)` **plus** a **`GPT-5.5` `menuitem`** that opens a family submenu. The **GPT-5.5 submenu** sub-radios (EXACT live labels) are: **`GPT-5.5`(checked), `GPT-5.4`, `GPT-5.3`, `GPT-4.5 Leaving on June 26`, `o3`**.
- **CONFIRMED BUG:** the production `menus.select_model(tab, sel, "GPT-5.4")` (and `"GPT-5.5"`) **fails closed** live with `MODEL_SELECTION_NOT_REFLECTED` (match_count 0). Two root causes:
  1. **Python (`menus.py`):** `select_model` only matches the requested label among the **top-level** options (`direct` = top-level `menuitemradio`, `family` = top-level `menuitem` whose label == requested). A sub-entry like `GPT-5.4` is **neither** at top level, so it's "absent". It never searches *inside* a family submenu for the requested sub-radio.
  2. **JS (`channels/cdp.py`):** `JS_MENU_ENUMERATE` and `JS_MENU_CLICK_LABEL` operate on `document.querySelector('[data-radix-popper-content-wrapper]')` — the **FIRST** popper portal. When a Radix **submenu** opens, there are **multiple** stacked `[data-radix-popper-content-wrapper]` portals; the submenu's items live in a **later/deepest** portal, so enumerating/clicking the first portal misses them.
- **Upload selectors (W2 live):** `file_input = input[type="file"]` is **too broad** (3 page-wide matches); the composer's is the only one inside the composer `form` (id `upload-files`). The real attachment chip is `button[aria-label="Remove file 1: m9-upload.txt"]` → stable form `button[aria-label*="Remove file" i]`. No `composer-attachment` data-testid exists.

## WORKER PYTHON GOTCHA
Bare `python`/`python3` resolves to a shared agent-python venv WITHOUT playwright/ask_chatgpt. Use **`uv run`** (`uv run pytest`) for everything.

## What to implement
### 1. Tighten the two upload selectors (in `src/ask_chatgpt/selectors/real.json`)
- `file_input` → **`form input[type="file"]`** (composer-scoped; matches the single composer input, avoids the 2 unrelated page inputs). (`input#upload-files` is an acceptable alternative if you justify it; prefer the `form`-scoped one as more robust to id churn.)
- `attachment_chip` → **`button[aria-label*="Remove file" i]`** (the W2-confirmed real chip). Keep it a single robust selector; drop the non-existent `composer-attachment` testid guess.
- These keys are already in `REQUIRED_SELECTOR_KEYS` + the `SelectorMap` TypedDict (W1) — just change the values. Confirm `load_selector_map("real")` still validates.

### 2. GPT-5.5 family-submenu selection — make it work live (general, label-driven)
The operator's standing preference is a **general** label-driven Radix-menu abstraction (not a GPT-5.5 special-case). Implement so `select_model(tab, sel, "<label>")` resolves a label that is **either** a top-level tier **or** a sub-radio inside any **non-forbidden** family submenu:
- **Python (`menus.py`):** when the requested label is not an enabled top-level `menuitemradio`/`menuitem` match, **search the family submenus**: for each enabled top-level `menuitem` that is **not** in `_FORBIDDEN_SUBMENUS` (`Recent files`, `Projects` — NEVER open those), open it (`action="open_submenu"`), enumerate its options, and if exactly one enabled sub-`menuitemradio` matches the requested label, select it via the existing `submenu_path` machinery. Keep it **fail-closed** (ambiguous/absent → `ModelSelectionNotReflectedError`; never silently pick the wrong model). Preserve the existing top-level tier path and the existing forbidden-submenu guard (there is a test `test_forbidden_recent_files_and_projects_submenus_are_listed_but_never_opened` — it must still pass).
- **JS (`channels/cdp.py`):** fix `JS_MENU_ENUMERATE` and `JS_MENU_CLICK_LABEL` so that when multiple `[data-radix-popper-content-wrapper]` portals are open (a submenu is showing), they operate on the **correct portal** — i.e. enumerate/find the requested item across **all** open portals (or the deepest/last), not just the first. This is the part W2 proved broken live. **This JS change cannot be exercised by the offline mock** (the mock abstracts portals) — it is **real-verified by W4**; write it carefully and note in your handoff that its live correctness rides on W4.
- **Mock (`tests/` + `channels/mock.py` if needed):** model the **real** family structure faithfully so your offline test is **falsifiable**: a top-level `GPT-5.5` `menuitem` whose `model>GPT-5.5` submenu contains sub-radios using the **real labels** (`GPT-5.5`, `GPT-5.4`, `GPT-5.3`, `GPT-4.5 Leaving on June 26`, `o3`). Note: the existing mock test `test_select_model_opens_family_submenu_then_radio_and_verifies_reflection` uses a same-named (`GPT-5.5`/`GPT-5.5`) shape that does NOT match live (sub-radio labels differ from the family name). **Add a new test** that selects a **differently-named** sub-entry (e.g. `select_model(..., "GPT-5.4")`) and asserts it opens the `GPT-5.5` submenu and selects `GPT-5.4` with verified reflection — this is the case W2 proved currently fails. **Beware the false-green trap** (M7b's gap-2 test was a false-green because a coarse mock bit opened the gate regardless of the fix): make sure that **reverting your Python submenu-search makes the new test RED** (demonstrate it).

### 3. Do NOT touch Deep Research / `set_tools` reflection
W2 found `set_tools(["Deep research"])` fails closed live (DR is a `menuitemradio` whose reflection signal differs from checkbox tools). Its true signal is **not yet captured**, so do **NOT** guess-code a DR fix — that would be coding against an assumption. `set_tools` already **fails closed** (no silent no-op), which is acceptable. Leave it. W4 will diagnose DR's real signal; DR will be fixed cheaply later or documented honestly. (You may add a one-line code comment noting the DR menuitemradio reflection caveat, but change no behavior.)

## Falsifiability + acceptance (verify, don't assume)
- `uv run pytest` → all green (baseline coming in is **259**; net may change as you add tests). Capture tail to `team/evidence/reports/M9-W3-pytest.txt`.
- Demonstrate the new family test is **falsifiable**: temporarily revert your `menus.py` submenu-search → run `uv run pytest -k <your_new_family_test>` → observe RED → restore → green. Paste the RED output in your handoff.
- Existing menu tests still pass (tier selection, ambiguity, forbidden submenus, tools Web-search).
- `git status --porcelain` shows ONLY your intended `src/` + `tests/` changes (+ your report). Do **NOT** commit. Do **NOT** touch `cache/`, `archive/`, `human/`, `issues/cdp-send-repro/controller.mjs`.

## Safety / isolation
- OFFLINE only. Branch `rewrite-v2` only. NEVER move/commit/checkout `stable`; NEVER `uv tool install/upgrade/reinstall`; NEVER `git push`; do not `git commit` (manager commits). No secrets/content written anywhere.

## Handoff (write, then stop)
Write `team/evidence/handoffs/M9-W3-family-selectors.md`:
1. **Status** (single token, top).
2. **What changed** — exact files + line ranges (real.json selectors; menus.py submenu-search; cdp.py JS portal fix; mock/test changes).
3. **Falsifiability evidence** — the RED `uv run pytest -k` output when you reverted the submenu-search; the green full-suite tail (count+exit) from `M9-W3-pytest.txt`.
4. **Live-rides-on-W4 note** — explicitly state the JS deepest-portal fix is NOT offline-testable and must be confirmed by W4's live family re-verify; give W4 the exact label to try (e.g. switch `Pro Extended`→`GPT-5.4`, then restore to `Pro Extended`).
5. **Selector values** now in real.json. **Artifacts**(+trust); **Blockers**; **Recommended next**.
Credential-free, factual, re-derived from the captured pytest output.
