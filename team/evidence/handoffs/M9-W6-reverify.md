PARTIAL

## A — upload end-to-end

- Production `send_budget.successful_submissions`: upload leg `0`, total `0` / cap `2`.
- Upload attempts: `2` (the allowed max); both were upload-smoke attempts only.
- Created conversation id+url: none captured; `session.ask(...)` did not return a `TurnRecord`.
- Send completed: `False`.
- Errors: both attempts raised typed `PromptNotSubmittedError` (`PROMPT_NOT_SUBMITTED`) after the verifier saw `last_seen_user_count=1`; no `AttachmentUploadError` was reported, but end-to-end upload was not proven.
- User-turn attachment evidence: unavailable (`user_turn_has_attachment=False`, `attachment_count=0`, `name_matches_m9_upload=False`, `size_matches=False`) because no captured conversation/history was produced.
- Assistant captured: `role_is_assistant=False`, `status_complete=False`, `content_nonempty=False`, `capture_source=None`.

## B — family

- Initial model label: `Pro Extended`; sustained ~12s: `True`.
- `select_model("GPT-5.4")`: fail-closed typed `ModelSelectionNotReflectedError` / `MODEL_SELECTION_NOT_REFLECTED`; details recorded only `requested_model=GPT-5.4`, `selected_label=GPT-5.4`.
- Verified+restored: `False`; restore was skipped because target selection was not verified.
- Sends: `0`.

## C — DR

- `set_tools(["Deep research"])` verified: `True`.
- Reflected value: `Deep research`.
- Verified via composer active-tool chip: `True`; selector `button[aria-label*="click to remove" i]`, chip aria label `Deep research, click to remove`.
- Cleared before upload: `True` via reload; post-clear active-tool-chip present `False`.
- Sends: `0`; Deep Research was never run.

## Safety

- Fresh throwaway chats only; order executed DR → family → upload.
- Protected `6a316aa8`/foreign tabs untouched per driver guards; own-tab-only via production `Session`/`TabPool`; no `/json/list` or page enumeration in driver.
- Browser not quit; `session.detach()` only; post-detach `/json/version` alive: `Chrome/149.0.7827.53`.
- No send while tool/DR armed; upload precheck was clear.
- No auth/OAI/cookie/bearer values or conversation content logged.
- Branch stayed `rewrite-v2`; `stable` unchanged; staged files at end `[]`.

## Artifacts (+trust)

- `scripts/m9_w6_reverify.py` — driver used with `uv run python`.
- `team/evidence/reports/M9-W6-reverify.txt` — trusted scrubbed driver report.
- `cache/m9-w6-reverify/` — gitignored Store data-dir; may contain raw capture/debug state, not summarized here.

## Blockers

- Upload smoke did not close: both allowed attempts failed with `PromptNotSubmittedError`, so no assistant capture and no backend attachment metadata were proven.

## Recommended next

- Do not spend more live sends without renewed budget. First inspect/fix the attachment prompt-submission verifier path offline against captured Store/DOM facts; then rerun a single fresh upload smoke if approved.
