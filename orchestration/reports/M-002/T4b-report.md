START_TIMESTAMP: 2026-06-12T00:32:41-05:00
ESTIMATE: T4b 45m
END_TIMESTAMP: 2026-06-12T00:46:19-05:00

Files touched:
- `tests/fixtures/mock_chatgpt/server.py`
- `src/ask_chatgpt/selector_maps/mock.json`
- `tests/test_fixture_files.py`
- `orchestration/reports/M-002/T4b-report.md`

STEP 0 inherited tree:
- `uv sync --all-groups` completed.
- `uv run pytest -q` summary before changes: `23 passed in 5.83s`.

TDD:
- Wrote `tests/test_fixture_files.py` first.
- Red check: `uv run pytest tests/test_fixture_files.py -q` failed at collection because `build_mock_patch_zip` did not exist yet.
- Implemented fixture/server and selector-map extensions.

Download modes:
- `ok`: latest assistant turn renders `download_artifact`; clicking captures a real Playwright download of a valid zip from `/download/<artifact_id>`.
- `missing`: no artifact rendered.
- `delayed`: artifact exists in state but is hidden until one extra `/c/<ref>` poll/reload.
- `wrong_older`: latest turn's download link points to a prior turn artifact and exposes `data-source-turn-id` for detection.
- `corrupt`: served bytes are not a valid zip.
- `truncated`: served bytes are a prefix of a valid zip and fail zip validation.
- `collision`: two artifact links share the same filename.
- `unsupported`: no artifact link; renders detectable `[data-testid="download-unsupported"]`.

Fenced base64url modes:
- `ok`: assistant body includes `BEGIN_PATCH_BUNDLE` / `END_PATCH_BUNDLE`, `MANIFEST_JSON`, `ZIP_BYTE_COUNT`, `ZIP_SHA256`, and unpadded base64url zip bytes.
- `missing_end`: omits `END_PATCH_BUNDLE`.
- `bad_hash`: manifest/line SHA-256 is intentionally wrong.
- `changed_and_unchanged`: manifest lists changed and unchanged files; zip contains only changed paths plus `manifest.json`.
- `oversized`: manifest carries `oversized: true` and a threshold smaller than the encoded zip byte count.

Upload modes:
- `ok`: renders `<input type="file" data-testid="mock-upload-input">`; browser computes filename/size/SHA-256 and posts metadata to loopback `/__upload__`; `/__inspect__` exposes `last_upload`.
- `unsupported`: no input; renders `[data-testid="upload-unsupported"]`.
- `reject_size_type`: records rejected upload with reason `file size/type rejected by mock` and updates DOM status marker.
- `corrupt`: records corrupted-upload state with zeroed SHA and `original_sha256` preserved.

New selector keys:
- `download_artifact`: `[data-testid="mock-download-artifact"]`
- `upload_input`: `[data-testid="mock-upload-input"]`

Zip/manifest/SHA construction:
- Uses only stdlib `zipfile`, `hashlib`, `base64`, `io`.
- `build_mock_patch_zip()` writes deterministic synthetic files and `manifest.json` in-memory.
- Manifest entries include `path`, `size`, `sha256`, and `status`; manifest includes `total_byte_count`.
- Download responses set `Content-Type: application/zip` and `Content-Disposition: attachment; filename="...zip"`.
- Fenced payload manifest additionally includes `zip_byte_count` and `zip_sha256`.

Verification:
- Targeted: `uv run pytest tests/test_fixture_files.py -q` -> `4 passed in 4.06s`.
- Full: `uv run pytest -q` -> `27 passed in 9.74s`.

Deviations:
- Existing fixture tests remain green; total test count is now 27 (23 inherited + 4 new grouped tests).
- The upload recording path sends metadata only over loopback after Playwright sets the file input; no file bytes are stored server-side.

Trust notes:
- Loopback-only server retained (`127.0.0.1`, ephemeral port).
- Upload test file is synthetic and created under `tmp_path` only.
- No external service contact; no credentials/cookies/session/profile data read or logged.
- Zero new dependencies; no sudo/apt/install; Python commands run through `uv run` from repo root.
T4b-STATUS: DONE
