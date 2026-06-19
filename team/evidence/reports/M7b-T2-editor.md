Status: DONE

# M7b-T2 editor report

## Files changed
- `src/ask_chatgpt/selectors/real.json`
- `src/ask_chatgpt/channels/cdp.py`
- `src/ask_chatgpt/channels/mock.py`
- `src/ask_chatgpt/menus.py`
- `src/ask_chatgpt/session.py`
- `tests/test_selectors.py`
- `tests/test_menus.py`
- `tests/test_cdp_channel.py`
- `tests/test_capture.py`
- `tests/test_session_draft_loop.py`
- `team/evidence/reports/M7b-T2-editor.md`

## Gap-1 summary
- Updated the real model selector to `form button[aria-haspopup="menu"]:not([data-testid])`; `tools_button` is unchanged.
- Added `ask_chatgpt_open_radix_trigger` through the channel `evaluate` seam; CDP dispatches pointerdown/mousedown/pointerup/mouseup plus click, and the mock opens the scripted menu through the same key.
- `menus.open_radix_menu` now uses that Radix activation evaluate path and fails closed with `SelectorNotFoundError` if activation does not report `{ok: true}`; `click` and `JS_CLICK_VISIBLE_ENABLED` were not changed.
- CDP menu item selection now sends the pointer/mouse sequence before `target.click()` for `select`, while preserving the existing submenu hover/focus behavior.

## Gap-2 summary
- Draft sends now reload the learned `/c/<id>` tab after `wait_for_completion(...)` and before `capture_conversation(...)`, then wait for `domcontentloaded`; existing-conversation sends and scrape paths are not gated through this draft-only reload.
- The mock can model fresh-chat missing backend GETs with `requests_require_reload=True`, withholding request snapshots until `reload()` has occurred.

## New falsifiable tests
- `tests/test_selectors.py::test_real_model_picker_selector_uses_live_form_pill_not_legacy_composer_footer`: reverting `real.json` to the old `composer-footer` selector fails this.
- `tests/test_menus.py::test_open_radix_menu_uses_pointer_activation_evaluate_not_click`: reverting menu open to `channel.click` removes the evaluate call and increments `click`.
- `tests/test_cdp_channel.py::test_cdp_open_radix_trigger_dispatches_pointer_sequence_through_evaluate_key`: removing the CDP dispatch branch or pointer sequence fails the JS/token assertions.
- `tests/test_cdp_channel.py::test_cdp_menu_select_label_dispatches_pointer_events_before_click`: reverting item selection to bare `target.click()` removes the pointer-event tokens.
- `tests/test_capture.py::test_mock_request_snapshots_can_require_reload_before_header_capture`: removing the mock reload gate makes pre-reload header acquisition succeed unexpectedly.
- `tests/test_session_draft_loop.py::test_draft_ask_reloads_learned_chat_before_capture_when_backend_get_requires_reload`: removing the draft reload leaves the gated mock without a backend GET, so capture cannot complete via `backend_api`.

## Acceptance
- Final command: `uv run pytest`
- Final result: `253 passed`
- Branch: `rewrite-v2`
- Stable branch rev observed: `779eb40b196e1a458a820248b2dbbca22411b0d3`; not moved by me.
- Staged files: none.
- Confirmations: no browser opened, no CDP touched, no send attempted, no `uv tool` used, no commit made, no push made.
