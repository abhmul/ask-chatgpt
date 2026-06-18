# T3 (CDP) — Real-site UC1–3 acceptance over CDP attach (ONE real worker, HARD ≤15 messages)

You are a fresh real-site worker. **You inherit NOTHING except this file.** This is a REAL chatgpt.com leg, authorized ONLY under D-002 (+ CDP addendum) within a hard message budget. Read the SAFETY BLOCK first and obey it literally. The repo destructive-guard hook blocks command text containing certain destructive substrings — if you ever need to revert tracked files use `git stash push -u`, never `git checkout`/`git clean`. NEVER `git commit` in this leg (the manager commits).

## ⛔ SAFETY BLOCK — obey exactly (you inherit nothing; this is the whole law)

- **Real channel = CDP ATTACH via the tool's own driver, never launch.** You run the PUBLIC tool (`ask_chatgpt(..., channel="cdp", cdp_endpoint="http://127.0.0.1:9222")` and `ask-chatgpt --channel cdp --cdp-endpoint http://127.0.0.1:9222 ...`). The driver attaches to the operator's already-running signed-in Chromium over CDP, opens its OWN new tab for each call, and detaches (does NOT quit the browser) when done. You NEVER launch a browser, NEVER pass a profile path, NEVER write raw Playwright. (Cloudflare blocks Playwright-launched browsers; that is why this is CDP-attach.)
- **NO stealth / anti-detection of ANY kind.** Forbidden. If a challenge appears, a HUMAN clears it (protocol below).
- **NEVER touch/navigate/close the operator's pre-existing tabs; NEVER quit the browser.** The driver guarantees new-tab + detach-not-quit (verified in T1b/T2). You must not add any browser manipulation outside the tool. After the leg, the operator's browser must still be running with their tabs intact.
- **LOGIN/LOGOUT NEVER automated.** If the tool raises `LoginRequiredError` → STOP, report BLOCKED `logged out` (operator action: sign in, resume T3). NEVER touch a login form, NEVER sign out.
- **Cloudflare/human-verification challenge → challenge-pause protocol.** If the tool raises `ChallengePresentError` (token `CHALLENGE_PRESENT`) at ANY point: STOP, log `HUMAN-ACTION-NEEDED: clear the Cloudflare/human-verification challenge in the browser`, poll READ-ONLY (re-attempt the SAME call after a wait, or just wait) up to 10 minutes for the human to clear it; cleared → continue; not cleared → end the leg PARTIAL with that state. NEVER interact with the challenge programmatically.
- NEVER read, copy, store, print, screenshot, commit, or log: credentials, cookies, session tokens, auth headers, local storage, or browser-profile contents.
- **NO account identifiers anywhere** (email, display name, org/workspace, real conversation titles/refs). Record conversation URLs only as SHAPE (`/c/<redacted-uuid>`), never the real id. The session registry under `ASK_CHATGPT_STATE_DIR` may contain real conversation refs — keep it under `tmp/`, NEVER commit it, NEVER paste its contents into the report.
- Use ONLY disposable chats and SYNTHETIC data (tiny dummy text/zip, harmless prompts). Never upload private source, the repo, the archive, or anything real.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Raw artifacts go under `tmp/real-accept-<ts>/`. NEVER `git push`. NEVER `git commit`.
- ONE real worker only (you). Human-paced (the tool's `timeout_s` + small waits). Never two real sessions at once.

## Message budget — HARD CAP ≤ 15 prompt-sends (this leg); mission already used 7/30, so ≤ this cap AND never exceed 30 total

A "message" = one prompt actually SENT to ChatGPT (a real `ask_chatgpt()`/CLI invocation that submits a prompt). A call that fails BEFORE sending (e.g. `select_model` raising on an unmapped model menu, or a preflight error) is 0 messages. **BEFORE each call that will send**, append ONE line to the ledger, THEN run the call:
`printf '%s\tT3\t%s\t%s\n' "$(date -Iseconds)" "<one-word-purpose>" "<conv-shape e.g. /c/redacted>" >> tmp/real-audit-20260612T194143/messages.log`
- APPEND only; never truncate. The 30-message mission cap spans ALL legs/ledgers; 7 are already used. **Target ~6–8 sends total** (UC1: 2 continuity; UC2: 1–2; UC3: 2). If you reach 15 T3 sends OR the running mission total would exceed 30, STOP sending, report PARTIAL with the count.

## Preflight (0 messages)
1. `uv sync --all-groups`.
2. CDP reachable: `urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5)` → JSON. Else BLOCKED `CDP_UNREACHABLE` (operator: `chromium --profile-directory='Profile 1' --remote-debugging-port=9222`).
3. `uv run ask-chatgpt --help` shows `--channel` (now includes `cdp`) and `--cdp-endpoint`. Confirm `real.json` is populated (it is, from T2/T2b/T2c).
4. Scratch: `TS=$(date +%Y%m%dT%H%M%S); A=tmp/real-accept-$TS; mkdir -p $A/state $A/uc2/root $A/uc3`; `export ASK_CHATGPT_STATE_DIR="$PWD/$A/state"`.

## UC1 — `ask_chatgpt()` text + continuity (+ a model fail-closed probe). Python via `uv run python`.
Run a script that calls the PUBLIC api with `channel="cdp", cdp_endpoint="http://127.0.0.1:9222"`:
1. **Call 1 (continuity seed, 1 msg — LOG FIRST):** `ask_chatgpt("Real-site UC1. Remember this codeword for later: BANANA-<nonce>. Reply with exactly: REAL-SITE-UC1-PASS <nonce>", session_identifier="m006-uc1", channel="cdp", cdp_endpoint=CDP, timeout_s=90)`. Assert the returned text contains `REAL-SITE-UC1-PASS <nonce>`.
2. **Call 2 (continuity proof, 1 msg — LOG FIRST):** SAME `session_identifier="m006-uc1"`: `ask_chatgpt("What codeword did I ask you to remember? Reply with exactly: REAL-SITE-UC1-CONT <the codeword>", session_identifier="m006-uc1", channel="cdp", cdp_endpoint=CDP, timeout_s=90)`. Assert the returned text contains `BANANA-<nonce>` (proves the SECOND call reopened the SAME conversation via the stored URL ref — true continuity, not a fresh chat). Also record that the stored registry ref/url shape was reused (same `/c/<redacted>`), WITHOUT printing the real ref.
3. **Model fail-closed probe (0 msgs expected):** `ask_chatgpt("noop", session_identifier="m006-uc1b", model_settings={"model":"gpt-4o"}, channel="cdp", cdp_endpoint=CDP, timeout_s=30)`. EXPECT it to raise `SelectorUnavailableError` or `ModelUnavailableError` (the model menu was not mapped in discovery → fail-closed) BEFORE sending. Record the exact named error. This demonstrates fail-closed model selection on the real tier; it is the honest outcome, NOT a failure of UC1. (If it unexpectedly sends, that counts as a message — log it first; but it should not.)

UC1 PASS = call 1 returned its nonce AND call 2 returned the codeword from call 1 (continuity). Record the model-probe named error as a finding.

## UC2 — bundle out → patch edit → retrieve → apply → diff. Via the CLI (`channel=cdp`).
Setup (0 msgs): `printf 'favorite_color = "red"\n' > $A/uc2/root/example.txt`.
**Apply (1 msg — LOG FIRST):**
```
uv run ask-chatgpt --channel cdp --cdp-endpoint http://127.0.0.1:9222 \
  --session m006-uc2 \
  --prompt 'Real-site UC2. You are editing a synthetic file. Change favorite_color from "red" to "blue" in example.txt. Return a patch bundle containing ONLY changed files, repo-root-relative forward-slash paths, no absolute paths, no .. traversal, no unchanged files. A downloadable .zip is NOT available here; use the EXACT fenced patch-bundle fallback required by the bundle protocol (BEGIN_PATCH_BUNDLE ... MANIFEST_JSON ... ZIP_BYTE_COUNT ... ZIP_SHA256 ... BASE64URL ... END_PATCH_BUNDLE).' \
  --files example.txt --root $A/uc2/root --apply \
  --out $A/uc2/assistant-apply.txt --timeout 150 | tee $A/uc2/apply-summary.json
grep -Fx 'favorite_color = "blue"' $A/uc2/root/example.txt && echo UC2_DIFF_OK
```
UC2 PASS = the command exits 0, the apply summary shows ONLY `example.txt`, and the scratch file becomes exactly `favorite_color = "blue"`. **Expect the fenced base64 fallback** (download_artifact is fail-closed; T2 found no Playwright Download event). If retrieval raises `PatchMalformedError`/`BundleIntegrityError`/`ResponseTruncatedError` (the fenced base64 may not round-trip byte-exact through the real markdown DOM — known GAP-3 risk), that is an HONEST record-only finding: capture the named error + the raw assistant text (`assistant-apply.txt`) and report UC2 as PARTIAL/record-only with the exact symptom (do NOT redesign mid-leg, do NOT broaden selectors). Optionally, if budget allows and apply fails, one `--dry-run` retry (1 msg) to capture the bundle text is acceptable.

## UC3 — same via the CLI, one prompt + a `--session` continuity rerun (`channel=cdp`).
**Call 1 (1 msg — LOG FIRST):**
```
NONCE3=UC3-$(date +%H%M%S)
uv run ask-chatgpt --channel cdp --cdp-endpoint http://127.0.0.1:9222 --session m006-uc3 \
  --prompt "Real-site UC3. Remember codeword CITRUS-$NONCE3. Reply with exactly: REAL-SITE-UC3-PASS $NONCE3" \
  --timeout 90 | tee $A/uc3/stdout1.txt
grep -F "REAL-SITE-UC3-PASS $NONCE3" $A/uc3/stdout1.txt && echo UC3_1_OK
```
**Call 2 (continuity, 1 msg — LOG FIRST):** SAME `--session m006-uc3`:
```
uv run ask-chatgpt --channel cdp --cdp-endpoint http://127.0.0.1:9222 --session m006-uc3 \
  --prompt "What codeword did I ask you to remember? Reply with exactly: REAL-SITE-UC3-CONT <codeword>" \
  --timeout 90 | tee $A/uc3/stdout2.txt
grep -F "CITRUS-$NONCE3" $A/uc3/stdout2.txt && echo UC3_CONT_OK
```
UC3 PASS = call 1 nonce present AND call 2 returns the codeword (CLI continuity via `--session`).

## Honest-failure (safe only; record-only) — nonexistent session
With budget remaining and ONLY if safe, do a 0–1 msg observation: point a NEW `session_identifier` at a bogus stored ref (or navigate the api to a random `/c/<uuid>` via a disposable session whose stored ref is a random uuid) and record what the tool does. NOTE: T2 found NO stable `conversation_not_found` marker and the real site may return a soft 200 (not a 404), so `SessionNotFoundError` may NOT fire cleanly — record the ACTUAL behavior as a finding (this informs whether `conversation_not_found` needs a real selector later). Do NOT spend more than 1 message here. NO logout test, NO rate-limit provocation.

## Record (do NOT redesign mid-leg) — D-001 / empirical findings for T4
- UC1 continuity worked via URL-derived conversation ref? (yes/no + evidence)
- UC2 retrieval path actually used: fenced fallback (expected) vs download — and did the fenced base64 round-trip byte-exact through the real `.markdown` DOM? (the key GAP-3 question)
- Completion signal reliability (copy-turn-action-button as completion_marker) — any premature/late completion?
- Model selection: fail-closed named error (expected) — record it.
- Nonexistent-session behavior on the real site.
- DOM-primary text fidelity vs the visible turn (any wrong-turn/partial?).

## Outputs
- Raw artifacts under `tmp/real-accept-<ts>/`: assistant outputs, apply/dry-run summaries, the scratch root, a copy of the T3 ledger lines. (NOT committed; may hold refs.)
- Report `orchestration/reports/M-006/T3.md` (cap ~250 lines): `START_TIMESTAMP:` + `ESTIMATE: T3 <min>m` first; `MESSAGES_USED: <n>` near top (must equal your T3 ledger lines); per-UC result (PASS/PARTIAL/BLOCKED) with anonymized evidence; the findings list above; `END_TIMESTAMP:` + last line `T3-STATUS: DONE` (all UC1–3 pass) / `PARTIAL` (some pass, some record-only) / `BLOCKED` (named precondition). State the EXACT resume action if PARTIAL/BLOCKED. NO account identifiers, NO real conversation ids, NO registry contents.

## Honest BLOCKED conditions (STOP, report, name the exact operator action)
`CDP_UNREACHABLE` (→ operator launches the CDP browser) · `logged out` / `LoginRequiredError` (→ operator signs in) · `CHALLENGE_NOT_CLEARED` (→ operator clears the challenge) — all "resume T3". On any BLOCKED, the driver has already detached safely; write partial findings; leave src/ and the suite untouched (you never edit them here).
