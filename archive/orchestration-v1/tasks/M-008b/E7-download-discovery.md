# M-008b · E7 (pi, single editor) — Add a real download-affordance DISCOVERY probe subcommand

You are the SINGLE EDITOR. WRITE code only; DO NOT RUN it / DO NOT touch the network or `127.0.0.1:9222` (the manager runs it). Offline-validate via `ast.parse` + import. NEVER `git push`.

## Goal
Determine empirically whether the operator's real ChatGPT surface, given the M-008a rewritten bundle prompt + an uploaded bundle, produces an ACTUAL downloadable file affordance (a download link/button) — so we can populate `real.json:download_artifact` and capture via the download path — OR whether it only emits text (→ honest `DownloadUnsupportedError`, the valid outcome; never claim success via base64 text). This is DISCOVERY only — NO file mutation, NO apply.

## Read FIRST
- `scripts/m008b_real_probe.py` — reuse `connect()`, `recheck_safe()`, `redact()`, `_redact_jsonable()`, `audit()`, `_latest_assistant_text()`, `_wait_for_completion_or_human_stop()`, `HUMAN_PACE_S`. Keep ALL discipline (attach-only, detach-not-quit, fail-closed on challenge/login, human-paced, redact `/c/<id>`, no credential/token logging).
- `src/ask_chatgpt/api.py` + `src/ask_chatgpt/bundle.py` — how a files/dirs request becomes an uploaded `.zip` bundle: find the function(s) that BUILD the bundle zip (e.g. a `build_*bundle*`/`*_bundle_bytes` in bundle.py) and the model-facing PROMPT template (`_PROMPT_INSTRUCTIONS_TEMPLATE` / the public prompt builder). Reuse them — do NOT hand-roll the prompt or zip.
- `src/ask_chatgpt/driver.py` — `BrowserSession`: `open_or_create_conversation`, the `upload_input` selector (`input[type="file"]`), `send_prompt`, `wait_for_completion`. Upload via `page.locator(<upload_input selector>).set_input_files(<zip path>)` (write the zip to a temp file under the system temp dir, NOT the repo).

## Add subcommand `download-discovery`
1. Build a TINY bundle for a 1-file synthetic project (e.g. a temp dir with `example.txt` containing `favorite_color = "red"`), using bundle.py's real bundle builder. Write the bundle `.zip` to a temp path.
2. `connect()`; `open_or_create_conversation(None)`; `recheck_safe`.
3. Upload the bundle zip: `session.page.locator('input[type="file"]').set_input_files(<zip_path>)` (handle the selector via the selector map / the `upload_input` key). `audit` the upload.
4. Send the M-008a rewritten bundle prompt (from bundle.py, with the bundle filename + a concrete tiny task like "In example.txt, change favorite_color from red to blue."). `audit` the send. `_wait_for_completion_or_human_stop`.
5. Inspect the DOM for download affordances — `page.evaluate` collecting, from the WHOLE page and the latest assistant turn region:
   - `a[download]`, `a[href^="blob:"]`, `a[href^="sandbox:"]`, `a[href*="/backend-api/"][href*="download"]`, `a[href*="files"]`, buttons/links whose text matches /download/i, file-attachment cards (`[data-testid*="file"]`, `[class*="download" i]`).
   - For each candidate: tagName, a stable-looking selector guess (data-testid or role+text), and the href SCHEME only (blob/sandbox/https — do NOT log full hrefs; redact `/c/<id>` and never log tokens/signed URLs; truncate hrefs to scheme + first path segment).
6. Capture the assistant response text via `_latest_assistant_text` (redacted) to classify what GPT produced: `file_link` (a download affordance present), `base64_text` (response contains a long base64/fenced block but no link), or `prose_only`.
7. Write `orchestration/reports/M-008b/T4-download-discovery.json`: `{download_affordance_found: bool, candidates: [...], response_kind: "file_link"|"base64_text"|"prose_only", response_excerpt: <first 400 chars redacted>}`. `audit` a summary row. `close()` (detach).
8. Print `DOWNLOAD-DISCOVERY: found=<bool> kind=<...> candidates=<n>`. Exit 0 (exit 5 on challenge/logout, leaving the browser as-is).

NO mutation, NO apply, NO download capture in this probe — DISCOVERY only (we inspect affordances + classify the response). The manager decides next steps (populate real.json + round-trip, or honest DownloadUnsupportedError).

## Hard rules (same as the probe)
Attach-only; `session.close()` only (never quit/close browser/context, never operator tabs); fail-closed on challenge/login; human-paced; redact `/c/<id>`; NEVER log credentials, cookies, tokens, signed download URLs (scheme + first path segment only).

## Verify (OFFLINE — do NOT run it)
- `uv run python -c "import ast; ast.parse(open('scripts/m008b_real_probe.py').read()); print('PARSE_OK')"`
- `uv run python -c "import scripts.m008b_real_probe as m; assert hasattr(m,'run_download_discovery'); print('IMPORT_OK')"`
- Confirm no `src/`/`tests/` changes (probe + report only).

## Report `orchestration/reports/M-008b/E7-worker-report.md`
STATUS; which bundle-builder + prompt template you reused (file:line); the subcommand behavior; parse/import outputs; confirmation you did NOT run it / no network; commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:`.

Commit the slice. NEVER `git push`. Do NOT run the probe.
