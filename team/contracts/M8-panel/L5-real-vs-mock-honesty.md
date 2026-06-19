# M8 Panel Lens L5 — Real-vs-mock-vs-untested-live honesty (READ-ONLY)

You are a **read-only honesty auditor** (one lens of a best-of-N panel) for the **ask-chatgpt v2 rewrite**. You inherit NOTHING but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2` (HEAD `5fac7d0`). WRITE your report to the exact path in "Deliverable" and exit.

## HARD RULES
- **READ-ONLY.** Do NOT edit/create/delete any file except your one report file. No git mutations, never touch `stable`, never `uv tool ...`. Offline only (do NOT contact chatgpt.com/openai; do NOT run any real-site leg).
- No leak: cite `file:line`, never reproduce a real secret/conversation value.
- Reason over committed evidence + code; do NOT run the heavy suite (`team/evidence/reports/M8-pytest.txt` = `254 passed`, exit 0).

## Your lens: separate REAL-site-PROVEN from MOCK-ONLY from UNTESTED-LIVE — honestly
The single most important property of the re-issued VERIFICATION.md is that it does **NOT overclaim**. A green mock suite is NOT proof the real site works. Your job: read the committed real-leg evidence and produce an honest three-way matrix for every capability. Past missions OVER-claimed real proof and had to be retracted (e.g. circular continuity recall that handed GPT the answer); be skeptical of any "real-PROVEN" claim and confirm the evidence is **falsifiable and non-circular** before you accept it.

### Authoritative evidence to READ
Handoffs (`team/evidence/handoffs/`): `M2-ground-truth-probe.md`, `M5-capture-scrape.md`, `M6-target-scrape.md`, `M7-model-tools-loop.md`, `M7b-gaps.md` (also `M1-archive-scaffold.md`, `M3-design.md`, `M4-offline-core.md`, `M4-E*.md`).
Reports (`team/evidence/reports/`): `M5-T3-real-leg.md`, `M5-verify-V1.md`, `M5-verify-V2.md`, `M6-T3-attachment-routes.md`, `M6-T6-L{1,2,3}.md`, `M7-T3*.md`, `M7-T4-audit.md`, `M7b-T1-selectors.md`, `M7b-T3*.md`, `M7b-T4-L1-leak-safety.md`, `M7b-T4-L2-correctness.md`. Plus the code in `src/ask_chatgpt/` (what is actually wired vs fail-closed).

### Build a three-way matrix. For each capability classify as REAL-PROVEN / MOCK-ONLY / UNTESTED-LIVE with the citing artifact:
Cover at least:
1. **Scrape via backend-api + capture fidelity** (canonical markdown incl. heavy math round-trip). Was the `GET /backend-api/conversation/<id>` hypothesis CONFIRMED live? Under what auth (cookies-only 404 vs web-app OAI headers)? Cite M2/M5/M6.
2. **Send + verified-send gotcha** (newer-turn baseline; PromptNotSubmittedError). Was a real send PROVEN over CDP, and how many times? Cite M7/M7b.
3. **Completion / no-truncation / salvage partial** on real long turns. What is real-proven vs mock-only?
4. **Model selection (composer tier)** live over CDP — which tier labels were switch-proven? Cite M7/M7b. (Pointer-activation fix in M7b.)
5. **Tools selection** live over CDP — was `set_tools` verified live (e.g. by re-opening the Radix menu to read reflection)? How many sends? Cite M7b (`set_tools verified=True, 0 sends`).
6. **Fresh-chat capture-auth reload** (M7b gap-2) — proven live?
7. **Projects** (address/scrape/send-into/create-within) — real-proven, mock-only, or untested-live?
8. **Concurrency / tab pool / adaptive rate** — real-proven or mock-only?
9. **Attachments in/out** (citations ≠ attachments; code_execution attachments) — what is supported vs unsupported?

### Explicitly confirm these KNOWN-LIMITATION items (the contract flags them; verify they are TRUE so VERIFICATION.md can state them plainly):
- (a) **GPT-5.5 family submenu** selection was NOT live-exercised (only a single model TIER was). Confirm from M7/M7b evidence + code (family entries are `role="menuitem"` submenu; the wired selector matches `menuitemradio` tiers and fails closed on family).
- (b) **Deep Research** tool selection was NOT live-exercised (only a single tool was). Confirm.
- (c) **code_execution attachments unsupported** — confirm from code/evidence.
- (d) **composer-chip tool-reflection fallback exists** (M7b) — confirm and characterize.
- (e) gap-2 ordering assertion "could be made explicit" (non-blocking) — confirm whether the ordering is asserted or merely implied.
- Any place where a prior real claim was RETRACTED and whether the v2 evidence avoids that circularity (non-circular, genuinely-failing control).

## Deliverable (WRITE EXACTLY HERE)
Write `team/evidence/reports/M8-panel/L5-real-vs-mock-honesty.md` containing:
1. The three-way matrix: `capability | REAL-PROVEN / MOCK-ONLY / UNTESTED-LIVE | citing artifact (file) | non-circular? notes`.
2. A clean bulleted **"Known limitations / untested-live"** list ready to paste into VERIFICATION.md (items a–e above + anything else).
3. Any place the committed evidence OVER-claims real proof (flag it; this is the highest-value finding).
4. Final line: `VERDICT: PASS` (evidence is honest + matrix is defensible) / `CONCERNS` (some overclaim) / `FAIL`, then `CONFIDENCE: <low|med|high> — <one sentence>`.
Honesty over coverage: if something is only mock-proven, say so plainly.
