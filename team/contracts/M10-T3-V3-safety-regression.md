# M10-T3-V3 — Safety/leak + regression + no-overclaim verifier (READ-ONLY)

**FIRST read `team/contracts/M10-common.md` (safety + ground truth) and
`team/evidence/handoffs/M10-T2-implement.md`.** You are an INDEPENDENT verifier —
re-derive from the code on branch `fix/m10-light-read-scrape` (HEAD). READ-ONLY:
modify NO source/test file; write ONLY your handoff. OFFLINE.

## Verify (cite file:line), CONFIRM or REFUTE:
1. **No secret leak.** The new/changed code never logs, prints, persists, or puts
   into exceptions/`details` any auth token, OAI header VALUE, cookie, or
   conversation content. Check `BackendAuthUnavailableError` and any new error
   `details`, any new logging, and the retarget/ambient code. (Header NAMES are OK;
   VALUES are not.)
2. **Diff scope is clean.** `git diff --name-status main..HEAD` touches only
   `src/ask_chatgpt/{session.py,capture.py,channels/cdp.py}`,
   `tests/{test_capture.py,test_session_stubs.py}`, and the T2 handoff. No unrelated
   files (the working tree had pre-existing dirty/untracked `issues/…`, `human/`,
   `controller.mjs` — confirm they were NOT committed). `stable` ref unmoved
   (`git rev-parse stable` = bbbe027). No push/merge happened.
3. **Regression surface.** Run `uv run pytest` once (read-only) and inspect the FULL
   summary (expect 275 passed). Then reason: does the `cdp.py:wait_for_request`
   change alter behavior for ANY existing caller besides ambient mode? Could the
   "retain deficient, keep scanning" change make the DEFAULT conversation harvest
   slower-to-fail or change its returned snapshot in a way that affects send/draft/
   completion? Could `(mode,url)` keying change eviction/LRU or `snapshot()` output
   relied on by existing tests?
4. **Attachment path.** `scrape --with-attachments` reuses the (now retargeted)
   conversation header dict for descriptor + byte-route fetches
   (`capture.py` ~314, ~422-429). Confirm attachments still use correct headers
   (not a generic ambient request's path) and existing attachment tests cover it;
   flag if a real attachment leg is needed.
5. **No overclaim / honesty.** The implementation/handoff must NOT claim the fix is
   real-site proven, nor that read cost is O(1) in bytes (the backend JSON fetch +
   parse still scale with conversation length; only the RENDER is removed). Flag any
   overclaim for the lead to correct in VERIFICATION/RESUME.

## Required output (handoff)
Write **`team/evidence/handoffs/M10-T3-V3-safety-regression.md`** per the handoff
protocol: STATUS token; per-item CONFIRM/REFUTE with evidence; each issue with
severity (BLOCKING / MAJOR / MINOR) + location; an explicit list of what remains
mock-only vs needs the T4 real leg. Do not run mutation tests (V2's job).
