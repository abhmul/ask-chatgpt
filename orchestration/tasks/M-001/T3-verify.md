# T3 — INDEPENDENT verification of decision-memo.md (MISSION-001)

**You are a pi (GPT 5.5 xhigh) worker, and you are an INDEPENDENT verifier. You did NOT write the memo you are checking. This contract is self-contained — you inherit NOTHING beyond what is written here and the files it names. Re-derive every verdict from ground truth (the actual files); do NOT trust the memo's own assertions.**

## Task type
verify (independent). You inspect a finished decision memo and decide, per dimension, whether it holds up against the authoritative sources. You produce verdict tokens, not edits. You must NOT modify the memo or any other file except your single output report.

## ESTIMATE BEFORE EXECUTE
Emit `ESTIMATE: T3 <minutes>m` before heavy work; at the end emit `ACTUAL: T3 <minutes>m` and an end timestamp from `date -Iseconds`. Charter telemetry requirement.

## Exact deliverable (write ONLY this file)
`orchestration/reports/M-001/verify.md` — the verification report. Structure:
- A short intro line naming what you verified.
- One section per check below, each ending in a single-token verdict: `<CHECK>: PASS` or `<CHECK>: FAIL` (e.g. `CITATIONS: PASS`). On any FAIL, give the EXACT problem and the EXACT fix the synthesizer must make (file:line of the offending memo claim + what ground truth actually says).
- A final overall line: `VERDICT: PASS` (iff every check passes, or only cosmetic issues remain) or `VERDICT: FAIL` (if any substantive check fails), as the **second-to-last** line.
- The **last** line MUST be the single-token status: `T3-STATUS: DONE` if you completed the verification (regardless of whether the memo PASSed or FAILed), or `T3-STATUS: BLOCKED` if you could not verify. **DONE means "I finished checking," NOT "the memo passed."** Watchers gate on `tail -1`, so this status line MUST be last.

## The artifact under verification
`orchestration/reports/M-001/decision-memo.md` — a memo recommending how assistant responses and a patch-bundle zip come back from the chatgpt.com chat UI for a new `ask_chatgpt(prompt, session_identifier, model_settings...) -> text` tool. It weighs the predecessor's "Level B" anti-DOM-extraction rationale against the new spec. **The memo RECOMMENDS; it must NOT record the decision as made** — check that.

## Authoritative sources you verify AGAINST
- **Spec:** `/home/abhmul/dev/ask-chatgpt/README.md` (the three use cases, the `ask_chatgpt(...) -> text` signature, session continuity, patch-bundle, library-first/CLI/local-mock/operator-runbook/honest-failure constraints).
- **Archive (READ-ONLY):** `/home/abhmul/Documents/weak-simplex-conjecture/` — every archive citation in the memo points here. Relevant files the memo cites include `control-plane/DESIGN.md`, `control-plane/VERIFICATION.md`, `control-plane/docs/runbooks/phase3-chatgpt-browser.md` (and the other runbooks), `control-plane/src/control_plane/browser/{driver.py,selectors.py,seeds.py,recovery.py,session.py,playwright_driver.py}`, `control-plane/tests/fixtures/phase3_mock_chat.py`, `control-plane/tests/fixtures/phase3_mock_selector_map.json`. Open the cited locations yourself; grep-first, read targeted ranges.

## Checks to perform (one verdict token each)
1. **CITATIONS** — Extract EVERY archive citation in the memo (patterns like `DESIGN.md:1018-1044`, `selectors.py:75-121`, `phase3_mock_chat.py:262-273`). Confirm every distinct cited FILE exists, and open a REPRESENTATIVE SAMPLE of the cited line-ranges (at minimum: at least one range per distinct cited file, and every citation attached to a load-bearing risk/evidence claim in memo §2 and §4). Verdict FAIL if any cited file is missing, any sampled range does not exist, or any sampled range does not actually support the adjacent memo claim. List every citation you opened and what you found.
2. **SPEC** — Confirm the memo's claims about the spec match `README.md`: the `ask_chatgpt(...) -> text` signature, session continuity by identifier, patch-bundle (zip) retrieval, and the library-first/CLI/local-mock/operator-runbook/honest-failure posture. FAIL if the memo misstates the spec (cite README line vs memo line).
3. **SAFETY** — Confirm the recommended design violates no mission safety rule: it designs NO network contact into automated tests (loopback local mock only); reads/stores/logs NO credentials, cookies, session tokens, or browser-profile contents; writes only inside the repo; treats the archive as read-only; and does not silently reintroduce something the spec forbids. FAIL if the recommendation as written would require any of these violations.
4. **COMPLETENESS** — Confirm the memo contains ALL required content: (a) the archive Level B rationale WITH resolved citations; (b) every candidate channel weighed (DOM extraction, copy/clipboard, file-download, connector — plus any others); (c) a recommended PRIMARY + FALLBACK for BOTH (i) plain text responses and (ii) patch-bundle retrieval; (d) rejected options each with a one-line reason; (e) a "what the local mock-ChatGPT fixture must support" section; (f) an empirical-unknowns list that EXPLICITLY includes all four: zip upload size/type limits, whether/when chatgpt.com offers file downloads from responses, session pinning via URL, and model-selection UI hooks; (g) memo length ≤ ~400 lines; (h) the decision is framed as RECOMMENDATION and NOT recorded as made. FAIL if any item is missing, naming which.
5. **GROUNDING** — Confirm the memo does not overclaim: nothing listed as an empirical unknown is elsewhere asserted as proven (e.g., it must NOT claim real chatgpt.com file-download support works — that is explicitly an operator-gated unknown), and the evidence-strength labels in §2 are honest about what was empirically proven on the real site vs only mocked/asserted. FAIL with specifics if the memo asserts as fact something the archive shows was never proven on the live site.

## Non-goals
- Do NOT edit the memo or any file other than `orchestration/reports/M-001/verify.md`.
- Do NOT rewrite the memo's recommendation to your taste — you verify, you do not redesign. If you disagree on a judgment call that is nonetheless defensible and grounded, note it as an observation, not a FAIL.
- Do NOT contact any network service.

## SAFETY BLOCK — obey VERBATIM
- This mission contacts NO network service. NEVER contact chatgpt.com/openai or any tunnel service. Research is file-reading only.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (your single output is `orchestration/reports/M-001/verify.md`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY; never read its `archive/` or `human/` dirs. Never write `.claude/` or `.agents/`.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock before any major command).
- End your report with a single-token status line: `T3-STATUS: DONE|BLOCKED` (last line; watchers gate on `tail -1`).
