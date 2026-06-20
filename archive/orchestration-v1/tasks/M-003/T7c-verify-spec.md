# T7c — VERIFY LENS: spec-conformance (independent NON-PRODUCER, read-only). Best-of-N panel member #2 of 3.

You are an INDEPENDENT verifier and a NON-PRODUCER: you did NOT write any M-003 code. You reason OVER the authoritative evidence set produced by T7a — you do **NOT** re-run the heavy suite or acceptance scripts (a second concurrent heavy runner would contend on the shared workspace). Re-derive every judgment from GROUND TRUTH = the binding spec docs + the RAW artifact files + the source. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). Read-only: do NOT edit any source/tests/scripts; do NOT git commit/push.

## Your dimension: SPEC-CONFORMANCE (does the implementation satisfy the BINDING obligations of UC2 + UC3?)
Map EVERY obligation to a concrete artifact/test/source line. A green suite that omits a required obligation is still a FAIL.

## Read FIRST (in order)
1. This contract in full.
2. `README.md` — UC2 + UC3 spec (binding): UC2 bundle-out → catalogue README for GPT → patch bundle (changed-files-only) → retrieve → apply → round-trip diff matches; UC3 `ask-chatgpt` CLI (prompt, session, file args, stdout/file); the named honest-failure modes.
3. `docs/bundle-protocol.md` — the BINDING protocol. Check conformance to: the catalogue/README content the bundle carries, the manifest schema, §5 validate-before-mutate, §6 zip-slip apply, §8 failure taxonomy / named errors, §9 adversarial matrix, §10 public API surface, §11 CLI flags + no-mutate default. (Read the actual section numbers in the doc; the §-references here are approximate — use the doc's real headings.)
4. `docs/DECISIONS.md` — D-001 (download-capture PRIMARY + checksummed fenced-base64url FALLBACK).
5. Evidence: newest `tmp/accept-uc2-*/results.json`, newest `tmp/accept-uc3-*/results.json`, `tmp/verify-m003/pytest.txt`, and `orchestration/reports/M-003/verify-run.md` (provisional summary).
6. Source: `src/ask_chatgpt/bundle.py` (the generated catalogue README + prompt instructions), `src/ask_chatgpt/patch.py`, `src/ask_chatgpt/api.py`, `src/ask_chatgpt/cli.py`, `src/ask_chatgpt/__init__.py`, `src/ask_chatgpt/errors.py`, `pyproject.toml` (`[project.scripts]`).

## REALIZED FACTS (verify against the binding docs — flag any non-conformance)
- §10 surface realized: `ask_chatgpt(..., files=None, dirs=None, bundle_root=None) -> str | AskChatGPTResult{text, patch_bundle}`; `apply_patch(bundle, root, *, dry_run=True) -> DiffSummary`; exports include those + `DiffSummary, FileDiff, PatchBundle` and the named errors. Confirm this matches the protocol's public-API section EXACTLY (names, no-files path returns plain `str`).
- §11 CLI realized: console script `ask-chatgpt = "ask_chatgpt.cli:main"`; flags `prompt`/`--prompt`, `--session`, `--model-settings`, `--files`/`--dirs`, `--out`, `--dry-run`/`--apply` (mutually exclusive), `--root` (required for dry-run/apply), `--channel`, `--base-url`, `--profile-path`, `--timeout`; no-mutate default; exit-code map 0/2/3-12/1. Confirm vs the protocol CLI section.
- **DEVIATION (a) to adjudicate:** T3 corrected the T2 upload mapping so that the mock UI `reject_size_type` rejection (AFTER a local preflight) raises `UploadUnsupportedError`, while a LOCAL preflight size-cap breach raises `OversizedPayloadError`. Read the protocol's failure-taxonomy section and the upload tests (`tests/test_bundle_out.py`) and RULE whether this mapping conforms. State PASS/FAIL with the protocol quote you relied on.

## Checks (each: PASS|FAIL + cite the binding doc section/line + the conforming artifact/source)
1. **UC2 round-trip obligation:** Confirm bundle-out → patch-back → apply → **diff matches** is satisfied for BOTH retrieval paths (download-primary + fenced-fallback), per the newest `accept-uc2` `results.json` AND `tests/test_uc2_roundtrip.py`. The "changed-files-only" patch must include ≥1 modified + ≥1 added + ≥1 deleted. Cite.
2. **Catalogue README conformance:** Read what `bundle.py` actually generates as the in-bundle catalogue/README + GPT response instructions. Confirm its CONTENT matches what the protocol says it must contain (what's inside / how GPT should respond / how to return a changed-files-only patch bundle / downloadable-zip-preferred + fenced-fallback format). Quote the protocol requirement and the generated text. Flag any required element missing.
3. **§10 public API conformance:** Confirm the realized surface == the protocol's public-API section (signature, result type, exports, UC1 no-files path preserved as `str`).
4. **§11 CLI conformance:** Confirm the realized flags + no-mutate default + `[project.scripts]` == the protocol CLI section.
5. **Honest-failure-mode coverage:** For EACH README-named failure mode (upload unsupported, download unsupported, patch malformed, hash/byte-count mismatch, oversized payload, path-escape attempt, response truncated), confirm a named error class exists in `errors.py`, is raised on the corresponding adversarial fixture variant (cite the test in `test_patch.py`/`test_bundle_out.py`), and (for the CLI) maps to a distinct exit code. Build the table.
6. **DEVIATION (a) adjudication:** As above — rule conformant or not, with the protocol quote.
7. **D-001 conformance:** Confirm retrieval is download-capture PRIMARY with checksummed fenced-base64url FALLBACK (not the reverse), per `patch.py` + the tests.

## Deliverable — `orchestration/reports/M-003/verify-spec.md` (≤180 lines)
- Header `LENS: spec-conformance`.
- One `CHECK <n>: PASS|FAIL` section each, with the binding-doc citation + the conforming evidence.
- The honest-failure-mode coverage TABLE (mode → error class → test id → CLI exit code).
- A line `V-SPEC-VERDICT: PASS|FAIL` (FAIL if any obligation is unmet OR deviation (a) is non-conformant; explain).
- Telemetry v2: FIRST line `ESTIMATE: T7c <min>m`; `date -Iseconds` START+END → literal `START_TIMESTAMP:`/`END_TIMESTAMP:`.
- LAST line: `T7c-STATUS: DONE|BLOCKED`.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. ZERO new pip deps. You run NOTHING heavy — you READ docs + artifacts + source. Do NOT re-run the full suite or acceptance scripts — T7a is the sole heavy runner.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your report only). Do NOT edit any source/tests/scripts. Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv run` from repo root ONLY; never bare `python`/`pip`. Kill only processes your own run started. NEVER `git push`/`git commit`.
- End your report with `T7c-STATUS: DONE|BLOCKED` as the LAST line.
