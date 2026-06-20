DONE

## A — upload affordance
- Confirmed composer file input selector: `form input[type="file"]` (driver found 3 page-wide `input[type="file"]` matches; only 1 in the composer form, id `upload-files`; `set_input_files` accepted it). W1 `input[type="file"]` is too broad/ambiguous on the live page.
- Attachment chip appeared after staging `/tmp/m9-upload.txt`; W1 `attachment_chip` union did match exactly 1 visible element via its remove-button branch.
- Real observed chip/remove selector: `button[aria-label="Remove file 1: m9-upload.txt"]`; stable selector recommendation from the live shape is `button[aria-label*="Remove file" i]` (no `composer-attachment`/attachment data-testid was present in this run).
- Reload discarded the staged file; composer was empty and no attachment was visible.

## B — GPT-5.5 family
- Current/original model label: `Pro Extended`.
- Top-level model options: `Instant` (`menuitemradio`, unchecked), `Medium` (`menuitemradio`, unchecked), `High` (`menuitemradio`, unchecked), `Extra High` (`menuitemradio`, unchecked), `Pro Extended` (`menuitemradio`, checked), `GPT-5.5` (`menuitem`, family submenu).
- GPT-5.5 submenu sub-radios: `GPT-5.5` (checked), `GPT-5.4`, `GPT-5.3`, `GPT-4.5 Leaving on June 26`, `o3`.
- `menus.select_model(..., "GPT-5.4")`: failed closed with `MODEL_SELECTION_NOT_REFLECTED` / requested model label absent; reflected label stayed `Pro Extended`.
- `menus.select_model(..., "GPT-5.5")`: failed closed with `MODEL_SELECTION_NOT_REFLECTED` / `label=GPT-5.5`, `role=menuitemradio`, `match_count=0`; reflected label stayed `Pro Extended`.
- Restore was not needed because neither selection changed the model.
- W3 fix needed: production family handling must open the top-level `GPT-5.5` `menuitem`, enumerate/click the second Radix portal’s `menuitemradio` entries, and support exact live labels `GPT-5.5`, `GPT-5.4`, `GPT-5.3`, `GPT-4.5 Leaving on June 26`, `o3`.

## C — Deep Research
- Present in tools menu as `Deep research` (`menuitemradio`, initially unchecked).
- `menus.set_tools(tab, sel, ["Deep research"])` did not verify: it raised `TOOL_SELECTION_NOT_REFLECTED` with selected label `Deep research`; re-opening the menu showed `Deep research` still unchecked.
- Deselect click was not needed because the tool was already off after the failed selection; final re-open confirmed `Deep research` unchecked. Code gap remains: do not assume DR works like Web search until its selection/reflection path is fixed or re-probed.

## Safety / teardown
- Send count: 0. The driver did not call submit/send or Enter-to-submit.
- Own-tab-only: driver opened one fresh `https://chatgpt.com/` tab through `CdpChannel.open_tab`; it did not call `/json/list` or enumerate pages, and it did not touch `6a316aa8` or any foreign tab.
- Browser alive post-detach: `/json/version` returned `Chrome/149.0.7827.53` after `channel.detach()`.

## Artifacts (+trust)
- Driver: `scripts/m9_w2_discover.py`.
- Stdout evidence: `team/evidence/reports/M9-W2-discover.txt`.
- Trust basis: all findings above are copied from the driver’s printed JSON events/final summary; no auth, cookie, `oai-*`, session, or conversation content is included.

## Blockers
- None for discovery. DR selection remains unverified and model family selection needs a code fix before relying on those paths.

## Recommended next
- Update the real selector map/file-input logic to prefer `form input[type="file"]` (or `input#upload-files`) over page-wide `input[type="file"]`.
- Tighten `attachment_chip` toward the observed remove-file selector branch.
- Implement W3 live-family submenu support for the exact GPT-5.5 sub-radio shape above.
- Investigate/fix Deep Research reflection separately before W4 real upload/DR smoke depends on it.
