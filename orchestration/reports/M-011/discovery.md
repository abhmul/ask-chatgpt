# M-011 discovery

## 1. The composer tools / add-on menu — the GENERAL tool selector

- **Trigger:** `button[data-testid="composer-plus-btn"]` (aria-label `Add files and more`, `aria-haspopup="menu"`), `.count()==1`. Clicking it opens a Radix portal `div[role="menu"]` (`.count()==1`). Pattern: **open-then-enumerate**: options exist only after the trigger is clicked.

| label | role | kind | data-state/aria-checked | paid_or_disabled | notes |
|---|---|---|---|---|---|
| `Add photos & files` | `menuitem` | **one-shot** | — | `false` | JSON captured this row with shortcut text `Ctrl U`. |
| `Recent files` | `menuitem`, `aria-haspopup="menu"` | **submenu** | `data-state="closed"` | `false` | NOT expanded; leak guard: may list the operator's files. |
| `Create image` | `menuitemradio` | **toggle** | `data-state="unchecked"`, `aria-checked="false"` | `false` | — |
| `Deep research` | `menuitemradio` | **toggle** | `data-state="unchecked"`, `aria-checked="false"` | `false` | Deep Research option. |
| `Web search` | `menuitemradio` | **toggle** | `data-state="unchecked"`, `aria-checked="false"` | `false` | — |
| `More` | `menuitem`, `aria-haspopup="menu"` | **submenu** | `data-state="closed"` | `false` | NOT expanded. |
| `Projects` | `menuitem`, `aria-haspopup="menu"` | **submenu** | `data-state="closed"` | `false` | NOT expanded; would list operator-private projects. |

- **Selector robustness caveat:** the per-option selectors captured are STRUCTURAL paths (`selector_basis="structural-path"`, e.g. `body > div:nth-of-type(5) > …`), valid ONLY while the menu is open. After Escape, `refindability.deep_research_option_selector_count` was **0** because the portal `div:nth-of-type(5)` unmounts. For M-012, robust selection should scope to `div[role="menu"] [role="menuitemradio"]` / `[data-radix-popper-content-wrapper] [role="menuitem*"]` and match by visible label, not the structural path.
- **Arming a toggle tool:** clicking `Deep research` arms it, and a removable chip renders near the composer (`aria-label="Deep research, click to remove"`); `armed_state.deep_research_armed=true`. **Escape closes the menu but KEEPS the tool armed** (`T1-tools-menu.json.after_escape.armed_state.deep_research_armed=true`). Selection as open menu → click toggle → Escape leaves the composer clear with the tool armed.

## 2. Deep Research full lifecycle — EXACTLY ONE run (honest PARTIAL outcome)

**Status = PARTIAL-TIMEOUT** (`total_wall_clock_s` ≈ 2426.9, `snapshots_recorded` = 300). What was proven vs not:

- **SELECT (proven):** tools menu opened via `composer-plus-btn`; `Deep research` (`menuitemradio`) clicked; `armed_state.deep_research_armed=true`.
- **SUBMIT (proven):** prompt `"Compare LFP vs NMC lithium battery chemistries for consumer EVs in exactly 3 bullet points, with a source per bullet."` submitted at +0s via the composer (`submitted_at` set; `prompt_chars`=117).
- **Completed turn at ≈ +8s:** `phase_timeline_summary.first_completion_marker_at` is about 8.0s after `submitted_at`; `button[data-testid="copy-turn-action-button"]` was present. Earlier heartbeat captured this as a SHORT turn (`section[data-testid="conversation-turn-1"]`, ~120px) with the turn action bar (Copy / Edit / Share / Switch model / More) and the composer re-enabled. This was **almost certainly the clarifying question**, but its TEXT was not captured.
- **LOAD-BEARING FINDING — the turn-selector blind spot:** that turn is **NOT** under `[data-message-author-role="assistant"]`; `max_assistant_turn_count = 0` across all 300 polls. The recorder keyed clarify/report detection on `[data-message-author-role="assistant"]` (inherited from normal chat), so it was **blind** to the DR turn, never recognized the clarification, never answered it, and Deep Research waited for a reply that never came, running out the 40-min observation ceiling. `clarify_observed=false`, `answered=false`, `first_report_at=null`.
- **PROGRESS UI (not positively characterized):** `progress_ui.present` was true throughout but is a **FALSE POSITIVE** from the armed `Deep research` chip text matching the lifecycle vocabulary regex; `streaming_active` was true only at the first poll then false (`first_streaming_at == last_streaming_at`). A genuine research/activity panel was NOT positively characterized on this run.
- **REPORT + CITATIONS (NOT reached):** `final_report_structure.present=false`; `citation_structure` empty; `first_report_at=null`. These remain UNKNOWN from this run.
- **Timing:** submitted +0s; first copy-marker ≈ +8s; ran to the 2400s ceiling → PARTIAL-TIMEOUT.

## 3. DESIGN IMPLICATIONS for the general tool abstraction (the point of this mission)

Capture the **axes of variation** so M-012 builds something GENERAL: Deep Research is the FIRST consumer, not a special case.

- **(a) Selection mechanism** varies by option kind: **one-shot** `menuitem` (fires an action, e.g. file dialog), **toggle** `menuitemradio` (arms a mode; `data-state`/`aria-checked` flips; shows a removable composer chip), and **submenu** `menuitem[aria-haspopup="menu"]` (expands nested options). The abstraction must branch on kind.
- **(b) Clarify round:** a tool may post a clarifying question before doing work. For Deep Research, this turn is rendered as `section[data-testid="conversation-turn-N"]` with a `button[data-testid="copy-turn-action-button"]` and the composer re-enabled, **NOT** as `[data-message-author-role="assistant"]`. Clarify detection MUST use the conversation-turn / copy-marker signal, not the author-role selector.
- **(c) Completion shape:** ranges from fast inline to **long, multi-phase, minutes-to-tens-of-minutes** (DR). The production `wait_for_completion` (`[data-message-author-role="assistant"]` + copy marker + 600s ceiling) is INSUFFICIENT for DR on two counts: wrong turn selector AND too-short ceiling. A tool-completion waiter needs a configurable long ceiling and the conversation-turn/copy-marker signal, and must distinguish a *clarify* turn (awaiting input) from a *final* turn.
- **(d) Output shape:** plain text vs structured report + citations. For DR the final output is a structured report with sources, but this run did NOT reach it, so its structure/citation rendering is an explicit UNKNOWN for M-012 to capture (see `verify.md` unverified lead).
- **Proposed surface (feeds M-012; keep `->text` as the base return):**
  - `select_tool(name)` → open `tools_menu` trigger → click the option whose visible label matches `name`, branching on kind (toggle: arm + verify chip; one-shot: fire; submenu: expand). Selector-map keys: `tools_menu_trigger`, `tool_option` (role-scoped within the portal), `tool_armed_chip`.
  - `answer_clarification(text)` (optional) → detect a clarify turn via `tool_turn` (`section[data-testid^="conversation-turn"]`) + `tool_completion_marker` (`copy-turn-action-button`) + composer-editable (NOT author-role); fill + submit once.
  - `wait_for_tool_completion()` → handle SHORT inline AND LONG multi-phase; key on `tool_turn` + `tool_completion_marker` + sustained stop-absence; configurable long ceiling (no hard 600s for DR); distinguish clarify vs final turn.
  - `read_tool_output()` → text (base) + optional structured (report headings/lists + citations/sources). Selector-map keys M-012 will need to ADD (fail-closed until verified): `tools_menu_trigger`, `tool_option`, `tool_armed_chip`, `tool_turn`, `tool_completion_marker`, `tool_clarify_composer`, `report_citation`.
