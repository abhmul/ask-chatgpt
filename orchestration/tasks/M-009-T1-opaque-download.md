# Worker contract — M-009 T1: opaque-real download mode (RED-first) + populate real.json

Single-editor pi worker. Add support for capturing a REAL ChatGPT download control that exposes
NO integrity metadata, validating the captured zip structurally, then populate the real selector.
Do NOT `git push`. Do NOT contact chatgpt.com. Use `uv run` for python/pytest; `uv sync --all-groups`
first if imports fail. Keep the change minimal and surgical.

## Why (verified evidence — do not re-litigate)
The production UC2 download path `retrieve_patch_bundle` → `_scan_download_artifacts`
(`src/ask_chatgpt/patch.py`) REQUIRES every download element to carry `data-source-turn-id`,
`data-byte-count`, `data-sha256` (the mock fixture emits these). The REAL ChatGPT affordance is a
bare `<button>Download the patch bundle</button>` with NONE of them — so the production path raises
`PatchMalformedError("download artifact metadata is missing data-source-turn-id")`. This was just
CONFIRMED on the real site over CDP (manager probe): with the keystone completion fix in place, the
retrieve reaches the scan and fails exactly there. Evidence:
`orchestration/reports/M-009/T1-uc2-roundtrip.json`.

Fix: when a latest-turn download control carries NONE of the integrity metadata, treat it as an
OPAQUE real download — the locator is already scoped to the latest completed turn, so turn-membership
is guaranteed without `data-source-turn-id`. Click, capture the bytes, and validate the zip
STRUCTURALLY (the captured bytes are the integrity source). Keep the mock/strict path UNCHANGED:
if SOME metadata is present, still require ALL of it (partial metadata = malformed = safe).

## Files you may edit (ONLY these four)
1. `src/ask_chatgpt/patch.py` — `_DownloadCandidate`, `_scan_download_artifacts`, `_download_candidate_bytes`.
2. `tests/fixtures/mock_chatgpt/server.py` — add an `opaque` download mode.
3. `tests/test_uc2_roundtrip.py` (and/or `tests/test_patch.py`) — add RED-first opaque tests.
4. `src/ask_chatgpt/selector_maps/real.json` — populate `download_artifact` (last step).

## STEP 1 — RED first. Add the mock `opaque` mode + a failing end-to-end test.

### 1a. Mock fixture: add an `opaque` download mode (`tests/fixtures/mock_chatgpt/server.py`)
- Find `_validated_download_mode` and ADD `"opaque"` to its allowed set (mirror how `"delayed"` /
  `"wrong_older"` are allowed).
- In `_attach_download_artifacts_unlocked`, `"opaque"` must fall through to the DEFAULT branch
  (the final `turn.download_artifact_ids = [self._create_artifact_unlocked(source_turn_id=turn.turn_id, mode=mode, **patch_kwargs)]`),
  so a normal, downloadable artifact is created with `mode == "opaque"`. Do not early-return it.
- In `_render_download_artifacts`, when `artifact["mode"] == "opaque"`, render the anchor WITHOUT the
  integrity attributes (no `data-source-turn-id`, `data-byte-count`, `data-sha256`, `data-filename`,
  and no `download=`), but KEEP `data-testid="mock-download-artifact"` and the working `href` so the
  mock selector still matches and the download still serves valid zip bytes. Concretely render:
  `<div data-testid="mock-artifact-card" data-artifact-id="{id}" data-artifact-mode="opaque"><a data-testid="mock-download-artifact" href="{href}">Download the patch bundle</a></div>`

### 1b. RED test (`tests/test_uc2_roundtrip.py`)
Mirror the existing `test_uc2_roundtrip_download_primary_public_api_dry_run_and_apply`, but script the
assistant response with `download_mode="opaque"` and a changed file that flips
`favorite_color = "red"` → `favorite_color = "blue"` while leaving a sibling line unchanged. Drive it
through the PUBLIC api: `ask_chatgpt(prompt, files=..., channel="mock", base_url=mock_chatgpt.base_url)`
→ `apply_patch(result.patch_bundle, root=..., dry_run=True)` then `dry_run=False`, and assert the
applied file content is correct (blue, sibling intact). Name it
`test_uc2_roundtrip_opaque_download_public_api_dry_run_and_apply`.

Run it and CONFIRM IT FAILS (RED) on current patch.py with
`PatchMalformedError` ("missing data-source-turn-id"):
`uv run pytest tests/test_uc2_roundtrip.py -k opaque -q`
Save the RED output to `orchestration/reports/M-009/T1-RED.txt`.

## STEP 2 — Implement the opaque path in `src/ask_chatgpt/patch.py`.

### 2a. `_DownloadCandidate` — allow unknown integrity:
Change `byte_count: int` → `byte_count: int | None` and `sha256: str` → `sha256: str | None`.

### 2b. `_scan_download_artifacts` — opaque branch. Inside the `for index in range(count):` loop,
replace the strict-only body so it reads all attributes first and branches:
```python
        link = links.nth(index)
        source_turn_id = link.get_attribute("data-source-turn-id")
        byte_count_text = link.get_attribute("data-byte-count")
        digest = link.get_attribute("data-sha256")
        filename_attr = link.get_attribute("data-filename") or link.get_attribute("download")

        if not source_turn_id and byte_count_text is None and digest is None:
            # Opaque real download control (bare ChatGPT "Download the patch bundle" button): the real
            # surface exposes no self-describing integrity metadata. The locator is already scoped to the
            # latest completed turn, so turn-membership holds without data-source-turn-id. Capture and
            # validate the zip structurally (see _download_candidate_bytes).
            filename = filename_attr or "patch-bundle.zip"
            if not _is_safe_download_filename(filename):
                raise PatchMalformedError("download artifact filename metadata is unsafe")
            if filename in filenames:
                raise PatchMalformedError("duplicate latest-turn download artifact filename collision")
            filenames.add(filename)
            eligible.append(_DownloadCandidate(locator=link, filename=filename, byte_count=None, sha256=None))
            continue

        # Self-describing (mock/strict) artifact: require the FULL metadata set, unchanged.
        if not source_turn_id:
            raise PatchMalformedError("download artifact metadata is missing data-source-turn-id")
        if source_turn_id != latest_turn_id:
            stale_artifact_seen = True
            continue
        filename = filename_attr or "patch-bundle.zip"
        if not _is_safe_download_filename(filename):
            raise PatchMalformedError("download artifact filename metadata is unsafe")
        if byte_count_text is None or not _DECIMAL_RE.fullmatch(byte_count_text):
            raise PatchMalformedError("download artifact byte-count metadata is malformed")
        if digest is None or not _HEX64_RE.fullmatch(digest):
            raise PatchMalformedError("download artifact SHA-256 metadata is malformed")
        byte_count = int(byte_count_text)
        if filename in filenames:
            raise PatchMalformedError("duplicate latest-turn download artifact filename collision")
        filenames.add(filename)
        eligible.append(_DownloadCandidate(locator=link, filename=filename, byte_count=byte_count, sha256=digest))
```
Preserve the existing behavior AFTER the loop verbatim (the `len(eligible) > 1` ambiguity check,
`delayed`/`unsupported` detection, and the returned `_DownloadScan`). Note the original `filename`
default was `link.get_attribute("data-filename") or link.get_attribute("download") or "patch-bundle.zip"`
— `filename_attr` above preserves that.

### 2c. `_download_candidate_bytes` — tolerate unknown byte_count/sha256:
```python
    if candidate.byte_count is not None and candidate.byte_count > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by declared download metadata: {candidate.byte_count} > {caps.max_zip_bytes}"
        )
```
(only the pre-click check gains the `is not None` guard). After `zip_bytes` is read, replace the
mismatch checks with:
```python
    if len(zip_bytes) > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by captured download bytes: {len(zip_bytes)} > {caps.max_zip_bytes}"
        )
    if candidate.byte_count is not None and len(zip_bytes) != candidate.byte_count:
        raise BundleIntegrityError(
            f"download byte count mismatch: expected {candidate.byte_count}, got {len(zip_bytes)}"
        )
    digest = sha256(zip_bytes).hexdigest()
    if candidate.sha256 is not None and digest != candidate.sha256:
        raise BundleIntegrityError("download SHA-256 mismatch against artifact metadata")
```
Keep building the `PatchBundle` with `sha256=digest, byte_count=len(zip_bytes)` (self-consistent), so
the downstream `_validate_zip_bytes` validates the zip STRUCTURE and never raises a spurious mismatch.

## STEP 3 — GREEN + full regression.
1. `uv run pytest tests/test_uc2_roundtrip.py -k opaque -q` → CONFIRM PASS. Save to `orchestration/reports/M-009/T1-GREEN.txt`.
2. Run the existing strict download tests, CONFIRM still PASS (must NOT regress):
   `uv run pytest tests/test_patch.py -k download -q`
3. FULL suite: `uv run pytest -q`. The CURRENT baseline is `211 passed, 4 deselected`. The ONLY delta
   may be the test(s) YOU add: expect `211 + <N new> passed, 4 deselected`. No pre-existing test may
   flip to failing or be deleted/skipped. Save the tail to `orchestration/reports/M-009/T1-pytest-full.txt`.

## STEP 4 — Populate the real selector (data; do this LAST, after the suite is green).
In `src/ask_chatgpt/selector_maps/real.json`, set:
`"download_artifact": "button:has-text(\"Download the patch bundle\")"`
(leave every other key unchanged). This selector was VERIFIED against the real site in M-008b and by
the M-009 manager probe (it matched the real latest-turn button). It is text-dependent and fails
closed if ChatGPT's button text drifts — that is acceptable (selectors-as-data).

## Report
Write `orchestration/reports/M-009/T1-opaque-worker-report.md`:
- `Status: DONE` (or PARTIAL/BLOCKED).
- RED command + verbatim failing output (or pointer to T1-RED.txt) proving PatchMalformedError first.
- `git diff --stat` + the patch.py hunks + the real.json line.
- GREEN output + strict-download-tests output + full-suite tail (`211 + N passed, 4 deselected`,
  state N and the exact total).
- Telemetry: `ESTIMATE: T1-opaque <minutes>m`, `ACTUAL: T1-opaque <minutes>m`, end timestamp from
  `date -Iseconds`, and `REWORK-CAUSE: <...>` for any rework leg.
- Do NOT commit; the manager commits. Do NOT `git push`.
