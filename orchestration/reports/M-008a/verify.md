# M-008a — T5 best-of-N verification synthesis + VERDICT

**Scope:** the MOCK/BUILD half of the prompt-fix mission. NO real-site contact occurred. Real assertions (continuity, truncation, UC2 download) are deferred to M-008b. This is the **producer-side gate**; the team lead runs an additional independent best-of-N panel (the non-producer gate) before M-008b.

## Methodology
Best-of-N over **one authoritative** `uv run pytest` (`orchestration/reports/M-008a/authoritative-pytest.txt`: `206 passed, 1 deselected in 67.92s`, `ASK_CHATGPT_REAL=<unset>`, head `05d67e8`). Three distinct non-producer lenses were run as **independent read-only pi workers** (disjoint single-problem contracts, reasoning over the one authoritative run — none re-ran the heavy suite), and corroborated by the **manager's own ground-truth analysis** (the manager did not produce the code/prompts — pi did). The manager lacks the Agent/Task tool by design; no claude subagents were used.

## Authoritative result
- `206 passed, 1 deselected` = prior baseline `198` + `8` new mission tests. The `1 deselected` is the single `real_site` sample (`tests/test_real_tier_gating.py`), deselected by `pyproject.toml` `-m "not real_site"`; **ZERO `real_site` tests collected/executed** (`ASK_CHATGPT_REAL` unset).

## Lens verdicts (each substantiated by file:line evidence in its report)
| Lens | Dimension | Verdict | Report |
|---|---|---|---|
| A | correctness / reproduction | **PASS** | `orchestration/reports/M-008a/T5-lensA.md` |
| B | prompt-quality + falsifiability (MANDATORY) | **PASS** | `orchestration/reports/M-008a/T5-lensB.md` |
| C | safety / parser-integrity / tier-purity | **PASS** | `orchestration/reports/M-008a/T5-lensC.md` |

- **Lens A:** authoritative suite green with real tier unset; new tests non-vacuous (cited ranges); T1 RED genuine (pre-fix `wait_for_completion` returned a clipped 5359-char body missing the terminal sentinel, `T1-worker-report.md:29-31`); the fix removed the `text_stable`-alone return (`driver.py:367-368` now requires `not streaming_visible and completion_visible`).
- **Lens B (operator-mandated):** re-ran `grep -niE 'base64|begin_patch_bundle|end_patch_bundle|fenced|marker block|5-line block' src/ask_chatgpt/bundle.py` → **empty**; the recall/control prompt contains no nonce/prefix/suffix and the test asserts it; the continuity CONTROL is byte-identical and conversation-scoped so it genuinely fails (`NO_TOKEN_RECALLED`); same-session recall asserts the EXACT nonce; the truncation verifier requires every ordered line + terminal sentinel + length ≥ 4096. Per-prompt adversarial reads found no circular/escape-hatch wording.
- **Lens C:** `patch.py` unchanged this mission (`git diff --exit-code` empty); fenced base64url parser intact as the silent fallback; download path is validate-first (no `extractall`/`extract`); zip-slip / path-escape / validate-before-mutate / dry-run-default coverage present and in the passing run; `real.json` fail-closed (`download_artifact: ""`, no `completion_affordance` value invented); optional `completion_affordance` seam honors-if-present/degrades-if-absent; mock completion semantics unchanged (only the `real`/`cdp` branch changed); autouse loopback socket guard + `real_site` double-gate intact; **no credential/cookie/token/profile/`/c/<id>` leakage and no real nonce in any M-008a artifact** (synthetic `ASKCG-NONCE-…` only).

## Mission acceptance — mapped to evidence
| Mission obligation | Evidence | Status |
|---|---|---|
| T1: RED→GREEN truncation/completeness; suite green; no real selectors; mechanism justified | `tests/test_driver.py` (6 real/cdp cases); `T1-worker-report.md` (RED + mechanism); `driver.py` fix | MET |
| T2: rewritten prompt has zero base64 wording; mock UC2 green via BOTH download + fenced; protocol/catalogue aligned; zip-slip intact | `grep` empty in `bundle.py`; `test_uc2_roundtrip.py` download+fenced; `docs/bundle-protocol.md`; `tests/test_patch.py` zip-slip | MET |
| T3: continuity + control + cross-process green on mock; control proves the test can fail; nonces full-length; no recall leak | `tests/test_continuity_mock.py` (3 functions); mock recall mode (`server.py`) | MET |
| T4: PROMPTS-FOR-REVIEW.md with every GPT-facing prompt verbatim + adversarial annotation | `orchestration/reports/M-008a/PROMPTS-FOR-REVIEW.md` | MET |
| T5: 3 distinct non-producer lenses over one authoritative run, synthesized | this doc + 3 lens reports | MET |
| Tier purity: `198+N passed, 1 deselected`, ZERO real_site; socket guard + double-gate intact | authoritative artifact; Lens C | MET |

## Honest scope & non-blocking notes (carry to M-008b)
1. **Mock-only.** Continuity, truncation, and the download-return prompt are proven on the loopback mock; real behavior is M-008b. Harness helpers are channel-agnostic so M-008b flips `channel="cdp"` without rewriting assertions.
2. **Bundle prompt presumes a file-tool-capable surface.** If the real ChatGPT surface cannot create a downloadable file, the honest outcome is `DownloadUnsupportedError` (the parser's base64 tolerance is a silent safety net, not an invited fallback). M-008b must run on a file-capable surface and discover/populate the real `download_artifact` selector.
3. **`wait_for_completion` default timeout changed 10s → 120s and is now progress-aware** (deadline extends while body text grows). Production callers pass their own `timeout_s`; the 120s default is a safety floor for direct callers. M-008b may consider a hard ceiling for pathological never-completing streams (the progress-aware extension otherwise waits while text grows). Non-defect; flagged for awareness.

## VERDICT
**PASS (mock/build half).** All three independent lenses PASS over one authoritative green run (`206 passed, 1 deselected`, zero real_site), corroborated by the manager's ground-truth analysis. The operator's two root-cause defects are fixed and proven falsifiable on the mock: (1) the bundle prompt asks for a downloadable `.zip` with **zero base64 wording** (base64 retained parser-only); (2) the continuity test is **non-circular** (nonce planted turn-1-only, absent from the recall prompt) with a **genuinely-failing control**. Tier purity, no-stealth posture, fail-closed real selectors, parser integrity, and patch-apply safety are intact. **No real-site work was performed.**

`GATE: AWAITING-TEAM-LEAD-ADVERSARIAL-VERIFY+SPOTCHECK` — on pass, the team lead dispatches M-008b (real legs over CDP).
