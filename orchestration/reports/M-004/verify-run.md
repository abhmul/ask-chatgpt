ESTIMATE: T1b 6m
START_TIMESTAMP: 2026-06-12T04:50:25-05:00
END_TIMESTAMP: 2026-06-12T04:54:52-05:00
LENS: authoritative-run (capture-only; corrected after offline-blocker resolved)

T1 initially ran `uv sync` with `UV_OFFLINE=1`, which blocked the clone venv build (greenlet cache miss). The manager rebuilt the clone venv with a normal network-allowed `uv sync --all-groups` (clone HEAD == main HEAD, project installed editable from the clone's own src). The heavy rows below are this corrected re-run; the non-heavy rows are carried forward from the original capture.

## Command evidence index
| check | command | exit code | evidence | one-line RAW observation |
|---|---|---:|---|---|
| main git status/log | `git -C /home/abhmul/dev/ask-chatgpt status --porcelain`; `git -C /home/abhmul/dev/ask-chatgpt log --oneline -15` | 0 / 0 | `tmp/verify-m004/git_state.txt` | `status --porcelain` emitted `?? orchestration/state/M-004-state.json` and `?? orchestration/tasks/M-004/`; log HEAD line `7755193 M-004: author final independent-verification contract; ingest M-003 (DONE, panel PASS)`. |
| local clean clone | `git clone /home/abhmul/dev/ask-chatgpt tmp/verify-m004/clone` | 0 | `tmp/verify-m004/clone_setup.txt` | cloned HEAD `7755193c68bb57a2e3f85c21e62e2bb00446c01a`; main HEAD `7755193c68bb57a2e3f85c21e62e2bb00446c01a`; clone porcelain empty. |
| historical T1 offline clone sync blocker | `cd tmp/verify-m004/clone && UV_OFFLINE=1 uv sync --all-groups` | 1 | `tmp/verify-m004/clone_sync.txt` | historical blocker line `× Failed to download greenlet==3.2.4`; corrected rerun used the manager-built clone venv and did not set `UV_OFFLINE`. |
| full clone pytest | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run pytest -q` | 0 | `tmp/verify-m004/clone_pytest.txt` | exact summary `119 passed in 43.60s`; total count `119`. |
| UC1 acceptance | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && bash scripts/accept_uc1.sh` | 0 | `tmp/verify-m004/clone_accept_uc1.txt`; `tmp/verify-m004/accept_uc1_results.json` | `artifact_dir=tmp/accept-uc1-20260612-045138`; `overall=pass`; `results_json=tmp/accept-uc1-20260612-045138/results.json`; copied newest results JSON. |
| UC2 acceptance | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && bash scripts/accept_uc2.sh` | 0 | `tmp/verify-m004/clone_accept_uc2.txt`; `tmp/verify-m004/accept_uc2_results.json` | `artifact_dir=tmp/accept-uc2-20260612-045148`; `overall=pass`; steps `download-primary-roundtrip` and `fenced-fallback-roundtrip`; copied newest results JSON. |
| UC3 acceptance | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && bash scripts/accept_uc3.sh` | 0 | `tmp/verify-m004/clone_accept_uc3.txt`; `tmp/verify-m004/accept_uc3_results.json` | `artifact_dir=tmp/accept-uc3-20260612-045156`; `overall=pass`; steps `prompt-stdout`, `out-file`, `files-dry-run-no-mutation`; copied newest results JSON. |
| network guard demo | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run pytest tests/test_network_guard.py -q` | 0 | `tmp/verify-m004/netguard.txt` | exact summary `2 passed in 0.47s`; test ids listed below. |
| zip-slip PRIMARY re-run | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run python /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/zipslip_probe.py` | 0 | `tmp/verify-m004/zipslip.txt` | appended under `=== PRIMARY uv run (venv built) ===`; printed four `VECTOR ...` lines with `PathEscapeError`, `CANARY_EXISTS=False`, `ROOT_UNCHANGED=True`. |
| zip-slip supplemental no-sync | `cd tmp/verify-m004/clone && UV_OFFLINE=1 PYTHONPATH=src uv run --no-sync python tmp/verify-m004/zipslip_probe.py` | 0 | `tmp/verify-m004/zipslip.txt` | printed four `VECTOR ...` lines; each line includes exception type/message, canary existence, and root unchanged flag. |
| CLI guardrails PRIMARY | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run ask-chatgpt --apply --dry-run --files /tmp/none`; `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run ask-chatgpt --apply --files /tmp/none` | 2 / 2 | `tmp/verify-m004/cli_exclusive.txt` | appended under `=== PRIMARY uv run (venv built) ===`; stderr `argument --dry-run: not allowed with argument --apply`; stderr `prompt is required: use positional prompt or --prompt TEXT`. |
| CLI supplemental parse | `cd tmp/verify-m004/clone && UV_OFFLINE=1 PYTHONPATH=src uv run --no-sync python tmp/verify-m004/cli_guardrail_probe.py ...` | 2 / 2 / 2 | `tmp/verify-m004/cli_exclusive.txt` | stderr lines: `argument --dry-run: not allowed with argument --apply`; `prompt is required: use positional prompt or --prompt TEXT`; `--apply/--dry-run require explicit --root`. |
| CLI tests/no-mutate | `cd /home/abhmul/dev/ask-chatgpt/tmp/verify-m004/clone && env -u VIRTUAL_ENV uv run pytest tests/test_cli.py -q` | 0 | `tmp/verify-m004/cli_tests.txt` | exact summary `28 passed in 5.00s`; requested test ids listed below. |
| inventory | `ls -laR src tests scripts docs` | 0 | `tmp/verify-m004/inventory.txt` | raw recursive listing captured. |
| grep chatgpt.com | `grep -rn 'chatgpt.com' src tests scripts` | 0 | `tmp/verify-m004/grep_chatgptcom.txt` | hits listed verbatim below, including binary `__pycache__` matches. |
| grep real/channel/storage | `grep -rn 'channel="real"\|channel=.real.\|launch_persistent_context\|storage_state' src tests scripts` | 0 | `tmp/verify-m004/grep_realchannel.txt` | hits listed in raw file; includes `driver.py` docstring, `launch_persistent_context`, binary `__pycache__` matches, and `api.py` docstring. |
| raw file manifest | `find tmp/verify-m004 \( -type f -o -type l \) | sort` | 0 | `tmp/verify-m004/evidence_manifest_raw.txt` | 1688 raw lines captured, including command/exit wrappers and every file/symlink path under `tmp/verify-m004/`. |

## Required verbatim excerpts
Clone HEAD hash vs main HEAD: `7755193c68bb57a2e3f85c21e62e2bb00446c01a` vs `7755193c68bb57a2e3f85c21e62e2bb00446c01a`.

Full pytest summary/count: exact summary line `119 passed in 43.60s`; total count `119`.

Acceptance `overall` values: UC1 `overall`: `pass`; UC2 `overall`: `pass`; UC3 `overall`: `pass`.

UC1 session-continuity evidence fields: `"conversation_ref": "conv-1"`; `"detail": "same session id reused the same conversation"`; `"returned_text": "accept UC1 answer two"`; `"user_prompts": ["accept UC1 prompt one", "accept UC1 prompt two"]`.

UC2 diff-match fields and retrieval paths: `download-primary-roundtrip` has `"patch_bundle": {"filename": "patch-bundle-artifact-1.zip", "source": "download"}` and `"patch_bundle_path": "tmp/accept-uc2-20260612-045148/download-primary-patch-bundle.zip"`; `fenced-fallback-roundtrip` has `"patch_bundle": {"filename": "patch-bundle.zip", "source": "fenced"}` and `"patch_bundle_path": "tmp/accept-uc2-20260612-045148/fenced-fallback-patch-bundle.zip"`; both have `"modified_matches": true`, `"modified_path": "src/app.txt"`, `"modified_text": "new app contents\nsecond line\n"`, `"added_matches": true`, `"added_path": "src/added.txt"`, `"added_text": "brand new file\n"`, `"deleted_absent": true`, `"deleted_path": "docs/delete-me.txt"`, `"overall_diff_matches": true`.

UC3 exercised-step fields: `prompt-stdout` returned `"accept UC3 prompt response"` with stdout `"accept UC3 prompt response"`; `out-file` wrote `"tmp/accept-uc3-20260612-045156/assistant-out.txt"` and left stdout `""`; `files-dry-run-no-mutation` emitted summary fields `"dry_run": true`, `"added": 1`, `"deleted": 1`, `"modified": 1`, `"total_files": 3`, `"total_bytes_changed": 61`.

Zip-slip vector observations from the PRIMARY uv run:
- `VECTOR absolute_path | EXCEPTION=PathEscapeError: Bundle path is unsafe or escapes the project root. Operator action: use repo-root-relative file paths without traversal, symlinks, or special files; no local files were changed. Detail: absolute paths and drive/UNC paths are rejected | CANARY_EXISTS=False | ROOT_UNCHANGED=True | ROOT_BEFORE=[] | ROOT_AFTER=[]`
- `VECTOR dotdot_traversal | EXCEPTION=PathEscapeError: Bundle path is unsafe or escapes the project root. Operator action: use repo-root-relative file paths without traversal, symlinks, or special files; no local files were changed. Detail: path traversal '..' is rejected | CANARY_EXISTS=False | ROOT_UNCHANGED=True | ROOT_BEFORE=[] | ROOT_AFTER=[]`
- `VECTOR symlink_final | EXCEPTION=PathEscapeError: Bundle path is unsafe or escapes the project root. Operator action: use repo-root-relative file paths without traversal, symlinks, or special files; no local files were changed. Detail: symlink final target rejected: link | CANARY_EXISTS=False | ROOT_UNCHANGED=True | ROOT_BEFORE=[('link', 'symlink', '/home/abhmul/dev/ask-chatgpt/tmp/verify-m004/slip-canary-OUTSIDE')] | ROOT_AFTER=[('link', 'symlink', '/home/abhmul/dev/ask-chatgpt/tmp/verify-m004/slip-canary-OUTSIDE')]`
- `VECTOR symlink_parent | EXCEPTION=PathEscapeError: Bundle path is unsafe or escapes the project root. Operator action: use repo-root-relative file paths without traversal, symlinks, or special files; no local files were changed. Detail: symlink parent component rejected: parentlink/slip-canary-OUTSIDE | CANARY_EXISTS=False | ROOT_UNCHANGED=True | ROOT_BEFORE=[('parentlink', 'symlink', '/home/abhmul/dev/ask-chatgpt/tmp/verify-m004')] | ROOT_AFTER=[('parentlink', 'symlink', '/home/abhmul/dev/ask-chatgpt/tmp/verify-m004')]`

Network guard result/test ids: exact result line `2 passed in 0.47s`; ids `tests/test_network_guard.py::test_autouse_socket_guard_blocks_deliberate_non_loopback_connect`; `tests/test_network_guard.py::test_mock_browser_context_route_blocks_non_loopback_navigation`.

CLI guardrail stderr/exit-code excerpts: primary `uv run ask-chatgpt --apply --dry-run --files /tmp/none` exit `2`, stderr `ask-chatgpt: error: argument --dry-run: not allowed with argument --apply`; primary `uv run ask-chatgpt --apply --files /tmp/none` exit `2`, stderr `ask-chatgpt: error: prompt is required: use positional prompt or --prompt TEXT`; carried-forward supplemental explicit-prompt root guard exit `2`, stderr `ask-chatgpt: error: --apply/--dry-run require explicit --root`.

CLI no-mutate/guardrail test ids: `tests/test_cli.py::test_files_without_apply_does_not_mutate_by_default`; `tests/test_cli.py::test_apply_requires_root_before_browser_side_effects`; `tests/test_cli.py::test_apply_and_dry_run_are_mutually_exclusive`.

Full `chatgpt.com` grep hits:
- `src/ask_chatgpt/driver.py:34:REAL_BASE_URL = "https://chatgpt.com"`
- `grep: src/ask_chatgpt/__pycache__/driver.cpython-313.pyc: binary file matches`
- `grep: tests/__pycache__/test_driver.cpython-313-pytest-9.0.3.pyc: binary file matches`
- `grep: tests/__pycache__/test_session_registry.cpython-313-pytest-9.0.3.pyc: binary file matches`
- `tests/test_driver.py:141:    assert REAL_BASE_URL == "https://chatgpt.com"`
- `tests/test_driver.py:147:        assert "chatgpt.com" not in session.page.url`
- `tests/test_session_registry.py:14:        url="https://chatgpt.com/c/conv_123",`

## EVIDENCE MANIFEST
- `tmp/verify-m004/git_state.txt` — main repo `status --porcelain` and last 15 commits from original capture.
- `tmp/verify-m004/clone_setup.txt` — local clone command, cloned/main HEAD hashes, initial clone porcelain.
- `tmp/verify-m004/clone_sync.txt` — historical offline `uv sync --all-groups` blocker raw output.
- `tmp/verify-m004/clone_pytest.txt` — corrected full-suite `uv run pytest -q` raw output and exit code.
- `tmp/verify-m004/clone_accept_uc1.txt` — corrected UC1 acceptance script raw output, exit code, and results copy line.
- `tmp/verify-m004/accept_uc1_results.json` — copied newest UC1 `results.json` from the clone artifact directory.
- `tmp/verify-m004/clone_accept_uc2.txt` — corrected UC2 acceptance script raw output, exit code, and results copy line.
- `tmp/verify-m004/accept_uc2_results.json` — copied newest UC2 `results.json` from the clone artifact directory.
- `tmp/verify-m004/clone_accept_uc3.txt` — corrected UC3 acceptance script raw output, exit code, and results copy line.
- `tmp/verify-m004/accept_uc3_results.json` — copied newest UC3 `results.json` from the clone artifact directory.
- `tmp/verify-m004/netguard.txt` — corrected network-guard pytest raw output and exit code.
- `tmp/verify-m004/zipslip_probe.py` — malicious patch-bundle probe source from original capture.
- `tmp/verify-m004/clone/tmp/verify-m004/zipslip_probe.py` — clone-relative probe copy from original capture.
- `tmp/verify-m004/zipslip.txt` — historical exact/supplemental zip-slip logs plus corrected primary uv-run append.
- `tmp/verify-m004/cli_guardrail_probe.py` — supplemental parse-only CLI probe source from original capture.
- `tmp/verify-m004/clone/tmp/verify-m004/cli_guardrail_probe.py` — clone-relative supplemental CLI probe copy from original capture.
- `tmp/verify-m004/cli_exclusive.txt` — historical exact/supplemental CLI guardrail logs plus corrected primary uv-run append.
- `tmp/verify-m004/cli-noapply-root/canary.txt` — no-mutate canary file from original CLI-test setup.
- `tmp/verify-m004/cli_tests.txt` — corrected CLI pytest raw output and exit code.
- `tmp/verify-m004/inventory.txt` — raw `ls -laR src tests scripts docs` listing from original capture.
- `tmp/verify-m004/grep_chatgptcom.txt` — raw `chatgpt.com` grep hits from original capture.
- `tmp/verify-m004/grep_realchannel.txt` — raw real-channel/storage grep hits from original capture.
- `tmp/verify-m004/evidence_manifest_raw.txt` — full 1688-line raw file/symlink manifest under `tmp/verify-m004/`.
- `tmp/verify-m004/clone/**` — local cloned HEAD tree, built `.venv`, acceptance temp directories, probe copies, and generated artifacts; full per-path list is in `tmp/verify-m004/evidence_manifest_raw.txt`.
- `tmp/verify-m004/slip-root/parentlink` — symlink left by final zip-slip vector setup; raw state is in `tmp/verify-m004/zipslip.txt`.
T1-STATUS: DONE
