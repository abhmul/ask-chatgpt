# T4b — Fixture bundle-facing affordances: download zip + fenced-base64 + upload input. TDD.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1–T4 are DONE/committed. The mock fixture (`tests/fixtures/mock_chatgpt/server.py`, ~914 lines) now has core + adversarial/failure/streaming/copy. You EXTEND it again with the BUNDLE affordances. These are a REQUIRED deliverable NOW even though UC1 (ask_chatgpt->text) does not exercise them — **M-003 consumes them**. Do NOT break the existing 23 tests.

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be green (23 passed). If not, STOP, report BLOCKED with output.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-001/decision-memo.md` — **§6: implement the "Download channel", "Fenced base64 fallback", and "Upload/file input" parts** (and the upload-unsupported / download-unsupported honest-failure states deferred from T4).
3. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001 #2: bundle zip PRIMARY = Playwright download capture; FALLBACK = checksummed fenced base64url zip (BEGIN/END markers, manifest, byte count, SHA-256 validated before apply). Your fixture must EXHIBIT both channels (+ adversarial variants) so M-003's retriever/validator can be built and tested against them.
4. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` — the server you extend. Read it (esp. the `/__script__` control + render paths) first.
5. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/selector_maps/mock.json` — add `download_artifact`, `upload_input` (keep all existing keys).

## Scope — extend the fixture (scriptable via `/__script__`; DRIVER never uses control endpoints)
1. **Download channel (real zip bytes).** After an assistant turn, scriptably render a download artifact card/link/button (selector `download_artifact`) that, when clicked, downloads a REAL zip served with header `Content-Disposition: attachment; filename="<name>.zip"` and `Content-Type: application/zip`. Build the zip in-memory with stdlib `zipfile`: include a `manifest.json` (list of files, each with path + size + SHA-256, plus an overall byte count) and the "changed" file contents. Serve it from a dedicated route (e.g. `GET /download/<artifact_id>`). The Playwright context must use `accept_downloads=True` so `expect_download` captures it. Scriptable `download_mode`: `ok` (default valid zip), `missing` (no artifact rendered), `delayed` (artifact appears only after an extra poll), `wrong_older` (links an OLDER turn's artifact), `corrupt` (bytes are not a valid zip), `truncated` (zip cut short), `collision` (two artifacts share a filename), `unsupported` (download affordance absent → maps to DownloadUnsupportedError later).
2. **Fenced base64url fallback payload.** Scriptably render an assistant turn whose body contains a fenced block carrying a small patch bundle: explicit `BEGIN_PATCH_BUNDLE` / `END_PATCH_BUNDLE` markers, a manifest (changed files w/ sizes+SHA-256, total byte count), and the **base64url** of the zip bytes. Scriptable `fenced_mode`: `ok` (valid, decodes to a real zip whose SHA matches the manifest), `missing_end` (no END marker), `bad_hash` (manifest SHA ≠ actual), `changed_and_unchanged` (manifest lists both changed and unchanged files; bundle contains only changed), `oversized` (payload exceeds a stated size threshold so M-003 can test the oversize honest-failure). Provide a tiny helper so tests can independently recompute the expected SHA/bytes.
3. **Upload / file input.** Render an `<input type="file">` (selector `upload_input`) and/or a drop target. When a file is set, the server records its metadata (filename, size, SHA-256) WITHOUT any real network — store it in state, exposed via `GET /__inspect__`. Scriptable `upload_mode`: `ok` (records metadata), `unsupported` (no input present → UploadUnsupportedError later), `reject_size_type` (server rejects with a detectable marker + reason), `corrupt` (records a corrupted-upload state). Tests use Playwright `set_input_files` with a `tmp_path` file (NEVER a real/private file).
4. **Honest-failure states deferred from T4:** `download_unsupported` and `upload_unsupported` (the `unsupported` modes above satisfy these — ensure each renders a detectable absence/marker the driver can fail-closed on).

### Selector-map additions (`src/ask_chatgpt/selector_maps/mock.json`) — ADD, keep existing keys
`download_artifact` (the artifact card/link/button), `upload_input` (the file input). Optionally `artifact_card` / fenced markers if useful. Every new selector MUST match the rendered DOM.

### TDD tests — `tests/test_fixture_files.py` (write FIRST, watch fail, implement)
- **Download ok:** script `download_mode=ok`; drive to the conversation; with `accept_downloads=True` + `expect_download`, click `download_artifact`; save to `tmp_path`; assert `zipfile.is_zipfile`, the `manifest.json` parses, and each listed file's SHA-256 matches the zip contents; assert `Content-Disposition: attachment`. Then variants: `missing` (no artifact), `corrupt` (not a valid zip), `truncated` (invalid/short), `wrong_older`, `collision`, `unsupported` (no artifact / disabled).
- **Fenced ok:** script `fenced_mode=ok`; read latest turn body; assert BEGIN/END markers, parse manifest, base64url-decode, assert decoded bytes are a valid zip whose SHA matches the manifest. Variants: `missing_end`, `bad_hash` (manifest SHA ≠ actual), `oversized` (flagged), `changed_and_unchanged` (manifest lists both).
- **Upload ok:** load app; `set_input_files(tmp_path file)` on `upload_input`; assert `/__inspect__` recorded filename+size+SHA. Variants: `unsupported` (no input), `reject_size_type` (rejection marker), `corrupt`.
- Full `uv run pytest -q` GREEN (existing 23 + new). Bound Playwright waits (no sleep-spin).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Tests and ALL work NEVER contact chatgpt.com/openai or any external service. The mock binds 127.0.0.1 ONLY, EPHEMERAL port (keep it). Downloads/uploads are served/recorded entirely on loopback; NO real network. Upload test files come from `tmp_path` only — NEVER a real/private file.
- The ONLY ever-permitted external download is chromium — ALREADY CACHED. ZERO new pip deps (stdlib `zipfile`/`hashlib`/`base64` + existing `playwright`). Never sudo/apt/install.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Zip/manifest contents are synthetic test data.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY. NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Tear down servers/browsers you start; kill only your own processes. NEVER `git push`. Do NOT `git commit`.
- Do NOT break the existing 23 tests. EXTEND server.py / mock.json. ESTIMATE BEFORE EXECUTE for anything >2 min.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-002/T4b-report.md`)
- `date -Iseconds` at START + END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- `ESTIMATE: T4b <min>m`.
- Report ≤200 lines: files touched, the download/fenced/upload scriptable modes (names + semantics), new selector keys, the exact `uv run pytest -q` summary, how the zip/manifest/SHA are built, deviations, trust notes (loopback-only, tmp_path-only uploads, synthetic data, zero new deps).
- End with `T4b-STATUS: DONE` (or `BLOCKED` + exact error + next action) LAST.

## Success criteria (all must hold)
- Download artifact serves a REAL zip (Content-Disposition attachment, manifest+SHA) captured by a real Playwright download event; all download variants implemented.
- Fenced base64url payload with BEGIN/END+manifest+bytecount+SHA-256 + variants (missing_end/bad_hash/oversized/changed_and_unchanged).
- Upload `<input type=file>` records metadata on loopback + variants (unsupported/reject/corrupt); download_unsupported + upload_unsupported failure states detectable.
- `mock.json` gains `download_artifact` + `upload_input` (match DOM; existing keys intact).
- `tests/test_fixture_files.py` green; full `uv run pytest -q` green (23 existing pass); zero new deps.
- Report with telemetry + `T4b-STATUS:` last.
