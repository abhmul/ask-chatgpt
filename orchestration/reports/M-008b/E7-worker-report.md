# E7 worker report

STATUS: PASS — added the attach-only `download-discovery` probe code and offline-validated it; the real probe was not run.

Reused builder/prompt:
- `src/ask_chatgpt/bundle.py:199` — `build_bundle(...)` for the outgoing zip bundle.
- `src/ask_chatgpt/bundle.py:165` — M-008a rewritten `_PROMPT_INSTRUCTIONS_TEMPLATE`.
- `src/ask_chatgpt/bundle.py:272` — `generate_prompt_instructions(...)` public prompt builder.

Subcommand behavior:
- `scripts/m008b_real_probe.py` now has `run_download_discovery` and a `download-discovery` CLI subcommand.
- At runtime only, it creates a system-temp tiny project with one `example.txt`, builds the real bundle zip through `build_bundle`, uploads the temp zip path through the `upload_input` selector with `set_input_files`, sends `generate_prompt_instructions(...)` with the concrete red→blue task, waits via the existing hardened completion helper, inspects page/latest-assistant DOM candidates, classifies `file_link`/`base64_text`/`prose_only`, writes `orchestration/reports/M-008b/T4-download-discovery.json`, audits a summary, and detaches with `session.close()`.
- It performs discovery only: no mutation, no apply, and no download capture.
- URL/log hygiene added for this probe path: `/c/<id>` redaction remains, and URL-ish text/hrefs are reduced to scheme plus first path segment or scheme-only for `blob:`.

Offline validation:
- `uv run python -c "import ast; ast.parse(open('scripts/m008b_real_probe.py').read()); print('PARSE_OK')"` → `PARSE_OK` (uv also warned that the harness `VIRTUAL_ENV` differs from project `.venv`).
- `uv run python -c "import scripts.m008b_real_probe as m; assert hasattr(m,'run_download_discovery'); print('IMPORT_OK')"` → `IMPORT_OK` (same uv environment warning).

No-run/no-network confirmation:
- Did NOT run `download-discovery`.
- Did NOT touch `127.0.0.1:9222`, browser CDP, or network endpoints.
- `git status --short src tests` produced no output; no `src/` or `tests/` files changed.

Commit sha: e95d6fcec7c8be9c819a0556ef76cafd07026e60

ESTIMATE: 90m
ACTUAL: 80m
REWORK-CAUSE: n/a
