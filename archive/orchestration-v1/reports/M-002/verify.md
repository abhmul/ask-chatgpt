# MISSION-002 — Independent verification (best-of-N panel + synthesis)

**Synthesizer:** mission manager (headless claude -p, Opus 4.8) — a NON-PRODUCER reconciling three independent non-producer lenses + one re-verify. Per `agent-rigor.md`, verification is itself a best-of-N task: a diverse panel reasoning over ONE authoritative build/test output, synthesized into a single verdict.

**Structure:** one authoritative heavy run (V1) produced the canonical pytest + acceptance-artifact output; two read-only lenses (V2 D-001/safety/adversarial, V3 completeness/spec) reasoned over V1's output + source (NOT re-running the heavy suite concurrently — avoids shared-workspace contention); the panel found ONE gap; a remediation leg (T4c) closed it; a re-verify lens (RV) confirmed closure with no regression.

## Lens reports (each committed alongside this file)
- `verify-run.md` — V1 authoritative run. **V1-VERDICT: PASS.**
- `verify-d001-safety.md` — V2 D-001 + safety + adversarial. **V2-VERDICT: PASS.**
- `verify-completeness.md` — V3 deliverables + memo §6 + README. **V3-VERDICT: FAIL** (one gap; now resolved).
- `verify-reverify.md` — RV re-verify after T4c. **RV-VERDICT: PASS.**

## Consolidated per-check verdicts

### Build & reproduction (V1)
- CHECK build/sync — PASS: fresh `uv sync --all-groups` clean; reproducible (greenlet via PyPI in `uv.lock`, no `tmp/` refs).
- CHECK full suite — PASS: `uv run pytest -q` → `60 passed` (RV re-confirmed after remediation), zero failures/errors.
- CHECK acceptance + ARTIFACT INSPECTION — PASS: `scripts/accept_uc1.sh` exit 0; the produced `tmp/accept-uc1-*/results.json` inspected (not exit code alone): `overall: pass`; **continuity proven** — both same-`session_identifier` calls used conversation `conv-1` and that conversation holds BOTH user prompts; a `model_settings` call succeeded (`conv-2`, model `mock-default`); the honest-failure step raised `LoginRequiredError` with an actionable, credential-free message.
- CHECK network guard trips — PASS: `tests/test_network_guard.py` deliberate-violation test attempts a non-loopback connect to `93.184.216.34` and asserts the autouse socket guard raises `RuntimeError: NETWORK BLOCKED`; guard confirmed in `tests/conftest.py`.
- CHECK zero chatgpt.com contact — PASS: every `chatgpt.com`/`openai` hit in `tests/`/`scripts/` is a non-navigation literal (a constant assertion, a stored-URL string in a registry round-trip, or the deliberate-block target); no `page.goto`/HTTP to chatgpt.com; no `channel="real"`/`launch_persistent_context` in any test/script.

### D-001 conformance + safety + adversarial (V2 — all PASS, with file:line evidence)
- DOM-primary DEFAULT order (`readers.py` `DEFAULT_READER_ORDER = (DomReader(), CopyButtonReader())`), order configurable.
- One `ResponseReader` interface; both `DomReader` + `CopyButtonReader` behind it.
- Bounded latest-completed-turn ONLY, NO transcript/history sweep (reads `message_body` within the supplied turn locator; driver selects only the latest assistant locator).
- Fail-closed selectors: `selector_map.py` raises `SelectorUnavailableError` on absent/empty/whitespace; never cross-channel fallback; `real.json` all-empty → real channel fails closed until operator fills it from the runbook.
- Adversarial: booby-trap sentinel NEVER returned across {DomReader, CopyButtonReader} × {stable, virtualized} × {booby-trap older turn, `copy_mode=wrong`}; default composite resists a poisoned copy affordance (the empirical justification for D-001's DOM-primary override).
- Real channel BUILT but NEVER invoked by any test; `profile_path` opaque (never opened/read/listed/logged); no credential/cookie/token/profile reads anywhere.
- Loopback-only: autouse socket guard + mock server binds 127.0.0.1 ephemeral + driver asserts mock `base_url` is loopback.
- Fail-closed NOT masked: `read_response` falls through to the fallback ONLY on `SelectorUnavailableError`; other named errors (e.g. `ResponseTruncatedError`) propagate.

### Completeness vs deliverables + memo §6 + README (V3 → resolved)
- All MISSION-002 deliverables present (package + browser controller mock/real, selector-map loader, completion detector, ResponseReader+DomReader+CopyButtonReader, session registry, model_settings selection, named errors, public `ask_chatgpt()`; tests + complete mock fixture; network guard; `scripts/accept_uc1.sh`; `docs/runbooks/observe-chatgpt-unknowns.md`). The two mission-CLOSE artifacts (`verify.md`, the handoff) are produced at synthesis/close (this file + the handoff) — they were "absent" only by sequence, not accidental defects.
- memo §6 fixture affordances: ALL PRESENT (loopback+ephemeral+control endpoints; conversations by stable ref + reuse-vs-new; selector-map-compatible UI; adversarial booby-trap + latest-turn-only; copy button + clipboard with stable/wrong/missing/truncated; **+ permission-denied, added in T4c**; DOM stable + virtualized variants + completion/streaming/truncation markers; download artifact serving a real zip with Content-Disposition + all 8 variants; fenced base64url BEGIN/END+manifest+bytecount+SHA256 + 5 variants; upload `<input type=file>` + variants; all honest-failure states).
- Named error taxonomy complete (login/session-not-found/model-unavailable/response-truncated/selector-unavailable/upload-unsupported/download-unsupported + rate-limit), each actionable.
- Observation runbook covers all 10 memo §7 unknowns, operator-run/consent-gated/credential-safe, with an M-003-consumable results template.
- Intended (NOT defects): `real.json` all-empty (fail-closed template, operator-runbook-gated); bundle retrieval/apply CODE is M-003 scope (the fixture affordances exist now, as required).

### Gap found, remediated, re-verified
- **Gap (V3):** memo §6 "Copy channel" requires simulating **permission denial**; T4's copy modes (ok/missing/wrong/stale/truncated) omitted it. REWORK-CAUSE: spec-gap (manager contract omission).
- **Remediation (T4c):** `BrowserSession(grant_clipboard: bool = True)` — mock context grants clipboard perms only when True (default preserved; real channel unchanged); `CopyButtonReader` already maps a clipboard rejection (`PlaywrightError`) to the named `SelectorUnavailableError`; 4 tests now prove the denial path (named error, not raw; DOM-primary robust under denial; copy-first falls through; copy-only fails closed).
- **Re-verify (RV):** PASS — `60 passed`, zero failures; the permission-denied test + driver guard confirmed; safety boundary not regressed.

## Mock-proven vs real-site-unproven (honest scope)
- **MOCK-PROVEN (automated, loopback, this mission):** UC1 `ask_chatgpt()->text` end-to-end incl. session continuity, model selection, honest failures, DOM-primary + copy-fallback reading, adversarial booby-trap resistance, and the bundle/upload fixture affordances M-003 will consume.
- **REAL-SITE-UNPROVEN (operator-runbook-gated, NEVER automated):** every empirical unknown in `docs/runbooks/observe-chatgpt-unknowns.md` (memo §7) — real chatgpt.com selectors (`real.json` is an all-empty fail-closed template), real download/upload/clipboard/model-selection/session-pinning/completion behavior. The `channel="real"` code path is built but exercised ONLY by operator-consented runbook runs, never by tests.

VERDICT: PASS
T9-STATUS: DONE
