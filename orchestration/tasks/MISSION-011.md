# MISSION-011 — Workstream B discovery: composer tools/add-on menu + Deep Research lifecycle. REAL SITE.

**Status:** DISPATCHED 2026-06-13. **Manager:** headless Opus under `claude-orchestrator-watch.sh`. **Editor:** pi, single editor. **ESTIMATE:** 120m (flag 240m); real-site + ONE minutes-long Deep Research run.

## Why
Agent-readiness for the core flows is complete (`VERIFICATION.md` M-010 gate). Operator chose to resume **Workstream B**: ONE general ChatGPT add-on/tools mechanism — **Deep Research as the FIRST consumer, NOT a special case** (memory: operator-prefers-general-abstractions). This mission is **DISCOVERY ONLY** — map the tools menu + observe the full Deep Research lifecycle so the next mission (M-012) can DESIGN + BUILD a general "select a tool → run it → read its output" abstraction. Do NOT build the abstraction here.

## HARD CONSTRAINTS — REAL SITE (read `docs/DECISIONS.md` D-002 + the charter)
- CDP attach ONLY; preflight `127.0.0.1:9222` FIRST → STOP `CDP_UNREACHABLE` if down (never launch a browser).
- NO stealth; login NEVER automated; ANY challenge/logout → STOP + `HUMAN-ACTION-NEEDED` + poll READ-ONLY, never click through. Own tabs only; `close()`=detach never quit; work in the tool's own tab; don't change global account settings.
- **LEAK GUARD (CRITICAL — model-menu discovery LEAKED operator profile text in M-009):** the tools menu sits near account/profile UI, and a Deep Research report may surface incidental personal data. Reuse the hardened `redact()` / `isAccount()` filters from `scripts/m010_real_probe.py`. Capture ONLY tool-option labels + lifecycle STRUCTURE; NEVER capture/log/commit account/profile/email/name/avatar elements or any `/c/<id>`. Scrub immediately; never let an identifier reach a commit.
- Human-paced, NO message cap, no spam; per-message audit log (redacted). **Deep Research is the most quota-heavy action + runs minutes — do EXACTLY ONE DR lifecycle run; never loop it; capture maximally per run.** Default tier stays mock-only; `uv sync --all-groups`; NEVER `git push`; telemetry v2.

## Read first
`VERIFICATION.md` (M-010 gate); the memory-equivalent facts in `orchestration/reports/M-010/discovery.md` (the model picker is a Radix portal: open-then-enumerate; selectors target `[data-radix-popper-content-wrapper]`); `scripts/m010_real_probe.py` (probe + hardened redaction pattern to reuse); `src/ask_chatgpt/driver.py` (`select_model`, `wait_for_completion` — the tools menu + long-run completion are analogous but DISTINCT); `src/ask_chatgpt/selector_maps/real.json`; this file; the charter.

---

## T1 — Map the composer tools / "+" / add-on menu (the GENERAL tool selector)
Over CDP, find the composer tools menu trigger (the "+"/tools/attachments button near the composer — DISTINCT from the model picker `model_menu`). It is a Radix-style menu: CLICK the trigger to OPEN, THEN enumerate the option entries from the portal. Capture VERIFIED selectors + on-screen labels for: the trigger, and each tool/mode entry present (Deep Research, web search, image, canvas, study/learn, connectors, etc.). Note role attributes (toggle vs submenu vs one-shot) and which require a paid plan. Record in the discovery report. Do NOT wire production `real.json` yet (M-012 does that, fail-closed) — discovery records VERIFIED selectors for the design.

## T2 — Deep Research full lifecycle (EXACTLY ONE economical run)
Select Deep Research from the tools menu; submit this small, quick-to-research prompt: **"Compare LFP vs NMC lithium battery chemistries for consumer EVs in exactly 3 bullet points, with a source per bullet."** Capture every phase (redacted):
- **Clarifying-question round:** Deep Research usually asks a clarifying question before starting. Capture its UI selectors; ANSWER it to proceed with: **"Keep it brief — 3 bullets, consumer-EV context, recent sources; no need to go deep."**; capture the answer/submit affordance.
- **Long-run progress UI + completion signal:** capture the in-progress state (progress UI, "researching…", step list) and EXACTLY how completion is signaled — this is the data for a future LONG-run completion detector (the production `wait_for_completion` 600s ceiling is for normal turns; DR runs minutes, multi-phase). Use a DISCOVERY probe with a generous observation budget (poll + log states up to ~40 min; STOP + record PARTIAL if exceeded). Do NOT use the production `wait_for_completion`.
- **Report output + citations:** capture the final report DOM structure + how citations/sources are rendered (links, footnotes, a sources panel) — informs structured extraction beyond `->text`.
Record total wall-clock + all selectors/states.

## T3 — Synthesis: `orchestration/reports/M-011/discovery.md`
- The tools-menu map (verified selectors + labels + role/kind per tool).
- The Deep Research lifecycle (select → clarify → progress → report+citations) with selectors + timing.
- **DESIGN IMPLICATIONS for the general abstraction** — capture the AXES OF VARIATION across tools so M-012 builds something general, not DR-specific: (a) selection (toggle vs submenu vs one-shot); (b) does it have a clarify round; (c) completion shape (fast inline vs long multi-phase, and how each signals done); (d) output shape (plain text vs structured report + citations). Propose the abstraction's surface: `select_tool(name)` → optional `answer_clarification(text)` → `wait_for_tool_completion()` (must handle short AND long/multi-phase) → `read_tool_output()` (text + optional structured/citations), and the selector-map keys it needs. Keep `->text` as the base return. This feeds M-012.

## T4 — Verify (producer-side) + handoff
Honest `verify.md`: what was really observed vs not (esp. DR completion-signal + report structure — the load-bearing unknowns). Real audit log (redacted; confirm a leak scan: no account identifier / `/c/<id>` / token in any M-011 artifact). `orchestration/handoffs/MISSION-011-handoff.json` — per-item status, commit shas (no push), any `CDP_UNREACHABLE`/`HUMAN-ACTION-NEEDED`, `GATE: AWAITING-TEAM-LEAD-SPOTCHECK`. Verify via pi / own analysis (no `claude` subagents).

## Deliverables
`orchestration/reports/M-011/{discovery.md,verify.md}` + redacted audit log; handoff. **Do NOT build the tool abstraction or wire production real.json — that is M-012 (design-informed by this discovery).**
