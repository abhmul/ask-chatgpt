# M-004 verification — 2026-06-12 independent non-producer verification of the full README.md directive

I read the directive, M-004 mission shape, the T1 authoritative evidence index, and all five T2 lens reports. All five lens files were present, non-empty, and emitted their verdict tokens; no dead candidates were discarded. Final adjudication is from ground truth, not lens majority.

## Per-obligation evidence table

| obligation | evidence (file:line / test id / artifact line) | verdict |
|---|---|---|
| UC1 exposes `ask_chatgpt(prompt, session_identifier, model_settings...) -> text`, returns latest assistant text, supports continuity and model selection where UI allows | `README.md:9`; `src/ask_chatgpt/api.py:30-47,55-74`; `tests/test_ask_chatgpt_uc1.py:19,74,105`; `tmp/verify-m004/accept_uc1_results.json:2,6,16-20,32-35`; `tmp/verify-m004/clone_accept_uc1.txt:15` | PASS |
| UC2 accepts files/dirs and builds a zip bundle with GPT catalogue README/instructions | `README.md:10-13`; `src/ask_chatgpt/api.py:41-43,107`; `src/ask_chatgpt/bundle.py:28,192-212,216-223,387-404,608-610`; `tests/test_bundle_out.py:55,77,119-122`; `tmp/verify-m004/clone_pytest.txt:4-5` | PASS |
| UC2 retrieves changed-files-only patch bundles via download-primary and fenced fallback, validates before mutation, applies locally, and round-trip diff matches | `src/ask_chatgpt/patch.py:186-255,258-276,618-626`; `tests/test_uc2_roundtrip.py:131,143`; `tmp/verify-m004/accept_uc2_results.json:2,54-62,114-120,184-192,244-250`; `tmp/verify-m004/clone_accept_uc2.txt:11` | PASS |
| UC3 provides installed `ask-chatgpt` CLI wrapping the function for prompt, stdout, `--out`, file args, dry-run/no-mutate, and apply guardrails | `README.md:14`; `pyproject.toml:11-12`; `src/ask_chatgpt/cli.py:54-87,100-114`; `tests/test_cli.py:161,191,226,254`; `tmp/verify-m004/accept_uc3_results.json:2,9-26,37-53,73-92,105,144`; `tmp/verify-m004/clone_accept_uc3.txt:13` | PASS |
| UC3 CLI session argument is exercised as part of the CLI acceptance shape | Code exists at `src/ask_chatgpt/cli.py:63,102`, but ground-truth search found no `--session` in `tests/`, `scripts/`, or `tmp/verify-m004/accept_uc3_results.json`; the three UC3 acceptance command arrays at `accept_uc3_results.json:9-20,40-53,73-92` omit it | FAIL |
| Each UC has automated E2E acceptance against local mock ChatGPT; automated tests never contact chatgpt.com/openai | `README.md:18`; `tmp/verify-m004/clone_pytest.txt:4-5`; `tmp/verify-m004/clone_accept_uc1.txt:5,15`; `tmp/verify-m004/clone_accept_uc2.txt:5,11`; `tmp/verify-m004/clone_accept_uc3.txt:5,13`; `tests/conftest.py:26-35,43-45`; `tmp/verify-m004/netguard.txt:3-4`; `tmp/verify-m004/grep_chatgptcom.txt:2,6-8` | PASS |
| Operator-gated real-site runbook half exists with explicit consent and mock-vs-real honesty | `README.md:18,25`; `docs/runbooks/real-site-acceptance.md:1,19-21,27`; `docs/runbooks/observe-chatgpt-unknowns.md:5,11` | PASS |
| Operator-gated real-site runbook is runnable as written against the actual CLI/error surface | Stale commands use `--profile`, `--patch-out`, `ask-chatgpt apply-patch`, and `--bundle` at `docs/runbooks/real-site-acceptance.md:150,166,171,180-188,224,241,263`; actual CLI exposes `--profile-path` at `src/ask_chatgpt/cli.py:113` and grep found no `apply-patch`, `--patch-out`, `--bundle`, or `--profile` flag in `src/ask_chatgpt/cli.py`; stale error names at `real-site-acceptance.md:132,213,290` diverge from `src/ask_chatgpt/errors.py:87,94,101,108` | FAIL |
| Honest failure modes are named actionably and credential-free | `README.md:20`; named errors in `src/ask_chatgpt/errors.py:16,24,32,40,48,55,63,71,87,94,101,108`; representative tests `tests/test_driver.py:80,89,98,107,119,130`, `tests/test_bundle_out.py:158`, `tests/test_patch.py:196,206,216,222`; `tmp/verify-m004/clone_pytest.txt:4-5` | PASS |
| D-001 channel layering and library-first posture are implemented | `README.md:24-27`; `docs/DECISIONS.md:13-16,35-37`; `src/ask_chatgpt/readers.py:87-98`; `src/ask_chatgpt/patch.py:208-231`; `src/ask_chatgpt/cli.py:54-87` | PASS |
| Real channel fail-closed posture prevents chatgpt.com navigation before selector enforcement when `real.json` is empty | `src/ask_chatgpt/selector_maps/real.json:6,28` is empty and `src/ask_chatgpt/selector_map.py:31-38` fails on use, but `load_selector_map` returns the empty map at `selector_map.py:69`; `src/ask_chatgpt/driver.py:75-90,270-276,289-291` launches a real persistent context and executes `page.goto(REAL_BASE_URL)` before any selector lookup when a `profile_path` is supplied; T1 grep shows no automated `channel="real"` coverage at `tmp/verify-m004/grep_realchannel.txt:1-7` | FAIL |
| Mission telemetry convention uses literal `ESTIMATE:`, `ACTUAL:`, and `REWORK-CAUSE:` lines in prior handoffs | `orchestration/handoffs/MISSION-002-handoff.json:8-9,71` and `MISSION-003-handoff.json:9-10,73-74` contain structured/prose fields, but exact-token grep for `ESTIMATE:`, `ACTUAL:`, and `REWORK-CAUSE:` over both handoffs had no matches | FAIL |

## Five lens verdicts

- spec-conformance → FAIL → UC3 `--session` acceptance coverage gap and real-site runbook CLI drift block full obligation mapping → `orchestration/reports/M-004/lens-spec.md:40`.
- correctness/reproduction → PASS → clean clone, full pytest, UC1/UC2/UC3 acceptance artifacts, and sampled non-vacuous tests are internally green → `orchestration/reports/M-004/lens-correctness.md:40`.
- safety/security → FAIL → real channel with `profile_path` can navigate to `https://chatgpt.com` before empty real selector map fails closed → `orchestration/reports/M-004/lens-safety.md:35`.
- honest-failure-modes → PASS → all 11 named failure modes exist, are exercised by T1-backed tests/artifacts, and have actionable credential-free messages → `orchestration/reports/M-004/lens-failures.md:25`.
- docs/runbooks/decisions/telemetry → FAIL → real-site acceptance runbook is stale against actual CLI/error names and prior handoffs lack literal telemetry lines → `orchestration/reports/M-004/lens-docs.md:32`.

## Mock-proven vs real-site-unproven scope

Automated proof is mock-only: the clean-clone `uv run pytest -q` plus `scripts/accept_uc1.sh`, `scripts/accept_uc2.sh`, and `scripts/accept_uc3.sh` passed against loopback `127.0.0.1` mock fixtures, proving the library, CLI, bundle/retrieval/apply, network guard, no-mutate default, and zip-slip defenses only for the local mock harness. The real `chatgpt.com` behavior is NOT automatically verified: real selectors, completion signals, DOM text extraction, copy fallback behavior, upload/download affordances, file size limits, session pinning, model selection, artifact-to-turn identity, and failure-message detectability remain unproven until the operator runs the operator-gated runbooks with explicit consent. Because `docs/runbooks/real-site-acceptance.md` is stale as written, M-005 must fix it before treating it as an executable proof path.

## Operator runbook pointers

- `docs/runbooks/observe-chatgpt-unknowns.md` — manual operator observation of real ChatGPT UI unknowns; it explicitly says no `ask-chatgpt`, Playwright, pytest, or automation is used for that observation run.
- `docs/runbooks/real-site-acceptance.md` — intended UC1/UC2/UC3 real-site acceptance after `real.json` is populated and typed consent is given; currently blocked by stale CLI/error-name commands and must be repaired before use as written.

## Three spot-check quotes from raw T1 artifacts

1. Clean-clone functional core: `tmp/verify-m004/clone_pytest.txt:4-5` quotes `119 passed in 43.60s` and `EXIT_CODE: 0`; this confirms T2b's green full-suite claim.
2. UC2 round-trip diff and retrieval channels: `tmp/verify-m004/accept_uc2_results.json:54-62,114-120,184-192,244-250` quotes `"source": "download"`, `"source": "fenced"`, `"modified_matches": true`, `"added_matches": true`, `"deleted_absent": true`, and `"overall_diff_matches": true`; this confirms the download-primary and fenced-fallback mock round trips.
3. Zip-slip rejection matrix: `tmp/verify-m004/zipslip.txt:24-28` quotes `VECTOR absolute_path | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`, `VECTOR dotdot_traversal | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`, `VECTOR symlink_final | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`, `VECTOR symlink_parent | EXCEPTION=PathEscapeError ... CANARY_EXISTS=False | ROOT_UNCHANGED=True`, and `EXIT_CODE: 0`; this confirms the four-vector no-escape claim.

## Defects requiring rework

1. Real-site acceptance runbook is stale relative to the committed CLI and error classes. REWORK-CAUSE: env-drift. Recommended M-005 fix mission: either update `docs/runbooks/real-site-acceptance.md` to the current one-shot CLI (`--profile-path`, `--files`/`--dirs`, `--out`, `--dry-run`/`--apply`, `--root`) and current error names (`PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`), or implement the documented `--profile`, `--patch-out`, `apply-patch --bundle` surface; then rerun the docs/spec lenses.
2. Real channel is not fail-closed before navigation when `channel="real"` and a `profile_path` are provided with empty `real.json`. REWORK-CAUSE: spec-gap. Recommended M-005 fix mission: add a pre-navigation real selector-map readiness validation that raises `SelectorUnavailableError` before `launch_persistent_context`/`page.goto`, and add a non-networking unit test proving no `chatgpt.com` navigation attempt occurs for the empty template.
3. UC3 `--session` is implemented but unproven by CLI tests or acceptance artifacts. REWORK-CAUSE: spec-gap. Recommended M-005 fix mission: add a CLI test and `scripts/accept_uc3.sh` step invoking `ask-chatgpt --session <id>` twice against the mock and proving the same conversation/ref and prompt history are reused through the public CLI.
4. Telemetry literal-line convention is absent from M-002/M-003 handoffs. REWORK-CAUSE: frozen-file. Recommended M-005 fix mission: backfill or formally supersede the handoff telemetry format so exact `ESTIMATE:`, `ACTUAL:`, and `REWORK-CAUSE:` lines are grep-visible, then add a lightweight check over handoffs.

## M-005 re-verification (2026-06-12) — independent non-producer panel

M-005 reconciles the historical M-004 FAIL defects above against the independent panel outputs and authoritative clean-clone artifacts. Ground truth did not contradict the panel: D1/D2/D3 are fixed and non-regressing; D4 is a minor process item resolved forward and is not a README product-directive blocker.

| defect | severity | fix commit | re-check evidence (file:line / artifact line) | verdict |
|---|---|---|---|---|
| D1 — real-site acceptance runbook stale vs actual CLI/error surface | major docs/runbook drift | `0179400` | `orchestration/reports/M-005/T4b.md:51` records no stale `--profile`/`--patch-out`/`--bundle`/`apply-patch` or stale patch error tokens; `orchestration/reports/M-005/T4b.md:61` says prerequisites match the real CLI surface; `orchestration/reports/M-005/T4b.md:63` records the D1 pass conclusion. | PASS |
| D2 — real channel could navigate before selector readiness failed closed | critical safety/spec gap | `2f0b8de` | `orchestration/reports/M-005/T4c.md:10` verifies readiness is checked before Playwright start and before `page.goto`; `orchestration/reports/M-005/T4a.md:18` quotes the targeted D2 artifact with test pass, ordering grep, and all-empty `real.json`; `orchestration/reports/M-005/T4c.md:18` records the D2 pass conclusion. | PASS |
| D3 — UC3 CLI `--session` continuity was implemented but not accepted/tested | major spec/acceptance gap | `261a16b` | `orchestration/reports/M-005/T4c.md:24` verifies the CLI test/acceptance drives two subprocesses with the same `--session` and exact user turns; `orchestration/reports/M-005/T4a.md:16-17` quotes UC3 `session-continuity` and overall pass artifacts; `orchestration/reports/M-005/T4c.md:26` records the D3 pass conclusion. | PASS |
| D4 — literal telemetry-line convention absent in frozen M-002/M-003 handoffs | minor process hygiene | n/a — resolved forward; historical handoffs intentionally not edited | `orchestration/tasks/M-005/T4d-synthesis.md:20-23` scopes D4 as fix-forward only, forbids claiming historical edits, and requires recording it as resolved forward; M-005 panel reports carry forward literal telemetry lines at `orchestration/reports/M-005/T4a.md:1-2`, `orchestration/reports/M-005/T4b.md:1-2`, and `orchestration/reports/M-005/T4c.md:1-2`; `orchestration/tasks/MISSION-005.md:18` keeps the manager handoff convention forward-only. | resolved forward (convention adopted in M-004/M-005 manager handoffs; historical handoffs frozen by decision) |

No-regression: the authoritative clean clone is HEAD `261a16b` and contains the D1/D2/D3 fix commits (`orchestration/reports/M-005/T4a.md:8`); the full suite is `121 passed` (`orchestration/reports/M-005/T4a.md:11`); UC1, UC2, and UC3 acceptance artifacts all report `overall=pass`, including UC3 `session-continuity` (`orchestration/reports/M-005/T4a.md:12`, `orchestration/reports/M-005/T4a.md:14`, `orchestration/reports/M-005/T4a.md:16-17`).

Independence: this re-verification uses a fresh non-producer panel, not T1-T3; T4a produced the authoritative evidence once, and T4b/T4c independently reasoned over those artifacts plus committed files without rerunning the heavy suite (`orchestration/reports/M-005/T4b.md:6,8`, `orchestration/reports/M-005/T4c.md:6`).

VERDICT: PASS

---

# M-006 (2026-06-12) — Real-site enablement (D-002): FINAL — real tier ENABLED + verified; UC1/UC3 real-PASS, UC2 real-PARTIAL (D-001)

Final mission verdict. The full best-of-N real-site verification ran — T4a/T4b/T4c independent non-producers, ALL PASS — over an authoritative `uv run pytest` (169 passed / 1 deselected / exit 0). Full detail + recommendation: `orchestration/reports/M-006/verify.md`. This SUPERSEDES the earlier interim "BLOCKED on operator sign-in" status: that "logged out" diagnosis was a Playwright-LAUNCH artifact (chatgpt.com Cloudflare-blocks launched browsers); the mission pivoted to operator-consented **CDP attach** (D-002 addendum) to the operator's own signed-in Chromium.

## Tier plumbing + CDP channel (T1, T1b, T2c–T2h) — mock-proven, T4a panel-verified
| item | evidence | verdict |
|---|---|---|
| `real_site` marker + default deselection + `ASK_CHATGPT_REAL=1` double-gate | `pyproject.toml`; `tests/conftest.py`; `tests/test_real_tier_gating.py`; clean run `1 deselected` | PASS |
| default-tier purity: autouse loopback socket guard intact; clean `uv run pytest` = 169 passed, ZERO real_site collected | `tests/conftest.py`; `tmp/verify-m006/T4-evidence.txt` | PASS |
| real-tier browser-level domain allowlist (abort+log off-domain; +`cdn.auth0.com` from discovery) | `src/ask_chatgpt/real_allowlist.py`; `tests/test_real_allowlist.py` | PASS |
| CDP attach channel (`channel="cdp"`, `connect_over_cdp`, brand-new tab, `close()`=detach-not-quit, login+challenge detection) | `src/ask_chatgpt/driver.py`; `tests/test_driver_cdp_attach.py` | PASS |
| public api/CLI `channel=cdp` + URL-derived `conversation_ref`; optional-marker tolerance; real readiness/send/completion/upload mechanics | `src/ask_chatgpt/{api,cli,driver,readers,patch,bundle}.py`; `orchestration/reports/M-006/T4a.md` | PASS |
| `real.json` populated (verified selectors only); fail-closed schema preserved (REQUIRED hard-fail; OPTIONAL degrade) | `src/ask_chatgpt/selector_maps/real.json`; `T4a.md` | PASS |

## Real-site acceptance (T2 discovery + T3 UC1–3 over CDP) — real-proven where stated
| item | evidence | verdict |
|---|---|---|
| T2 selector discovery over the operator's signed-in CDP browser (7/12 msgs; priority selectors stable; tab-hygiene clean; no leakage) | `orchestration/reports/M-006/discovery.md`, `real-selectors-proposed.json` | PASS (real) |
| UC1 — `ask_chatgpt()` real text + continuity (URL-derived ref) + model fail-closed probe | `orchestration/reports/M-006/T3.md` UC1 | PASS (real) |
| UC3 — `ask-chatgpt` CLI real text + `--session` continuity | `T3.md` UC3 | PASS (real) |
| UC2 — CLI bundle out → retrieve → apply | `T3.md` UC2 `DownloadUnsupportedError` (that turn); but `T3-uc2char.md` proved GPT emits a valid fenced bundle (matching SHA-256) + a unified diff | PARTIAL (real) — ACHIEVABLE; format-alignment follow-up |

## D-001 revisit (real) + findings
- DOM-primary text read: CONFIRMED real (UC1/UC3 via `.markdown`). KEEP.
- Download-primary bundle: NOT viable (no Playwright `Download` event). Fenced-base64-zip fallback: VIABLE — a post-T4 characterization (`orchestration/reports/M-006/T3-uc2char.md`, run after operator correction af09077 lifted the message cap) proved ChatGPT emits a valid fenced bundle (144-byte zip, matching SHA-256) AND a clean unified diff; UC2's T3 failure was prompt↔parser↔DOM format-alignment/elicitation, NOT a fundamental limit. UC2 is ACHIEVABLE: align `generate_prompt_instructions`↔`_parse_fenced_patch_bundle`↔real `.markdown` rendering, OR adopt the unified-diff text-native channel. KEEP D-001 DOM-primary text read.
- GAP-15: new-CDP-chat `conversation_ref` persists empty (sampled before the URL settles to `/c/<id>`); continuity proven via a tmp URL-derived repair; production fix = refresh the ref post-completion before registry `set()`.

## Conformance (T4b) — PASS
NO stealth/anti-detection anywhere (independent grep clean; plain `connect_over_cdp`, no UA/fingerprint spoofing); CDP attach to the operator's signed-in browser; login/logout never automated; Cloudflare/human-verification handled by a challenge-pause (never circumvented); budget 24/30 ledger lines (30 never exceeded; log-before-send conservatism — actual sends ≈11 < ledger); ZERO credential/account-identifier/token/raw-conversation-id leakage in committed artifacts; `tmp/` (may hold local registry refs) gitignored + uncommitted.

VERDICT: PARTIAL — real-site tier ENABLED + independently VERIFIED; **UC1 + UC3 real-PASS** (text + continuity, API and CLI); **UC2 real-PARTIAL but ACHIEVABLE** — a post-T4 characterization corrected the earlier "fenced not viable" hypothesis (ChatGPT DID emit a valid fenced base64-zip bundle with matching SHA-256, and a clean unified diff); UC2's gap is prompt↔parser↔DOM format-alignment, a tractable follow-up, NOT a fundamental limit or defect. tier-purity + CDP-safety + D-002-conformance (no stealth) + mock acceptance (169) all PASS. Recommended follow-ups: (1) bring UC2 to green via fenced-format alignment OR a unified-diff channel; (2) fix GAP-15 registry persistence. NOTE: the "≤30 budget" wording above is superseded by operator correction af09077 (no message cap; rule = human-paced + no programmatic spamming).

---

# M-007 (2026-06-13) — UC2 real-green (fenced-format alignment) + GAP-15 fixed: FINAL — PASS

Supersedes M-006's UC2 real-PARTIAL and the open GAP-15. Flow: best-of-N design (N=3 parser/safety/prompt lenses → synthesis `orchestration/reports/M-007/T0-design.md`) → single-editor RED-first impl (T1, T2) → real-site CDP acceptance (T3) → best-of-N verification (3 independent non-producer lenses — correctness, spec-conformance, safety/adversarial — ALL PASS) over an authoritative `uv run pytest` = **198 passed / 1 deselected / exit 0**. Full synthesis: `orchestration/reports/M-007/verify.md`.

## UC2 + GAP-15 (mock-proven + real-proven over CDP)
| item | evidence | verdict |
|---|---|---|
| UC2 mock round-trip — canonical fenced (manifest-less reconstruction) parse→validate→apply→diff-match | `tests/test_patch.py` (`test_bare_zip_real_m006_payload_roundtrips`, `…reconstructs_and_applies_modified_and_added`, `test_fenced_real_bare_format_roundtrips_via_reconstruction`), `tests/test_uc2_roundtrip.py`; `tmp/verify-m007/pytest-full.txt` | PASS |
| UC2 real round-trip over CDP — fenced bundle out→retrieve→apply→diff-match (modified-file) | `orchestration/reports/M-007/T3.md` `UC2_DIFF_OK`; `tmp/real-accept-m007-20260613T003803-0500/uc2/{response.txt,patch-bundle.zip,apply-summary.json}`; source `fenced`, 144-byte zip, matching SHA-256; `example.txt` red→blue, siblings unchanged | **PASS (real)** |
| GAP-15 — `conversation_ref` settled-`/c/<id>`-URL refresh post-completion before registry `set()`, fail-closed (no empty-ref persist), both text+bundle paths | `src/ask_chatgpt/driver.py:100` `refresh_active_conversation_ref`; `api.py:63,68,130,134`; `tests/test_api_cdp_public_path.py`, `tests/test_driver.py`; real `gap15-retry-3/summary-redacted.json` `same_ref:true` | **FIXED / PASS (real)** |

## Alignment + safety (panel-verified)
| item | evidence | verdict |
|---|---|---|
| Canonical fenced format aligned across prompt↔parser↔protocol-doc↔runbook (space-keyed, inline BASE64URL, embedded `manifest.json` OPTIONAL); fenced base64url is now the DOCUMENTED real bundle mechanism | `src/ask_chatgpt/bundle.py`, `patch.py`; `docs/bundle-protocol.md` §1/§4/§12; `docs/runbooks/real-site-acceptance.md` | PASS |
| Patch-apply validate-before-mutate PRESERVED under manifest-optional reconstruction (path-traversal/absolute/backslash/drive/symlink-entry+parent/encrypted/special/reserved rejected before any write, sourced from zip member names; integrity anchored on `sha256(decoded)==ZIP_SHA256`+byte-count; no `extractall`; dry-run writes nothing) | `src/ask_chatgpt/patch.py` (`_reconstruct_entries_from_zip`, `_validate_zip_info_basic`, apply transaction); `tests/test_patch.py` security suite | PASS |
| Real-drift END-marker prefix tolerance (`9b7fd30`) — accepts a clipped full-line sentinel only when the full marker is absent and exactly one such line follows BEGIN; integrity still enforced unconditionally → NO fail-open hole | `git show 9b7fd30`; drift + truncation tests; Lens C adversarial trace (6 cases) | PASS (safe) |
| Tier purity (default loopback-mock-only, ZERO real_site collected, `ASK_CHATGPT_REAL=1`+`real_site` double-gate); NO stealth (independent grep clean); CDP detach-not-quit + operator-tab/browser preservation; login never automated; challenge fail-closed; ZERO credential/identifier/`/c/<id>` leakage (redacted) | `pyproject.toml:20`; `tests/conftest.py`; `driver.py`; `tests/test_driver_cdp_attach.py`; `orchestration/reports/M-007/T4-evidence.md` | PASS |

## Honest scope + non-blocking follow-ups
- **Real UC2 scope:** proven real for the **modified-single-file** round-trip; **added/deleted/multi-file proven on the mock only** (reconstruction add+modify; manifest-bearing deletions). README UC2 obligation satisfied; not full real-matrix coverage.
- **END-marker drift root cause** uncharacterized (GPT vs a completion-timing read-race) — tolerance is safe (SHA-anchored) regardless; consider a completion-stability follow-up.
- Cosmetic `docs/bundle-protocol.md:100` vs `bundle.py:160` BASE64URL wording nit (same semantics).

Commits (no push): `5c26977` T1 · `90e4f86` T2 · `9b7fd30` T3 drift · `4a68100` T3 runbook.

VERDICT: PASS — [PARTIALLY RETRACTED 2026-06-13, see CORRECTION below] UC2 bundle round-trip GREEN on the real site over CDP (fenced base64url) and on the mock (198 passed / 1 deselected); GAP-15 conversation_ref persistence FIXED (settled-URL refresh, fail-closed). Tier-purity, no-stealth, CDP tab-hygiene, login-never-automated, no-leakage, and patch-apply validate-before-mutate (preserved under manifest-optional reconstruction) all independently PASS. Real coverage scoped to modified-file; added/deleted/multi-file proven on mock — non-blocking follow-up.

## CORRECTION (2026-06-13, operator review — test-validity defects)

The operator inspected the real chat transcript and found two real-site claims were not validly proven. The mock-tier results (198 passed), tier-purity, no-stealth, and patch-apply safety are unaffected. Retractions:

- **Semantic continuity NOT validly proven (was "GAP-15 FIXED / PASS (real)").** The recall prompt INCLUDED the answer: `"What exact nonce appeared in my previous message? Reply exactly: GAP15_RECALL N5C85C"`. GPT echoing `GAP15_RECALL N5C85C` proves nothing about recall — a zero-history conversation would reply identically. The test is circular. **What IS still proven:** structural same-conversation reuse — `same_ref: true` (the 2nd turn went to the same `/c/<id>` thread) and the registry settled-URL refresh code. **What is NOT:** that GPT actually uses prior-turn context. Redo required: seed a nonce in turn 1; in turn 2 ask for it with the nonce ABSENT from turn 2. The same flaw applies to the M-006 UC1 continuity check (same pattern).
- **Reader truncation observed, not flagged.** `gap15-retry-1/response1.txt` = `GAP15_SEEDED M007-GAP15-1F3845_` — the seeded nonce `…1F38453BF567` came back CLIPPED; the leg only "passed" after retrying with a short nonce. Completion/read may be clipping responses; needs a real truncation-detection test.
- **UC2 real round-trip — DOWNGRADE to "tiny-bundle only; not robust."** Content correctness holds (decoded `patch-bundle.zip` = `example.txt` → `favorite_color = "blue"`). But GPT returned a base64url TEXT blob in chat, not a file; combined with the truncation above, base64-in-chat will clip for real-size bundles (base64 ≈ +33%). Not proven sufficient beyond a trivial single-file edit; real file-download capture (or a chunking/integrity-resync strategy) is unresolved (M-006 found no Playwright Download event).

Net corrected status: mock half intact; real half = structural continuity + tiny-bundle UC2 content correctness proven; **semantic continuity and robust/real-size bundle return are UNPROVEN and need corrected tests.** Tracked for redo (see also `docs/BACKLOG.md`).

---

# M-008a INDEPENDENT GATE (2026-06-13, team-lead non-producer panel) — PASS, 2 concerns routed to M-008b

Operator waived manual prompt sign-off; the gate is adversarial verifiers + a team-lead spot check. The team lead ran an independent N=3 read-only panel (distinct from the producing manager's T5) over the committed code at head `5e230ee`, plus a personal spot-read of every rewritten GPT-facing prompt.

**Prompts (the core fix) — PASS.** The bundle prompt now asks for one actual downloadable `.zip` file with a download link and explicitly forbids inline/text representation; ZERO base64/marker wording in any GPT-facing string (grep-confirmed; guard test `tests/test_bundle_out.py:203`). Continuity is non-circular: the turn-2 recall prompt contains no nonce/prefix/suffix, the fresh-conversation CONTROL genuinely fails (mock recall is conversation-scoped), and a cross-process CLI variant proves registry-carried continuity. Truncation elicitation uses a terminal sentinel + exact-ordered-line check; the driver-level RED at `tests/test_driver.py:832` provably fails against the old logic (non-vacuous). Safety intact: the download path applies the full zip-slip + sha + caps gauntlet (source-agnostic, re-run at apply); base64 parser tolerance retained in `patch.py` but purged from model-facing text; tier double-gate empirically deselects+skips `real_site` by default; `real.json:download_artifact` still fail-closed; no credential/conversation-id leakage; no real-site contact.

**Completion hardening — SOUND, 2 concerns (→ M-008b):**
1. The fix replaced "text-stable OR completion-marker" with **completion-marker ONLY** (`not streaming_visible AND completion_visible`, driver.py:367). Eliminates the micro-pause clip with no fail-open, but makes correctness **wholly dependent on the real `completion_marker` (copy-turn-action button) reliably appearing at end-of-turn** — unverifiable offline. If that button is delayed/hover-gated/virtualized live, a complete turn flips from "clipped" to a false `ResponseTruncatedError` after the no-progress window. **M-008b must validate completion_marker reliability on the real site as the #1 risk before trusting the truncation fix; restore a hardened stability fallback if it is unreliable.**
2. The progress-aware timeout extends the deadline on every text change with **no absolute wall-clock ceiling** → a pathologically-oscillating body could wait unbounded. **M-008b: add an absolute ceiling (defense-in-depth) + remove the now-dead `_REAL_COMPLETION_STABLE_S` (driver.py:45).**

Non-blocking: the M-008a handoff mis-attributes the (pre-existing M-003/M-007) download-capture retrieve path to M-008a; that code is unchanged and safe — provenance note only.

GATE: **PASSED** — prompts independently verified; the completion concerns are real-site-validation items, appropriately M-008b's job. Proceeding to M-008b (real legs over CDP), no operator halt per the waiver.
