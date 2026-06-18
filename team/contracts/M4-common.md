# M4 COMMON PREAMBLE — read this IN FULL before doing anything

You are a worker on the `ask-chatgpt-dev` team, dispatched by the M4 (offline core) Claude-Opus manager. **You inherit nothing** but this file, your per-task contract, and the files they name. Everything you must honor is written here explicitly — there is no hidden context.

Repo: `/home/abhmul/dev/ask-chatgpt`. Branch: **`rewrite-v2`** (already checked out; do not change branches).

## What ask-chatgpt is
A Python tool for programmatic interaction with chatgpt.com via a CDP-attached, operator-signed-in Chromium (Playwright). We are **rewriting the library from scratch** in Python. **Mission M4 = the OFFLINE CORE only**, test-driven against a `mock` channel. **No real chatgpt.com / CDP / browser legs in M4 at all.**

## Authoritative sources (READ the parts your task needs, IN FULL — they are ground truth)
- **`team/evidence/reports/M3-detailed-design.md`** — the AUTHORITATIVE, verified detailed design. Implement to it exactly. Your per-task contract names the sections you must read. Key sections: §2 module signatures, §3 JSONL schema/layout/linearization, §4 capture pipeline, §5 completion, §6 send, §8 CLI verbs, §9 error taxonomy, §10 (M4 steps 1–6 = the build plan + per-step acceptance).
- **`team/contracts/M4-offline-core.md`** — the mission contract (scope, lead decisions, acceptance bar).
- **`team/evidence/reports/M4-test-plan.md`** — the synthesized falsifiable-behavior checklist (your TDD target). Read it if it exists.
- **`docs/REWRITE-SPEC.md`** — higher-level spec (the four gotcha fixes; safety §13). Consult as needed.
- A claim being in prose does NOT make it true. The M3 design + the actual code/tests are ground truth; reconcile to them.

## Lead decisions (APPLY THESE; they resolve the design's open questions for M4)
- **Pending eager-write stub: ACCEPT** `message_id = "local:<client_send_id>"` for the pre-submission stub (hidden/superseded in default reads); do NOT use a separate outbox file.
- **Clipboard fallback: fail-closed by default** — on backend failure with no faithful fallback, stop with `HumanActionNeededError`/code `HUMAN-ACTION-NEEDED`; never auto-read the clipboard. In M4 this is only the *mock-tested* fallback chain; real clipboard is M5+.
- **Projects: identity parsing for BOTH URL shapes is IN M4 scope** (`/c/<id>` and `/g/g-p-<projid>/c/<chatid>`). Project *send/create* is M7 (out of M4).
- All other open questions (completion-status vocab, `stream_status`, attachment byte routes, send-rate defaults, memory budget, multi-part join, profile verification) → implement the design's **conservative offline defaults**; do NOT guess live values.

## SAFETY INVARIANTS (verbatim, non-negotiable — violating any is a mission failure)
1. Work ONLY on `rewrite-v2`. **NEVER** check out, commit to, merge into, fast-forward, or otherwise move the **`stable`** branch.
2. **NEVER** run `uv tool install` / `uv tool upgrade` / `uv tool ... --reinstall` (these rebuild the operator's separately-installed running tool that ANOTHER agent is using right now). Use **`uv run …` / `uv sync`** (the project `.venv`) only.
3. **NEVER** `git push` and never merge to a published branch.
4. **OFFLINE ONLY.** No chatgpt.com / openai / CDP / browser in M4. Production CDP code must import Playwright **lazily** (only inside the cdp channel), so the offline test suite never imports Playwright or launches a browser, and **never** runs `playwright install`.
5. **Stage ONLY the explicit paths you changed** (your contract names them — e.g. `git add src/ask_chatgpt tests pyproject.toml`). **NEVER** `git add -A`, `git add .`, or `git add <repo-root>`. Before committing, run `git status --porcelain` and confirm ONLY your intended files are staged. If `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, or `human/` ever appear, DO NOT stage them — another agent / the team-lead owns those.
6. Do not touch `human/`, `archive/`, the git stashes, or `docs/` (read-only). `team/` is manager-owned: write ONLY the single deliverable file your contract names (if any).
7. Another agent may be editing reference files in this working tree concurrently — touch ONLY the files your contract names.
8. Never use `git checkout` / `git stash` / `git branch` / `git reset --hard` / `git rebase` / `git merge` / `git push`. A destructive-action guard hook may block these (it substring-matches commit messages too — keep messages plain; avoid the words checkout/reset/stash/force). If any git command is blocked by a hook, STOP, report it in your handoff, and do not try to work around it.

## Python / venv
- ALWAYS use `uv run` (e.g. `uv run pytest`, `uv run python -c '...'`). **Never** call bare `python`/`pytest` — the shell has `VIRTUAL_ENV` pointing at a shared agent-python venv you must NOT use; `uv run` correctly targets the project `.venv` (you will see a harmless "VIRTUAL_ENV ... does not match" warning — ignore it).
- `uv run`/`uv sync` may install PyPI deps into the project `.venv` — that is allowed and offline-compatible (only chatgpt.com/openai network is forbidden, not PyPI).
- Acceptance command for the whole suite: **`uv run pytest`** (the `real_site` marker is deselected by default; default runs never touch the network).

## TDD discipline (rigid — follow exactly)
- **Vertical slices, never horizontal.** ONE test → minimal impl to green → next test. Do NOT write all tests first then all code. Each test responds to what the last cycle taught you.
- Tests verify **behavior through public interfaces**, not implementation details — they should survive an internal refactor.
- **Tests must be FALSIFIABLE.** A test that cannot fail proves nothing. For every behavior, ensure a plausible WRONG implementation would make the test RED. While doing TDD you must actually observe RED before GREEN for each new behavior (a green-on-first-write test is suspect — make it fail first, e.g. by stubbing the impl to return the wrong thing, then implement). Avoid circular/self-answering tests (a test that feeds the expected answer in and reads it back proves nothing).
- Refactor only while GREEN. Never refactor while RED.
- Verdict = **inspected artifacts, not exit codes.** When you claim the suite passes, paste the actual `uv run pytest` summary line (counts).

## Reporting (every worker)
Write your deliverable/handoff to the EXACT path your contract names. If it is a handoff, put a single-token **STATUS: DONE | PARTIAL | BLOCKED** on line 1, then: what you verified (paste the real `uv run pytest` summary + counts; show that new tests are falsifiable — e.g. note the RED you saw or a one-line mutation that flips them), the commit hash + `git log -1 --oneline`, the exact files you changed (`git show --stat HEAD`), any blockers (with the precise action needed), and recommended next steps. Never claim "green" without the pasted summary. Never report elapsed time from your own sense of it — it is not trusted.

## Anti-over-engineering
Prefer the simplest correct design that satisfies the M3 contract and the test-plan. `loop`, full `menus.py`, `TabPool`, and `AdaptiveSendBudget` are OUT of M4 except as **minimal stubs** needed by falsifiable core tests. Do not build M5/M7 features.

## MANAGER DECISIONS — resolved ambiguities (apply EXACTLY; these are authoritative for M4)
These resolve the open questions the test plan (`team/evidence/reports/M4-test-plan.md`) raised. Where the M3 design defers a *live* value, M4 uses the conservative offline default below.

1. **Project id normalization.** `ConversationRef.project_id` stores the token **without** the `g-p-` literal (the `<project_id>` capture in M3 §2.8's `/g/g-p-<project_id>/c/<conversation_id>`). `parse_project_address` returns that same bare token. `conversation_url(ref)` reconstructs `https://chatgpt.com/g/g-p-<project_id>/c/<conversation_id>` when `project_id` is set, else `/c/<conversation_id>`. Require round-trip: `conversation_url(parse_conversation_address(u)) == u` for both URL shapes (with a canonical trailing-slash/query/fragment-stripped form).
2. **Prompt normalization** (one public function, used by BOTH composer-fill verification and submitted-user comparison): strip leading/trailing whitespace and normalize line endings CRLF/CR → `\n`. Do NOT collapse internal whitespace. Tests must assert against **literal expected strings** (adversarial trailing-newline / CRLF / leading-space cases), never call the normalizer as its own oracle.
3. **Markdown render.** `render_markdown(transcript)` = visible turns in order, each as `## User`/`## Assistant`, a blank line, then the **literal** `content_markdown`, turns separated by exactly one blank line; output ends with exactly one `\n`. No timestamps, no "rendered at", no re-escaping, no attachment/citation inlining. CLI `ask` stdout is the assistant's **raw `content_markdown`** + exactly one trailing newline (NOT the role-header render). `scrape`/`history`/`export` use `render_markdown`.
4. **Empty visible parts.** A visible `user:text`/`assistant:text` whose `content.parts == []` → `content_markdown=""` (valid empty string, not an error). Non-list parts, or any non-string element, → fail closed (`BackendCaptureShapeError`). Include a fixture pinning both.
5. **DR/Pro classification.** No numeric threshold. Classify `kind="deep_research"` only on the **conjunction**: same `turn_exchange_id` + ≥1 hidden reasoning/tool/code node in the group + citation/search metadata present + a visible final `assistant:text`. Any missing element → `kind="normal"`. Keep fixtures far from any boundary.
6. **Attachment `download_state`.** All M4-normalized `AttachmentRef`s default to `download_state="pending"`, `local_path=None`, `sha256=None`; `bytes` only from metadata when present else `None`. M4 NEVER fetches bytes. Tests require: no fetch attempted, `local_path is None`, `sha256 is None`, state != `"downloaded"`.
7. **Torn-line interface.** One tolerated torn TRAILING line → emit a `warnings.warn(...)` of a dedicated `StoreWarning(UserWarning)` and load the prior valid records. Mid-file invalid JSON, or >1 trailing invalid line → raise `StoreError`. Tests use `pytest.warns(StoreWarning)` / `pytest.raises(StoreError)`.
8. **Backend cadence.** Cheap DOM progress polls at `progress_poll_interval_s`; backend checks at `backend_check_interval_s`. When `backend_check_interval_s is None`, the MockChannel supplies a sparse default strictly greater than the DOM interval (real default deferred to M5). Cadence tests use EXPLICIT intervals (e.g. progress=2s, backend=30s) under a fake clock; one separate test asserts `None` does NOT collapse to the DOM cadence.
9. **`StatusReport`** uses the EXACT M3 §2.1 field names: `ok, cdp, signed_in, login_or_challenge, selector_valid, conversations, blocking_code, details`. `present` per selector is `null` when not safely checked.
10. **`--project` flag.** `create` accepts `--project` (forwarded to `Session.create(project=...)`). M4 `ask` does **NOT** expose `--project` (project send is M7) — do not add a dangling no-op flag; defer it.
11. **Timeout split (confirmed).** No-progress activity window elapsed → `CompletionTimeoutError` (code 50) WITH partial salvage persisted. Explicit `max_total_wait_s` cap elapsed → `MaxTotalWaitExceededError` (code 51). `max_total_wait_s=None` = unbounded; a hidden 600s ceiling MUST make the long-progress test fail.
12. **Validation entry points (test via PUBLIC behavior, not private constructors).** Invalid selector map → `load_selector_map(name_or_path, *, strict=True)` (or `Session(strict_selectors=True)` construction) raises `SelectorNotFoundError`. Invariant violations on a turn (`partial` inconsistent with `status`; `local:` id on a non-pending/complete record; pending stub with a numeric `turn_index`) → construction/persistence of that record raises (prefer dataclass `__post_init__` validation), surfaced as a `StoreError`/`ValueError` at the public boundary. Tests assert the observable failure, not the mechanism.
