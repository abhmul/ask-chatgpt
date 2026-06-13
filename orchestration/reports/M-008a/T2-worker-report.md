# M-008a / T2 worker report

STATUS: DONE

## Files changed

- `src/ask_chatgpt/bundle.py`: rewrote both GPT-facing bundle templates to request one actual downloadable `.zip` file plus a download link; removed all model-facing fallback/encoded-block wording; kept the parser fallback untouched elsewhere.
- `docs/bundle-protocol.md`: made downloadable `.zip` the documented primary return mechanism, updated §2 template duplicates to match `bundle.py` exactly, kept the parser-facing fallback token spec only in the retrieval/fallback documentation, and updated lifecycle/rationale wording.
- `tests/test_bundle_out.py`: replaced the old protocol-token presence assertions with a falsifiable guard that checks both generated model-facing outputs have no fallback terms and do request a downloadable `.zip` file/download link.

## Rewritten `_PROMPT_INSTRUCTIONS_TEMPLATE`

````text
I uploaded a zip project-context bundle named `{{BUNDLE_FILENAME}}`. First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip. Then complete this task:

{{USER_TASK}}

If no file edits are needed, reply exactly `NO_CHANGES_NEEDED` and nothing else. Do not create a downloadable file in that case.

If file edits are needed, create exactly one actual downloadable `.zip` file and provide the download link to that file in your reply. Use your file/output tools to create the `.zip`; do not represent the patch as inline text. The `.zip` file is the patch bundle.

The `.zip` must contain only changed or added file payloads at repo-root-relative forward-slash paths, with no wrapping directory. Do not return the whole tree. Do not include unchanged files, `ASK_CHATGPT_BUNDLE_README.md`, absolute paths, `..`, backslashes, drive letters, symlinks, or files outside the project root.

A top-level `manifest.json` is optional for added or modified files; the tool reconstructs per-file metadata from verified zip entries after checking the whole-zip SHA-256. If you must delete files, additionally include a top-level `manifest.json` with deletion entries and omit payloads for deleted paths.

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

Patch caps: zip < 25 MiB, each file < 5 MiB, and at most 1000 files.

Return exactly one downloadable `.zip` file per response.
````

## Rewritten download-return section of `_CATALOGUE_TEMPLATE`

````markdown
## If no edits are needed

If the correct response requires no file changes, reply exactly:

```text
NO_CHANGES_NEEDED
```

Do not create a downloadable file in that case.

## If edits are needed: create one downloadable patch `.zip`, not the whole tree

Create exactly one actual downloadable `.zip` file and provide the download link to that file in your reply. Use your file/output tools to create the `.zip`; do not represent the patch as inline text. The `.zip` file is the patch bundle.

The `.zip` must contain only changed or added file payloads at repo-root-relative forward-slash paths, with no wrapping directory. Do not include unchanged files. Do not include this instruction file. Do not include the whole project tree. Do not include `ASK_CHATGPT_BUNDLE_README.md`, absolute paths, `..`, backslashes, drive letters, symlinks, or paths outside the project root.

A top-level `manifest.json` is optional for added or modified files; the tool reconstructs per-file metadata from verified zip entries after checking the whole-zip SHA-256. If you must delete files, additionally include a top-level `manifest.json` with deletion entries and omit payloads for deleted paths.

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

Patch caps: zip < 25 MiB, each file < 5 MiB, and at most 1000 files.

When your reply is complete, it should expose exactly one download link for the `.zip` file. Do not return multiple archives, separate changed files, a wrapping directory, or inline payload content.
````

## Adversarial self-review

- `_PROMPT_INSTRUCTIONS_TEMPLATE`: The old escape hatch was removed; there is no fallback format for the model to copy into chat. The wording predetermines either the exact `NO_CHANGES_NEEDED` sentinel or one created `.zip` artifact with a download link. Misread risks left: a model might still try to summarize changes or say it cannot create files, but the prompt directly says to use file/output tools, not inline text, and to return exactly one downloadable `.zip` file per response. The no-edits branch is the only legitimate file-avoidance path.
- `_CATALOGUE_TEMPLATE` download-return section: The in-zip instructions now reinforce the same outcome after the model opens the uploaded archive. Misread risks left: a model might include a wrapping directory, unchanged files, or a manifest for all cases; the section explicitly bans wrapping dirs/unchanged files and says `manifest.json` is optional for add/modify but required for deletions. Nothing in the section offers an encoded/text alternative, so the expected outcome is a real downloadable `.zip` plus one download link.

## Evidence / success criteria

1. Bundle templates rewritten and free of model-facing fallback terms. Grep proof:

```text
$ grep -niE 'base64|begin_patch_bundle|end_patch_bundle|fenced' src/ask_chatgpt/bundle.py
# no output
```

2. Guard test present and passing: `tests/test_bundle_out.py::test_model_facing_bundle_outputs_request_downloadable_zip_without_parser_fallback_terms` asserts both `generate_prompt_instructions(...)` and `generate_catalogue_readme(...)` have none of `base64`, `base64url`, `begin_patch_bundle`, `end_patch_bundle`, `fenced`, `marker block`, `5-line block`, or `paste`, and both mention a downloadable `.zip` file plus a download link. Confirmed it would fail against the old templates by read-only `git show HEAD:src/ask_chatgpt/bundle.py | grep -niE 'base64|begin_patch_bundle|end_patch_bundle|fenced'`, which shows old template hits including `BASE64URL`, `BEGIN_PATCH_BUNDLE`, `END_PATCH_BUNDLE`, and `fenced`; `git show HEAD:src/ask_chatgpt/bundle.py | grep -ni 'download link'` had no output.

3. Documentation aligned: `docs/bundle-protocol.md` §1 lifecycle now names downloadable `.zip`/download link first; §2 templates match `bundle.py`; §3 documents download-capture zip as primary and the encoded text block only as parser fallback; §12 rationale says model-facing templates do not surface fallback tokens. Exact-match check:

```text
catalogue match: True
prompt match: True
```

4. Mock UC2 round-trip is green via both paths: `tests/test_uc2_roundtrip.py::test_uc2_roundtrip_download_primary_public_api_dry_run_and_apply` covers upload -> mock `.zip` download affordance -> `source == "download"` -> validate -> dry run -> apply -> diff match; `tests/test_uc2_roundtrip.py::test_uc2_roundtrip_fenced_fallback_public_api_dry_run_and_apply` keeps the parser fallback round-trip green. Targeted run also included `tests/test_patch.py` and passed: `59 passed in 17.09s`.

5. Safety invariants preserved: `git diff -- src/ask_chatgpt/patch.py` has no output, so fenced parser/retrieval logic was not edited. Zip-slip and validate-before-mutate coverage remains in `tests/test_patch.py::test_bare_zip_unsafe_member_paths_rejected_before_write`, `test_zip_slip_absolute_path_raises_path_escape_and_writes_nothing_outside`, `test_zip_slip_parent_traversal_raises_path_escape_and_writes_nothing_outside`, and `test_zip_slip_symlink_parent_escape_raises_path_escape_and_writes_nothing_outside`; dry-run-default remains covered by `tests/test_patch.py::test_dry_run_returns_diff_summary_and_writes_nothing`, which calls `apply_patch(bundle, apply_root)` and asserts `dry_run is True`. Real selector stayed fail-closed: `src/ask_chatgpt/selector_maps/real.json:20:    "download_artifact": "",`.

6. Full suite is green with real tier deselected by default and no real-site env set:

```text
203 passed, 1 deselected in 61.86s (0:01:01)
```

## Telemetry

ESTIMATE: T2 75m
ACTUAL: T2 80m
REWORK-CAUSE: One targeted test assertion expected capitalized prompt wording; fixed the assertion to match the actual sentence without changing functionality.
END: 2026-06-13T10:23:11-05:00
