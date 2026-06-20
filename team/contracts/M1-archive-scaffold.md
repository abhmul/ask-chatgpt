# Mission M1 — Archive the v1 library + scaffold a clean fresh Python package

You are a **pi WORKER** for the `ask-chatgpt-dev` team. Execute this mission exactly. You inherit nothing but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`. You are on git branch `rewrite-v2`.

## Mission
`ask-chatgpt` (a Python CLI that drives chatgpt.com via a CDP-attached Chromium) is being rewritten from scratch. Your job is ONLY: (1) archive the existing v1 library + its tests into `archive/lib-v1/`, and (2) lay down a clean, minimal, GREEN scaffold for the new package. Do NOT implement features. Do NOT pre-build the detailed modules. Keep it minimal and non-hacky. The full target spec is `docs/REWRITE-SPEC.md` — read it for context; its §2 has the eventual module layout, but the DETAILED design is a LATER mission (M3), so do NOT build it now.

## Current tree state (already prepared for you — trust but verify)
- You are on branch `rewrite-v2`; clean working tree (only `human/` is untracked — leave it).
- The pre-rewrite uncommitted WIP of `src/ask_chatgpt/driver.py` is ALREADY safely preserved in a git stash (`git stash list` shows an entry "v1 M-011b driver.py WIP (pre-rewrite, preserved)"). Do NOT stash anything; do NOT pop/apply/drop any stash; do NOT try to preserve `driver.py` again — it is done.
- `src/ask_chatgpt/` and `tests/` currently hold the v1 code at HEAD.

## HARD SAFETY CONSTRAINTS (verbatim — violating any is a critical failure)
- A separate copy of this tool is INSTALLED via `uv tool install` from git branch `stable`, in its own frozen venv, and ANOTHER AGENT IS USING IT RIGHT NOW. Your edits on `rewrite-v2` CANNOT affect it — keep it that way:
  - NEVER check out, commit to, merge into, or move the `stable` branch.
  - NEVER run `uv tool install`, `uv tool upgrade`, or `… --reinstall`.
  - `uv run …` and `uv sync` use the PROJECT venv (`.venv`) and are SAFE — use them. Do NOT use the shared `~/.local/share/agent-python/.venv`; this repo has its own project venv.
- NEVER `git push`; never merge to any published branch. Local commits to `rewrite-v2` only.
- Stay on `rewrite-v2`. FIRST run `git branch --show-current`; if it is not `rewrite-v2`, STOP and report BLOCKED (do not switch branches yourself).
- Do NOT touch `human/`, `archive/orchestration-v1/`, or any git stash.
- Avoid `rm -rf` / recursive force-removes (a guard may block them). Use `git mv` for moves; you won't need recursive deletes.

## Steps
1. `git branch --show-current` → must be `rewrite-v2` (else STOP → BLOCKED).
2. Inspect: `ls -R src/ask_chatgpt tests`. (A prior attempt was reverted; if a stale `archive/lib-v1/` dir exists, clear only its non-tracked `__pycache__` with plain non-recursive `rm archive/lib-v1/ask_chatgpt/__pycache__/*.pyc` + `rmdir`, then proceed. Report what you found/did.)
3. Archive v1 with history preserved using `git mv`: move `src/ask_chatgpt` → `archive/lib-v1/ask_chatgpt`, and `tests` → `archive/lib-v1/tests`. The v1 tests test the old API and are archived as REFERENCE (M4 writes fresh tests; the v1 mock fixtures under `tests/fixtures/` are valuable reference). Do NOT touch `archive/orchestration-v1/`.
4. Scaffold a fresh minimal `src/ask_chatgpt/`:
   - `__init__.py` with a `__version__` string and a one-line docstring naming the v2 rewrite.
   - `cli.py` with `main(argv=None) -> int` that handles `--help`/`--version`, and for any other verb prints a clear, actionable "not yet implemented (rewrite in progress; see docs/REWRITE-SPEC.md)" to stderr and returns a nonzero code — so the console entry point resolves and runs cleanly.
   - Do NOT scaffold the detailed modules (session.py, capture.py, store.py, …) — a clean minimal package only.
5. Ensure `pyproject.toml`'s console-script entry resolves to the new `ask_chatgpt.cli:main`; run `uv sync` if needed (project venv).
6. Scaffold a fresh `tests/` with a FALSIFIABLE smoke test (`tests/test_smoke.py`) that genuinely exercises the package: assert it imports, `__version__` is a non-empty `str`, and `main(["--version"])` / `main(["--help"])` behave as intended. NOT `assert True`.
7. Verify: run `uv run pytest` and INSPECT the full output (do not trust the exit code alone). Confirm the smoke test was collected, ran, and passed. Fix until green (or report PARTIAL/BLOCKED with the exact failure). Capture the output for your handoff.
8. Commit to `rewrite-v2` (NOT push). Stage ONLY the files you changed (the `git mv` moves + new scaffold + tests + any `pyproject.toml` change) — do NOT `git add -A` blindly. Imperative message; end the body with exactly:
   `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
9. Write a handoff to `team/evidence/handoffs/M1-archive-scaffold.md`: (1) **Status** `DONE`/`PARTIAL`/`BLOCKED` on line 1; (2) **What was verified** — exact commands run + the actual `uv run pytest` output lines + `git log --oneline -1` + confirmation the driver.py WIP stash is untouched (`git stash list`); (3) **Artifacts produced** with paths + trust level; (4) **Blockers**; (5) **Recommended next**; (6) **Complexity / paradigm signals**.

## Acceptance bar
`uv run pytest` is GREEN with ≥1 falsifiable smoke test that genuinely exercises the new package; the v1 library + tests are archived under `archive/lib-v1/` with history preserved; the `ask-chatgpt` console entry point resolves to the new package; everything committed to `rewrite-v2`; nothing pushed; `stable` untouched; no `uv tool` commands run; the driver.py WIP stash untouched. Report honestly — if you could not meet the bar, say `PARTIAL`/`BLOCKED` with specifics. Never overclaim.
