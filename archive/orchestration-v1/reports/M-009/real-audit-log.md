# M-009 — Real-site per-message audit log (transparency, not rationing)

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
| 0 | 2026-06-13T15:47:24.483018-05:00 | T0-connectivity | open new conversation (no send) | n/a | ready_root+composer present | n/a | OK |
| 1 | 2026-06-13T15:47:53.477576-05:00 | T1-uc2 | upload-bundle | tiny-2key-bundle | uploaded basename=ask-chatgpt-bundle-65fd10ce9ea723ec.zip,bytes=4443 | n/a | OK |
| 2 | 2026-06-13T15:47:58.791164-05:00 | T1-uc2 | send-uc2-prompt | uc2-red-to-blue | sent; prompt_chars=2193 | n/a | OK |
| 3 | 2026-06-13T15:48:43.713556-05:00 | T1-uc2 | first-wait_for_completion | uc2-red-to-blue | returned | n/a | returned |
| 4 | 2026-06-13T15:49:03.719573-05:00 | T1-uc2 | retrieve_patch_bundle (PRODUCTION path) | uc2-red-to-blue | outcome=ResponseTruncatedError; completion marker did not appear before timeout | n/a | ResponseTruncatedError |
| 5 | 2026-06-13T16:12:06.208952-05:00 | T1-uc2 | upload-bundle | tiny-2key-bundle | uploaded basename=ask-chatgpt-bundle-65fd10ce9ea723ec.zip,bytes=4443 | n/a | OK |
| 6 | 2026-06-13T16:12:16.322393-05:00 | T1-uc2 | send-uc2-prompt | uc2-red-to-blue | sent; prompt_chars=2193 | n/a | OK |
| 7 | 2026-06-13T16:12:51.001536-05:00 | T1-uc2 | first-wait_for_completion | uc2-red-to-blue | returned | n/a | returned |
| 8 | 2026-06-13T16:12:54.107322-05:00 | T1-uc2 | retrieve_patch_bundle (PRODUCTION path) | uc2-red-to-blue | outcome=PatchMalformedError; download artifact metadata is missing data-source-turn-id | n/a | PatchMalformedError |
| 9 | 2026-06-13T16:14:16.504288-05:00 | T2-short | ask_chatgpt()->text (PRODUCTION) | short-ping | outcome=returned,len=4 | n/a | returned |
| 10 | 2026-06-13T16:14:43.331039-05:00 | T2-short | ask_chatgpt()->text (PRODUCTION) | short-hi | outcome=returned,len=2 | n/a | returned |
| 11 | 2026-06-13T16:15:07.972723-05:00 | T2-short | ask_chatgpt()->text (PRODUCTION) | short-num | outcome=returned,len=1 | n/a | returned |
| 12 | 2026-06-13T16:15:34.453934-05:00 | T2-short | ask_chatgpt()->text (PRODUCTION) | short-ok | outcome=returned,len=2 | n/a | returned |
| 13 | 2026-06-13T16:29:03.206155-05:00 | T1-uc2 | upload-bundle | tiny-2key-bundle | uploaded basename=ask-chatgpt-bundle-65fd10ce9ea723ec.zip,bytes=4443 | n/a | OK |
| 14 | 2026-06-13T16:29:13.266885-05:00 | T1-uc2 | send-uc2-prompt | uc2-red-to-blue | sent; prompt_chars=2193 | n/a | OK |
| 15 | 2026-06-13T16:29:47.565914-05:00 | T1-uc2 | first-wait_for_completion | uc2-red-to-blue | returned | n/a | returned |
| 16 | 2026-06-13T16:29:51.316711-05:00 | T1-uc2 | retrieve_patch_bundle (PRODUCTION path) | uc2-red-to-blue | outcome=retrieved;  | n/a | retrieved |
| 17 | 2026-06-13T16:32:00.141925-05:00 | T3-model | enumerate (menu closed, read-only) | n/a | triggers=0,menuitems_closed=0 | n/a | OK |
| 18 | 2026-06-13T16:32:00.142086-05:00 | T3-model | open menu + enumerate options + Escape (no select) | n/a | menuitems_open=0 | n/a | OK |
| 19 | 2026-06-13T16:32:48.157053-05:00 | T3-model | enumerate (menu closed, read-only) | n/a | triggers=0,menuitems_closed=0 | n/a | OK |
| 20 | 2026-06-13T16:32:48.158364-05:00 | T3-model | open menu + enumerate options + Escape (no select) | n/a | menuitems_open=0 | n/a | OK |
| 21 | 2026-06-13T16:34:56.142151-05:00 | T3-model | enumerate (menu closed, read-only) | n/a | triggers=0,menuitems_closed=0 | n/a | OK |
| 22 | 2026-06-13T16:34:56.142443-05:00 | T3-model | open menu + enumerate options + Escape (no select) | n/a | menuitems_open=0 | n/a | OK |
| 23 | 2026-06-13T16:36:36.151649-05:00 | T3-model | enumerate (menu closed, read-only) | n/a | triggers=0,menuitems_closed=0 | n/a | OK |
| 24 | 2026-06-13T16:36:36.152027-05:00 | T3-model | open menu + enumerate options + Escape (no select) | n/a | menuitems_open=0 | n/a | OK |
