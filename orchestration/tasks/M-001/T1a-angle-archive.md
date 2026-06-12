# TASK T1a — archive-fidelity / risk lens (MISSION-001)

**Type:** research (NON-EDITING). **Worker:** pi (GPT 5.5 xhigh). **You inherit nothing — this file is your whole world.**
**Deliverable (write EXACTLY here):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/angle-archive.md`
**Report length cap:** ~300 lines. Dense, cited, no filler.

## The decision this mission feeds (context — do NOT decide it)

The team is building a new tool `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` that must (a) return the assistant's **response text** and (b) retrieve a **patch bundle** (a zip of only the changed files) — i.e. CAPTURE assistant output from the chatgpt.com browser UI. The predecessor `control-plane` system's **"Level B" contract** allowed ONLY seeding prompts into the chat UI and **FORBADE DOM extraction** of responses; results instead flowed back through an MCP connector (GPT called tools). The new spec needs to capture output WITHOUT that connector. Your job is NOT to pick a channel — it is to **faithfully extract and cite the archive's Level B rationale and the existing infra**, so a later synthesizer can weigh it. Do not recommend; report what the archive actually says, with citations.

## Your single problem (narrow — stay in this lens)

Produce `angle-archive.md` answering, with **citations (file path + section heading or line number) for every nontrivial claim**:

1. **What exactly was the Level B contract / rule?** Quote the actual definition. What did it permit vs forbid, and where is it stated?
2. **What risks were claimed to justify forbidding DOM extraction of responses?** Enumerate each (e.g. selector fragility / UI drift, account / ToS / ban risk, complexity, detectability). For EACH risk: what **evidence or argument** backed it in the archive (measured? asserted? proven on the real site? hand-reasoned?). Be explicit about evidence strength.
3. **What was empirically PROVEN on the real chatgpt.com site** (per the runbooks/verification record) vs what was only designed/mocked? Distinguish sharply.
4. **What infra already exists** in the archive per candidate channel — quote filenames + what they do:
   - selector maps (selector-map-as-data pattern),
   - the `ChatUIDriver` 8-method allowlist (what 8 methods? does any read responses?),
   - seed-prompt builders,
   - download handling / file-attachment handling (does any exist?),
   - clipboard / copy-button use (does any exist?),
   - session recovery / continuity.
5. **What did the browser-adapter mission (M-004) actually slice and what blocked?** (from the archive handoff).

End with a short **"fidelity notes"** list: anything in the new mission's framing that the archive does NOT actually support, or supports more/less strongly than assumed.

## Grep-FIRST instruction (do not read whole files)

Search, then read only the targeted hits + surrounding section. Suggested seeds: `Level B`, `DOM`, `extract`, `extraction`, `selector`, `copy`, `clipboard`, `download`, `attach`, `ToS`, `ban`, `fragile`, `allowlist`, `read`.

## Archive pointers (READ-ONLY: `/home/abhmul/Documents/weak-simplex-conjecture/`)

- `control-plane/DESIGN.md` — Phase-3 section; Level B / M-004 design rationale (grep `Level B`; there are ~7 hits).
- `control-plane/src/control_plane/browser/` — `driver.py` (ChatUIDriver 8-method allowlist), `selectors.py` (selector maps), `seeds.py` (seed-prompt builders), `recovery.py`, `session.py`, `playwright_driver.py`, `watcher.py`.
- `control-plane/VERIFICATION.md` — what was independently verified (§1–§10.1) and HOW (distinguishes real-site vs mock).
- `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md`, `phase3-chatgpt-browser.md`, `mvp-demo.md` — what was empirically proven on the REAL site (login, profile, consent flows).
- `orchestration/handoffs/MISSION-004-handoff.json` — how the browser adapter mission was sliced and what blocked.

## SAFETY BLOCK (obey verbatim; you inherit nothing else)

- This mission contacts NO network service. NEVER contact chatgpt.com/openai or any tunnel service. Research is file-reading only.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report under `orchestration/reports/M-001/`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY; **never read its `archive/` or `human/` dirs**. Never write `.claude/` or `.agents/`.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock before any major command).
- End your report with a single-token status line: `T1a-STATUS: DONE|BLOCKED` (last line; watchers gate on `tail -1`).

## Telemetry (required in your report)

- FIRST line of your report: `ESTIMATE: T1a <minutes>m` (your up-front wall-clock estimate before starting work).
- Near the end: `ACTUAL: T1a <minutes>m` and an end timestamp from `date -Iseconds`.
- LAST line: `T1a-STATUS: DONE|BLOCKED`.
