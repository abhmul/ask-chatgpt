# T1c — DESIGN LENS: ergonomics (public API surface, apply API, CLI flags, stdout conventions, no-mutate default)

**Type:** design (NON-EDITING, spec). **Worker:** pi (GPT 5.5 xhigh). **You inherit NOTHING except this file and what it tells you to read.**
**Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd).**
**Deliverable (write EXACTLY here, create the file):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/design-ergonomics.md`
**Report length cap:** ~250 lines. Concrete signatures + flag tables. ONE of 3 parallel design lenses; a synthesizer reconciles yours with the GPT-interaction and integrity/safety lenses.

## Context — library-first; the function is the product, the CLI wraps it

`ask-chatgpt` is library-first (README "Design constraints"): the Python function is the product; the CLI is a THIN wrapper that adds NO logic the library lacks. UC2 adds a bundle round-trip (send files -> retrieve a changed-files-only patch bundle -> apply locally). UC3 adds a console-script CLI. This lens defines the **caller-facing ergonomics**: function signatures, the apply API, CLI flags, stdout/exit conventions, and the no-mutation-by-default safety posture.

## What already exists (READ to extend, do NOT redesign)
- `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/api.py` — the current public `ask_chatgpt(...)` (UC1). Read its EXACT current signature, return type, and how `session_identifier` / `model_settings` / channel are handled. Your extension must be backward-compatible (existing UC1 callers unchanged).
- `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/__init__.py` — the current public export surface (what names are exported).
- `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` — named errors callers catch.
- `/home/abhmul/dev/ask-chatgpt/README.md` UC2 + UC3 spec; `/home/abhmul/dev/ask-chatgpt/pyproject.toml` (for `[project.scripts]` console-script wiring + current deps).

## Your single problem (stay in THIS lens)

Design the caller-facing surface, concretely:

1. **`ask_chatgpt()` signature extension for UC2.** How does a caller pass files/dirs and get back a patch handle? Propose the exact signature delta — e.g. `files: list[str|Path] | None = None`, `dirs: list[...] | None = None` (or a unified `paths=`) — and the RETURN shape when files are sent. Decide: does `ask_chatgpt(files=...)` return just the text, or a richer result object carrying the response text AND a retrieved patch-bundle handle? Define that result type (fields, types). Keep UC1 (`-> text` with no files) behavior intact. Justify the return-shape choice (back-compat + discoverability).
2. **Apply API.** Define `apply_patch(bundle, root, *, dry_run: bool = ...) -> <DiffSummary>`: parameters, the patch-handle/bundle input type, the `root` (caller-specified apply root), and the returned **diff summary** type (per-file: path, change-kind added/modified/deleted, bytes-changed or line-stat; plus an overall summary). Specify `dry_run` semantics: compute and return the diff summary WITHOUT writing. Decide the default for `dry_run` at the LIBRARY level (recommend: explicit, no silent default mutation) and justify. Note: the actual validation/zip-slip/write mechanics are owned by the integrity-safety lens — you define the SIGNATURE + the diff-summary shape + the dry-run contract, and reference that the apply MUST validate-before-mutate.
3. **CLI design (UC3).** Define the `ask-chatgpt` console script:
   - `[project.scripts]` entry (e.g. `ask-chatgpt = "ask_chatgpt.cli:main"`).
   - Full flag table: `--prompt`/positional, `--session`, `--model-settings` (how passed: repeatable `k=v`? JSON?), `--files`/`--dirs` (repeatable), `--out FILE` (else stdout), `--apply` / `--dry-run` (apply a retrieved patch bundle to a `--root`), and any `--root`. For EACH flag: type, default, repeatability, help text.
   - **No-mutation default (SAFETY):** the CLI MUST NOT mutate local files without an explicit `--apply` flag; `--dry-run` shows the diff summary and writes nothing; `--apply` without an explicit root must error rather than guess. Specify this precisely.
   - **stdout/exit conventions:** what goes to stdout (response text by default; the diff summary on apply/dry-run) vs stderr (diagnostics); exit codes (0 success; nonzero per failure class — map to the named errors). Keep machine-friendliness (e.g. the response text is the only thing on stdout by default, so the CLI is pipe-friendly).
4. **Library-first invariant.** State explicitly which logic lives in the library vs the CLI (answer: ALL logic in the library; the CLI only parses args, calls the public functions, formats output, sets exit codes). Flag any temptation to put logic in the CLI as a thing to avoid.

## Deliverable structure (`design-ergonomics.md`)
- `LENS: ergonomics`
- The CURRENT `ask_chatgpt` signature quoted from api.py (file:line) — proof of back-compat anchoring.
- Proposed `ask_chatgpt(...)` extended signature + return-type definition (UC1 path unchanged).
- `apply_patch(...)` signature + DiffSummary type + dry_run contract.
- CLI flag table + `[project.scripts]` line + stdout/stderr/exit-code conventions + the no-mutate-default rule.
- Library-vs-CLI responsibility split.
- "Open questions for synthesis."

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). This is a FILE-READING design task.
- PATCH APPLY SAFETY (informs your apply/CLI contract): validate the ENTIRE bundle (manifest, hashes, byte counts, path safety) BEFORE mutating ANY file; reject absolute paths, `..` traversal, and symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); **the CLI never mutates local files without an explicit apply flag** (this lens specifies that flag contract).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real".
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS (if you run anything). Serialize pytest runs in this tree. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report with `T1c-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED in your report)
- FIRST content line: `ESTIMATE: T1c <minutes>m`.
- `date -Iseconds` at START and END -> literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- LAST line: `T1c-STATUS: DONE|BLOCKED`.
