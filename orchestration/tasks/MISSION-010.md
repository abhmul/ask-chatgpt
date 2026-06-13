# MISSION-010 — Wire real model-selection (close B-2). REAL SITE.

**Status:** DISPATCHED 2026-06-13. **Manager:** headless Opus under `claude-orchestrator-watch.sh`. **Editor:** pi, single editor. **ESTIMATE:** 105m (flag 210m); real-site human-paced.

## Why
The tool is agent-usable for the core flows (`VERIFICATION.md` M-009 gate). The ONE remaining real capability gap is `model_settings`: mock-proven but FAIL-CLOSED on real (`real.json` `model_menu`/`model_option` empty). M-009 T3 concluded "no targetable model switcher" — but flagged the likely cause: it enumerated WITHOUT opening the picker. Close B-2: map + wire the real model picker so `model_settings={"model": "..."}` actually selects a model live.

## ROOT-CAUSE INSIGHT (why T3 missed it) — the picker is a Radix dropdown
The model menu is a **Radix dropdown**: its option elements render in a **PORTAL** (appended near `document.body`, OUTSIDE the trigger's DOM subtree) only AFTER the trigger is clicked. So the wiring is: (1) find + CLICK the model-menu **trigger** (a button in the composer/header that shows the current model name) to OPEN it; (2) THEN enumerate the portal-rendered **option** elements; (3) capture selectors that match post-open. Enumerating before opening finds nothing — that was T3's miss.

## HARD CONSTRAINTS — REAL SITE (read `docs/DECISIONS.md` D-002 + the charter)
- CDP attach ONLY; preflight `127.0.0.1:9222` FIRST → STOP `CDP_UNREACHABLE` if down (never launch a browser).
- NO stealth; login NEVER automated; ANY challenge/logout → STOP + `HUMAN-ACTION-NEEDED` + poll READ-ONLY, never click through. Own tabs only; `close()`=detach never quit.
- Human-paced, NO message cap, no spam; per-message audit log. Default tier stays mock-only (`real_site`+`ASK_CHATGPT_REAL=1`); `uv sync --all-groups`; NEVER `git push`; telemetry v2; RED-first for behavior changes.
- **LEAK GUARD (CRITICAL — this exact task leaked in M-009):** the model picker sits near ACCOUNT/PROFILE UI. M-009's model-enumeration probe captured operator profile text mid-run (scrubbed pre-commit). When discovering/enumerating the menu, capture ONLY model-option elements; NEVER capture, log, or commit any account/profile/email/name/avatar/plan-personal element. Reuse the M-009 probe's hardened `redact()`. If ANY account identifier surfaces, scrub immediately and never let it reach a commit. Redact aggressively.
- Work in the tool's OWN tab; a model choice there is scoped to that conversation — do NOT change global account settings.

## Read first
`VERIFICATION.md` (M-009 gate + the model-selection remaining item); `orchestration/reports/M-009/T3-model-findings.md` (the prior attempt + the 37-testid inventory + the "must open Radix dropdown" note); `scripts/m008b_real_probe.py` / the M-009 probe (pattern + hardened redaction); `src/ask_chatgpt/driver.py` (`select_model` + how it consumes `model_menu`/`model_option`); `src/ask_chatgpt/selector_maps/{real.json,mock.json}` (mock has the keys populated — match the code's expectations); `src/ask_chatgpt/api.py` (where `select_model` is called before send); this file; the charter.

---

## T1 — Discover the model picker (real, OPEN-then-enumerate)
Over CDP: find the model-menu TRIGGER (composer/header button showing the current model name) and capture its selector. CLICK it to open the Radix dropdown. THEN enumerate the portal-rendered option elements; capture a VERIFIED `model_option` selector strategy that targets an option BY ITS VISIBLE MODEL LABEL (so `model_settings={"model": "<label>"}` can pick it). Record the available model labels (depends on the operator's plan — capture the list, no personal data). Close the menu cleanly (Escape) without selecting if just discovering. Record selectors + the model list in the discovery report (redacted).

## T2 — Wire + populate (RED-first)
1. Populate `real.json` `model_menu` (trigger) + `model_option` (the open-menu option strategy) with the verified selectors. Update the real fail-closed test that asserted these were empty (as M-009 did for `download_artifact`).
2. Make `select_model` work on real: read its current contract (how mock uses `model_menu`/`model_option`) and ensure the real path = click `model_menu` to OPEN → click the `model_option` matching the requested label → confirm. Keep it FAIL-CLOSED: a requested model absent from the open menu → `ModelUnavailableError` (named, actionable), never silently sends on the wrong model. Keep all mock tests green (212). Add a unit test for the open-then-select real ordering if the logic changed.

## T3 — Prove a real model switch (UI-state, not self-report)
Over CDP, request a specific AVAILABLE model via `model_settings` and prove the selection took effect via **UI STATE** — the trigger/header now shows the chosen model — NOT by asking the model what it is. Do TWO switches (model A → model B) to prove selection genuinely changes state, with a UI-state assertion after each. Also prove the fail-closed path: request a bogus/absent model → `ModelUnavailableError` before any send. Capture redacted evidence (model labels only, no account data).

## T4 — Verify + docs + handoff
- Update `VERIFICATION.md`: model-selection now real-PROVEN (or honest partial if some limitation found), with evidence.
- Update `docs/USAGE.md`: `model_settings` now works on real — replace the "fails closed / omit it" caveat with the real usage (available model labels + how to request + the `ModelUnavailableError` fail-closed behavior). Do NOT overclaim (only claim what T3 proved; scope to the models actually tested).
- Producer-side `verify.md` (lenses via pi / own analysis — no `claude` subagents) with a prompt-quality/honesty + safety(leak) lens. Real audit log (redacted). `orchestration/handoffs/MISSION-010-handoff.json` — per-item real status, commit shas (no push), any `CDP_UNREACHABLE`/`HUMAN-ACTION-NEEDED`, `GATE: AWAITING-TEAM-LEAD-SPOTCHECK`.

## Deliverables
`real.json` `model_menu`/`model_option` populated (or honest fail-closed if genuinely unmappable after OPENING the dropdown); `select_model` real path working; real two-switch proof + fail-closed proof; updated `VERIFICATION.md` + `docs/USAGE.md`; `orchestration/reports/M-010/{discovery.md,verify.md}` + audit log; handoff. If, after correctly opening the Radix dropdown, the picker is STILL genuinely unmappable, that is an honest fail-closed outcome — document WHY with DOM evidence; do not fabricate selectors.
