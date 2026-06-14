# M-011 — Real-site per-message audit log (transparency, not rationing)

| # | timestamp (ISO) | leg | action | prompt-label (redacted) | observation | markers (stop/copy) | result |
|---|---|---|---|---|---|---|---|
| 0 | 2026-06-13T20:42:16.181617-05:00 | T1-tools-menu | closed-state enumerate after hydration wait | n/a | triggers=3,best=True | no prompt sent | OK |
| 1 | 2026-06-13T20:42:21.201894-05:00 | T1-tools-menu | open trigger + enumerate tool options | n/a | trigger_count=1,options=7,dr_found=True | Escape pending,no prompt sent | OK |
| 2 | 2026-06-13T20:42:24.045191-05:00 | T1-tools-menu | best-effort select Deep Research without submit | n/a | selector_count=1,armed=True | no prompt sent | OK |
| 3 | 2026-06-13T20:42:24.657225-05:00 | T1-tools-menu | Escape close + write report | n/a | trigger_count=1,options=7,dr_found=True | no prompt sent | FOUND |
| 4 | 2026-06-13T20:49:42.054687-05:00 | T2-deep-research | select-deep-research | n/a | option_selector_count=1 | no prompt sent yet | OK |
| 5 | 2026-06-13T20:49:46.211117-05:00 | T2-deep-research | submit-dr-prompt | lfp-vs-nmc-3bullets | sent via BrowserSession.send_prompt | recorder starting | OK |
| 6 | 2026-06-13T21:29:49.959901-05:00 | T2-deep-research | write final DR structured capture | lfp-vs-nmc-3bullets | status=PARTIAL-TIMEOUT,snapshots=300,report_present=False | stop=False,copy=True | PARTIAL-TIMEOUT |
