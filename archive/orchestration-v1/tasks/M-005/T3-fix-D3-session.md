# T3 — Fix D3: exercise the CLI `--session` flag by test + acceptance (single editor)

You are a fresh worker. You inherit NOTHING except this file and the files it tells you to read. Everything you need is below.

## The defect (re-verify before editing)

`src/ask_chatgpt/cli.py:102` defines `--session ID` and `cli.py:63` passes `session_identifier=args.session` into `ask_chatgpt(...)`, but NO test and NO acceptance script ever invokes `--session`. The underlying continuity (same `session_identifier` reuses one conversation) IS proven at the LIBRARY level in `tests/test_ask_chatgpt_uc1.py`, but never through the public CLI. Your job: prove `--session` continuity THROUGH THE CLI, with a test AND an acceptance step.

## CRITICAL mechanism you MUST understand (re-verify in the code)

- The CLI has NO `--registry` flag. When `ask_chatgpt()` is called without a `registry`, it builds a default `SessionRegistry()` (`src/ask_chatgpt/api.py:51,110`).
- `SessionRegistry._resolve_store_path` (`src/ask_chatgpt/session_registry.py:65-70`) resolves the on-disk store as: explicit `store_path` -> else `$ASK_CHATGPT_STATE_DIR/sessions.json` -> else `~/.local/state/ask-chatgpt/sessions.json`.
- Therefore, to make `--session S` reuse ONE conversation across TWO separate CLI invocations, BOTH invocations must share the SAME registry file. You MUST isolate this to a tmp dir by setting the env var `ASK_CHATGPT_STATE_DIR` to a temp directory for BOTH invocations. DO NOT let it fall through to `~/.local/state/...` — that writes OUTSIDE the repo (forbidden) and is non-deterministic.
- The mock fixture: pytest fixture `mock_chatgpt` is in `tests/conftest.py:68`; the server class is `tests/fixtures/mock_chatgpt/server.py` (`MockChatGPTServer`, `make_handle()`, `inspect()`). `inspect()` returns a snapshot shaped like:
  `{"conversations": {"<ref>": {"turns": [{"role": "user"|"assistant", "text": "..."}, ...]}, ...}, ...}`.
  Helper to read a conversation's user prompts (copy this pattern; see `tests/test_ask_chatgpt_uc1.py:11-16,64-68`):
  ```python
  def _user_texts(snapshot, ref):
      return [t["text"] for t in snapshot["conversations"][ref]["turns"] if t["role"] == "user"]
  ```
- The autouse session-scoped socket guard `_network_guard` in `tests/conftest.py:26` allows loopback/unix only. Do NOT disable it. The mock runs on loopback `127.0.0.1`.

## Part A — CLI test (read `tests/test_cli.py` first and MATCH its style/fixtures)

Add a test (in `tests/test_cli.py`) named e.g. `test_main_session_reuses_same_conversation_through_cli`. It must:
1. `monkeypatch.setenv("ASK_CHATGPT_STATE_DIR", str(tmp_path / "state"))` (use pytest `tmp_path` + `monkeypatch` fixtures) so the default registry persists to an ISOLATED tmp file across both `cli.main` calls.
2. `mock_chatgpt.reset()`; script the first response (`mock_chatgpt.script_next_response("first answer")`).
3. `code1 = cli.main(["--channel","mock","--base-url",mock_chatgpt.base_url,"--timeout","5","--session","sess-A","first prompt"])`; assert `code1 == 0` and captured stdout == "first answer", stderr == "".
4. Script the second response; `code2 = cli.main([... "--session","sess-A","second prompt"])`; assert `code2 == 0` and stdout == "second answer".
5. NON-VACUOUS continuity assertion via `mock_chatgpt.inspect()`: there must be EXACTLY ONE conversation, and its user turns must equal `["first prompt","second prompt"]` (this proves the second CLI call reused the first conversation, not created a new one). Use the `_user_texts` helper above.
6. (Recommended, strengthens non-vacuity) a contrasting call with a DIFFERENT `--session sess-B` (after scripting another response) creates a SECOND conversation — assert `len(conversations) == 2` and `sess-B`'s conversation holds only its own prompt. This shows the proof is sensitive to the session id, not always-one-conversation.

## Part B — acceptance step in `scripts/accept_uc3.py` (read it first)

Add a new step (registered via `_run_step(out_dir, steps, "session-continuity", session_continuity)`, placed alongside the existing three step registrations near line 256-258) that proves the SAME thing through the installed CLI subprocess (`uv run ask-chatgpt`):
1. Create an isolated state dir, e.g. `state_dir = out_dir / "session-state"`. Both subprocess invocations MUST run with env `ASK_CHATGPT_STATE_DIR=<state_dir>`. The existing `_run_cli` helper (line 83) calls `subprocess.run(command, cwd=ROOT, ...)` with NO env, so EXTEND `_run_cli` to accept an optional `env: dict | None = None` and pass `env=({**os.environ, **env} if env else None)` to `subprocess.run`; then call it with `env={"ASK_CHATGPT_STATE_DIR": str(state_dir)}` for this step. (`os` is already imported.)
2. `handle.reset()`; script first response; `_run_cli(out_dir, "session-first", ["--channel","mock","--base-url",handle.base_url,"--timeout","5","--session","accept-uc3-sess","accept UC3 session prompt one"], env=...)`; assert returncode 0 and stdout == scripted first response, no stderr.
3. Script second response; `_run_cli(out_dir, "session-second", [... "--session","accept-uc3-sess","accept UC3 session prompt two"], env=...)`; assert returncode 0 and stdout == scripted second response.
4. NON-VACUOUS: `snapshot = handle.inspect()`; assert exactly ONE conversation whose user turns == `["accept UC3 session prompt one","accept UC3 session prompt two"]`. Return this evidence in the step `data` (e.g. `{"detail": "...", "conversation_ref": ref, "user_turns": [...], "subprocess_first": run1, "subprocess_second": run2}`) so it is recorded in `results.json` and the per-step json.
5. Confirm `scripts/accept_uc3.sh` still drives `accept_uc3.py` and that the new step lands in `results.json` with `overall == "pass"`. (The `.sh` is a thin wrapper; you likely need no change to it, but VERIFY by running it.)

## Run + prove (capture all of this in your report)

- `uv sync --all-groups`, then `uv run pytest` (ALL tests, serialized) -> MUST be fully green; paste the summary line + exit code (expect one more test than before).
- Run the UC3 acceptance and capture the new step: `bash scripts/accept_uc3.sh` (or `uv run python scripts/accept_uc3.py --out tmp/accept_uc3_T3`) -> open the produced `results.json`, confirm `overall=pass` AND a `session-continuity` step with `status:pass`; paste the session step's recorded `user_turns` evidence.

## Constraints / SAFETY (transcribed verbatim — obey exactly)

- Automated tests + ALL mission work NEVER contact chatgpt.com/openai or any external network service; loopback/local only. The mock is loopback `127.0.0.1`. Keep the autouse socket guard active.
- Registry isolation is MANDATORY: use `ASK_CHATGPT_STATE_DIR` -> a tmp path for the test and for the acceptance step. NEVER write the registry to `~/.local/state` or anywhere outside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Do NOT write `.claude/` or `.agents/`. Do NOT touch the shared agent venv; use `uv run`/`uv sync` from the repo root.
- `uv sync --all-groups` ALWAYS before `uv run`. Serialize pytest. Ephemeral ports. Kill only your own processes. NEVER `git push`. ESTIMATE BEFORE EXECUTE.

## Commit

Commit the new CLI test + the `scripts/accept_uc3.py` change (and `accept_uc3.sh` only if you changed it) with a message starting `M-005: ` (e.g. `M-005: fix D3 — exercise CLI --session via test + accept_uc3 continuity step`). Commit ONLY those files. Do NOT commit `tmp/` artifacts. Report the commit SHA.

## Telemetry + report (write to `orchestration/reports/M-005/T3.md`, cap ~200 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T3 <minutes>m`.
- Body: the new CLI test (or its key assertions), full-suite green summary + exit code, the acceptance `results.json` session-continuity evidence (`overall=pass`, the step's `user_turns`), and the commit SHA.
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T3-STATUS: DONE` (or `T3-STATUS: BLOCKED` with the exact blocker).
