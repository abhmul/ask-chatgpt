# M9 · V-A — Independent falsifiability re-derivation (mutation testing, self-restoring)

You are an independent **pi verifier** for `ask-chatgpt-dev`, branch `rewrite-v2`, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. You will temporarily mutate source to prove the M9 tests are falsifiable, then **restore byte-for-byte**. Do NOT commit. Do NOT touch the browser/CDP. Use `uv run` for python.

## Critical restore discipline (read first)
The full M9 change set is **uncommitted** in the working tree. To revert/restore a file safely, **use a file-copy backup**, NOT `git stash`/`git restore`/`git checkout` (those would drop ALL uncommitted M9 work, and the destructive-guard hook substring-matches the words check​out/re​set even in comments — avoid them entirely). Pattern per mutation:
```
cp src/ask_chatgpt/<file>.py /tmp/vA-<file>.bak     # backup the exact current bytes
# ...make the mutation with your editor...
uv run pytest -q -k <targeted_test>                  # expect RED
cp /tmp/vA-<file>.bak src/ask_chatgpt/<file>.py      # restore exact bytes
```
After EVERY mutation, restore immediately. At the very end, run `uv run pytest` and confirm **268 passed** and `git diff --stat -- src tests` is **identical to before you started** (capture `git diff --stat -- src tests` at the start and end and diff them). If they differ, you corrupted the tree — say so loudly at the top of your report.

## Mutations to prove falsifiable (each: mutate → targeted test RED → restore)
Read `team/evidence/M9-change-map.md` to locate code. For EACH, confirm the named behavior's test flips to **RED** when the fix is reverted, then restore:
1. **Upload wire** — in `send.py:upload_attachments`, remove/short-circuit the `tab.channel.upload_files(...)` call → the "upload happens in production path" test (asserts a `upload_files` MockCall) goes RED.
2. **Fail-closed chip** — make `_wait_for_attachment_chip` return without raising → the "fail-closed no chip raises `AttachmentUploadError`" test goes RED.
3. **Send-enable-after-attach** — force the 2s settle even with attachments → the send-enable-waits-past-2s test goes RED.
4. **Verify substring for attachments** — force exact equality even when `has_attachments=True` → the attachment-turn substring-verify test goes RED.
5. **DR chip reflection** — remove the `active_tool_chip` fallback in `set_tools` → the set_tools-verifies-via-chip test goes RED.
6. **Family submenu** — neutralize `_select_model_from_family_submenus` → the select_model-finds-`GPT-5.4` test goes RED.

## Vacuousness scan (read-only)
Read every NEW/CHANGED M9 test (`git diff main -- tests`). Flag any that would pass regardless of the fix (assert only on shape/types, no behavioral assertion, or an assertion that can't fail). Confirm the 6 above each have a genuine behavioral assertion.

## Acceptance
- All 6 mutations produce the expected RED; all restored byte-for-byte; final `uv run pytest` = 268 passed; `git diff --stat -- src tests` unchanged start↔end.
- 0 vacuous tests among the M9 additions (or list any found).

## Handoff (write ONLY this, then stop)
Write `team/evidence/reports/M9-panel/LA-falsifiability.md`:
1. **Status** (single token: `PASS`/`CONCERNS`/`FAIL`), top — and an explicit line: `TREE RESTORED: yes/no` with the start vs end `git diff --stat -- src tests`.
2. Per-mutation (1–6): the targeted test, the RED evidence (the failing assertion / error line), and confirmation of restore.
3. Vacuousness findings (none, or the list).
4. Final `uv run pytest` count.
Credential-free, factual. If the tree is not fully restored, put that FIRST and loudest.
