# T5 — IMPLEMENT the `ask-chatgpt` CLI (UC3): console script wrapping the public function ONLY + UC3 acceptance + `scripts/accept_uc3.sh`. TDD. SINGLE EDITOR.

You are an INDEPENDENT pi worker and the ONLY editor of this repo right now. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). M-002 (UC1) + M-003 T2 (bundle-out) + T3 (patch retrieve/validate/apply) + T4 (public API wiring `ask_chatgpt(files=...)` + `apply_patch` + UC2 round-trip) are DONE/committed. `docs/bundle-protocol.md` is the BINDING spec.

**Your slice: the `ask-chatgpt` CLI per §11 — a THIN wrapper over the public library functions. LIBRARY-FIRST: the CLI must contain NO logic the library lacks; it only parses args, calls the public functions, formats output, and sets exit codes. NO local file mutation without an explicit `--apply` flag.**

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be all-green, ZERO failures (now includes T2+T3+T4 tests + the UC2 round-trip). If not, STOP and report BLOCKED with exact output — do not edit.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/docs/bundle-protocol.md` — BINDING. Implement **§11 (CLI)** EXACTLY: the `[project.scripts]` entry, the full flag table (prompt/positional, `--session`, `--model-settings`, `--files`/`--dirs`, `--out`, `--apply`/`--dry-run`, `--root`, plus whatever §11 specifies), stdout/stderr/exit-code conventions, and the **no-mutation-without-explicit-`--apply`** rule. Re-read **§10** for the exact public functions you wrap (`ask_chatgpt(...)`, `apply_patch(...)`, the result/`DiffSummary` types) — do not reach past the public surface.
3. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/__init__.py` + `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/api.py` — the PUBLIC surface you wrap. Use ONLY exported names. If you find yourself needing logic the library doesn't expose, STOP and report it (do not implement library logic in the CLI).
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` — the named errors; map each to a distinct nonzero exit code + an actionable, credential-free stderr message per §11.
5. `/home/abhmul/dev/ask-chatgpt/pyproject.toml` — add the `[project.scripts]` entry per §11 (e.g. `ask-chatgpt = "ask_chatgpt.cli:main"`); confirm the build backend picks up the new module. Do NOT add dependencies (use stdlib `argparse`).
6. `/home/abhmul/dev/ask-chatgpt/scripts/accept_uc1.sh` + `/home/abhmul/dev/ask-chatgpt/scripts/accept_uc2.sh` (T4) — the MODEL for `accept_uc3.sh` (ephemeral port; raw artifacts to `tmp/accept-uc3-<ts>/`; nonzero exit on failure). Mirror their structure.
7. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` + `/home/abhmul/dev/ask-chatgpt/tests/conftest.py` — how the mock is booted on an ephemeral loopback port so the CLI (run as a subprocess) can target it. The CLI must accept the mock base_url / channel via the same configuration the library uses (do not hardcode chatgpt.com; tests use the loopback mock).

## Scope
1. **`src/ask_chatgpt/cli.py`** with a `main(argv=None) -> int` entry point using stdlib `argparse` (zero new deps). Implement §11's flags exactly. Behavior:
   - Default (prompt + optional `--session`/`--model-settings`): call `ask_chatgpt(...)`, write the response text to stdout (or `--out FILE`). stdout carries ONLY the response by default (pipe-friendly).
   - With `--files`/`--dirs`: bundle-out round-trip via the public API; on a returned patch bundle, default behavior MUST NOT mutate local files — print the diff summary (dry-run semantics) unless `--apply` is given.
   - `--dry-run`: compute + print the `DiffSummary`, write nothing. `--apply`: apply the retrieved patch bundle to `--root` (REQUIRED with `--apply`; if absent, error — never guess a root). `--apply` and `--dry-run` are mutually exclusive.
   - Exit codes: 0 success; distinct nonzero codes per named-error class (document the mapping in §11/your report); errors go to stderr with actionable, credential-free messages.
   - The CLI sets `channel` appropriately; for tests it must be pointable at the loopback mock (NEVER chatgpt.com). Do not read/store/log credentials/profile.
2. **`[project.scripts]`** entry in `pyproject.toml` per §11.
3. **TDD tests — `tests/test_cli.py`** (write FIRST). Two layers:
   - In-process: call `main([...])` with argv lists; assert stdout/exit-code/no-mutation-by-default/`--dry-run` writes nothing/`--apply` requires `--root`/mutually-exclusive flags/named-error→exit-code mapping. Drive the loopback mock.
   - Subprocess (UC3 acceptance flavor): run the installed/console entry (or `python -m ask_chatgpt.cli` via `uv run`) as a subprocess against the booted mock; assert the response prints to stdout / `--out` writes the file; assert exit codes.
4. **`scripts/accept_uc3.sh` + `scripts/accept_uc3.py`** (mirror accept_uc1/uc2): boot the mock on an EPHEMERAL port, exercise the CLI as a subprocess (a prompt→text call, an `--out` call, and a `--files … --dry-run` call showing a diff summary without mutation), write raw artifacts to `tmp/accept-uc3-<ts>/` (incl. `results.json` with `overall` + per-step outcomes), and EXIT NONZERO on any failure.
5. Full `uv run pytest -q` GREEN (all existing + new). Bound waits.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). ZERO new pip deps (stdlib `argparse` only).
- PATCH APPLY SAFETY: the CLI NEVER mutates local files without an explicit `--apply` flag; `--apply` requires an explicit `--root`; `--dry-run` writes nothing; apply goes through the library's validated `apply_patch` (validate-everything-before-mutate, zip-slip-safe, never `extract`/`extractall`); in tests, apply targets `tmp/` ONLY.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real". Every test/script targets the loopback mock base_url.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- Python: `uv run <cmd>` from repo root ONLY; NEVER bare `python`/`pip`. `uv sync --all-groups` ALWAYS (re-sync after editing pyproject so the console script registers). Serialize pytest. Kill only processes your own run started. NEVER `git push`. Do NOT `git commit` (the manager commits). Do not break existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.
- End your report with `T5-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-003/T5-report.md`, ≤200 lines)
- FIRST content line: `ESTIMATE: T5 <minutes>m`.
- `date -Iseconds` at START and END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- Report: `cli.py` flag table as implemented + the named-error→exit-code mapping; proof the CLI is a thin wrapper (which public functions it calls; that it adds no library logic); how the no-mutate-default + `--apply`/`--root`/`--dry-run` rules are enforced; the `[project.scripts]` line; the EXACT `uv run pytest -q` summary; the `bash scripts/accept_uc3.sh` outcome + the `tmp/accept-uc3-<ts>/` path; deviations; trust notes (loopback-only, no credential/profile reads, zero new deps).
- LAST line: `T5-STATUS: DONE` (or `BLOCKED` + exact error + next action).

## Success criteria (all must hold)
- `ask-chatgpt` console script (`[project.scripts]`) wraps the public function ONLY (no library logic in the CLI); §11 flags implemented; stdout pipe-friendly; named-error→exit-code mapping.
- No-mutation default proven: `--files` without `--apply` writes nothing; `--dry-run` writes nothing; `--apply` requires `--root`; `--apply`/`--dry-run` mutually exclusive.
- `tests/test_cli.py` green (in-process + subprocess); `scripts/accept_uc3.{sh,py}` exits 0 on success / nonzero on failure with raw artifacts in `tmp/accept-uc3-<ts>/`.
- Full `uv run pytest -q` green; zero new deps; no credential/profile reads; no chatgpt.com contact.
- Report with telemetry + `T5-STATUS:` last. You did NOT git commit.
