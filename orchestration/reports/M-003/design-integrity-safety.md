ESTIMATE: T1b 55m
START_TIMESTAMP: 2026-06-12T02:06:03-05:00
LENS: integrity-safety

## 1. Fixture ground truth to preserve/reject

- Binding decision: `docs/DECISIONS.md:14` says patch bundle primary is Playwright download and fallback is checksummed fenced base64url with `BEGIN/END` markers, manifest, byte count, and SHA-256 validated before apply.
- README acceptance: `README.md:13` requires a patch bundle containing changed files only; `README.md:20` requires honest named failures for upload/download unsupported and response truncated.
- Variant sets: `tests/fixtures/mock_chatgpt/server.py:38` defines download `{"ok", "missing", "delayed", "wrong_older", "corrupt", "truncated", "collision", "unsupported"}`; `server.py:39` defines fenced `{"ok", "missing_end", "bad_hash", "changed_and_unchanged", "oversized"}`; `server.py:41` defines upload `{"ok", "unsupported", "reject_size_type", "corrupt"}`.
- Fixture manifest today: entries are emitted as `{"path": path, "size": len(data), "sha256": sha256(data).hexdigest(), "status": "changed"}` at `server.py:86`, optional `"status": "unchanged"` at `server.py:90`, and top-level `"version": 1`, `"files"`, `"total_byte_count"` at `server.py:94-96`; `manifest.json` is written to the zip at `server.py:101`, while only changed file bytes are written at `server.py:103`.
- Fenced literal tokens: `server.py:114-115` adds `zip_byte_count` and `zip_sha256` to the fenced manifest object; `server.py:124-128` emits `BEGIN_PATCH_BUNDLE`, `MANIFEST_JSON:`, `ZIP_BYTE_COUNT:`, `ZIP_SHA256:`, and `BASE64URL:`; `server.py:131-132` omits `END_PATCH_BUNDLE` for `missing_end`.
- Integrity adversaries: `server.py:116-117` makes `bad_hash` set `zip_sha256` to 64 zeroes; `server.py:118-120` marks `oversized` and records `_OVERSIZED_THRESHOLD_BYTES = 64` from `server.py:50`; `server.py:110` injects unchanged files for `changed_and_unchanged`.
- Download ground truth: links carry `data-filename`, `data-byte-count`, `data-sha256`, and `data-source-turn-id` at `server.py:852-855`; the server responds as `Content-Type: application/zip`, `Content-Disposition: attachment`, and `content-length` at `server.py:1106-1111`; corrupt/truncated bodies are produced at `server.py:556-559`; wrong-older/collision/delayed are produced at `server.py:519-541`.
- Upload ground truth: the upload affordance is `<input data-testid="mock-upload-input" ... accept=".zip,application/zip">` at `server.py:923`; rejection/corruption reasons are at `server.py:604`, `server.py:614`, and `server.py:623`; selector names `download_artifact`/`upload_input` map at `src/ask_chatgpt/selector_maps/mock.json:19-20`.
- Test API assertions: `tests/test_fixture_files.py:64-78` parses `BEGIN_PATCH_BUNDLE`, `END_PATCH_BUNDLE`, `MANIFEST_JSON:`, `ZIP_BYTE_COUNT:`, and `ZIP_SHA256:`; `test_fixture_files.py:52-59` validates `manifest.json` sizes and hashes; `test_fixture_files.py:224-231` proves `changed_and_unchanged` includes an `unchanged` manifest entry without zip bytes.
- Existing named errors: `src/ask_chatgpt/errors.py:40`, `:63`, and `:71` already define `ResponseTruncatedError`, `UploadUnsupportedError`, and `DownloadUnsupportedError`.

## 2. Manifest schema

Canonical schema version: `version: 2`. Current fixture schema version `1` is accepted only as a compatibility input: `status: "changed"` normalizes to `kind: "modified"`; `status: "unchanged"` is rejected because a patch bundle contains changed/deleted paths only.

| Field | Type | Required | Ordering/constraints | Notes |
|---|---:|---:|---|---|
| `version` | integer | yes | canonical value `2`; fixture `1` accepted as above | reject other values as `PatchMalformedError` |
| `zip_byte_count` | integer | external/envelope yes | `0 <= value <= PATCH_BUNDLE_MAX_ZIP_BYTES`; exact byte length of downloaded/decoded zip | in fenced, `MANIFEST_JSON.zip_byte_count` must equal `ZIP_BYTE_COUNT`; embedded `manifest.json` omits this to avoid circular self-hash |
| `zip_sha256` | string | external/envelope yes | exactly 64 lowercase hex chars; exact SHA-256 of zip bytes | in fenced, `MANIFEST_JSON.zip_sha256` must equal `ZIP_SHA256`; download uses trusted artifact metadata such as fixture `data-sha256` |
| `files` | array | yes | sorted lexicographically by `path`; unique paths; nonempty unless an explicit empty patch mode is later designed | semantic order is deterministic, not JSON object order |
| `files[].path` | string | yes | repo-root-relative, forward slash only, no empty/`.`/`..` component, not absolute, no NUL, not reserved `manifest.json` | same path names as zip entries for added/modified |
| `files[].kind` | string enum | yes in v2 | one of `added`, `modified`, `deleted` | fixture v1 `status:"changed"` maps to `modified`; no `unchanged` kind |
| `files[].size` | integer | for `added`/`modified` only | exact uncompressed byte length; `0 <= size <= PATCH_BUNDLE_MAX_FILE_BYTES` | must be absent for `deleted` |
| `files[].sha256` | string | for `added`/`modified` only | exactly 64 lowercase hex chars; exact SHA-256 of file bytes | must be absent for `deleted` |
| `total_byte_count` | integer | compatibility optional | if present, equals sum of `size` for added/modified entries | fixture emits this at `server.py:96`; do not trust it instead of per-file checks |

Deletion representation: a deleted file has `{ "path": "...", "kind": "deleted" }`, no zip member, no bytes, no `size`, and no `sha256`. A deletion never deletes directories and never follows/deletes symlinks.

## 3. Validation order: validate everything before mutating anything

1. Select retrieval channel and latest turn: only the latest completed assistant turn is eligible. If a download artifact has `data-source-turn-id` not equal to that turn, fail/fallback; if no valid channel remains, raise the mapped error below. No target-root writes occur in this phase.
2. Build an integrity envelope: download must provide declared `zip_byte_count` and `zip_sha256` from artifact metadata/sidecar; fenced must provide one complete `BEGIN_PATCH_BUNDLE`...`END_PATCH_BUNDLE` block with `MANIFEST_JSON:`, `ZIP_BYTE_COUNT:`, `ZIP_SHA256:`, and `BASE64URL:`. Missing `END_PATCH_BUNDLE` raises existing `ResponseTruncatedError` before decoding.
3. Enforce prefetch/predecode caps: if declared `zip_byte_count > PATCH_BUNDLE_MAX_ZIP_BYTES`, if `Content-Length` exceeds the cap, or if base64url length implies decoded bytes above cap, raise `OversizedPayloadError` before download/decode expansion. Fenced `oversized` tests should set the cap to 64 bytes from the fixture threshold; the assistant-provided `oversized*` fields are not trusted as policy.
4. Materialize zip bytes only into memory or a non-target temp file under the configured temp area. If actual byte length differs from declared `zip_byte_count`, raise `BundleIntegrityError`; if actual SHA-256 differs from declared `zip_sha256`, raise `BundleIntegrityError`.
5. Open the zip without extracting. If central directory parsing fails, duplicate entry names exist, entries are encrypted, entries are symlinks, or `manifest.json` is missing/duplicated/unreadable, raise `PatchMalformedError`. Inspect `ZipInfo.file_size` first; if any file or the expanded total exceeds caps, raise `OversizedPayloadError` before reading contents.
6. Parse and normalize the manifest. Fenced `MANIFEST_JSON` must agree with embedded `manifest.json` after removing external-only `zip_byte_count`/`zip_sha256`. JSON must be UTF-8 object; keys/field types must match the schema; unknown `status`, `status:"unchanged"`, bad hex, unsorted/duplicate paths, or inconsistent `total_byte_count` raise `PatchMalformedError`.
7. Check zip-entry set exactly: `{zip names except manifest.json}` must equal `{path for kind in {added, modified}}`; deleted paths must have no zip entry; no extra directory/file entries. Mismatch raises `PatchMalformedError`.
8. For every added/modified entry, read bytes through `ZipFile.open` only after caps, let zip CRC validation run, and verify `len(bytes)==size` and `sha256(bytes)==sha256`. Any mismatch raises `BundleIntegrityError`; decompression/CRC failure raises `PatchMalformedError` unless the whole-zip hash already mismatched.
9. Run path-safety resolution for every manifest path and every to-be-created parent. Any absolute path, traversal, symlink component, non-descendant, directory target, or reserved metadata conflict raises `PathEscapeError` or `PatchMalformedError` as below. Still no target-root mutation.
10. Only after all checks pass, enter apply transaction. If any step above fails, raise the named error and write nothing to the caller root.

## 4. Apply semantics and crash safety

Use staged transaction, not direct buffered writes. Stage validated added/modified bytes under a fresh transaction directory inside the allowed temp area, fsync staged files, write a credential-free journal containing target relative paths and backup paths, then commit using per-file atomic `os.replace` for writes and `os.unlink` for deletions. Never call `ZipFile.extract` or `extractall`.

All-or-nothing on validation failure is absolute: no mutation before step 10. Crash safety for in-place multi-file apply requires recovery: before each apply and CLI startup, detect an incomplete journal and roll back from backups or complete the recorded commit before accepting new work. Without this recovery layer, in-place multi-file apply cannot honestly promise crash-safe all-or-nothing on ordinary POSIX filesystems; therefore T3 should implement journaled recovery or constrain `--apply` to a dedicated temp worktree/snapshot mode.

Kind-specific target rules: `added` and `modified` write regular files only, creating non-symlink directories as needed; existing symlink or directory targets are rejected; `deleted` unlinks only an existing regular file at the resolved path and is a no-op if absent unless synthesis chooses stricter conflict detection.

## 5. Zip-slip containment algorithm

For each `rel` from the manifest:

```text
root_real = realpath(root)
reject if root_real is not an existing directory
reject rel if rel is empty, contains NUL or backslash, starts with `/`, has a Windows drive/UNC form, or any component is `""`, `"."`, or `".."`
parts = rel.split("/")
lexical_target = normpath(join(root_real, *parts))
reject unless commonpath([root_real, lexical_target]) == root_real
walk from root_real through parts[:-1] using lstat/openat(O_DIRECTORY|O_NOFOLLOW): if an existing component is a symlink, reject; if it is outside root after realpath/commonpath, reject; if it is a non-directory, reject; missing components may be created only after validation and only as real directories
if target lexists: lstat target; reject if symlink; reject if directory for file write/delete; reject unless commonpath([root_real, realpath(target)]) == root_real
when opening/replacing, operate relative to checked parent dir_fd and use no-follow semantics; never follow the final target symlink
```

`commonpath`/`realpath` containment is required; string-prefix-only checks are forbidden. Tests must include absolute paths, `../`, `a/../../b`, backslashes/drive paths, symlink parent escaping outside root, final-file symlink, and a sibling-prefix trap such as root `/tmp/repo` vs target `/tmp/repo2/file`.

## 6. Oversize caps

| Constant | Default | Applies where |
|---|---:|---|
| `PATCH_BUNDLE_MAX_ZIP_BYTES` | 25 MiB | declared/actual zip bytes, download `Content-Length`, fenced decoded length; reject before fetch/decode where possible |
| `PATCH_BUNDLE_MAX_FILE_BYTES` | 5 MiB | each added/modified uncompressed member size from manifest and central directory before reading |
| `PATCH_BUNDLE_MAX_EXPANDED_BYTES` | 50 MiB | sum of added/modified uncompressed sizes before reading, zip-bomb guard |
| `PATCH_MANIFEST_MAX_BYTES` | 1 MiB | embedded/external manifest bytes before JSON parse |
| `PATCH_BUNDLE_MAX_BASE64URL_CHARS` | derived from zip cap | fenced text block size guard before base64 decode |

All caps are API/CLI/test overridable. Upload preflight should use the same zip cap or an `UPLOAD_BUNDLE_MAX_ZIP_BYTES` alias so oversized outgoing bundles fail locally before UI upload.

## 7. Failure taxonomy and named errors

| Failure | Error | Existing? | Message shape |
|---|---|---:|---|
| Malformed fenced block, invalid JSON/schema, bad zip central directory, missing/extra zip entries, `status:"unchanged"`, ambiguous/collision artifact | `PatchMalformedError` | new | `Patch bundle is malformed or not a valid changed-files patch. Operator action: retry retrieval or ask for a fresh patch bundle; no local files were changed. Detail: phase=<phase>; reason=<safe reason>; path=<rel optional>.` |
| Whole zip byte count/SHA mismatch; per-file size/SHA mismatch; upload recorded SHA differs from local expected SHA | `BundleIntegrityError` | new | `Patch bundle integrity check failed. Operator action: retry the transfer or use the alternate return channel; no local files were changed. Detail: expected_<field>=...; actual_<field>=...; path=<rel optional>.` |
| Any cap exceeded before/while validating | `OversizedPayloadError` | new | `Payload exceeds configured size limits. Operator action: reduce selected files, split the patch, or raise an explicit limit; no local files were changed. Detail: limit=<name>; max=<bytes>; actual=<bytes>.` |
| Absolute/traversal path, symlink component/final target, non-descendant real path | `PathEscapeError` | new | `Patch bundle contains a path that would escape the apply root. Operator action: reject this bundle and request root-relative file paths; no local files were changed. Detail: path=<rel>; reason=<safe reason>.` |
| Upload input absent or UI rejects upload size/type | `UploadUnsupportedError` | yes, `errors.py:63` | keep existing default; detail may include `reason=file size/type rejected by UI` without filenames outside basename |
| Download affordance absent/unsupported and no fallback succeeds | `DownloadUnsupportedError` | yes, `errors.py:71` | keep existing default; detail may include `reason=no valid latest-turn artifact` |
| Missing `END_PATCH_BUNDLE`, incomplete latest response, network body shorter than declared | `ResponseTruncatedError` | yes, `errors.py:40` | keep existing default; detail may include `phase=fenced_patch_bundle` |

Add new classes to `src/ask_chatgpt/errors.py` and `__all__`; do not log credentials, cookies, profile paths, or full external URLs in details.

## 8. Mandatory adversarial test matrix for T3

| Fixture variant | Expected handling/error |
|---|---|
| download `missing` | No latest-turn artifact: try fenced fallback; if none, `DownloadUnsupportedError`; no mutation. |
| download `delayed` | Bounded poll/reload until artifact appears, then normal validation OK; timeout falls back, then `DownloadUnsupportedError` if no fallback. |
| download `wrong_older` | Reject artifact whose `data-source-turn-id` is not latest turn; `PatchMalformedError` or fallback to fenced if valid. |
| download `corrupt` | Declared whole hash may match corrupt bytes, but zip open fails; `PatchMalformedError`; no mutation. |
| download `truncated` | Fixture body is not a valid zip; `PatchMalformedError`; if transport length is shorter than declared in other tests, `ResponseTruncatedError`/`BundleIntegrityError` as applicable. |
| download `collision` | Multiple same-turn artifacts/filename collision is ambiguous; `PatchMalformedError`; no mutation. |
| download `unsupported` | Use fenced fallback if present; otherwise existing `DownloadUnsupportedError`. |
| fenced `missing_end` | Existing `ResponseTruncatedError` before base64 decode. |
| fenced `bad_hash` | `BundleIntegrityError` on `ZIP_SHA256`/actual zip SHA mismatch. |
| fenced `changed_and_unchanged` | `PatchMalformedError` because `status:"unchanged"` is not a patch kind and has no zip bytes. |
| fenced `oversized` | `OversizedPayloadError` using test override cap `PATCH_BUNDLE_MAX_ZIP_BYTES=64`; reject before decode/expand. |
| upload `unsupported` | Existing `UploadUnsupportedError`; no attempt to read credentials or use real site. |
| upload `reject_size_type` | Existing `UploadUnsupportedError` with safe UI reason, or `OversizedPayloadError` if local preflight cap was exceeded before upload. |
| upload `corrupt` | `BundleIntegrityError` because mock-recorded SHA differs from local upload SHA; retry/fallback, no local mutation. |

## 9. Open questions for synthesis

1. When should the fixture move from v1 `status:"changed"` to canonical v2 `kind:{added,modified,deleted}`? Until then, keep the narrow compatibility shim above.
2. Is journaled recovery sufficient crash safety for in-place apply, or must `--apply` require a dedicated temp worktree/snapshot to give true atomic tree replacement?
3. Should v2 add optional `base_sha256` for modified/deleted files to prevent overwriting local files that changed after upload?
4. Real ChatGPT downloads may not expose independent byte-count/SHA metadata; should primary download without such metadata be considered unsupported and force fenced fallback?
5. Should deletion of an already-missing file be accepted as idempotent or reported as a local-state conflict?

END_TIMESTAMP: 2026-06-12T02:10:44-05:00
T1b-STATUS: DONE