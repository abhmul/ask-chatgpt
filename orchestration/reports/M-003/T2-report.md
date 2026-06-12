ESTIMATE: T2 75m
START_TIMESTAMP: 2026-06-12T02:39:27-05:00
END_TIMESTAMP: 2026-06-12T02:40:22-05:00

## Files created/modified
- Created `src/ask_chatgpt/bundle.py`.
- Created `tests/test_bundle_out.py`.
- Modified `src/ask_chatgpt/errors.py`.
- Modified `src/ask_chatgpt/__init__.py`.
- Created `orchestration/reports/M-003/T2-report.md`.

## Public surface built
- `UploadBundleCaps`: upload cap configuration (`max_file_bytes`, `max_total_file_bytes`, `max_zip_bytes`, `max_file_count`).
- `BundleEntry`: deterministic inventory row metadata (`path`, `kind`, `size`, `sha256`).
- `OutgoingBundle`: built zip handle (`filename`, `content`, `sha256`, `byte_count`, `readme`, `entries`, `bundle_id`, root/timestamp metadata).
- `UploadConfirmation`: credential-free upload confirmation (`filename`, `size`, `sha256`, `content_type`, `status`, optional `reason`).
- `build_bundle(files=None, dirs=None, *, root=None, caps=None)`: builds the deterministic bundle-out zip; raises `PathEscapeError` for path-rule/reserved/duplicate/symlink escape failures, `OversizedPayloadError` for caps and non-regular entry types, and `AskChatGPTError` for unreadable selected files.
- `generate_catalogue_readme(entries, *, project_root_name, bundle_id, created_at_iso8601=...)`: emits the §2 catalogue README.
- `generate_prompt_instructions(user_task, *, bundle_filename)`: emits the §2 accompanying prompt-instructions text.
- `upload_bundle(session, bundle, *, filename=None, caps=None, timeout_s=5.0)`: uploads through `upload_input`; raises `UploadUnsupportedError`, `OversizedPayloadError`, `BundleIntegrityError`, or `PathEscapeError` for unsafe override names.
- Constants exported from `bundle.py`: `ASK_CHATGPT_BUNDLE_README`, `UPLOAD_BUNDLE_MAX_FILE_BYTES`, `UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES`, `UPLOAD_BUNDLE_MAX_ZIP_BYTES`, `UPLOAD_BUNDLE_MAX_FILE_COUNT`.

## New error classes added
- `PatchBundleValidationError(AskChatGPTError)`.
- `PatchMalformedError(PatchBundleValidationError)`.
- `BundleIntegrityError(PatchBundleValidationError)`.
- `OversizedPayloadError(PatchBundleValidationError)`.
- `PathEscapeError(PatchBundleValidationError)`.
- `PatchApplyError(AskChatGPTError)`.
- Existing `UploadUnsupportedError` was reused, not duplicated.

## Path rules and size/type guard
- Selected paths are lexically rejected before filesystem reads for absolute paths, drive-letter paths, NULs, backslashes, empty/`.` components, and `..` traversal.
- The generated README path `ASK_CHATGPT_BUNDLE_README.md` is reserved; selected-file collision fails with `PathEscapeError`.
- Duplicate normalized repo-root-relative paths fail with `PathEscapeError`.
- Directory inputs expand recursively in deterministic order; `os.walk(..., followlinks=False)` is used, and symlink files/dirs are rejected rather than skipped.
- Only regular files are included. Directory-as-file and special entries raise `OversizedPayloadError`; symlink components raise `PathEscapeError`.
- File count, per-file size, and total selected-file bytes are preflighted from `lstat()` before file content reads. Actual reads are bounded by `max_file_bytes + 1`, and actual total bytes are rechecked.
- Zip bytes are generated in memory with fixed metadata and `ZIP_STORED`; `UPLOAD_BUNDLE_MAX_ZIP_BYTES` is enforced before returning/uploading the bundle.

## Upload mapping
- Fixture `unsupported`: absent `upload_input`/unsupported status -> `UploadUnsupportedError`.
- Fixture `reject_size_type`: fixture rejection -> `OversizedPayloadError` as the T2 contract's size/type-guard error.
- Fixture `corrupt`: mock SHA-256/status mismatch -> `BundleIntegrityError`.

## Test results
- STEP 0 pre-edit: `60 passed in 30.51s` after `uv sync --all-groups`.
- TDD red observed: `ModuleNotFoundError: No module named 'ask_chatgpt.bundle'`.
- Targeted bundle tests: `9 passed in 2.34s`.
- Full final `uv run pytest -q`: `69 passed in 28.30s`.

## Deviations / notes
- Bundle layout, catalogue content, prompt instructions, path discipline, deterministic ordering, and build-time caps follow `docs/bundle-protocol.md` for T2 scope.
- Upload `reject_size_type` is surfaced as `OversizedPayloadError` per this T2 contract's explicit failure-mapping bullet; the broader §9 wording can also be read as `UploadUnsupportedError` for UI-side rejection after local preflight.
- `created_at_iso8601` is deterministic (`1970-01-01T00:00:00Z`) so identical inputs produce byte-identical README/zip, as required.

## Trust notes
- Tests used only `channel="mock"` and `mock_chatgpt.base_url` loopback URLs.
- No chatgpt.com/openai or external network access was added; existing socket guard remained active.
- No credential, cookie, session-token, or browser-profile file reads/logging were added.
- Zero new pip dependencies; implementation uses stdlib plus existing Playwright.
- No git commit/push performed.
T2-STATUS: DONE
