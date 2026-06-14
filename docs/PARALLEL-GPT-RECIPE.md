# Recipe: a Claude agent using GPT Pro via ask-chatgpt (single + parallel)

For an autonomous Claude agent (e.g. the Weak Simplex Conjecture driver) to query the operator's
signed-in **GPT Pro** account. The **stable** build is installed on PATH as `ask-chatgpt` (via `uv tool install` from the `stable` git ref); use it directly. (If it is not installed on a given machine, substitute `uv run --project /home/abhmul/dev/ask-chatgpt ask-chatgpt …` to run the dev tree.)

**PREREQUISITE (attended):** the operator's Chromium must be running, signed into chatgpt.com (Pro),
with `--remote-debugging-port=9222`. Verify: `curl -s http://127.0.0.1:9222/json/version`.
If it's down, calls raise `CDPUnreachableError` — only the operator can relaunch/sign in.

## (1) Single call — one GPT Pro chat
```bash
ask-chatgpt --channel cdp "YOUR PROMPT"
```
Prints GPT's reply text to stdout. Add `--session <id>` to keep talking in the SAME chat across calls.
Verified 2026-06-13: returned `PONG` in ~9.5s.

## (2) Parallel directions — N concurrent GPT Pro chats
Launch N calls concurrently; give EACH its own `ASK_CHATGPT_STATE_DIR` so their conversation
registries don't collide (the registry is a JSON file; distinct dirs = no write race):
```bash
ASK_CHATGPT_STATE_DIR=~/wsc-gpt/dir1 ask-chatgpt --channel cdp --session main "DIRECTION 1 ..." &
ASK_CHATGPT_STATE_DIR=~/wsc-gpt/dir2 ask-chatgpt --channel cdp --session main "DIRECTION 2 ..." &
ASK_CHATGPT_STATE_DIR=~/wsc-gpt/dir3 ask-chatgpt --channel cdp --session main "DIRECTION 3 ..." &
wait
```
Each direction keeps its own resumable conversation (`--session main` within its own state dir).
Verified 2026-06-13: 3 concurrent calls returned correct distinct answers (42 / blue / 99) in ~12s
(≈ one call's time — genuinely parallel, no cross-talk).

## Honest limits (read before overnight / high-volume use)
- **ATTENDED:** the Pro CDP browser must stay up the whole time. Logout → `LoginRequiredError`;
  Cloudflare challenge → `ChallengePresentError`. Treat ANY raised error as "back off / retry later,"
  NOT "hammer." Named errors fail closed; nothing is silently wrong.
- **CONCURRENCY:** smoke-proven at **3-way parallel only**. NOT stress-tested at high concurrency or
  sustained load. Keep parallelism MODEST (a handful at a time); the account's rate limits are the
  main unknown. Heavy/long GPT-Pro reasoning holds tabs open longer → more concurrent load.
- **MODEL:** uses whatever model the Pro UI has selected (your Pro model). `--model-settings '{"model":"Pro Extended"}'`
  picks a reasoning tier; base model-family selection is not wired.
- **One ChatGPT account** is shared across all parallel chats — the operator's account + quota.

Full API, error table, and caveats: `docs/USAGE.md`.
