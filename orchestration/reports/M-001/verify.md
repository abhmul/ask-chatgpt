Verified `orchestration/reports/M-001/decision-memo.md` against `/home/abhmul/dev/ask-chatgpt/README.md` and the cited read-only archive files.

ESTIMATE: T3 60m

## CITATIONS

Opened the cited archive files directly under `/home/abhmul/Documents/weak-simplex-conjecture/`; all distinct cited files exist. Sampled/load-bearing ranges and findings:

- `control-plane/DESIGN.md:46`: events/SQLite reports-patches are canonical; transcripts, DOM, stdout, dashboard are not; supports the Level B/audit claims.
- `control-plane/DESIGN.md:146`: browser module row states Level B shell automation and never extracting mathematical/code DOM output; supports the Level B claim.
- `control-plane/DESIGN.md:871`: Phase-3 design states loopback-only automated work, OP-3 real runbook scope, and no credentials/cookies/session/profile contents in artifacts; supports safety claims.
- `control-plane/DESIGN.md:888-961`: D3 lists exactly the closed `ChatUIDriver` methods and forbidden assistant/text/transcript extraction tokens; supports memo §2 and §4.
- `control-plane/DESIGN.md:1018-1044`: D9 makes selector maps operator-versioned and external ChatGPT opt-in with selector map/profile; supports selector/UI-drift claims.
- `control-plane/DESIGN.md:1084-1086`: forbids cookies/profile contents/secret selectors in artifacts and defines adversarial DOM sentinel tripwires; supports credential and assistant-DOM risk claims.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md:7-9`: Level-B real browser adapter sends seeds and verifies completion from events, not assistant text; supports memo §2.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md:13`: operator-owned profile; no automated login or credential handling; supports credential/profile claim.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md:43-45`: user data dir is operator-owned logged-in profile; operator handles login/approval manually; supports credential/profile claim.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md:77`: stale selector map should stop at coarse health instead of guess-clicking; supports selector fragility claim.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md:126-131`: selector/model/unavailable cases degrade or escalate without broadening to assistant text; supports fail-closed selector claim.
- `control-plane/docs/runbooks/phase3-chatgpt-browser.md:134-136`: real ChatGPT browser half remains operator-verified; supports empirical-scope claim.
- `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:5-11`: connector runbook is manual, offline gate first, not chat-text canonical, no credential/token/profile recording; supports connector/canonical/safety claims.
- `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:66-76`: loopback local MCP, HTTPS/Secure MCP Tunnel requirements, auth/approval constraints, `cp_apply_patch` operator-local; supports account/auth/connector claims.
- `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:135-137`: explicitly verifies completion from orchestrator state, never chat text; supports canonical-state claim.
- `control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:207-217`: non-loopback refusal, tunnel/auth cautions, approval-scope warnings; supports adjacent auth/account-safety claim.
- `control-plane/docs/runbooks/mvp-demo.md:7-11`: real MVP judged from events/reports/patch rows/git/audit bundle, never transcript text; supports canonical-state claim.
- `control-plane/docs/runbooks/mvp-demo.md:111-142`: manager sequence, local diff inspection, local patch approval/application; supports predecessor structured patch/audit path.
- `control-plane/docs/runbooks/mvp-demo.md:144-167`: audit bundle and events/reports/patch artifacts are authoritative; supports predecessor patch artifacts/events, not UI downloads.
- `control-plane/src/control_plane/browser/driver.py:15-27`: forbidden source tokens list assistant/response/text/transcript extraction names; supports closed-surface claim.
- `control-plane/src/control_plane/browser/driver.py:97-105`: protocol exposes only open/select/seed/coarse-health/health/close methods; supports no copy/download/upload allowlist in predecessor driver.
- `control-plane/src/control_plane/browser/playwright_driver.py:41-78`: open/select path uses selectors and blocked results, not assistant reading; supports shell-automation claim.
- `control-plane/src/control_plane/browser/playwright_driver.py:117-128`: model selection degrades when stable selectors are absent; supports selector-map reuse and no guessing.
- `control-plane/src/control_plane/browser/playwright_driver.py:184-203`: composer fill/send seed path only; supports shell-action claim.
- `control-plane/src/control_plane/browser/playwright_driver.py:368-386`: locator helper maps selector-map entries to Playwright locators; supports selector infrastructure reuse.
- `control-plane/src/control_plane/browser/playwright_driver.py:418-426`: reads only `data-conversation-ref` from ready root; supports conversation-ref shell metadata claim.
- `control-plane/src/control_plane/browser/selectors.py:12-15`: selector kinds and required shell keys; supports selector-map schema claim.
- `control-plane/src/control_plane/browser/selectors.py:75-121`: validates selector maps and required keys; supports selector-map/data-driven claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:1-3`: mock intentionally renders adversarial assistant DOM and control endpoints do not return assistant messages; supports adversarial fixture claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:22-23`: loopback default host is `127.0.0.1`; supports local mock safety claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:238-251`: login wall, missing app, rate-limit states are rendered; supports reusable failure-state claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:262-273`: assistant sentinel messages are rendered into DOM; supports booby-trap claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:300-327`: mock serves ready root, chat list/items, model/connector controls, composer, send button; supports mock-fixture content claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:435-492`: control endpoints expose state/history/actions, not assistant text; supports withheld assistant-text claim.
- `control-plane/tests/fixtures/phase3_mock_chat.py:501-518`: mock server binds only loopback and reports loopback base URL; supports local mock safety claim.
- `control-plane/tests/fixtures/phase3_mock_selector_map.json:1-77`: fixture maps ready root, login marker, chat item, new chat, prompt, send, model, connector, rate-limit, rename/archive keys; supports selector/failure-state claim.
- `control-plane/VERIFICATION.md:5`: final verification says real ChatGPT connector/browser/MVP halves were operator-verified by design and not contacted by automation; supports empirical-scope claim.
- `control-plane/VERIFICATION.md:121-122`: DOM extraction prohibition and live sentinel tripwire were verified; supports zero sentinel leak/adversarial-DOM claim.
- `control-plane/VERIFICATION.md:126-130`: machine verification was loopback/mock/local; OP-1/OP-3/OP-4 are operator-gated; supports empirical-scope claim.
- `control-plane/VERIFICATION.md:307-308`: residual says the mock selector map is only a fixture and real ChatGPT DOM automation needs an operator-supplied real selector map; supports real-selector unknown/operator-data claim.
- `orchestration/handoffs/MISSION-004-handoff.json:36-47`: handoff describes the driver boundary, selector data, no assistant-read method, no guess-clicking, event watcher, loopback config, and adversarial mock; supports complexity/containment claim.

CITATIONS: PASS

## SPEC

README ground truth:

- `README.md:9` defines `ask_chatgpt(prompt, session_identifier, model_settings...) -> text`, persistent session continuity by identifier, model/options selection where UI allows, and returning assistant response text. Memo lines 6, 15, 74, 84 match this.
- `README.md:10-13` define bundle-out and patch-bundle-back, where the returned patch bundle contains only changed files and is retrieved/applied locally. Memo lines 6, 9-10, 47-52, 65-70, 77-78 match this.
- `README.md:14` requires a CLI entry point; memo line 6 includes CLI posture.
- `README.md:18-20` require automated acceptance only against a loopback local mock, operator-gated real-site halves, round-trip file test, and actionable honest failures. Memo lines 6, 93-100, 102-113 match this.
- `README.md:24-26` state Level B conflicts with `-> text`/patch retrieval, operator owns account/profile/credentials/quota and tool never touches credentials, and the product is library-first with CLI wrapper and no daemons/frameworks unless forced. Memo lines 6, 11, 74, 79, 84, 88 match this.

SPEC: PASS

## SAFETY

The recommendation does not require automated tests to contact any network service: memo lines 23, 74, 93, and 99 keep automated evidence/local fixture loopback-only and operator-gate real-site observations. It does not require reading/storing/logging credentials, cookies, session tokens, or browser-profile contents: memo lines 21, 74, 76, and 113 preserve no-credential/profile-read constraints. It recommends local repo/mock filesystem behavior only and does not require writing outside `/home/abhmul/dev/ask-chatgpt`; the archive was used read-only here. It does not silently reintroduce a forbidden predecessor assumption: the deliberate departure from “never extract assistant output” is explicitly tied to the new README requirement and bounded by selector scopes, checksums/end markers, mock adversarial tests, honest failures, and operator-gated real-site runbooks.

SAFETY: PASS

## COMPLETENESS

Required content is present:

- Archive Level B rationale with resolved citations: memo §2 lines 15-23.
- Candidate channels weighed: DOM extraction §3.1, copy/clipboard §3.2, file download §3.3, connector callback §3.4, fenced base64 zip §3.5.
- Recommended primary/fallback for text and patch-bundle retrieval: memo lines 7-10 and §4 lines 75-78.
- Rejected options with one-line reasons: memo §5 lines 84-89.
- Local mock-ChatGPT fixture requirements: memo §6 lines 93-100.
- Empirical unknowns include the four required items: zip upload limits line 104, file downloads line 105, session pinning line 106, model-selection UI hooks line 107.
- Length is 120 lines, within the requested ~400-line bound.
- Decision framing is recommendation-only: memo line 5 says the team lead decides and the decision is not made; no later section records it as already decided.

COMPLETENESS: PASS

## GROUNDING

The memo keeps evidence-strength labels honest. It marks predecessor anti-DOM evidence as strong for the predecessor audit/tripwire model but not a proof over live `chatgpt.com` (memo lines 17, 20, 23, 80). It does not assert real ChatGPT file-download support as proven: memo lines 9, 77, 78, and 105 keep downloads operator-gated/unknown. It does not assert copy/clipboard server invisibility or stability as proven: memo lines 41, 75, 108 keep those empirical. It does not claim archive proof of ToS/ban/detectability risk: memo line 22 explicitly says no resolved archive claim was found and limits evidence to adjacent auth/account policies. The §7 unknowns are not contradicted elsewhere.

GROUNDING: PASS

ACTUAL: T3 43m
END_TIMESTAMP: 2026-06-11T23:06:33-05:00
VERDICT: PASS
T3-STATUS: DONE
