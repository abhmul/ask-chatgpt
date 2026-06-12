ESTIMATE: T1a 45m
START_TIMESTAMP: 2026-06-12T02:04:19-05:00
LENS: gpt-interaction

## Fixture-grounded tokens and fields

- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:87-96` manifest file entries use `"path"`, `"size"`, `"sha256"`, `"status": "changed"`; the top-level manifest uses `"version": 1`, `"files"`, and `"total_byte_count"`.
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:101-103` the zip contains `manifest.json` and then file payloads at their repo-relative paths; unchanged adversarial entries are not written to the zip.
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:114-127` fenced fallback augments the manifest with `"zip_byte_count"` and `"zip_sha256"`, then emits literal lines `"BEGIN_PATCH_BUNDLE"`, `"MANIFEST_JSON: "`, `"ZIP_BYTE_COUNT: "`, `"ZIP_SHA256: "`, and `"BASE64URL:"`.
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:131-132` the closing marker is literal `"END_PATCH_BUNDLE"` unless the `missing_end` adversarial variant is requested.
- `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_files.py:63-79` the fixture parser splits on `BEGIN_PATCH_BUNDLE` / `END_PATCH_BUNDLE`, searches lines starting `MANIFEST_JSON:`, `ZIP_BYTE_COUNT:`, `ZIP_SHA256:`, requires a standalone `BASE64URL:` line, joins subsequent non-empty lines, pads, and base64url-decodes.
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:29-31` names fenced variants `ok`, `missing_end`, `bad_hash`, `changed_and_unchanged`, `oversized` and download variants `ok`, `missing`, `delayed`, `wrong_older`, `corrupt`, `truncated`, `collision`, `unsupported`.
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:852-855` download artifacts expose `data-testid="mock-download-artifact"`, `data-filename`, `data-byte-count`, `data-sha256`, and `data-source-turn-id`; `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py:923` upload input exposes `data-testid="mock-upload-input"`.

## Full catalogue README content/template

Recommended generated filename inside the outgoing zip: `ASK_CHATGPT_BUNDLE_README.md` at archive root. It is metadata, not a project file; GPT must never include it in a patch bundle unless explicitly asked to edit that metadata file.

````markdown
# ask-chatgpt bundle instructions

Read this file first. This zip is a project-context bundle prepared by `ask-chatgpt` so you can answer the user using local files and, if needed, return edits as a machine-readable patch bundle.

## Project root and path rules

The archive root represents the project root named `{{PROJECT_ROOT_NAME}}`. Every project file path below is repo-root-relative. Use forward slashes only. Never use absolute paths, drive letters, leading `/`, backslashes, empty path segments, or `..`. Treat paths as case-sensitive. Patch bundles may contain only regular file entries plus `manifest.json`; do not create symlinks or special files.

## Bundle identity

- Bundle id: `{{BUNDLE_ID}}`
- Created at: `{{CREATED_AT_ISO8601}}`
- Project root display name: `{{PROJECT_ROOT_NAME}}`
- Included file count: `{{FILE_COUNT}}`
- Included payload bytes: `{{TOTAL_BYTES}}`

## Included file inventory

Directories supplied by the caller were expanded recursively. The table lists every included project file; empty directories are not represented. `Path` is the canonical path to use in discussion and patch bundles. `Zip entry` is where the file appears inside this archive. `Size` is decimal bytes. `SHA-256` is lowercase hex of the included file bytes.

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

Do not attach a zip and do not emit a fenced patch bundle in that case.

## If edits are needed: return a patch bundle, not the whole tree

Return exactly one patch bundle containing only changed paths and `manifest.json`. Do not include unchanged files. Do not include this instruction file. Do not include the whole project tree.

Example: if you change `src/app.py`, add `tests/test_app.py`, and leave `README.md` unchanged, the patch zip must contain:

```text
manifest.json
src/app.py
tests/test_app.py
```

It must not contain `README.md`.

## Patch zip manifest

Every patch zip must contain top-level `manifest.json` encoded as UTF-8 JSON. Use this schema, keeping the fixture-compatible fields `version`, `files`, `total_byte_count`, `path`, `size`, `sha256`, and `status`:

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

For added and modified files, include the new file bytes in the zip at exactly `path`, set `status` to `changed`, set `operation` to `added` or `modified`, set `size` to the byte length, and set `sha256` to the lowercase SHA-256 of the included bytes. For deleted files, do not include a file payload, set `status` and `operation` to `deleted`, set `size` to `0`, and set `sha256` to `null`. `total_byte_count` is the sum of byte sizes for added and modified payloads; deletions contribute zero. Do not use `status: "unchanged"` in real patch bundles.

## Response channel priority

Primary/preferred: produce a downloadable `.zip` file named `patch-bundle.zip` containing the patch zip described above. If you provide a downloadable zip, do not also emit the fallback text block. In the chat message body, write only:

```text
PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip
```

Fallback: if you cannot produce a downloadable `.zip`, emit the same zip bytes as one base64url marker block. The marker block must be the only patch bundle in the response. Do not wrap it in Markdown triple backticks; the `BEGIN_PATCH_BUNDLE` and `END_PATCH_BUNDLE` lines are the fence. Do not put commentary inside the block. Use unpadded base64url (`A-Z`, `a-z`, `0-9`, `-`, `_`), preferably on one line.

Exact fallback format:

```text
BEGIN_PATCH_BUNDLE
MANIFEST_JSON: {"files":[{"operation":"modified","path":"src/example.py","sha256":"<sha256-of-new-bytes>","size":123,"status":"changed"}],"total_byte_count":123,"version":1,"zip_byte_count":456,"zip_sha256":"<sha256-of-zip-bytes>"}
ZIP_BYTE_COUNT: 456
ZIP_SHA256: <sha256-of-zip-bytes>
BASE64URL:
<unpadded-base64url-of-the-zip-bytes>
END_PATCH_BUNDLE
```

`MANIFEST_JSON` must be compact JSON on the same line. Its `zip_byte_count` and `zip_sha256` must match `ZIP_BYTE_COUNT`, `ZIP_SHA256`, and the decoded zip bytes. Emit exactly one `BEGIN_PATCH_BUNDLE` and exactly one `END_PATCH_BUNDLE`.
````

Delta note: `operation` and deletion semantics are refinements beyond the current fixture's happy-path `status: "changed"`; they are backward-compatible if the parser treats missing `operation` plus `status: "changed"` as a generic modified/changed file.

## Full accompanying prompt-instructions text

This intentionally repeats the README because the prompt controls immediate behavior in the chat turn, while the README travels with the zip and remains available after upload/download UI steps.

````text
I uploaded a zip project-context bundle named `{{BUNDLE_FILENAME}}`. First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip. Then complete this task:

{{USER_TASK}}

If no file edits are needed, reply exactly `NO_CHANGES_NEEDED` and nothing else.

If file edits are needed, return exactly one patch bundle. The patch bundle must contain only `manifest.json` plus added or modified file payloads at repo-root-relative paths. Do not return the whole tree. Do not include unchanged files. Do not include absolute paths, `..`, backslashes, symlinks, or files outside the project root.

Preferred response channel: attach or produce a downloadable zip named `patch-bundle.zip`. In the message body, write only `PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip`. Do not also include the base64 fallback if a downloadable zip is available.

Fallback response channel, only if no downloadable zip can be produced: emit exactly this marker-block shape and no other patch bundle. Do not wrap it in triple backticks. Do not add commentary inside the block.

BEGIN_PATCH_BUNDLE
MANIFEST_JSON: {"files":[{"operation":"modified","path":"src/example.py","sha256":"<sha256-of-new-bytes>","size":123,"status":"changed"}],"total_byte_count":123,"version":1,"zip_byte_count":456,"zip_sha256":"<sha256-of-zip-bytes>"}
ZIP_BYTE_COUNT: 456
ZIP_SHA256: <sha256-of-zip-bytes>
BASE64URL:
<unpadded-base64url-of-the-zip-bytes>
END_PATCH_BUNDLE

For added files use `status: "changed"` and `operation: "added"`; for modified files use `status: "changed"` and `operation: "modified"`; for deletions use `status: "deleted"`, `operation: "deleted"`, `size: 0`, `sha256: null`, and omit the deleted file payload from the zip. Compute sizes and hashes from the actual bytes in the patch zip. Emit exactly one bundle per response.
````

## Compliance rationale

| Instruction | Why it improves parseability/compliance |
| --- | --- |
| Generated README has a reserved name and says read first. | Avoids collision with project `README.md` and gives the model a stable local contract even if the chat prompt is separated from the upload. |
| Inventory table uses repo-root-relative `Path`, `Zip entry`, byte size, and SHA-256. | Gives GPT unambiguous names and lets later validation distinguish stale or hallucinated content. |
| Forward slashes, no absolute paths, no `..`, no symlinks. | Aligns model output with path-safety rejection before apply and reduces ambiguous OS-specific paths. |
| `NO_CHANGES_NEEDED` exact singleton response. | Lets the tool distinguish intentional no-op from a missing/failed bundle without NLP. |
| Patch zip contains only changed payloads plus `manifest.json`. | Matches UC2 acceptance and avoids reapplying stale unchanged files or bloating fallback text. |
| `status: "changed"` retained for added/modified files. | Preserves fixture ground truth while `operation` supplies human/model clarity for add vs modify. |
| Deletions represented only in manifest. | A zip cannot contain absence; explicit tombstone entries make deletion machine-readable without fake files. |
| Download primary with a one-line body. | Lets Playwright capture a real zip and gives a minimal textual sentinel without mixing channels. |
| Fallback markers and line labels copied exactly from fixture. | Parser can split deterministically on fixed tokens and validate byte count/hash before applying. |
| No Markdown triple backticks around fallback. | Prevents fence characters from being accidentally captured as base64 payload or surrounding text. |
| Exactly one bundle per response. | Avoids choosing among stale/colliding artifacts, a fixture-covered failure mode. |

## Open questions for synthesis

1. Integrity lens must decide the final deletion schema: `sha256: null` is clean but requires validator support; alternatives are omitting `sha256` for deletions or using a manifest-only tombstone convention.
2. Parser should explicitly reject `status: "unchanged"` in real outputs even though the fixture can emit `changed_and_unchanged` to test validator behavior.
3. Download-primary ergonomics may need a less strict body line if real ChatGPT insists on adding natural-language text around file artifacts; the retrieval code should anchor artifact identity to latest turn/download metadata, not only text.
4. Need a policy for rare collision if the project already has `ASK_CHATGPT_BUNDLE_README.md`; likely reserve `.ask-chatgpt/` metadata or escape generated metadata outside the project path namespace.
5. Fenced fallback size limit/line wrapping should be capped by integrity/CLI design; this lens recommends one base64url line but parser can safely join non-empty lines after `BASE64URL:` as fixture tests do.

END_TIMESTAMP: 2026-06-12T02:06:59-05:00
T1a-STATUS: DONE
