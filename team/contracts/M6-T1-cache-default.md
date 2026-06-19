# M6-T1 — Make repo `cache/` the default data-dir + cement cache semantics (OFFLINE, TDD)

You are a **pi worker** for the `ask-chatgpt-dev` team, mission M6 task T1. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit **nothing** but this contract and the files it names — read what it points you to. **First load and obey the `tdd` skill** and the rigor file `.claude/skills/manager/references/agent-rigor.md` (read it). This is an **OFFLINE** task: **do NOT touch the browser, the network beyond PyPI/uv, git, or chatgpt.com.**

## Goal
The operator decided scraped conversations live in a **repo-local, gitignored `cache/` folder that acts as a cache**. Make `cache/` the **DEFAULT data-dir**, and prove (with falsifiable tests) the cache semantics:
- `scrape` populates the cache (already true via `capture_conversation`).
- `history` / `export` read from the cache **without any browser/CDP/network and without re-scraping** (already true in code — you ADD the falsifiable tests + the new default).
- Re-scrape **refreshes** (append-only + last-writer-wins read is already idempotent).
- CLI `--data-dir` and env `ASK_CHATGPT_DATA_DIR` still **override** the default (unchanged priority).

## Exact change point (verify against ground truth before editing)
`src/ask_chatgpt/store.py`, method `Store.resolve_data_dir()` (around lines 48–54). It currently is:
```python
def resolve_data_dir(self) -> Path:
    if self._explicit_data_dir is not None:
        return self._explicit_data_dir
    env_dir = self._env.get("ASK_CHATGPT_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / ".local" / "state" / "ask-chatgpt"   # <-- CHANGE ONLY THIS FALLBACK
```
Keep the priority order **`--data-dir` (explicit) > `ASK_CHATGPT_DATA_DIR` > default**. Change ONLY the final fallback to the **repo-local `cache/`**.

### Required default-resolution behavior (cleanest correct implementation)
Resolve the default to the repo's `cache/` so it lands in the **already-gitignored** location regardless of invocation directory:
- **Recommended:** walk up from `Path.cwd()` looking for a repo-root marker (`pyproject.toml`); if found, default = `<that dir>/cache`. If no marker is found walking up, fall back to `Path.cwd() / "cache"`. (CWD-relative `cache/` is an acceptable simpler alternative ONLY if you are confident it still lands in the gitignored repo cache for the normal `uv run` invocation from repo root — prefer the repo-root-anchored form for determinism.)
- Do **not** create the directory inside `resolve_data_dir()` (it stays pure resolution; `ensure_conversation`/index writes create dirs as today).
- `.gitignore` already contains `cache/` (line 15) — do **not** modify `.gitignore`. Confirm `git check-ignore cache` would match, but do NOT run git.

## TDD — vertical slices (one test → impl → next), behaviors that MUST be falsifiable
Write tests that **can fail** (a test that cannot fail proves nothing). Suggested behaviors (use the public interface — `Store` / `Session(channel="mock")` / `cli.main`):
1. **Default is the repo cache, not the home dir.** `Store().resolve_data_dir()` ends in `cache` and equals the repo-root `cache` (NOT `~/.local/state/ask-chatgpt`). Make this a **pure resolution** assertion (no writes). This test would FAIL on the old code (proves the change).
2. **Overrides still win.** Explicit `data_dir=X` → `X`; `ASK_CHATGPT_DATA_DIR=Y` (and no explicit) → `Y`. (env path unchanged.)
3. **history/export read from cache with NO browser.** Populate a temp cache (write a transcript via `Store(data_dir=tmp)` append, or scrape over `MockChannel`), then call `Session(channel="cdp", data_dir=tmp).history(<id>)` (or `cli.main(["history", <id>, "--data-dir", tmp])`) and assert it returns the transcript **without ever attaching/ preflighting**. Make it falsifiable: e.g. assert that constructing the session and calling history does not invoke any channel method — a way to prove "no browser" is to use `channel="cdp"` with NO real endpoint and confirm history still succeeds (it must not call preflight/attach). `export` behaves identically.
4. **Re-scrape refreshes (idempotent).** Over `MockChannel`, scrape the same conversation twice (or upsert a corrected record) and assert reads are last-writer-wins / no duplication explosion.

You may add a focused new test module (e.g. `tests/test_cache_default.py`) and/or extend existing store/cli tests.

## MANDATORY: fix the test that encodes the OLD default
`tests/test_store_layout.py` (around lines 32–35) constructs `Store()` with no data-dir and asserts the **old** `~/.local/state/ask-chatgpt` home default (`from_home`). **Update it** to assert the new repo-`cache/` default. Keep its `from_env` (`ASK_CHATGPT_DATA_DIR`) assertion — that path is unchanged. Read the whole file first and adjust precisely.

## MANDATORY: no test may pollute the repo cache
After your change, a no-arg `Store()` / default `Session()` resolves to `<repo>/cache`. Audit the suite so that **no test writes into the real repo `cache/`**: tests that actually create files must pass `data_dir=tmp_path` or set `ASK_CHATGPT_DATA_DIR`/`monkeypatch.chdir(tmp)`. The default-resolution test (#1) must be pure (no `ensure_conversation`/write). After running the suite, confirm **no new `cache/` directory or files appeared at the repo root** (use `ls`/`find`, NOT git). If the suite created repo `cache/` content, fix the offending test(s) to isolate.

## Acceptance (re-derive from ground truth — do NOT trust your own claim)
- `uv run pytest` is **fully green** (must remain ≥ the 205 baseline plus your new tests). Run it and paste the exact summary line. NOTE: a harmless warning `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv does not match ... will be ignored` is expected — `uv run` uses the project `.venv`; ignore it.
- The default-data-dir change is the **only** behavioral change; overrides unchanged.
- No `cache/` content created at repo root by the test run.
- You did NOT touch git, the browser, the network (beyond uv/PyPI), `stable`, or run any `uv tool` command.

## Safety / isolation (HARD RULES — obey exactly)
- **OFFLINE only.** No browser, no CDP, no chatgpt.com, no `curl`, no Playwright. (`uv run`/`uv sync` for deps is fine; PyPI is allowed.)
- **Do NOT commit / stage / push.** Leave your edits in the working tree; the manager reviews & commits. Do **not** run `git add`, `git commit`, `git push`, `git checkout`, `git stash`, or any branch op.
- **Never** move/commit/merge/checkout the `stable` branch. **Never** run `uv tool install/upgrade/reinstall`. Use `uv run`/`uv sync` only.
- Edit ONLY: `src/ask_chatgpt/store.py` and test files under `tests/`. Do not edit `.gitignore`, `cli.py`, `session.py`, or any other module unless strictly required to keep the suite green (if you must, justify it in your report). Do NOT touch `archive/`, `human/`, `issues/`, `team/state/`.
- No secrets, no network egress to chatgpt.com/openai.

## Report (write your handoff here)
Write `team/evidence/reports/M6-T1-cache-default.md` containing, in order:
1. **STATUS:** `DONE` / `PARTIAL` / `BLOCKED` (single token near top).
2. **Exact files changed** (paths) and a 1-line summary of each change; the new default-resolution rule you implemented.
3. **Tests added/changed** and, for each, the **behavior** it pins and **how it can fail** (falsifiability).
4. **Acceptance evidence:** the exact `uv run pytest` summary line (e.g. `N passed in ...s`); confirmation that no repo `cache/` content was created by the run (the `ls`/`find` you used + result).
5. **Anything you had to touch beyond store.py/tests** and why.
6. **Blockers** (if any) with the exact action needed.
Do NOT print conversation content or any secret. Keep the report factual and concise.
