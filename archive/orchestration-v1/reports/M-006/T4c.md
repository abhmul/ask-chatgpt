# M-006 T4c — independent verification of empirical findings and D-001 revisit

Scope honored: no real-site contact, no real legs re-run, no source edits; verification used the requested reports/artifacts only and redacts real conversation ids.

## 10 runbook unknowns vs T2 discovery

| # | Unknown | Verification | Evidence-backed vs deferred |
|---:|---|---|---|
| 1 | Zip upload size/type limits | PARTIAL/HONEST. A small synthetic zip was accepted and upload hooks were found; true max size/count/type limits were not measured. | Evidence-backed: `input[type="file"]`, file chip, 437-byte zip accepted, README/nested visibility later. Deferred: max bytes, first rejected size, file-count/MIME policy. |
| 2 | Response downloads | PARTIAL/HONEST. A download-labelled affordance was observed, but no Playwright `Download` event or verified zip bytes were observed. | Evidence-backed: `button[aria-label*="Download"]` candidate and T2 “Download event = no”. Deferred: filename/MIME/retention/integrity; not a real UC2 download channel. |
| 3 | Session pinning | PARTIAL with useful proof. URL shape `/c/<redacted>` is the real ref source; reopen-by-URL within a running session worked; DOM ref attr absent. | Evidence-backed: URL-derived ref and T3 continuity. Deferred: restart/archive/delete/simultaneous-tab behavior. |
| 4 | Model UI hooks | HONEST UNKNOWN/fail-closed. No safe stable model-menu/options were found. | Evidence-backed: empty model selectors in proposed map and expected `SelectorUnavailableError` on model probe. Deferred: labels, persistence, unavailable copy. |
| 5 | Copy/clipboard | PARTIAL. Copy button exists and can be targeted; clipboard content/fidelity was intentionally not read. | Evidence-backed: `button[data-testid="copy-turn-action-button"]`. Deferred: Markdown/code/citation fidelity, permission prompts, stale clipboard races. |
| 6 | Completion signal | ADEQUATELY ANSWERED for normal turns. Stop button plus completion/copy action or text-stability with stable wait is supported by T2/T3. | Evidence-backed: `stop-button`, copy action completion marker, UC1/UC3 no premature reads. Deferred: regenerate/retry/very-long virtualization. |
| 7 | File upload UI hooks | PARTIAL but strong for baseline upload. Upload input found; tiny zip accepted; README/catalog and nested paths visible to the model. | Evidence-backed: `input[type="file"]`, upload chip, synthetic bundle response. Deferred: progress/error states, large archives, parse lag. |
| 8 | Text-channel truncation | HONEST UNKNOWN for limits. No stress generation was performed. | Evidence-backed: only short/medium responses completed. Deferred: max fenced payload, truncation symptoms, marker reliability under stress. |
| 9 | Artifact/turn identity | PARTIAL/HONEST. Multiple artifacts/download affordances were observed, but turn scoping was not conclusively proven. | Evidence-backed: assistant turn selector and download affordance. Deferred: duplicate filename behavior, wrong-turn risk; downstream must scope latest turn/fail closed. |
| 10 | Operator UX/failure messaging | MOSTLY DEFERRED/HONEST. Login/rate-limit/model-unavailable/upload/download unsupported were not forced; not-found marker was not stable. | Evidence-backed: no login/challenge in T3-diag, empty fail-closed UX selectors. Deferred: exact visible copy and mappings for most failure states. |

Conclusion on unknowns: discovery.md answers every runbook item either with empirical evidence or an explicit deferred/unknown statement. The proposed selector map is consistent with that scope: core composer/send/assistant/completion/copy/upload hooks are evidence-backed; model/login/not-found/truncation/rate-limit/conversation-ref are intentionally empty or URL-derived/fail-closed.

## UC1–UC3 evidence consistency

| UC | Reported verdict | Verification |
|---|---|---|
| UC1 | PASS | Supported. Artifacts show call 1 returned `REAL-SITE-UC1-PASS <nonce>` and call 2 returned `REAL-SITE-UC1-CONT BANANA-<nonce>` using the same `/c/<redacted>` shape after tmp URL-derived registry repair. The model-selector probe failed closed before send. |
| UC2 | PARTIAL | Supported and honestly scoped. The required `--apply` and one `--dry-run` retry both exited 10 with `DownloadUnsupportedError: no eligible latest-turn download artifact and no fenced patch-bundle fallback were present`; the target file stayed unchanged. T3 explicitly says byte-exact fenced round-trip was `not_observed_no_fallback_block`, not failed checksum validation. |
| UC3 | PASS | Supported. CLI call 1 returned `REAL-SITE-UC3-PASS <nonce>` and call 2 returned `REAL-SITE-UC3-CONT CITRUS-<nonce>` with the same session after tmp URL-derived registry repair. |

T3 does not overclaim the UC2 retrieval path in its report: it records absence of both a retrievable download and a parseable fallback block, and does not claim a successful patch or a checksum mismatch.

## D-001 revisit assessment

DOM-primary text read remains correct for the real site on current evidence: UC1 and UC3 returned exact expected latest-turn text via `.markdown`, with no copy fallback needed and no wrong-turn/partial-read symptom observed.

Download-primary bundle return is not real enough for UC2: T2 observed an affordance but no Playwright `Download` event/bytes, and T3 found no eligible latest-turn download artifact. A labelled button is not sufficient evidence of an automatable zip channel.

Fenced base64 zip fallback is not a real-site bundle strategy as implemented. The direct empirical result is “no `BEGIN_PATCH_BUNDLE` block,” not “bad SHA.” The broader D-001 revisit is nevertheless sound as a design finding: an LLM text response should not be relied on to synthesize deterministic ZIP bytes, base64url-encode them, and provide matching SHA-256/byte counts for unattended file writes. That requirement needs a deterministic producer, not probabilistic prose generation.

Explicit recommendation: keep D-001 DOM-primary text reading for real-site text responses; revise the UC2 bundle return channel for real use. Either implement a true downloadable/artifact integration that Playwright can capture and validate, or replace the fallback with a text-native deterministic edit format (for example unified diff or structured JSON edit operations) validated and applied by the local tool. Retain fenced base64 zip parsing only for mock/precomputed deterministic producers unless a real deterministic file-generation channel is proven.

## GAP-15 registry-persistence finding

Confirmed real and well characterized. T3 artifacts show the registry stored a final `/c/<redacted>` URL while `conversation_ref` was empty after new-CDP-chat seeds; continuity passed only after tmp-only repair deriving the ref from the URL. The source mechanism matches the finding: new-chat open can return `""`, `send_prompt` may sample before the URL settles, and registry persistence later uses `session.active_conversation_ref or active_ref` without refreshing after completion even though `session.page.url` has settled. Production fix: refresh/read the active conversation ref from the final URL after completion and before registry `set()` for both text and bundle paths.

T4c-VERDICT: PASS
MESSAGES_USED: 0
T4c-STATUS: DONE
