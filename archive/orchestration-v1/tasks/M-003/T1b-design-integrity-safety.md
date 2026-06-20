# T1b — DESIGN LENS: integrity & safety (manifest schema, validate-before-mutate, zip-slip-safe apply, oversize caps, failure taxonomy)

**Type:** design (NON-EDITING, spec). **Worker:** pi (GPT 5.5 xhigh). **You inherit NOTHING except this file and what it tells you to read.**
**Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd).**
**Deliverable (write EXACTLY here, create the file):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/design-integrity-safety.md`
**Report length cap:** ~250 lines. Precise, enumerated, no hand-waving on safety. ONE of 3 parallel design lenses; a synthesizer reconciles yours with the GPT-interaction and ergonomics lenses.

## Context — UC2 bundle workflow, retrieval + apply

`ask-chatgpt` zips caller files/dirs into an outgoing bundle (with a catalogue README for GPT), then retrieves a **patch bundle** (changed files only) and can apply it locally. Binding retrieval (D-001, `docs/DECISIONS.md` #2): **download-capture PRIMARY** (Playwright file-download of a real zip) + **checksummed fenced-base64url FALLBACK** (`BEGIN/END_PATCH_BUNDLE` markers + manifest + `ZIP_BYTE_COUNT` + `ZIP_SHA256`, validated before apply).

This lens owns the **integrity and filesystem-safety contract**: how a retrieved bundle is validated, and how it is applied without ever escaping the caller's root or corrupting state on a partial/forged bundle.

## Your single problem (stay in THIS lens)

Produce a precise, implementable spec for:

1. **Manifest schema.** Define the exact fields for the patch-bundle manifest: per-file `path` (repo-root-relative, forward-slash), `size` (bytes), `sha256` (hex), and a change-`kind` (added / modified / deleted), PLUS whole-zip integrity (`zip_byte_count`, `zip_sha256`). Specify types, required/optional, ordering, and how a deletion is represented (no bytes, but a manifest entry). Reconcile with the literal tokens the fixture already emits (`ZIP_BYTE_COUNT`, `ZIP_SHA256`, `manifest`) — quote them from ground truth (below).
2. **Validation order — VALIDATE EVERYTHING BEFORE MUTATING ANYTHING.** Give the exact ordered checklist a retrieved bundle passes before a single byte is written:
   - whole-zip byte count matches; whole-zip SHA-256 matches; zip opens / is not corrupt/truncated;
   - manifest present and parseable; every manifest entry's per-file size + SHA-256 matches the bytes inside the zip; the set of zip entries matches the manifest (no extra/missing);
   - every path is SAFE (see #3); oversize caps respected (#4).
   - Define the all-or-nothing semantics: if ANY check fails, raise the mapped named error and write NOTHING. Specify whether apply is staged (write to temp then atomic-rename) or buffered-in-memory then written — pick one and justify (crash-safety: a mid-apply crash must not leave a half-applied tree).
3. **Zip-slip-safe apply semantics.** The core safety property. Specify precisely how each target path is resolved and rejected:
   - reject absolute paths; reject any `..` traversal component; resolve the final real path and require it to be a descendant of the caller-specified `root` (use realpath/normpath containment, not string prefix alone);
   - reject symlink escapes (a path component that is a symlink pointing outside root; and do not follow symlinks when writing);
   - only ever write within `root` (and, in tests, within the repo's `tmp/`). Deletions: only delete files that exist within root and are named in the manifest.
   - Give the containment-check algorithm in enough detail to implement (and to write adversarial tests against): e.g. `os.path.realpath(join(root, rel))` startswith `realpath(root) + os.sep`.
4. **Oversize caps.** Define caps (a per-file cap and a whole-bundle cap) and where they apply (refuse to fetch/decode/expand beyond cap — a zip-bomb / oversized-base64 must be refused BEFORE expansion). State the caps as named constants with defaults; note they should be overridable. The fixture has an `oversized` fenced variant and the affordance inventory includes oversize cases — your spec must reject them.
5. **Failure taxonomy -> named errors.** Map every failure to an actionable, credential-free named error EXTENDING the existing errors module (`src/ask_chatgpt/errors.py`). The mission names these failure modes: upload/download unsupported, patch malformed, hash/byte-count mismatch, oversized payload, path-escape attempt, response truncated. Propose the error class names (e.g. `PatchMalformedError`, `BundleIntegrityError`/hash+bytecount, `OversizedPayloadError`, `PathEscapeError`, `UploadUnsupportedError`/`DownloadUnsupportedError`, reuse `ResponseTruncatedError`) and the exact actionable message shape for each. Note which already exist vs are new (read errors.py).

## Anchor to ground truth (READ — quote with file:line)
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` — grep `BEGIN_PATCH_BUNDLE`, `END_PATCH_BUNDLE`, `ZIP_BYTE_COUNT`, `ZIP_SHA256`, `manifest`, `download_artifact`, `upload_input`, and the variant names (`bad_hash`, `oversized`, `corrupt`, `truncated`, `changed_and_unchanged`, etc.). Your manifest/validation spec MUST be able to consume what the fixture emits and MUST reject every adversarial variant.
- `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_files.py` — the variant-driving API + assertions.
- `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` — existing named errors (extend, don't duplicate).
- `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` D-001 #2; `/home/abhmul/dev/ask-chatgpt/README.md` honest-failure-modes bullet.

## Deliverable structure (`design-integrity-safety.md`)
- `LENS: integrity-safety`
- Quoted fixture ground-truth tokens + variant list (file:line).
- Manifest schema (table). Validation-order checklist (numbered, with the fail-action per step). Apply semantics (staged vs buffered, with crash-safety justification). Zip-slip containment algorithm (implementable). Oversize caps (named constants + defaults). Failure-taxonomy -> named-error table (new vs existing).
- A mandatory **adversarial test matrix**: each fixture variant (download: missing/delayed/wrong_older/corrupt/truncated/collision/unsupported; fenced: missing_end/bad_hash/changed_and_unchanged/oversized; upload: unsupported/reject_size_type/corrupt) -> expected named error or expected handling. This becomes T3's mandatory test list.
- "Open questions for synthesis."

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). This is a FILE-READING design task.
- PATCH APPLY SAFETY: validate the ENTIRE bundle (manifest, hashes, byte counts, path safety) BEFORE mutating ANY file; reject absolute paths, `..` traversal, and symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); the CLI never mutates local files without an explicit apply flag. (THIS LENS owns the precise spec of these properties.)
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real".
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS (if you run anything). Serialize pytest runs in this tree. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report with `T1b-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED in your report)
- FIRST content line: `ESTIMATE: T1b <minutes>m`.
- `date -Iseconds` at START and END -> literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- LAST line: `T1b-STATUS: DONE|BLOCKED`.
