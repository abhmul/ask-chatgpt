START_TIMESTAMP: 2026-06-12T06:40:27-05:00
ESTIMATE: T4a 15m

# T4a authoritative evidence index

| Artifact | Key quoted line(s) |
|---|---|
| `tmp/verify-m005/clone_head.txt` | `261a16b33e3240b4d629e72c0ae8a1fd318ff538`<br>`MATCH: yes`<br>`CONTAINS_0179400: yes`<br>`CONTAINS_2f0b8de: yes`<br>`CONTAINS_261a16b: yes`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/clone_final_status.txt` | `COMMAND: git status --porcelain`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/clone_uv_sync.txt` | `Editable project location: /home/abhmul/dev/ask-chatgpt/tmp/verify-m005/clone`<br>`EDITABLE_SRC_CONFIRMED: /home/abhmul/dev/ask-chatgpt/tmp/verify-m005/clone/src/ask_chatgpt/__init__.py`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/clone_pytest.txt` | `121 passed in 58.82s`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/accept_uc1_stdout.txt` | `mock_base_url=http://127.0.0.1:48375`<br>`overall=pass`<br>`results_json=tmp/accept-uc1-20260612-064214/results.json`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/accept_uc1_results.json` | `"overall": "pass"`<br>`"name": "same-session-call-2-continuity"`<br>`"status": "pass"` |
| `tmp/verify-m005/accept_uc2_stdout.txt` | `mock_base_url=http://127.0.0.1:48009`<br>`overall=pass`<br>`results_json=tmp/accept-uc2-20260612-064224/results.json`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/accept_uc2_results.json` | `"overall": "pass"`<br>`"name": "download-primary-roundtrip"` / `"status": "pass"`<br>`"name": "fenced-fallback-roundtrip"` / `"status": "pass"` |
| `tmp/verify-m005/accept_uc3_stdout.txt` | `mock_base_url=http://127.0.0.1:37997`<br>`STEP session-continuity: pass`<br>`overall=pass`<br>`results_json=tmp/accept-uc3-20260612-064232/results.json`<br>`EXIT_CODE: 0` |
| `tmp/verify-m005/accept_uc3_results.json` | `"overall": "pass"`<br>`"name": "session-continuity"`<br>`"status": "pass"`<br>`"user_turns": [`<br>`"accept UC3 session prompt one"`<br>`"accept UC3 session prompt two"` |
| `tmp/verify-m005/d2_demo.txt` | `1 passed in 0.08s`<br>`D2_FAILCLOSED_PYTEST_EXIT_CODE: 0`<br>`102:            self._ensure_real_selector_map_ready()`<br>`103:        self._playwright = sync_playwright().start()`<br>`115:            page.goto(self._base_url, wait_until="load", timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)`<br>`295      def _ensure_real_selector_map_ready(self) -> None:`<br>`297              self.selectors.selector(key)`<br>`299              self.selectors.attribute(key)`<br>`31          if not isinstance(value, str) or not value.strip():`<br>`38              raise SelectorUnavailableError(f"attribute '{key}' unavailable for channel '{self.channel}'")`<br>`REAL_JSON_SELECTORS_COUNT: 20`<br>`REAL_JSON_ATTRIBUTES_COUNT: 2`<br>`REAL_JSON_ALL_EMPTY: True`<br>`EXIT_CODE: 0` |

Recovery note: none. `uv sync --all-groups` in the clean clone succeeded with package network permitted; no `tmp/verify-m005/clone_sync_RECOVERY.txt` was needed.

END_TIMESTAMP: 2026-06-12T06:45:03-05:00
T4a-STATUS: DONE
