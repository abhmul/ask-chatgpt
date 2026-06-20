# T6 — Real-site acceptance runbook (operator-gated UC1+UC2+UC3 halves; NEVER run by automation)

**Type:** doc authoring (NON-EDITING source; writes ONE new disjoint doc file — may overlap the editing chain). **Worker:** pi (GPT 5.5 xhigh). **You inherit NOTHING except this file and what it tells you to read.**
**Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd).**
**Deliverable (write EXACTLY here, create the file):** `/home/abhmul/dev/ask-chatgpt/docs/runbooks/real-site-acceptance.md`
**Report ALSO required (write here):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/T6-report.md`
**Runbook length:** as long as it needs to be to be operator-followable and unambiguous; the report ~120 lines.

## Context — what this runbook is for

`ask-chatgpt` proves each use case TWO ways: (a) an automated end-to-end acceptance against a **local mock ChatGPT** (loopback fixture; tests NEVER touch chatgpt.com); and (b) an **operator-gated runbook half** proving it against the REAL chatgpt.com on the operator's own account, with explicit typed consent. This task authors the operator-gated half for ALL THREE use cases:
- **UC1** `ask_chatgpt(prompt, session, model_settings) -> text` (already built + mock-proven, M-002).
- **UC2** bundle workflow: send files/dirs -> retrieve a changed-files-only patch bundle -> apply locally (built in M-003 T2/T3/T4; mock-proven).
- **UC3** `ask-chatgpt` CLI wrapping the function (built in M-003 T5; mock-proven).

The real channel is built but UNPROVEN against the live site: `src/ask_chatgpt/selector_maps/real.json` is an all-empty fail-closed template until the operator resolves the observation runbook. This runbook is how a consenting operator proves the real halves on their own machine.

## Read these FIRST (in order)
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/docs/runbooks/observe-chatgpt-unknowns.md` — the EXISTING operator observation runbook (resolves the 10 empirical unknowns + fills `selector_maps/real.json`). Match its tone/structure/consent style. Your runbook's PREREQUISITE section points the operator here: real-site acceptance CANNOT run until this is done and `real.json` is filled.
3. `/home/abhmul/dev/ask-chatgpt/README.md` — the 3 use cases + "Acceptance shape" (each UC has an operator-gated runbook half) + honest failure modes.
4. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` D-001 — DOM-primary text read; download-capture-primary + fenced fallback for bundles; operator-owned profile/credentials (tool never reads/stores/logs them); empirical-revisit triggers (e.g. flip reader order if real-site DOM is flakier than copy).
5. `/home/abhmul/dev/ask-chatgpt/orchestration/handoffs/MISSION-002-handoff.json` — what is mock-proven vs real-unproven (the `mock_proven_vs_real_unproven` block); the honest-failure list.
6. SKIM `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/api.py` + `pyproject.toml` (`[project.scripts]` if present) so the example commands you write match the ACTUAL public function + CLI name. NOTE: T5 (CLI) may still be in progress when you run — if the exact CLI flags are not yet final, write the runbook against the documented CLI contract in `docs/bundle-protocol.md` (read it if it exists) and the README, and clearly mark any command the operator must confirm against `ask-chatgpt --help`.

## Your single problem (author the runbook)

`docs/runbooks/real-site-acceptance.md` must contain, for a consenting operator on their OWN profile:

- **A top CONSENT + SAFETY preamble:** this runbook drives the operator's REAL chatgpt.com session on their own browser profile, consumes their quota, and is NEVER executed by automation or by any test. Explicit typed-consent gate before any step (e.g. the operator must type a consent token). The tool never reads/stores/logs credentials, cookies, tokens, or profile contents. Loopback mock is for automation; this is the human half.
- **A PREREQUISITE section:** real-site acceptance requires `selector_maps/real.json` to be FILLED via `docs/runbooks/observe-chatgpt-unknowns.md` first (else the real channel correctly fails closed with `SelectorUnavailableError`). State how the operator confirms real.json is populated.
- **Per use case (UC1, UC2, UC3): an acceptance procedure** with:
  - 1-2 concrete commands the operator runs (with an inline typed-consent prompt before the command actually contacts the site);
  - the **expected observations** (what a PASS looks like — e.g. UC1 returns the assistant's text for a known prompt; UC2 round-trip: a bundle is sent, GPT returns a patch bundle, applying it locally reproduces the expected edit + the diff matches; UC3 the CLI prints the response / writes `--out`);
  - **honest-failure interpretations** — for each documented failure mode (login required, session not found, upload/download unsupported, patch malformed, hash/byte-count mismatch, oversized payload, path-escape attempt, response truncated) what the operator will SEE and what it means / what to do. Map each to the named error the tool raises.
  - Note the D-001 empirical-revisit triggers the operator should watch for (e.g. real-site DOM extraction materially flakier than copy-button -> report it; download affordance present/absent -> determines whether bundle retrieval uses download-capture or the fenced fallback on the real site).
- **An explicit "NEVER automated" banner** repeated near the run steps: no CI, no test, no script runs this; it is operator-hands-on-keyboard only.

Be honest about what is UNPROVEN: every real-site behavior is an operator-observed unknown until this runbook is executed. Do not assert real-site behavior as fact; frame as "expected, to be confirmed."

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). YOU are authoring a doc — do NOT contact the network and do NOT run the real channel; the runbook is for the operator to execute later, by hand.
- PATCH APPLY SAFETY: validate the ENTIRE bundle (manifest, hashes, byte counts, path safety) BEFORE mutating ANY file; reject absolute paths, `..` traversal, and symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); the CLI never mutates local files without an explicit apply flag. (Reflect this in the UC2/UC3 apply steps — the operator applies only to an explicit root, with an explicit apply flag.)
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real". (The runbook must reinforce this to the operator.)
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS (if you run anything). Serialize pytest runs in this tree. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report with `T6-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED in `T6-report.md`)
- FIRST content line: `ESTIMATE: T6 <minutes>m`.
- `date -Iseconds` at START and END -> literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- Report: the runbook's section outline, which existing docs you anchored to, any command you marked "confirm against --help" (because T5 may be mid-flight), trust notes (no network, no credential reads).
- LAST line: `T6-STATUS: DONE|BLOCKED`.
