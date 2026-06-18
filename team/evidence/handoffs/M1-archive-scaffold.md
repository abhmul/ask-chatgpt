DONE

## What was verified

Exact commands run: `git branch --show-current`; `ls -R src/ask_chatgpt tests` plus a non-mutating `archive/lib-v1` existence check; `git stash list`; `mkdir -p archive/lib-v1`; `git mv src/ask_chatgpt archive/lib-v1/ask_chatgpt`; `git mv tests archive/lib-v1/tests`; scaffold file writes for `src/ask_chatgpt/__init__.py`, `src/ask_chatgpt/cli.py`, and `tests/test_smoke.py`; `uv sync`; `uv run ask-chatgpt --version`; `uv run pytest`; explicit `git add` of changed scaffold paths only, with `git mv` entries already staged; `git commit -m "Archive v1 library and scaffold v2 package"`; `git log --oneline -1`; `git stash list`.

Branch check: `git branch --show-current` returned `rewrite-v2`.

Inspection result: `ls -R src/ask_chatgpt tests` showed the v1 library and v1 tests at mission start. `archive/lib-v1` did not exist, so no stale `__pycache__` cleanup was needed.

Console entry check: `pyproject.toml` already had `ask-chatgpt = "ask_chatgpt.cli:main"`; no `pyproject.toml` change was required. `uv run ask-chatgpt --version` printed `0.0.1`.

`uv run pytest` output inspected in full:

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/abhmul/dev/ask-chatgpt
configfile: pyproject.toml
testpaths: tests
collected 4 items

tests/test_smoke.py ....                                                 [100%]

============================== 4 passed in 0.01s ===============================
```

`git log --oneline -1`:

```text
b875521 Archive v1 library and scaffold v2 package
```

`git stash list` after the commit, confirming the preserved driver.py WIP stash is still present and untouched:

```text
stash@{0}: On rewrite-v2: interrupted M1 worker staged renames
stash@{1}: On rewrite-v2: v1 M-011b driver.py WIP (pre-rewrite, preserved)
stash@{2}: WIP on main: bb50a35 Operator pause (trip): graceful stop of M-006; pause record + resume prompt
```

## Artifacts produced

- `archive/lib-v1/ask_chatgpt/` — archived v1 library reference. Trust level: high; moved with `git mv`, except files replaced at the same live paths appear as archive adds plus live-path modifications in Git's single-commit summary.
- `archive/lib-v1/tests/` — archived v1 tests and fixtures reference. Trust level: high; moved with `git mv`, with the same single-commit caveat for `tests/test_smoke.py`.
- `src/ask_chatgpt/__init__.py` — minimal v2 rewrite package scaffold with non-empty `__version__`. Trust level: high; covered by smoke test.
- `src/ask_chatgpt/cli.py` — minimal v2 CLI entry point supporting `--help`, `-h`, `--version`, and actionable nonzero not-yet-implemented errors. Trust level: high; covered by smoke test and console script check.
- `tests/test_smoke.py` — falsifiable smoke tests for package import/version, help/version CLI behavior, and unimplemented-command error behavior. Trust level: high; collected and passed under `uv run pytest`.
- Local commit `b875521` on `rewrite-v2` — product commit. Trust level: high; no push performed.
- `team/evidence/handoffs/M1-archive-scaffold.md` — this handoff. Trust level: high; written after the product commit as required by the contract.

## Blockers

None for M1 acceptance. Pre-existing/unrelated working tree entries remain outside the product commit: untracked `human/`, untracked `team/contracts/`, and an unstaged `team/state/live-state.json` manager-state update. This handoff is also untracked because it was written after the product commit step. No stash was changed.

## Recommended next

Proceed to M2 attended ground-truth probe against the live site per `docs/REWRITE-SPEC.md` §16. Leave `archive/lib-v1/` as reference only; do not port feature code until the M3 detailed design and M4 implementation missions.

## Complexity / paradigm signals

This is intentionally a minimal green scaffold, not a partial implementation. The design paradigm remains library-core plus thin CLI with CDP-attached browser operations deferred; detailed modules such as `session.py`, `capture.py`, and `store.py` were deliberately not scaffolded in M1. The smoke suite is falsifiable and offline-only, preserving a clean substrate for M4 tests.
