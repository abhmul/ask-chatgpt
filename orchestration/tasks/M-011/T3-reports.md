# M-011 T3 — Write the discovery + verify reports (pi, SINGLE EDITOR for the report files)

You are pi, the single editor for the M-011 report files. Author TWO markdown files:
`orchestration/reports/M-011/discovery.md` and `orchestration/reports/M-011/verify.md`.
You INHERIT NOTHING except this contract and the files it names. Everything you need is here.

## READ FIRST (authoritative ground truth — all already redacted)
- `orchestration/reports/M-011/T1-tools-menu.json` — the composer tools-menu map (trigger, 7 options, Deep Research option, armed-state chip).
- `orchestration/reports/M-011/T2-deep-research.json` — the ONE Deep Research run's final capture (timeline summary, armed state, statuses).
- (Optional) `orchestration/reports/M-011/T2-dr-progress.jsonl` — 300 raw snapshots; the key facts are transcribed below, so you do NOT need to parse all of it.

## ABSOLUTE constraints (non-negotiable)
- Cite ONLY facts present in the two JSON artifacts (and the transcribed facts below). Do NOT invent selectors, labels, counts, or timings.
- **LEAK GUARD:** NEVER write any account/profile/email/name/avatar, any `/c/<conversation-id>`, or any token. The artifacts are already redacted — keep them redacted. Do NOT reference, quote, or reconstruct any operator conversation content. A read-only inspector and its one output file were DELETED for a leak (see "INCIDENT" below); do NOT recreate them or resurrect their content. The only place the incident is described is the verbatim block below, which you copy into verify.md as-is.
- Do NOT edit `src/**`, `src/ask_chatgpt/selector_maps/real.json`, or the probe scripts. Do NOT run git. Do NOT contact the real site. Do NOT run the probe.

---

## FILE 1 — `orchestration/reports/M-011/discovery.md`

Write these sections (use the JSON for exact selectors/labels; the structure below is the required shape):

### 1. The composer tools / add-on menu — the GENERAL tool selector
- **Trigger:** `button[data-testid="composer-plus-btn"]` (aria-label "Add files and more", `aria-haspopup="menu"`), `.count()==1`. Clicking it opens a Radix portal `div[role="menu"]` (`.count()==1`). Pattern: **open-then-enumerate** (options exist only after the trigger is clicked).
- **The 7 top-level options** (from `T2-deep-research.json` → `opened_state.options`, identical to `T1-tools-menu.json`). Render a table with columns: label | role | kind | data-state/aria-checked | paid_or_disabled | notes. The rows are exactly:
  - `Add photos & files` — role `menuitem` — kind **one-shot**
  - `Recent files` — role `menuitem`, `aria-haspopup="menu"` — kind **submenu** — note: NOT expanded (leak guard — may list the operator's files)
  - `Create image` — role `menuitemradio` — kind **toggle** — `data-state="unchecked"`
  - `Deep research` — role `menuitemradio` — kind **toggle** — `data-state="unchecked"`, `aria-checked="false"`
  - `Web search` — role `menuitemradio` — kind **toggle**
  - `More` — role `menuitem`, `aria-haspopup="menu"` — kind **submenu** — NOT expanded
  - `Projects` — role `menuitem`, `aria-haspopup="menu"` — kind **submenu** — NOT expanded (would list operator-private projects)
- **Selector robustness caveat:** the per-option selectors captured are STRUCTURAL paths (`selector_basis="structural-path"`, e.g. `body > div:nth-of-type(5) > …`), valid ONLY while the menu is open — `refindability.deep_research_option_selector_count` was **0** after Escape (the portal `div:nth-of-type(5)` unmounts). For M-012, robust selection should scope to `div[role="menu"] [role="menuitemradio"]` / `[data-radix-popper-content-wrapper] [role="menuitem*"]` and match by visible label, not the structural path.
- **Arming a toggle tool:** clicking `Deep research` arms it → a removable chip renders near the composer (`aria-label="Deep research, click to remove"`); `armed_state.deep_research_armed=true`. **Escape closes the menu but KEEPS the tool armed** (verified: `T1-tools-menu.json.after_escape.armed_state.deep_research_armed=true`). So selection (open menu → click toggle → Escape) leaves the composer clear with the tool armed.

### 2. Deep Research full lifecycle — EXACTLY ONE run (honest PARTIAL outcome)
State up front: **status = PARTIAL-TIMEOUT** (`total_wall_clock_s` ≈ 2426.9, `snapshots_recorded` = 300). What was proven vs not:
- **SELECT (proven):** tools menu opened via `composer-plus-btn`; `Deep research` (`menuitemradio`) clicked; `armed_state.deep_research_armed=true`.
- **SUBMIT (proven):** prompt `"Compare LFP vs NMC lithium battery chemistries for consumer EVs in exactly 3 bullet points, with a source per bullet."` submitted at +0s via the composer (`submitted_at` set; `prompt_chars`=117).
- **A completed turn appeared at ≈ +8s** (`phase_timeline_summary.first_completion_marker_at` is ~8s after `submitted_at`; `button[data-testid="copy-turn-action-button"]` present). Earlier heartbeat captured this as a SHORT turn (`section[data-testid="conversation-turn-1"]`, ~120px) with the turn action bar (Copy / Edit / Share / Switch model / More) and the composer re-enabled. This was **almost certainly the clarifying question**, but its TEXT was not captured.
- **LOAD-BEARING FINDING — the turn-selector blind spot:** that turn is **NOT** under `[data-message-author-role="assistant"]` — `max_assistant_turn_count = 0` across all 300 polls. The recorder keyed clarify/report detection on `[data-message-author-role="assistant"]` (inherited from normal chat), so it was **blind** to the DR turn, never recognized the clarification, never answered it, and Deep Research waited for a reply that never came — running out the 40-min observation ceiling. `clarify_observed=false`, `answered=false`, `first_report_at=null`.
- **PROGRESS UI (not positively characterized):** `progress_ui.present` was true throughout but is a **FALSE POSITIVE** from the armed "Deep research" chip text matching the lifecycle vocabulary regex; `streaming_active` was true only at the first poll then false (`first_streaming_at == last_streaming_at`). So a genuine research/activity panel was NOT positively characterized on our run.
- **REPORT + CITATIONS (NOT reached):** `final_report_structure.present=false`; `citation_structure` empty; `first_report_at=null`. These remain UNKNOWN from our run.
- **Timing:** submitted +0s; first copy-marker ≈ +8s; ran to the 2400s ceiling → PARTIAL-TIMEOUT.

### 3. DESIGN IMPLICATIONS for the general tool abstraction (the point of this mission)
Capture the **axes of variation** so M-012 builds something GENERAL (Deep Research is the FIRST consumer, not a special case):
- **(a) Selection mechanism** varies by option kind: **one-shot** `menuitem` (fires an action, e.g. file dialog), **toggle** `menuitemradio` (arms a mode; `data-state`/`aria-checked` flips; shows a removable composer chip), **submenu** `menuitem[aria-haspopup="menu"]` (expands nested options). The abstraction must branch on kind.
- **(b) Clarify round:** a tool may post a clarifying question before doing work. For Deep Research, this turn is rendered as `section[data-testid="conversation-turn-N"]` with a `button[data-testid="copy-turn-action-button"]` and the composer re-enabled — **NOT** as `[data-message-author-role="assistant"]`. Clarify detection MUST use the conversation-turn / copy-marker signal, not the author-role selector.
- **(c) Completion shape:** ranges from fast inline to **long, multi-phase, minutes-to-tens-of-minutes** (DR). The production `wait_for_completion` (`[data-message-author-role="assistant"]` + copy marker + 600s ceiling) is INSUFFICIENT for DR on two counts: wrong turn selector AND too-short ceiling. A tool-completion waiter needs a configurable long ceiling and the conversation-turn/copy-marker signal, and must distinguish a *clarify* turn (awaiting input) from a *final* turn.
- **(d) Output shape:** plain text vs structured report + citations. For DR the final output is a structured report with sources — but our run did NOT reach it, so its structure/citation rendering is an explicit UNKNOWN for M-012 to capture (see verify.md "unverified lead").
- **Proposed surface (feeds M-012; keep `->text` as the base return):**
  - `select_tool(name)` → open `tools_menu` trigger → click the option whose visible label matches `name`, branching on kind (toggle: arm + verify chip; one-shot: fire; submenu: expand). Selector-map keys: `tools_menu_trigger`, `tool_option` (role-scoped within the portal), `tool_armed_chip`.
  - `answer_clarification(text)` (optional) → detect a clarify turn via `tool_turn` (`section[data-testid^="conversation-turn"]`) + `tool_completion_marker` (`copy-turn-action-button`) + composer-editable (NOT author-role); fill + submit once.
  - `wait_for_tool_completion()` → handle SHORT inline AND LONG multi-phase; key on `tool_turn` + `tool_completion_marker` + sustained stop-absence; configurable long ceiling (no hard 600s for DR); distinguish clarify vs final turn.
  - `read_tool_output()` → text (base) + optional structured (report headings/lists + citations/sources). Selector-map keys M-012 will need to ADD (fail-closed until verified): `tools_menu_trigger`, `tool_option`, `tool_armed_chip`, `tool_turn`, `tool_completion_marker`, `tool_clarify_composer`, `report_citation`.

---

## FILE 2 — `orchestration/reports/M-011/verify.md`

Write these sections:

### Producer-side verification — what was REALLY observed vs not
- **VERIFIED (real, self-derived from our own CDP tab):** tools-menu trigger + 7 options + kinds + the Deep Research option + the armed-chip behavior + "Escape keeps armed" (T1, reproduced in the T2 open); DR select + submit + arm; a completed turn at ≈ +8s carrying a copy-turn-action-button but NO `[data-message-author-role="assistant"]` (the turn-selector finding); PARTIAL-TIMEOUT at the 2400s ceiling (300 polls).
- **NOT verified / UNKNOWN (load-bearing for M-012):** the clarifying-question TEXT and exact structure (turn not captured); a genuine research/activity progress UI (only a false-positive chip match); the FINAL REPORT structure + CITATION rendering (run never reached the report). The DR "completion signal" is therefore only partially characterized: we know a turn's copy-marker appears, and that DR turns are NOT author-role-tagged, but we did NOT observe the *final-report* completion.
- **UNVERIFIED LEAD (provenance-disclosed, do NOT treat as evidence):** during the run a since-deleted inspector incidentally (and wrongly — see INCIDENT) observed that a *completed* Deep Research report can render as `section[data-testid="conversation-turn-N"]` containing a nested `[data-message-author-role="assistant"]` with a "Thought for Xm Ys" header and multiple headings/list-items. This was from a MIS-TARGETED tab, its content was scrubbed, and it is NOT verified on our own run — M-012 must verify the report+citation structure directly. (No operator content is reproduced here; only the generic structural shape is noted as a lead.)

### INCIDENT — operator-content leak (caught + scrubbed) — copy this block VERBATIM
> During T2, the manager wrote a read-only CDP inspector (`scripts/_m011_inspect.py`) to diagnose why the recorder saw `assistant_turn_count=0`. To find the Deep Research tab among the browser's open tabs, the inspector matched on loose substrings (`lfp` / `nmc`) and the Deep Research chip. The operator was **concurrently** running their own, unrelated Deep Research conversation, and that loose match selected the OPERATOR's tab instead of ours. The inspector captured ~5 gated lines of the operator's conversation (an unrelated research topic) into `orchestration/reports/M-011/T2-dr-inspect-initial.json`. This was a leak of operator-private (non-PII) content. It was caught on the FIRST (read-only) inspector run — no second run, and `--answer-clarify` was NOT used, so the operator's session was never modified. Remediation, same step: both `T2-dr-inspect-initial.json` and `scripts/_m011_inspect.py` were DELETED; `git log` confirmed HEAD was unchanged (still the dispatch commit), so the leaked content NEVER entered git history; a full leak scan (operator terms + `/c/<id>` + token patterns) over all M-011 artifacts returned CLEAN. The captured lines were printed to the manager's transient session log (not a repo artifact). ROOT CAUSE: loose-substring tab identification. LESSON: only inspect the recorder's OWN owned tab; never enumerate the operator's tabs; if a tab must be identified by content, use a precise verbatim phrase, never loose substrings.

### Leak scan (record the commands + the CLEAN result)
State that a leak scan was run over `orchestration/reports/M-011/` (and the probe + handoff) for: operator/account identifiers, the operator's concurrent-conversation topic terms (do NOT spell them out — that would re-leak them), the generic `thought for` activity-header phrase, `/c/<hex>`, and token shapes (`sk-`, `eyJ`, `Bearer`), and returned no matches (only a benign `VIRTUAL_ENV` uv warning in the stdout log). Note the manager re-confirms this before commit.

### Telemetry
Include literal lines:
`ESTIMATE: m011-reports <n>m`
`ACTUAL: m011-reports <n>m`
and a `REWORK-CAUSE:` line ONLY if you reworked. Also restate the mission-level telemetry the manager will finalize: T2 was the long leg (DR ran the full 2426.9s ceiling).

### Artifact trust levels
List each artifact and its trust: `T1-tools-menu.json` (producer-run, manager-inspected, leak-clean); `T2-deep-research.json` + `T2-dr-progress.jsonl` (producer-run recorder, manager-inspected, PARTIAL); `discovery.md` / `verify.md` (pi-authored, pending manager independent verification vs the JSON).

## Report back (handoff)
Status DONE/PARTIAL; the two file paths; a 2-line summary of each; confirm you cited ONLY the JSON + transcribed facts and wrote NO operator content / NO `/c/<id>` / NO tokens; and the telemetry lines (`ESTIMATE:`/`ACTUAL:` for `m011-reports`).
