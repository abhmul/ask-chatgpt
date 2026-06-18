# T1d — SYNTHESIS: reconcile the 3 design lenses into the binding `docs/bundle-protocol.md`

**Type:** synthesis (NON-EDITING source; writes ONE new doc + a short report). **Worker:** pi (GPT 5.5 xhigh). **You inherit NOTHING except this file and what it tells you to read.**
**Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd).**
**Deliverables (write EXACTLY here, create them):**
- `/home/abhmul/dev/ask-chatgpt/docs/bundle-protocol.md` — the binding protocol spec (users + GPT + the implementers T2-T5 follow it).
- `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/T1d-report.md` — telemetry + a "conflicts reconciled" log + status line.

You are the best-of-N SYNTHESIZER for the UC2 bundle-protocol design. Three parallel design lenses were produced INDEPENDENTLY; your job is to produce ONE coherent, implementation-grade spec: keep the strongest elements of each, reconcile conflicts with an explicit decision + rationale, and ensure the result is precise enough that four downstream implementers can build to it with no further design choices.

## Read these FIRST, IN FULL (the 3 lens reports — they are your inputs)
1. This contract.
2. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/design-gpt-interaction.md` (LENS gpt-interaction): catalogue-README content + GPT response/patch-bundle instructions + the fence/marker format.
3. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/design-integrity-safety.md` (LENS integrity-safety): manifest schema, validation order, zip-slip-safe apply, oversize caps, failure taxonomy -> named errors, adversarial test matrix.
4. `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/design-ergonomics.md` (LENS ergonomics): `ask_chatgpt(files=...)` extension + return type, `apply_patch()` + DiffSummary + dry_run, CLI flags + `[project.scripts]` + stdout/exit conventions + no-mutate default.

## Re-anchor to GROUND TRUTH (do NOT trust the lenses blindly — verify their fixture claims)
5. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` — confirm the LITERAL parser-facing tokens the implementers must match: `BEGIN_PATCH_BUNDLE`, `END_PATCH_BUNDLE`, `ZIP_BYTE_COUNT`, `ZIP_SHA256`, the manifest shape, and the `download_artifact` / `upload_input` affordances + their variant names. If a lens proposed a format the fixture cannot emit/parse, the FIXTURE WINS for the parser-facing tokens — reconcile to it and note the correction.
6. `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_files.py` — the variant list each path must handle.
7. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` D-001 (#2 binding: download-capture primary + checksummed fenced fallback); `/home/abhmul/dev/ask-chatgpt/README.md` (UC2/UC3 spec + honest-failure list); `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/api.py` + `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` + `/home/abhmul/dev/ask-chatgpt/pyproject.toml` (back-compat anchors for the API/CLI/errors sections).

## `docs/bundle-protocol.md` — required sections (implementation-grade; this is the binding contract for T2-T5)
1. **Overview + round-trip lifecycle** — the end-to-end flow (caller files/dirs -> outgoing bundle -> GPT -> patch bundle -> validate -> apply -> diff), one diagram/列 acceptable.
2. **Outgoing bundle format (UC2 bundle-out, implemented by T2)** — zip layout; the **catalogue README** full content/template GPT reads; the accompanying **prompt instructions** sent with the upload; path conventions (repo-root-relative, forward-slash, no absolute, no `..`); size/type guard at build time.
3. **Patch-bundle return format (retrieved by T3)** — BOTH paths with PRIMARY/FALLBACK priority: (a) download-capture (Playwright download of a real zip); (b) checksummed fenced base64url fallback with the EXACT literal markers/manifest/`ZIP_BYTE_COUNT`/`ZIP_SHA256` (quoted from the fixture). Specify how the retriever decides primary-vs-fallback.
4. **Manifest schema** — fields, types, required/optional, per-file (path, size, sha256, change-kind added/modified/deleted) + whole-zip (byte count, sha256); deletion representation.
5. **Validation order (validate EVERYTHING before mutating ANYTHING)** — the exact ordered checklist; all-or-nothing semantics; apply mechanism (staged-temp + atomic rename vs buffered) with crash-safety rationale.
6. **Zip-slip-safe apply** — the containment algorithm (realpath-under-root), reject absolute/`..`/symlink-escape, write only within caller root; deletion safety.
7. **Oversize caps** — named constants + defaults (per-file + whole-bundle); refuse BEFORE expansion (zip-bomb / oversized-base64).
8. **Failure taxonomy -> named errors** — the table mapping each failure (upload/download unsupported, patch malformed, hash/byte-count mismatch, oversized payload, path-escape attempt, response truncated) to an actionable, credential-free named error EXTENDING `errors.py`; mark new vs existing class names.
9. **Adversarial handling matrix** — each fixture variant (download: missing/delayed/wrong_older/corrupt/truncated/collision/unsupported; fenced: missing_end/bad_hash/changed_and_unchanged/oversized; upload: unsupported/reject_size_type/corrupt) -> expected outcome/named error. (This is the MANDATORY test list for T3.)
10. **Public API surface (T4 wires it)** — `ask_chatgpt(...)` extended signature (UC1 path unchanged) + the result/patch-handle type; `apply_patch(bundle, root, *, dry_run=...) -> DiffSummary` + the DiffSummary shape + dry_run contract; the `__init__` exports.
11. **CLI (UC3, T5)** — `[project.scripts]` line; the full flag table; stdout/stderr/exit-code conventions; the **no-mutation-without-explicit-apply-flag** rule; library-first invariant (no logic in the CLI the library lacks).
12. **Rationale + reconciled conflicts** — for each place the three lenses disagreed, the decision taken and why (Occam: prefer the simplest correct design).

## Reconciliation rules
- Parser-facing tokens: the FIXTURE is ground truth (quote it). D-001 is binding (download primary + fenced fallback). README UC2/UC3 spec is binding.
- Back-compat: the UC1 `ask_chatgpt(...) -> text` behavior with no files MUST be preserved exactly.
- Safety is non-negotiable: validate-before-mutate, zip-slip rejection, oversize caps, no-mutate CLI default all stay.
- Prefer the simplest correct design; cut accreted complexity; justify any non-obvious choice.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). This is a FILE-READING synthesis task — no network, no code execution required.
- PATCH APPLY SAFETY: validate the ENTIRE bundle (manifest, hashes, byte counts, path safety) BEFORE mutating ANY file; reject absolute paths, `..` traversal, and symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); the CLI never mutates local files without an explicit apply flag. (Encode these precisely in the spec.)
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real".
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS (if you run anything). Serialize pytest runs in this tree. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report (`T1d-report.md`) with `T1d-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED in `T1d-report.md`)
- FIRST content line: `ESTIMATE: T1d <minutes>m`.
- `date -Iseconds` at START and END -> literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- Report: the section outline of `bundle-protocol.md`; the list of conflicts reconciled (lens-vs-lens) + each decision; any fixture-token correction you made against a lens; trust notes.
- LAST line: `T1d-STATUS: DONE|BLOCKED`.
