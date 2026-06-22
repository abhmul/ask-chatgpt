# Common contract — backlog verification round (M11/M12/M13), team `ask-chatgpt-dev`

> You are a **Round-1 verification/analysis MANAGER** (Opus, `claude -p`, single-shot) for the team `ask-chatgpt-dev`, working in repo `/home/abhmul/dev/ask-chatgpt`. Your mission file (M11/M12/M13) points you here: **read this file IN FULL first**, then your mission file. You decompose your mission into **pi worker(s)**, **block them to completion in this one turn**, synthesize their findings, and write ONE handoff. **This round is READ-ONLY: you MUST NOT edit any source file, MUST NOT commit, MUST NOT git push.** The only writes you make are (a) your handoff under `team/evidence/handoffs/`, and (b) pi run dirs under `.pi-workers/`.

## Why this is read-only
The operator asked us to first *verify* current state from ground truth and produce exact fix specs; the actual fixes are a later, separate, serialized round gated on operator review. Mutating now would (a) race the other parallel managers' audits of the same tree and (b) pre-empt an operator scope decision. So: **audit and specify; do not change code.**

## Ground-truth & environment (verify, don't trust)
- Repo root: `/home/abhmul/dev/ask-chatgpt`. Current git branch: `fix/m10-light-read-scrape`. Its working-tree CONTENT equals merged `main` (PR #2 was merged post-M10), so auditing the current tree == auditing `main`. Audit the **current working tree**.
- **Re-derive every claim from ground truth — including every claim in your mission contract.** File:line pointers I give you are convenience pointers and may be stale; open the file and confirm. A claim being in your contract does NOT make it true (agent-rigor).
- Python execution, if any: use `uv run …` (this resolves the PROJECT venv `.venv` = the new code). **NEVER** invoke the bare installed `ask-chatgpt` (that is an isolated `uv tool` copy built from the `stable` ref, which a *different* agent is using — do not disturb it). **NEVER** run `uv tool install/upgrade/reinstall`. **NEVER** move or commit the git ref `stable` (currently `bbbe027`).
- This is **static code analysis** — no browser, no CDP, no network to chatgpt.com/openai. Do **not** run any real-site/CDP command, do **not** `curl :9222`, do **not** open a browser.
- Do **not** touch, read into your handoff, or mention the contents of `issues/cdp-send-repro/controller.mjs` or `human/` (pre-existing, unrelated, out of scope; `human/` is off-limits per AGENTS.md).

## Safety (transcribe the relevant ones into every pi worker prompt — children inherit nothing)
- Never print, log, or persist: auth tokens, `Authorization`/OAI header VALUES, cookies, conversation content, file ids, or attachment bytes. Header NAMES (e.g. `x-openai-target-path`) and request PATHS/methods are fine to discuss.
- Never commit anything. Never `git add`/`git commit`/`git push`/`git checkout`/`git stash` in this round. (If you find yourself wanting to, you've left read-only scope — stop and report instead.)
- The acceptance command for this team is `uv run pytest`, but **do not run it in this read-only round** — your verdict comes from *inspecting code and test files*, not from exit codes. If you need to know what a test asserts, READ the test file.

## Dispatch policy (HARD RULES)
- **WORKERS → pi**, launched ONLY via:
  `bash .claude/skills/manager/references/launchers/parent-claude/pi-watch.sh [opts] "<prompt>"`
- **NEVER** use the Claude `Agent`/`Task` tool to spawn workers. NEVER spawn sub-managers for this round (the work is leaf-sized).
- pi-watch.sh: run dir = `$PWD/.pi-workers/<run_id>`; `<run_dir>/status` holds the worker's exit code once finished; `<run_dir>/output.log` is the worker console. `--tools` sets the pi tool allowlist; **use `--tools read,grep,find,ls,bash`** (NO `edit`/`write`) to enforce read-only on source — the worker reports findings via its stdout (captured in `output.log`).
- **You are single-shot (`claude -p`): you will NOT be re-invoked. You MUST block every worker to completion within THIS turn.** Two valid patterns:
  - **Block one at a time:** `pi-watch.sh --wait-seconds 1800 --poll-seconds 15 --tools read,grep,find,ls,bash "<prompt>"` returns only when the worker writes `status` (or 1800 s elapse).
  - **Parallel then poll:** launch each with `--wait-seconds 0` (returns immediately, worker runs detached), capture each run dir, then loop in bash polling every `status` file until all exist (you may `sleep` in your own bash), then read each `output.log`.
- **Verify shipment, not liveness:** confirm each worker's `status` exists AND read its `output.log` for the actual findings. A `--wait-seconds` elapse without a `status` file is NOT completion. Never trust a worker's self-reported "it passed"; re-derive from the inspected evidence.
- Best-of-N: for genuinely multi-faceted analysis use N parallel read-only lenses + your own synthesis (you are the synthesizer). For a concrete "is X present in the code?" audit, a single careful worker + your own independent re-derivation from ground truth is sufficient.

## Handoff (write exactly one, then report)
Write `team/evidence/handoffs/<MISSION-ID>.md` with, in order:
1. **Status:** single token `DONE` / `PARTIAL` / `BLOCKED` at the very top.
2. **Verdict:** the mission's required verdict token(s) (see your mission file).
3. **What was verified** — exact files + `file:line`, what each pi worker did, commands run.
4. **Artifacts + trust level** (verified-independently / producer-only / unverified).
5. **Blockers** (exact action needed), if any.
6. **Recommended next mission(s)** — for an UNRESOLVED issue, the **exact Round-2 fix spec**: which file(s)/function(s) change, the precise change, and the **falsifiable test** to add (what it asserts, how it fails pre-fix). Note file-conflict/parallelism with the other backlog fixes.
7. **Complexity / paradigm-shift signals.**

Your FINAL stdout message MUST contain: the single-token Status, the Verdict token(s), and the handoff path — so the lead can smoke-check without parsing your whole log.
