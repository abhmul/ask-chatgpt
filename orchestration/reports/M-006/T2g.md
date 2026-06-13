START_TIMESTAMP: 2026-06-12T22:08:36-05:00
END_TIMESTAMP: 2026-06-12T22:21:30-05:00
ESTIMATE: T2g 60m
MESSAGES_USED: 0

## Changes
- GAP-11 nav timeout: `src/ask_chatgpt/driver.py:42,129,189-190,520-521` adds `_REAL_NAV_TIMEOUT_MS = 60_000` and routes `start()` plus existing-conversation `goto()` through `_navigation_timeout_ms()`, using 60s for `real`/`cdp` and preserving 5s for `mock`, matching T2's `timeout=60000`.
- GAP-10b send mechanics: `src/ask_chatgpt/driver.py:251-314` gates the proven real/CDP path to `channel in {"real", "cdp"}`: click composer to focus, try `fill()`, fallback to `Control+A` + `keyboard.insert_text()`, click send button when attached, otherwise press Enter once. The mock branch retains the previous fill/wait/click path.
- GAP-13 completion: `src/ask_chatgpt/driver.py:316-367,622-630` keeps mock completion-marker/reload polling gated to `channel == "mock"`; real/CDP now returns only when a latest assistant turn exists, stop/streaming marker is gone, and either completion marker is present or latest body text is stable for `_REAL_COMPLETION_STABLE_S = 2.0`.
- GAP-12 upload confirmation: `src/ask_chatgpt/bundle.py:37,336-340,648-709` preserves mock `data-upload-status` handling and adds real/CDP fallback when that status element is absent: wait up to `_REAL_UPLOAD_CHIP_TIMEOUT_S = 90.0` for the uploaded filename text/chip, then confirm `status="ok"`.

## TDD evidence
- RED-first targeted tests before implementation: `10 failed, 2 passed` across GAP-11/10b/13/12 tests; representative failures were 5s nav timeout, send-button absence raising `SelectorUnavailableError`, no contenteditable fallback, absent stable-completion constant/path, and absent upload chip timeout/path.
- GREEN targeted tests after implementation: `12 passed in 0.19s` for the new GAP-11/10b/13/12 tests.
- Test anchors: `tests/test_driver_real_preflight.py:187`, `tests/test_driver.py:498,559,571,583,598,608,618`, `tests/test_bundle_out.py:212,223`.

## Full suite / tier purity
- Ran `uv sync --all-groups` before the full default suite.
- Authoritative full suite: `uv run pytest` → `169 passed, 1 deselected in 66.57s`; pytest default marker deselected `real_site`, so ZERO real-site tests/contact.
- Mock UC1 happy path green: `tests/test_ask_chatgpt_uc1.py ....` in the full run.
- Mock UC2 happy path green: `tests/test_uc2_roundtrip.py ..` in the full run.
- Unchanged forbidden files verified with `git diff --name-only -- src/ask_chatgpt/selector_maps/real.json src/ask_chatgpt/selector_maps/mock.json tests/conftest.py src/ask_chatgpt/selector_map.py src/ask_chatgpt/api.py src/ask_chatgpt/cli.py` → no output.
- Pre-existing dirty files before T2g edits: `orchestration/reports/M-006/T3.md`, `orchestration/state/M-006-state.json`, and untracked `orchestration/tasks/M-006/T2g-real-mechanics.md`; not touched for T2g.

## git diff --stat scope
```text
src/ask_chatgpt/bundle.py           |  61 +++++++-
src/ask_chatgpt/driver.py           | 110 ++++++++++++---
tests/test_bundle_out.py            |  81 +++++++++++
tests/test_driver.py                | 272 +++++++++++++++++++++++++++++++++++-
tests/test_driver_real_preflight.py | 137 +++++++++++++++++-
5 files changed, 639 insertions(+), 22 deletions(-)
```

T2g-STATUS: DONE
