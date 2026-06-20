# M5-T3 real-CDP read-only verification

## 1. Status

DONE.

## 2. Preflight

Step 0 preflight passed: `Browser=Chrome/149.0.7827.53`, `webSocketDebuggerUrl` present. Browser-alive-after-each-run: yes after smoke, yes after target, yes after optional header check.

## 3. Real capture verdict

Smoke end-to-end real backend-api capture: CONFIRMED. Exit code 0, `turn_count=7`, `assistant_markdown_total_length=10608`, `raw_mapping_byte_size=445813`, `mapping_node_count=87`. `raw_top_level_keys`: `title`, `create_time`, `update_time`, `moderation_results`, `plugin_ids`, `conversation_id`, `conversation_template_id`, `gizmo_id`, `gizmo_type`, `is_archived`, `is_starred`, `safe_urls`, `blocked_urls`, `default_model_slug`, `atlas_mode_enabled`, `conversation_origin`, `is_read_only`, `voice`, `async_status`, `disabled_tool_ids`, `is_temporary_chat`, `is_do_not_remember`, `memory_scope`, `context_scopes`, `sugar_item_id`, `sugar_item_visible`, `pinned_time`, `is_study_mode`, `owner`, `mapping`, `current_node`. This includes the M2-required backend shape names (`conversation_id`, `mapping`, `current_node`, `default_model_slug`, `async_status`).

Smoke artifacts were written under out-of-repo tmp `/tmp/tmp.6E6BBtBBTF`: `data/conversations/6a3483b3-9850-83ea-a9f7-3e269932e387/transcript.jsonl` exists, 1043879 bytes; `data/conversations/6a3483b3-9850-83ea-a9f7-3e269932e387/raw-mapping.json` exists, 445813 bytes; `smoke.md` exists, 10775 bytes. No artifact content is included here.

Target read-only scale/fidelity run: exit code 0, `turn_count=481`, `assistant_markdown_total_length=2031266`, `raw_mapping_byte_size=20190597`, `mapping_node_count=6124`. Artifacts were written under out-of-repo tmp `/tmp/tmp.icuINwFiEf`: `data/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/transcript.jsonl` exists, 5206584 bytes; `data/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/raw-mapping.json` exists, 20190597 bytes; `target.md` exists, 2038069 bytes.

## 4. Fidelity booleans

| run | `\\widehat` | `\\ne`/`\\neq` | `\\frac` | no literal `≠` replacement | no flattened frac observed |
|---|---:|---:|---:|---:|---:|
| smoke | true | false | true | true | true |
| target | true | true | true | true | true |

## 5. Memory

| run | after attach RSS / traced current / peak MiB | fetch-only RSS max / traced peak MiB | fetch-only deltas over attach | end-to-end RSS max / traced peak MiB |
|---|---:|---:|---:|---:|
| smoke | 66.980 / 19.337 / 19.477 | 80.605 / 26.451 | RSS +13.625, traced peak +6.974 | 98.887 / 37.666 |
| target | 76.195 / 23.857 / 24.097 | 92.031 / 32.753 | RSS +15.836, traced peak +8.656 | 353.949 / 253.823 |

Decision-rule verdict: keep the current whole-file `json.load` parse for M5/M6. Target fetch-only stayed within ≤128 MiB RSS and ≤32 MiB tracemalloc-peak over post-attach baseline; target end-to-end stayed within ≤512 MiB RSS and ≤256 MiB tracemalloc peak. Note: target end-to-end tracemalloc peak was close to the threshold (253.823 MiB vs 256 MiB).

Target bytes-per-mapping-node: `20190597 / 6124 = 3296.9623` bytes/node. Target wall-clock estimate was 60 s; actual wall-clock was 147 s, with measured fetch-only elapsed 130.509 s.

## 6. Completion vocabulary catalogue

Smoke: `async_status={}`; `message.status={"finished_successfully":82,"in_progress":4}`; `metadata.is_complete={"true":21}`; `metadata.is_finalizing={}`; `metadata.pro_progress={}`; `node.status={}`. In-progress message statuses were observed.

Target: `async_status={"int":1}`; `message.status={"finished_successfully":5064,"in_progress":1059}`; `metadata.is_complete={"true":360}`; `metadata.is_finalizing={"false":1,"true":93}`; `metadata.pro_progress={"float":94}`; `node.status={}`. In-progress states were observed. `/stream_status` was not probed.

## 7. Header mechanism

Optional production `CdpChannel` header-name check passed, exit code 0. Names/booleans only: `authorization=true`, `oai-client-build-number=true`, `oai-client-version=true`, `oai-device-id=true`, `oai-language=true`, `oai-session-id=true`, `x-openai-target-path=true`, `x-openai-target-route=true`. This verifies the production request snapshot contained all required header names; no header values were printed or persisted.

## 8. SAFETY AUDIT

Own-tab-only held: I used only `scripts/m5_capture_measure.py` plus the production `CdpChannel` optional check; I did not write raw Playwright, did not touch `context.pages`, and did not inspect foreign tabs. ZERO sends/new turns: no `ask`/`send`/`loop`/`create`, no typing, no Enter, no model/tool selection, no clicks. Browser left running: preflight passed after every run. No authorization/oai/cookie header values and no conversation content are in this report. Data-dir/out were out-of-repo tmp paths and were not staged. No git add/commit/push, no stable checkout/move, no `uv tool`.

## 9. Blockers and recommended next

Blockers: none. Recommended next: proceed to M6 target full scrape/attachment leg using the same safety constraints and out-of-repo evidence handling.
