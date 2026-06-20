PARTIAL

## A — upload smoke
- Upload leg sends: `0`; total sends: `0` / cap `2`.
- Created throwaway conversation id+url: `None` / `None`.
- `AttachmentUploadError`: not raised in either allowed attempt; both attempts progressed past upload staging, then failed at submit with `SelectorNotFoundError` because the send button was visible but disabled.
- User-turn attachment evidence: no backend user turn exists because no send/conversation was created; `user_turn_has_attachment=false`, `attachment_count=0`, `name_matches_m9_upload=false`, `size_matches=false`.
- Assistant captured: `role_is_assistant=false`, `status_complete=false`, `content_nonempty=false`, `capture_source=None`.

## B — family
- Initial label: `Pro Extended`; sustained ~12s: `true`.
- `select_model("GPT-5.4")`: failed closed with `MODEL_SELECTION_NOT_REFLECTED` (`reason=TimeoutError`); target sustained confirmation not run.
- Restore: `Pro Extended` restored, reflected, verified; restore sustained ~12s: `true`.
- Sends: `0`.

## C — DR diagnostic
- `Deep research` present: `true` (`role=menuitemradio`, `aria-checked=false`).
- `set_tools`: failed closed with `TOOL_SELECTION_NOT_REFLECTED`; however the composer showed the true armed signal.
- Exact reflection signal: composer chip `button`, `aria-label="Deep research, click to remove"`; candidate stable selector: `button[aria-label*="Deep research" i]`. Menu reopen `aria-checked` remained `false`, so menu checked state is not authoritative.
- Cleared by reload; post-clear chip absent and menu `aria-checked=false`.
- Recommendation: cheap-wire DR reflection to the composer chip selector, not menu `aria-checked` alone.

## Safety
- Total sends `0 <= 2`; fresh throwaway chats only.
- `6a316aa8`/foreign tabs untouched; own-tab-only via `Session`/`TabPool`; no `/json/list` or page enumeration.
- Browser alive post-detach: `Chrome/149.0.7827.53`.
- No Deep Research run; no send while tool/DR armed; no auth/OAI/cookie/bearer/conversation content logged.

## Artifacts (+trust)
- `scripts/m9_w4_smoke.py`
- `team/evidence/reports/M9-W4-smoke.txt`

## Blockers
- Upload smoke did not produce a send/capture: after attachment staging, submit failed twice with send button visible but disabled.
- Family GPT-5.4 selection failed closed live with a timeout.

## Recommended next
- Fix/upload-wire wait: after attachment chip appears, wait for file upload completion / send button enabled before submit, then run a newly authorized smoke.
- Wire DR reflection to `button[aria-label*="Deep research" i]` and document menu `aria-checked` as non-authoritative for this live state.
