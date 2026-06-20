# MISSION-011b — Deep Research lifecycle re-capture (completes M-011 T2). REAL SITE.

**Status:** DISPATCHED 2026-06-13. **Manager:** headless Opus under `claude-orchestrator-watch.sh`. **Editor:** pi, single editor. **ESTIMATE:** 90m (flag 180m); real-site + ONE Deep Research execution (minutes-long).

## Why
M-011 mapped the tools menu (COMPLETE) but the Deep Research lifecycle was NOT captured: the recorder keyed on `[data-message-author-role="assistant"]`, which **DR turns do not use** — they use `section[data-testid="conversation-turn-N"]` + `button[data-testid="copy-turn-action-button"]`. So the clarifying question went unread/unanswered and DR timed out before producing a report. **Operator confirmed a CLEAN run window (they are NOT using the ChatGPT browser concurrently).** Re-capture the full DR lifecycle so M-012 can design the general `wait_for_tool_completion` + `read_tool_output`.

## HARD CONSTRAINTS — REAL SITE (read `docs/DECISIONS.md` D-002 + the charter)
- CDP attach ONLY; preflight `127.0.0.1:9222` FIRST → STOP `CDP_UNREACHABLE` if down (never launch a browser).
- NO stealth; login NEVER automated; ANY challenge/logout → STOP + `HUMAN-ACTION-NEEDED` + poll READ-ONLY, never click through.
- **OWN TAB ONLY — by the tool-created page identity, NEVER by title/substring tab-matching (this caused M-011 leak #2).** Work exclusively in the tab the tool opens (`session.page` / the CDP `new_page`); never enumerate, read, click, or navigate any other tab; never open the chat-history sidebar / account UI. `close()`=detach never quit.
- **LEAK GUARD:** reuse the hardened `redact()` from `scripts/m011_real_probe.py`. The report content is the team's OWN neutral prompt (batteries) — capture its STRUCTURE; redact any incidental account/personal data, `/c/<id>`, names, emails. Per-message audit log (redacted). NEVER commit an identifier; scrub immediately.
- Human-paced, NO message cap. **EXACTLY ONE Deep Research execution.** Default tier stays mock-only; NEVER `git push`; telemetry v2.

## Read first
`orchestration/reports/M-011/{discovery.md,verify.md}` (the tools-menu map + the corrected-selector finding + the incident); `scripts/m011_real_probe.py` (probe + redaction; FIX the turn selector); `src/ask_chatgpt/driver.py` (`select_model` open-then-enumerate pattern; the composer-plus-btn tools trigger); this file; the charter.

## Approach: FRESH DR run in the tool's own tab (do NOT dig through chat history)
Do NOT try to resume the M-011 stalled conversation (finding it means touching the history sidebar = account UI = leak risk). Start FRESH in the tool's own new tab.

---

## T1 — Arm Deep Research + submit
Open the tools menu (`button[data-testid="composer-plus-btn"]` → Radix menu), select the `Deep research` `menuitemradio` toggle (confirm the removable chip arms), then submit the prompt: **"Compare LFP vs NMC lithium battery chemistries for consumer EVs in exactly 3 bullet points, with a source per bullet."** Use the CORRECTED DR-turn selector `section[data-testid="conversation-turn-N"]` (+ `copy-turn-action-button`) for ALL turn detection — NOT `[data-message-author-role="assistant"]`.

## T2 — Read + ANSWER the clarifying question (the step M-011 missed)
DR asks a clarifying question first. READ its text from the latest `conversation-turn-N` (redact if anything personal appears — it won't, the topic is batteries). Capture the clarify UI (is it a normal assistant turn? a special input?). ANSWER it: **"Keep it brief — 3 bullets, consumer-EV context, recent sources; no need to go deep."** Capture the answer/submit affordance. Confirm DR then STARTS the research (progress UI appears).

## T3 — Long-run completion signal (the load-bearing unknown)
Observe the deep-research execution: capture the in-progress UI (progress bar / "researching…" / step/activity list) and EXACTLY how the FINAL completion is signaled — the report turn appears, a `copy-turn-action-button` on the report turn, composer re-enables, any "research complete" marker. CRITICALLY distinguish the clarify turn from the FINAL report turn (turn index, content length, markers). Generous discovery budget (~40 min from the clarify answer; STOP + record PARTIAL if exceeded). Do NOT use the production `wait_for_completion`.

## T4 — Report + citations structure
Capture the final report DOM structure (headings, bullets, length) and how citations/sources render — inline links, numbered footnotes, a "Sources" section/panel, hover cards. This is the data for `read_tool_output` structured extraction beyond `->text`. Record selectors + the structure (redacted).

## T5 — Synthesis + handoff
Append a **"Deep Research lifecycle — CAPTURED"** section to `orchestration/reports/M-011/discovery.md` (or `orchestration/reports/M-011b/discovery.md`): the full select → clarify(read+answer) → progress → final-completion-signal → report+citations, with selectors + timing. Update the DESIGN IMPLICATIONS: `wait_for_tool_completion` (no 600s ceiling; clarify-vs-final-turn distinction; the real completion signal) and `read_tool_output` (report structure + citation extraction). Honest `verify.md` (what's captured vs still unknown). Redacted audit log + leak scan (confirm no identifier in any artifact). `orchestration/handoffs/MISSION-011b-handoff.json` — STATUS, commit shas (no push), any `CDP_UNREACHABLE`/`HUMAN-ACTION-NEEDED`, `GATE: AWAITING-TEAM-LEAD-SPOTCHECK`. Verify via pi / own analysis (no `claude` subagents).

## Deliverables
Updated DR-lifecycle discovery + `verify.md` + redacted audit log; the fixed probe (`scripts/m011_real_probe.py` turn selector); handoff. **Report-only / discovery — NO product code or real.json wiring (M-012 does that).**
