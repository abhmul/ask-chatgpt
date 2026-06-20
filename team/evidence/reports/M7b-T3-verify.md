Status: PARTIAL

# M7b-T3 real verification

## CDP preflight
- Endpoint used: `/json/version` only.
- Browser version: `Chrome/149.0.7827.53`
- Protocol-Version: `1.3`
- WebSocket URL present: `True`
- Preflight ok/error: `True` / `None`

## Send count
- Exact this-run `send_budget.successful_submissions`: `1`
- Per-leg sends: Leg 1=`0`, Leg 2=`1`, loop=`0`
- Cap respected (`<= 3`): `True`
- Leg 1 zero sends: `True`

## NEW throwaway conversations created
- `/c/6a3591ae-d330-83ea-8a18-543701a8c33f` — `https://chatgpt.com/c/6a3591ae-d330-83ea-8a18-543701a8c33f`
- Protected conversation `6a316aa8` touched: `False`

## Gap-1 results — live model/tool selection, zero sends
- Initial model label `L0`: `Pro Extended`; initial sustained read ok: `True`
- Target tier `T`: `High`
- `select_model` result: `{"reflected": "High", "requested": "High", "verified": true}`
- `select_model` fail-closed error: `null`
- Independent ~12s model-label confirmation: `{"duration_s": 12.003, "last_labels": ["High"], "ok": true, "sample_count": 7}`
- `set_tools` result: `null`
- `set_tools` fail-closed error: `{"code": "TOOL_SELECTION_NOT_REFLECTED", "details": {"requested_tool": "Web search", "selected_label": "Web search"}, "exit_code": 32, "message": "requested tool was selected but not reflected", "retry_action": "retry_tool_selection", "retryable": true, "type": "ToolSelectionNotReflectedError"}`
- Restore original model outcome: `{"attempted": true, "error": null, "reflected": "Pro Extended", "verified": true}`
- Selector note: current model selector is `form button[aria-haspopup="menu"]:not([data-testid])`; old offline selector was `composer-footer button[aria-haspopup="menu"]`.
- Selector counts from own tab: `{"new_model_count": 1, "new_model_selector": "form button[aria-haspopup=\"menu\"]:not([data-testid])", "new_model_visible_count": 1, "old_model_count": 0, "old_model_selector": "composer-footer button[aria-haspopup=\"menu\"]", "old_model_visible_count": 0, "tools_count": 1, "tools_selector": "button[data-testid=\"composer-plus-btn\"]", "tools_visible_count": 1}`
- Fail-closed behavior observed: typed menu-selection errors are recorded above when raised; success path raised none.
- Send count after Leg 1: `0`
- Verdict: gap-1 `NOT CLOSED`

## Gap-2 results — fresh-chat send→capture
- Assistant role/id/status/partial: `assistant` / `514b9aba-a6f2-42bc-8269-a35e46f05510` / `complete` / `False`
- Assistant char-count: `4`
- Capture source/fidelity: `backend_api` / `canonical`
- Checks: `{"all_proven": true, "assistant_turn_present": true, "capture_backend_api": true, "content_nonempty": true, "conversation_id_not_target": true, "conversation_id_present": true, "conversation_url_has_id": true, "fidelity_canonical": true, "partial_false": true, "role_is_assistant": true, "status_complete": true, "transcript_roles": {"assistant": 1, "user": 1}, "transcript_turn_count": 2, "transcript_user_and_assistant_present": true, "user_prompt_present": true}`
- User prompt present (bool only): `True`
- Content non-empty (bool only): `True`
- `all_proven`: `True`
- Backend capture verdict: `capture_source == backend_api`; reload→GET→header-harvest path worked.
- Transcript metadata: `{"conversation_id": "6a3591ae-d330-83ea-8a18-543701a8c33f", "conversation_url": "https://chatgpt.com/c/6a3591ae-d330-83ea-8a18-543701a8c33f", "ids_by_role": {"assistant": ["514b9aba-a6f2-42bc-8269-a35e46f05510"], "user": ["4a0864fb-f046-438c-b27f-ec98df69ec4b"]}, "raw_mapping_path": "cache/m7b-t3-verify/conversations/6a3591ae-d330-83ea-8a18-543701a8c33f/raw-mapping.json", "roles": {"assistant": 1, "user": 1}, "transcript_path": "cache/m7b-t3-verify/conversations/6a3591ae-d330-83ea-8a18-543701a8c33f/transcript.jsonl", "turn_count": 2}`
- Submissions after Gap 2: `1`
- Error: `null`
- Verdict: gap-2 `CLOSED`

## Loop leg
- Status: `SKIPPED`
- Reason: `frugal: optional 2-iter loop skipped after required backend_api smoke verification`
- Turns: `[]`
- Error: `null`

## Confirmations
- Branch at start/end: `rewrite-v2` / `rewrite-v2`
- HEAD short at start/end: `1ea867a` / `1ea867a`; expected `1ea867a` at start: `True`
- Own-tab-only via Session/TabPool: `True`
- No `/json/list` call and no page enumeration in driver: `True`
- Browser not quit; Session.detach only: `True`
- Post-detach `/json/version` ok: `True`; browser: `Chrome/149.0.7827.53`
- Fresh throwaway sends only: `True`
- No auth/OAI/cookie/bearer values logged: `True`
- No conversation content printed or reported: `True`
- `cache/` not staged: `True`
- `controller.mjs` and `human/` unstaged: `True`
- `stable` unmoved by this script: `True`
- Stable rev start/end: `779eb40b196e1a458a820248b2dbbca22411b0d3` / `779eb40b196e1a458a820248b2dbbca22411b0d3`
- Staged files at end: `[]`

## Blockers
- `GAP1_NOT_CLOSED` in `gap1`: `set_tools` failed closed with `TOOL_SELECTION_NOT_REFLECTED` after selecting `Web search`; update/inspect the live tool reflection path before claiming gap-1 closed.

## Signals
- Model selection portion of gap-1 did verify live: `Pro Extended` → `High`, independent ~12s sustained read ok, then restored to `Pro Extended`.
- Tool selection failed closed on the live composer; the selected label was clicked but reflected checked state was not observed.
- Gap-2 backend capture is closed: fresh throwaway `/c/6a3591ae-d330-83ea-8a18-543701a8c33f` captured via `backend_api` / `canonical`.
