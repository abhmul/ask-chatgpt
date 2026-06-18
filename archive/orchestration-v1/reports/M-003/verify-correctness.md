ESTIMATE: T7b 25m
LENS: correctness-reproduction
START_TIMESTAMP: 2026-06-12T04:01:35-05:00

CHECK 1: PASS
Raw suite evidence matches T7a: `tmp/verify-m003/pytest.txt:4` is exactly `119 passed in 43.37s`. The raw file shows only progress dots plus this pass summary, with no failure/error summary.

CHECK 2: PASS
Newest UC2 artifact inspected: `tmp/accept-uc2-20260612-034717/results.json`; raw `tmp/verify-m003/accept_uc2.txt` points to the same `results_json=tmp/accept-uc2-20260612-034717/results.json` and `overall=pass`.
Top-level reproduction: `tmp/accept-uc2-20260612-034717/results.json:2` says `"overall": "pass"`.
Download-primary step: `results.json:131-132` says `"name": "download-primary-roundtrip"` and `"status": "pass"`; `results.json:13/24/35` show `"change_kind": "deleted"`, `"added"`, `"modified"`; `results.json:54-65` show `"added_matches": true`, `"added_text": "brand new file\n"`, `"deleted_absent": true`, `"modified_matches": true`, `"modified_text": "new app contents\nsecond line\n"`, `"overall_diff_matches": true`, `"unchanged_matches": true`, and `"unchanged_path": "README.md"`.
Fenced-fallback step: `results.json:261-262` says `"name": "fenced-fallback-roundtrip"` and `"status": "pass"`; `results.json:143/154/165` show `"change_kind": "deleted"`, `"added"`, `"modified"`; `results.json:184-195` repeat `"added_matches": true`, `"added_text": "brand new file\n"`, `"deleted_absent": true`, `"modified_matches": true`, `"modified_text": "new app contents\nsecond line\n"`, `"overall_diff_matches": true`, `"unchanged_matches": true`, and `"unchanged_path": "README.md"`.
Direct artifact spot-check agreed: both applied trees have `src/app.txt` content `new app contents\nsecond line\n`, `src/added.txt` content `brand new file\n`, `docs/` empty, and `README.md` content `leave this file unchanged\n`.

CHECK 3: PASS
Newest UC3 artifact inspected: `tmp/accept-uc3-20260612-034726/results.json`; raw `tmp/verify-m003/accept_uc3.txt` points to the same results file and `overall=pass`.
Top-level reproduction: `tmp/accept-uc3-20260612-034726/results.json:2` says `"overall": "pass"`.
Prompt-to-stdout step: `results.json:6-7` says `"detail": "prompt call printed only assistant text"` and `"returned_text": "accept UC3 prompt response"`; `results.json:26` says `"stdout": "accept UC3 prompt response"`; `results.json:31-32` says `"name": "prompt-stdout"`, `"status": "pass"`.
`--out` file-write step: `results.json:36-38` says `"detail": "--out wrote assistant text and left stdout empty"`, `"out_file": "tmp/accept-uc3-20260612-034726/assistant-out.txt"`, and `"returned_text": "accept UC3 out-file response"`; `results.json:60` says `"stdout": ""`; `results.json:65-66` says `"name": "out-file"`, `"status": "pass"`. Direct read of `assistant-out.txt` is `accept UC3 out-file response`.
`--files ... --dry-run` step: `results.json:70-71` says `"detail": "--files --dry-run printed diff summary without mutation"` and the dry-run project path; `results.json:105` says `"dry_run": true`; `results.json:109/120/131` show deleted/added/modified entries; `results.json:145` says `"total_files": 3`; `results.json:149-150` says `"name": "files-dry-run-no-mutation"`, `"status": "pass"`. Direct artifact read confirms no mutation: `dry-run-project/src/app.txt` is `old app contents\nsecond line\n`, `dry-run-project/src/` lists only `app.txt`, and `dry-run-project/docs/delete-me.txt` is `delete this file\n`.

CHECK 4: PASS
Retrieval code selects a download only after latest-turn filtering and metadata validation: `src/ask_chatgpt/patch.py:322` has `if source_turn_id != latest_turn_id: stale_artifact_seen = True; continue`; `patch.py:326` rejects unsafe download filenames; `patch.py:331-334` reject malformed byte-count/SHA metadata; `patch.py:340-341` raises `PatchMalformedError("multiple latest-turn download artifacts are ambiguous")`; `patch.py:391-397` checks actual downloaded byte count and SHA before returning the `PatchBundle`.
Fallback/error behavior is explicit: `patch.py:229` returns `None` only for exact `NO_CHANGES_NEEDED`; `patch.py:252` raises on stale/wrong-turn artifact without fallback; `patch.py:254-255` raise named `DownloadUnsupportedError` for unsupported/missing download with no fenced fallback. A stale artifact with a valid fenced block falls through to fenced validation rather than being selected.
Fenced parsing is non-silent and integrity checked: `patch.py:420-427` counts markers and raises unless there is exactly one complete block; `patch.py:453/457/462/469` validate decimal byte count, lowercase 64-hex SHA, zip-byte cap, and base64url alphabet before decode; `patch.py:477-481` then verifies decoded byte count and SHA; `patch.py:615` requires embedded `manifest.json` to match fenced `MANIFEST_JSON`. I found no code path that can silently choose a wrong or stale bundle.

CHECK 5: PASS
Validation-before-mutation ordering is correct for patch contents and paths: `src/ask_chatgpt/patch.py:263-270` calls `_validate_zip_bytes(...)` before resolving/applying to the root; within validation, `patch.py:631-633` validates manifest and payload relative paths, and `patch.py:654` raises on payload SHA mismatch; only after that does `patch.py:271-272` resolve the apply root and prepare all target plans. Dry run is no-write by construction: `patch.py:273-274` returns `prepared.summary` before `_recover_incomplete_transactions` or `_apply_transaction` (`patch.py:275-276`).
Non-dry-run writes are after preparation: first transaction staging write is `patch.py:1027` (`staged_path.write_bytes(...)`), and target mutation is under `_commit_plan` after the journal/backup loop (`patch.py:1055`, `patch.py:1091+`). Rollback exists for apply-time failures (`patch.py:1063`).
Cross-check test is substantive: `tests/test_patch.py:277` defines `test_late_validation_failure_leaves_apply_root_byte_for_byte_unchanged`; `tests/test_patch.py:283` corrupts the second file SHA with `"0" * 64`; `tests/test_patch.py:286-289` expects `BundleIntegrityError` and asserts `_snapshot_tree(apply_root) == before`. Since SHA validation occurs at `patch.py:654` before transaction writes, this test's green result is meaningful.

CHECK 6: PASS
Sampled critical tests are not vacuous.
Round-trip diff-match: `tests/test_uc2_roundtrip.py:63-66` asserts exact modified-file content, added-file content, deleted-file absence, and unchanged README bytes; `tests/test_uc2_roundtrip.py:117-121` asserts dry-run leaves the snapshot unchanged; `tests/test_uc2_roundtrip.py:124-127` applies and then calls `_assert_diff_match(root)`.
Late-validation failure: `tests/test_patch.py:283/286/289` corrupts a real payload SHA, expects `BundleIntegrityError`, and asserts the tree equals the preimage snapshot.
Dry-run writes nothing: `tests/test_patch.py:306-320` asserts `summary.dry_run is True`, counts/kinds/paths/hashes, `_snapshot_tree(apply_root) == before`, and no `.ask-chatgpt-tmp` remains.
CLI no-mutate: `tests/test_cli.py:161-188` seeds a project, captures `before`, runs bundled CLI mode without `--apply/--dry-run`, asserts stdout is `PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip`, then asserts `_snapshot_tree(cli_project_root) == before` and no `.ask-chatgpt-tmp`; `tests/test_cli.py:219-223` separately parses dry-run JSON, asserts expected summary, unchanged snapshot, and no temp dir.
No weak/vacuous critical test was found in the sampled set.

END_TIMESTAMP: 2026-06-12T04:07:12-05:00
V-CORRECTNESS-VERDICT: PASS
T7b-STATUS: DONE