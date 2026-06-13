# M-009 T3 — Real model-selection: discovery findings + honest fail-closed outcome

**Verdict: FAIL-CLOSED (honest partial).** The real model picker is NOT reproducibly discoverable
or targetable as selectors-as-data in the current ChatGPT UI, so `model_menu` / `model_option` /
`model_option_disabled` remain EMPTY (the shipped fail-closed default — no real.json change). An
explicit model request fails closed with a named, actionable error before any send. The default
(no `model_settings`) path is unaffected and works (proven by T1/T2 real probes).

## What the mission required
1. Discover the model picker over CDP; capture verified `model_menu` trigger + per-model
   `model_option` selectors; populate real.json. **(Selectors-as-data; fail-closed if not mappable.)**
2. Wire `select_model` and prove the selection via UI STATE. **(Optional on top of #1.)**
3. If a requested model is absent, raise a named actionable error (fail-closed), never silently
   send on the wrong model. Document operator-plan-dependent availability.

## Discovery evidence (read-only CDP enumeration; operator's Pro account; new-chat state; 2026-06-13)
Probe: `scripts/m009_real_probe.py model-discovery` (privacy-safe — account/profile elements
excluded; only model-name-matching text emitted; the operator's identity is never written to any
artifact). Raw: `orchestration/reports/M-009/T3-model-discovery.json`.

- **Full `data-testid` inventory (37):** `create-new-chat-button`, `close-sidebar-button`,
  `sidebar-item-recall`, `apps-button`, `history-item-0..27-options`,
  `thread-header-right-actions[-container]`, `composer-plus-btn`, `upload-photos-input`,
  `blocking-initial-modals-done`. **No `model`/`switcher`/model-picker testid exists.**
- **Composer/header buttons:** `composer-plus-btn` (Add files/uploads, `aria-haspopup=menu`); an
  unlabeled `aria-haspopup=menu` button whose text is **"Extra High"** (a reasoning-EFFORT control,
  not a model selector); dictation/voice buttons. No model-name button with a menu popup.
- **Doc-wide model-name-text search:** the ONLY model-name text on the page is a single
  **non-clickable `<span>` reading "ChatGPT"** (a static label/logo — no testid, no role, no
  clickable/haspopup ancestor). Not a switcher.
- **`[aria-haspopup=menu]` elements (40):** all are sidebar/history/project/recents/account controls
  — none is a model picker.

Conclusion: the current ChatGPT build does not expose a model switcher that read-only CDP
enumeration can map to a stable selector (no testid, no model-name menu-popup button). It may be
gated behind a different interaction/build, or relocated; it is not targetable now. Per
"selectors-as-data, fail-closed if not mappable," `model_menu`/`model_option` stay EMPTY rather than
guess a brittle selector.

## Fail-closed behavior — VERIFIED end-to-end (real CDP)
`ask_chatgpt('Reply with just: ok', model_settings={'model': 'gpt-5-nonexistent-probe'},
channel='cdp')` →
```
SelectorUnavailableError: selector 'model_menu' unavailable for channel 'real'
```
Raised inside `select_model` (driver.py:236 `_require_present("model_menu")`) **before** `send_prompt`
— so NO prompt is sent and the tool NEVER silently proceeds on the wrong model. This is a named,
actionable error (operator action: update the selector map / model selection unsupported). The
mission's hard requirement (#3) is satisfied.

Note: when the menu itself is unmapped the error is `SelectorUnavailableError` (selector-map gap),
which is distinct from `ModelUnavailableError` (menu present but the requested model absent from it).
Both are named, fail-closed, and safe; the latter path is exercised by the existing mock tests.

## Honest scope / availability
Which models a real account exposes is operator-plan-dependent and was NOT enumerable here because
the picker was not discoverable. Observed adjacent control: a reasoning-effort menu ("Extra High") in
the composer — a different axis from model identity and out of scope for `model_settings['model']`.

## Recommendation (follow-up mission)
Real model selection should be revisited when the model switcher is reachable: capture the trigger +
per-model option selectors over CDP (likely after opening an in-conversation header control), then —
because the real picker is a render-on-open dropdown — `select_model` will also need to OPEN the menu
BEFORE enumerating `model_option` (today it calls `_find_model_option` before `menu.click()`, which
suits the mock's always-in-DOM `<select>` but not a real Radix dropdown). Until then, fail-closed is
the correct, safe behavior and the default no-model path is fully functional.
