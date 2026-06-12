# T2 — Build-landmine fix + errors module + session registry (pure Python, TDD)

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1 (scaffold) is DONE: `pyproject.toml`, `src/ask_chatgpt/__init__.py`, `tests/conftest.py` (autouse socket guard), `tests/test_smoke.py` (import + real chromium-vs-loopback) all exist and pass.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/pyproject.toml` — you will edit it (greenlet fix below).
3. `/home/abhmul/dev/ask-chatgpt/README.md` §Specification (use case 1: `session_identifier` names a persistent chat session; continuity across calls) — informs the registry.
4. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` D-001 — for the named-error posture (fail-closed, actionable messages).

## STEP 0 — Confirm you inherit a GREEN tree
Run `uv sync --all-groups` then `uv run pytest -q`. It MUST be green (2 passed) before you change anything. If not, STOP and report BLOCKED with the output.

## STEP 1 — BUILD-LANDMINE FIX (do this BEFORE writing new code; commit-blocking)
T1 left `pyproject.toml` referencing a `greenlet` wheel under `tmp/` (which is **gitignored** → not reproducible on a fresh checkout). Remove ALL THREE greenlet-specific blocks from `pyproject.toml`:
- `[tool.uv.sources]` (the `greenlet = { path = "tmp/wheels/..." }` entry),
- the `greenlet==...` line under `[tool.uv].constraint-dependencies` (remove the whole `[tool.uv]` table if greenlet was its only content),
- the `[[tool.uv.dependency-metadata]]` block for greenlet.

Then make the build reproducible WITHOUT any reference into `tmp/`:
- **PREFERRED:** run `uv sync --all-groups` allowing uv's default index (PyPI). Resolving `greenlet` (a declared transitive dependency of `playwright` — the browser layer) from PyPI is normal ONE-TIME project setup, explicitly sanctioned by README ("zero-dependency bias **beyond what the browser layer needs**"). It is NOT a test contacting an external service and NOT chatgpt.com/openai. uv.lock will pin exact versions → reproducible.
- **FALLBACK (only if uv genuinely cannot reach PyPI / network-blocked):** create an IN-REPO committed dir `vendor/wheels/`, move the greenlet wheel there from `tmp/wheels/`, and set `[tool.uv.sources].greenlet = { path = "vendor/wheels/<wheel-filename>" }`. This is offline AND reproducible (committed, not gitignored).

Acceptance for STEP 1: `grep -n "tmp/" pyproject.toml` returns NOTHING; `uv run pytest -q` still green (the chromium smoke still passes); state in your report which path (PyPI or vendor) you used and why.

## STEP 2 — Errors module (`src/ask_chatgpt/errors.py`)
Pure Python, no imports beyond stdlib. Define a base exception and the named error types the whole package will raise. Each must carry an **actionable** default message (what happened + what the operator should do), and accept an optional detail string. EXACT class names (downstream legs import these — do not rename):
- `AskChatGPTError(Exception)` — base for all package errors.
- `LoginRequiredError(AskChatGPTError)` — ChatGPT profile not logged in; operator must sign in (tool never reads/stores credentials).
- `SessionNotFoundError(AskChatGPTError)` — a stored conversation ref/URL no longer resolves to a reachable conversation.
- `ModelUnavailableError(AskChatGPTError)` — requested model/option not offered by the UI.
- `ResponseTruncatedError(AskChatGPTError)` — assistant turn incomplete / end-marker missing / payload truncated.
- `SelectorUnavailableError(AskChatGPTError)` — a required selector-map key is missing/stale; fail closed (NEVER guess/broaden).
- `UploadUnsupportedError(AskChatGPTError)` — upload affordance absent/rejected.
- `DownloadUnsupportedError(AskChatGPTError)` — download affordance absent.
Design notes: give the base an `__init__(self, detail: str | None = None)` that composes `default_message` (a class attribute) with the optional detail. Keep messages free of any credential/cookie/profile content. ~60–90 lines.

## STEP 3 — Session registry (`src/ask_chatgpt/session_registry.py`)
Maps `session_identifier -> conversation reference/URL` so the same identifier returns to the same conversation (README UC1 continuity). Pure Python, JSON-backed, **store path overridable for tests**. No network.
- A small dataclass `ConversationRef` with at least: `conversation_ref: str` (stable ref/id) and `url: str | None` (optional conversation URL), plus optional `model_settings: dict | None` last used. JSON-serializable.
- Class `SessionRegistry`:
  - `__init__(self, store_path: pathlib.Path | str | None = None)` — if `store_path` is None, default to an env-overridable location: read `ASK_CHATGPT_STATE_DIR` if set else `~/.local/state/ask-chatgpt/`, file `sessions.json`. Tests pass an explicit `store_path` (e.g. `tmp_path/sessions.json`). Create parent dirs lazily on write.
  - `get(self, session_identifier: str) -> ConversationRef | None` — returns None for unknown identifier (caller decides to create a NEW session; do NOT raise here — `SessionNotFoundError` is for the driver layer when a stored ref fails to reopen).
  - `set(self, session_identifier: str, ref: ConversationRef) -> None` — upsert; persist atomically (write to a temp file in the same dir, then `os.replace`).
  - `list(self) -> dict[str, ConversationRef]` and `delete(self, session_identifier: str) -> bool`.
  - Load is tolerant: missing file → empty registry; corrupt JSON → raise `AskChatGPTError` with an actionable message (don't crash with a bare JSONDecodeError).
- ~110–150 lines.

## STEP 4 — Tests (TDD: write tests first, watch them fail, then implement)
- `tests/test_errors.py`: each error subclasses `AskChatGPTError`; each has a non-empty actionable default message; detail composes into the message; no message leaks anything credential-like (trivial assertion that messages are static strings you wrote).
- `tests/test_session_registry.py`: round-trip set→get with an explicit `tmp_path` store; persistence across a fresh `SessionRegistry(store_path=...)` instance (reads back what a prior instance wrote); unknown id → None; delete; list; atomic write leaves no partial file on simulated failure (optional); corrupt JSON → `AskChatGPTError`. Use pytest's `tmp_path` so NOTHING writes outside the repo/test area and the default user-state dir is never touched.
- Run `uv run pytest -q`. ALL tests (old smoke + new) green.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL work NEVER contact chatgpt.com/openai or any external network service. Any HTTP server binds 127.0.0.1 only on EPHEMERAL ports (bind 0). (This leg starts no servers.)
- The ONLY ever-permitted external download is Playwright chromium — ALREADY CACHED. The greenlet PyPI resolution in STEP 1 is one-time package SETUP (sanctioned by README), not a test/runtime network call; if PyPI is unreachable use the in-repo vendor fallback. Download nothing else. Never sudo/apt/install system packages.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents anywhere.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`. Do not write to `~/.local/state/` from tests (use tmp_path).
- Python: `uv run <cmd>` from repo root ONLY (this repo's own uv venv). NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Kill only processes you started. NEVER `git push`. Do NOT `git commit` (the manager commits verified slices).
- ESTIMATE BEFORE EXECUTE: state expected wall-clock + output volume before any command expected to exceed ~2 min.

## Telemetry v2 (REQUIRED — write report to `orchestration/reports/M-002/T2-report.md`)
- Run `date -Iseconds` at START and END; write literal `START_TIMESTAMP:` and `END_TIMESTAMP:` lines.
- Emit `ESTIMATE: T2 <min>m` (your own estimate).
- Report ≤200 lines: list files created/edited (paths), STEP 1 fix path used + `grep tmp/ pyproject.toml` result, the exact `uv run pytest -q` summary, error class names, registry API, deviations, trust notes.
- End with `T2-STATUS: DONE` (or `BLOCKED` + exact error + next action) as the LAST line.

## Success criteria (all must hold)
- `pyproject.toml` has NO reference into `tmp/`; build reproducible; `uv run pytest -q` GREEN.
- `src/ask_chatgpt/errors.py` defines exactly the 8 named classes above with actionable messages.
- `src/ask_chatgpt/session_registry.py` provides `ConversationRef` + `SessionRegistry` with overridable store path, JSON persistence, atomic write, tolerant load.
- `tests/test_errors.py` + `tests/test_session_registry.py` exist and pass; tests use `tmp_path` (never the real user-state dir).
- Report written with telemetry lines and `T2-STATUS:` last.
