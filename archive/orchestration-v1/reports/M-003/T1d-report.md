ESTIMATE: T1d 60m
START_TIMESTAMP: 2026-06-12T02:15:51-05:00

## Deliverables

- Wrote `/home/abhmul/dev/ask-chatgpt/docs/bundle-protocol.md`.
- Wrote this report at `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/T1d-report.md`.

## `bundle-protocol.md` section outline

1. Overview and round-trip lifecycle.
2. Outgoing bundle format, catalogue README template, prompt instructions, path/size/type guards.
3. Patch-bundle return format with download primary and fenced fallback.
4. Manifest schema.
5. Validation order and all-or-nothing apply semantics.
6. Zip-slip-safe apply and deletion safety.
7. Oversize caps.
8. Failure taxonomy to named errors.
9. Adversarial handling matrix.
10. Public API surface.
11. CLI.
12. Rationale and reconciled conflicts.

## Conflicts reconciled

- Manifest version/kind conflict: integrity proposed canonical `version: 2` with `kind`; GPT-interaction and the fixture use `version: 1`, `status: "changed"`, `total_byte_count`, `path`, `size`, and `sha256`. Decision: keep canonical embedded manifest at `version: 1`, add optional `operation` for `added|modified|deleted`, accept missing `operation` only for fixture-compatible changed entries, and reject `status: "unchanged"`.
- Deletion schema conflict: integrity proposed deletion entries without size/hash; GPT-interaction proposed `status: "deleted"`, `operation: "deleted"`, `size: 0`, `sha256: null`. Decision: use the explicit tombstone with `size: 0` and `sha256: null` because the task required per-file size/sha fields and it is simple to validate.
- Download-vs-fallback behavior conflict: D-001 and GPT-interaction make download primary with fenced fallback; integrity emphasized failing safely on corrupt primary artifacts. Decision: choose download when exactly one eligible latest-turn artifact exists, fallback only when no eligible artifact exists, and fail rather than silently switch if a selected primary artifact is corrupt or malformed.
- Whole-zip integrity location conflict: integrity treated zip hash/count as schema; the fixture embeds those only in fenced `MANIFEST_JSON` and DOM metadata, not in embedded `manifest.json`. Decision: define them as retrieval-envelope fields; embedded `manifest.json` omits them, fenced `MANIFEST_JSON` carries them for parser comparison.
- API root conflict: ergonomics left bundle-root determinism open. Decision: add optional `bundle_root` keyword at the end of the UC2 `ask_chatgpt` signature while preserving UC1 `-> str`; CLI `--root` is required for dry-run/apply and also supplies `bundle_root` there.
- Apply atomicity conflict: a simple buffered write is easier but cannot honestly promise multi-file all-or-nothing under crash. Decision: validate all bytes in memory first, then use a staged transaction with backups and a credential-free journal; document recovery instead of claiming impossible atomic tree replacement.
- README metadata collision conflict: GPT-interaction left collision open. Decision: reserve `ASK_CHATGPT_BUNDLE_README.md` and fail if a selected project file would collide, which is the simplest safe rule for MVP.
- Error taxonomy conflict: ergonomics suggested broad `PatchBundleValidationError` and `PatchApplyError`; integrity named concrete failures. Decision: add `PatchBundleValidationError` as a new base for CLI exit mapping, with concrete `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, and `PathEscapeError`; add `PatchApplyError` for post-validation apply failures.

## Fixture-token corrections and confirmations

- Confirmed fallback markers are literal `BEGIN_PATCH_BUNDLE` and `END_PATCH_BUNDLE`, with line prefixes `MANIFEST_JSON:`, `ZIP_BYTE_COUNT:`, `ZIP_SHA256:`, and standalone `BASE64URL:`; the spec quotes these exactly.
- Corrected away from the integrity lens's canonical v2 parser-facing manifest: fixture ground truth is `version: 1`, `files`, `total_byte_count`, and entries with `path`, `size`, `sha256`, `status: "changed"`; `operation` remains a compatible refinement, not a replacement token.
- Confirmed fixture fenced variants: `ok`, `missing_end`, `bad_hash`, `changed_and_unchanged`, `oversized`.
- Confirmed fixture download variants: `ok`, `missing`, `delayed`, `wrong_older`, `corrupt`, `truncated`, `collision`, `unsupported`.
- Confirmed fixture upload variants: `ok`, `unsupported`, `reject_size_type`, `corrupt`.
- Confirmed download affordance selector name `download_artifact` maps to `data-testid="mock-download-artifact"` and exposes `data-filename`, `data-byte-count`, `data-sha256`, and `data-source-turn-id`.
- Confirmed upload affordance selector name `upload_input` maps to `data-testid="mock-upload-input"`.

## Trust notes

- Read the task contract in full first, then read all three design-lens reports in full.
- Re-anchored against `tests/fixtures/mock_chatgpt/server.py`, `tests/test_fixture_files.py`, `docs/DECISIONS.md`, `README.md`, `src/ask_chatgpt/api.py`, `src/ask_chatgpt/errors.py`, `src/ask_chatgpt/__init__.py`, `src/ask_chatgpt/selector_maps/mock.json`, and `pyproject.toml`.
- No tests were run and no external network service was contacted. The only shell commands used were `date -Iseconds` for required telemetry.
- Wrote only inside `/home/abhmul/dev/ask-chatgpt`.

END_TIMESTAMP: 2026-06-12T02:24:23-05:00
T1d-STATUS: DONE