# MISSION-006-RESUME — real-site discovery + acceptance (T2 onward; T1 done)

**You are the resumed manager for MISSION-006.** Read in order: (1) this file; (2) `orchestration/state/M-006-state.json`; (3) the original contract `orchestration/tasks/MISSION-006.md` (ALL its rules remain binding: D-002 bounds, SAFETY BLOCK, telemetry, watch recipe). The operator has confirmed (via the team lead) that the signed-in browser is CLOSED before this resume was dispatched.

## State at resume (re-verify, don't trust)

- T1 DONE + verified (commits `3693388`, `13b494c`): `real_site` marker + addopts deselection + `ASK_CHATGPT_REAL=1` double gate + guard test; default suite 132 passed / 1 deselected; `selector_maps/real.json` is a 5-key fail-closed scaffold (empty selectors). Do NOT redo T1.
- **Message budget: 30 remaining of 30** (audit log `tmp/real-audit-20260612T100518/messages.log` has zero data lines; START A NEW audit dir for this resume and carry the budget across both).
- T2 was BLOCKED: `~/.config/chromium` profile `Default` rendered chatgpt.com LOGGED OUT. The operator says they are signed in via "chromium" — the session likely lives in ANOTHER profile dir.
- Duplicate-manager precedent: on startup, check `M-006-state.json` for a `manager_pid` that is still alive (`kill -0`); if a live sibling exists, write a standdown note and exit cleanly (see `orchestration/state/M-006-DUPLICATE-STANDDOWN-3286529.json` for the pattern). Record YOUR pid in the state file.

## T2-pre: signed-in profile discovery (new sub-leg, ZERO messages)

Probe candidate profile dirs HEADED, one at a time, browser-rendered login state only (NEVER parse/read profile files; path is opaque config):

1. Candidates in order: `~/.config/chromium/Default`, `~/.config/chromium/Profile *` (each), `~/.config/google-chrome/Default`, `~/.config/google-chrome/Profile *`, flatpak variants (`~/.var/app/org.chromium.Chromium/config/chromium/...`, `~/.var/app/com.google.Chrome/config/google-chrome/...`) — only dirs that exist. NOTE: for Chromium multi-profile, `launch_persistent_context(user_data_dir=<root>)` + `--profile-directory=<name>` arg selects the profile; verify the mechanics empirically.
2. Per candidate: launch headed (system executable `/usr/bin/chromium` or matching binary for the dir family), goto chatgpt.com, classify rendered state {signed-in | login-page | error} via robust generic markers (login page has login/signup affordances; signed-in shows a composer). Close context. ~15 s each. If a profile is LOCKED (browser running), raise the named actionable error and STOP the mission leg with handoff PARTIAL ("close <browser>") — do not kill anything, do not delete locks.
3. First signed-in candidate wins: record the PATH (and profile-directory name) in `M-006-state.json` and in `src/ask_chatgpt/selector_maps/real.json`'s metadata (path only — no contents, no account identifiers). All candidates logged-out → handoff PARTIAL with exact operator action: "Open <the browser you use>, sign into chatgpt.com, close the browser, then tell the team lead to resume."

## Then proceed per the ORIGINAL contract, unchanged

- T2 discovery (≤12 messages) → fill `real.json`, `orchestration/reports/M-006/discovery.md` (extend the existing T1-era discovery notes), asset-domain list for the allowlist.
- T3 real UC1–3 acceptance (≤15 messages) → `tmp/real-accept-<ts>/`.
- T4 N=3 verification panel + synthesis → update `VERIFICATION.md` + `orchestration/reports/M-006/verify.md` with final `VERDICT:`.
- Handoff `orchestration/handoffs/MISSION-006-handoff.json` (replace the PARTIAL one; carry total MESSAGES_USED across both audit logs; telemetry as literal JSON fields; `ESTIMATE: M-006 150m` with ACTUAL from the FIRST manager's start ~09:59), state DONE, closeout commit `M-006:`. SAFETY BLOCK from the original contract goes VERBATIM into every worker contract — including: headed only, human-paced, one real worker at a time, login NEVER automated, no credential/profile-content reads, no account identifiers anywhere, budget is HARD.
