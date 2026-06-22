# WORKER CONTRACT — M13-complete TASK 1 (OFFLINE editor): descriptor-header mock test

You are a single WORKER (pi, tools `read,grep,find,ls,edit,write,bash`) for repo `/home/abhmul/dev/ask-chatgpt`.
This contract is FULLY SELF-CONTAINED. You inherit nothing. Read it in full and execute end-to-end, then print a structured report to stdout (your stdout IS the deliverable — there is no separate handoff file for you to write).

## Goal
Add ONE falsifiable mock test to `tests/test_capture.py` that pins the attachment **descriptor** request's headers. **TEST-ONLY. NO production change.** Then run the offline suite and prove the test is falsifiable.

## Hard constraints (OBEY EXACTLY)
- **NO production-code change.** You touch ONLY `tests/test_capture.py`. `src/` must end byte-identical to its current state.
- Do **NOT** `git commit`, `git push`, `git checkout`, `git stash`, or switch branches. Do **NOT** run `uv tool install/upgrade/reinstall`. Do **NOT** touch `issues/cdp-send-repro/controller.mjs`, `human/`, or `archive/`.
- Use `uv run pytest` (the PROJECT `.venv`) — never the bare installed `ask-chatgpt`.
- Stay on the current branch; do not create/switch branches.

## Step 1 — add the import symbol
In `tests/test_capture.py` the existing import block is:
```python
from ask_chatgpt.capture import (
    acquire_backend_headers,
    capture_conversation,
    fallback_capture_ui,
    iter_current_branch_records,
    validate_backend_shape,
)
```
Add `REQUIRED_CAPTURE_HEADERS,` to that import (e.g. as the first name). `Store`, `MockChannel`, `MockScenario`, `MockBackendResponse`, `ConversationRef` are ALREADY imported in this file, and the helpers `_attachment_download_raw`, `_backend_request_snapshot`, `_headers_for_path` ALREADY exist in it — do not redefine them.

## Step 2 — add this EXACT test
Insert this test near the other attachment-download tests in `tests/test_capture.py` (anywhere at module top level among the `def test_...` functions; e.g. right after `test_conversation_fetch_retargets_harvested_target_path`):

```python
def test_attachment_descriptor_fetch_reuses_conversation_retargeted_headers(tmp_path) -> None:
    conversation_id = "conv_mock_descriptor_header_path"
    conversation_path = f"/backend-api/conversation/{conversation_id}"
    harvested_path = "/backend-api/accounts/check"
    harvested_route = "MOCK_DESCRIPTOR_HEADER_ROUTE"
    attachment_id = "file_" + "descriptor_header_probe"
    descriptor_path = f"/backend-api/files/{attachment_id}/download"
    payload = b"mock descriptor header bytes"
    download_url = "https://chatgpt.com/backend-api/mock-downloads/descriptor-header-probe"

    class RecordingChannel(MockChannel):
        def __init__(self, scenario: MockScenario) -> None:
            super().__init__(scenario)
            self.descriptor_requests: list[tuple[str, str, dict[str, str]]] = []

        def fetch_in_page(self, tab, url, *, method="GET", headers=None, body=None, stream_to=None, timeout_s=None):  # noqa: ANN001, ANN201
            if url == descriptor_path:
                self.descriptor_requests.append(
                    (
                        method,
                        url,
                        {str(key).lower(): str(value) for key, value in dict(headers or {}).items()},
                    )
                )
            return super().fetch_in_page(
                tab,
                url,
                method=method,
                headers=headers,
                body=body,
                stream_to=stream_to,
                timeout_s=timeout_s,
            )

    raw = _attachment_download_raw(
        conversation_id,
        user_metadata={
            "attachments": [
                {
                    "id": attachment_id,
                    "name": "descriptor-header.txt",
                    "mime_type": "text/plain",
                    "size": len(payload),
                }
            ]
        },
    )
    scenario = MockScenario(
        name="attachment_descriptor_header_path",
        backend_conversations={conversation_id: raw},
        request_snapshots=(
            _backend_request_snapshot(
                harvested_path,
                headers=_headers_for_path(
                    harvested_path,
                    **{"x-openai-target-route": harvested_route},
                ),
            ),
        ),
        file_downloads={
            attachment_id: MockBackendResponse(
                200,
                {
                    "download_url": download_url,
                    "file_size_bytes": len(payload),
                    "mime_type": "text/plain",
                    "status": "success",
                },
            )
        },
        download_responses={
            download_url: MockBackendResponse(200, payload, headers={"content-type": "text/plain"})
        },
    )
    channel = RecordingChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/")
    conv = ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}")

    result = capture_conversation(
        tab,
        conv,
        Store(data_dir=tmp_path),
        with_attachments=True,
        header_mode="ambient_backend",
    )

    assert result.transcript.turns[0].attachments[0].download_state == "downloaded"
    assert channel.method_counts["attachment_descriptor_fetches"] == 1
    assert channel.method_counts["attachment_byte_fetches"] == 1

    # ASSERTION: descriptor request identity.
    assert len(channel.descriptor_requests) == 1
    method, url, descriptor_headers = channel.descriptor_requests[0]
    assert method == "GET"
    assert url == descriptor_path

    # ASSERTION: descriptor request carries all required backend auth/OAI header names.
    assert set(REQUIRED_CAPTURE_HEADERS) <= set(descriptor_headers)

    # ASSERTION: current M10 design keeps descriptor x-openai-target-path on the conversation fetch path.
    assert descriptor_headers["x-openai-target-path"] == conversation_path
    assert descriptor_headers["x-openai-target-route"] == harvested_route
```

(If you prefer, you may copy this exact test verbatim from `.pi-workers/M13/lensB/pi-20260622-103506-3077813-19261/output.log` section (c), lines 42–143 — it is identical to the above.)

## Step 3 — run the offline suite (authoritative)
1. Full suite: `uv run pytest -q` — record the EXACT summary line (e.g. `281 passed`). Expectation: **280 → 281 passed** (baseline ~280; if the real baseline differs, report the actual numbers — do NOT assume).
2. Targeted: `uv run pytest tests/test_capture.py -k descriptor_fetch_reuses -q` — must show `1 passed`. This pins that the NEW test actually ran and passed (independent of the total).

## Step 4 — prove falsifiability (do this WITHOUT git checkout/stash)
Pick ONE:
- **(preferred) Temporary mutate + Edit-restore:** Use the `edit` tool to temporarily break the production descriptor header spread in `src/ask_chatgpt/capture.py` `_fetch_attachment_descriptor` (≈ lines 459–466) — e.g. change the descriptor fetch to pass `headers=None` or drop one required header. Run `uv run pytest tests/test_capture.py -k descriptor_fetch_reuses -q` and CONFIRM it now **FAILS** with an assertion error on the header names / target-path. Then use the `edit` tool to restore `capture.py` to its EXACT original. Finally run `git diff --stat -- src/ask_chatgpt/capture.py` and CONFIRM it is **EMPTY** (production unchanged). If you cannot guarantee a clean restore, use the reasoning option instead and leave `src/` untouched.
- **(fallback) Precise reasoning:** Explain, mapping each assertion to the production line it pins (the descriptor header spread at `capture.py:459–466` and the conversation-path retarget at `capture.py:342–343`), exactly which production regressions would make the test fail (dropped header spread, a missing required header name, or a silent target-path change).

## Step 5 — final integrity check
Run `git diff --stat` and confirm the ONLY changed file is `tests/test_capture.py`. Report the exact `git diff --stat` output.

## Report (print to stdout — this IS your deliverable)
Print, clearly labeled:
- `STATUS: DONE | PARTIAL | BLOCKED`
- The exact full-suite summary line (`N passed`) and the targeted `1 passed` line.
- Falsifiability: which method you used and the observed FAIL evidence (assertion message) or the precise reasoning.
- `git diff --stat` output (must show only `tests/test_capture.py`).
- Any blocker with the exact action needed.
