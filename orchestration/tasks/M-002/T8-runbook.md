# T8 — Operator OBSERVATION runbook from memo §7 (doc only; NON-EDITING of source)

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). This is a DOCUMENTATION-ONLY leg: you create ONE markdown file and touch NO source, NO tests, NO pyproject, and run NO pytest/uv. Another worker may be editing source concurrently — stay entirely out of `src/`, `tests/`, `pyproject.toml`, `uv.lock`.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/decision-memo.md` — **§7 (lines ~102-113) "Empirical unknowns resolvable only by operator-gated runbooks" is the VERBATIM SOURCE.** Each bullet there becomes a runbook section. Also read §6 briefly for context on what the mock simulates (the real runbook observes the REAL site to confirm/correct those mock assumptions).
3. `/home/abhmul/dev/ask-chatgpt/README.md` — "Acceptance shape" (each use case has an operator-gated runbook half proving it against the real site with explicit consent) and the posture (operator owns account/profile/credentials; tool never touches credentials).
4. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001 "Deferred to operator-gated runbooks" list (mirrors §7); the runbook's results later fill the REAL-site selector map + config (model selection, session pinning, upload/download support).
5. READ-ONLY format reference (adapt tone/structure, do NOT copy content): `/home/abhmul/Documents/weak-simplex-conjecture/control-plane/docs/runbooks/phase3-chatgpt-browser.md`. (NEVER read that archive's `archive/` or `human/` dirs.)

## Scope
Produce a single operator-facing observation runbook: a manual, consent-gated procedure (NO automated tool required, nothing contacts the site on the operator's behalf) by which the operator, using THEIR OWN browser/profile/account, observes the real chatgpt.com UI and records the empirical facts that the automated mock had to assume. These results unblock M-003 (real-site selector maps + config) and let the operator work in parallel.

### Deliverable (exact path)
`docs/runbooks/observe-chatgpt-unknowns.md` (create `docs/runbooks/` if needed). Structure:
- **Title + purpose**: what this runbook is for, that it is OPERATOR-RUN and CONSENT-GATED, and that the automated tool/tests NEVER perform these steps (tests are loopback-only against a mock).
- **Safety preamble (REQUIRED, prominent):** the operator uses their own account with explicit consent; record ONLY UI selectors/labels/visible behaviors; NEVER record/paste credentials, cookies, session tokens, or profile contents; nothing here is automated against the real site; the tool takes a profile DIRECTORY PATH as config and never inspects its contents.
- **One section per memo §7 unknown** (transcribe ALL of them — there are ten bullets; keep their meaning verbatim). For EACH, give: (a) **What to observe** (the question, from §7), (b) **How to observe it manually** (concrete steps the operator does in their browser), (c) **What to record** (the exact fact/selector/label/limit to write down, and where it will feed — e.g. "→ real-site selector map key `composer`" or "→ config: model option label"), (d) any **gotchas** (e.g. virtualized/lazy-loaded long responses; hidden hover menus; permission prompts).
- **Results template**: a short fill-in section (a table or checklist) the operator completes, structured so M-003 can consume it (selector keys to resolve, limits to record, yes/no capability flags for download/upload support, session-pinning behavior, model-selection hooks, completion-signal behavior).
- **Cross-references**: note that the mock fixture (memo §6) encodes the ASSUMED answers; this runbook's job is to confirm/correct them on the real site; results feed `src/ask_chatgpt/selector_maps/real.json` (a template produced later) and tool config.

The §7 unknowns to cover (each its own section): (1) zip attachment upload size/type limits; (2) whether/when ChatGPT offers file downloads from responses (+ Playwright Download integrity, filename/MIME, retention/scanning); (3) session pinning via URL/conversation ref across restarts/deleted/renamed/archived/simultaneous; (4) model-selection UI hooks (selectors/labels, persistence, failure states, manual-only?); (5) copy-button/clipboard behavior (availability, hidden menus, permission prompts, completeness for Markdown/code/citations, stale-clipboard races, telemetry visibility); (6) assistant completion signal (end-of-turn markers, streaming stop, regenerate/retry effects, virtualization of long responses); (7) file-upload UI hooks (attachment/drop selectors, progress/failure messages, whether bundle README/catalog is visible to the model); (8) text-channel size/truncation limits (max safe fenced payload, truncation symptoms, whether checksums/end-markers catch partial output); (9) artifact↔turn identity (associating a response file with a specific turn when older artifacts exist); (10) operator UX/failure messaging (login, session-not-found, upload/download-unsupported, model-unavailable detectable without reading credentials/account-private data).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- You write ONE doc. You do NOT run any automation against chatgpt.com/openai — the runbook DESCRIBES manual operator steps; nothing in this leg contacts any external service or network. Do NOT open chatgpt.com yourself.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents; the runbook explicitly forbids the operator from recording them.
- Write ONLY `docs/runbooks/observe-chatgpt-unknowns.md` (and create `docs/runbooks/`) inside `/home/abhmul/dev/ask-chatgpt`. Touch NO `src/`, `tests/`, `pyproject.toml`, `uv.lock` (a source-editing worker may be running concurrently — collisions are forbidden). Archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Do NOT run `uv`, `pytest`, `playwright`, or any build. No bare `python`. NEVER `git push`. Do NOT `git commit` (the manager commits).

## Telemetry v2 (REQUIRED — write report to `orchestration/reports/M-002/T8-report.md`)
- Run `date -Iseconds` at START and END; write literal `START_TIMESTAMP:` and `END_TIMESTAMP:` lines.
- Emit `ESTIMATE: T8 <min>m`.
- Report ≤120 lines: the deliverable path, the ten sections covered, confirmation you touched no source/tests, deviations.
- End with `T8-STATUS: DONE` (or `BLOCKED` + reason) as the LAST line.

## Success criteria
- `docs/runbooks/observe-chatgpt-unknowns.md` exists, covers ALL ten §7 unknowns (verbatim-faithful), has the prominent safety preamble, manual observation steps, a results template consumable by M-003, and cross-references to the mock (§6) and the real selector map.
- No source/tests/pyproject touched; no network; report written with `T8-STATUS:` last.
