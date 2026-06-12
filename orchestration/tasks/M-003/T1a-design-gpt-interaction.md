# T1a — DESIGN LENS: GPT-interaction (catalogue README + response instructions that maximize patch-bundle compliance)

**Type:** design (NON-EDITING, research/spec). **Worker:** pi (GPT 5.5 xhigh). **You inherit NOTHING except this file and what it tells you to read.**
**Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd).**
**Deliverable (write EXACTLY here, create the file):** `/home/abhmul/dev/ask-chatgpt/orchestration/reports/M-003/design-gpt-interaction.md`
**Report length cap:** ~250 lines. Dense, concrete, with rationale. This is ONE of 3 parallel design lenses; a synthesizer will reconcile yours with the other two — so be opinionated and justify, do not hedge into mush.

## Context — the thing being built (UC2 bundle workflow)

`ask-chatgpt` exposes the operator's ChatGPT.com browser UI as a callable function. UC2 = local-filesystem round-trip via a **bundle workflow**:
1. The caller passes a list of files/dirs; the tool **zips them into a bundle** that includes a generated **README / informational catalogue file for GPT** (what's inside, how to respond).
2. When GPT needs to make edits, it is asked to return a **patch bundle** — a bundle containing ONLY the changed files — which the tool retrieves and can apply locally.
3. Round-trip acceptance: bundle out -> (mock) GPT edits -> patch bundle back -> applied locally -> diff matches expectation.

Binding retrieval design (D-001, `docs/DECISIONS.md`): patch bundle returns via **download-capture PRIMARY** (Playwright file-download of a real zip) + **checksummed fenced-base64url FALLBACK** over the text channel (`BEGIN/END_PATCH_BUNDLE` markers, a manifest, byte count, SHA-256, validated before apply).

## Your single problem (stay in THIS lens — the GPT-facing prompt-engineering interface)

Design the **exact text content** of two artifacts. Treat wording as a design artifact: every instruction has a rationale tied to making GPT's response machine-parseable and compliant.

1. **The catalogue README embedded in the outgoing bundle** (the file GPT reads first inside the zip). Specify its concrete sections and the actual prose/templated text:
   - What the bundle is, the file inventory (how to present paths + sizes so GPT can refer to them unambiguously), and the project root convention.
   - **How to respond when making edits:** GPT must return a **patch bundle containing ONLY changed files** (not the whole tree) — say this unambiguously, with an example. Define how GPT references file paths (repo-root-relative, forward slashes, no absolute paths, no `..`).
   - **Channel instruction (both paths, with PRIMARY/FALLBACK priority):** (a) PREFERRED — produce a downloadable `.zip` of the changed files; (b) FALLBACK when a download cannot be produced — emit the changed files as a **single fenced base64url block** between exact `BEGIN_PATCH_BUNDLE` / `END_PATCH_BUNDLE` markers, preceded by a manifest and a `ZIP_BYTE_COUNT:` and `ZIP_SHA256:` line. Give the EXACT literal fence/marker format GPT must emit so the tool's parser can extract it deterministically.
   - Rules that reduce ambiguity: no commentary inside the fenced block; exactly one bundle per response; how to signal "no changes needed"; how to indicate a new file vs a modified file vs a deletion.
2. **The response/prompt instructions** the tool sends alongside the bundle (the prompt text accompanying the upload) — the imperative version of the above, tuned so a real GPT model complies. Note where this overlaps the README and why both exist (the README travels in the zip; the prompt is the chat message).

## Anchor your design to the ACTUAL fixture parser contract (read these — do not invent a format the parser cannot read)

The mock fixture already emits the fenced fallback in a specific shape; the real tool parser must match it. READ to learn the exact tokens already in play:
- `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` — grep `BEGIN_PATCH_BUNDLE`, `END_PATCH_BUNDLE`, `ZIP_BYTE_COUNT`, `ZIP_SHA256`, `manifest`, `download_artifact`, `upload_input`. Quote the literal marker strings and manifest fields the fixture uses.
- `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_files.py` — how those payloads are driven/asserted (the variant names: missing_end / bad_hash / changed_and_unchanged / oversized for fenced; missing/delayed/wrong_older/corrupt/truncated/collision/unsupported for download).
- `/home/abhmul/dev/ask-chatgpt/README.md` (UC2 spec) and `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` (D-001 #2).

Your fence/manifest format MUST be reconcilable with what the fixture already emits — if you propose a refinement, state it as a delta and justify it, but the parser-facing tokens (`BEGIN_PATCH_BUNDLE`/`END_PATCH_BUNDLE`/`ZIP_BYTE_COUNT`/`ZIP_SHA256`) are fixed ground truth — quote them verbatim from the fixture.

## Deliverable structure (`design-gpt-interaction.md`)
- `LENS: gpt-interaction`
- The verbatim quoted fixture tokens (proof you anchored to ground truth, with file:line).
- The full catalogue-README content/template (copy-pastable).
- The full accompanying prompt-instructions text.
- A short "compliance rationale" table: instruction -> why it improves parseability/compliance.
- "Open questions for synthesis" (conflicts the integrity or ergonomics lens may need to resolve).

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). This is a FILE-READING design task — no network, no code execution required.
- PATCH APPLY SAFETY (for your awareness as you design the format): validate the ENTIRE bundle (manifest, hashes, byte counts, path safety) BEFORE mutating ANY file; reject absolute paths, `..` traversal, and symlink escapes; write only within the caller-specified root (and this repo's `tmp/` in tests); the CLI never mutates local files without an explicit apply flag.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real".
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv.
- `uv sync --all-groups` ALWAYS (if you run anything). Serialize pytest runs in this tree. Kill only processes your own run started. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End your report with `T1a-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED in your report)
- FIRST content line: `ESTIMATE: T1a <minutes>m` (your up-front wall-clock estimate).
- `date -Iseconds` at START and END -> literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- LAST line: `T1a-STATUS: DONE|BLOCKED` (watchers gate on `tail -1`).
