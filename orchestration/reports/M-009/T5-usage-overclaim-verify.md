# M-009 T5 — USAGE overclaim verification

VERDICT: CONCERNS

1. `docs/USAGE.md:85` overclaims that the CLI maps each named error to a distinct exit code “in parentheses.” The rows with explicit codes are correct, but `CDPUnreachableError`, `ChallengePresentError`, and `ProfileLockedError` exist as named `AskChatGPTError` subclasses (`src/ask_chatgpt/errors.py:18`, `:26`, `:40`) and have no specific `_ERROR_EXIT_CODES` entries (`src/ask_chatgpt/cli.py:35-50`), so they fall through to generic `AskChatGPTError` exit code 1. Also, bundle-validation errors intentionally share exit code 11 (`src/ask_chatgpt/cli.py:44-48`), so “distinct” is not literally true. Exact fix: change `docs/USAGE.md:85` to say the CLI maps the codes shown in the table, add `(1)` to `docs/USAGE.md:89`, `:91`, and `:92` unless code-specific mappings are added, and replace “distinct” with “documented” or “grouped.”

## Independent `uv run pytest -q` tail

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........................................................................ [ 33%]
........................................................................ [ 67%]
....................................................................     [100%]
212 passed, 4 deselected in 74.27s (0:01:14)
```

## Per-check table

| Check | Verdict | Evidence |
|---|---|---|
| 1. UC2 real-proven claim | OK | `docs/USAGE.md:107-111` is supported by `orchestration/reports/M-009/T1-uc2-roundtrip.json:2` applied text (`favorite_color` changed, sibling line present), `:3` 161 bytes, `:5` `bundle_source=download`, `:6` `content_correct=true`, `:8` `download_selector_injected=null` (shipped config), and `:11` `retrieve_outcome=retrieved`. This closes the M-008b prior gap where full real apply+diff was explicitly not yet run (`VERIFICATION.md:171-172`). |
| 2. Short-response claim | OK | `docs/USAGE.md:104-106` is supported by `orchestration/reports/M-009/T2-short-response.json:33-35`: `prompts=4`, `returned=4`, `spurious_truncations=[]`, with returned texts at `:7`, `:14`, `:21`, `:28`. |
| 3. Model-selection claim | OK | `docs/USAGE.md:76-82` and `:113` correctly say real model selection is not wired and fails closed. `real.json:12-14` leaves `model_menu`, `model_option`, and `model_option_disabled` empty; empty selector values raise `SelectorUnavailableError` (`src/ask_chatgpt/selector_map.py:29-32`); `select_model` requires `model_menu` before sending (`src/ask_chatgpt/driver.py:226-236`). T3 records the same fail-closed behavior (`orchestration/reports/M-009/T3-model-findings.md:3-6`, `:44-46`). |
| 4. Download-path honesty | OK | `docs/USAGE.md:110-111` and `:121-122` match code and config. The shipped selector is `button:has-text("Download the patch bundle")` (`real.json:20`). Opaque real controls with no `data-source-turn-id`, byte-count, or SHA are accepted as candidates with `byte_count=None`/`sha256=None` (`src/ask_chatgpt/patch.py:333-344`), captured bytes tolerate absent metadata (`src/ask_chatgpt/patch.py:397-431`), and the resulting zip is structurally opened/validated (`src/ask_chatgpt/patch.py:606-631`). |
| 5. Error table | CONCERN | All USAGE-listed classes exist and subclass `AskChatGPTError` or `PatchBundleValidationError` (`src/ask_chatgpt/errors.py:4`, `:18`, `:26`, `:33`, `:40`, `:48`, `:56`, `:63`, `:71`, `:78`, `:86`, `:94`, `:110`, `:117`, `:124`, `:131`, `:138`). Explicit codes in `docs/USAGE.md:90-101` match `src/ask_chatgpt/cli.py:36-49`, but `docs/USAGE.md:85` overstates distinct per-error mapping; `CDPUnreachableError`, `ChallengePresentError`, and `ProfileLockedError` are not specifically mapped and fall to `AskChatGPTError` code 1 (`src/ask_chatgpt/cli.py:50`). |
| 6. Test-tier claim | OK | Independent run produced `212 passed, 4 deselected` exactly. The default deselection is configured at `pyproject.toml:20-21`, and env gating is in `tests/conftest.py:15-20`. |
| 7. Channel honesty | OK | `docs/USAGE.md:48-49` says CLI default is `--channel real`; `src/ask_chatgpt/cli.py:112` confirms default `real`. The real channel launches a persistent context (`src/ask_chatgpt/driver.py:517`); CDP attaches via `connect_over_cdp` (`src/ask_chatgpt/driver.py:530`), opens its own page (`src/ask_chatgpt/driver.py:542-546`), and closes owned CDP pages rather than the browser (`src/ask_chatgpt/driver.py:163-168`). |
| 8. No-leak spot check | OK | Greps over `orchestration/reports/M-009/` found no unredacted real `/c/<id>`-shape conversation refs, no emails, and no credential/token material. False positives were only redaction-policy text, mock/fixture path shapes, and non-secret bundle basename substrings; no values reproduced here. |

ESTIMATE: T5-verify 30m
ACTUAL: T5-verify 24m
END: 2026-06-13T16:47:48-05:00
