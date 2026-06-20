# M-011 T1 — Author the real-site discovery probe `scripts/m011_real_probe.py` (pi, SINGLE EDITOR)

You are pi, the single editor for this mission. Author ONE new file: `scripts/m011_real_probe.py`.
You INHERIT NOTHING except this contract and the files it tells you to read. Everything you need is here.

## What this probe is for (context)
It is a real-site **discovery** probe (a sibling of `scripts/m010_real_probe.py`) that attaches to an operator-launched Chrome over CDP and discovers, on `chatgpt.com`:
- **T1:** the composer **tools / "+" / add-on menu** (the GENERAL tool selector — DISTINCT from the model picker) — enumerate every tool option with VERIFIED selectors + labels + role/kind.
- **T2:** the **Deep Research full lifecycle** (select -> clarify -> long-run progress -> report+citations), captured by a *dumb recorder* that snapshots the redacted DOM state timeline.

This is DISCOVERY tooling, NOT product code. You will NOT edit `src/ask_chatgpt/**`, NOT edit `src/ask_chatgpt/selector_maps/real.json`, and NOT run any git command. The manager runs the legs and writes nothing in `src/`.

## HARD SAFETY CONSTRAINTS (transcribe into the code's behavior; non-negotiable)
- **CDP attach only.** Reuse the imported `connect()` (it preflights and fail-closes `CDP_UNREACHABLE`). NEVER launch a browser. NEVER automate login.
- **Challenge/logout = STOP.** Reuse `recheck_safe(session)` and the `HUMAN_ERRORS` handling exactly as m010 does: on any `ChallengePresentError`/`LoginRequiredError`/`ProfileLockedError`, emit `HUMAN-ACTION-NEEDED: <label>`, do NOT close the session (so the human can act), do NOT click through, and return exit code 5.
- **Own tabs only.** The session opens its own CDP tab; `session.close()` detaches (closes only owned tabs, never quits the operator's browser). Always `session.close()` in a `finally`.
- **LEAK GUARD (CRITICAL — a prior mission leaked operator profile text).** The tools menu sits near account/profile UI and a Deep Research report may surface incidental personal data. Capture ONLY tool-option labels + lifecycle STRUCTURE. NEVER capture, log, or write: account/profile/email/name/avatar/`img alt`, or any `/c/<conversation-id>`. Apply the imported `redact()` to EVERY emitted string AND to EVERY artifact write (redact strips `/c/<id>`, URLs, and secret params). In the page-evaluate JS, REUSE the m010 sensitivity filters verbatim (below) and ADD an email/`@` blocker.
- **Human-paced, no spam.** Small waits between actions (reuse `HUMAN_PACE_S`). No rapid-fire loops faster than ~8s in the observe loop.

## Read first (authoritative)
- `scripts/m010_real_probe.py` — COPY its proven primitives + JS leak-guard helpers (details below). Note it is inert on import (`if __name__ == "__main__"` guard), so you can import from it.
- `src/ask_chatgpt/driver.py` — method signatures you will call: `BrowserSession.open_or_create_conversation(None)`, `.send_prompt(text)` (fills composer AND submits), `.page` (the Playwright `Page`), `.close()`. (You do NOT modify this file.)
- `orchestration/reports/M-010/discovery.md` — confirms the Radix open-then-enumerate pattern; the model picker (DISTINCT from the tools menu) is `form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])`; options render in `[data-radix-popper-content-wrapper]`.

## Reuse: import these PROVEN primitives from m010 (do NOT re-implement)
At top of the new file (the `scripts/` dir is on `sys.path[0]` when the script runs, so a bare import works):
```python
from m010_real_probe import (
    redact, _emit, _emit_human_action_needed,
    connect, recheck_safe, HUMAN_ERRORS, HumanActionStop,
    BASE_URL, CDP_ENDPOINT, HUMAN_PACE_S,
)
```
Define your OWN (M-011-scoped) `REPORT_DIR = Path(__file__).resolve().parents[1] / "orchestration" / "reports" / "M-011"`, `AUDIT_LOG = REPORT_DIR / "real-audit-log.md"`, an `audit(row: dict)` (copy m010's `audit()` + its header/regex EXACTLY but pointed at the M-011 AUDIT_LOG), and a `_write_json(path, payload)` that does `path.write_text(redact(json.dumps(payload, indent=2, sort_keys=True, default=str)), encoding="utf-8")` after `REPORT_DIR.mkdir(parents=True, exist_ok=True)`. Reuse m010's audit table columns (#, timestamp, leg, action, prompt-label, observation, markers, result).

## Reuse the JS leak-guard helpers VERBATIM
In `scripts/m010_real_probe.py`, inside `_MODEL_ENUMERATE_JS` (≈ lines 374-870), copy these JS helper functions UNCHANGED into your new JS string(s): `isAccount`, `safeAria`, `ownText`, `compact`, `rawVisibleText`, `attrBlob`, `isSensitive`, `isVisible`, `qAttr`, `selectorCount`, `structuralPath`, `uniqueSelector`, `rectShape`, plus the constant `SENSITIVE_TEXT_RE`. Keep ALL account/profile/personal blockers intact. Then ADD this extra gate used by every text you emit:
```js
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+/;            // never emit anything email-shaped
const LONGID_RE = /[A-Za-z0-9_-]{20,}/;                          // never emit long id/token-shaped tokens
function labelSafe(value){                                       // gate for tool/option labels
  const t = compact(value);
  if(!t) return false;
  if(t.length > 80) return false;
  if(SENSITIVE_TEXT_RE.test(t)) return false;
  if(EMAIL_RE.test(t)) return false;
  if(LONGID_RE.test(t)) return false;
  return true;
}
function gatedLabel(value, limit){ const t = compact(value); return labelSafe(t) ? t.slice(0, limit||80) : '<omitted-or-unsafe>'; }
```
Every option/label/snippet you put into output MUST pass through `gatedLabel()` (or be a pure structural count / boolean / role string). Structural fields (counts, role names, aria-haspopup values, data-state, booleans, rect numbers) are safe to emit raw. Never emit `innerText`/`textContent` of the account control, the page, a conversation link, or a report body except via `gatedLabel()` truncation.

---

## CLI: argparse with two subcommands (mirror m010's `build_parser`/`main` shape)
```
tools-menu                      # repeatable, NO quota. enumerate the composer tools/add-on menu.
deep-research [--max-observe-s 2400] [--clarify-wait-s 150] [--poll-s 8] [--force]
```

### Subcommand `tools-menu` (REPEATABLE — the manager will run this several times)
1. `session = connect()`. `session.open_or_create_conversation(None)` (on `HUMAN_ERRORS`: emit HUMAN-ACTION-NEEDED, set close_on_exit=False, return 5). `if not recheck_safe(session): return 5`.
2. `page = session.page`.
3. Hydration: evaluate `_TOOLS_ENUMERATE_JS` in a loop (poll every 500ms, up to 10s) until a tools-menu **trigger candidate** is found, capturing the closed-state. The trigger is the composer **"+" / tools / attachments** button NEAR the composer — DISTINCT from the model picker. Identify candidates among visible composer-area clickables (`button, [role=button], [aria-haspopup], [data-state]` within/near `form:has(#prompt-textarea)`) whose attr-blob/text suggests tools/add/attach/plus (e.g. `aria-haspopup=menu` AND composer-area AND NOT the model picker `:not([data-testid])` reasoning button; or testid/aria containing `tools`/`add`/`attach`/`plus`/`compose`; or visible text `+`). Capture ALL plausible trigger candidates (redacted shapes) so the manager can pick if the auto-choice is wrong; also pick a `best_trigger`.
4. Capture `closed_state`. `audit(...)`. `recheck_safe`.
5. If no trigger candidate: write `T1-tools-menu.json` with `verdict="HONEST-FAIL-CLOSED"`, `fail_closed_reason`, and the closed_state evidence (all candidate shapes); `audit`; `_emit("TOOLS-MENU: HONEST-FAIL-CLOSED no-trigger")`; return 0 (NOT an error — honest fail-closed).
6. Else: click `best_trigger` -> `page.wait_for_timeout(1000)` -> evaluate `_TOOLS_ENUMERATE_JS` again to capture `opened_state`: the portal root(s) (`[data-radix-popper-content-wrapper], [role=menu]`), and for EACH option entry (`[data-radix-popper-content-wrapper] [role=menuitem], [role=menuitemradio], [role=menuitemcheckbox], [role=option]`): `{selector (uniqueSelector), selector_count, role, aria_haspopup, aria_checked, data_state, data_radix_collection_item, disabled, kind, label (gatedLabel)}`. Classify `kind`: `"submenu"` if `aria-haspopup=="menu"`; `"toggle"` if role is `menuitemradio`/`menuitemcheckbox` or `aria-checked` is present; else `"one-shot"`. Also record a `paid_or_disabled` boolean (disabled, `aria-disabled`, or an upgrade/lock affordance in the row).
7. Identify the **Deep Research** option (label matches `/deep\s*research/i`). Record `deep_research_option` (its full redacted shape).
8. BEST-EFFORT (wrap in try/except so a failure here does NOT fail the leg): probe **selecting** Deep Research WITHOUT submitting — click the Deep Research option, `wait_for_timeout(800)`, re-evaluate to capture the **armed state** (how a selected tool manifests: an option `aria-checked`/`data-state` change, or a "Deep research" chip/pill rendered near the composer). Capture `armed_state` (redacted structure: any composer-adjacent chip's gatedLabel + role + a remove-affordance selector). Do NOT press Enter / do NOT submit. Then press `Escape` (and if a chip remains, that's fine — we close the tab; do NOT submit).
9. `page.keyboard.press("Escape")`; `wait_for_timeout(500)`; re-evaluate `after_escape` (confirm the portal closed). Set `verdict="FOUND"` if >=1 option enumerated AND Deep Research located, else fail-closed reason.
10. `_write_json(REPORT_DIR/"T1-tools-menu.json", payload)` with: closed_state, chosen trigger + selector + `.count()`, opened_state (portal_roots, options[]), deep_research_option, armed_state, after_escape, refindability (trigger selector + count, option selector strategy + count). `audit(...)`. `_emit("TOOLS-MENU: <verdict> trigger_count=.. options=.. dr_found=..")`. `finally: session.close()`.

### Subcommand `deep-research` (EXACTLY ONE RUN — quota-heavy, minutes-long; NEVER loop it)
1. **Exactly-once guard:** if `(REPORT_DIR/"T2-deep-research.json").exists()` and not `args.force`: `_emit("DR-ALREADY-RAN: refusing (T2-deep-research.json exists; pass --force to override)")`; return 0.
2. Write `T2-status.json` = `{"status":"STARTED","started_at":<iso>}` immediately (so the detached run is observable).
3. `connect()`; `open_or_create_conversation(None)`; `recheck_safe`. `page=session.page`.
4. Open the tools menu (same trigger logic as `tools-menu`: evaluate the enumerate JS, click best_trigger, wait). Find + click the **Deep Research** option (label `/deep\s*research/i`). `audit("select-deep-research")`. If the option is not found, write `T2-status.json` PARTIAL + reason, write `T2-deep-research.json` with what you have, `session.close()`, return 0 (fail-closed; nothing submitted).
5. Capture `armed_state` (redacted). Then submit the research prompt via `session.send_prompt(DR_PROMPT)` where:
   `DR_PROMPT = "Compare LFP vs NMC lithium battery chemistries for consumer EVs in exactly 3 bullet points, with a source per bullet."`
   `audit("submit-dr-prompt", prompt-label="lfp-vs-nmc-3bullets")`.
6. **DUMB RECORDER loop** (this is the core capture — do NOT try to be a clever completion detector; just record the redacted state timeline). Define `_DR_STATE_JS` returning a redacted snapshot dict:
   `{ ts, elapsed_s, assistant_turn_count, streaming_active (stop-button present: button[data-testid="stop-button"]), completion_marker_present (button[data-testid="copy-turn-action-button"]), composer_present, composer_editable, progress_ui: {present, gated_texts:[..], element_count} (any visible element whose gatedLabel matches DR-lifecycle vocab /research|searching|reading|browsing|analyz|thinking|sources?|activity|steps?|working|planning/i — counts + a few gatedLabel short texts), report: {present, heading_count, listitem_count, paragraph_count, link_count, has_sources_panel, has_numbered_citations, gated_snippets:[first few gatedLabel-truncated lines]} (only when an assistant turn looks like a rendered report), clarify_ui: {looks_like_clarify (>=1 assistant turn AND not streaming AND composer editable AND progress_ui NOT present), suggestion_chip_count, gated_chip_texts:[..]} }`. ALL text via `gatedLabel`. NO raw URLs (redact handles), NO `/c/<id>`, NO account.
   - Each poll (`poll_s`, default 8s): evaluate `_DR_STATE_JS`; append the snapshot as one line to `T2-dr-progress.jsonl`; overwrite `T2-dr-latest.json` (heartbeat) with the latest snapshot + a running phase guess. Every ~5th poll call `recheck_safe`; if it returns False -> write `T2-status.json` = HUMAN-ACTION-NEEDED + PARTIAL, break (do NOT click through), keep session open (close_on_exit=False), return 5.
7. **Clarify round** (interleaved with the recorder, first `clarify_wait_s` seconds, default 150s, ANSWER AT MOST ONCE): when a snapshot shows `clarify_ui.looks_like_clarify` is true and you have NOT yet answered: capture the clarify structure into `clarify_capture` (assistant-turn selector shape + suggestion chips + composer-awaiting state), then `session.send_prompt(CLARIFY_ANSWER)` where
   `CLARIFY_ANSWER = "Keep it brief — 3 bullets, consumer-EV context, recent sources; no need to go deep."`
   `audit("answer-clarification", prompt-label="brief-3bullets")`; set `answered=True`. If no clarify appears within `clarify_wait_s` and research progress IS present, proceed WITHOUT answering (record `clarify_observed=False`).
8. **Completion (best-effort, do not over-trust):** consider the run complete when a report-looking assistant turn is present AND `streaming_active` is False AND `completion_marker_present` is True AND that has held stable across >= 2 consecutive polls (~>=16s). On completion: capture the final `report_structure` (headings/list/links/sources-panel/numbered-citations + gated truncated snippets) and `citation_structure`; break the loop.
9. Stop conditions: completion (above) OR `elapsed_s >= max_observe_s` (record `PARTIAL-TIMEOUT`, STOP, do not loop again).
10. Write `T2-deep-research.json` = full structured capture: armed_state, clarify_observed/clarify_capture/answered, the phase timeline summary (derived from jsonl: when streaming started/stopped, when progress UI appeared/disappeared, when report appeared), final report_structure + citation_structure, ALL VERIFIED selectors used (tools trigger, DR option, progress UI, report turn, citations, copy/stop markers), and timing (submitted_at, first_progress_at, report_at, total_wall_clock_s). Write `T2-status.json` = `{"status":"DONE"|"PARTIAL-TIMEOUT"|..., "ended_at":<iso>, "total_wall_clock_s":..}`. `audit(...)`. `_emit("DEEP-RESEARCH: <status> wall_clock=..s turns=.. report_present=..")`. `finally: session.close()`.

## Output files (all under `orchestration/reports/M-011/`, all redacted)
`T1-tools-menu.json`, `T2-deep-research.json`, `T2-dr-progress.jsonl`, `T2-dr-latest.json`, `T2-status.json`, and the appended `real-audit-log.md`.

## Self-validation you MUST do (and report), but NOTHING that hits the real site
- `uv run python -m py_compile scripts/m011_real_probe.py` (MUST be clean).
- `uv run python scripts/m011_real_probe.py --help` and `... tools-menu --help` and `... deep-research --help` (MUST print usage; confirms imports resolve + argparse wired).
- Do NOT run the `tools-menu` or `deep-research` legs — the manager runs those (the manager controls the exactly-once DR run). Do NOT edit `src/**` or `real.json`. Do NOT run git.

## Report back (handoff)
Status DONE/PARTIAL/BLOCKED; the py_compile + --help evidence (paste the key lines); the list of m010 primitives imported and JS helpers copied; confirmation the leak filters + `gatedLabel`/email/longid gates are applied to every emitted label; and telemetry lines: `ESTIMATE: author-m011-probe <n>m` and `ACTUAL: author-m011-probe <n>m`, an end timestamp, and a `REWORK-CAUSE:` line only if you reworked.
