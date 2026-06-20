ESTIMATE: T1a 45m

# T1a archive-fidelity / risk lens

Scope: file-reading only in `/home/abhmul/Documents/weak-simplex-conjecture/`; I did not contact network services.

## 1. Exact Level B contract / rule

Actual definition: “The target automation level is Level B: browser automation may open/wake ChatGPT Pro chats and send seed prompts, but structured task transfer, reports, repository interaction, and state updates must happen through explicit local tools rather than copy/paste or DOM-scraped assistant output.” (`control-plane/README.md:7`, §Purpose)

Actual allowed actions: Level B allowed exactly seven default UI-shell actions: open/focus chatgpt.com with an operator-controlled persistent profile; create/select a chat; select configured Pro model only if a stable selector exists; attach/enable the project connector if needed; send a worker seed; wake manager with a seed; record coarse UI health. (`control-plane/README.md:153-161`, §Level B browser automation contract)

Actual forbidden behavior: “The browser adapter is not allowed to parse, summarize, or extract mathematical/code output from assistant messages. Completion is detected by orchestrator events such as `report_submitted`, `patch_proposed`, or `operator_input_requested`.” (`control-plane/README.md:163`, §Level B browser automation contract)

Same rule in design language: authoritative progress is SQLite events plus stored report/patch metadata; ChatGPT transcripts, browser DOM content, stdout logs, and dashboard display state are not canonical; completion is by events, never parsing assistant text. (`control-plane/DESIGN.md:46`, §Events, not transcripts, prove progress)

## 2. Risks claimed for forbidding DOM extraction, and evidence strength

1. Canonical-state/audit risk: DOM/chat text is not the system of record; if chat text and events disagree, events win. Evidence strength: strong as a stated architecture invariant and repeatedly implemented/tested for event causality, but not a measurement of real ChatGPT DOM behavior. (`control-plane/DESIGN.md:46`; `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:195`; `control-plane/VERIFICATION.md:128-130`)

2. Selector fragility / UI drift risk: real UI selectors are treated as operator-versioned data, no hardcoded real ChatGPT selectors; model selection happens only when stable selectors exist; stale selectors should stop with coarse health rather than guess-clicking. Evidence strength: source-level design plus mock/selector tests; real-site selector drift is anticipated, not empirically measured on chatgpt.com in the cited verification. (`control-plane/DESIGN.md:113`; `control-plane/DESIGN.md:1018-1044`; `control-plane/docs/runbooks/phase3-chatgpt-browser.md:77`; `control-plane/docs/runbooks/phase3-chatgpt-browser.md:131`; `control-plane/VERIFICATION.md:64`)

3. Scraper complexity / attack-surface risk: “Do not build a generic ChatGPT scraper” is a non-goal, and D3 deliberately makes assistant reading unrepresentable by an 8-method driver allowlist plus forbidden source tokens. Evidence strength: structural source audit and mock tests prove the shipped driver lacks response-reader methods; this is stronger than prose but still not a comparative measurement of a scraper implementation. (`control-plane/README.md:26`; `control-plane/DESIGN.md:961`; `control-plane/src/control_plane/browser/driver.py:18-27`; `control-plane/src/control_plane/browser/driver.py:97-105`; `control-plane/VERIFICATION.md:21`)

4. Assistant-DOM prompt-injection / adversarial-content risk: M-004 put sentinel strings inside the mock assistant DOM and required durable sinks not to contain them; screenshots/traces/videos are disallowed on green runs because they would capture the booby-trapped assistant DOM. Evidence strength: strong for loopback mock adversarial DOM and durable-sink scanning; not a proof over live chatgpt.com assistant DOM. (`control-plane/DESIGN.md:1086`; `orchestration/handoffs/MISSION-004-handoff.json:18`; `orchestration/handoffs/MISSION-004-handoff.json:61`; `control-plane/VERIFICATION.md:122`)

5. Credential/profile/account-safety risk: profile credentials, cookies, raw profile paths, session tokens, invitation codes, and seed bodies must not enter events/logs/reports; real login/profile handling remains operator-owned. Evidence strength: normative rule plus artifact scans in mock/offline verification; no evidence of automated real-site credential handling, by design. (`control-plane/DESIGN.md:871`; `control-plane/DESIGN.md:1084`; `control-plane/docs/runbooks/phase3-chatgpt-browser.md:13`; `control-plane/VERIFICATION.md:93`; `orchestration/handoffs/MISSION-004-handoff.json:138`)

6. Usage-limit / approval / auth-control risk: the spec forbids bypassing usage limits, auth controls, or approvals; OP-1 warns that connector setup depends on plan/workspace/admin permission and that unsafe public tunnel/auth shortcuts should stop the run. Evidence strength: hand-reasoned/runbook policy based partly on external docs captured in the runbook; not a measured ban/ToS result. (`control-plane/README.md:30`; `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:47`; `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:72`; `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:215`)

7. Ban/ToS/detectability: I found no archive claim that DOM extraction specifically causes bans, violates ToS, or is detectable by chatgpt.com anti-bot systems. The archive supports adjacent “do not bypass usage limits/authentication/approval” and “operator-owned profile/login” constraints, but not a measured or explicit ban/ToS rationale. (`control-plane/README.md:30`; `control-plane/docs/runbooks/phase3-chatgpt-browser.md:13`)

## 3. Empirically proven on real chatgpt.com vs designed/mocked

Machine-proven: full local tests, Phase 1 local acceptance, Phase 2 local MCP/stdio acceptance, Phase 3 loopback Playwright/mock browser acceptance with DOM sentinel checks, Phase 4 local multi-worker acceptance, Phase 5 toy/browser/patch/audit acceptance; this machine verification deliberately used loopback/mock/local artifacts and did not contact chatgpt.com/OpenAI. (`control-plane/VERIFICATION.md:128`, §4 Machine-verified vs operator-verified)

Operator-gated, not machine-proven by the archive: real ChatGPT connector/app setup (OP-1), real authenticated browser profile/model/app UI wake (OP-3), and real end-to-end MVP demo (OP-4) remain operator-gated to preserve zero automated ChatGPT contact/quota use. (`control-plane/VERIFICATION.md:130`, §4 Machine-verified vs operator-verified)

The OP-3 runbook is a procedure for the real `chatgpt.com` half: it says the automated half is loopback mock acceptance and that OP-3 plus OP-1 are the operator-verified halves that cannot be automated under the no-real-ChatGPT rule. (`control-plane/docs/runbooks/phase3-chatgpt-browser.md:7`, §Purpose & scope)

The OP-3 “remaining real authenticated ChatGPT browser trial” consists of headed profile, real Pro account/model selection, real app/connector UI, and operator-owned login; anything not proven by events/cpctl remains unverified. (`control-plane/docs/runbooks/phase3-chatgpt-browser.md:136`, §Which acceptance halves remain operator-verified)

OP-1 is likewise a manual runbook for real ChatGPT manager/worker chats using a custom MCP app/connector; it explicitly says the authoritative local gate is offline and that the runbook does not verify success from chat text. (`control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:7-11`, §Purpose & scope)

Therefore, per the archive I read, real chatgpt.com DOM extraction was not proven; real chatgpt.com browser opening/profile/model/connector behavior is documented as an operator-run trial, while the hard empirical DOM-extraction prohibition proof is against the loopback mock. (`control-plane/VERIFICATION.md:69`; `control-plane/VERIFICATION.md:103`; `control-plane/docs/runbooks/phase3-chatgpt-browser.md:136`)

## 4. Existing infra by candidate channel

Selector maps: `selectors.py` implements selector-map-as-data, with required keys `ready_root`, `new_chat_button`, `prompt_textbox`, `send_button`, loader/validator, URL classifier, safe template formatting, and no real ChatGPT selectors hardcoded. (`control-plane/src/control_plane/browser/selectors.py:15`; `control-plane/src/control_plane/browser/selectors.py:75`; `control-plane/src/control_plane/browser/selectors.py:86`; `control-plane/src/control_plane/browser/selectors.py:124`; `control-plane/src/control_plane/browser/selectors.py:159`)

Selector-map fixture: the mock map includes optional keys for login marker, chat item, model menu/option, connector button/option/missing marker, rate-limit banner, rename, and archive button; this is mock/fixture data, not a real chatgpt.com selector map. (`control-plane/tests/fixtures/phase3_mock_selector_map.json`, top-level `selectors`; `control-plane/QUICKSTART.md:15`; `control-plane/VERIFICATION.md:308`)

ChatUIDriver allowlist: the low-level driver exposes exactly `open_or_focus`, `new_or_select_chat`, `select_model_if_available`, `enable_connector_if_available`, `send_seed_prompt`, `read_coarse_health`, `health`, and `close`; none reads assistant responses/transcripts. (`control-plane/src/control_plane/browser/driver.py:97-105`; `control-plane/DESIGN.md:879-961`)

Playwright driver implementation: positive methods navigate/open, click/select chat/model/connector selectors, fill prompt textbox, click send, read coarse health markers, and read only `data-conversation-ref` from the ready root; no method copies assistant text. (`control-plane/src/control_plane/browser/playwright_driver.py:41`; `:63`; `:107`; `:136`; `:184`; `:208`; `:418`)

Seed-prompt builders: `seeds.py` has `PromptKind = worker_boot|worker_reconnect|manager_boot|manager_report_wake`, builders for each, redacted metadata (`prompt_template_id`, hash, char count, invitation mode/present), and a guard rejecting literal `worker_endpoint_id` in seed text. (`control-plane/src/control_plane/browser/seeds.py:10`; `:42`; `:53`; `:65`; `:77`; `:89`; `:118`)

Download / file-attachment handling: I found no browser driver/session allowlist method for downloads, file chooser/upload, or file attachments; the only “attach” in the Level B browser rule is app/connector enablement. Existing patch/diff/audit artifacts are local control-plane tools, not browser downloads from ChatGPT. (`control-plane/README.md:158`; `control-plane/src/control_plane/browser/driver.py:97-105`; `control-plane/src/control_plane/browser/playwright_driver.py:136-181`; `control-plane/docs/runbooks/mvp-demo.md:167`)

Clipboard / copy-button use: I found no browser allowlist method for clipboard or copy-button extraction; response-copy would violate the closed driver surface and forbidden assistant-output extraction rule. (`control-plane/src/control_plane/browser/driver.py:18-27`; `control-plane/src/control_plane/browser/driver.py:97-105`; `control-plane/README.md:163`)

Session recovery / continuity: `BrowserSessionController` supports start worker/manager, wake manager, reconnect endpoint, recover endpoint, apply watcher decisions, attach consumed endpoint, prepare/health, and stop; it mints server-side invitations and records redacted browser events. (`control-plane/src/control_plane/browser/session.py:171`; `:216`; `:258`; `:301`; `:363`; `:438`; `:574`; `:633`; `:673`; `:710`; `:801`; `:829`; `:864`; `:923`)

Watcher continuity: `OrchestratorWatcher.tick` reads `cp_get_status`, `cp_list_events`, and `cp_list_pending_reports`; manager wake triggers only on `report_submitted`, `task_completed`, or `operator_input_requested`; worker seeding is capacity-gated; backpressure becomes backoff/escalation, not DOM reading. (`control-plane/src/control_plane/browser/watcher.py:40`; `:92`; `:113`; `:189`; `:263`; `:320`; `:357`)

Recovery policy: nonrecoverable login/app/model/selector states escalate to operator; rate limits back off only; stale/chat-unavailable reconnects; page-load failure gets one `refresh_once` then escalation; backoff is bounded/capped. (`control-plane/src/control_plane/browser/recovery.py:22`; `:30`; `:56`; `:92`; `:94`; `:104`; `:114`; `:129`)

## 5. What M-004 sliced, and what blocked

M-004 objective/slice: implement Playwright/Chrome-profile automation for opening/waking manager and worker chats, selecting model/app, sending seed prompts, with all automated dev+verification against a local loopback mock; real chatgpt.com stayed operator-run. (`orchestration/handoffs/MISSION-004-handoff.json:11`)

Built slices: driver boundary, selectors, seed builders, session state machine, watcher, recovery, facade/events, config, dashboard/daemon wiring, loopback mock, acceptance tests/script, OP-3 runbook, and verification artifacts. (`orchestration/handoffs/MISSION-004-handoff.json:36-47`; `:71-76`)

Verification result: M-004 handoff reports all in-scope deliverables done, all seven Level B actions implemented/degraded, structural DOM prohibition by 8-method surface, event-only completion, green phase3 acceptance/full suite, and clean adversarial DOM anchor. (`orchestration/handoffs/MISSION-004-handoff.json:5`; `:17-19`; `:28-31`)

Blockers: handoff `blockers` array is empty. (`orchestration/handoffs/MISSION-004-handoff.json:82`)

Remaining operator actions: OP-3 real chatgpt.com Phase-3 browser acceptance and OP-1 real ChatGPT connector/app acceptance remained operator-run/nonblocking. (`orchestration/handoffs/MISSION-004-handoff.json:84-86`)

Follow-ups from M-004: R1 daemon/dashboard MVP entrypoint, R2 browser channel/executable selector, FU-A manager admin decisions over MCP, FU-B stronger bare-IP scan, FU-2 facade reads. (`orchestration/handoffs/MISSION-004-handoff.json:89-92`)

## Fidelity notes

- The new mission’s desired `ask_chatgpt(...)->text` response capture and patch-bundle retrieval are not supported by the Level B archive contract; Level B explicitly forbids assistant output extraction and uses MCP/event/report tools instead. (`control-plane/README.md:7`; `control-plane/README.md:163`)

- The archive’s anti-DOM evidence is strongest for “current control-plane does not extract mock assistant DOM into durable sinks,” not for “DOM extraction is impossible or unsafe on real chatgpt.com in general.” (`control-plane/VERIFICATION.md:122`; `control-plane/docs/runbooks/phase3-chatgpt-browser.md:136`)

- I found no archive support for a specific ToS/ban/detectability claim about DOM extraction; account/auth/approval safety is present, but ban-risk is not evidenced. (`control-plane/README.md:30`; `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:47`)

- Existing “patch bundle” infrastructure is local control-plane patch/audit export, not ChatGPT UI download capture. (`control-plane/docs/runbooks/mvp-demo.md:111`; `control-plane/docs/runbooks/mvp-demo.md:167`)

- Existing browser code has no clipboard/copy/download/file-attachment response-capture path; adding one would be new architecture, not reuse of Level B driver capabilities. (`control-plane/src/control_plane/browser/driver.py:97-105`)

ACTUAL: T1a 42m
END_TIMESTAMP: 2026-06-11T22:48:18-05:00
T1a-STATUS: DONE
