# MISSION-003 — Bundle workflow (UC2) + CLI (UC3) + real-site acceptance runbook

**Mission type:** design (best-of-N) + implement (TDD/RED-first, single-editor legs) + best-of-N verification panel.
**Dispatched by:** ask-chatgpt team lead, 2026-06-12.
**Wall-clock estimate:** `ESTIMATE: M-003 120m` (flag threshold 2× = 240 min).

## Read these files FIRST (in order)

1. `docs/DECISIONS.md` — D-001 binding: bundle retrieval = download-capture PRIMARY + checksummed fenced-base64url FALLBACK; text reader order DOM-primary (already built).
2. `README.md` — UC2 + UC3 spec (binding, transcribed below) + acceptance shape + honest failure modes.
3. `orchestration/handoffs/MISSION-002-handoff.json` — what exists, trust levels, and the fixture affordances you CONSUME (inventory below).
4. `orchestration/state/M-003-state.json` — create and maintain resume-ready at all times.

## Spec (README, binding)

- UC2: "the caller passes a list of relevant files and/or directories; the tool zips them into a bundle that includes a README / informational catalogue file for GPT (what's inside, how to respond); when GPT needs to make edits, it is asked to return a patch bundle — a bundle containing only the files that changed — which the tool retrieves and can apply locally." Round-trip acceptance: bundle out → (mock) GPT edits → patch bundle back → applied locally → diff matches expectation.
- UC3: "`ask_chatgpt` callable from the command line (e.g. an `ask-chatgpt` CLI wrapping the function: prompt, session, file args, output to stdout/file)."
- Honest failure modes, named actionably (extend the existing errors module): upload/download unsupported, patch malformed, hash/byte-count mismatch, oversized payload, path-escape attempt, response truncated.

## What ALREADY EXISTS (M-002, verified — do NOT rebuild; extend only on genuine gap)

- `src/ask_chatgpt/`: errors, session_registry, selector_map (fail-closed), driver (mock/real channels, completion detector), readers (DomReader primary + CopyButtonReader fallback), api.ask_chatgpt() — UC1 mock-proven (60 tests green; `scripts/accept_uc1.sh`).
- Mock fixture (`tests/fixtures/mock_chatgpt/server.py`) ALREADY serves the bundle affordances M-003 consumes:
  - `download_artifact`: real zip + Content-Disposition, variants missing / delayed / wrong_older / corrupt / truncated / collision / unsupported → for download-capture-primary retrieval;
  - fenced base64url payload: `BEGIN/END_PATCH_BUNDLE` + manifest + `ZIP_BYTE_COUNT` + `ZIP_SHA256`, variants missing_end / bad_hash / changed_and_unchanged / oversized → for the fenced fallback;
  - `upload_input`: `<input type=file>` + metadata recording, variants unsupported / reject_size_type / corrupt → for bundle-out.
- Network guard (autouse socket guard + route interception) — every new test runs under it.

## Task plan (manager refines; per operator emphasis 2026-06-12, best-of-N is the DEFAULT for every non-editing leg — never narrow N for resource caution; pi workers have NO concurrency cap; EDITING legs serialize)

- **T1 bundle-protocol design — best-of-N=3 PARALLEL lenses + synthesis (non-editing):**
  - T1a GPT-interaction lens: the catalogue README content + response instructions that maximize patch-bundle compliance from GPT (how to ask for changed-files-only; downloadable-zip preferred, fenced-base64url fallback with exact fence/manifest format; how GPT should reference file paths). This text IS the prompt-engineering interface — treat wording as a design artifact with rationale.
  - T1b integrity/safety lens: manifest schema (paths, sizes, SHA-256 per file + whole-zip), validation order (validate EVERYTHING before mutating ANYTHING), zip-slip-safe apply semantics (reject absolute paths, `..`, symlink escapes; apply only within the caller-specified root), oversize caps, failure taxonomy mapped to named errors.
  - T1c ergonomics lens: `ask_chatgpt()` signature extension (e.g. `files=[...]`, returned patch handle), apply API (`apply_patch(bundle, root, dry_run=...)` returning a diff summary), CLI flags (`--files/--dirs --session --model-settings --out --apply/--dry-run`), stdout conventions. CLI default posture: NO local mutation without an explicit apply flag.
  - T1d synthesis (fresh worker) → `docs/bundle-protocol.md` (the protocol spec users and GPT see; rationale included; conflicts reconciled).
- **T2** implement bundle-out: zip builder from files/dirs + generated catalogue README per protocol; size/type guard; upload via existing driver/fixture affordance. [single editor, TDD]
- **T3** implement patch retrieval + apply: download-capture primary (fixture `download_artifact`), fenced-base64url fallback, full validation (manifest + SHA-256 + byte count) BEFORE any write; zip-slip-safe apply, changed-files-only, dry-run diff. [single editor, TDD — adversarial variants above are MANDATORY test cases]
- **T4** UC2 round-trip E2E (bundle out → mock edits → patch back → apply → diff matches) + `scripts/accept_uc2.sh` (ephemeral port, raw artifacts to `tmp/accept-uc2-<ts>/`, nonzero on failure). [single editor]
- **T5** CLI: `ask-chatgpt` console script (`[project.scripts]`), wrapping the public function ONLY (library-first; no logic in the CLI that the library lacks); UC3 acceptance via subprocess against the mock + `scripts/accept_uc3.sh`. [single editor, TDD]
- **T6** real-site acceptance runbook `docs/runbooks/real-site-acceptance.md` (non-editing; parallel-ok): the operator-gated halves for UC1+UC2+UC3 — per use case: 1–2 commands with inline typed-consent prompt, expected observations, honest-failure interpretations; PREREQUISITE section pointing at `docs/runbooks/observe-chatgpt-unknowns.md` (fills `selector_maps/real.json`); NEVER run by automation.
- **T7 verification — best-of-N PANEL (operator-emphasized; N=3 + synthesis):**
  - T7a evidence runner (non-producer): fresh `uv sync --all-groups`; FULL `uv run pytest` (UC1 regression included); `scripts/accept_uc1.sh` + `accept_uc2.sh` + `accept_uc3.sh`; deliberate zip-slip attempt + deliberate network-guard violation (both must fail safely); capture ALL raw output to `tmp/verify-m003/` as the ONE authoritative evidence set.
  - T7b/T7c/T7d PARALLEL read-only lenses over T7a evidence + code: correctness/reproduction; spec-conformance (UC2+UC3 obligations incl. round-trip diff-matches and catalogue README content vs protocol doc); safety (zip-slip variants all rejected, validation-before-mutation proven, no credential reads, loopback-only, CLI no-mutate default).
  - T7e synthesis → `orchestration/reports/M-003/verify.md`, per-dimension verdicts + final `VERDICT: PASS|FAIL` + `T7-STATUS:` last line. On FAIL: revive offending leg (REWORK-CAUSE coded), re-run evidence + failed dimensions.

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed).
- PATCH APPLY SAFETY: validate the ENTIRE bundle (manifest, hashes, byte counts, path safety) BEFORE mutating ANY file; reject absolute paths, `..` traversal, and symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); the CLI never mutates local files without an explicit apply flag.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real".
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS. Serialize pytest runs in this tree. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report with `T<ID>-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (unchanged from M-002; pi minute self-reports are hallucinated)

- Workers: `date -Iseconds` → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines + `ESTIMATE: T<ID> <min>m`. Manager derives `ACTUAL` from `.pi-workers/<run>/metadata.txt started_at` + report `END_TIMESTAMP` / mtimes.
- Manager handoff: `ESTIMATE: M-003 120m`, derived `ACTUAL`, end timestamp, `REWORK-CAUSE:` per rework leg, as TOP-LEVEL JSON FIELDS (M-002's were prose-embedded; keep them machine-greppable too: emit bare `ESTIMATE:`/`ACTUAL:` lines in your final log message).

## Worker mechanics

- pi via `bash .claude/skills/orchestration/references/pi-worker-watch.sh "<pointer>"` from repo root; FOREGROUND blocking watches (you die at turn end). NO pi concurrency cap; editing legs serialize; T1 lenses and T7 panel run fully parallel; T6 may overlap any editor leg.
- Worker contracts under `orchestration/tasks/M-003/`, fully self-contained (SAFETY BLOCK verbatim; exact deliverable paths; the files to read; report cap ~200 lines).

## Handoff (`orchestration/handoffs/MISSION-003-handoff.json`)

Rigor protocol (STATUS top; verified-what + evidence; artifacts + trust; blockers exact; recommended next; complexity signals). State mock-proven vs real-site-unproven honestly. Recommend M-004 (independent directive verification) readiness. Commit prefix `M-003:`; final closeout commit includes handoff + verify reports. NEVER push.
