# MISSION-008a — Fix GPT-facing prompts + completion/truncation hardening (MOCK-proven). NO real site.

**Status:** DISPATCHED 2026-06-13. **Manager:** headless Opus `claude -p` under `claude-orchestrator-watch.sh`. **Editor:** pi (GPT-5.5 xhigh), single editor (editing legs serialize).

**ESTIMATE:** 150m (flag at 300m).

## Why this mission (operator root-cause, 2026-06-13)

The directive's mock half is solid (198 passed). Real-site claims were **PARTIALLY RETRACTED** — the cause was **prompt design**, not the site (see `VERIFICATION.md` CORRECTION; `orchestration/NEXT-SESSION-compacted.md`):
- The patch-bundle prompt told ChatGPT to emit a fenced **BASE64URL text** blob → GPT returned text → **no download affordance** ("downloads don't work" was CIRCULAR).
- The continuity recall prompt **contained the answer** → proved nothing.
- A seeded nonce came back **clipped** (`…1F3845_`) → completion/read may truncate `->text` (UC1 CORE).

**Two operator decisions fixed for this mission:**
1. **A-first:** do this prompt-fix + verification before any add-on/Deep-Research work.
2. **base64 = PARSER-ONLY.** The GPT-facing prompt asks **only** for a downloadable `.zip` — **NO base64 wording anywhere in the prompt**. The parser keeps base64 tolerance as a *silent* code-side fallback (for when GPT spontaneously emits base64), never as an instruction.

## HARD CONSTRAINTS (read before editing — you inherit nothing)

- **NO real-site contact in this mission.** Everything here is mock/loopback + unit. Real legs are M-008b, separately dispatched after operator prompt sign-off. Do not run `ASK_CHATGPT_REAL=1`; do not touch `127.0.0.1:9222`.
- Default tier stays loopback-mock-only; the autouse socket guard and tier double-gate must remain intact; `uv run pytest` must end `198+N passed, 1 deselected` (N = your new tests) with ZERO `real_site` collected.
- `uv sync --all-groups` (bare `uv sync` drops groups). `uv run` from repo root. Zero new deps. Never touch the shared agent venv.
- Single editor for shared-tree mutations. RED-first for every behavior change. Telemetry lines (`ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:`) + end timestamp in the handoff.
- Commit working slices only; **NEVER `git push`** (operator pushes). Base is clean tree @ `e254845`.
- **Adversarially review EVERY GPT-facing prompt you write** (memory: prompt-design-adversarial-review). For each: "How could a chatbot misread this? What outcome does the wording predetermine? Want a file → ask for a file. Test recall → never include the thing being recalled."
- Real selector maps stay fail-closed: `real.json:download_artifact` stays EMPTY (its real value is M-008b discovery). Do NOT invent real selectors.

## Read first
`orchestration/NEXT-SESSION-compacted.md`; `VERIFICATION.md` (CORRECTION); `docs/DECISIONS.md` (D-001 channels, D-002 real-site); `docs/bundle-protocol.md`; this file; the charter (your `--append-system-prompt-file`).

---

## T1 — Completion/truncation hardening (UC1 CORE; highest priority)

**Surface (read these):** `src/ask_chatgpt/driver.py:325 wait_for_completion` — the **real/cdp branch** at lines ~352–365 returns when `not streaming_visible and (completion_visible or text_stable)`, where `text_stable` = body text unchanged for `_REAL_COMPLETION_STABLE_S` (driver.py:45 = **2.0s**; poll `_POLL_INTERVAL_S` driver.py:44 = 0.1s; default `timeout_s=10.0`). `src/ask_chatgpt/readers.py:93 read_response` / `DomReader` reads `inner_text` of `message_body`. Real `truncation_marker` is empty. `tests/test_driver_cdp_attach.py` exists as cdp-path scaffolding.

**Root-cause hypothesis (verify, don't assume):** a streaming **micro-pause** — the stop button (`streaming_marker`, real = `button[data-testid="stop-button"]`) momentarily absent AND body text momentarily unchanged for ≥2.0s **mid-stream** — satisfies `text_stable` and returns a half-rendered turn → clipped text read. The 10s default `timeout_s` is likely also too short for long real responses (separate angle).

**Do:**
1. **RED:** Build a deterministic reproduction (no real site) in which the cdp/real completion path observes: streaming starts → grows text → a micro-pause (stop-button absent + text unchanged > 2.0s) → resumes → finishes a **long** body (≥ ~4 KB / ≥150 lines) with a terminal sentinel. Drive `wait_for_completion(channel="cdp"|"real")` against a controllable loopback page (extend the cdp scaffolding / serve a scripted HTML over loopback — your choice; must be deterministic and offline). Assert the **current** code returns **clipped** text (test fails). If you cannot reproduce a clip, say so explicitly and pivot to the timeout angle — do not fabricate a green.
2. **GREEN:** Harden completion so a micro-pause is **not** misread as done. Requirement (you choose the mechanism, justify it): completion must require *evidence the turn actually finished*, not merely "text briefly stable." Options: require that the streaming marker was **seen and then sustainedly absent**; require N consecutive stable polls AND no streaming marker; gate on an optional completion affordance selector (a turn-action toolbar appears only when done) read from the selector map when present; and/or lengthen the stability window. Keep **fail-closed** (timeout → `ResponseTruncatedError`). Make the long-response timeout adequate/derived, not a fixed 10s that clips legitimate long outputs. Structure the code so M-008b can wire a real completion-affordance selector without a redesign (e.g., honor an OPTIONAL `completion_affordance`/turn-action selector if present in the map; absent → degrade to the hardened stability logic).
3. **Completeness test:** assert a long deterministic body returns **complete** (terminal sentinel present, no internal gaps).
4. Do **not** regress the mock-channel completion path or any of the 198 existing tests.

**Acceptance:** new RED→GREEN truncation/completeness tests; existing suite green; no real selectors invented; mechanism justified in the handoff.

## T2 — Bundle prompt rewrite → downloadable `.zip` (base64 parser-only) + download retrieve path + mock fixture

**Surface:** `src/ask_chatgpt/bundle.py:185 _PROMPT_INSTRUCTIONS_TEMPLATE` (the GPT-facing prompt; currently base64-centric — REWRITE), `bundle.py:288 generate_prompt_instructions`; the catalogue README template (`_CATALOGUE_TEMPLATE` / `generate_catalogue_readme` bundle.py:263); `docs/bundle-protocol.md`; the retrieve/parse path in `src/ask_chatgpt/patch.py` (fenced base64url parser — KEEP as silent fallback; add a download path); the loopback mock-ChatGPT fixture (locate via `tests/conftest.py`); mock context already sets `accept_downloads=True` (driver.py:386).

**Do:**
1. **Rewrite `_PROMPT_INSTRUCTIONS_TEMPLATE`** so it instructs ChatGPT to return the changed/added files as **one actual downloadable `.zip` file** (it can create a file with its tools and provide a download link), preserving the existing payload rules: changed/added files only, repo-root-relative forward-slash paths, no whole tree, no unchanged files, no `ASK_CHATGPT_BUNDLE_README.md`, no absolute/`..`/backslash/drive/symlink/outside-root; deletions via a top-level `manifest.json` with `status:"deleted"` entries; `manifest.json` OPTIONAL for add/modify (per D-001 — tool reconstructs from verified zip entries). Keep the `NO_CHANGES_NEEDED` sentinel. Caps: zip < 25 MiB, each file < 5 MiB, ≤ 1000 files. **Remove ALL base64/BEGIN_PATCH_BUNDLE/marker-block wording from this prompt.** Adversarially review the result (attach the review to T4).
2. **Update `docs/bundle-protocol.md` + the catalogue README** so the **documented primary** return mechanism is a downloadable `.zip` file; base64-in-chat is described **only** in the protocol doc as a tolerated parser fallback, never surfaced to the model.
3. **Add a download-capture retrieve path:** detect the assistant turn's download-link affordance (selector key `download_artifact`, OPTIONAL/fail-closed — empty on real until M-008b), click it, capture the Playwright `Download`, read the zip bytes. **Integrity on the download path** = structural zip validity + the existing per-member path-safety (zip-slip matrix) + caps (no GPT-declared SHA on this path, since the bytes are authentic). The base64 fenced path keeps its declared-`ZIP_SHA256` check unchanged.
4. **Mock fixture:** add a download-affordance variant to the loopback mock so the assistant turn exposes a real download link to a `.zip`; add a mock UC2 round-trip test that retrieves via the **download** path (Playwright download event fires) → validate → apply → diff-match. Keep the existing base64-fenced mock round-trip test green (fallback still works).
5. Preserve validate-before-mutate, the zip-slip rejection matrix, and dry-run-default.

**Acceptance:** rewritten prompt has zero base64 wording; mock UC2 round-trip green via BOTH download (new) and base64 fenced (fallback); protocol doc + catalogue README aligned; zip-slip matrix still rejects all vectors.

## T3 — Falsifiable continuity test harness (mock-proven now; real assertions deferred to M-008b)

**Do (design the prompts and the harness; prove falsifiability on the mock):**
1. **Turn 1** plants a full-length high-entropy nonce ("Remember this token for later: `<NONCE>`. Reply `ACK` only." — exact wording is yours, adversarially reviewed). The nonce appears in turn 1 ONLY.
2. **Turn 2** (same `session_identifier`, **nonce ABSENT from the turn-2 text**) asks GPT to recall it ("What was the token I asked you to remember? Reply with only the token."). Assert the response contains the **exact** nonce.
3. **CONTROL (falsifiability):** the identical turn-2 question against a **FRESH** conversation (no turn 1) MUST FAIL to produce the nonce. The harness must demonstrate the test *can* fail.
4. **CROSS-PROCESS variant:** turn-1 via one CLI invocation, turn-2 via a **separate** process, proving the JSON session registry carries continuity across invocations.
5. Prove all of this on the **mock** (the mock fixture must model "same-conversation remembers across turns" vs "fresh conversation does not" so the control genuinely fails). Real execution is M-008b — structure the tests so M-008b flips them to the real channel without rewrite.

**Acceptance:** continuity + control + cross-process tests green on mock; the control proves the test can fail; nonces are full-length; no recall answer leaks into the asking prompt.

## T4 — Emit `orchestration/reports/M-008a/PROMPTS-FOR-REVIEW.md` (adversarial-verification + spot-check deliverable — HARD)

A single doc consumed by the adversarial prompt-quality lens (T5 Lens B) and the team lead's pre-real spot check. (Operator WAIVED manual sign-off 2026-06-13: adversarial verifiers + a quick team-lead spot check are the gate, not operator approval.) Include, verbatim, every GPT-facing prompt this mission produces — the rewritten bundle prompt, the continuity turn-1/turn-2/control prompts, the truncation-elicitation prompt — each with an **adversarial annotation**: how could GPT misread it, what outcome it predetermines, and why the corresponding test *can fail*. This deliverable must exist even if T5's verdict is PARTIAL.

## T5 — Best-of-N verification (N=3 independent non-producer lenses) over ONE authoritative `uv run pytest`

Run distinct lenses, synthesize, emit a VERDICT. **The manager lacks the Agent/Task tool** (launcher omits it by design) — run these lenses via **pi workers** (`pi-worker-watch.sh`, disjoint single-problem contracts) and/or the manager's own ground-truth analysis; do NOT attempt `claude` subagents. (The team lead will run an ADDITIONAL independent best-of-N panel as parallel `Plan` subagents over your authoritative run before operator sign-off — your T5 is the producer-side gate, theirs is the non-producer gate.) MANDATORY lenses:
- **Lens A — correctness/reproduction:** authoritative `uv run pytest -q` green (198+N passed, 1 deselected, 0 real_site); new tests are non-vacuous; the truncation test genuinely fails pre-fix (show the RED).
- **Lens B — prompt-quality + falsifiability (MANDATORY, operator-required):** adversarially read EVERY GPT-facing prompt — can it be misread? does it predetermine an outcome? Confirm zero base64 wording in the bundle prompt; confirm the continuity recall prompt does NOT contain the nonce; confirm each real-site test (continuity, truncation) *can fail* (control/sentinel present). A green suite is NOT sufficient — this lens inspects wording and falsifiability.
- **Lens C — safety/parser-integrity:** download-path integrity (structural + zip-slip + caps); base64 parser tolerance intact but absent from GPT-facing text; validate-before-mutate preserved; tier purity + socket guard intact; no real-site contact; no credential/identifier leakage in artifacts.

## Deliverables & handoff
- Code: T1 completion hardening + tests; T2 rewritten prompt + download path + mock fixture + protocol/README alignment; T3 continuity harness.
- `orchestration/reports/M-008a/PROMPTS-FOR-REVIEW.md` (T4) and `orchestration/reports/M-008a/verify.md` (T5 synthesis + VERDICT).
- `orchestration/handoffs/MISSION-008a-handoff.json` — STATUS DONE (or PARTIAL/BLOCKED with exact resume state), telemetry lines, commit shas (no push), and an explicit `GATE: AWAITING-TEAM-LEAD-ADVERSARIAL-VERIFY+SPOTCHECK` (operator WAIVED manual sign-off 2026-06-13 — the gate is adversarial verifiers + a team-lead spot check; on pass the team lead dispatches M-008b real legs with no operator halt).
- **STOP at the gate.** This mission (the build/mock half) ends with prompts adversarially vetted and the mock half green; it does NOT do real-site work itself. The team lead spot-checks, then dispatches M-008b (real legs).
