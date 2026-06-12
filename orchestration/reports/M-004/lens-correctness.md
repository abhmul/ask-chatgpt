ESTIMATE: T2b 12m
START_TIMESTAMP: 2026-06-12T05:08:06-05:00
END_TIMESTAMP: 2026-06-12T05:49:59-05:00
LENS: correctness/reproduction

## CHECK 1: PASS — clean-clone green
Raw evidence: `clone_setup.txt` says clone HEAD `7755193c68bb57a2e3f85c21e62e2bb00446c01a`, main HEAD `7755193c68bb57a2e3f85c21e62e2bb00446c01a`, and clone status porcelain empty. `clone_pytest.txt` ran `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run pytest -q`, exited `0`, and has exact summary `119 passed in 43.60s`.

The initial offline sync is not a code/repro failure: `clone_sync.txt` quotes `× Failed to download greenlet==3.2.4` under `UV_OFFLINE=1`. `clone_sync_RECOVERY.txt` quotes `SYNC_EXIT=0`, `+ greenlet==3.2.4`, `Built ask-chatgpt @ file:///home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone`, validation import path `ask_chatgpt /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone/src/ask_chatgpt/__init__.py`, and `All subsequent heavy runs ... executed against THIS clone venv`.

## CHECK 2: PASS — UC1 artifact consistency
Raw evidence: `accept_uc1_results.json` top-level `"overall": "pass"`. Continuity is concrete: first step has `"conversation_ref": "conv-1"` and `"returned_text": "accept UC1 answer one"`; second step `same-session-call-2-continuity` has `"conversation_ref": "conv-1"`, `"detail": "same session id reused the same conversation"`, `"returned_text": "accept UC1 answer two"`, and `"user_prompts": ["accept UC1 prompt one", "accept UC1 prompt two"]`. That is same-session reuse, not merely a fresh successful response.

## CHECK 3: PASS — UC2 round-trip diff-match
Raw evidence: `accept_uc2_results.json` top-level `"overall": "pass"`. Download-primary has `"patch_bundle": {"filename": "patch-bundle-artifact-1.zip", ... "source": "download"}` and path `tmp/accept-uc2-20260612-045148/download-primary-patch-bundle.zip`; fenced-fallback has `"patch_bundle": {"filename": "patch-bundle.zip", ... "source": "fenced"}` and path `tmp/accept-uc2-20260612-045148/fenced-fallback-patch-bundle.zip`.

Both round-trips quote the same concrete diff evidence: `"modified_matches": true`, `"modified_path": "src/app.txt"`, `"modified_text": "new app contents\nsecond line\n"`, `"added_matches": true`, `"added_path": "src/added.txt"`, `"added_text": "brand new file\n"`, `"deleted_absent": true`, `"deleted_path": "docs/delete-me.txt"`, and `"overall_diff_matches": true`. Supporting after-apply trees contain `src/app.txt` with `new app contents\nsecond line\n`, contain `src/added.txt` with `brand new file\n`, keep `README.md` unchanged, and omit `docs/delete-me.txt`.

## CHECK 4: PASS — UC3 artifact consistency
Raw evidence: `accept_uc3_results.json` top-level `"overall": "pass"`. Prompt-to-stdout has returned text and stdout both `"accept UC3 prompt response"`, returncode `0`, and stderr `""`. `--out` has `"out_file": "tmp/accept-uc3-20260612-045156/assistant-out.txt"`, returned text `"accept UC3 out-file response"`, stdout `""`, and the raw `assistant-out.txt` contains exactly `accept UC3 out-file response`.

Dry-run evidence has command args including `"--files", "README.md", "--dirs", "src", "--dirs", "docs", "--dry-run"`, and stdout JSON summary with `"dry_run": true`, `"added": 1`, `"deleted": 1`, `"modified": 1`, `"total_files": 3`, and `"total_bytes_changed": 61`. Raw before/after dry-run tree artifacts are identical: both still include `docs/delete-me.txt` text `delete this file\n`, `src/app.txt` text `old app contents\nsecond line\n`, and unchanged `README.md`.

## CHECK 5: PASS — sampled tests are non-vacuous
Representative raw source assertions include `assert s1_ref.conversation_ref == first_ref.conversation_ref`, `assert s1_user_texts == ["UC1 continuity prompt one", "UC1 continuity prompt two"]`, `assert _snapshot_tree(root) == before_dry_run`, `assert (root / "src" / "app.txt").read_text(...) == PATCH_CHANGED_FILES["src/app.txt"]`, `assert first.stdout == "subprocess stdout response"`, and `assert out_path.read_text(encoding="utf-8") == "subprocess file response"`.

| sampled test | concrete assertion / fails-if-broken rationale | vacuous? |
|---|---|---|
| `tests/test_ask_chatgpt_uc1.py::test_uc1_continuity_same_identifier_reuses_conversation_and_different_identifier_creates_new` | Asserts same session keeps the same `conversation_ref`, different session gets a different ref, exact prompt history, and exact returned answers; would fail if continuity, prompt sending, or response reading regressed. | no |
| `tests/test_ask_chatgpt_uc1.py::test_uc1_returns_scripted_latest_text_without_older_sentinel` | Asserts result equals a unique latest answer and excludes the older sentinel; would fail if the reader returned an older/combined turn. | no |
| `tests/test_session_registry.py::test_persists_across_fresh_registry_instance` | Writes a `ConversationRef` then constructs a fresh registry and asserts equality; would fail if session persistence were in-memory only or serialized incorrectly. | no |
| `tests/test_uc2_roundtrip.py::test_uc2_roundtrip_download_primary_public_api_dry_run_and_apply` | Uses public API with bundle upload, asserts source `download`, upload metadata, dry-run no mutation, summary counts/paths, and exact applied file bytes/deletion; would fail if download retrieval or apply were a no-op/wrong diff. | no |
| `tests/test_uc2_roundtrip.py::test_uc2_roundtrip_fenced_fallback_public_api_dry_run_and_apply` | Forces missing download and valid fenced fallback, asserts source `fenced`, marker text, no-mutation dry-run, and exact applied tree; would fail if fenced fallback or apply path broke. | no |
| `tests/test_patch.py::test_dry_run_returns_diff_summary_and_writes_nothing` | Builds a real patch zip and asserts diff counts, paths, hashes, and byte-for-byte pre/post snapshot equality; would fail if dry-run mutated or summary was bogus. | no |
| `tests/test_cli.py::test_subprocess_module_prompt_stdout_and_out` | Runs `python -m ask_chatgpt.cli` in subprocess and asserts stdout/stderr/return codes plus exact `--out` file contents; would fail if CLI stdout or file output contract broke. | no |
| `tests/test_cli.py::test_dry_run_prints_diff_summary_and_writes_nothing` | Calls CLI dry-run with files/dirs/root, parses stdout JSON, asserts root/counts/kinds and unchanged tree; would fail if CLI dry-run mutated or printed a wrong summary. | no |

No sampled test is tautological (`assert True`) or mocks away the behavior it claims to test; the loopback mock supplies deterministic UI responses while public API/patch/CLI code performs the real registry, reader, bundle, retrieval, dry-run, apply, and output work.

T2b-VERDICT: PASS
T2b-STATUS: DONE