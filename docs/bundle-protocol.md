# UC2/UC3 bundle protocol

This file is the binding protocol for local-file bundle upload, patch-bundle retrieval, validation, application, public API wiring, and CLI behavior. Fixture-facing tokens and selector affordances are grounded in `tests/fixtures/mock_chatgpt/server.py` and `tests/test_fixture_files.py`; when this document names parser-facing tokens, downstream code must match them literally.

## 1. Overview and round-trip lifecycle

A **bundle root** is the caller's project root for path relativization and application. All project paths in both directions are POSIX-style paths relative to that root, never absolute paths. A **bundle-out** zip is uploaded to GPT and contains selected project files plus one generated catalogue README. A **patch bundle** is a changed-files-only zip returned by GPT; it is never applied until the entire bundle, manifest, hashes, byte counts, size limits, and paths have been validated.

```text
caller files/dirs under bundle root
  -> build bundle-out zip with ASK_CHATGPT_BUNDLE_README.md + selected regular files
  -> upload through upload_input and send prompt instructions
  -> GPT reads catalogue and either replies NO_CHANGES_NEEDED or returns one patch bundle
  -> retriever parses fenced base64url patch block, with legacy/mock download_artifact zip still supported
  -> validate envelope byte count/SHA-256, zip structure, manifest schema, file hashes, caps, and root containment
  -> apply_patch(..., dry_run=True) returns DiffSummary without writes, or dry_run=False commits through a journaled staged transaction
```

Implementation ownership: T2 builds bundle-out and prompt instructions; T3 retrieves and validates patch bundles and implements `apply_patch`; T4 wires the public API; T5 wires the CLI. The safety invariant is shared: no target-root mutation occurs before validation succeeds for the whole bundle, and the CLI never mutates files without `--apply`.

## 2. Outgoing bundle format (UC2 bundle-out, implemented by T2)

The bundle builder takes explicitly supplied `files` and/or `dirs`, resolves them under a bundle root, expands directories recursively, and writes one deterministic zip. Relative input paths are interpreted relative to `bundle_root` when supplied; otherwise they are interpreted relative to `Path.cwd()`. Absolute input paths are allowed only if their resolved real path is inside the bundle root. Paths outside the bundle root are rejected before any upload.

Zip layout is flat relative to the bundle root: `ASK_CHATGPT_BUNDLE_README.md` at archive root, followed by selected project file entries at their repo-root-relative paths. Directory entries are not required and empty directories are not represented. Zip member names use forward slashes, UTF-8 names, deterministic lexicographic order, and no leading `./`. Duplicate normalized paths are rejected. The generated README is reserved metadata; if a selected project file would have relative path `ASK_CHATGPT_BUNDLE_README.md`, the build fails instead of silently shadowing either file.

Only regular files may be included. Symlinks, device files, FIFOs, sockets, unreadable files, browser profile paths supplied through `profile_path`, absolute paths, paths containing `..`, paths containing backslashes, and paths with empty or `.` components are rejected. File contents are read only for user-selected project files after these guards pass; the tool never reads browser-profile contents, cookies, session tokens, credentials, or unrelated filesystem trees. Build-time caps are enforced before upload: `UPLOAD_BUNDLE_MAX_FILE_BYTES = 5 MiB`, `UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES = 50 MiB`, `UPLOAD_BUNDLE_MAX_ZIP_BYTES = 25 MiB`, and `UPLOAD_BUNDLE_MAX_FILE_COUNT = 1000`, all overridable by explicit API/CLI configuration in tests or advanced use.

The fixture upload affordance is `upload_input`, rendered as `data-testid="mock-upload-input"` and accepting `.zip,application/zip`. Upload fixture variants are exactly `ok`, `unsupported`, `reject_size_type`, and `corrupt`; the uploader must surface them as specified in the adversarial matrix.

### Catalogue README full template

T2 must generate the following README as `ASK_CHATGPT_BUNDLE_README.md`, replacing `{{...}}` placeholders and `{{INVENTORY_ROWS}}` with deterministic data from the selected files.

````markdown
# ask-chatgpt bundle instructions

Read this file first. This zip is a project-context bundle prepared by `ask-chatgpt` so you can answer the user using local files and, if needed, return edits as a machine-readable patch bundle.

## Project root and path rules

The archive root represents the project root named `{{PROJECT_ROOT_NAME}}`. Every project file path below is repo-root-relative. Use forward slashes only. Never use absolute paths, drive letters, leading `/`, backslashes, empty path segments, or `..`. Treat paths as case-sensitive. Patch bundles may contain only regular file entries; include a top-level `manifest.json` only when representing deletions. Do not create symlinks or special files.

## Bundle identity

- Bundle id: `{{BUNDLE_ID}}`
- Created at: `{{CREATED_AT_ISO8601}}`
- Project root display name: `{{PROJECT_ROOT_NAME}}`
- Included file count: `{{FILE_COUNT}}`
- Included payload bytes: `{{TOTAL_BYTES}}`

## Included file inventory

Directories supplied by the caller were expanded recursively. The table lists every included project file; empty directories are not represented. `Path` is the canonical path to use in discussion and patch bundles. `Zip entry` is where the file appears inside this archive. `Kind` is `text` or `binary` by conservative local detection. `Size` is decimal bytes. `SHA-256` is lowercase hex of the included file bytes.

| Path | Zip entry | Kind | Size bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
{{INVENTORY_ROWS}}

Inventory row template:

| `src/example.py` | `src/example.py` | text | 1234 | `0123456789abcdef...` |

If a file you need is not in this inventory, say what is missing in your ordinary answer. Do not invent unseen file contents. You may create a new repo-root-relative file when the user task clearly requires it.

## If no edits are needed

If the correct response requires no file changes, reply exactly:

```text
NO_CHANGES_NEEDED
```

Do not emit a fenced patch bundle in that case.

## If edits are needed: return a patch bundle, not the whole tree

Return exactly one patch bundle containing only changed/added file payloads at repo-root-relative forward-slash paths. Do not include unchanged files. Do not include this instruction file. Do not include the whole project tree. Do not include `ASK_CHATGPT_BUNDLE_README.md`, absolute paths, `..`, backslashes, drive letters, symlinks, or paths outside the project root.

No `manifest.json` is required for added or modified files; the tool reconstructs per-file metadata from verified zip entries after checking the whole-zip SHA-256. If deletions are required, additionally include one top-level `manifest.json` with deletion entries and omit payloads for deleted paths.

Deletion manifest schema, only when needed:

```json
{
  "version": 1,
  "files": [
    {"path": "src/existing.py", "status": "changed", "operation": "modified", "size": 1200, "sha256": "<sha256-of-new-bytes>"},
    {"path": "src/new_file.py", "status": "changed", "operation": "added", "size": 300, "sha256": "<sha256-of-new-bytes>"},
    {"path": "docs/obsolete.md", "status": "deleted", "operation": "deleted", "size": 0, "sha256": null}
  ],
  "total_byte_count": 1500
}
```

For added and modified files, include the new file bytes in the zip at exactly `path`. For deleted files, set `status` and `operation` to `deleted`, set `size` to `0`, set `sha256` to `null`, and omit the deleted file payload from the zip. Do not use `status: "unchanged"` in real patch bundles.

## Fenced patch-bundle response format

Emit exactly this 5-line block and no other patch bundle. Do not wrap it in Markdown triple backticks. Do not add commentary inside the block. Use a single space after each key and no colon. Put the `BASE64URL` payload on the same line, one unbroken unpadded base64url token using only `A-Z`, `a-z`, `0-9`, `-`, and `_`; do not use `+`, `/`, or `=`.

```text
BEGIN_PATCH_BUNDLE
ZIP_BYTE_COUNT <decimal byte length of the zip>
ZIP_SHA256 <lowercase 64-hex sha256 of the exact zip bytes>
BASE64URL <unpadded base64url of the zip bytes, one unbroken token on this line>
END_PATCH_BUNDLE
```

`ZIP_BYTE_COUNT` and `ZIP_SHA256` describe the exact zip bytes before base64url encoding. Patch caps: zip < 25 MiB, each file < 5 MiB, and at most 1000 files.

Worked example shape from a 144-byte single-file zip:

```text
BEGIN_PATCH_BUNDLE
ZIP_BYTE_COUNT 144
ZIP_SHA256 3dce3bc5690138135aca9a04e04973c7f75f36e337e1579bf63230a69fbbd050
BASE64URL UEsDBBQAAAAAAAAAIQCdm2LOGAAAABgAAAALAAAAZXhhbXBsZS50eHRmYXZvcml0ZV9jb2xvciA9ICJibHVlIgpQSwECFAMUAAAAAAAAACEAnZtizhgAAAAYAAAACwAAAAAAAAAAAAAApIEAAAAAZXhhbXBsZS50eHRQSwUGAAAAAAEAAQA5AAAAQQAAAAAA
END_PATCH_BUNDLE
```

Emit exactly one `BEGIN_PATCH_BUNDLE` and exactly one `END_PATCH_BUNDLE`.
````

### Accompanying prompt-instructions text

T2 sends this text with the upload, replacing placeholders. It intentionally repeats the README because the prompt controls the immediate chat turn while the README travels inside the zip.

````text
I uploaded a zip project-context bundle named `{{BUNDLE_FILENAME}}`. First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip. Then complete this task:

{{USER_TASK}}

If no file edits are needed, reply exactly `NO_CHANGES_NEEDED` and nothing else.

If file edits are needed, return exactly one fenced patch bundle. Build a zip containing only changed/added file payloads at repo-root-relative forward-slash paths. Do not return the whole tree. Do not include unchanged files, `ASK_CHATGPT_BUNDLE_README.md`, absolute paths, `..`, backslashes, drive letters, symlinks, or files outside the project root. No `manifest.json` is required for added or modified files; the tool reconstructs per-file metadata from verified zip entries. To delete files, additionally include a top-level `manifest.json` with `status: "deleted"` entries and no deleted-file payloads.

Emit exactly this 5-line marker-block shape and no other patch bundle. Do not wrap it in triple backticks. Do not add commentary inside the block. Use a single space after each key and no colon. Put the `BASE64URL` payload on the same line, one unbroken unpadded base64url token using only `A-Z`, `a-z`, `0-9`, `-`, and `_`; do not use `+`, `/`, or `=`.

BEGIN_PATCH_BUNDLE
ZIP_BYTE_COUNT <decimal byte length of the zip>
ZIP_SHA256 <lowercase 64-hex sha256 of the exact zip bytes>
BASE64URL <unpadded base64url of the zip bytes, one unbroken token on this line>
END_PATCH_BUNDLE

`ZIP_BYTE_COUNT` and `ZIP_SHA256` describe the exact zip bytes before base64url encoding. Patch caps: zip < 25 MiB, each file < 5 MiB, and at most 1000 files.

Worked example:

BEGIN_PATCH_BUNDLE
ZIP_BYTE_COUNT 144
ZIP_SHA256 3dce3bc5690138135aca9a04e04973c7f75f36e337e1579bf63230a69fbbd050
BASE64URL UEsDBBQAAAAAAAAAIQCdm2LOGAAAABgAAAALAAAAZXhhbXBsZS50eHRmYXZvcml0ZV9jb2xvciA9ICJibHVlIgpQSwECFAMUAAAAAAAAACEAnZtizhgAAAAYAAAACwAAAAAAAAAAAAAApIEAAAAAZXhhbXBsZS50eHRQSwUGAAAAAAEAAQA5AAAAQQAAAAAA
END_PATCH_BUNDLE

Emit exactly one bundle per response.
````

## 3. Patch-bundle return format (retrieved by T3)

The canonical assistant-authored return channel is a checksummed fenced base64url block. The retriever still supports legacy/mock Playwright download capture for backward compatibility. It considers only the latest completed assistant turn and must not scan transcript history for older bundles.

### Primary: download-capture zip

The fixture download artifact affordance is `download_artifact`, rendered as `data-testid="mock-download-artifact"`. The parser-facing metadata attributes are `data-filename`, `data-byte-count`, `data-sha256`, and `data-source-turn-id`. The fixture serves the clicked artifact as `Content-Type: application/zip`, `Content-Disposition: attachment`, and `content-length`.

A download artifact is eligible only when it belongs to the latest completed assistant turn (`data-source-turn-id` equals that turn's `data-turn-id`), has parseable decimal `data-byte-count`, has a 64-character lowercase hex `data-sha256`, and is the only eligible artifact for that turn. T3 captures it with Playwright's download API, saves or reads the real zip bytes, verifies actual byte length and SHA-256 against the metadata, then passes the bytes to common validation. Multiple eligible artifacts, duplicate filename collisions, malformed metadata, or a selected artifact that fails validation are failures, not opportunities to guess. If no eligible current-turn artifact exists because downloads are missing, unsupported, delayed beyond the bounded wait, or stale/wrong-turn, T3 may try the fenced fallback in the latest assistant text.

### Fenced: checksummed base64url block

The canonical fixture tokens are:

```text
BEGIN_PATCH_BUNDLE
ZIP_BYTE_COUNT <decimal-byte-count>
ZIP_SHA256 <64-lowercase-hex-sha256>
BASE64URL <unpadded-base64url-zip-bytes>
END_PATCH_BUNDLE
```

The parser must require exactly one complete `BEGIN_PATCH_BUNDLE` ... `END_PATCH_BUNDLE` block in the latest assistant text when using the fenced channel. `ZIP_BYTE_COUNT`, `ZIP_SHA256`, and `BASE64URL` accept the canonical space-separated form and the legacy colon form for backward compatibility. `MANIFEST_JSON` is optional/advisory when present: parse it as a JSON object for diagnostics only and do not cross-check it against the decoded bytes or embedded manifest. The `BASE64URL` payload is canonical inline on its key line; legacy wrapped payload lines after `BASE64URL:` are also tolerated by concatenating remaining lines and stripping whitespace. Missing `END_PATCH_BUNDLE` is `ResponseTruncatedError` before decode. The decoded bytes must have exact length `ZIP_BYTE_COUNT` and exact SHA-256 `ZIP_SHA256`.

If the latest assistant text is exactly `NO_CHANGES_NEEDED` after stripping surrounding whitespace and no eligible patch bundle is present, `ask_chatgpt(files=..., dirs=...)` returns an `AskChatGPTResult` whose `patch_bundle` is `None`. If ordinary explanatory text appears without `NO_CHANGES_NEEDED` and without any valid bundle, retrieval fails with `DownloadUnsupportedError` when the download path is unavailable and no fallback block exists.

## 4. Manifest schema

The embedded `manifest.json` file is optional. If absent, validators reconstruct changed-file entries from the verified zip members and deletions are unsupported. If present, the canonical embedded schema remains `version: 1` because the mock fixture emits `version`, `files`, `total_byte_count`, and per-file `path`, `size`, `sha256`, `status`. The protocol adds the optional `operation` field for add/modify clarity and requires it for deletions, without breaking fixture v1 inputs. Validators must accept fixture-compatible entries with `status: "changed"` and no `operation`; they must reject `status: "unchanged"`.

| Field | Type | Required | Constraints |
| --- | --- | --- | --- |
| `version` | integer | yes | Must equal `1`; other versions are `PatchMalformedError`. |
| `files` | array of objects | yes | Unique `path` values; empty array is allowed only for a no-op patch bundle but producers should use `NO_CHANGES_NEEDED` instead. |
| `total_byte_count` | integer | yes | Sum of `size` for all entries whose `status` is `changed`; deletions contribute zero. |
| `files[].path` | string | yes | Repo-root-relative POSIX path; no absolute form, drive/UNC prefix, backslash, NUL, empty/`.`/`..` component, or reserved metadata path. |
| `files[].status` | string | yes | `changed` or `deleted`; `unchanged` and all other values are rejected. |
| `files[].operation` | string or absent | required for `deleted`, recommended for `changed` | For `changed`, absent, `added`, or `modified`; absent is accepted only for fixture compatibility. For `deleted`, must be `deleted`. |
| `files[].size` | integer | yes | For `changed`, exact uncompressed payload byte length and `0 <= size <= PATCH_BUNDLE_MAX_FILE_BYTES`; for `deleted`, exactly `0`. |
| `files[].sha256` | string or null | yes | For `changed`, exact lowercase 64-hex SHA-256 of payload bytes; for `deleted`, `null`. |
| whole-zip `zip_byte_count` | integer | envelope yes | Exact byte length of the patch zip; provided by download artifact metadata or fenced `ZIP_BYTE_COUNT`, not by embedded `manifest.json`. |
| whole-zip `zip_sha256` | string | envelope yes | Exact lowercase 64-hex SHA-256 of the patch zip; provided by download artifact metadata or fenced `ZIP_SHA256`, not by embedded `manifest.json`. |

For `status: "changed"`, the zip must contain one regular file entry at exactly `path`. If `operation` is absent, validation preserves the fixture-compatible changed file and `apply_patch` reports the diff as `added` when the target did not exist and `modified` when it did. For `status: "deleted"`, the zip must not contain a file entry at `path`; `size` is `0`, `sha256` is `null`, and application unlinks only an existing regular file under the apply root. Unknown top-level manifest keys and unknown per-file keys are rejected after cap checks. Fenced `MANIFEST_JSON`, if present in legacy responses, is advisory and is not cross-checked.

## 5. Validation order and all-or-nothing apply semantics

Validation must complete for the entire bundle before any target-root mutation. T3 must never call `ZipFile.extract` or `extractall`.

1. Identify the latest completed assistant turn and choose a retrieval channel. If exactly one eligible latest-turn download artifact exists, download primary is selected. If no eligible artifact exists, parse the fenced fallback from the latest assistant text. If the response is exactly `NO_CHANGES_NEEDED`, return no patch. No target-root writes occur in this phase.
2. Build an integrity envelope. For download, parse `data-byte-count` and `data-sha256` before clicking. For fenced fallback, require a complete marker block with `ZIP_BYTE_COUNT`, `ZIP_SHA256`, and `BASE64URL`; tolerate the legacy colon form and optional advisory `MANIFEST_JSON`. Missing end markers or incomplete latest turns raise `ResponseTruncatedError`.
3. Enforce prefetch and predecode caps. If declared `zip_byte_count` or download `Content-Length` exceeds `PATCH_BUNDLE_MAX_ZIP_BYTES`, fail before fetching or accepting the body when possible. If fenced base64url character count implies decoded bytes above the cap, fail before decode. Test mode must be able to set `PATCH_BUNDLE_MAX_ZIP_BYTES = 64` for the fixture `oversized` variant.
4. Materialize patch zip bytes into memory only for the validation path. If actual byte length differs from the envelope byte count, raise `BundleIntegrityError`. If actual SHA-256 differs from the envelope digest, raise `BundleIntegrityError`.
5. Open the zip without extracting. Reject invalid central directories, encrypted entries, duplicate names, duplicate `manifest.json`, directory entries other than harmless implicit parent directories, symlinks or special files as indicated by `ZipInfo.external_attr`, and any member whose declared uncompressed size exceeds caps.
6. If embedded `manifest.json` is present, read it only after confirming `ZipInfo.file_size <= PATCH_MANIFEST_MAX_BYTES`; parse it as UTF-8 JSON object and validate field types, required fields, unknown keys, unique paths, `total_byte_count`, status/operation combinations, lowercase hashes, and deletion representation.
7. If embedded `manifest.json` is present, validate the zip-entry set exactly: non-manifest file entries must equal manifest paths with `status: "changed"`; deleted paths must have no zip entry; no extra payloads are allowed. If embedded `manifest.json` is absent, reconstruct changed entries from all non-directory zip members after validating every member path; fail closed if there are zero members.
8. Run lexical path validation for every manifest path and zip entry: reject empty paths, absolute paths, drive/UNC paths, NULs, backslashes, `.` components, `..` components, leading slashes, and reserved metadata paths such as `manifest.json`, `ASK_CHATGPT_BUNDLE_README.md`, and `.ask-chatgpt-tmp/`.
9. Read each changed payload with `ZipFile.open`, after caps and entry-set checks. Let zip CRC validation run; verify `len(bytes) == size`; verify `sha256(bytes) == sha256` when a manifest declares one; sum expanded bytes and fail if the total exceeds `PATCH_BUNDLE_MAX_EXPANDED_BYTES`. CRC/decompression failures are `PatchMalformedError` unless a whole-zip hash mismatch has already been detected.
10. Resolve every patch path against the caller-specified apply root with the containment algorithm in section 6. Reject symlink parents, symlink final targets, non-directory parents, directory targets for file writes/deletions, and non-descendant real paths. Compute the `DiffSummary` against current filesystem state while still performing no mutation.
11. If `dry_run=True`, return the `DiffSummary` and perform no writes, chmods, deletes, directory creation, temp-file creation under root, or journal creation. If `dry_run=False`, only now enter the apply transaction.

Mutation uses a staged transaction with journaled recovery. After validation, create a fresh transaction directory under `<root>/.ask-chatgpt-tmp/apply-<uuid>/`, re-check containment with no-follow operations, write staged new file bytes, backup existing regular targets that will be overwritten or deleted, and write a credential-free journal containing relative paths, operation kinds, old/new hashes, staged paths, and backup paths. Commit each file with same-filesystem atomic `os.replace` for writes and `os.unlink` for deletions; create missing parent directories only after they were validated as non-symlink paths. On any apply error, roll back from backups and remove newly created targets. On CLI startup and before every new apply, detect incomplete journals and roll back or complete the recorded transaction before accepting new work. This does not claim a single atomic multi-file filesystem primitive; it gives validation-time all-or-nothing, ordinary failure rollback, and crash recovery without ever applying unvalidated bytes.

## 6. Zip-slip-safe apply and deletion safety

Containment is realpath-under-root, not string-prefix matching. The apply root is always caller-specified; if it does not exist as a directory, `apply_patch` fails before validation reaches mutation.

```text
root_real = realpath(root)
reject if root_real is not an existing directory
for each manifest rel path:
  reject if rel is empty, contains NUL or backslash, starts with '/', has a Windows drive/UNC form, or any component is '', '.', or '..'
  parts = rel.split('/')
  lexical_target = normpath(join(root_real, *parts))
  reject unless commonpath([root_real, lexical_target]) == root_real
  walk from root_real through parts[:-1] with lstat/openat-style no-follow checks
  reject if an existing parent component is a symlink, a non-directory, or resolves outside root_real
  allow missing parent components only for changed-file writes, and create them only during the post-validation apply transaction as real directories
  if the final target lexists, lstat it without following symlinks
  reject final symlinks and directories for all operations
  reject any final target whose realpath/commonpath would escape root_real
```

Changed-file writes replace or create regular files only after the transaction starts. Deletions unlink only an existing regular file at the resolved target; an already-missing deletion target is treated as idempotently absent and is reported in the diff with `old_sha256=None`, but a symlink, directory, or escaping path is rejected. No deletion ever removes directories recursively.

## 7. Oversize caps

All caps are enforced before expansion where possible and are API/CLI/test overridable. The defaults are intentionally small enough for text-channel fallback and fixture speed, not a claim about real-site limits.

| Constant | Default | Applies where |
| --- | ---: | --- |
| `PATCH_BUNDLE_MAX_ZIP_BYTES` | 25 MiB | Declared and actual patch zip bytes, download `Content-Length`, fenced decoded length. |
| `PATCH_BUNDLE_MAX_FILE_BYTES` | 5 MiB | Each changed file's uncompressed payload size from manifest and zip central directory before reading. |
| `PATCH_BUNDLE_MAX_EXPANDED_BYTES` | 50 MiB | Sum of changed-file uncompressed sizes, zip-bomb guard before payload reads complete. |
| `PATCH_MANIFEST_MAX_BYTES` | 1 MiB | Embedded `manifest.json` and optional advisory fenced `MANIFEST_JSON` line before JSON parse. |
| `PATCH_BUNDLE_MAX_BASE64URL_CHARS` | derived from `PATCH_BUNDLE_MAX_ZIP_BYTES` as `ceil(max_zip * 4 / 3) + 4` | Fenced text guard before base64url decode. |
| `PATCH_BUNDLE_MAX_FILE_COUNT` | 1000 | Manifest entries and zip payload entries. |
| `UPLOAD_BUNDLE_MAX_ZIP_BYTES` | 25 MiB | Outgoing zip preflight before UI upload. |
| `UPLOAD_BUNDLE_MAX_FILE_BYTES` | 5 MiB | Each outgoing selected regular file before reading into bundle. |
| `UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES` | 50 MiB | Sum of outgoing selected file bytes before zip creation. |

If a cap is exceeded, raise `OversizedPayloadError` before reading more bytes, decoding more base64, or expanding more zip members. Do not trust assistant-provided advisory fields such as the fixture's `oversized_threshold_bytes`; use configured policy caps.

## 8. Failure taxonomy to named errors

All named errors extend `AskChatGPTError`. New validation errors should share a new base `PatchBundleValidationError(AskChatGPTError)` so the CLI can map them together, while preserving concrete error names for tests and user action.

| Failure | Named error | Existing in `errors.py`? | Actionable message rule |
| --- | --- | --- | --- |
| Upload input absent, upload UI unsupported, or UI rejects file size/type after local preflight passed | `UploadUnsupportedError` | yes | Keep credential-free default; detail may include `reason=file size/type rejected by UI` and upload basename only. |
| Upload mock records a SHA-256 different from the local outgoing zip SHA-256 | `BundleIntegrityError` subclass of `PatchBundleValidationError` | new | Transfer integrity failed; retry upload or reduce bundle; no local files were changed. |
| No eligible latest-turn download and no valid fenced fallback; download unsupported affordance present | `DownloadUnsupportedError` | yes | Use text-channel fallback or inspect UI support; no local files were changed. |
| Missing `END_PATCH_BUNDLE`, incomplete latest turn, or transport body shorter than a trusted declared length | `ResponseTruncatedError` | yes | Retry or reduce payload; no local files were changed. |
| Malformed fenced block, invalid base64 alphabet, invalid JSON/schema, invalid zip central directory, encrypted zip, duplicate entries, missing/extra zip entries, collision artifact, stale wrong-turn artifact without fallback, `status: "unchanged"`, unknown manifest fields | `PatchMalformedError` subclass of `PatchBundleValidationError` | new | Patch bundle is malformed or not a changed-files patch; request a fresh patch bundle; no local files were changed. |
| Whole-zip byte count mismatch, whole-zip SHA-256 mismatch, per-file size mismatch, per-file SHA-256 mismatch | `BundleIntegrityError` subclass of `PatchBundleValidationError` | new | Retry transfer or alternate return channel; no local files were changed. |
| Declared, encoded, compressed, manifest, per-file, expanded, or outgoing upload cap exceeded | `OversizedPayloadError` subclass of `PatchBundleValidationError` | new | Reduce selected files, split patch, or raise an explicit limit; no local files were changed. |
| Absolute path, traversal, drive/UNC path, backslash path, root sibling-prefix trap, symlink parent, symlink final target, non-descendant real path | `PathEscapeError` subclass of `PatchBundleValidationError` | new | Reject bundle and request root-relative file paths; no local files were changed. |
| Post-validation apply I/O failure, local conflict detected during transaction, rollback failure, or unrecoverable incomplete journal | `PatchApplyError` | new | Inspect local filesystem and transaction journal; validation succeeded but requested mutation could not be completed safely. |

Error details must never include credentials, cookies, session tokens, browser-profile contents, full external URLs, or arbitrary file contents. Relative project paths, byte counts, hashes, cap names, and safe phase names are allowed.

## 9. Adversarial handling matrix

This table is the mandatory T3 test list. All failures leave the caller root unchanged unless explicitly in a post-validation `PatchApplyError` scenario.

| Fixture area and variant | Expected outcome |
| --- | --- |
| download `missing` | No artifact is eligible; parse fenced fallback if present and valid; otherwise raise `DownloadUnsupportedError`. |
| download `delayed` | Poll/reload within a bounded wait until the artifact appears; if it appears, validate normally; on timeout parse fallback if valid, otherwise raise `DownloadUnsupportedError`. |
| download `wrong_older` | Reject artifact whose `data-source-turn-id` is not the latest turn id; parse fallback if valid; without fallback raise `PatchMalformedError` for stale artifact. |
| download `corrupt` | Metadata may match corrupt bytes, but zip open fails; raise `PatchMalformedError`. |
| download `truncated` | Fixture metadata matches a non-zip truncated body, so zip open fails; raise `PatchMalformedError`; if a future transport body is shorter than a trusted declared length, use `ResponseTruncatedError` or `BundleIntegrityError` according to the failed check. |
| download `collision` | Multiple same-turn artifacts or duplicate filenames are ambiguous; raise `PatchMalformedError`, do not choose one. |
| download `unsupported` | Use fenced fallback if present and valid; otherwise raise `DownloadUnsupportedError`. |
| fenced `missing_end` | Raise existing `ResponseTruncatedError` before base64 decode. |
| fenced `bad_hash` | `ZIP_SHA256` does not match decoded zip bytes; raise `BundleIntegrityError`. |
| fenced `changed_and_unchanged` | Manifest contains `status: "unchanged"` without payload; raise `PatchMalformedError`. |
| fenced `oversized` | With test override `PATCH_BUNDLE_MAX_ZIP_BYTES = 64`, raise `OversizedPayloadError` before decode/expand; ignore assistant advisory threshold fields as policy. |
| upload `unsupported` | Upload input is absent/unsupported; raise existing `UploadUnsupportedError`. |
| upload `reject_size_type` | If local preflight exceeded a configured upload cap, raise `OversizedPayloadError` before UI interaction; otherwise the fixture rejection maps to existing `UploadUnsupportedError` with safe reason. |
| upload `corrupt` | Mock-recorded upload SHA-256 differs from local expected SHA-256; raise `BundleIntegrityError` and do not proceed to prompt/patch apply. |

## 10. Public API surface (T4 wires it)

The UC1 behavior is preserved exactly: when no non-empty `files` or `dirs` are supplied, `ask_chatgpt(...)` returns a plain `str` and existing parameters keep their current semantics. UC2 adds keyword-only parameters at the end and returns a result object only when at least one file or directory is supplied.

```python
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Pathish = str | Path
PatchSource = Literal["download", "fenced"]

@dataclass(frozen=True, slots=True)
class PatchBundle:
    filename: str
    content: bytes
    sha256: str
    byte_count: int
    source: PatchSource

@dataclass(frozen=True, slots=True)
class AskChatGPTResult:
    text: str
    patch_bundle: PatchBundle | None

def ask_chatgpt(
    prompt: str,
    *,
    session_identifier: str | None = None,
    model_settings: dict[str, Any] | None = None,
    channel: str = "real",
    base_url: str | None = None,
    profile_path: str | Path | None = None,
    registry: SessionRegistry | None = None,
    reader_order: Iterable[ResponseReader] | None = None,
    timeout_s: float = 30.0,
    files: Sequence[Pathish] | None = None,
    dirs: Sequence[Pathish] | None = None,
    bundle_root: str | Path | None = None,
) -> str | AskChatGPTResult:
    ...
```

`PatchBundle` is an opaque, unapplied handle accepted by `apply_patch`; callers should not extract it themselves. `patch_bundle is None` means GPT intentionally produced the exact no-edit sentinel `NO_CHANGES_NEEDED`. Retrieval failures raise named errors rather than returning `None`.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PatchBundleSource = PatchBundle | bytes | str | Path
ChangeKind = Literal["added", "modified", "deleted"]

@dataclass(frozen=True, slots=True)
class FileDiff:
    path: str
    change_kind: ChangeKind
    old_sha256: str | None
    new_sha256: str | None
    old_bytes: int | None
    new_bytes: int | None
    byte_delta: int
    lines_added: int | None
    lines_deleted: int | None

@dataclass(frozen=True, slots=True)
class DiffSummary:
    root: Path
    dry_run: bool
    files: tuple[FileDiff, ...]
    added: int
    modified: int
    deleted: int
    total_files: int
    total_byte_delta: int
    total_bytes_changed: int

def apply_patch(
    bundle: PatchBundleSource,
    root: str | Path,
    *,
    dry_run: bool = True,
) -> DiffSummary:
    ...
```

`root` has no default. `dry_run=True` is the library default and must perform full validation and diff computation without creating, modifying, deleting, chmodding, replacing, or journaling anything under `root`. `dry_run=False` performs the same validation first, then uses the transaction in section 5. `bytes` input to `apply_patch` is interpreted as raw patch zip bytes with computed local whole-zip metadata; `str`/`Path` input is read as a patch zip file path and then validated the same way. Public `ask_chatgpt.__init__` exports must include `ask_chatgpt`, `AskChatGPTResult`, `PatchBundle`, `apply_patch`, `DiffSummary`, `FileDiff`, `PatchBundleValidationError`, `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`, and `PatchApplyError`, plus all existing errors.

## 11. CLI (UC3, T5)

`pyproject.toml` must add:

```toml
[project.scripts]
ask-chatgpt = "ask_chatgpt.cli:main"
```

The CLI is library-first: it parses arguments, rejects usage errors before browser/upload side effects, calls `ask_chatgpt(...)`, optionally calls `apply_patch(...)`, formats output, and maps exceptions to exit codes. It must not contain private bundle walking, manifest validation, path containment, symlink handling, diff computation, or file-write logic that the library lacks.

| Flag/argument | Type/default | Semantics |
| --- | --- | --- |
| `prompt` | optional positional string | Prompt text. Mutually exclusive with `--prompt`; one of the two prompt forms is required. |
| `--prompt TEXT` | optional string | Prompt text as an option for awkward shell quoting. |
| `--session ID` | optional string | Passes `session_identifier=ID`. |
| `--model-settings JSON` | optional JSON object string | Parsed as a dictionary and passed as `model_settings`; invalid JSON or non-object JSON is usage error. |
| `--files PATH` | repeatable path | Appends a file to the outgoing bundle selection; requires UC2 result mode when at least one file/dir is supplied. |
| `--dirs PATH` | repeatable path | Appends a directory to recursively expand into the outgoing bundle. |
| `--out FILE` | optional path | Writes assistant response text to `FILE` instead of stdout. In `--dry-run`/`--apply` modes, stdout remains reserved for JSON diff summary, so `--out` is the only way to preserve assistant text. |
| `--dry-run` | boolean, mutually exclusive with `--apply` | Requires at least one `--files`/`--dirs` path and explicit `--root`; retrieves a patch bundle and calls `apply_patch(..., dry_run=True)`. |
| `--apply` | boolean, mutually exclusive with `--dry-run` | Requires at least one `--files`/`--dirs` path and explicit `--root`; retrieves a patch bundle and calls `apply_patch(..., dry_run=False)`. This is the only local-mutation flag. |
| `--root DIR` | optional path, required for `--dry-run` and `--apply` | Apply root passed to `apply_patch`; in apply/dry-run modes it is also passed as `bundle_root` so outgoing and incoming paths share one root. It is never inferred from cwd for mutation modes. |
| `--channel {real,mock}` | string, default `real` | Browser channel passed to `ask_chatgpt`; automated tests use `mock` with loopback `--base-url` and never set `real`. |
| `--base-url URL` | optional string | Passed through for mock/local fixtures. |
| `--profile-path PATH` | optional path | Browser profile path passed through; CLI never inspects credentials, cookies, or profile contents. |
| `--timeout SECONDS` | float, default `30.0` | Completion timeout passed as `timeout_s`. |

No mutation without explicit `--apply`: default ask mode never calls `apply_patch(..., dry_run=False)`, and `--dry-run` validates/diffs without writes. `--apply` without `--root` is a usage error before any network/browser/upload action. `--dry-run` is not the default ask mode; it specifically means retrieve a patch bundle and print a diff summary without applying it.

Stdout/stderr conventions: default ask mode writes assistant response text, and only that text, to stdout unless `--out` is set; diagnostics, progress, and errors go to stderr. In `--dry-run` or `--apply` mode, stdout is a stable JSON object matching `DiffSummary`; assistant text is written only when `--out` is set. All error diagnostics are concise, credential-free, and omit cookies, session tokens, profile contents, and arbitrary file contents.

| Exit code | Meaning |
| ---: | --- |
| `0` | Success. |
| `2` | CLI usage error: bad flags, both prompt forms, missing prompt, invalid `--model-settings`, `--apply`/`--dry-run` without `--root`, no file paths for patch mode, or mutually exclusive flags. |
| `3` | `LoginRequiredError`. |
| `4` | `SessionNotFoundError`. |
| `5` | `ModelUnavailableError`. |
| `6` | `RateLimitedError`. |
| `7` | `ResponseTruncatedError`. |
| `8` | `SelectorUnavailableError`. |
| `9` | `UploadUnsupportedError`. |
| `10` | `DownloadUnsupportedError`. |
| `11` | `PatchBundleValidationError` and subclasses: `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`. |
| `12` | `PatchApplyError`. |
| `1` | Other `AskChatGPTError` or unexpected uncaught failure after a safe diagnostic. |

## 12. Rationale and reconciled conflicts

Real-site ground truth beats the earlier fixture-only format. The canonical fenced block uses literal `BEGIN_PATCH_BUNDLE`, `END_PATCH_BUNDLE`, space-separated `ZIP_BYTE_COUNT`, `ZIP_SHA256`, and inline `BASE64URL`; the parser keeps the legacy colon form and optional advisory `MANIFEST_JSON` for backward compatibility.

Manifest version stays `1`, not the integrity lens's proposed canonical `version: 2`, because the fixture and acceptance tests emit `version: 1` with `status: "changed"`. The minimal compatible refinement is to keep v1 core fields and add optional `operation` for add/modify/delete clarity. Validators accept missing `operation` only for fixture-compatible changed files and reject `status: "unchanged"`.

Deletion uses a manifest tombstone, not a fake zip payload: `status: "deleted"`, `operation: "deleted"`, `size: 0`, `sha256: null`, and no zip entry. This matches how absence must be represented in a changed-files-only zip and keeps deletion validation simple.

Download primary is honored, but fallback is used only when no eligible latest-turn artifact exists. If one eligible artifact is selected and its bytes are malformed or fail integrity, T3 fails instead of silently switching channels, because GPT was instructed to emit exactly one bundle and a corrupt primary is not safely equivalent to absence.

Whole-zip integrity is an envelope, not embedded self-reference. The embedded `manifest.json` omits `zip_byte_count` and `zip_sha256`; download metadata or fenced labels carry those values. Fenced `MANIFEST_JSON`, if present in legacy responses, is advisory only and is not compared to the embedded manifest.

The public API adds `bundle_root` as an optional UC2 keyword while preserving UC1 return type exactly. This resolves the ergonomics open question about deterministic repo-relative paths without forcing existing UC1 callers to change.

Dry-run is the default for `apply_patch`, and the CLI mutates only with `--apply`. This follows the safety lens and ergonomics lens over any convenience design that would infer cwd and write by default.

Apply uses validation plus a journaled staged transaction rather than claiming impossible multi-file atomicity. POSIX can atomically replace one file, not an arbitrary tree; the selected design gives no-mutation-on-validation-failure, rollback on ordinary apply errors, and recovery from incomplete journals.

The generated README path is reserved. Rejecting a selected project file named `ASK_CHATGPT_BUNDLE_README.md` is simpler and safer than escaping metadata into a second namespace for the first implementation.
