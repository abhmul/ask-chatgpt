DONE

2. Files changed
- src/ask_chatgpt/cli.py:14 — imported `MaxTotalWaitExceededError` beside `CompletionTimeoutError`.
- src/ask_chatgpt/cli.py:92 — widened the salvage branch to `except (CompletionTimeoutError, MaxTotalWaitExceededError) as exc:` while keeping the `command == "ask"` gate and `exc.exit_code`.
- tests/test_cli.py:10,114-117,812 — imported/raised `MaxTotalWaitExceededError` in the fake session and added `test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error`.

3. FALSIFIABILITY PROOF
Red command: `uv run pytest "tests/test_cli.py::test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error" -x 2>&1 | tail -40`
Relevant failing-output snippet before the fix:
```text
____ test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error _____
...
        assert code == 51
>       assert captured.out == "PARTIAL-ANSWER-SENTINEL\n"
E       AssertionError: assert '' == 'PARTIAL-ANSWER-SENTINEL\n'
E         
E         - PARTIAL-ANSWER-SENTINEL
...
FAILED tests/test_cli.py::test_cli_max_total_wait_prints_salvage_to_stdout_and_out_before_error
============================== 1 failed in 0.07s ===============================
```
Green confirmation after the fix: the same single-test command passed with `1 passed in 0.04s`.

4. FULL-suite summary
`============================= 282 passed in 1.28s ==============================`

5. ask/loop salvage asymmetry note
This fix intentionally preserves the existing scope: salvage handling fires only for `ask`. `loop` also accepts `--max-total-wait`, but only has `KeyboardInterrupt` partial handling; that asymmetry is out of scope for this task.
