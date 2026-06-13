# M-008b · E3 (pi, single editor) — Real-site pytest harnesses: T3 truncation completeness + T5 falsifiable continuity

You are the SINGLE EDITOR. WRITE two `real_site`-marked pytest files. **DO NOT RUN THEM** (they send real prompts; the manager runs them with `ASK_CHATGPT_REAL=1`). You may only run OFFLINE checks: `--collect-only` and the default suite (which must keep deselecting them). Do NOT set `ASK_CHATGPT_REAL`. Do NOT touch `127.0.0.1:9222`. NEVER `git push`.

## Environment / safety (you inherit nothing)
- `uv sync --all-groups`; run via `uv run pytest`. Touch only `tests/` (two new files). Do NOT modify `src/`, the mock test, or `orchestration/` except your report.
- These are REAL-tier tests gated by the autouse `tests/conftest.py` (`real_site` marker + `ASK_CHATGPT_REAL=1`); without the env var they are SKIPPED/deselected. Confirm that, do not weaken it.

## Read FIRST (ground truth)
- `tests/test_continuity_mock.py` — REUSE its channel-agnostic builders/asserts by importing them (do NOT rewrite the assertions): `NONCE_PREFIX`, `RECALL_PROMPT`, `NONCE` pattern, `LONG_LINE_COUNT` (180), `LONG_SENTINEL` (`__ELICIT_COMPLETE__`), `_new_nonce`, `_plant_prompt`, `_truncation_elicitation_prompt`, `_assert_recall_prompt_does_not_leak_nonce`. Import via `from tests.test_continuity_mock import ...`.
- `src/ask_chatgpt/api.py` — `ask_chatgpt(prompt, *, session_identifier=None, channel="real", base_url=None, registry=None, timeout_s=..., cdp_endpoint=None, ...)`. Confirm the exact kwargs it accepts (session_identifier, channel, registry, timeout_s). Each call opens its own `BrowserSession` and `close()`s it (so each call re-runs `start()` → re-checks challenge/login — that is your cross-call safety).
- `src/ask_chatgpt/session_registry.py` — `SessionRegistry(store_path=...)` carries `session_identifier → conversation_ref` (used for continuity, and across processes via `ASK_CHATGPT_STATE_DIR`).
- `src/ask_chatgpt/driver.py` — `wait_for_completion(timeout_s=120, max_total_wait_s=None)` (the new T1 ceiling; default ceiling 600s is fine — do not override).
- `src/ask_chatgpt/cli.py` — confirm `--channel`, `--session`, `--prompt`, `--timeout` flags for the cross-process continuity subprocess (M-006/M-007 used `--channel cdp`).
- `src/ask_chatgpt/errors.py` — `ResponseTruncatedError`, `ChallengePresentError`, `LoginRequiredError`.

## Redaction (every artifact these tests write)
Redact any `/c/<id>` to `/c/<redacted>` (regex `r"/c/[^/?#\s]+"`). The nonce itself is fresh per-run test data (NOT a credential) and may appear in artifacts; conversation refs must NOT.

---

## File 1 — `tests/test_truncation_real.py` (T3, marked `@pytest.mark.real_site`)

Goal: prove `ask_chatgpt() -> text` returns the long response **COMPLETE** on the real site (the M-007 `…1F3845_` clip must not recur). FALSIFIABLE + HONEST three-way outcome — never conflate GPT non-compliance with client truncation.

`test_real_long_response_is_not_client_truncated`:
1. `token = f"ELICIT-{secrets.token_hex(12)}"`; `prompt = _truncation_elicitation_prompt(line_count=LONG_LINE_COUNT, token=token)`.
2. Up to **3 attempts** (human-paced: `time.sleep(5)` between attempts), each: `text = ask_chatgpt(prompt, channel="cdp", session_identifier=None, timeout_s=180)`. Write each raw response (redacted) to `orchestration/reports/M-008b/T3-real-response-<attempt>.txt`.
3. Classify each response with a helper `_classify_long_response(text, token)` returning `(verdict, max_k, has_sentinel, nbytes)`:
   - Compute `max_k` = the largest K such that lines `LINE-1 <token>` … `LINE-K <token>` ALL appear, in order and contiguous (a preamble before LINE-1 is allowed; scan the lines, find the LINE-1 anchor, count consecutive `LINE-<k> <token>` with k incrementing by 1). 
   - `has_sentinel` = `LONG_SENTINEL` appears as the last non-empty line at/after `LINE-180`.
   - `nbytes = len(text.encode("utf-8"))`.
   - verdict = **"COMPLETE"** if `max_k == LONG_LINE_COUNT and has_sentinel and nbytes >= 4096`; **"CLIP_SUSPECT"** if `1 <= max_k < LONG_LINE_COUNT` OR (`max_k>=1` and not `has_sentinel`) — i.e. the sequence started but did not finish (missing tail/sentinel) = the truncation failure mode; **"NONCOMPLIANT"** if `max_k == 0` (GPT never produced the format).
4. Outcome rules (HONEST):
   - If any attempt is **COMPLETE** → assert PASS (UC1 real truncation PROVEN). Record which attempt + max_k/nbytes.
   - Else if any attempt is **CLIP_SUSPECT** → **`pytest.fail`** with a message naming it a client/completion truncation candidate (max_k, nbytes, whether sentinel present) — THIS is the real defect signal (completion design wrong → manager iterates T2). Include the artifact path.
   - Else (all **NONCOMPLIANT**) → **`pytest.skip`** (or `pytest.xfail`) with reason `"INCONCLUSIVE: GPT did not emit the deterministic body in N attempts (non-compliance, not a proven client clip)"`. Do NOT pass; do NOT claim a clip.
5. Also write a JSON summary `orchestration/reports/M-008b/T3-real-summary.json`: list of `{attempt, verdict, max_k, has_sentinel, nbytes}` + final outcome. Redact.

Make the strict-form check available too: record `strict_exact_match = (text.splitlines() == expected_lines)` for the chosen attempt in the summary (informational; the PASS gate is the anti-clip COMPLETE property, which tolerates a GPT preamble).

---

## File 2 — `tests/test_continuity_real.py` (T5, marked `@pytest.mark.real_site`)

Goal: prove **falsifiable** semantic continuity on the real site (NOT the retracted circular M-007 test). Nonce planted turn-1 only; recall prompt has the nonce ABSENT; a FRESH-conversation control must FAIL to recall; plus a cross-process variant.

Use a persistent registry/state dir under `tmp_path` (NOT the production registry). Use `nonce in text` (contains) for recall and `nonce not in text` for control (the real GPT may add natural phrasing; the mock's exact-match is too strict for real prose — but `contains` is still falsifiable: a control conversation cannot contain a nonce it never saw).

`test_real_semantic_continuity_in_process(tmp_path)`:
1. `nonce = _new_nonce()`; `_assert_recall_prompt_does_not_leak_nonce(RECALL_PROMPT, nonce)` (guard: recall prompt must not contain nonce/prefix/suffix).
2. `registry = SessionRegistry(store_path=tmp_path/"sessions.json")`.
3. Plant: `ask_chatgpt(_plant_prompt(nonce), channel="cdp", session_identifier="m008b-cont-real", registry=registry, timeout_s=120)`. Do NOT assert hard on the turn-1 reply.
4. `time.sleep(5)` (human pace). Recall: `recalled = ask_chatgpt(RECALL_PROMPT, channel="cdp", session_identifier="m008b-cont-real", registry=registry, timeout_s=120)`. Assert `nonce in recalled`.
5. `time.sleep(5)`. CONTROL (fresh conversation, different session id, SAME prompt): `control = ask_chatgpt(RECALL_PROMPT, channel="cdp", session_identifier="m008b-cont-real-control", registry=registry, timeout_s=120)`. Assert `nonce not in control` (the falsifiability mechanism — proves the test CAN fail and recall is conversation-scoped).
6. Write redacted artifacts `orchestration/reports/M-008b/T5-recall.txt` (contains nonce — ok) and `T5-control.txt` (must not). Redact `/c/<id>`.

`test_real_semantic_continuity_cross_process(tmp_path)`:
1. `state_dir = tmp_path/"state"`; `nonce = _new_nonce()`.
2. Turn-1 plant via a SEPARATE CLI subprocess: `python -m ask_chatgpt.cli --channel cdp --session m008b-cont-xproc --prompt <plant> --timeout 120` with `env[ASK_CHATGPT_STATE_DIR]=state_dir`. Assert returncode 0.
3. `time.sleep(5)`. Turn-2 recall via ANOTHER subprocess (same state dir, same session): assert returncode 0 and `nonce in stdout`.
4. CONTROL subprocess (same state dir, DIFFERENT session `--session m008b-cont-xproc-control`, same recall prompt): assert `nonce not in stdout`.
5. Use a generous subprocess `timeout=` (e.g. 240). Redact `/c/<id>` from any captured output you write to artifacts. Do NOT print the registry's conversation_ref.

Both tests: each `ask_chatgpt`/CLI call re-runs `start()` (re-checks challenge/login) — if a challenge/logout occurs, the call raises `ChallengePresentError`/`LoginRequiredError` and the test ERRORS (acceptable; the manager handles HUMAN-ACTION-NEEDED). Do NOT catch-and-pass those.

---

## Verify (OFFLINE ONLY — do NOT run real tests)
- `uv run pytest --collect-only -q tests/test_truncation_real.py tests/test_continuity_real.py` → MUST collect 3 tests (1 truncation + 2 continuity), all under the `real_site` marker. Save output to your report.
- `uv run pytest -q` (NO `ASK_CHATGPT_REAL`) → MUST still be `207 passed, N deselected, 0 real_site executed` where N is now `1 (existing) + 3 (new) = 4` deselected. Save the summary line to `orchestration/reports/M-008b/E3-pytest-default.txt`. (If the count differs, reconcile — the new real_site tests must be DESELECTED, not passed/failed, by default.)
- Confirm imports from `tests.test_continuity_mock` resolve (no assertion rewrite).

## Report `orchestration/reports/M-008b/E3-worker-report.md`
STATUS; the two file paths; the helper imports reused; the collect-only output; the default-suite summary (confirm new real_site tests DESELECTED, 0 executed); confirmation you did NOT run the real tests / did NOT set ASK_CHATGPT_REAL / did NOT touch the network; commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:` lines.

Commit the slice. NEVER `git push`. Do NOT run the real tests.
