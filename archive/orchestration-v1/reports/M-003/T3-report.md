ESTIMATE: T3 30m
START_TIMESTAMP: 2026-06-12T02:44:43-05:00
END_TIMESTAMP: 2026-06-12T03:03:59-05:00

## Files created/modified
- Created: `src/ask_chatgpt/patch.py`, `tests/test_patch.py`, `orchestration/reports/M-003/T3-report.md`.
- Modified: `src/ask_chatgpt/__init__.py`, `src/ask_chatgpt/bundle.py`, `src/ask_chatgpt/driver.py`, `tests/test_bundle_out.py`.
- `src/ask_chatgpt/errors.py` already contained the §8 patch errors; no duplicate classes added.

## Public surface implemented
- `PatchBundle`, `PatchBundleCaps`, `retrieve_patch_bundle(session, ...)`, `apply_patch(bundle, root, *, dry_run=True)`, `FileDiff`, `DiffSummary` in `ask_chatgpt.patch`.
- Re-exported from package root: `PatchBundle`, `apply_patch`, `DiffSummary`, `FileDiff`.
- Named validation/apply errors reused: `PatchBundleValidationError`, `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`, `PatchApplyError`; existing `DownloadUnsupportedError` and `ResponseTruncatedError` used for retrieval failures.

## Retrieval decision logic
- The retriever calls `session.wait_for_completion` and considers only the latest completed assistant turn.
- Download primary is selected only for exactly one latest-turn artifact with `data-source-turn-id == data-turn-id`, parseable decimal byte count, lowercase 64-hex SHA-256, and safe basename; duplicate eligible artifacts/filenames or malformed current-turn metadata raise `PatchMalformedError`.
- Delayed artifacts are polled with bounded reloads. Missing/unsupported/delayed-timeout/stale-only cases fall back to the latest-turn fenced block. A selected artifact whose bytes fail integrity or zip validation fails; it does not fall back.
- Fenced fallback requires exactly one complete `BEGIN_PATCH_BUNDLE`/`END_PATCH_BUNDLE` block; missing end raises `ResponseTruncatedError` before decode; byte count/SHA and fenced `MANIFEST_JSON` envelope fields are verified before common zip validation.

## Validation-before-mutate ordering implemented
1. Enforce declared/actual zip caps and whole-zip byte count/SHA-256 envelope.
2. Open zip in memory only; never call `ZipFile.extract`/`extractall`.
3. Reject corrupt/encrypted/duplicate/missing-manifest/symlink/special/oversized entries.
4. Cap and parse `manifest.json`; schema-check version, fields, unknown keys, statuses, operations, unique paths, totals, hashes, and sizes.
5. Enforce zip payload entry set equals manifest changed paths; deleted paths have no payloads.
6. Run shared lexical POSIX path validation for all manifest and payload paths, including reserved metadata paths and `.ask-chatgpt-tmp`.
7. Read changed payloads only after entry-set/path/cap checks; verify per-file size and SHA-256 and expanded-byte cap.
8. Resolve every path under the caller root with no-follow symlink checks and compute `DiffSummary`; `dry_run=True` returns here without writes/temp/journal.
9. Only after all validation succeeds does `dry_run=False` create a root-local staged transaction and journal.

## Zip-slip containment and apply transaction
- Containment uses `realpath(root)`, lexical `normpath(join(root, parts))`, and `commonpath == root`, not string prefixes.
- Parent walk uses `lstat`/no-follow semantics; existing symlink parents, final symlinks, directories, special files, and escaping realpaths raise `PathEscapeError` before writes.
- Missing parents are allowed only for changed-file writes and are created one component at a time during the post-validation transaction after rechecking no symlink/non-directory races.
- Writes stage bytes under `<root>/.ask-chatgpt-tmp/apply-<uuid>/staged`; existing regular targets are backed up; a credential-free journal records relative paths and hashes; commits use same-filesystem `os.replace` or `os.unlink`; ordinary apply failures roll back from backups.

## §9 adversarial coverage matrix
| Variant | Test | Asserted outcome |
| --- | --- | --- |
| download `missing` | `tests/test_patch.py::test_download_missing_falls_back_to_valid_fenced_bundle` | No eligible artifact; valid fenced fallback returns `PatchBundle(source="fenced")`. |
| download `delayed` | `tests/test_patch.py::test_download_delayed_is_polled_with_bounded_wait_and_uses_download` | Bounded polling/reload finds artifact; returns `PatchBundle(source="download")`. |
| download `wrong_older` | `tests/test_patch.py::test_download_wrong_older_rejects_stale_artifact_and_uses_fallback_or_fails` | Stale artifact ignored; valid fallback succeeds; without fallback raises `PatchMalformedError`. |
| download `corrupt` | `tests/test_patch.py::test_download_corrupt_and_truncated_artifacts_raise_patch_malformed[corrupt]` | Metadata-valid non-zip body raises `PatchMalformedError`. |
| download `truncated` | `tests/test_patch.py::test_download_corrupt_and_truncated_artifacts_raise_patch_malformed[truncated]` | Truncated non-zip body raises `PatchMalformedError`. |
| download `collision` | `tests/test_patch.py::test_download_collision_is_ambiguous_and_does_not_choose_or_fallback` | Multiple same-turn artifacts/duplicate filename raises `PatchMalformedError`; no fallback guessing. |
| download `unsupported` | `tests/test_patch.py::test_download_unsupported_uses_valid_fenced_fallback_when_present` and `...without_fallback_raises_download_unsupported` | Valid fallback succeeds; no fallback raises `DownloadUnsupportedError`. |
| fenced `missing_end` | `tests/test_patch.py::test_fenced_missing_end_raises_response_truncated_before_decode` | Raises `ResponseTruncatedError` before decode. |
| fenced `bad_hash` | `tests/test_patch.py::test_fenced_bad_hash_raises_bundle_integrity` | Decoded bytes SHA mismatch raises `BundleIntegrityError`. |
| fenced `changed_and_unchanged` | `tests/test_patch.py::test_fenced_changed_and_unchanged_manifest_is_rejected` | `status:"unchanged"` rejected with `PatchMalformedError`. |
| fenced `oversized` | `tests/test_patch.py::test_fenced_oversized_refuses_before_decode_with_test_cap` | With `max_zip_bytes=64`, raises `OversizedPayloadError` before decode/expand. |
| upload `unsupported` | `tests/test_bundle_out.py::test_upload_failures_map_to_named_errors[unsupported-UploadUnsupportedError]` | Raises `UploadUnsupportedError`. |
| upload `reject_size_type` | `tests/test_bundle_out.py::test_upload_failures_map_to_named_errors[reject_size_type-UploadUnsupportedError]`; `test_upload_local_preflight_cap_rejects_before_ui_interaction` | UI rejection after local preflight raises `UploadUnsupportedError`; local cap breach raises `OversizedPayloadError` before UI. |
| upload `corrupt` | `tests/test_bundle_out.py::test_upload_failures_map_to_named_errors[corrupt-BundleIntegrityError]` | Mock-recorded SHA mismatch raises `BundleIntegrityError`. |
| zip-slip absolute | `tests/test_patch.py::test_zip_slip_absolute_path_raises_path_escape_and_writes_nothing_outside` | Raises `PathEscapeError`; outside file absent; root unchanged. |
| zip-slip `..` | `tests/test_patch.py::test_zip_slip_parent_traversal_raises_path_escape_and_writes_nothing_outside` | Raises `PathEscapeError`; outside file absent; root unchanged. |
| symlink escape | `tests/test_patch.py::test_zip_slip_symlink_parent_escape_raises_path_escape_and_writes_nothing_outside` and `test_zip_symlink_entry_raises_path_escape_and_writes_nothing` | Symlink parent/archive symlink rejected with `PathEscapeError`; no outside/root mutation. |
| late validation failure | `tests/test_patch.py::test_late_validation_failure_leaves_apply_root_byte_for_byte_unchanged` | Second-file SHA mismatch raises `BundleIntegrityError`; root snapshot unchanged. |
| dry run | `tests/test_patch.py::test_dry_run_returns_diff_summary_and_writes_nothing` | Correct added/modified/deleted `DiffSummary`; no writes and no `.ask-chatgpt-tmp`. |
| happy path | `tests/test_patch.py::test_happy_path_valid_bundle_applies_modified_added_and_deleted_files` | Modified+added+deleted files applied under repo `tmp/` root. |

## Test result
- Exact full-suite command: `uv run pytest -q`
- Exact summary line: `89 passed in 41.35s`

## Deviations from protocol
- No functional deviations. One existing T2 upload mapping was corrected to the binding §8/§9 behavior: UI `reject_size_type` after local preflight now raises `UploadUnsupportedError`; local preflight cap breach remains `OversizedPayloadError`.

## Trust notes
- Tests use `channel="mock"`/loopback fixture only; no chatgpt.com/OpenAI/external network contact.
- Patch apply tests create roots only under repo `tmp/` and assert outside targets remain absent.
- No credential/profile/cookie/session-token reads or logging.
- `grep` found no `extract()`/`extractall()` calls in `src` or `tests`.
- Zero new dependencies; stdlib plus existing Playwright only.
- No git commit and no git push.
T3-STATUS: DONE
