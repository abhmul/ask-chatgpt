# T2 — IMPLEMENT bundle-out: zip builder + generated catalogue README + prompt instructions + size/type guard + upload. TDD vs the mock fixture. SINGLE EDITOR.

You are an INDEPENDENT pi worker and the ONLY editor of this repo right now. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). M-002 is DONE/committed (UC1 `ask_chatgpt()->text` mock-proven, 60 tests green). M-003 design is DONE: `docs/bundle-protocol.md` is the BINDING spec.

**Your slice is NARROW: build the outgoing bundle (zip + catalogue README + prompt text) and upload it. Do NOT implement patch retrieval/apply (that is T3). Do NOT wire `ask_chatgpt(files=...)` or the CLI (that is T4/T5).** Keep it self-contained and verifiable.

## STEP 0 — Confirm you inherit a GREEN tree
Run `uv sync --all-groups` (MANDATORY `--all-groups`) then `uv run pytest -q`. MUST be green (60 passed; ~30s). If not green, STOP and report BLOCKED with the exact failing output — do not edit anything.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/docs/bundle-protocol.md` — THE BINDING SPEC. Implement to it exactly. Your sections: **§1 (lifecycle), §2 (Outgoing bundle format) — the zip layout, the full `ASK_CHATGPT_BUNDLE_README.md` catalogue template, the accompanying prompt-instructions text, path rules, bundle identity, inventory**; plus the bundle-out-relevant parts of **§7 (oversize caps — the size/type guard at build time)** and **§8 (failure taxonomy → named errors)** for upload failures. Read the whole doc for context; implement only the bundle-OUT + upload responsibilities here.
3. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — D-001 (operator-owned profile; tool never reads/stores/logs credentials/profile; loopback-only tests; fail-closed).
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` — existing named errors. EXTEND with any upload/bundle-build errors §8 names (e.g. `UploadUnsupportedError`, an oversize/type-guard error) — actionable, credential-free messages. Do NOT duplicate existing ones.
5. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/driver.py` — the `BrowserSession` surface (channels, `.page`, `.selectors`, how it navigates the mock). You upload through it.
6. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/selector_map.py` + `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/selector_maps/mock.json` — the `upload_input` selector key (fail-closed loader).
7. `/home/abhmul/dev/ask-chatgpt/tests/fixtures/mock_chatgpt/server.py` — the `upload_input` affordance (`<input type=file>` + metadata recording) and its variants: `unsupported`, `reject_size_type`, `corrupt`. Grep `upload_input`, `upload`, and the variant names.
8. `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_files.py` + `/home/abhmul/dev/ask-chatgpt/tests/conftest.py` — how the `mock_chatgpt` fixture is driven (`.base_url`, `.reset()`, `.script_next_response(...)`/`/__script__`, `.inspect()`) and how upload variants are scripted/asserted. Match this style in your tests.

## Scope — create `src/ask_chatgpt/bundle.py` (you may split, e.g. a small `catalogue.py`, but keep it tight)
1. **Bundle builder.** A function/class that takes selected files and/or directories + a `root` and produces an in-memory zip (bytes) per §2: flat-from-root layout, repo-root-relative POSIX entry names, deterministic lexicographic order, the generated `ASK_CHATGPT_BUNDLE_README.md` catalogue at archive root, no `./` prefixes. Enforce path rules AT BUILD TIME: reject absolute paths, `..`, backslashes, NUL, empty segments; reject/dedupe duplicate normalized paths; FAIL if a selected file would collide with the reserved `ASK_CHATGPT_BUNDLE_README.md` name. Directory inputs expand to their regular files (define + document symlink handling — do not follow symlinks out of root). Skip nothing silently — a rejected path is an actionable error, not a silent drop.
2. **Catalogue README generator.** Produce the exact `ASK_CHATGPT_BUNDLE_README.md` content from §2's template, filling the inventory (paths + sizes), project-root name, bundle identity, and the response/patch-bundle instructions (changed-files-only; download-preferred, fenced-fallback with the literal `BEGIN_PATCH_BUNDLE`/`END_PATCH_BUNDLE`/`ZIP_BYTE_COUNT`/`ZIP_SHA256`/`MANIFEST_JSON` format). Deterministic output (same inputs → byte-identical README).
3. **Prompt-instructions text generator.** Produce the accompanying chat-message text from §2's "Accompanying prompt-instructions text" template (the imperative version sent with the upload).
4. **Size/type guard (build-time).** Per §7 caps (named constants, overridable; test-mode override-able). Refuse to build an oversized bundle BEFORE producing it; refuse disallowed entry types per the protocol.
5. **Upload.** A function that, given a `BrowserSession` (channel="mock" in tests) and the built zip, uploads via the `upload_input` affordance and returns whatever handle/confirmation the protocol/driver expects. Map failures to named errors: `unsupported` variant → `UploadUnsupportedError`; `reject_size_type` → the size/type-guard error; `corrupt` → an actionable error. Never read/store/log profile/credentials.

### TDD tests — `tests/test_bundle_out.py` (write FIRST, watch them fail, then implement) — channel="mock" ONLY
Cover, driving the `mock_chatgpt` fixture (headless chromium, loopback):
- Catalogue README: generated content contains the §2-required elements (inventory rows for each file with sizes; the changed-files-only instruction; the literal fence tokens; path rules) and is deterministic (build twice → identical).
- Zip layout: README at archive root; selected files at repo-root-relative POSIX names; deterministic lexicographic order; no `./`.
- Path-rule rejections (build-time): absolute path → error; `..` → error; reserved-name collision (`ASK_CHATGPT_BUNDLE_README.md`) → error; duplicate normalized path → error.
- Size/type guard: oversized selection → guard error BEFORE upload; disallowed type → guard error.
- Upload happy path: upload succeeds against the fixture; the fixture's recorded metadata reflects the uploaded bundle (assert via `.inspect()`).
- Upload failures: `unsupported` → `UploadUnsupportedError`; `reject_size_type` → guard/size-type error; `corrupt` → actionable error.
- Full `uv run pytest -q` GREEN (60 existing + your new tests). Bound any waits.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports. No new external downloads expected (chromium already installed). ZERO new pip deps (stdlib `zipfile`/`hashlib`/`base64` + existing `playwright` only).
- PATCH APPLY SAFETY (you build the OUTGOING bundle; apply is T3, but the same path discipline applies to bundle building): reject absolute paths, `..` traversal, and symlink escapes; operate only within the caller-specified root (and this repo's `tmp/` in tests).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. The real channel stays fail-closed; no test or script sets channel="real". Every test navigates ONLY to `mock_chatgpt.base_url`.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never its `archive/` or `human/`). Never write `.claude/` or `.agents/`. Never touch the shared agent venv (`~/.local/share/agent-python/.venv`).
- Python: `uv run <cmd>` from repo root ONLY; NEVER bare `python`/`pip`. `uv sync --all-groups` ALWAYS. Serialize pytest runs in this tree. Kill only browsers/processes your own run started. NEVER `git push`. Do NOT `git commit` (the manager commits the slice). Do not break the 60 existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.
- End your report with `T2-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-003/T2-report.md`, ≤200 lines)
- FIRST content line: `ESTIMATE: T2 <minutes>m`.
- `date -Iseconds` at START and END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- Report: files created/modified; the public surface you built (functions/classes + which errors each raises + new error classes added to errors.py); how the size/type guard + path-rule rejection work; how upload maps the 3 fixture variants; the EXACT `uv run pytest -q` summary line (count); deviations from the protocol (with reason) if any; trust notes (loopback-only, no credential/profile reads, zero new deps).
- LAST line: `T2-STATUS: DONE` (or `BLOCKED` + exact error + next action).

## Success criteria (all must hold)
- `bundle.py` builds a §2-conformant zip (README + files, deterministic, path-rules enforced at build) + generates the catalogue README + prompt text + a §7 size/type guard.
- Upload through the driver/`upload_input` affordance works against the mock and maps `unsupported`/`reject_size_type`/`corrupt` to named errors.
- New named errors added to `errors.py` per §8 (upload/bundle scope only).
- `tests/test_bundle_out.py` green; full `uv run pytest -q` green (60 existing pass); zero new deps; no credential/profile reads; no chatgpt.com contact.
- Report with telemetry + `T2-STATUS:` last. You did NOT git commit.
