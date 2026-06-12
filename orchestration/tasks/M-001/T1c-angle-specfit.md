# TASK T1c — spec-fit / simplicity lens (MISSION-001)

**Type:** design (NON-EDITING). **Worker:** pi (GPT 5.5 xhigh). **You inherit nothing — this file is your whole world.**
**Deliverable (write EXACTLY here):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/angle-specfit.md`
**Report length cap:** ~300 lines. Occam-driven, minimal, testable.

## The decision this mission feeds (context — do NOT decide it)

The team is building `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` plus a zip-bundle file workflow plus a CLI. The predecessor forbade DOM extraction ("Level B"); the new spec needs to capture assistant output. Candidate return channels under debate: (1) DOM extraction via selector maps, (2) copy-button/clipboard, (3) file-download capture, (4) connector-style callback. **Your lens is spec-fit + simplicity:** start from THIS repo's spec and the operator-UX bar, and derive the MINIMAL design that satisfies the three use cases. You evaluate channels by *simplicity / moving-parts / testability*, not by archive fidelity (another worker owns that) or low-level Playwright mechanics (another worker owns that).

## Your single problem (narrow — Occam's razor over the spec)

Read THIS repo's spec FIRST: `/home/abhmul/dev/ask-chatgpt/README.md` (the three use cases, the acceptance shape, the library-first posture, the honest-failure-modes requirement) and the operator-UX rule in `/home/abhmul/dev/ask-chatgpt/orchestration/handoffs/SEED-from-control-plane.md` (1–2 commands, inline prompts, honest actionable failures; **long runbooks were rejected as UX, 2026-06-10**; library-first; zero-dependency bias). Then produce `angle-specfit.md` answering:

1. **The three use cases, restated as testable obligations** — what must demonstrably work for each (`ask_chatgpt -> text`; bundle out → patch bundle back → applied locally with diff matching; CLI wrapping the function).
2. **The MINIMAL design** that satisfies all three — fewest moving parts (Occam). Which return channel(s) minimize complexity for (a) plain text and (b) patch-bundle retrieval? Argue from moving-parts / failure-surface / dependency count, not raw capability. A layered "primary + simple fallback" is allowed only if you justify the added part pays for itself.
3. **What a local mock-ChatGPT fixture must support** to test each candidate channel end-to-end with **ZERO chatgpt.com contact** (loopback only). Be concrete: for DOM extraction the mock serves an HTML page whose DOM matches a selector map; for clipboard it must populate a clipboard; for downloads it must serve a real downloadable file; etc. State what is cheap-to-mock vs hard-to-mock — this is a strong simplicity signal (a channel a mock can't faithfully exercise is risky).
4. **The honest-failure-mode taxonomy** the design owes (login required, session not found, upload/download unsupported, response truncated) and which channel makes each failure easiest to detect & report actionably.
5. **What ONLY operator-gated runbooks can prove** (never assumed in automated tests): upload size/type limits for zip attachments; whether/when chatgpt.com offers file downloads from responses; session pinning via URL; model-selection UI hooks. List these as explicit empirical unknowns.

End with a one-paragraph **minimal-design recommendation from this lens only** (clearly scoped as "spec-fit/simplicity view, input to synthesis").

## Grep-FIRST instruction

Read `README.md` fully (it's short). Grep the SEED handoff for `UX`, `runbook`, `library-first`, `mock`, `fixture`. For the mock-fixture question, peek at the archive mock pattern (pointers below) — grep, don't read whole files.

## Pointers

- **Primary (THIS repo):** `/home/abhmul/dev/ask-chatgpt/README.md`; `/home/abhmul/dev/ask-chatgpt/orchestration/handoffs/SEED-from-control-plane.md`.
- **Mock-fixture prior art (READ-ONLY archive `/home/abhmul/Documents/weak-simplex-conjecture/`):** `control-plane/tests/` (phase3 mock chat fixture — grep for `mock`, `fixture`, `loopback`, `selector`), `control-plane/tests/fixtures/phase3_mock_selector_map.json` (the mock-vs-real selector knobs). Use these to ground point 3 (what a mock must support), not to copy.

## SAFETY BLOCK (obey verbatim; you inherit nothing else)

- This mission contacts NO network service. NEVER contact chatgpt.com/openai or any tunnel service. Research is file-reading only.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report under `orchestration/reports/M-001/`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY; **never read its `archive/` or `human/` dirs**. Never write `.claude/` or `.agents/`.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock before any major command).
- End your report with a single-token status line: `T1c-STATUS: DONE|BLOCKED` (last line; watchers gate on `tail -1`).

## Telemetry (required in your report)

- FIRST line of your report: `ESTIMATE: T1c <minutes>m` (your up-front wall-clock estimate before starting work).
- Near the end: `ACTUAL: T1c <minutes>m` and an end timestamp from `date -Iseconds`.
- LAST line: `T1c-STATUS: DONE|BLOCKED`.
