# M-009 T1 opaque download worker report

Status: DONE

## RED
Command: `uv run pytest tests/test_uc2_roundtrip.py -k opaque -q`

Output: see `orchestration/reports/M-009/T1-RED.txt`. It fails first with `ask_chatgpt.errors.PatchMalformedError` and detail `download artifact metadata is missing data-source-turn-id`.

## Diff evidence
Scoped to contract files:

```text
$ git diff --stat -- src/ask_chatgpt/patch.py tests/fixtures/mock_chatgpt/server.py tests/test_uc2_roundtrip.py src/ask_chatgpt/selector_maps/real.json
 src/ask_chatgpt/patch.py                | 37 +++++++++++++++++++++++++-------
 src/ask_chatgpt/selector_maps/real.json |  2 +-
 tests/fixtures/mock_chatgpt/server.py   | 10 ++++++++-
 tests/test_uc2_roundtrip.py             | 38 +++++++++++++++++++++++++++++++++
 4 files changed, 77 insertions(+), 10 deletions(-)
```

Note: `orchestration/reports/M-009/real-audit-log.md` was already modified before this worker started and is excluded from the scoped stat above.

### `src/ask_chatgpt/patch.py` hunks

```diff
diff --git a/src/ask_chatgpt/patch.py b/src/ask_chatgpt/patch.py
index a644440..729d43f 100644
--- a/src/ask_chatgpt/patch.py
+++ b/src/ask_chatgpt/patch.py
@@ -127,8 +127,8 @@ class DiffSummary:
 class _DownloadCandidate:
     locator: Locator
     filename: str
-    byte_count: int
-    sha256: str
+    byte_count: int | None
+    sha256: str | None
 
 
 @dataclass(frozen=True, slots=True)
@@ -326,16 +326,33 @@ def _scan_download_artifacts(turn: Locator, selectors: Any) -> _DownloadScan:
     for index in range(count):
         link = links.nth(index)
         source_turn_id = link.get_attribute("data-source-turn-id")
+        byte_count_text = link.get_attribute("data-byte-count")
+        digest = link.get_attribute("data-sha256")
+        filename_attr = link.get_attribute("data-filename") or link.get_attribute("download")
+
+        if not source_turn_id and byte_count_text is None and digest is None:
+            # Opaque real download control (bare ChatGPT "Download the patch bundle" button): the real
+            # surface exposes no self-describing integrity metadata. The locator is already scoped to the
+            # latest completed turn, so turn-membership holds without data-source-turn-id. Capture and
+            # validate the zip structurally (see _download_candidate_bytes).
+            filename = filename_attr or "patch-bundle.zip"
+            if not _is_safe_download_filename(filename):
+                raise PatchMalformedError("download artifact filename metadata is unsafe")
+            if filename in filenames:
+                raise PatchMalformedError("duplicate latest-turn download artifact filename collision")
+            filenames.add(filename)
+            eligible.append(_DownloadCandidate(locator=link, filename=filename, byte_count=None, sha256=None))
+            continue
+
+        # Self-describing (mock/strict) artifact: require the FULL metadata set, unchanged.
         if not source_turn_id:
             raise PatchMalformedError("download artifact metadata is missing data-source-turn-id")
         if source_turn_id != latest_turn_id:
             stale_artifact_seen = True
             continue
-        filename = link.get_attribute("data-filename") or link.get_attribute("download") or "patch-bundle.zip"
+        filename = filename_attr or "patch-bundle.zip"
         if not _is_safe_download_filename(filename):
             raise PatchMalformedError("download artifact filename metadata is unsafe")
-        byte_count_text = link.get_attribute("data-byte-count")
-        digest = link.get_attribute("data-sha256")
         if byte_count_text is None or not _DECIMAL_RE.fullmatch(byte_count_text):
             raise PatchMalformedError("download artifact byte-count metadata is malformed")
         if digest is None or not _HEX64_RE.fullmatch(digest):
@@ -377,7 +394,7 @@ def _download_candidate_bytes(
     *,
     timeout_s: float,
 ) -> tuple[bytes, PatchBundle]:
-    if candidate.byte_count > caps.max_zip_bytes:
+    if candidate.byte_count is not None and candidate.byte_count > caps.max_zip_bytes:
         raise OversizedPayloadError(
             f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by declared download metadata: {candidate.byte_count} > {caps.max_zip_bytes}"
         )
@@ -401,12 +418,16 @@ def _download_candidate_bytes(
     except OSError as exc:
         raise DownloadUnsupportedError("download body could not be read after capture") from exc
 
-    if len(zip_bytes) != candidate.byte_count:
+    if len(zip_bytes) > caps.max_zip_bytes:
+        raise OversizedPayloadError(
+            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by captured download bytes: {len(zip_bytes)} > {caps.max_zip_bytes}"
+        )
+    if candidate.byte_count is not None and len(zip_bytes) != candidate.byte_count:
         raise BundleIntegrityError(
             f"download byte count mismatch: expected {candidate.byte_count}, got {len(zip_bytes)}"
         )
     digest = sha256(zip_bytes).hexdigest()
-    if digest != candidate.sha256:
+    if candidate.sha256 is not None and digest != candidate.sha256:
         raise BundleIntegrityError("download SHA-256 mismatch against artifact metadata")
     bundle = PatchBundle(
         filename=candidate.filename,
```

### `real.json` line

```text
20:    "download_artifact": "button:has-text(\"Download the patch bundle\")",
```

## GREEN and regression
Command: `uv run pytest tests/test_uc2_roundtrip.py -k opaque -q`

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
.                                                                        [100%]
1 passed, 2 deselected in 0.83s
```

Strict download tests command: `uv run pytest tests/test_patch.py -k download -q`

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
.........                                                                [100%]
9 passed, 35 deselected in 7.84s
```

Full suite command: `uv run pytest -q`

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........................................................................ [ 33%]
........................................................................ [ 67%]
....................................................................     [100%]
212 passed, 4 deselected in 62.74s (0:01:02)
```

Baseline was 211 passed / 4 deselected. Added N=1 test, exact total 212 passed / 4 deselected. Full suite was run before the final `real.json` selector population, per the worker contract ordering.

## Telemetry
ESTIMATE: T1-opaque 45m

ACTUAL: T1-opaque 32m

END: 2026-06-13T16:23:40-05:00

REWORK-CAUSE: Removed an accidental stray non-ASCII character inserted during the test edit before running RED.
