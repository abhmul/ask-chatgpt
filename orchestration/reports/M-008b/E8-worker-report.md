# E8 worker report

STATUS: PASS — added the attach-only `download-capture` probe code and offline-validated it; the real probe was not run.

Implementation:
- `scripts/m008b_real_probe.py` now has `run_download_capture` and a `download-capture` CLI subcommand.
- Runtime flow reuses the E7 discovery discipline: builds the tiny one-file bundle with `build_bundle`, uploads it via `upload_input`, sends the `generate_prompt_instructions` red→blue task, waits with `_wait_for_completion_or_human_stop`, rechecks safety, writes `orchestration/reports/M-008b/T4-download-capture.json`, audits a summary row, and detaches with `session.close()`.
- The runtime JSON shape is `{captured, is_zip, nbytes, entry_names, proposed_selector, candidate_attrs, failure_reason}`. It is not generated offline because the probe was not run.

Candidate-selection logic:
- Selection searches the latest assistant turn first using the configured `assistant_message` selector, then falls back to page scope only if no latest-turn candidate is found.
- Eligible candidates are `a[download]`, `a[href^="blob:"]`, `a[href^="sandbox:"]`, or interactive `a`/`button`/role button/link elements with `/download/i` text plus nearby patch context (`patch`, `bundle`, `.zip`, `zip`, or the generated bundle filename).
- Chrome false positives are avoided by latest-turn precedence, patch-context gating for text controls, and explicit rejection of known chrome-like controls such as `Download apps` and account/profile/sidebar download text without patch context.
- The selected candidate records stable attributes (`tagName`, `data-testid`, `role`, aria/title/download attrs, safe href shape, text snippet, outerHTML snippet) plus a proposed selector such as `latest assistant turn >> button:has-text("Download the patch bundle")`; URL-ish values are reduced to scheme/first path segment and `/c/<id>` is redacted.

Capture mechanism:
- The click is wrapped exactly as `with page.expect_download(timeout=60000): candidate.click(timeout=15000)`.
- If a Download event yields a body path, bytes are copied only into a system temp `.zip`, `zipfile.is_zipfile` is checked, byte count is recorded, and only top-level zip entry names are logged.
- If no Download event fires, the honest runtime failure is `button present but no capturable Download event`; no apply/mutation path is invoked.

Offline validation:
- `uv run python -c "import ast; ast.parse(open('scripts/m008b_real_probe.py').read()); print('PARSE_OK')"` → `PARSE_OK` (uv warned that harness `VIRTUAL_ENV` differs from project `.venv`).
- `uv run python -c "import scripts.m008b_real_probe as m; assert hasattr(m,'run_download_capture'); print('IMPORT_OK')"` → `IMPORT_OK` (same uv environment warning).

No-run/no-network confirmation:
- Did NOT run `download-capture` or any real-site subcommand.
- Did NOT touch `127.0.0.1:9222`, browser CDP, or network endpoints.
- `git status --short src tests` produced no output; no `src/` or `tests/` files changed.

Implementation commit sha: a22ebf8a400b0a12cf783756da975899a8f56e87

ESTIMATE: 90m
ACTUAL: 80m
REWORK-CAUSE: n/a
