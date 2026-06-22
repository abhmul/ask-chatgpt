# Common contract — issues-backlog triage round (M14), team `ask-chatgpt-dev`

> You are a **READ-ONLY triage/analysis MANAGER** (Opus, `claude -p`, single-shot) for the team `ask-chatgpt-dev`, working in repo `/home/abhmul/dev/ask-chatgpt` on branch `main`. Your mission file (M14) points you here: **read this file IN FULL first**, then your mission file. You decompose your mission into **pi worker(s)**, **block them to completion in this one turn**, synthesize their findings, and write ONE handoff. **This round is READ-ONLY: you MUST NOT edit/move/delete any file in the repo (no source, no issue files), MUST NOT `git mv`/`git add`/`git commit`/`git push`/`git checkout`/`git stash`/`git branch`.** The only writes you make are (a) your handoff under `team/evidence/handoffs/M14-triage-issues.md`, and (b) pi run dirs under `.pi-workers/`. The actual archival (moving issue files) is the LEAD's job and happens AFTER you report — your job is to produce an independently-verified verdict + archive recommendation.

## Why this is read-only
The operator asked the team to *go through the issues backlog, determine which are actually relevant, and archive the complete / no-longer-relevant ones*. Your mission is the **judgement half**: classify each issue from ground truth and recommend the exact archive set with evidence. The LEAD executes the reversible file moves + git packaging afterward (and resolves any flagged judgement calls with the operator). Mutating now would (a) risk colliding with the working tree and (b) pre-empt the lead's packaging + an operator decision on borderline issues. So: **audit and recommend; do not change the tree.**

## Ground-truth & environment (verify, don't trust)
- Repo root: `/home/abhmul/dev/ask-chatgpt`. Current git branch: `main`, HEAD `837f7aa` (= `origin/main` = the `stable` ref = the 0.2.1 release; all of PR #1 rewrite / PR #2 M10 / PR #3 backlog M11-M13 / PR #4 release are MERGED). **Auditing the current working tree == auditing released `main`.** Audit the **current working tree**.
- **Re-derive every claim from ground truth — including every claim in your mission contract and in any RESUME/handoff/issue-file prose.** `file:line` pointers and prior "FIXED/RESOLVED/VERIFIED" stamps are CONVENIENCE CLAIMS that may be stale or wrong; open the file, read the code, read the test, check `git log` and CONFIRM. A claim being written somewhere does NOT make it true (agent-rigor). Treat every "this is resolved" as a hypothesis to be **adversarially falsified**, not confirmed.
- Python execution, if any: use `uv run …` (resolves the PROJECT venv `.venv` = the released code). Running `uv run pytest <path>` is non-mutating and ALLOWED as corroboration, but your verdict must rest on **inspected code + test + git evidence**, never on a green exit alone. **NEVER** invoke the bare installed `ask-chatgpt` (an isolated `uv tool` copy built from the `stable` ref that a *different* agent uses — do not disturb it). **NEVER** run `uv tool install/upgrade/reinstall`. **NEVER** move or commit the git ref `stable` (currently `837f7aa`).
- This is **static code analysis** — no browser, no CDP, no network to chatgpt.com/openai. Do **not** run any real-site/CDP command, do **not** `curl :9222`, do **not** open a browser.
- Do **not** touch, read into your handoff, or quote the contents of `issues/cdp-send-repro/controller.mjs` or `human/` (pre-existing, unrelated, out of scope; `human/` is off-limits per AGENTS.md). `issues/cdp-send-repro/` is a CDP send REFERENCE harness, **not** one of the 8 backlog issues to triage — leave it out of the triage set.
- A separate `claude` tmux session unrelated to this team may be running; ignore it. Your pi workers live under `.pi-workers/`; your own run dir is under `.managers/m14/`.

## Safety (transcribe the relevant ones into every pi worker prompt — children inherit nothing)
- Never print, log, or persist: auth tokens, `Authorization`/OAI header VALUES, cookies, conversation content, file ids, or attachment bytes. Header NAMES (e.g. `x-openai-target-path`) and request PATHS/methods are fine to discuss.
- Never mutate the repo. Never `git add`/`commit`/`push`/`checkout`/`stash`/`mv`/`branch`/`rm`. (If you find yourself wanting to, you've left read-only scope — stop and report instead.)
- The team acceptance command is `uv run pytest`; a targeted `uv run pytest <node>` is fine for corroboration, but do not rely on exit codes — READ the test to see what it asserts and whether it actually pins the fix (a test that can't fail proves nothing — falsifiability).

## Dispatch policy (HARD RULES)
- **WORKERS → pi**, launched ONLY via:
  `bash .claude/skills/manager/references/launchers/parent-claude/pi-watch.sh [opts] "<prompt>"`
- **NEVER** use the Claude `Agent`/`Task` tool to spawn workers. Do **not** spawn sub-managers (the work is leaf-sized).
- Worker tools: **`--tools read,grep,find,ls,bash`** (NO `edit`/`write` — read-only enforcement). Workers report findings via stdout (captured in `<run_dir>/output.log`).
- pi-watch.sh: run dir = `$PWD/.pi-workers/<run_id>`; `<run_dir>/status` holds the worker's exit code once finished; `<run_dir>/output.log` is the worker console.
- **You are single-shot (`claude -p`): you will NOT be re-invoked. You MUST block every worker to completion within THIS turn. NO background monitor. NO yield. NO dispatch-and-exit.** Two valid patterns:
  - **Block one at a time:** `pi-watch.sh --wait-seconds 1800 --poll-seconds 15 --tools read,grep,find,ls,bash "<prompt>"` returns only when the worker writes `status` (or 1800 s elapse — if it elapses without a `status` file, re-`--watch` the run dir; do NOT treat elapse as completion).
  - **Parallel then poll:** launch each with `--wait-seconds 0` (returns immediately, worker runs detached), capture each run dir, then loop in your own bash polling every `status` file until all exist, then read each `output.log`.
- **Verify shipment, not liveness:** confirm each worker's `status` exists AND read its `output.log` for the actual findings. Never trust a worker's self-reported "it passed / it's resolved"; re-derive from the inspected evidence yourself before accepting a verdict.
- **Independent verification is mandatory.** The worker that PRODUCES the verdict table must not be the only voice. A SEPARATE worker (distinct prompt/lens) must adversarially re-derive every **ARCHIVE** candidate (try to prove the bug is still live in current `main`). You (manager) are the synthesizer/adjudicator over both.

## Handoff (write exactly one, then report)
Write `team/evidence/handoffs/M14-triage-issues.md` with, in order:
1. **Status:** single token `DONE` / `PARTIAL` / `BLOCKED` at the very top.
2. **Verdict table:** one row per issue — `issue-filename` → verdict `RESOLVED|OBSOLETE|STILL-RELEVANT|JUDGEMENT-CALL` → recommendation `ARCHIVE|KEEP|LEAD-DECIDE` → the single strongest piece of ground-truth evidence (commit / `file:line` / test name) → adversarial-verification result (could the bug be reproduced in current `main`? yes/no/n-a).
3. **The exact ARCHIVE list** (filenames only) and the exact **KEEP list**, plus any **LEAD-DECIDE** items with both readings stated.
4. **What was verified** — exact files + `file:line`, what each pi worker did, commands run, per-issue evidence in full.
5. **Artifacts + trust level** (verified-independently / producer-only / unverified).
6. **Blockers** (exact action needed), if any.
7. **Complexity / paradigm-shift signals.**

Your FINAL stdout message MUST contain: the single-token Status, the ARCHIVE list, the KEEP list, any LEAD-DECIDE items, and the handoff path — so the lead can smoke-check without parsing your whole log.
