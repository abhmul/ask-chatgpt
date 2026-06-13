# T3-uc2char — Characterize the real UC2 bundle-response format (real CDP, human-paced, NO message cap)

You are a real-site worker. **You inherit NOTHING except this file.** REAL chatgpt.com via CDP attach. **There is NO message budget/cap** (the earlier ≤30/≤15 was a self-imposed fiction the operator REMOVED, commit af09077 — see docs/DECISIONS.md D-002 item 2). The ONLY rule on send volume: human-paced + attended, NEVER programmatically spam the site (small 1-3 s waits; no rapid-fire loops). Still log every send to the audit ledger for transparency. Obey the SAFETY BLOCK.

## Goal
UC2 (patch-bundle out → retrieve → apply) came back PARTIAL with `DownloadUnsupportedError` and the assistant text was NOT captured. Determine empirically WHAT ChatGPT actually emits when asked for a patch bundle, so the D-001 bundle-channel revision recommendation is evidence-backed (not just reasoned). The hypothesis: an LLM cannot emit a byte-exact base64-encoded zip with a correct SHA-256/byte-count, so the fenced `BEGIN_PATCH_BUNDLE ... BASE64URL ... END_PATCH_BUNDLE` format is not produced; GPT instead emits a unified diff / code block / prose. CONFIRM what it really does.

## ⛔ SAFETY BLOCK (you inherit nothing)
- Real channel = CDP attach via the PUBLIC tool: `ask_chatgpt(..., channel="cdp", cdp_endpoint="http://127.0.0.1:9222")`. NEVER launch a browser; NO stealth; the driver opens its OWN tab and detaches without quitting; NEVER touch/navigate/close operator tabs; NEVER quit the browser. login/logout never automated; on `ChallengePresentError` run the challenge-pause (stop, log `HUMAN-ACTION-NEEDED`, poll read-only ≤10 min, else PARTIAL).
- Synthetic data only. NO account identifiers, credentials, cookies, tokens, or real conversation ids in any artifact; URLs as path-shape only (`/c/<redacted>`). Write only under `/home/abhmul/dev/ask-chatgpt` (+ tmp/). NEVER `git push`/`git commit`.
- Log each send BEFORE sending: `printf '%s\tT3uc2char\t%s\t%s\n' "$(date -Iseconds)" "<purpose>" "<conv-shape>" >> tmp/real-audit-20260612T194143/messages.log`.

## Steps (human-paced; 1-3 sends)
1. Preflight: `uv sync --all-groups`; CDP reachable (`urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5)`).
2. Send (plain, no files) via `ask_chatgpt(prompt, session_identifier="m006-uc2char", channel="cdp", cdp_endpoint="http://127.0.0.1:9222", timeout_s=120)` a prompt that asks GPT to return a tiny patch bundle for a synthetic one-line change (`favorite_color = "red"` → `"blue"` in `example.txt`) in the EXACT fenced format: a code block containing `BEGIN_PATCH_BUNDLE`, `MANIFEST_JSON {...}`, `ZIP_BYTE_COUNT <n>`, `ZIP_SHA256 <hex>`, `BASE64URL <...>`, `END_PATCH_BUNDLE`. Capture the FULL returned text to `tmp/real-accept-<ts>/uc2char/response1.txt`.
3. Assess the captured response (record in the report, NO account data): does it contain the `BEGIN_PATCH_BUNDLE`/`END_PATCH_BUNDLE` markers? a `BASE64URL` line that is valid base64url and decodes to a valid zip whose SHA-256 matches the declared `ZIP_SHA256` and byte count? OR is it a unified diff / fenced code block of file contents / prose explanation / refusal? Quote only SHORT synthetic-relevant snippets (e.g. the marker lines, the first ~40 chars of any base64), never private data.
4. (Optional, if useful + still human-paced) one follow-up send asking specifically for a unified diff, to confirm GPT CAN produce a deterministic text-native edit format — evidence for the recommended UC2 channel revision.
5. Detach (the driver does this). Tab-hygiene preserved.

## Output → `orchestration/reports/M-006/T3-uc2char.md` (cap ~120 lines)
`START_TIMESTAMP:`/`END_TIMESTAMP:`; `MESSAGES_USED: <n>`; the characterization verdict: what format ChatGPT actually emits for a patch-bundle request, whether the fenced base64-zip format is produced (expected: NO — base64/SHA not byte-exact), and whether a text-native format (unified diff) is viable. This is EVIDENCE for the D-001 UC2-channel revision. Last line: `T3-uc2char-STATUS: DONE` (or PARTIAL/BLOCKED).
