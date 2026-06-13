# M-010 model picker discovery

## Verdict
- Verdict: `FOUND`
- Source leg: `T1c-model-capture`
- Ended at: `2026-06-13T18:37:53.567048-05:00`

## Selectors
- model_menu (trigger) selector: `form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])`
- model_menu .count(): `1`
- Robustness note: Chosen by ordered T1c selector test: data-testid candidates first, then unique composer attribute selector, then T1b structural fallback. This selector had count==1 and reproducibly opened the Radix menuitemradio model menu.
- model_option selector: `[data-radix-popper-content-wrapper] [role="menuitemradio"]`
- model_option count while open: `5`
- model_option_disabled selector: `[data-radix-popper-content-wrapper] [role="menuitemradio"][aria-disabled="true"], [data-radix-popper-content-wrapper] [role="menuitemradio"][data-disabled="true"], [data-radix-popper-content-wrapper] [role="menuitemradio"][disabled]`
- model_option_disabled count while open: `0`

## Matching rule for `model_settings={"model": "<label>"}`
Open model_menu, query model_option, skip model_option_disabled. For each option, prefer a nonempty value attribute; otherwise compare requested exactly to option.inner_text().strip(). In this capture inner_text().strip() is single-line and equals the first-line label for every top-level radio option.
- Observed `value` attrs null/empty for all options: `True`
- Observed `inner_text().strip()` single-line for all options: `True`

## Available model labels
- `Instant` — selectable; full inner_text=`Instant`; value=`n/a`
- `Medium` — selectable; full inner_text=`Medium`; value=`n/a`
- `High` — selectable; full inner_text=`High`; value=`n/a`
- `Extra High` — CURRENT/checked, selectable; full inner_text=`Extra High`; value=`n/a`
- `Pro Extended` — selectable; full inner_text=`Pro Extended`; value=`n/a`

## Two-switch labels
- Use these distinct selectable labels: `Extra High -> Instant`

## Menuitem/submenu note
- `GPT-5.5` — submenu=`True`, aria-haspopup=`menu`, data-state=`closed`; expansion probe: not attempted (not needed for top-level two-switch)

## Audit
- `audit()` rows appended to `orchestration/reports/M-010/real-audit-log.md` for T1c enumerate, selector-test, capture, Escape, and reproducibility actions.

## Selector-attempt evidence
```json
[
  {
    "basis": "attribute-no-testid",
    "count": 1,
    "opens_menuitemradio": true,
    "option_count_after_click": 5,
    "reject_reason": null,
    "selector": "form:has(#prompt-textarea) button[aria-haspopup=\"menu\"]:not([data-testid])"
  }
]
```
