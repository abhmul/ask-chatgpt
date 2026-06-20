# M-010 — Real-site per-message audit log (transparency, not rationing)

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
| 0 | 2026-06-13T18:03:24.718848-05:00 | T1-model-discovery | closed-state enumerate after hydration wait | n/a | headers=6,triggers=1,best=True | n/a | OK |
| 1 | 2026-06-13T18:03:30.268101-05:00 | T1-model-discovery | Escape close + refindability report | n/a | menu_count=0,option_count=None,labels=0 | no option selected | HONEST-FAIL-CLOSED |
| 2 | 2026-06-13T18:05:04.732891-05:00 | T1-model-discovery | closed-state enumerate after hydration wait | n/a | headers=6,triggers=1,best=True | n/a | OK |
| 3 | 2026-06-13T18:05:07.118944-05:00 | T1-model-discovery | open trigger + enumerate portal options | n/a | options=0,available=0 | Escape pending | OK |
| 4 | 2026-06-13T18:05:07.692615-05:00 | T1-model-discovery | Escape close + refindability report | n/a | menu_count=1,option_count=0,labels=0 | no option selected | HONEST-FAIL-CLOSED |
| 5 | 2026-06-13T18:06:45.703356-05:00 | T1-model-discovery | closed-state enumerate after hydration wait | n/a | headers=6,triggers=1,best=False | n/a | OK |
| 6 | 2026-06-13T18:06:45.712504-05:00 | T1-model-discovery | choose trigger | n/a | no trigger candidate | n/a | HONEST-FAIL-CLOSED |
| 7 | 2026-06-13T18:07:56.179215-05:00 | T1-model-discovery | closed-state enumerate after hydration wait | n/a | headers=6,triggers=1,best=False | n/a | OK |
| 8 | 2026-06-13T18:07:56.188550-05:00 | T1-model-discovery | choose trigger | n/a | no trigger candidate | n/a | HONEST-FAIL-CLOSED |
| 9 | 2026-06-13T18:22:32.140987-05:00 | T1b-model-open-probe | open own tab conversation | n/a | open_or_create_conversation(None); no prompt sent | attach-only | OK |
| 10 | 2026-06-13T18:22:32.154576-05:00 | T1b-model-open-probe | enumerate home-initial | n/a | composer=4,header_left=0,candidates=4 | no prompt sent | OK |
| 11 | 2026-06-13T18:22:36.539872-05:00 | T1b-model-open-probe | click candidate home-initial#0 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 12 | 2026-06-13T18:22:39.566516-05:00 | T1b-model-open-probe | click candidate home-initial#1 | n/a | roots=2,options=6,model_like=0,labels=0 | Escape,no selection | not-model |
| 13 | 2026-06-13T18:22:42.638042-05:00 | T1b-model-open-probe | click candidate home-initial#2 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 14 | 2026-06-13T18:22:44.514246-05:00 | T1b-model-open-probe | click candidate home-initial#3 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 15 | 2026-06-13T18:22:47.124446-05:00 | T1b-model-open-probe | Step4a focus composer space-delete | n/a | no prompt sent | no send | OK |
| 16 | 2026-06-13T18:22:47.132165-05:00 | T1b-model-open-probe | enumerate home-after-composer-focus | n/a | composer=2,header_left=0,candidates=1 | no prompt sent | OK |
| 17 | 2026-06-13T18:22:50.496985-05:00 | T1b-model-open-probe | click candidate home-after-composer-focus#0 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 18 | 2026-06-13T18:22:55.110611-05:00 | T1b-model-open-probe | Step4b open most recent history conversation | n/a | thread loaded; URL redacted; message area not enumerated | no prompt sent | OK |
| 19 | 2026-06-13T18:22:55.128545-05:00 | T1b-model-open-probe | enumerate thread-recent-header-composer | n/a | composer=9,header_left=0,candidates=9 | no prompt sent | OK |
| 20 | 2026-06-13T18:22:58.532570-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#0 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 21 | 2026-06-13T18:23:01.518268-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#1 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 22 | 2026-06-13T18:23:03.531909-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#2 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 23 | 2026-06-13T18:23:06.530038-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#3 | n/a | roots=2,options=4,model_like=0,labels=0 | Escape,no selection | not-model |
| 24 | 2026-06-13T18:23:09.673122-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#4 | n/a | roots=2,options=4,model_like=1,labels=1 | Escape,no selection | not-model |
| 25 | 2026-06-13T18:23:14.246468-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#5 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | TimeoutError |
| 26 | 2026-06-13T18:23:15.900848-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#6 | n/a | roots=2,options=6,model_like=0,labels=0 | Escape,no selection | not-model |
| 27 | 2026-06-13T18:23:17.688926-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#7 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 28 | 2026-06-13T18:23:19.565167-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#8 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 29 | 2026-06-13T18:23:19.580295-05:00 | T1b-model-open-probe | write report + discovery verdict | n/a | home-initial: clicked=4 opened(option/model-like)=[0/0,6/0,0/0,0/0]; home-after-composer-focus: clicked=1 opened(option/model-like)=[0/0]; thread-recent-header-composer: clicked=9 opened(option/model-like)=[0/0,0/0,0/0,4/0,4/1,0/0,6/0,0/0,0/0] | no option selected | HONEST-FAIL-CLOSED |
| 30 | 2026-06-13T18:25:01.142024-05:00 | T1b-model-open-probe | open own tab conversation | n/a | open_or_create_conversation(None); no prompt sent | attach-only | OK |
| 31 | 2026-06-13T18:25:01.155217-05:00 | T1b-model-open-probe | enumerate home-initial | n/a | composer=3,header_left=0,candidates=3 | no prompt sent | OK |
| 32 | 2026-06-13T18:25:06.637127-05:00 | T1b-model-open-probe | click candidate home-initial#0 | n/a | roots=2,options=6,model_like=0,labels=0 | Escape,no selection | not-model |
| 33 | 2026-06-13T18:25:09.690330-05:00 | T1b-model-open-probe | click candidate home-initial#1 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 34 | 2026-06-13T18:25:12.677264-05:00 | T1b-model-open-probe | click candidate home-initial#2 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 35 | 2026-06-13T18:25:15.196265-05:00 | T1b-model-open-probe | Step4a focus composer space-delete | n/a | no prompt sent | no send | OK |
| 36 | 2026-06-13T18:25:15.228914-05:00 | T1b-model-open-probe | enumerate home-after-composer-focus | n/a | composer=2,header_left=0,candidates=1 | no prompt sent | OK |
| 37 | 2026-06-13T18:25:18.601935-05:00 | T1b-model-open-probe | click candidate home-after-composer-focus#0 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 38 | 2026-06-13T18:25:23.109170-05:00 | T1b-model-open-probe | Step4b open most recent history conversation | n/a | thread loaded; URL redacted; message area not enumerated | no prompt sent | OK |
| 39 | 2026-06-13T18:25:23.166346-05:00 | T1b-model-open-probe | enumerate thread-recent-header-composer | n/a | composer=3,header_left=0,candidates=3 | no prompt sent | OK |
| 40 | 2026-06-13T18:25:26.676833-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#0 | n/a | roots=2,options=6,model_like=0,labels=0 | Escape,no selection | not-model |
| 41 | 2026-06-13T18:25:29.675643-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#1 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 42 | 2026-06-13T18:25:32.572299-05:00 | T1b-model-open-probe | click candidate thread-recent-header-composer#2 | n/a | roots=0,options=0,model_like=0,labels=0 | Escape,no selection | not-model |
| 43 | 2026-06-13T18:25:32.586112-05:00 | T1b-model-open-probe | write report + discovery verdict | n/a | home-initial: clicked=3 opened(option/model-like)=[6/0,0/0,0/0]; home-after-composer-focus: clicked=1 opened(option/model-like)=[0/0]; thread-recent-header-composer: clicked=3 opened(option/model-like)=[6/0,0/0,0/0] | no option selected | HONEST-FAIL-CLOSED |
| 44 | 2026-06-13T18:37:04.143597-05:00 | T1c-model-capture | open own tab conversation | n/a | open_or_create_conversation(None); no prompt sent | attach-only | OK |
| 45 | 2026-06-13T18:37:04.148395-05:00 | T1c-model-capture | enumerate composer menu buttons | n/a | composer_menu_buttons=2 | model-gated text only | OK |
| 46 | 2026-06-13T18:37:07.592088-05:00 | T1c-model-capture | test trigger selector attribute-no-testid | n/a | count=1,opens=True,options=5 | Escape,no selection | FOUND |
| 47 | 2026-06-13T18:37:11.566411-05:00 | T1c-model-capture | capture model option labels | n/a | options=5,current=Extra High,selectable=5 | Escape,no selection | OK |
| 48 | 2026-06-13T18:37:15.573106-05:00 | T1c-model-capture | re-open selector and confirm reproducible capture | n/a | same_labels=True,second_options=5 | Escape,no selection | OK |
| 49 | 2026-06-13T18:37:15.575594-05:00 | T1c-model-capture | write T1c report + final discovery.md | n/a | selector_count=1,labels=5,current=Extra High | no prompt sent; no option selected | DONE |
| 50 | 2026-06-13T18:37:42.143839-05:00 | T1c-model-capture | open own tab conversation | n/a | open_or_create_conversation(None); no prompt sent | attach-only | OK |
| 51 | 2026-06-13T18:37:42.148270-05:00 | T1c-model-capture | enumerate composer menu buttons | n/a | composer_menu_buttons=2 | model-gated text only | OK |
| 52 | 2026-06-13T18:37:45.600970-05:00 | T1c-model-capture | test trigger selector attribute-no-testid | n/a | count=1,opens=True,options=5 | Escape,no selection | FOUND |
| 53 | 2026-06-13T18:37:49.572532-05:00 | T1c-model-capture | capture model option labels | n/a | options=5,current=Extra High,selectable=5 | Escape,no selection | OK |
| 54 | 2026-06-13T18:37:53.566967-05:00 | T1c-model-capture | re-open selector and confirm reproducible capture | n/a | same_labels=True,second_options=5 | Escape,no selection | OK |
| 55 | 2026-06-13T18:37:53.568292-05:00 | T1c-model-capture | write T1c report + final discovery.md | n/a | selector_count=1,labels=5,current=Extra High | no prompt sent; no option selected | DONE |
| 56 | 2026-06-13T19:08:41.158244-05:00 | model-switch-proof | open own tab conversation | n/a | open_or_create_conversation(None); no prompt sent | attach-only | OK |
| 57 | 2026-06-13T19:08:41.162079-05:00 | model-switch-proof | read initial trigger label | n/a | ORIG=Extra High | model trigger text only | OK |
| 58 | 2026-06-13T19:08:45.784061-05:00 | model-switch-proof | read selectable model option labels | n/a | selectable=['Instant', 'Medium', 'High', 'Extra High', 'Pro Extended'],targets=Instant->Medium | Escape,no selection | OK |
| 59 | 2026-06-13T19:08:49.756946-05:00 | model-switch-proof | Switch 1 via production BrowserSession.select_model | n/a | Extra High->Instant; target=Instant | no prompt sent | OK |
| 60 | 2026-06-13T19:08:51.742391-05:00 | model-switch-proof | Switch 2 via production BrowserSession.select_model | n/a | Instant->Medium; target=Medium | no prompt sent | OK |
| 61 | 2026-06-13T19:08:52.427905-05:00 | model-switch-proof | fail-closed bogus model via production select_model | n/a | exception=ModelUnavailableError,trigger_unchanged=True,no_send=True | Escape,no prompt sent | OK |
| 62 | 2026-06-13T19:08:54.717616-05:00 | model-switch-proof | restore original model selection | n/a | before=Medium,after=Extra High | no prompt sent | OK |
| 63 | 2026-06-13T19:09:19.407701-05:00 | model-switch-proof | ask_chatgpt(model_settings) production entrypoint | trivial-ok | outcome=returned,len=2 | one trivial send | returned |
