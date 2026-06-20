# T1 — Scaffold the uv project + socket-guard conftest + REAL chromium-vs-loopback smoke

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and the files it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). This is the FIRST leg of MISSION-002 — a clean slate (no pyproject/src/tests yet).

## Read these files FIRST (in order)
1. `/home/abhmul/dev/ask-chatgpt/README.md` — product spec (package is `ask_chatgpt`, library-first, Python uv).
2. This contract in full.

## Scope (do EXACTLY this; no more)
Create a `uv`-managed Python project, `src/` layout, package `ask_chatgpt`, with a dev dependency group, an autouse network (socket) guard, and a REAL Playwright headless-chromium smoke test that loads a loopback page. Leave `uv run pytest` GREEN.

### Deliverables (exact paths)
1. `pyproject.toml` — project name `ask-chatgpt`, package `ask_chatgpt` under `src/` (`[tool.hatchling]`/`[tool.setuptools]` or `uv`'s default `src` layout — use a `[build-system]` that works with `uv`). Requires Python >=3.11. A **dependency group `dev`** (use `[dependency-groups]` per PEP 735, which `uv` supports) containing `pytest` and `playwright`. No runtime deps yet beyond what you need; `playwright` may be a runtime dep (the browser layer needs it) — put `playwright` as a normal project dependency and `pytest` in the `dev` group.
2. `src/ask_chatgpt/__init__.py` — `__version__ = "0.0.1"` and a module docstring naming the product. Nothing else yet.
3. `tests/__init__.py` (empty) and `tests/conftest.py` — an **autouse, session-or-function-scoped network guard**: monkeypatch `socket.socket.connect`/`connect_ex` (and `socket.create_connection`) so any TCP connect to a NON-loopback address raises `RuntimeError("NETWORK BLOCKED: <addr>")`. ALLOW `127.0.0.1`, `::1`, `localhost`, and AF_UNIX sockets (Playwright/chromium talk to the fixture and to their own pipes over loopback/unix — these MUST still work). Provide a way for tests to assert the guard is active. Keep it ~40 lines, well-commented. (T7 later extends this with Playwright route interception + a deliberate-violation demo test — leave room; do not implement those now.)
4. `tests/test_smoke.py` with TWO tests:
   - `test_import_package`: imports `ask_chatgpt`, asserts `__version__`.
   - `test_playwright_chromium_loopback`: starts a trivial stdlib `http.server` bound to `127.0.0.1` port `0` (EPHEMERAL — read back the assigned port), serving one tiny HTML page containing a unique marker string; launches Playwright **chromium headless** using the ALREADY-CACHED browser; navigates to the loopback URL; asserts the marker is in the page. Tear down browser + server cleanly. This proves chromium launches and loopback binding works end-to-end. Use the sync or async Playwright API — your choice; keep it minimal and robust.

### Build / verify steps
- `uv sync --all-groups` (ALWAYS `--all-groups`; bare `uv sync` drops non-default groups → phantom ModuleNotFoundError). ESTIMATE: this may take 1–3 min on first sync — state your estimate before running; if >2 min expected, that's fine, just note it.
- Chromium is **ALREADY CACHED** at `~/.cache/ms-playwright/chromium-1223` and `chromium_headless_shell-1223`. Do **NOT** run `playwright install` / download anything. Verify the cache dir exists (`ls ~/.cache/ms-playwright`). If Playwright cannot find/launch the browser, FIRST try `uv run playwright install --help` to confirm wiring, but do NOT download; if launch fails for missing **system libraries** (e.g. libnss3), STOP and report BLOCKED with the exact error (do not sudo/apt/install).
- Run `uv run pytest -q` from repo root. Paste the FULL summary line(s) into your report. Both smoke tests MUST pass.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL work NEVER contact chatgpt.com/openai or any external network service. Any HTTP server you start binds **127.0.0.1 only**, on **EPHEMERAL** ports (bind port 0, read back the assigned port — never assume a fixed port is free; the operator runs long-lived daemons).
- The ONLY ever-permitted external download is Playwright chromium — and it is ALREADY CACHED, so you download NOTHING. Report BLOCKED on missing system libs; never sudo/apt/install.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents anywhere (code, tests, logs, reports).
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY (never its `archive/` or `human/` dirs). Never write `.claude/` or `.agents/`.
- Python: use `uv run <cmd>` from `/home/abhmul/dev/ask-chatgpt` ONLY (this repo's own uv venv). NEVER bare `python`/`pip`. NEVER touch the shared agent venv `~/.local/share/agent-python/.venv`.
- You are the ONLY editor right now — do not spawn parallel pytest. Kill only processes your own run started. NEVER `git push`. Do NOT `git commit` (the manager commits verified slices).
- ESTIMATE BEFORE EXECUTE: state expected wall-clock + output volume before any command expected to exceed ~2 min.

## Telemetry v2 (REQUIRED — write into your report `orchestration/reports/M-002/T1-report.md`)
- Run `date -Iseconds` at START and END; write literal `START_TIMESTAMP: <iso>` and `END_TIMESTAMP: <iso>` lines.
- Emit `ESTIMATE: T1 <min>m` (your own honest estimate).
- Report length cap ~200 lines. Include: what you created (paths), the exact `uv run pytest -q` summary output, any deviations, and trust notes.
- End your report with `T1-STATUS: DONE` (or `BLOCKED` with the exact blocking error + the precise next action) as the LAST line.

## Success criteria (all must hold)
- `pyproject.toml`, `src/ask_chatgpt/__init__.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_smoke.py` all exist at the exact paths.
- `uv sync --all-groups` succeeds; `uv run pytest -q` is GREEN with BOTH smoke tests passing (the real chromium-vs-loopback test included).
- The socket guard is autouse and provably blocks non-loopback (note in report how you confirmed it does not break the loopback Playwright test).
- Report written with telemetry lines and `T1-STATUS:` last.
