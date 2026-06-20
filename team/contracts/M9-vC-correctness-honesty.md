# M9 · V-C — Independent correctness / spec / claim-honesty audit (READ-ONLY)

You are an independent **pi verifier** for `ask-chatgpt-dev`, branch `rewrite-v2`, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **READ-ONLY**: do not edit `src/`/`tests/`, do not commit, do not run the browser. You may run `git` + `uv run pytest` + read files. Write ONLY your report. Use `uv run` for python.

## Your job
Independently verify the M9 changes are **correct and that the claimed results are HONEST** (no overclaim, no absence-of-assertion gaps). Use `team/evidence/M9-change-map.md` as a navigation map only; re-derive every claim from the actual code/tests/handoffs.

## Checks (re-derive each from ground truth; single-token verdict + evidence)
1. **Upload wire is real (not a stub).** Read `src/ask_chatgpt/send.py:upload_attachments` — confirm it actually calls `tab.channel.upload_files(tab, selectors["file_input"], paths)` and waits for `selectors["attachment_chip"]`, raising `AttachmentUploadError` (fail-closed) if no chip. Confirm the PRODUCTION path `Session._run_send_turn` reaches it (no `del tab, selectors` remains). Confirm `ask --attach` can **NEVER silently no-op** (it either uploads-with-chip or raises).
2. **Selectors projected.** Confirm `file_input`, `attachment_chip`, `active_tool_chip` are in `REQUIRED_SELECTOR_KEYS` AND `SelectorMap` TypedDict AND `real.json`, and that `load_selector_map("real")` returns them (the strict loader projects only required keys — a key missing from `REQUIRED_SELECTOR_KEYS` would be silently dropped).
3. **Send-enable + verify-tolerance correct.** Confirm `_run_send_turn`/`send_prompt` pass the 60s settle timeout ONLY when attachments present, and `verify_prompt_submitted(has_attachments=True)` uses substring-contains (exact equality otherwise — the no-attachment gotcha-#2 guard must be intact). Confirm `SubmittedTurn.normalized_prompt` stays the bare prompt (canonical user content is not polluted with the filename).
4. **DR reflection general + fail-closed.** Confirm `set_tools` reflects via `active_tool_chip` OR menu aria-checked, fail-closed if neither, and is NOT a literal "Deep research" special-case (operator wants general abstractions). Confirm Web-search reflection still works.
5. **Family is fail-closed + honestly limited.** Confirm `_select_model_from_family_submenus` never opens `Recent files`/`Projects`, is fail-closed, and that the LIVE result was a fail-closed error (W4/W6 handoffs) — i.e. family live selection is an HONEST documented limitation, not silently broken.
6. **No absence-of-assertion gaps.** For each of the 6 fixes, confirm a test actually PINS the behavior (would catch a regression), not just exercises shape. Specifically hunt: does a test assert `upload_files` is actually invoked in the production path? does a test assert the fail-closed raise? does a test assert send waits past 2s for attachments? does a test assert substring-verify for attachment turns? does a test assert chip-reflection for an unchecked-menu tool? Flag any fix lacking a real pinning assertion.
7. **Claim honesty.** Cross-check the W1–W7 handoffs' claims against the code + the W7 `uv run pytest` (267). Flag ANY overclaim — especially: is "upload real-verified" honestly scoped (live staging + live send/user-turn-creation PROVEN; final library capture of the attachment turn NOT live-re-verified because send budget spent)? Is DR honestly "live-verified via chip"? Is family honestly "fails-closed live / documented limitation"?

## Handoff (write ONLY this, then stop)
Write `team/evidence/reports/M9-panel/LC-correctness-honesty.md`:
1. **Status** (single token: `PASS`/`CONCERNS`/`FAIL`), top.
2. Per-check verdict (1–7) with code evidence (file:line, test names).
3. Any correctness bug, absence-of-assertion gap, or overclaim — with exact location and the honest correction.
4. A crisp, ground-truth-checked statement of what is TRUE for each of the 3 mission items (upload / family / DR), suitable for the manager to fold into `VERIFICATION.md` without overclaiming.
Credential-free, factual, re-derived from the files.
