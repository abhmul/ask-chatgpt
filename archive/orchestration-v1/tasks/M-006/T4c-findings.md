# T4c — VERIFY (independent, non-producer): empirical findings, UC1-3 real evidence, spec coverage, D-001 revisit

You are an INDEPENDENT verifier. You did NOT produce this work. **You inherit NOTHING but this file.** ZERO real-site contact, ZERO messages. Read-only. Do NOT edit source or re-run real legs.

## Read
- `docs/runbooks/observe-chatgpt-unknowns.md` (the 10 unknowns) vs `orchestration/reports/M-006/discovery.md` (T2 answers) + `real-selectors-proposed.json`.
- `orchestration/reports/M-006/T3.md` (UC1-3 real evidence) + `T3-diag.md` (readiness/send/completion measurements).
- `docs/DECISIONS.md` D-001 (DOM-primary read; download-primary bundle with fenced base64 fallback).

## Verify / assess (with evidence)
1. **10 unknowns:** each answered or honestly marked unknown in discovery.md (selectors for composer/send/assistant-turn/completion/copy/download/upload; session pinning; model hooks; completion signal; truncation; artifact identity; UX errors). Note which are evidence-backed vs deferred.
2. **UC1-3 real evidence is internally consistent (T3.md):** UC1 PASS (real `ask_chatgpt()` text + continuity via URL-derived ref — codeword recall), UC3 PASS (real CLI text + continuity), UC2 PARTIAL. Confirm the evidence supports these verdicts and that no overclaiming occurred.
3. **UC2 D-001 finding is SOUND:** UC2 failed with `DownloadUnsupportedError` (no Playwright Download event on the real site — per T2 — AND no parseable fenced `BEGIN_PATCH_BUNDLE` block). Assess the manager's conclusion that the fenced-base64-zip fallback is fundamentally non-viable on the real site because an LLM cannot emit a byte-exact base64 zip with a correct SHA-256. Is this a correct D-001 revisit (recommend a different bundle channel, e.g., text/diff or a real download integration) rather than a checksum mismatch?
4. **D-001 revisit verdict:** is DOM-primary read correct on the real site? (UC1/UC3 read via `.markdown` succeeded.) Is download-primary real? (No.) Is the fenced fallback real? (Not for LLM-generated zips.) Give an explicit, evidence-based recommendation.
5. **GAP-15 finding:** new-CDP-chat `conversation_ref` persists empty (captured before the URL settles to `/c/<id>`); continuity proven via a tmp URL-derived repair; production fix = refresh ref post-completion. Confirm this is a real, well-characterized finding.

## Output → `orchestration/reports/M-006/T4c.md` (cap ~140 lines)
Findings table + assessments; `T4c-VERDICT: PASS|FAIL|PARTIAL` (PASS = evidence is sound + honestly scoped, even though UC2 is PARTIAL) + the explicit D-001 recommendation. `MESSAGES_USED: 0`. Last line: `T4c-STATUS: DONE`.
