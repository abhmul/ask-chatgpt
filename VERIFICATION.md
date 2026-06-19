# VERIFICATION — ask-chatgpt v2 (rewrite-v2) — re-issued 2026-06-19 (M8, independent terminal verification)

> This file verifies the **v2 rewrite** on branch `rewrite-v2` (@ `5fac7d0`). It **replaces** the prior v1 verification (missions M-004…M-010), which verified the now-archived v1 library and is stale. The v1 verdict history remains in git.
>
> **Lens: falsifiability + prompt-quality, NOT a green exit.** A green suite is necessary, not sufficient — every load-bearing claim below was either mutation-proven falsifiable or re-derived from ground truth. Real-site-proven, mock-only, and untested-live are kept strictly separate; known limitations are stated plainly.
>
> **Method (M8):** one authoritative `uv run pytest` produced once, then a best-of-N panel of 5 independent read-only lenses (correctness/spec, falsifiability, gotcha-coverage, safety/leak, real-vs-mock) reasoning over it + committed M1–M7b evidence; the manager re-derived every contested claim from ground truth. No new real-site leg was run (offline-preferred). Full evidence: `team/evidence/reports/M8-verification.md` + `team/evidence/reports/M8-panel/L{1..5}-*.md`.

## Headline verdict
**Offline core: VERIFIED — PASS with documented limitations.** Real-site capabilities: **honestly scoped** (a defined set proven over attended CDP; the rest mock-only/untested-live). One material correctness footgun (outgoing upload is a stub — see Limitations). Safety/leak/isolation: **PASS** (one non-blocking hygiene note). Merge `rewrite-v2 → main`: **conditional GO, operator-reserved** (see end).

## Authoritative test result
`uv run pytest` → **254 passed, exit 0** (`team/evidence/reports/M8-pytest.txt`). Mock suite only: `real_site` tests are deselected by default (`addopts -m "not real_site"`) **and** gated on `ASK_CHATGPT_REAL=1`; default runs never contact chatgpt.com (0 real_site collected).

## Falsifiability — the suite CAN fail (independently mutation-proven)
9 distinct **source** mutations across the 4 gotchas + core-store invariants each flipped a passing test to RED, then were restored byte-for-byte (tree verified pristine). **0 vacuous tests.** Examples: rewriting `\widehat`→`\hat` fails the math-fidelity render test; accepting a send unconditionally fails the no-op `PromptNotSubmittedError` test; suppressing stdout fails the `--out`-mirror test; dropping the `oai-` key clause fails the never-persist-auth test. Detail: `team/evidence/reports/M8-panel/L2-falsifiability.md`.

## The four rewrite gotchas — all FIXED and PINNED
| gotcha | fix (mechanism) | pinned by |
|---|---|---|
| Rendered-DOM **math corruption** | reads via the page's own authenticated `GET /backend-api/conversation/<id>` → canonical markdown; lossy clipboard/KaTeX/DOM fallback is permission-gated, marked degraded, fails closed; render preserves literal markdown | `test_store_render`, `test_capture` (math) |
| **Silent no-op send** | baseline latest user-turn id before send; require a **newer** turn + exact normalized prompt, else `PromptNotSubmittedError`; retry transient composer; reload-when-idle | `test_send_completion` no-op/wrong-turn |
| **Truncation / hidden ceiling** | timeout = **no-activity** window (resets on progress); no hard total cap (`max_total_wait_s` opt-in, `None` default); eager-write turn at send; salvage partial with honest `status`/`partial` | `test_send_completion` past-600 + cap + salvage, `test_store_partial` |
| **`--out` suppresses stdout** | `emit_payload` writes stdout **then** `--out`, identical bytes (incl. NUL); `ask/scrape/history/export` route through it | `test_store_payload`, `test_cli` |

**Prompt-quality:** the capture path has **no** GPT-facing prompt; the only send-side model input is the operator's normalized prompt; no base64/marker/self-answering directive exists (grep-clean). *Operational caveat:* the `--out`/stdout mirror is deliberate — agent runs should redirect stdout so response content does not land in logs.

## M7 gaps closed (real-verified, M7b)
- **Gap-1 — live model + tools selection.** The composer model picker is a Radix dropdown activated on **pointerdown** (bare click was the M7 TimeoutError root cause); `select_model` opens → enumerates the portal → selects by label, fail-closed. Real-verified: a model **tier** switch (`Pro Extended`→`High`, sustained ~12 s + restored, by DOM label not model self-report) and a **tool** (`Web search`, verified by re-opening the menu to read `aria-checked`, **0 sends**).
- **Gap-2 — fresh-chat capture-auth.** A client-navigated fresh chat never issues the authenticated backend GET, so headers can't be harvested → the draft branch reloads `/c/<id>` after id-learn + completion before capture (the M6-proven mechanism). Real-verified: a fresh throwaway PONG chat captured `backend_api`/`canonical`.

## Real-site-PROVEN vs MOCK-ONLY vs UNTESTED-LIVE
**REAL-PROVEN** (attended CDP; committed M2/M5/M6/M7/M7b evidence; DOM/backend-state, non-circular):
- Backend-api **scrape** of existing conversations **with harvested web-app Authorization/OAI headers** → canonical markdown (cookies-only/accept-only is **live-refuted**, 404). Math/format **fidelity** on a long real target.
- **Verified send** over CDP (~3 real submissions; one fresh-chat send end-to-end backend-captured).
- **Model tier** selection (one tier, switch+restore) and **one tool** (Web search, no-send).
- **Fresh-chat** capture-auth reload; incoming **attachment** refs for target shapes; own-tab attach/detach hygiene; **detach-not-quit** (browser stays alive).

**MOCK-ONLY / UNTESTED-LIVE** (the documented v2 boundary — validate incrementally via attended legs):
- Outgoing **file upload** on send (also a code stub — see Limitations).
- **loop** multi-turn; **concurrency / TabPool LRU-eviction / adaptive send-rate (AIMD backoff, hard pause)**.
- **Projects** (scrape / send-into / create-within) — code parses project URLs + makes local drafts; no project real leg.
- **GPT-5.5 base-family submenu** selection (only a tier was live; family entries are `menuitem`, the wired selector matches tier `menuitemradio` and **fails closed** on family).
- **Deep Research** tool selection (only Web search was live).
- Newly-generated **long-real-turn** completion / real timeout & partial salvage (existing long-transcript capture IS real-proven; long *generation* is not).
- **code_execution_output attachments** → real-probed and **unsupported** (no byte route; fails closed).

## Known limitations (stated plainly)
1. **Outgoing upload is a stub (material).** `upload_attachments` (`send.py:91`) discards the tab/selectors and records `AttachmentRef` metadata only — it never calls `channel.upload_files`. So `ask --attach FILE` **sends the prompt without uploading the files, silently** (no error, no test pins it). This is the silent-no-op class the rewrite targets. **Fix before relying on upload:** wire `upload_files` into the send path, or make `--attach` fail-closed.
2. **GPT-5.5 family submenu** + **Deep Research** selection are **not** live-exercised (only one tier + Web search were). Fail-closed structurally; recommend one operator-attended **no-send** selection leg to close.
3. **code_execution_output attachments unsupported** (fails closed; no downloadable byte route observed).
4. `create` is a pure-offline **draft** (id materializes on first send; first-send materialization real-proven) — diverges from M3's "opens a chat tab" wording (does no browser action). `fetch` serves **cached** bytes and fails closed for uncached refs (download is via `scrape --with-attachments`). `status` diagnostics are shallow vs the spec. TabPool lacks **idle-eviction** (`max_active_tab_ops` unused). Default data-dir is the repo `cache/` (intentional M6 decision; `--data-dir`/`ASK_CHATGPT_DATA_DIR` override). All non-blocking; loop/concurrency/projects are mock-only regardless.
5. **Transcript append-only nicety:** `transcript.jsonl` is append-only and retains superseded records; readers must dedupe by `message_id` (last-writer-wins) — implemented and tested; no compaction step (by design).

## Safety / leak / isolation — PASS (one hygiene note)
- **No credential / cookie / Authorization / OAI-header / account-identifier / conversation-content leak.** Header names are constants; sensitive keys dropped from persisted raw + redacted in repr/errors (pinned by `test_store_atomic_raw…never_persists_auth_oai_keys`, mutation-proven). No real account email/org/user-UUID committed.
- **No stealth/anti-detection** (`src/` grep-clean; plain `connect_over_cdp`). **Domain allowlist** + **fail-closed selectors** + **atomic writes** + credential-free **error taxonomy** (incl. `PromptNotSubmittedError`). **CDP**: attach-only, own tool-opened tabs only, `detach()` = client disconnect (browser stays alive, real-proven).
- **Isolation:** `stable` **unmoved** (`779eb40`); **nothing pushed** (no `origin/rewrite-v2`); **no `uv tool` install/upgrade/reinstall**; `cache/` and run-dirs gitignored + untracked.
- **Hygiene note (non-blocking, operator pre-push decision):** committed *evidence/docs* contain conversation/message IDs of **test** conversations (the sanctioned read-only target, an approved smoke chat, and a fresh throwaway chat) — not credentials, not content. Pre-existing across M2–M7b; accepted by prior leak gates. The operator may wish to scrub these before any **public** push (the operator owns push). M8's own artifacts are id-free.

## Merge recommendation (operator-reserved)
**Conditional GO.** `rewrite-v2` is independently verified (offline core), falsifiable, safe, and a clean **strict-ahead fast-forward** over `main` (49 ahead / 0 behind) that supersedes stale v1 and regresses nothing. Recommended to merge, eyes open to: **(1)** resolve the **upload stub** (wire or fail-closed) — the one item not to ship silent; **(2)** treat the mock-only/untested-live list as the v2 boundary, closed incrementally via attended legs (cheapest next: one no-send leg for family-submenu + Deep-Research selection). Optional: scrub committed test-conversation IDs before a public push. The merge itself is the operator's call; this is a recommendation, not an approval.

VERDICT: **PASS (offline core) — with documented limitations and a conditional, operator-reserved merge recommendation.** Mock-first + committed-evidence; no new real-site behavior was exercised in M8.
