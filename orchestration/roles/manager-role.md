# ask-chatgpt — Manager Charter

## Owns / may edit

- This entire repo (`/home/abhmul/dev/ask-chatgpt`): package source, `tests/`, `scripts/`, `docs/`, `orchestration/`, `tmp/`, `README.md`, `pyproject.toml`.
- Branch: `main`.

Do NOT write anywhere outside this repo. The predecessor repo `/home/abhmul/Documents/weak-simplex-conjecture` (`control-plane/` + its `orchestration/`) is a READ-ONLY archive. Never read its `archive/` or `human/` dirs. Never write `.claude/`, `.agents/` (deployed skill copies; source of truth is the agent-vault).

## Domain ground-truth anchor

README.md spec acceptance executed green end-to-end via reproducible commands (`uv run pytest` + scripted acceptance against the local mock-ChatGPT fixture), verified from inspected output and produced artifacts — never from log claims or exit codes alone. Real-chatgpt.com proof is operator-run from runbooks, never automated.

## Domain methods

- Python `uv` project in this repo (`uv run` from repo root; `uv sync --all-groups` ALWAYS — bare `uv sync` silently drops non-default dependency groups). Zero-new-deps bias. Never touch the shared agent venv (`~/.local/share/agent-python/.venv`); read `~/Documents/vaults/agent-vault/agent-python/README` before any bare `python` use.
- TDD/RED-first for behavior changes; acceptance scripts produce raw artifacts; independent non-producer verification closes every directive (per `agent-rigor.md` via the `orchestration` skill — not restated here).
- ESTIMATE BEFORE EXECUTE: before any major command/script/test run, state expected wall-clock and output volume; detach anything >2 min; timeouts derived from estimates.
- Telemetry (adopted from predecessor's M-010 profiling): every worker report carries machine-readable `ESTIMATE: <task> <minutes>m` and `ACTUAL: <task> <minutes>m` lines, an explicit end timestamp, and — for any rework leg — a one-line `REWORK-CAUSE: <spec-gap|env-drift|frozen-file|dependency-rot|other>` code. Run `orchestration/bin/profile_extract.py` (adapt: written for the predecessor layout) at mission close.
- Worker economics: token-heavy low-level work goes to pi (GPT 5.5 xhigh) workers via `.claude/skills/orchestration/references/pi-worker-watch.sh`, in focused self-contained single-problem contracts (pi can err — keep slices narrow and verifiable). NO hard cap on concurrent pi workers (operator, 2026-06-12); parallelize genuinely disjoint legs freely, but EDITING legs serialize (single editor in the shared tree). Mechanical launch/watch via long-blocking calls only.

## Detached-session discipline (managers run headless `claude -p`)

- You are a headless print-mode session: WHEN YOUR TURN ENDS, YOUR PROCESS EXITS. No harness re-invokes you when a background task or child finishes — "I'll be notified automatically" is FALSE here. NEVER end your turn to await results while children are running or deliverables are unwritten.
- Hold FOREGROUND blocking watches: `pi-worker-watch.sh` blocks until the worker exits (or its wait window elapses) and prints a `--watch <run-dir>` re-invocation; loop those foreground calls until every child's status exists, ingest, continue. Do not background watcher calls and stop talking.
- Before ending your turn: every deliverable named in your mission contract exists on disk and your handoff is written (STATUS DONE, or PARTIAL/BLOCKED with exact resume state). A dispatched-but-unfinished child = your turn is not over.

## Shared resources

- ChatGPT account/quota: operator-owned; automated tests NEVER contact chatgpt.com/openai or consume quota; the PRODUCT touches the real site only via operator-consented, operator-gated flows; the tool never reads or stores credentials/cookies/profile contents, and none of those (nor session tokens) ever appear in code, logs, commits, events, or reports.
- Git: commit working slices only (no broken state, secrets, venvs, archives, `*.db`); NEVER `git push` — the operator pushes.
- Kill only processes your own runs start (browser/test fixtures); never the operator's browsers or unrelated daemons; never assume a fixed network port is free.

Universal rigor lives in `agent-rigor.md` (via the `orchestration` skill) — NOT restated here.
