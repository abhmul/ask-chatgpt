Status: PASS

# M7b-T4-L2 correctness + falsifiability audit

Overall verdict: PASS — both M7b gap fixes are correct in source, the offline suite is green, the required broken-code probes fail for the right reasons, and I found no blocking false-green in the manager-authored mock corrections.

## 1. Offline suite green

Verdict: PASS.

Evidence: `uv run pytest -q -p no:cacheprovider` passed twice after probe reverts. Initial authoritative run: `254 passed in 1.01s`. Final post-probe run: `254 passed in 0.99s`.

## 2. Falsifiability — gap-2 draft reload before capture

Verdict: PASS; failed when broken.

Probe: temporarily changed `src/ask_chatgpt/session.py` draft capture reload guard from `if draft:` to `if draft and False:`.

Command: `uv run pytest -q -p no:cacheprovider tests/test_session_draft_loop.py::test_draft_ask_reloads_learned_chat_before_capture_when_backend_get_requires_reload`.

Observed failure: `1 failed`; mock first raised `TimeoutError: mock request requires reload before capture`, then `BackendAuthUnavailableError: BACKEND_AUTH_UNAVAILABLE: required backend request headers were not observed`, then `HumanActionNeededError: HUMAN-ACTION-NEEDED: clipboard fallback requires explicit permission` with `backend_reason=BACKEND_AUTH_UNAVAILABLE`.

Reverted: yes; `git diff -- src/ask_chatgpt/session.py` is empty.

## 3. Falsifiability — gap-1 tools re-open after select

Verdict: PASS; failed when broken.

Probe: temporarily made `src/ask_chatgpt/menus.py::_reflected_tool_by_reopen` skip `open_radix_menu(tab, selectors["tools_button"])` and directly call `_reflected_tool`.

Command: `uv run pytest -q -p no:cacheprovider tests/test_menus.py`.

Observed failure: `1 failed, 13 passed`; `tests/test_menus.py::test_set_tools_reopens_tools_menu_after_select_when_menu_closes` failed with `ToolSelectionNotReflectedError: TOOL_SELECTION_NOT_REFLECTED: requested tool was selected but not reflected`.

Reverted: yes; `git diff -- src/ask_chatgpt/menus.py` is empty.

## 4. Falsifiability — gap-1 menu activation and selector

Verdict: PASS.

Activation guards: `tests/test_menus.py::test_open_radix_menu_uses_pointer_activation_evaluate_not_click` asserts `channel.method_counts.get("click", 0) == 0`, observes an `evaluate` call with `js_key == "ask_chatgpt_open_radix_trigger"`, and waits for the Radix portal. I also probed it by temporarily replacing `open_radix_menu` with `channel.click`; the test failed with `AssertionError: assert 1 == 0` for click count.

CDP pointer guards: `tests/test_cdp_channel.py::test_cdp_open_radix_trigger_dispatches_pointer_sequence_through_evaluate_key` and `::test_cdp_menu_select_label_dispatches_pointer_events_before_click` assert the evaluated JS contains `pointerdown`, `mousedown`, `pointerup`, `mouseup`, and `target.click()`. I temporarily changed the `pointerdown` token in each implementation; each corresponding test failed on the missing token. Both edits were reverted.

Selector guards: `tests/test_selectors.py::test_packaged_real_selector_map_loads_with_exact_required_keys` and `::test_real_model_picker_selector_uses_live_form_pill_not_legacy_composer_footer` lock `model_picker_trigger_candidates` to `form button[aria-haspopup="menu"]:not([data-testid])` and reject `composer-footer button[aria-haspopup="menu"]`. I temporarily reverted `src/ask_chatgpt/selectors/real.json` to the legacy selector; both selector tests failed. Reverted; `git diff -- src/ask_chatgpt/selectors/real.json src/ask_chatgpt/channels/cdp.py` is empty.

## 5. Adversarial false-green hunt

Verdict: PASS; no blocking false-green found.

Gap-2 mock correction: `MockChannel.reload` only sets `_reloaded_on_conversation` when the tab URL contains `/c/`; `MockChannel._current_url` updates the stored tab URL only after `ask_chatgpt_current_url` observes a `/c/<id>` URL. Therefore the pre-send idle reload on the new-chat root cannot satisfy `requests_require_reload`. The disabled-reload probe proves this: without the session draft reload after ID learning/completion, `wait_for_request` rejects capture and the test fails through `BACKEND_AUTH_UNAVAILABLE`/`HUMAN-ACTION-NEEDED`. Source placement in `session._run_send_turn` is also correct: the reload occurs after `wait_for_completion(...)` and immediately before `capture_conversation(...)`.

Gap-1 tools mock correction: `menu_closes_on_select=True` closes the active Radix portal after a select while retaining the checked state in the underlying menu options. Without the production re-open path, enumeration sees no active menu and reflection fails with `TOOL_SELECTION_NOT_REFLECTED`; with the re-open path, the checked state is observed. This matches the real bug shape closely enough for the guard, and the live tools report independently verifies the behavior.

Non-blocking modeling limits: the mock uses a substring `/c/` URL gate rather than parsing the path, and the gap-2 test primarily guards that a conversation-page reload happened before capture rather than independently proving reload ordering relative to completion. The current source proves the intended ordering, and the broken-code probe proves the test does not pass because of the pre-send root reload.

## 6. Real-leg evidence soundness

Verdict: PASS.

`team/evidence/reports/M7b-T3-verify.md` backs gap-2 closure: assistant role/id/status/partial are reported as `assistant` / concrete id / `complete` / `False`; capture source/fidelity are `backend_api` / `canonical`; checks include `assistant_turn_present`, `capture_backend_api`, `fidelity_canonical`, `transcript_user_and_assistant_present`, and `all_proven: true` with one user and one assistant turn.

The same M7b-T3 report backs the model portion of gap-1: initial label `Pro Extended`, target `High`, `select_model` returned `verified: true`, independent sustained confirmation ran for `12.003s` with last label `High`, and restore returned `Pro Extended` with `verified: true`. It does not claim tools closed there; it explicitly reports `GAP1_NOT_CLOSED` due to `TOOL_SELECTION_NOT_REFLECTED`.

`team/evidence/reports/M7b-T3c-tools-verify.md` backs the tools closure: zero sends, initial Web search unchecked, `set_tools(["Web search"])` returned `{"reflected": "Web search", "requested": "Web search", "verified": true}`, typed error `null`, and restore cleared the tool without error.

I found no real-leg claim among the requested items that is unsupported by emitted evidence.

## Probe revert / working tree confirmation

All probe edits were reverted. Source probe paths are byte-clean versus HEAD: `src/ask_chatgpt/session.py`, `src/ask_chatgpt/menus.py`, `src/ask_chatgpt/selectors/real.json`, and `src/ask_chatgpt/channels/cdp.py` all had empty `git diff` after probes.

Working tree note: the repository was already dirty before this audit (`issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, `human/`, this contract, and M7b-T4-L1 artifacts). I did not touch those. After this report is written, the only new path attributable to this audit is `team/evidence/reports/M7b-T4-L2-correctness.md`; tracked `git diff --stat` remains the pre-existing two-file diff.

Final `git status --short` observed after writing this report:

```text
 M issues/cdp-send-repro/controller.mjs
 M team/state/live-state.json
?? human/
?? team/contracts/M7b-T4-L1-leak-safety-audit.md
?? team/contracts/M7b-T4-L2-correctness-audit.md
?? team/evidence/reports/M7b-T4-L1-leak-safety.md
?? team/evidence/reports/M7b-T4-L2-correctness.md
```

Final `git diff --stat` observed after writing this report:

```text
 issues/cdp-send-repro/controller.mjs | 180 +++++++++++++++++++++++++++++------
 team/state/live-state.json           |  12 ++-
 2 files changed, 161 insertions(+), 31 deletions(-)
```
