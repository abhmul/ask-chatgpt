ESTIMATE: T4 60m
START_TIMESTAMP: 2026-06-12T03:23:07-05:00
END_TIMESTAMP: 2026-06-12T03:23:26-05:00

## Public API wiring
- Extended `ask_chatgpt(prompt, *, session_identifier=None, model_settings=None, channel="real", base_url=None, profile_path=None, registry=None, reader_order=None, timeout_s=30.0, files=None, dirs=None, bundle_root=None) -> str | AskChatGPTResult`.
- `AskChatGPTResult` is a frozen slots dataclass: `text: str`, `patch_bundle: PatchBundle | None`.
- UC1 no-files/no-dirs path remains plain `str`; empty `files`/`dirs` selections stay on the UC1 path.
- New/public exports: `AskChatGPTResult` added; existing §10 exports include `PatchBundle`, `apply_patch`, `DiffSummary`, `FileDiff`, `PatchBundleValidationError`, `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`, `PatchApplyError`, plus existing errors.

## T2/T3 composition
- UC2 path composes T2 `build_bundle(...)`, `upload_bundle(...)`, and `generate_prompt_instructions(...)`.
- It sends the protocol prompt, waits for completion, reads assistant text, then composes T3 `retrieve_patch_bundle(...)` to return the opaque `PatchBundle` handle.
- Local mutation is not in `ask_chatgpt`; callers use exported T3 `apply_patch(bundle, root, dry_run=...)`.

## Round-trip coverage
- Added `tests/test_uc2_roundtrip.py`.
- `test_uc2_roundtrip_download_primary_public_api_dry_run_and_apply` covers download-primary retrieval.
- `test_uc2_roundtrip_fenced_fallback_public_api_dry_run_and_apply` covers fenced base64url fallback retrieval.
- Each test seeds a repo-local `tmp/test_uc2_roundtrip/...` project, calls public `ask_chatgpt(files=..., dirs=..., bundle_root=...)`, verifies upload prompt wiring, dry-runs the returned patch with no writes, applies it under the `tmp/` root, and inspects the tree: one modified file matches expected content, one added file matches expected content, one deleted file is absent, and one untouched file is unchanged.

## Acceptance script
- Added executable `scripts/accept_uc2.sh` and `scripts/accept_uc2.py`.
- `accept_uc2.sh` creates `tmp/accept-uc2-<ts>/`, runs `uv run python scripts/accept_uc2.py --out <dir>`, tees stdout to `<dir>/stdout.log`, echoes `artifact_dir=...`, and exits with the Python script status.
- `accept_uc2.py` starts the loopback mock on an ephemeral port, runs both `download-primary-roundtrip` and `fenced-fallback-roundtrip`, saves assistant text, raw patch zip bytes, mock inspect snapshots, before/after tree snapshots, per-step JSON, and `results.json`.
- `results.json` shape: `{ "overall": "pass|fail", "steps": [{ "name", "status", "detail", "data" | "error_type"/"traceback" }] }`; each pass `data` includes patch metadata, upload metadata, dry-run/apply summaries, and `diff_match_evidence` with `overall_diff_matches` plus per-file inspection booleans.

## Verification
- TDD RED observed first: new UC2 test initially failed on missing `AskChatGPTResult` export.
- Final `uv run pytest -q` summary line: `91 passed in 38.00s`.
- `bash scripts/accept_uc2.sh` outcome: `overall=pass`; artifact dir `tmp/accept-uc2-20260612-032152`; results `tmp/accept-uc2-20260612-032152/results.json`.

## Deviations and trust notes
- No new pip dependencies; no external network; tests/scripts use `channel="mock"` and loopback base URLs only.
- Patch application in tests/acceptance targets repo `tmp/` only and uses exported `apply_patch`, never zip extraction.
- Extended the mock fixture only to allow scripted custom changed/deleted patch bundles needed for UC2 round-trip evidence.
- Did not git commit or push.

T4-STATUS: DONE
