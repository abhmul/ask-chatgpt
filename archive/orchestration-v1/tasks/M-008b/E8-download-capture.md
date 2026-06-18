# M-008b · E8 (pi, single editor) — Real download CAPTURE test (decisive UC2 evidence) + stable-selector report

You are the SINGLE EDITOR. WRITE code only; DO NOT RUN it / DO NOT touch network or `127.0.0.1:9222` (manager runs it). Offline-validate via `ast.parse`+import. NEVER `git push`.

## Why
The download-discovery probe found the real ChatGPT surface produces a **"Download the patch bundle"** button in the assistant response (`T4-download-discovery.json`: `download_affordance_found:true`, `kind:file_link`). DECISIVE question for UC2: does clicking it yield a CAPTURABLE file (a Playwright `Download` event + a valid `.zip`)? M-006 claimed "no Download event"; verify on the current surface. Also report a STABLE selector so the manager can populate `real.json:download_artifact`.

## Read FIRST
- `scripts/m008b_real_probe.py` — reuse the discovery flow you wrote (`run_download_discovery`): the bundle build (`build_bundle`), upload, `generate_prompt_instructions` prompt, send, `_wait_for_completion_or_human_stop`, plus all discipline helpers (`connect`, `recheck_safe`, `redact`, `audit`, `session.close()` detach). Factor shared steps into a helper if convenient.
- `src/ask_chatgpt/patch.py` — `_download_candidate_bytes` / `retrieve_patch_bundle` show how a download is captured (`page.expect_download()` pattern) and validated. You may reuse the zip-validation entrypoint if cheap; otherwise just check the captured bytes are a valid zip (`zipfile.is_zipfile`).

## Add subcommand `download-capture`
1. Same as discovery: build tiny 1-file bundle, upload, send the rewritten bundle prompt (task: change example.txt favorite_color red->blue), wait (hardened).
2. Locate the PATCH download control, SCOPED to avoid UI chrome ("Download apps", accounts button): search WITHIN the latest assistant turn region first, then page, for an `a[download]`/`a[href^="blob:"]`/`a[href^="sandbox:"]` OR a button/link whose text matches /download/i AND (text or nearby text mentions patch|bundle|\.zip|the bundle filename). Pick the best single candidate; record its stable attributes (tagName, data-testid, role, an outerHTML snippet truncated to ~200 chars and redacted, and a proposed STABLE selector).
3. Attempt capture: `with page.expect_download(timeout=60000) as dl: <candidate>.click(timeout=15000)`; on success read `download.path()` bytes. If no download event fires within the timeout, record `captured=false` with the failure reason (the HONEST "button present but no capturable Download event" outcome).
4. If captured: write the bytes to a temp file; verify `zipfile.is_zipfile`; record `is_zip`, `nbytes`, and the zip's top-level entry names (names only — these are synthetic test paths like `example.txt`, safe to log). Do NOT apply/mutate anything.
5. Write `orchestration/reports/M-008b/T4-download-capture.json`: `{captured: bool, is_zip: bool|null, nbytes: int|null, entry_names: [...]|null, proposed_selector: <str>, candidate_attrs: {...}, failure_reason: <str|null>}`. `audit` a summary row. `close()` (detach).
6. Print `DOWNLOAD-CAPTURE: captured=<bool> is_zip=<bool> nbytes=<n> selector=<proposed>`. Exit 0 (5 on challenge/logout, leaving browser as-is).

NO apply/mutation. Redact `/c/<id>`; NEVER log signed download URLs / tokens / cookies (scheme + first path segment only; the captured BYTES go only to a temp file, never logged).

## Hard rules
Attach-only; `session.close()` only (never quit/close browser/context, never operator tabs); fail-closed on challenge/login; human-paced; redact `/c/<id>`.

## Verify (OFFLINE)
- `uv run python -c "import ast; ast.parse(open('scripts/m008b_real_probe.py').read()); print('PARSE_OK')"`
- `uv run python -c "import scripts.m008b_real_probe as m; assert hasattr(m,'run_download_capture'); print('IMPORT_OK')"`
- No `src/`/`tests/` changes.

## Report `orchestration/reports/M-008b/E8-worker-report.md`
STATUS; the candidate-selection logic (how you avoid chrome false positives); the capture mechanism (`expect_download`); parse/import; confirm not run / no network; commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:`.

Commit. NEVER `git push`. Do NOT run it.
