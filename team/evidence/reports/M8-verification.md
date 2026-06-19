# M8 — Independent terminal verification of the ask-chatgpt v2 rewrite (2026-06-19)

**Manager:** detached Claude Opus (M8, terminal mission). **Branch:** `rewrite-v2` @ `5fac7d0`. **Method:** one authoritative `uv run pytest` produced once, then a best-of-N panel of five distinct read-only lenses (pi `gpt-5.5 xhigh` workers) reasoning over that output + the committed M1–M7b evidence; the manager then **re-derived every contested/blocking claim from ground truth** rather than averaging verdict tokens. No real-site leg was run (offline-preferred per contract; the optional no-send leg was declined — see §7).

This report is the evidence behind the re-issued root `VERIFICATION.md`. It supersedes the v1 verification (M-004…M-010), which verified the archived v1 library and is stale for v2.

## 1. Authoritative test output
`team/evidence/reports/M8-pytest.txt`: **254 passed in 1.01s, exit 0** (`uv run pytest -v`; mock suite — `real_site` deselected by `addopts -m "not real_site"` and double-gated on `ASK_CHATGPT_REAL=1`; default runs never touch chatgpt.com). 0 real_site collected.

## 2. Panel composition + raw verdicts (then adjudication)
| lens | dimension | raw verdict | manager adjudication |
|---|---|---|---|
| L1 | correctness + spec-conformance | FAIL | **CONCERNS** — most "blocking" items are intentional designs or false alarms; one genuine functional gap (upload stub) + several non-blocking partials. |
| L2 | falsifiability (mutation/revert) | PASS | **PASS** — confirmed; 9/9 source mutations went RED, 0 vacuous, tree restored byte-for-byte. |
| L3 | gotcha-fix coverage | PASS | **PASS** — confirmed; all 4 gotchas fixed + pinned by non-vacuous tests. |
| L4 | safety / leak / isolation | FAIL | **PASS (with one hygiene note)** — no credential/content/account-id leak; the FAIL was committed *test-conversation IDs*, over-scored for missing context (see §5). |
| L5 | real-vs-mock honesty | CONCERNS | **CONCERNS (honest)** — evidence is honest; risk is scope *wording*. Matrix adopted into §6. |

Reports: `team/evidence/reports/M8-panel/L{1..5}-*.md`. Contracts: `team/contracts/M8-panel/L{1..5}-*.md`.

## 3. Falsifiability (L2) — the suite CAN fail
9 distinct **source** mutations (not test edits), each restored via cp-backup with sha-match:

| protected behavior | test | mutation → result |
|---|---|---|
| math fidelity (render) | `test_store_render.py::…literal_math…` | `store.py:290` rewrote `\widehat`→`\hat` → RED |
| math fidelity (capture) | `test_capture.py::…preserves_parts_math` | `capture.py:732` rendered-glyph for `\ne` → RED |
| verified send | `test_send_completion.py::test_no_op_submit_verification_raises_prompt_not_submitted` | `send.py:180` accept unconditionally → DID NOT RAISE → RED |
| no hidden ceiling | `test_send_completion.py::test_continuous_progress_past_600_without_total_cap_completes` | `completion.py:151` fire at 600s → RED |
| partial salvage honesty | `test_store_partial.py::…honest_partial_salvage…` | `store.py:324` force `status="error"` → RED |
| `--out` mirrors stdout | `test_store_payload.py::…stdout_and_out_…identical…` | `store.py:378` suppress stdout → RED |
| last-writer-wins | `test_store_read_semantics.py::…last_writer_wins…` | `store.py:272` `setdefault` → RED |
| auth/oai never persisted | `test_store_atomic_raw.py::…never_persists_auth_oai_keys` | `store.py:589` drop `oai-` clause → RED |
| menu fail-closed | `test_menus.py::test_select_model_absent_label_fails_…` | `menus.py:206` accept wrong label → RED |

**0 vacuous/green-by-triviality tests.** Independent confirmation of the operator-core discipline *tests must be falsifiable*.

## 4. The 4 rewrite gotchas (L3) — all FIXED + PINNED
1. **Rendered-DOM math corruption** → FIXED. Reads go through the page's own authenticated backend endpoint (`capture.py:140,171,178`); records are `backend_api`/`canonical` from `content.parts`; UI fallback (clipboard→KaTeX→DOM) is permission-gated, marked `partial`/`lossy_dom_text`, and fails closed. Render preserves literal markdown (`store.py:281–290`). Pinned by `test_store_render`/`test_capture` (and L2-falsifiable).
2. **Silent no-op send** → FIXED. Baseline latest user-turn read before fill/click; verification requires a **newer** user turn AND exact normalized prompt, else `PromptNotSubmittedError` (`send.py:158–196`, `errors.py:170`). Pinned by `test_send_completion` no-op/wrong-turn tests (L2-falsifiable).
3. **Truncation / hidden completion ceiling** → FIXED. `wait_for_completion` treats the timeout as a **no-progress** window (resets on activity); `max_total_wait_s` is opt-in (`None` by default); partials salvaged with honest `status`/`partial` (`completion.py:127–206`, `store.py:292–324`). Adversarial check: no `600`/`_CEILING` hard cap in `completion.py`; the only `600.0` is `activity_timeout_s`. Pinned by past-600 + explicit-cap + salvage tests (L2-falsifiable).
4. **`--out` suppresses stdout** → FIXED. `emit_payload` writes stdout **then** `--out`, identical bytes incl. NUL; `ask`/`scrape`/`history`/`export` route through it (`store.py:371–490`, `cli.py`). Pinned by `test_store_payload` (L2-falsifiable). *Operational caveat (documented):* the mirror is deliberate — agent runs must redirect stdout so response content does not land in logs.

No GPT-facing prompt re-introduces a gotcha: capture has **no** model-facing prompt; the only send-side model input is the operator's normalized prompt; grep found no base64/marker/self-answering directive.

## 5. Safety / leak / isolation (L4, adjudicated) — PASS, one hygiene note
- **No credential / cookie / Authorization / OAI-header / account-identifier / conversation-content leak.** Header names are constants only; `HeaderBundle` suppresses repr; CDP drops sensitive response headers; raw persistence drops sensitive keys (`capture.py:39–76`, `channels/cdp.py:339–346,433–437`, `store.py:554–589`), pinned by `test_store_atomic_raw…never_persists_auth_oai_keys` (L2-falsifiable). No real account email/org/user-UUID found.
- **Committed test-conversation IDs (hygiene, NON-BLOCKING).** Ground-truth scan found **6 distinct UUID-shaped tokens** in committed *evidence/docs/scripts* (none in `src/` or `tests/`): the operator-sanctioned **read-only target** (protected, "not touched"); the operator-approved **smoke** conversation (M5); a **fresh throwaway** chat + its message ids created for the M7b PONG smoke; and a message id in an issue repro. These are conversation/message identifiers of *test* conversations — not credentials, not content. They pre-date M8 and passed the prior dedicated leak gates (M7b-T4-L1, M-009, M-010), whose bar is *no credentials / no account identifier / no content*. L4's raw FAIL applied a stricter "`/c/<uuid>` committed = fail" rule without that context. **Adjudication:** not a sensitive leak; a low-sensitivity exposure relevant only to the operator's pre-**public-push** hygiene decision (the operator owns push). Locations enumerated (values withheld) in `team/evidence/reports/M8-panel/L4-safety-leak-isolation.md`. The M8 deliverables themselves are id-free (leak-scanned pre-commit).
- **No stealth/anti-detection** anywhere in `src/` (plain `connect_over_cdp`). **Domain allowlist** fail-closed (`allowlist.py`, `test_allowlist.py`). **Error taxonomy** credential-free incl. `PromptNotSubmittedError`. **Atomic writes** (temp+fsync+`os.replace`). **CDP isolation**: attach-only (not launch), own tool-opened tabs only, lease-validated; `detach()`'s `browser.close()` is the connect-over-cdp **client disconnect** (detach-not-quit), established real-proven across M-006/M-008b ("browser alive after every run"). Minor hardening nit: `attach()` does not force a preflight curl (fails closed if CDP down anyway).
- **Branch/tool isolation: PASS.** `git rev-parse stable` = `779eb40b196e1a458a820248b2dbbca22411b0d3` (**unmoved**). No `origin/rewrite-v2` (nothing pushed). No `uv tool install/upgrade/reinstall` in v2 dev. Cache (`cache/`, `.pi-workers/`, `tmp/`, `.venv`…) gitignored + untracked.

## 6. Real-vs-mock-vs-untested-live matrix (from L5, manager-checked)
**REAL-site-PROVEN (attended CDP, committed M2/M5/M6/M7/M7b evidence, DOM/backend-state — non-circular):**
- Backend-api scrape of existing conversations **with harvested web-app Authorization/OAI headers** → canonical markdown (cookies-only/accept-only **live-REFUTED**, 404). Math/format fidelity on a long real target (content-free token/shape/count checks).
- Verified send over CDP: ~3 real submissions across M7/M7b; **one** M7b fresh-chat send end-to-end backend-captured (gotcha-4 newer-turn proven there).
- Model selection: **one composer tier** (`Pro Extended`→`High`, sustained + restored; DOM-label, not model self-report).
- Tools selection: **one tool** (`Web search`) verified via re-opened Radix menu reflection, **0 sends**.
- Fresh-chat capture-auth reload (M7b gap-2) for one fresh throwaway chat.
- Incoming attachment refs for the target shapes; own-tab attach/detach hygiene; detach-not-quit.

**MOCK-ONLY / UNTESTED-LIVE (documented v2 boundary):** outgoing **upload** on send (also a code stub — §below); **loop** multi-turn; **concurrency / TabPool LRU-evict / AdaptiveSendBudget AIMD-backoff/hard-pause**; **Projects** scrape/send-into/create-within; **GPT-5.5 base-family submenu** selection (only a tier was live); **Deep Research** tool selection (only Web search was live); newly-generated **long-real-turn** completion / real timeout & partial salvage; **code_execution_output attachments** (real-probed → **unsupported**, fails closed).

## 7. Correctness gaps & partials (L1, adjudicated)
**Material — one genuine functional gap (silent footgun):**
- **Outgoing attachment upload is a STUB, not wired.** `send.py:91–114` `upload_attachments` does `del tab, selectors` and builds `AttachmentRef` metadata only — it **never** calls `channel.upload_files` (which exists + is unit-tested at `cdp.py:841`). So `ask --attach FILE` records refs and **silently sends the prompt without uploading the files**, with no error. No test pins "send actually uploads," which is why it passes 254. This is the *silent-no-op* class the rewrite set out to kill. **Recommendation: wire upload into the send path, OR make `--attach` fail-closed ("outgoing upload not yet supported"), before users rely on it / before merge if upload is a v2.0 requirement.**

**Non-blocking partials (intentional designs, false alarms, or near-term):**
- `create` is a pure-offline **draft** (`conversation_id=None, is_draft=True`); id materializes on first send. Matches M3 §643 intent; first-send materialization is real-proven (M7b). Diverges from M3's "opens a tool-owned new chat" wording (it does **no** browser action) — honest note, functionally sound.
- `fetch` returns **cached** attachment bytes and **fails closed** for uncached refs; on-demand download is via `scrape --with-attachments` (real-proven for target shapes, M6). Conservative per M3 §748 ("remain lazy/unsupported for unknown refs until byte routes are verified"); the standalone `fetch` "lazy download" promise (SPEC §52) is only partially met. Moderate, documented.
- `status` diagnostics shallower than M3 §12 (omits model/active-tools/last-turn/branch/selector-presence; treats CDP-preflight-OK as signed-in without login-wall DOM check). Non-blocking.
- **TabPool** does lazy-open + LRU-on-full but **no idle-TTL eviction**; `max_active_tab_ops` stored but **unused** (M3 §734 lists idle-evict as acceptance). Non-blocking; concurrency is mock-only anyway.
- Capture **fallback chain** (clipboard/KaTeX/DOM) requires explicit `allow_clipboard=True`; `scrape` doesn't pass it, so a backend-shape failure **fails closed** to `HUMAN-ACTION-NEEDED` rather than silently returning lossy DOM. Conservative (good), but the fallback is not reachable through `scrape` without the lower-level flag. Non-blocking.
- Default data-dir is the **repo `cache/`** (when `pyproject.toml` is found), not M3/SPEC §8 `~/.local/state/ask-chatgpt/`. This is the **intentional M6 cache-default decision** (`test_cache_default.py`); CLI `--data-dir`/`ASK_CHATGPT_DATA_DIR` still win. Documented divergence.

**PASS (strong + non-vacuously tested):** CLI verb wiring (`ask·create·scrape·history/export·fetch·loop·status`; v1 bundle/patch **absent**); store (layout, append-only-by-message_id, atomic raw, last-writer-wins, partial salvage, payload mirror); identity (stateless URL/id, both shapes, alias, project_id); backend capture parse/linearize + math fidelity; verified send + completion; menu Radix model+tools abstraction (DR orthogonal; `active_tools`≠`model`); channels (mock+cdp; launched-`real` **dropped**); allowlist; error taxonomy.

## 8. Verdict + merge recommendation
**Offline core: VERIFIED — PASS with documented limitations.** 254 passing + **falsifiable** (9/9) + **4 gotchas fixed & pinned** + **safe & leak-clean** (real bar) + `stable` unmoved + nothing pushed + no `uv tool`. Real-site coverage is **honestly scoped** (§6). One material correctness footgun (upload stub, §7) and a set of mock-only/untested-live capabilities that constitute the documented v2 boundary.

**Recommendation to the team lead / operator (merge is operator-reserved):** **Conditional GO.** `rewrite-v2` is a clean strict-ahead fast-forward over `main` (49 ahead / 0 behind) and a sound v2 foundation that regresses nothing (it supersedes stale v1 on `main`). I recommend the operator **merge**, eyes open to two items: (1) **resolve the upload stub** — wire `upload_files` or make `--attach` fail-closed — this is the one item I would not ship silent, as it reproduces the silent-no-op bug class; (2) accept the **mock-only/untested-live list** (§6) as the v2 boundary, validated incrementally via attended real legs (the cheapest next step: one operator-attended **no-send** leg to close GPT-5.5 family-submenu + Deep-Research **selection**). Optional, operator-discretion: scrub committed test-conversation IDs before any **public** push. I do **not** block the merge on the mock-only items; I **flag** the upload stub as the one pre-merge correctness fix to consider.

Do not overclaim: this verification is **mock-first + committed-evidence**; no new real-site behavior was exercised in M8.
