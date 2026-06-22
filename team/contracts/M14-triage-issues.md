# Mission M14 — Triage the `issues/` backlog (read-only); recommend the archive set

**Read `team/contracts/M14-common.md` IN FULL first** (your role, the READ-ONLY rule, ground-truth-first, dispatch policy, safety, handoff format). This file is the mission.

## Objective
The operator wants the team to go through the `issues/` backlog, determine which issues are **actually still relevant**, and archive the ones that are **complete or no longer relevant**. Produce an **independently-verified, evidence-backed verdict for every backlog issue** and a concrete **ARCHIVE / KEEP / LEAD-DECIDE** recommendation. You do NOT move any file — the lead executes the archival afterward.

## The backlog to triage (exactly these 8 files under `issues/`)
1. `2026-06-14-capture-renders-dom-not-raw-markdown.md`
2. `2026-06-14-out-suppresses-stdout.md`
3. `2026-06-14-response-truncated-drops-out-file-and-session.md`
4. `2026-06-18-cdp-send-noop-returns-stale-response.md`
5. `2026-06-20-cli-leaks-browser-tab-per-invocation.md`
6. `2026-06-21-chatgpt-rate-limit-too-many-requests.md`
7. `2026-06-22-read-ops-render-full-conversation-page.md`
8. `2026-06-22-scrape-with-attachments-light-path-unverified.md`

`issues/cdp-send-repro/` is a CDP send REFERENCE harness, NOT a backlog issue — exclude it from the triage set (do not recommend archiving or keeping it; just note it is out of scope).

## Taxonomy (assign exactly one verdict per issue)
- **RESOLVED** — the bug/defect the issue describes has a fix that **landed in current `main`**. You must cite the fix: the commit (`git log`), the code that implements it (`file:line` in `src/`), AND ideally the falsifiable test that pins it (`tests/...::test_name`) — and confirm the test actually asserts the fixed behavior (read it; a green exit is not enough). → recommend **ARCHIVE**.
- **OBSOLETE** — the issue describes a behavior/code path that **no longer exists** in current `main` (e.g. the v1 library or an early-rewrite code path it targeted was removed/replaced), so the bug is moot. Show the described code path is gone (the old symbol/function/file does not exist; the subsystem was rewritten). → recommend **ARCHIVE**.
- **STILL-RELEVANT** — the described problem is **still reproducible / still present** in current `main`, OR it is an accepted open enhancement/finding the team intends to keep tracking. → recommend **KEEP**.
- **JUDGEMENT-CALL** — the disposition genuinely depends on operator intent (not resolvable from the directive's own "complete or no longer relevant" criterion). State BOTH readings with evidence. → recommend **LEAD-DECIDE** (do NOT pick for them).

The **ARCHIVE set = RESOLVED ∪ OBSOLETE**. The **KEEP set = STILL-RELEVANT**. JUDGEMENT-CALL items go to the lead.

## Per-issue CLAIMS to verify (these are hypotheses to FALSIFY from ground truth, NOT facts)
Re-derive each from the current tree; do not trust the stamp/claim:
- **#5 tab-leak (06-20):** the file carries a "Resolution (2026-06-22) — FIXED" stamp; the claim is M11 wrapped `ask`/`scrape`/`loop` handlers in `try/finally: session.detach()` in `src/ask_chatgpt/cli.py` + added lifecycle tests in `tests/test_cli.py`. VERIFY the `finally: detach()` is actually present on those handlers in current `main`, and a test pins open==close. Adversarially: is there any CLI path that still leaks a tab?
- **#7 read-ops render full page (06-22):** stamp "Resolution — FIXED on `fix/m10-light-read-scrape`" (M10, merged via PR #2). Claim: `TabPool.acquire(ref, render=...)` + `scrape` uses a light page + ambient backend-header harvest. VERIFY the render-control + ambient-harvest code is in current `main` (`src/ask_chatgpt/session.py`, `capture.py`, `channels/cdp.py`) and a test pins it.
- **#8 scrape --with-attachments light path (06-22):** stamp "Resolution — VERIFIED, no code change needed" (M13). Claim: descriptor fetch tolerates the conversation-path header on the light origin; a falsifiable descriptor-header mock test was added to `tests/test_capture.py`. VERIFY that test exists + asserts the descriptor headers, and confirm whether this follow-up is fully closed (the "unverified" in its title is what M13 closed).
- **#1 capture renders DOM not raw markdown (06-14):** math corruption (`\widehat`/`\ne` dropped) from capturing rendered-DOM `textContent`. This predates the rewrite. The rewrite (M5/M6) captures via the authenticated `GET /backend-api/conversation/<id>` (canonical JSON), not DOM `textContent`. VERIFY: does current `capture.py` read from backend-API canonical content (not DOM textContent)? Is there a test pinning math fidelity (e.g. `\widehat`/`\ne`/`\frac` preserved, flattened-frac=0, literal U+2260=0)? Is the old DOM-`textContent` capture path GONE? → likely RESOLVED-or-OBSOLETE, but PROVE it.
- **#2 --out suppresses stdout (06-14):** `--out FILE` wrote to file only, not stdout. Current behavior (per team memory) is that `--out` mirrors to BOTH stdout and file. VERIFY in current `cli.py`/`store.py` (the emit/`emit_payload` path): does `--out` now also write stdout? Is there a test? → likely RESOLVED, but PROVE it (and note: this is the intended current design).
- **#3 ResponseTruncatedError drops --out file + session registry (06-14):** on a truncated long reply, the `--out` file wasn't written and the session registry wasn't saved. This predates the rewrite. VERIFY: does a `ResponseTruncatedError` class still exist in current `src/ask_chatgpt/`? Does the rewrite's eager-write / partial-salvage behavior write partial output + persist state on truncation? Is the v1 code path the issue describes still present? → could be RESOLVED (eager-write/salvage) or OBSOLETE (path gone) — determine which from the code, and check for a pinning test.
- **#4 cdp send no-op returns stale response (06-18):** `--channel cdp` against an already-complete session silently did NOT send and returned the stale prior response as success. Two defects: `send_prompt` never verified a turn was submitted; `wait_for_completion` had no new-turn baseline. This was filed against the OLD stable CLI; the rewrite added "gotcha-4" new-turn verification. VERIFY in current `src/ask_chatgpt/` (session/send path): does the send path now verify a NEW user turn was created (baseline user-turn count → assert increment), and does completion wait key off the new turn? Is there a falsifiable test? → likely RESOLVED, but PROVE it. (Memory note for context only, still verify: the *separately-installed* `stable` tool may still carry the old bug, but the issue is about the library/code, and the team tracks `main`.)
- **#6 rate-limit "Too many requests" (06-21):** this is a **FINDING** (documents incident R-001 + operational guidance) PLUS a "Suggested tool-side fixes" section. M12 verified the three tool-side fixes (429/modal detection + distinct exit code; Retry-After/backoff; cross-process governor) are **ABSENT** in `main`, and the operator decided **DO NOT BUILD** (the issue was augmented with an implementation sketch). VERIFY: (a) are those tool-side fixes still absent in current `src/ask_chatgpt/` (grep for 429 / RateLimited / Retry-After / backoff / governor; check `errors.py`)? (b) is the operational guidance still accurate? (c) is the operator's "do not build" + impl sketch recorded in the file? This is the **JUDGEMENT-CALL**: one reading = "documented finding + explicitly-declined enhancement → archive"; other reading = "open (un-built) tool-side enhancement we still track → keep". Present BOTH; recommend LEAD-DECIDE.

## Recommended decomposition (you may adapt; the independent-verification requirement is non-negotiable)
- **W1 — investigator (read-only pi).** Reads all 8 issue files + re-derives each verdict from current `main` (code in `src/ask_chatgpt/`, tests in `tests/`, `git log --oneline` + `git log -p -- <path>` / `git log --all --grep`). Produces a full per-issue verdict table with `file:line` / commit / test evidence. (If you prefer, split W1 into two workers — e.g. one for the 4 older 06-14/06-18 issues, one for the 4 newer 06-20→06-22 issues — for parallelism; that's fine.)
- **W2 — adversarial verifier (read-only pi, distinct prompt).** For EVERY issue W1 marked ARCHIVE (RESOLVED/OBSOLETE), independently tries to **falsify** that verdict: re-read the issue's root-cause, then hunt the current `main` code for the bug STILL being live (the vulnerable code path still present; the fix absent or incomplete; the pinning test missing or non-falsifiable). W2's job is to find a reason NOT to archive. It reports, per archive candidate: `CONFIRMED-RESOLVED` or `CHALLENGE: <evidence the bug may still be live>`.
- **You (manager)** synthesize W1 + W2 and adjudicate. An ARCHIVE verdict only stands if W2 could not falsify it (or its challenge is, on your own ground-truth re-derivation, wrong). Where W1/W2 disagree and you cannot resolve it from ground truth, downgrade to STILL-RELEVANT (KEEP) — **archiving a live bug is the costly error; keeping a resolved one is harmless.**

## Output
- The handoff `team/evidence/handoffs/M14-triage-issues.md` per the format in `M14-common.md` §Handoff.
- Final stdout: Status token + the exact ARCHIVE list (filenames) + the KEEP list + any LEAD-DECIDE items + the handoff path.

## Hard constraints (repeat)
- READ-ONLY. No file moves, no edits, no git mutation, no commit/push. You only write the handoff + pi run dirs.
- Re-derive from ground truth; adversarially falsify every "resolved". Bias to KEEP when uncertain.
- Single-shot: block your pi workers to completion in this one turn; NO background monitor, NO yield; write the handoff before exiting.
