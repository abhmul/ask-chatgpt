# M-008b — Real-site per-message audit log (transparency, not rationing)

**Rules.** Human-paced; NO message cap; never programmatic spam; small waits between sends. Every real GPT-facing send (and every read-only real navigation/observation) gets one redacted line below. NEVER record credentials, cookies, session tokens, profile contents, account identifiers, or literal `/c/<id>` (redact conversation refs to `/c/<redacted>`). On any Cloudflare/human-verification challenge or logout: STOP, write `HUMAN-ACTION-NEEDED`, poll READ-ONLY ~10min, never click through.

**CDP:** attach-only (`connect_over_cdp` to operator's signed-in browser at `127.0.0.1:9222`); `close()` = detach the tool's own tab, never quit the browser.

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
| 0 | 2026-06-13T11:26:00-05:00 | preflight | curl /json/version | n/a | CDP reachable: Chrome/149.0.7827.53 | n/a | PASS |
| 1 | 2026-06-13T11:57:30.258656-05:00 | T0-connectivity | open new conversation (no send) | n/a | ready_root+composer present | n/a | OK |
| 2 | 2026-06-13T11:58:01.667474-05:00 | T2 | send | short-ping | sent; prompt_chars=50 | stop:0/copy:0 | OK |
| 3 | 2026-06-13T11:58:11.275517-05:00 | T2 | observe-completion | short-ping | copy_appeared=True,gap=0.000s,stable=True,visible_no_hover=True | stop:0/copy:2 | returned |
| 4 | 2026-06-13T11:58:15.489686-05:00 | T2 | send | short-two | sent; prompt_chars=33 | stop:0/copy:2 | OK |
| 5 | 2026-06-13T11:58:24.543619-05:00 | T2 | observe-completion | short-two | copy_appeared=True,gap=0.000s,stable=True,visible_no_hover=True | stop:0/copy:4 | returned |
| 6 | 2026-06-13T11:58:29.060906-05:00 | T2 | send | medium-40 | sent; prompt_chars=83 | stop:0/copy:4 | OK |
| 7 | 2026-06-13T11:58:36.582580-05:00 | T2 | observe-completion | medium-40 | copy_appeared=True,gap=0.000s,stable=True,visible_no_hover=True | stop:0/copy:6 | returned |
| 8 | 2026-06-13T11:58:41.157900-05:00 | T2 | send | long-120 | sent; prompt_chars=84 | stop:0/copy:6 | OK |
| 9 | 2026-06-13T11:58:49.706521-05:00 | T2 | observe-completion | long-120 | copy_appeared=True,gap=0.000s,stable=True,visible_no_hover=True | stop:0/copy:5 | returned |
| 10 | 2026-06-13T12:10:00-05:00 | diagnostic | open new conversation (no send), read-only DOM probe | n/a | composer visible+enabled, element-at-center is own placeholder, dialogCount=0 (no overlay) | n/a | OK |
| 11 | 2026-06-13T12:12:00-05:00 | T3 | send (attempt) | truncation-elicit-180 | FAILED pre-send at composer.click (transient SPA race after new-chat); NO GPT message sent | n/a | composer-click-flake |
| 12 | 2026-06-13T12:16:00-05:00 | T3 | send + capture | truncation-elicit-180 | 180/180 ordered lines + 7287 bytes captured COMPLETE (no client clip); terminal sentinel __ELICIT_COMPLETE__ markdown-rendered to 'ELICIT_COMPLETE' (.markdown stripped the bold __) -> false CLIP_SUSPECT; body PROVEN complete | stop:0/copy:present | body-complete; sentinel-format fix queued |
| 13 | 2026-06-13T12:31:00-05:00 | T3 | send + capture (post-fix) | truncation-elicit-180 | markdown-inert sentinel ELICIT-COMPLETE-SENTINEL; verdict COMPLETE max_k=180 nbytes=7296 strict_exact_match=true; PASS_COMPLETE 36.26s | stop:0/copy:present | PROVEN (no client clip) |
| 14 | 2026-06-13T12:34:00-05:00 | T5-in-process run1 | plant + recall + control (3 sends) | plant(ACK)/recall(nonce-absent prompt)/control | plant OK; RECALL returned exact nonce (T5-recall.txt) -> semantic recall non-circular; CONTROL turn timed out (apparatus stall, ResponseTruncatedError) | stop/copy varies | recall PROVEN; control apparatus-stall |
| 15 | 2026-06-13T12:38:00-05:00 | T5-in-process run2 | plant + recall + control (3 sends) | plant/recall/control | plant OK; recall returned exact nonce; CONTROL (fresh conversation) LEAKED the planted nonce -> account cross-chat Memory ON, defeats fresh-convo control | stop/copy varies | FINDING: account-memory confounds control (honest fail) |
| 16 | 2026-06-13T12:53:14.305386-05:00 | T5-temp-A | send-plant | plant-nonce | sent; prompt_chars=97 | n/a | OK |
| 17 | 2026-06-13T12:53:27.170984-05:00 | T5-temp-A | observe-plant | plant-nonce | plant_reply= | n/a | OK |
| 18 | 2026-06-13T12:53:37.189023-05:00 | T5-temp-A | send-recall | recall-same-temp-chat | sent; prompt_chars=70 | n/a | OK |
| 19 | 2026-06-13T12:54:11.337353-05:00 | T5-temp-B | send-control | recall-fresh-temp-control | sent; prompt_chars=70 | n/a | OK |
| 20 | 2026-06-13T12:54:23.436074-05:00 | T5-temp | summary | temp-continuity | recall_ok=False,control_clean=True,recall_len=4,control_len=7 | n/a | RECALL_FAILED |
| 21 | 2026-06-13T12:58:24.319675-05:00 | T5-temp-A | send-plant | plant-nonce | sent; prompt_chars=97 | n/a | OK |
| 22 | 2026-06-13T12:58:29.168884-05:00 | T5-temp-A | observe-plant | plant-nonce | plant_reply=ACK | n/a | OK |
| 23 | 2026-06-13T12:58:39.230113-05:00 | T5-temp-A | send-recall | recall-same-temp-chat | sent; prompt_chars=70 | n/a | OK |
| 24 | 2026-06-13T12:59:19.337485-05:00 | T5-temp-B | send-control | recall-fresh-temp-control | sent; prompt_chars=70 | n/a | OK |
| 25 | 2026-06-13T12:59:31.105646-05:00 | T5-temp | summary | temp-continuity | recall_ok=True,control_clean=True,recall_len=44,control_len=7 | n/a | FALSIFIABLE_CONTINUITY_PROVEN |
| 26 | 2026-06-13T13:38:33.290671-05:00 | T5-temp-A | send-plant | plant-nonce | sent; prompt_chars=97 | n/a | OK |
| 27 | 2026-06-13T13:38:45.400661-05:00 | T5-temp-A | observe-plant | plant-nonce | plant_reply=ACK | n/a | OK |
| 28 | 2026-06-13T13:38:55.218554-05:00 | T5-temp-A | send-recall | recall-same-temp-chat | sent; prompt_chars=70 | n/a | OK |
| 29 | 2026-06-13T13:39:43.334963-05:00 | T5-temp-B | send-control | recall-fresh-temp-control | sent; prompt_chars=70 | n/a | OK |
| 30 | 2026-06-13T13:39:55.398926-05:00 | T5-temp | summary | temp-continuity | recall_ok=True,control_clean=True,recall_len=44,control_len=7 | n/a | FALSIFIABLE_CONTINUITY_PROVEN |
| 31 | 2026-06-13T13:40:33.289770-05:00 | T5-temp-A | send-plant | plant-nonce | sent; prompt_chars=97 | n/a | OK |
| 32 | 2026-06-13T13:40:45.303813-05:00 | T5-temp-A | observe-plant | plant-nonce | plant_reply=ACK | n/a | OK |
| 33 | 2026-06-13T13:40:56.213952-05:00 | T5-temp-A | send-recall | recall-same-temp-chat | sent; prompt_chars=70 | n/a | OK |
| 34 | 2026-06-13T13:41:40.380760-05:00 | T5-temp-B | send-control | recall-fresh-temp-control | sent; prompt_chars=70 | n/a | OK |
| 35 | 2026-06-13T13:41:54.307552-05:00 | T5-temp | summary | temp-continuity | recall_ok=True,control_clean=True,recall_len=44,control_len=7 | n/a | FALSIFIABLE_CONTINUITY_PROVEN |
| 36 | 2026-06-13T13:42:25.351403-05:00 | T5-temp-A | send-plant | plant-nonce | sent; prompt_chars=97 | n/a | OK |
| 37 | 2026-06-13T13:42:32.104040-05:00 | T5-temp-A | observe-plant | plant-nonce | plant_reply=ACK | n/a | OK |
| 38 | 2026-06-13T13:42:38.187885-05:00 | T5-temp-A | send-recall | recall-same-temp-chat | sent; prompt_chars=70 | n/a | OK |
| 39 | 2026-06-13T13:43:17.367095-05:00 | T5-temp-B | send-control | recall-fresh-temp-control | sent; prompt_chars=70 | n/a | OK |
| 40 | 2026-06-13T13:43:31.314547-05:00 | T5-temp | summary | temp-continuity | recall_ok=True,control_clean=True,recall_len=44,control_len=7 | n/a | FALSIFIABLE_CONTINUITY_PROVEN |
| 41 | 2026-06-13T14:01:48.222887-05:00 | T4-download-discovery | upload-bundle | tiny-one-file-bundle | uploaded basename=ask-chatgpt-bundle-b2a9a7c8ee96f841.zip,bytes=4419 | n/a | OK |
| 42 | 2026-06-13T14:01:58.287001-05:00 | T4-download-discovery | send-rewritten-bundle-prompt | download-discovery-task | sent; prompt_chars=2159; bundle=ask-chatgpt-bundle-b2a9a7c8ee96f841.zip | n/a | OK |
| 43 | 2026-06-13T14:02:33.488797-05:00 | T4-download-discovery | summary | download-discovery-task | found=True,kind=file_link,candidates=3,response_chars=25 | n/a | OK |
| 44 | 2026-06-13T14:15:00.187462-05:00 | T4-download-capture | upload-bundle | tiny-one-file-bundle | uploaded basename=ask-chatgpt-bundle-b2a9a7c8ee96f841.zip,bytes=4419 | n/a | OK |
| 45 | 2026-06-13T14:15:11.341549-05:00 | T4-download-capture | send-rewritten-bundle-prompt | download-capture-task | sent; prompt_chars=2159; bundle=ask-chatgpt-bundle-b2a9a7c8ee96f841.zip | n/a | OK |
| 46 | 2026-06-13T14:18:00.220842-05:00 | T4-download-capture | upload-bundle | tiny-one-file-bundle | uploaded basename=ask-chatgpt-bundle-b2a9a7c8ee96f841.zip,bytes=4419 | n/a | OK |
| 47 | 2026-06-13T14:18:10.290122-05:00 | T4-download-capture | send-rewritten-bundle-prompt | download-capture-task | sent; prompt_chars=2159; bundle=ask-chatgpt-bundle-b2a9a7c8ee96f841.zip | n/a | OK |
| 48 | 2026-06-13T14:18:42.720483-05:00 | T4-download-capture | summary | download-capture-task | captured=True,is_zip=True,nbytes=146,selector=latest assistant turn >> button:has-text("Download the patch bundle") | n/a | OK |
| -- | (pytest-based real sends below — not auto-logged by the probe; added by the manager for completeness/transparency) | | | | | | |
| 49 | 2026-06-13T13:08:00-05:00 | T3 pytest (post-E6, pre-E6b) | send truncation-elicit-180 | truncation-elicit-180 | wait_for_completion TIMED OUT — E6 over-scoping regression (copy button is OUTSIDE the turn element); fixed in E6b | n/a | timeout (E6 regression, fixed E6b) |
| 50 | 2026-06-13T13:33:00-05:00 | T3 pytest (post-E6b) | send truncation-elicit-180 | truncation-elicit-180 | PASS_COMPLETE max_k=180 nbytes=7296 strict_exact_match=true; 51.55s | stop:0/copy:present | PROVEN (post-hardening re-verify) |
| 51 | 2026-06-13T13:50:00-05:00 | T5 cross-process pytest run1 | plant(procA)+recall(procB)+control | plant/recall/control | plant OK; recall subprocess transient navigation failure opening stored conversation | n/a | nav-flake (transient) |
| 52 | 2026-06-13T13:55:00-05:00 | T5 cross-process pytest run2 | plant(procA)+recall(procB)+control | plant/recall/control | plant OK; recall (separate process) RETURNED the nonce -> xproc registry mechanism observed; control LEAKED nonce (account memory) | n/a | xproc recall observed; control leak (memory) |
