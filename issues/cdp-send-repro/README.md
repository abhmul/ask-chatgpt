# CDP send/verify reference (for issue 2026-06-18-cdp-send-noop-returns-stale-response)

Working, direct-CDP reference for reliably sending a turn into an existing ChatGPT
conversation and **verifying it actually landed** — demonstrating the guard the
stable `ask-chatgpt` CLI lacks (see the issue for root cause).

## CDP endpoint

The operator runs Chromium with remote debugging on:

```
http://127.0.0.1:9222
```

(signed into chatgpt.com). The scripts attach to the EXISTING tab whose URL path is
the target conversation; they never open a new tab (new tabs hydrate the wrong/blank
model label).

## Files

- `status-probe.mjs` — read-only state probe (user/assistant counts, latest message
  id + length, `stopVisible`, model label). Run: `node status-probe.mjs`.
- `controller.mjs` — persistent keep-alive loop. Per cycle, when idle it **reloads the
  page** (clears SPA staleness / re-mounts a clean composer + model label), sends the
  prompt, **verifies a NEW user-turn `data-message-id` appeared**, then waits for the
  response to finish (stop-control-absent + text-stable). Resilient to transient DOM
  absences (missing composer, empty model label) — those are retried, not fatal; only
  a *contradicting* model label halts. Env knobs: `PUSH_URL`, `PUSH_PROMPT`,
  `REQUIRE_MODEL`, `CDP_ENDPOINT`.

## The key correctness move

```js
// after fill + send-button click — count success ONLY on a new user-turn id:
const newUser = after.latestUser.includes(prompt)
  && (after.latestUserId !== before.latestUserId || after.users > before.users);
if (!newUser) throw new Error('message did not appear after send');
```

The stable CLI returns the previous completed assistant turn without this check, so a
no-op submission reads as success.
