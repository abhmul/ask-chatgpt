Status: DONE

# M7b-T1 live selector rediscovery

## CDP preflight
- Endpoint used: `/json/version` only (no `/json/list`).
- Browser version: `Chrome/149.0.7827.53`
- Protocol-Version: `1.3`
- WebSocket URL present: `True`
- Preflight ok/error: `True` / `None`

## Recommended real.json selectors
```json
{
  "model_picker_trigger_candidates": "form button[aria-haspopup=\"menu\"]:not([data-testid])",
  "tools_button": "button[data-testid=\"composer-plus-btn\"]"
}
```
- Current-model-label readout: trigger text itself (`same_as_trigger=True`).
- Tools menu shape: `direct`; `submenu_path`: `[]`.

## Evidence
### Model picker
- Selector: `form button[aria-haspopup="menu"]:not([data-testid])`
- `querySelectorAll(...).length`: `1`; visible count: `1`
- Opened portal: `True`; item count: `6`
- Sample menuitem labels: `['Instant', 'Medium', 'High', 'Extra High', 'Pro Extended']`
- Portal item dump (label/role/aria-checked): `[{"label": "Instant", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "Medium", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "High", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "Extra High", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "Pro Extended", "role": "menuitemradio", "aria_checked": "true", "checked": true, "disabled": false}, {"label": "GPT-5.5", "role": "menuitem", "aria_checked": null, "checked": null, "disabled": false}]`
- Label readout selector: `form button[aria-haspopup="menu"]:not([data-testid])`; count: `1`; sample text: `Pro Extended`
- Old offline model selector `composer-footer button[aria-haspopup="menu"]` count: `0`
- Error: `None`

### Tools button
- Selector: `button[data-testid="composer-plus-btn"]`
- `querySelectorAll(...).length`: `1`; visible count: `1`
- Opened portal: `True`; item count: `7`
- Sample menuitem labels: `['Add photos & files Ctrl U', 'Recent files', 'Create image', 'Deep research', 'Web search']`
- Portal item dump (label/role/aria-checked): `[{"label": "Add photos & files Ctrl U", "role": "menuitem", "aria_checked": null, "checked": null, "disabled": false}, {"label": "Recent files", "role": "menuitem", "aria_checked": null, "checked": null, "disabled": false}, {"label": "Create image", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "Deep research", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "Web search", "role": "menuitemradio", "aria_checked": "false", "checked": false, "disabled": false}, {"label": "More", "role": "menuitem", "aria_checked": null, "checked": null, "disabled": false}, {"label": "Projects", "role": "menuitem", "aria_checked": null, "checked": null, "disabled": false}]`
- Direct known tool labels observed: `['Create image', 'Deep research', 'Web search']`
- Old offline tools selector `button[data-testid="composer-plus-btn"]` count: `1`; visible count: `1`
- Error: `None`

## Button dumps
### Model-area structural candidates
```json
{
  "candidates": [
    {
      "aria_expanded": "false",
      "aria_haspopup": "menu",
      "aria_label": "Add files and more",
      "class_hint": "composer-btn",
      "data_testid": "composer-plus-btn",
      "disabled": false,
      "id": "composer-plus-btn",
      "in_composerish": false,
      "in_form": true,
      "index": 0,
      "innerText": "",
      "keep": true,
      "raw_index": 85,
      "role": null,
      "sort_distance": 266,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    },
    {
      "aria_expanded": "false",
      "aria_haspopup": "menu",
      "aria_label": null,
      "class_hint": "__composer-pill __composer-pill--neutral text-body-regular group/pill",
      "data_testid": null,
      "disabled": false,
      "id": "radix-_r_1p_",
      "in_composerish": false,
      "in_form": true,
      "index": 1,
      "innerText": "Pro Extended",
      "keep": true,
      "raw_index": 86,
      "role": null,
      "sort_distance": 319,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    },
    {
      "aria_expanded": null,
      "aria_haspopup": null,
      "aria_label": "Start dictation",
      "class_hint": "composer-btn h-9 min-h-9 w-9 min-w-9",
      "data_testid": null,
      "disabled": false,
      "id": null,
      "in_composerish": false,
      "in_form": true,
      "index": 2,
      "innerText": "",
      "keep": true,
      "raw_index": 87,
      "role": null,
      "sort_distance": 407,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    },
    {
      "aria_expanded": null,
      "aria_haspopup": null,
      "aria_label": "Start Voice",
      "class_hint": "composer-submit-button-color text-submit-btn-text keyboard-focused:focus-ring r…",
      "data_testid": null,
      "disabled": false,
      "id": null,
      "in_composerish": false,
      "in_form": true,
      "index": 3,
      "innerText": "",
      "keep": true,
      "raw_index": 88,
      "role": null,
      "sort_distance": 451,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    }
  ],
  "old_model_selector_count": 0,
  "old_tools_selector_count": 1,
  "scope": "model-before-open",
  "total_nearby": 4
}
```

### Tools-area structural candidates
```json
{
  "candidates": [
    {
      "aria_expanded": "false",
      "aria_haspopup": "menu",
      "aria_label": "Add files and more",
      "class_hint": "composer-btn",
      "data_testid": "composer-plus-btn",
      "disabled": false,
      "id": "composer-plus-btn",
      "in_composerish": false,
      "in_form": true,
      "index": 0,
      "innerText": "",
      "keep": true,
      "raw_index": 85,
      "role": null,
      "sort_distance": 266,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    },
    {
      "aria_expanded": "false",
      "aria_haspopup": "menu",
      "aria_label": null,
      "class_hint": "__composer-pill __composer-pill--neutral text-body-regular group/pill",
      "data_testid": null,
      "disabled": false,
      "id": "radix-_r_1p_",
      "in_composerish": false,
      "in_form": true,
      "index": 1,
      "innerText": "Pro Extended",
      "keep": true,
      "raw_index": 86,
      "role": null,
      "sort_distance": 319,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    },
    {
      "aria_expanded": null,
      "aria_haspopup": null,
      "aria_label": "Start dictation",
      "class_hint": "composer-btn h-9 min-h-9 w-9 min-w-9",
      "data_testid": null,
      "disabled": false,
      "id": null,
      "in_composerish": false,
      "in_form": true,
      "index": 2,
      "innerText": "",
      "keep": true,
      "raw_index": 87,
      "role": null,
      "sort_distance": 407,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    },
    {
      "aria_expanded": null,
      "aria_haspopup": null,
      "aria_label": "Start Voice",
      "class_hint": "composer-submit-button-color text-submit-btn-text keyboard-focused:focus-ring r…",
      "data_testid": null,
      "disabled": false,
      "id": null,
      "in_composerish": false,
      "in_form": true,
      "index": 3,
      "innerText": "",
      "keep": true,
      "raw_index": 88,
      "role": null,
      "sort_distance": 451,
      "tagName": "BUTTON",
      "title": null,
      "type": "button"
    }
  ],
  "old_model_selector_count": 0,
  "old_tools_selector_count": 1,
  "scope": "tools-before-open",
  "total_nearby": 4
}
```

## Confirmations
- Own-tab-only: `true` (driver uses `CdpChannel.open_tab(...)`; no `/json/list`; no page enumeration; only closes its lease).
- ZERO sends: `true` (`Session.ask/loop` and composer submit were never used; `successful_submissions` not applicable).
- Browser not quit: `true`; post-detach `/json/version` ok: `True`
- No auth/cookie/oai values logged: `true`
- No conversation content: `true`
- Branch start/end: `rewrite-v2` / `rewrite-v2`; rewrite-v2: `true`
- Stable rev start/end: `779eb40b196e1a458a820248b2dbbca22411b0d3` / `779eb40b196e1a458a820248b2dbbca22411b0d3`; unchanged: `true`
- Nothing staged: `true`; staged files: `[]`
- Protected paths not staged (`cache/`, `issues/cdp-send-repro/controller.mjs`, `human/`): `true`

## Blockers
- None.

## Signals
- Menu opening was verified with JS-dispatched pointer/mouse/click activation; no composer submission was made.
- Tools selector is unchanged from the offline map; live evidence says the selector is present and opens the Radix tools portal under pointer/mouse activation.
- Offline model selector misses because the live composer no longer has a `composer-footer` ancestor for the model trigger.
