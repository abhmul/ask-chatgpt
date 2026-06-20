PASS-WITH-NOTES

# M4 verify lens 5 — reproduction / isolation / offline

## Summary
- `uv run pytest` is GREEN: `183 passed`, matching `team/evidence/reports/M4-pytest-authoritative.txt` (`183 passed`).
- Offline import check passed: importing `ask_chatgpt.cli` and `ask_chatgpt.session` did not import `playwright`.
- `pyproject.toml` deselects `real_site` by default and documents gating on `ASK_CHATGPT_REAL=1`.
- Git isolation hard checks passed: current branch is `rewrite-v2`; `stable` resolves to `779eb40`.
- M4 implementation step commits inspected below touched only `src/ask_chatgpt` and `tests`. No inspected M4 stat output contains `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, or `human/`.
- Note: non-step M4 manager/report commits in the same range touched `team/contracts`, `team/evidence`, and `team/state/M4-manager-state.json`; I treated these as report/state commits, not implementation step commits. They did not touch the explicit forbidden paths.
- I ran no `uv tool` command and no `git push` command. Local remote/upstream checks show no configured upstream or `origin/rewrite-v2` ref, so remote push state was not further provable without fetching/network; no push-capable command was invoked by this lens.

## 1. Reproduction: `uv run pytest`

Authoritative file `team/evidence/reports/M4-pytest-authoritative.txt` ends with:

```text
============================= 183 passed in 0.40s ==============================
```

Command output:

```text
$ uv run pytest
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/abhmul/dev/ask-chatgpt
configfile: pyproject.toml
testpaths: tests
collected 183 items

tests/test_allowlist.py .......................                          [ 12%]
tests/test_capture.py .................                                  [ 21%]
tests/test_channels_base.py ...                                          [ 23%]
tests/test_cli.py .........                                              [ 28%]
tests/test_errors.py ....................                                [ 39%]
tests/test_identity.py ..............                                    [ 46%]
tests/test_mock_channel.py ........                                      [ 51%]
tests/test_models.py ................                                    [ 60%]
tests/test_selectors.py ..................                               [ 69%]
tests/test_send_completion.py ..................                         [ 79%]
tests/test_session_stubs.py ..                                           [ 80%]
tests/test_smoke.py ......                                               [ 84%]
tests/test_store_atomic_raw.py ...                                       [ 85%]
tests/test_store_attachment_path.py ...                                  [ 87%]
tests/test_store_durability.py ..                                        [ 88%]
tests/test_store_identity_resolution.py ..                               [ 89%]
tests/test_store_index.py ..                                             [ 90%]
tests/test_store_jsonl.py ..                                             [ 91%]
tests/test_store_layout.py ..                                            [ 92%]
tests/test_store_partial.py ...                                          [ 94%]
tests/test_store_payload.py ...                                          [ 96%]
tests/test_store_pending_send.py ..                                      [ 97%]
tests/test_store_read_semantics.py .                                     [ 97%]
tests/test_store_render.py .                                             [ 98%]
tests/test_store_torn_line.py ...                                        [100%]

============================= 183 passed in 0.36s ==============================
```

## 2. Offline checks

Command output:

```text
$ uv run python -c "import sys,ask_chatgpt.cli,ask_chatgpt.session; assert 'playwright' not in sys.modules; print('ok')"
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
ok
```

`pyproject.toml` grep output:

```text
pyproject.toml-17- ]
pyproject.toml-18- 
pyproject.toml-19- [tool.pytest.ini_options]
pyproject.toml:20: addopts = ["-m", "not real_site"]
pyproject.toml-21- markers = ["real_site: real chatgpt.com tests; deselected by default and gated on ASK_CHATGPT_REAL=1"]
pyproject.toml-22- testpaths = ["tests"]
pyproject.toml-23- 
pyproject.toml-18- 
pyproject.toml-19- [tool.pytest.ini_options]
pyproject.toml-20- addopts = ["-m", "not real_site"]
pyproject.toml:21: markers = ["real_site: real chatgpt.com tests; deselected by default and gated on ASK_CHATGPT_REAL=1"]
pyproject.toml-22- testpaths = ["tests"]
pyproject.toml-23- 
pyproject.toml-24- [build-system]
```

## 3. Git isolation

Command outputs:

```text
$ git rev-parse --short stable
779eb40

$ git rev-parse --abbrev-ref HEAD
rewrite-v2

$ git log --oneline -10
7d01351 M4: E6 cli manager record + authoritative pytest output (183 passed)
66b5533 M4 step 6: cli verbs and status over mock
7db36f4 M4: E4 capture + E5 send/completion manager record
274e8bc M4 step 5: verified send + completion detection over mock
de96e20 M4 step 4c: cover capture fallback degradation
3d30e2d M4 step 4b: add offline capture parser
379795a M4 step 4a: relax created_at invariant
43c45bf M4: E2 store + E3 mock manager record; pin DECISION 13 seam fix for E4
64a9f97 M4 step 3: MockChannel offline fixtures
9c599d1 M4 E2 (store layer) preserved: JSONL store + index + atomic + pending-stub + render
```

Extended enumeration used to include older M4 step commits not in the top 10:

```text
$ git log --oneline stable..HEAD
7d01351 M4: E6 cli manager record + authoritative pytest output (183 passed)
66b5533 M4 step 6: cli verbs and status over mock
7db36f4 M4: E4 capture + E5 send/completion manager record
274e8bc M4 step 5: verified send + completion detection over mock
de96e20 M4 step 4c: cover capture fallback degradation
3d30e2d M4 step 4b: add offline capture parser
379795a M4 step 4a: relax created_at invariant
43c45bf M4: E2 store + E3 mock manager record; pin DECISION 13 seam fix for E4
64a9f97 M4 step 3: MockChannel offline fixtures
9c599d1 M4 E2 (store layer) preserved: JSONL store + index + atomic + pending-stub + render
b6d954c M4 step 2: store.py JSONL persistence, atomic writes, pending-stub supersession, render, payload helper
0d8051d M4: test-plan + E1 scaffold manager record
7c1cdf3 M4 step 1: scaffold offline core seam
5450561 M3 done: detailed design verified (best-of-N + 3-panel + revisions); M4 ready
103e8b8 Ingest M1+M2: archive/scaffold done; probe confirms backend-api capture (auth-header adjustment)
b875521 Archive v1 library and scaffold v2 package
ec2dafc Track project files + CDP-send gotcha evidence on main; signpost rewrite-v2 branch
6391e7f M0: author ask-chatgpt v2 rewrite spec from grill-me intake; populate mission queue
bf208d8 team: set up team-lead-v2 state surface; archive stale v1 orchestration
7483806 M-011b WIP (paused): corrected DR-turn selectors + composer-chip exclusion; PAUSED banner + resume instructions
f816393 checkpoint 2026-06-16: session daily note + track capture-renders-DOM issue
9667d0c Track issues/ — tool bug/feature tracker (referenced by docs/DESIGN-SPEC.md)
499f1ce docs: DESIGN-SPEC — Web-UI-mirroring interface + persistence/cache redesign (for future agents)
```

Implementation step commit stats:

```text
$ git show --stat --oneline --no-renames 66b5533
66b5533 M4 step 6: cli verbs and status over mock
 src/ask_chatgpt/cli.py      | 449 +++++++++++++++++++++++++++++++++++++++++---
 src/ask_chatgpt/session.py  | 375 ++++++++++++++++++++++++++++++++----
 tests/test_cli.py           | 336 +++++++++++++++++++++++++++++++++
 tests/test_session_stubs.py | 121 ++++++++++++
 tests/test_smoke.py         |  89 ++++++++-
 5 files changed, 1305 insertions(+), 65 deletions(-)

$ git show --stat --oneline --no-renames 274e8bc
274e8bc M4 step 5: verified send + completion detection over mock
 src/ask_chatgpt/capture.py       |   5 +-
 src/ask_chatgpt/channels/mock.py |   2 +
 src/ask_chatgpt/completion.py    | 507 +++++++++++++++++++++++++++++++
 src/ask_chatgpt/menus.py         | 106 +++++++
 src/ask_chatgpt/send.py          | 243 +++++++++++++++
 src/ask_chatgpt/session.py       | 245 ++++++++++++++-
 src/ask_chatgpt/store.py         |  12 +-
 tests/__init__.py                |   1 +
 tests/conftest.py                |   8 +
 tests/test_send_completion.py    | 639 +++++++++++++++++++++++++++++++++++++++
 10 files changed, 1750 insertions(+), 18 deletions(-)

$ git show --stat --oneline --no-renames de96e20
de96e20 M4 step 4c: cover capture fallback degradation
 tests/test_capture.py | 72 ++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 71 insertions(+), 1 deletion(-)

$ git show --stat --oneline --no-renames 3d30e2d
3d30e2d M4 step 4b: add offline capture parser
 src/ask_chatgpt/capture.py | 749 +++++++++++++++++++++++++++++++++++++++++++++
 tests/test_capture.py      | 290 ++++++++++++++++++
 2 files changed, 1039 insertions(+)

$ git show --stat --oneline --no-renames 379795a
379795a M4 step 4a: relax created_at invariant
 src/ask_chatgpt/models.py   |  2 --
 src/ask_chatgpt/store.py    |  6 +++---
 tests/test_models.py        | 29 ++++++++++++++++++++++++++++-
 tests/test_store_partial.py | 38 ++++++++++++++++++++++++++++++++++++--
 4 files changed, 67 insertions(+), 8 deletions(-)

$ git show --stat --oneline --no-renames 64a9f97
64a9f97 M4 step 3: MockChannel offline fixtures
 src/ask_chatgpt/channels/mock.py | 564 ++++++++++++++++++++++++++++
 tests/mock_scenarios.py          | 786 +++++++++++++++++++++++++++++++++++++++
 tests/test_mock_channel.py       | 277 ++++++++++++++
 3 files changed, 1627 insertions(+)

$ git show --stat --oneline --no-renames b6d954c
b6d954c M4 step 2: store.py JSONL persistence, atomic writes, pending-stub supersession, render, payload helper
 src/ask_chatgpt/__init__.py             |   4 +
 src/ask_chatgpt/identity.py             |  11 +-
 src/ask_chatgpt/store.py                | 714 ++++++++++++++++++++++++++++++++
 tests/test_identity.py                  |  22 +-
 tests/test_store_atomic_raw.py          |  89 ++++
 tests/test_store_attachment_path.py     |  47 +++
 tests/test_store_durability.py          |  83 ++++
 tests/test_store_identity_resolution.py |  68 +++
 tests/test_store_index.py               |  74 ++++
 tests/test_store_jsonl.py               | 129 ++++++
 tests/test_store_layout.py              |  39 ++
 tests/test_store_partial.py             |  32 ++
 tests/test_store_payload.py             |  54 +++
 tests/test_store_pending_send.py        |  76 ++++
 tests/test_store_read_semantics.py      | 102 +++++
 tests/test_store_render.py              | 117 ++++++
 tests/test_store_torn_line.py           |  73 ++++
 17 files changed, 1728 insertions(+), 6 deletions(-)

$ git show --stat --oneline --no-renames 7c1cdf3
7c1cdf3 M4 step 1: scaffold offline core seam
 src/ask_chatgpt/__init__.py           | 100 ++++++++++++
 src/ask_chatgpt/allowlist.py          | 102 ++++++++++++
 src/ask_chatgpt/channels/__init__.py  |  19 +++
 src/ask_chatgpt/channels/base.py      | 110 +++++++++++++
 src/ask_chatgpt/errors.py             | 286 ++++++++++++++++++++++++++++++++++
 src/ask_chatgpt/identity.py           | 156 +++++++++++++++++++
 src/ask_chatgpt/models.py             | 273 ++++++++++++++++++++++++++++++++
 src/ask_chatgpt/selectors/__init__.py |  91 +++++++++++
 src/ask_chatgpt/selectors/real.json   |  12 ++
 src/ask_chatgpt/session.py            | 118 ++++++++++++++
 tests/test_allowlist.py               |  90 +++++++++++
 tests/test_channels_base.py           | 116 ++++++++++++++
 tests/test_errors.py                  |  95 +++++++++++
 tests/test_identity.py                |  80 ++++++++++
 tests/test_models.py                  | 219 ++++++++++++++++++++++++++
 tests/test_selectors.py               |  76 +++++++++
 16 files changed, 1943 insertions(+)
```

Non-step M4 report/state commit stats inspected for explicit forbidden paths:

```text
$ git show --stat --oneline --no-renames 7d01351
7d01351 M4: E6 cli manager record + authoritative pytest output (183 passed)
 team/contracts/M4-E6-cli.md                       |  43 +++++
 team/evidence/handoffs/M4-E6-cli.md               |  89 ++++++++++
 team/evidence/reports/M4-pytest-authoritative.txt | 193 ++++++++++++++++++++++
 team/state/M4-manager-state.json                  |   2 +-
 4 files changed, 326 insertions(+), 1 deletion(-)

$ git show --stat --oneline --no-renames 7db36f4
7db36f4 M4: E4 capture + E5 send/completion manager record
 team/contracts/M4-E4-capture.md                 | 37 ++++++++++++++++++
 team/contracts/M4-E5-send-completion.md         | 37 ++++++++++++++++++
 team/evidence/handoffs/M4-E4-capture.md         | 52 +++++++++++++++++++++++++
 team/evidence/handoffs/M4-E5-send-completion.md | 46 ++++++++++++++++++++++
 team/state/M4-manager-state.json                |  4 +-
 5 files changed, 174 insertions(+), 2 deletions(-)

$ git show --stat --oneline --no-renames 43c45bf
43c45bf M4: E2 store + E3 mock manager record; pin DECISION 13 seam fix for E4
 team/contracts/M4-E3-mock.md          | 32 ++++++++++++++++++++
 team/contracts/M4-common.md           |  1 +
 team/evidence/handoffs/M4-E2-store.md | 44 +++++++++++++++++++++++++++
 team/evidence/handoffs/M4-E3-mock.md  | 57 +++++++++++++++++++++++++++++++++++
 team/state/M4-manager-state.json      |  4 +--
 5 files changed, 136 insertions(+), 2 deletions(-)

$ git show --stat --oneline --no-renames 9c599d1
9c599d1 M4 E2 (store layer) preserved: JSONL store + index + atomic + pending-stub + render
 team/contracts/M4-E2-store.md    | 33 +++++++++++++++++++++++++++++++++
 team/state/M4-manager-state.json |  2 +-
 2 files changed, 34 insertions(+), 1 deletion(-)

$ git show --stat --oneline --no-renames 0d8051d
0d8051d M4: test-plan + E1 scaffold manager record
 team/contracts/M4-E1-scaffold.md             |  40 +++
 team/contracts/M4-common.md                  |  65 ++++
 team/evidence/handoffs/M4-E1-scaffold.md     |  67 ++++
 team/evidence/reports/M4-test-plan-lens-1.md | 165 ++++++++++
 team/evidence/reports/M4-test-plan-lens-2.md | 365 ++++++++++++++++++++++
 team/evidence/reports/M4-test-plan-lens-3.md | 445 +++++++++++++++++++++++++++
 team/evidence/reports/M4-test-plan.md        | 403 ++++++++++++++++++++++++
 team/state/M4-manager-state.json             |  54 ++++
 8 files changed, 1604 insertions(+)
```

## 4. No `uv tool` / no push evidence

Commands I ran were limited to `uv run pytest`, `uv run python`, read/grep, and read-only `git rev-parse`/`git log`/`git show`; no `uv tool` or `git push` command was invoked. Local remote/upstream probes:

```text
$ git rev-parse --short HEAD
7d01351

$ git rev-parse --short origin/rewrite-v2
fatal: Needed a single revision

$ git log --oneline origin/rewrite-v2..HEAD
fatal: ambiguous argument 'origin/rewrite-v2..HEAD': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'

$ git rev-parse --abbrev-ref --symbolic-full-name @{u}
fatal: no upstream configured for branch 'rewrite-v2'
```

## 5. Independent falsifiable behavior spot-runs via public API

Allowlist suffix-confusion rejection:

```text
$ uv run python - <<'PY'
from ask_chatgpt.allowlist import Allowlist
from ask_chatgpt.errors import DomainNotAllowedError

url = "https://chatgpt.com.evil.example/c/chat_123"
try:
    Allowlist().require_allowed_url(url)
except DomainNotAllowedError as exc:
    print(f"rejected {url} code={exc.code} exit={exc.exit_code}")
else:
    raise SystemExit("allowlist accepted suffix-confusion URL")
PY
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
rejected https://chatgpt.com.evil.example/c/chat_123 code=DOMAIN_NOT_ALLOWED exit=22
```

No-op `Session.ask` over public mock channel raises `PromptNotSubmittedError`:

```text
$ uv run python - <<'PY'
from tempfile import TemporaryDirectory

from ask_chatgpt.channels.mock import MockChannel, MockScenario, ScriptedClock
from ask_chatgpt.errors import PromptNotSubmittedError
from ask_chatgpt.session import Session

clock = ScriptedClock()
mock = MockChannel(
    MockScenario(name="external_no_op_public_api"),
    monotonic=clock.monotonic,
    sleeper=clock.sleep,
)
with TemporaryDirectory() as data_dir:
    session = Session(
        data_dir=data_dir,
        channel=mock,
        send_verify_timeout_s=1.0,
        composer_wait_timeout_s=1.0,
    )
    try:
        session.ask("conv_no_op_public_api", "literal prompt")
    except PromptNotSubmittedError as exc:
        print(
            f"raised {type(exc).__name__} code={exc.code} "
            f"clock={clock.monotonic():.1f} query_turns={mock.method_counts.get('query_turns', 0)}"
        )
    else:
        raise SystemExit("no-op send did not raise PromptNotSubmittedError")
PY
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
raised PromptNotSubmittedError code=PROMPT_NOT_SUBMITTED clock=1.0 query_turns=6
```
