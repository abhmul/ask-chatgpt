# M7-T3b

Status: DONE

- Test evidence: `uv run pytest -q` -> `247 passed in 1.00s`.
- Commit: `d9437d75c8fd7997ac505d0097bd57b49fd0d84c` — `M7-T3b: poll post-submit URL for draft conversation id`.
- Falsifiability: `test_draft_url_poll_tolerates_spa_navigation_latency` scripts two pre-navigation URL reads before `/c/learned-xyz`; a one-shot implementation raises before learning the id and cannot satisfy `current_url_reads >= 3` or the learned transcript path assertion.
- Falsifiability: `test_draft_url_poll_fails_closed_when_never_navigates` keeps the URL at `https://chatgpt.com/`; an unbounded/success-biased implementation would not raise, and a one-shot implementation fails `current_url_reads > 1` plus the clear timeout-message/details assertions.
- No real `time.sleep`: post-submit URL polling uses `ask_chatgpt.send._monotonic` and `_sleep_until`; `git show --format= --unified=0 HEAD -- src/ask_chatgpt/session.py src/ask_chatgpt/channels/mock.py tests/test_session_draft_loop.py | grep -n "time\.sleep"` produced no matches.
- Staging isolation: `git diff --cached --name-only` was empty after the commit; `issues/cdp-send-repro/controller.mjs` remains unstaged modified and `human/` remains unstaged untracked.
- Blockers: none.
