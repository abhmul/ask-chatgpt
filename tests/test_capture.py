from __future__ import annotations

import json
from pathlib import Path

import pytest

from ask_chatgpt.capture import (
    REQUIRED_CAPTURE_HEADERS,
    acquire_backend_headers,
    capture_conversation,
    fallback_capture_ui,
    iter_current_branch_records,
    validate_backend_shape,
)
from ask_chatgpt.channels.base import RequestSnapshot
from ask_chatgpt.channels.mock import HEADER_CANARIES, MockBackendResponse, MockChannel, MockScenario
from ask_chatgpt.errors import (
    BackendAuthUnavailableError,
    BackendCaptureShapeError,
    CaptureFailedClosedError,
    HumanActionNeededError,
)
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.session import Session
from ask_chatgpt.store import Store
from mock_scenarios import (
    CONTENT_PARTS_EXPECTED,
    attachment_citation_raw,
    backend_header_scenario,
    current_branch_ids,
    deep_research_scenarios,
    large_mapping_raw,
    malformed_mapping_variants,
    safety_scenarios,
)


def test_404_without_required_headers_does_not_emit_canonical_transcript(tmp_path) -> None:
    channel = MockChannel(MockScenario(name="no_backend_headers"))
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_headers")
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")

    with pytest.raises(HumanActionNeededError) as error_info:
        capture_conversation(tab, ref, store)

    assert error_info.value.details["reason"] == "clipboard_permission"
    transcript_path = tmp_path / "conversations" / "conv_mock_headers" / "transcript.jsonl"
    raw_path = tmp_path / "conversations" / "conv_mock_headers" / "raw-mapping.json"
    assert not transcript_path.exists() or transcript_path.read_text(encoding="utf-8") == ""
    assert not raw_path.exists()
    assert channel.method_counts.get("fetch_in_page", 0) == 0


def test_authorized_200_capture_promotes_validated_raw_and_complete_backend_records(tmp_path) -> None:
    scenario = backend_header_scenario()
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_headers")
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")

    result = capture_conversation(tab, ref, store)

    assert result.source == "backend_api"
    assert result.fidelity == "canonical"
    assert result.async_status is None
    assert "mapping" in result.raw_top_level_keys
    assert result.transcript.raw_mapping_path is not None
    raw = json.loads(result.transcript.raw_mapping_path.read_text(encoding="utf-8"))
    assert raw["title"] == "Mock 5k mapping"
    assert raw["default_model_slug"] == "gpt-5.5-pro"
    assert len(raw["mapping"]) > 5000
    assert {turn.capture_source for turn in result.transcript.turns} == {"backend_api"}
    assert {turn.fidelity for turn in result.transcript.turns} == {"canonical"}
    assert {turn.status for turn in result.transcript.turns} == {"complete"}
    assert {turn.partial for turn in result.transcript.turns} == {False}
    assert [turn.turn_index for turn in result.transcript.turns] == list(range(len(result.transcript.turns)))


@pytest.mark.parametrize(
    "response",
    [
        MockBackendResponse(500, {"detail": "server error"}),
        MockBackendResponse(200, b"<html>not json</html>", headers={"content-type": "text/html"}),
        MockBackendResponse(200, b"{not json", headers={"content-type": "application/json"}),
        MockBackendResponse(200, large_mapping_raw(conversation_id="wrong_conversation_id")),
    ],
)
def test_invalid_backend_responses_fail_closed_and_leave_old_raw_intact(tmp_path, response) -> None:
    scenario = MockScenario(
        name="invalid_backend_response",
        backend_responses={"/backend-api/conversation/conv_mock_headers": response},
        request_snapshots=backend_header_scenario().request_snapshots,
    )
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_headers")
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")
    paths = store.ensure_conversation(ref)
    old_raw = {"mapping": {"old_node": {"parent": None}}, "current_node": "old_node"}
    paths.raw_mapping_json.write_text(json.dumps(old_raw, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(HumanActionNeededError):
        capture_conversation(tab, ref, store)

    assert json.loads(paths.raw_mapping_json.read_text(encoding="utf-8")) == old_raw
    assert paths.transcript_jsonl.read_text(encoding="utf-8") == ""


def _write_raw(tmp_path: Path, raw: dict[str, object]) -> Path:
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return raw_path


def _attachment_request_snapshot(conversation_id: str) -> RequestSnapshot:
    return RequestSnapshot(
        url=f"https://chatgpt.com/backend-api/conversation/{conversation_id}",
        method="GET",
        headers=dict(HEADER_CANARIES),
    )


def _backend_request_snapshot(path: str, *, headers: dict[str, str] | None = None) -> RequestSnapshot:
    return RequestSnapshot(
        url=f"https://chatgpt.com{path}",
        method="GET",
        headers=dict(headers or HEADER_CANARIES),
    )


def _headers_for_path(path: str, **overrides: str) -> dict[str, str]:
    headers = dict(HEADER_CANARIES)
    headers["x-openai-target-path"] = path
    headers.update(overrides)
    return headers


def _attachment_download_raw(
    conversation_id: str,
    *,
    user_metadata: dict[str, object] | None = None,
    assistant_metadata: dict[str, object] | None = None,
    assistant_content_extra: dict[str, object] | None = None,
) -> dict[str, object]:
    assistant_content: dict[str, object] = {"content_type": "text", "parts": ["assistant"]}
    if assistant_content_extra:
        assistant_content.update(assistant_content_extra)
    return {
        "conversation_id": conversation_id,
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["user"], "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "children": ["assistant"],
                "message": {
                    "id": "msg_user",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["prompt"]},
                    "metadata": user_metadata or {},
                    "status": "finished_successfully",
                },
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": {
                    "id": "msg_assistant",
                    "author": {"role": "assistant"},
                    "content": assistant_content,
                    "metadata": assistant_metadata or {},
                    "status": "finished_successfully",
                },
            },
        },
        "current_node": "assistant",
    }


def _scrape_attachment_fixture(tmp_path: Path, scenario: MockScenario, conversation_id: str):
    channel = MockChannel(scenario)
    session = Session(data_dir=tmp_path, channel=channel)
    transcript = session.scrape(ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}"), with_attachments=True)
    return channel, transcript


def test_scrape_uses_light_root_and_generic_backend_header_harvest(tmp_path) -> None:
    conversation_id = "conv_mock_light_scrape"
    scenario = MockScenario(
        name="light_scrape_generic_backend_harvest",
        backend_conversations={conversation_id: _attachment_download_raw(conversation_id)},
        request_snapshots=(
            _backend_request_snapshot(
                "/backend-api/accounts/check",
                headers=_headers_for_path("/backend-api/accounts/check"),
            ),
        ),
    )
    channel = MockChannel(scenario)
    session = Session(data_dir=tmp_path, channel=channel)

    transcript = session.scrape(ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}"))

    open_urls = [call.details["url"] for call in channel.calls if call.method == "open_tab"]
    fetch_urls = [call.details["url"] for call in channel.calls if call.method == "fetch_in_page"]
    assert open_urls == ["https://chatgpt.com/"]
    assert all(f"/c/{conversation_id}" not in str(url) for url in open_urls)
    assert fetch_urls == [f"/backend-api/conversation/{conversation_id}"]
    assert [turn.role for turn in transcript.turns] == ["user", "assistant"]
    assert {turn.capture_source for turn in transcript.turns} == {"backend_api"}


def test_ambient_backend_header_harvest_skips_deficient_requests() -> None:
    conversation_id = "conv_mock_ambient_skip"
    deficient = _headers_for_path("/backend-api/accounts/check")
    deficient.pop("authorization")
    complete = _headers_for_path("/backend-api/models", authorization="Bearer MOCK_COMPLETE_REQUEST")
    scenario = MockScenario(
        name="ambient_skip_deficient",
        request_snapshots=(
            _backend_request_snapshot("/backend-api/accounts/check", headers=deficient),
            _backend_request_snapshot("/backend-api/models", headers=complete),
        ),
    )
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/")
    conv = ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}")

    bundle = acquire_backend_headers(tab, conv, mode="ambient_backend", timeout_s=0.0)

    headers = bundle.for_single_fetch()
    assert headers["authorization"] == "Bearer MOCK_COMPLETE_REQUEST"
    assert headers["x-openai-target-path"] == "/backend-api/models"
    assert channel.method_counts["header_acquisitions"] == 1


def test_conversation_harvest_default_ignores_generic_backend_requests() -> None:
    conversation_id = "conv_mock_exact_default"
    generic = _headers_for_path("/backend-api/accounts/check", authorization="Bearer MOCK_GENERIC_REQUEST")
    exact = _headers_for_path(
        f"/backend-api/conversation/{conversation_id}",
        authorization="Bearer MOCK_EXACT_CONVERSATION_REQUEST",
    )
    scenario = MockScenario(
        name="exact_default_ignores_generic",
        request_snapshots=(
            _backend_request_snapshot("/backend-api/accounts/check", headers=generic),
            _backend_request_snapshot(f"/backend-api/conversation/{conversation_id}", headers=exact),
        ),
    )
    channel = MockChannel(scenario)
    tab = channel.open_tab(f"https://chatgpt.com/c/{conversation_id}")
    conv = ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}")

    bundle = acquire_backend_headers(tab, conv, timeout_s=0.0)

    assert bundle.for_single_fetch()["authorization"] == "Bearer MOCK_EXACT_CONVERSATION_REQUEST"


def test_conversation_fetch_retargets_harvested_target_path(tmp_path) -> None:
    conversation_id = "conv_mock_retarget_path"
    harvested_path = "/backend-api/accounts/check"
    harvested_route = "MOCK_HARVESTED_ROUTE_KEEP_VERBATIM"

    class RecordingChannel(MockChannel):
        def __init__(self, scenario: MockScenario) -> None:
            super().__init__(scenario)
            self.full_conversation_headers: list[dict[str, str]] = []

        def fetch_in_page(self, tab, url, *, method="GET", headers=None, body=None, stream_to=None, timeout_s=None):  # noqa: ANN001, ANN201
            if url == f"/backend-api/conversation/{conversation_id}":
                self.full_conversation_headers.append(dict(headers or {}))
            return super().fetch_in_page(
                tab,
                url,
                method=method,
                headers=headers,
                body=body,
                stream_to=stream_to,
                timeout_s=timeout_s,
            )

    scenario = MockScenario(
        name="retarget_conversation_fetch_headers",
        backend_conversations={conversation_id: _attachment_download_raw(conversation_id)},
        request_snapshots=(
            _backend_request_snapshot(
                harvested_path,
                headers=_headers_for_path(harvested_path, **{"x-openai-target-route": harvested_route}),
            ),
        ),
    )
    channel = RecordingChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/")
    conv = ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}")

    capture_conversation(tab, conv, Store(data_dir=tmp_path), header_mode="ambient_backend")

    assert channel.full_conversation_headers
    fetch_headers = channel.full_conversation_headers[0]
    assert fetch_headers["x-openai-target-path"] == f"/backend-api/conversation/{conversation_id}"
    assert fetch_headers["x-openai-target-route"] == harvested_route


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


def test_mock_request_snapshots_can_require_reload_before_header_capture() -> None:
    # Falsifiability: removing the mock reload gate makes the pre-reload header acquisition succeed unexpectedly.
    conversation_id = "conv_mock_requires_reload"
    scenario = MockScenario(
        name="request_requires_reload",
        requests_require_reload=True,
        request_snapshots=(_attachment_request_snapshot(conversation_id),),
    )
    channel = MockChannel(scenario)
    tab = channel.open_tab(f"https://chatgpt.com/c/{conversation_id}")
    conv = ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}")

    with pytest.raises(BackendAuthUnavailableError):
        acquire_backend_headers(tab, conv, timeout_s=0.0)

    channel.reload(tab)
    bundle = acquire_backend_headers(tab, conv, timeout_s=0.0)

    assert set(bundle.for_single_fetch()) == set(HEADER_CANARIES)
    assert channel.method_counts.get("reload", 0) == 1


def test_large_current_branch_linearizes_iteratively_excludes_hidden_and_preserves_parts_math(tmp_path) -> None:
    raw = large_mapping_raw()
    raw["mapping"]["node_0005"]["message"].pop("create_time")
    raw["mapping"]["node_0005"]["message"].pop("id")
    raw_path = _write_raw(tmp_path, raw)
    conv = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")

    top = validate_backend_shape(raw_path, "conv_mock_headers")
    records = tuple(iter_current_branch_records(raw_path, conv))

    assert top.mapping_node_count == 5003
    assert len(current_branch_ids(raw)) == 5001
    assert [record.message_id for record in records] == [
        "msg_user_1",
        "msg_assistant_single",
        "msg_user_empty",
        "msg_assistant_multi",
        "node_0005",
    ]
    assert [record.turn_index for record in records] == [0, 1, 2, 3, 4]
    assert [record.content_markdown for record in records] == [
        "Fixture prompt",
        CONTENT_PARTS_EXPECTED["single"],
        CONTENT_PARTS_EXPECTED["empty"],
        CONTENT_PARTS_EXPECTED["multi"],
        CONTENT_PARTS_EXPECTED["math_markdown"],
    ]
    assert records[3].content_markdown == "alphabeta\ngamma"
    assert "\\widehat{x}" in records[4].content_markdown
    assert "\\ne y" in records[4].content_markdown
    assert "\\neq z" in records[4].content_markdown
    assert "\\frac{}{}" in records[4].content_markdown
    assert "≠" not in records[4].content_markdown
    assert records[4].created_at is None
    assert records[4].parent_id == "node_0004"
    transcript_text = "\n".join(record.content_markdown for record in records)
    assert "hidden current-branch reasoning" not in transcript_text
    assert "print(1000)" not in transcript_text
    assert "side branch answer" not in transcript_text
    raw_text = raw_path.read_text(encoding="utf-8")
    assert "hidden current-branch reasoning" in raw_text
    assert "side branch answer" in raw_text


def test_message_level_model_slug_overrides_top_level_default(tmp_path) -> None:
    raw = large_mapping_raw()
    raw["default_model_slug"] = "top-level-default"
    raw["mapping"]["node_0002"]["message"]["metadata"]["model_slug"] = "message-level-model"
    raw_path = _write_raw(tmp_path, raw)
    conv = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")

    records = tuple(iter_current_branch_records(raw_path, conv))
    by_id = {record.message_id: record for record in records}

    assert by_id["msg_user_1"].model is not None
    assert by_id["msg_user_1"].model.slug == "top-level-default"
    assert by_id["msg_assistant_single"].model is not None
    assert by_id["msg_assistant_single"].model.slug == "message-level-model"


def _malformed_capture_variants() -> dict[str, dict[str, object]]:
    variants = dict(malformed_mapping_variants())
    non_list = large_mapping_raw(conversation_id="conv_mock_non_list_part", leaf_index=5)
    non_list["mapping"]["node_0005"]["message"]["content"]["parts"] = "not a list"
    variants["non_list_parts"] = non_list
    return variants


@pytest.mark.parametrize("name, raw", _malformed_capture_variants().items())
def test_malformed_current_branch_and_non_string_visible_parts_fail_closed(tmp_path, name, raw) -> None:
    raw_path = _write_raw(tmp_path, raw)
    conv = ConversationRef(raw["conversation_id"], f"https://chatgpt.com/c/{raw['conversation_id']}")

    with pytest.raises(BackendCaptureShapeError):
        tuple(iter_current_branch_records(raw_path, conv))


def test_deep_research_requires_same_exchange_conjunction_and_attaches_hidden_refs(tmp_path) -> None:
    scenarios = deep_research_scenarios()
    positive_path = _write_raw(tmp_path, scenarios["positive"])
    positive_conv = ConversationRef("conv_dr_positive", "https://chatgpt.com/c/conv_dr_positive")

    positive_records = tuple(iter_current_branch_records(positive_path, positive_conv))
    final = positive_records[-1]

    assert final.kind == "deep_research"
    assert "deep_research" in final.active_tools
    assert "hidden reasoning" not in final.content_markdown
    assert {attachment.source_kind for attachment in final.attachments} >= {"generated_asset", "code_execution_output"}
    assert {citation.source for citation in final.citations} >= {"citations", "content_references", "search_result_groups"}

    for name, raw in scenarios.items():
        if name == "positive":
            continue
        raw_path = _write_raw(tmp_path, raw)
        conv_id = raw["conversation_id"]
        conv = ConversationRef(conv_id, f"https://chatgpt.com/c/{conv_id}")
        records = tuple(iter_current_branch_records(raw_path, conv))
        assert all(record.kind == "normal" for record in records), name
        assert all("deep_research" not in record.active_tools for record in records), name


def test_all_attachment_shapes_and_citations_normalize_separately_without_download_state_pollution(tmp_path) -> None:
    raw = attachment_citation_raw()
    raw_path = _write_raw(tmp_path, raw)
    conv = ConversationRef("conv_mock_mixed_attachments", "https://chatgpt.com/c/conv_mock_mixed_attachments")

    records = tuple(iter_current_branch_records(raw_path, conv))
    all_attachments = [attachment for record in records for attachment in record.attachments]
    all_citations = [citation for record in records for citation in record.citations]

    assert {attachment.source_kind for attachment in all_attachments} == {
        "user_upload",
        "file_reference",
        "generated_asset",
        "code_execution_output",
    }
    code_outputs = [attachment for attachment in all_attachments if attachment.source_kind == "code_execution_output"]
    assert code_outputs[0].source_ref == "run_mock_code_1"
    assert code_outputs[0].filename == "run_run_mock_code_1_aggregate.json"
    assert code_outputs[0].mime == "application/json"
    assert all(attachment.download_state == "pending" for attachment in all_attachments)
    assert all(attachment.local_path is None for attachment in all_attachments)
    assert all(attachment.sha256 is None for attachment in all_attachments)
    assert not any("/backend-api/files" in repr(attachment) for attachment in all_attachments)
    assert {citation.source for citation in all_citations} == {
        "citations",
        "content_references",
        "search_result_groups",
    }
    assert not any(hasattr(citation, "download_state") for citation in all_citations)
    assert not any(citation.url == "file_reference_1" for citation in all_citations)
    assert "mock search query" not in repr(all_citations)


def test_scrape_with_attachments_downloads_bytes_and_rewrites_local_path(tmp_path) -> None:
    conversation_id = "conv_mock_attachment_download"
    payload = b"downloaded attachment bytes"
    download_url = "https://chatgpt.com/backend-api/mock-downloads/downloadable"
    raw = _attachment_download_raw(
        conversation_id,
        user_metadata={
            "attachments": [
                {
                    "id": "file_mock_downloadable",
                    "name": "downloadable.txt",
                    "mime_type": "text/plain",
                    "size": len(payload),
                }
            ]
        },
    )
    scenario = MockScenario(
        name="attachment_download",
        backend_conversations={conversation_id: raw},
        request_snapshots=(_attachment_request_snapshot(conversation_id),),
        file_downloads={
            "file_mock_downloadable": MockBackendResponse(
                200,
                {
                    "download_url": download_url,
                    "file_size_bytes": len(payload),
                    "mime_type": "text/plain",
                    "file_name": "downloadable.txt",
                    "status": "success",
                },
            )
        },
        download_responses={download_url: MockBackendResponse(200, payload, headers={"content-type": "text/plain"})},
    )

    channel, transcript = _scrape_attachment_fixture(tmp_path, scenario, conversation_id)

    attachment = transcript.turns[0].attachments[0]
    assert attachment.download_state == "downloaded"
    assert attachment.local_path is not None
    assert attachment.metadata == {}
    cached = tmp_path / "conversations" / conversation_id / attachment.local_path
    assert cached.exists()
    assert cached.parent == tmp_path / "conversations" / conversation_id / "attachments"
    assert cached.read_bytes() == payload
    assert channel.method_counts["attachment_descriptor_fetches"] == 1
    assert channel.method_counts["attachment_byte_fetches"] == 1


def test_attachment_200_error_json_without_download_url_is_not_downloadable(tmp_path) -> None:
    conversation_id = "conv_mock_attachment_error_json"
    raw = _attachment_download_raw(
        conversation_id,
        user_metadata={
            "attachments": [
                {
                    "id": "file_mock_error_json",
                    "name": "not-downloadable.txt",
                    "mime_type": "text/plain",
                    "size": 12,
                }
            ]
        },
    )
    scenario = MockScenario(
        name="attachment_200_error_json",
        backend_conversations={conversation_id: raw},
        request_snapshots=(_attachment_request_snapshot(conversation_id),),
        file_downloads={
            "file_mock_error_json": MockBackendResponse(
                200,
                {
                    "error_code": "mock_error",
                    "error_message": "mock 200 error shape",
                    "error_type": "not_found",
                    "status": "error",
                },
            )
        },
    )

    channel, transcript = _scrape_attachment_fixture(tmp_path, scenario, conversation_id)

    attachment = transcript.turns[0].attachments[0]
    assert attachment.download_state == "not_downloadable"
    assert attachment.local_path is None
    assert channel.method_counts["attachment_descriptor_fetches"] == 1
    assert channel.method_counts.get("attachment_byte_fetches", 0) == 0
    assert list((tmp_path / "conversations" / conversation_id / "attachments").iterdir()) == []


def test_unsupported_attachment_kinds_and_schemes_skip_download_fetches(tmp_path) -> None:
    conversation_id = "conv_mock_attachment_unsupported"
    raw = _attachment_download_raw(
        conversation_id,
        assistant_metadata={"aggregate_result": {"run_id": "run_mock_unsupported", "status": "success"}},
        assistant_content_extra={
            "assets": [
                {
                    "asset_pointer": "sediment://mock-without-token",
                    "filename": "unsupported.bin",
                    "content_type": "application/octet-stream",
                }
            ]
        },
    )
    scenario = MockScenario(
        name="attachment_unsupported",
        backend_conversations={conversation_id: raw},
        request_snapshots=(_attachment_request_snapshot(conversation_id),),
    )

    channel, transcript = _scrape_attachment_fixture(tmp_path, scenario, conversation_id)

    states = [attachment.download_state for turn in transcript.turns for attachment in turn.attachments]
    assert states == ["unsupported", "unsupported"]
    assert channel.method_counts.get("attachment_descriptor_fetches", 0) == 0
    assert channel.method_counts.get("attachment_byte_fetches", 0) == 0
    assert list((tmp_path / "conversations" / conversation_id / "attachments").iterdir()) == []


def test_attachment_downloads_are_deduped_by_resolved_file_id(tmp_path) -> None:
    conversation_id = "conv_mock_attachment_dedup"
    payload = b"dedup bytes"
    download_url = "https://chatgpt.com/backend-api/mock-downloads/dedup"
    raw = _attachment_download_raw(
        conversation_id,
        user_metadata={
            "attachments": [
                {
                    "id": "file_mock_dedup",
                    "name": "first.txt",
                    "mime_type": "text/plain",
                    "size": len(payload),
                }
            ]
        },
        assistant_metadata={
            "content_references": [
                {
                    "type": "file",
                    "id": "file_mock_dedup",
                    "name": "second.txt",
                    "mime_type": "text/plain",
                    "size": len(payload),
                }
            ]
        },
    )
    scenario = MockScenario(
        name="attachment_dedup",
        backend_conversations={conversation_id: raw},
        request_snapshots=(_attachment_request_snapshot(conversation_id),),
        file_downloads={
            "file_mock_dedup": MockBackendResponse(
                200,
                {
                    "download_url": download_url,
                    "file_size_bytes": len(payload),
                    "mime_type": "text/plain",
                    "status": "success",
                },
            )
        },
        download_responses={download_url: MockBackendResponse(200, payload, headers={"content-type": "text/plain"})},
    )

    channel, transcript = _scrape_attachment_fixture(tmp_path, scenario, conversation_id)

    attachments = [attachment for turn in transcript.turns for attachment in turn.attachments]
    assert [attachment.download_state for attachment in attachments] == ["downloaded", "downloaded"]
    assert attachments[0].local_path is not None
    assert attachments[0].local_path == attachments[1].local_path
    assert channel.method_counts["attachment_descriptor_fetches"] == 1
    assert channel.method_counts["attachment_byte_fetches"] == 1
    cached = tmp_path / "conversations" / conversation_id / attachments[0].local_path
    assert cached.read_bytes() == payload


def test_scrape_without_attachments_keeps_pending_refs_and_does_not_fetch_bytes(tmp_path) -> None:
    conversation_id = "conv_mock_attachment_default_noop"
    raw = _attachment_download_raw(
        conversation_id,
        user_metadata={
            "attachments": [
                {
                    "id": "file_mock_default_noop",
                    "name": "default.txt",
                    "mime_type": "text/plain",
                    "size": 3,
                }
            ]
        },
    )
    scenario = MockScenario(
        name="attachment_default_noop",
        backend_conversations={conversation_id: raw},
        request_snapshots=(_attachment_request_snapshot(conversation_id),),
        file_downloads={
            "file_mock_default_noop": MockBackendResponse(
                200,
                {"download_url": "https://chatgpt.com/backend-api/mock-downloads/default", "file_size_bytes": 3},
            )
        },
    )
    channel = MockChannel(scenario)
    session = Session(data_dir=tmp_path, channel=channel)

    transcript = session.scrape(ConversationRef(conversation_id, f"https://chatgpt.com/c/{conversation_id}"))

    attachment = transcript.turns[0].attachments[0]
    assert attachment.download_state == "pending"
    assert attachment.local_path is None
    assert channel.method_counts.get("attachment_descriptor_fetches", 0) == 0
    assert channel.method_counts.get("attachment_byte_fetches", 0) == 0
    assert list((tmp_path / "conversations" / conversation_id / "attachments").iterdir()) == []


def test_header_bundle_is_one_use_and_header_canaries_do_not_persist_on_failed_capture(tmp_path) -> None:
    scenario = backend_header_scenario()
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_headers")
    conv = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")

    bundle = acquire_backend_headers(tab, conv)
    first_headers = bundle.for_single_fetch()

    assert set(first_headers) >= set(HEADER_CANARIES)
    with pytest.raises(BackendAuthUnavailableError):
        bundle.for_single_fetch()
    for canary in HEADER_CANARIES.values():
        assert canary not in repr(bundle)
        assert canary not in str(bundle)
        assert canary not in repr(bundle.redacted())

    failing = MockScenario(
        name="header_canary_failed_capture",
        backend_conversations={"conv_mock_headers": large_mapping_raw(conversation_id="wrong_conversation_id")},
        request_snapshots=backend_header_scenario().request_snapshots,
    )
    failing_channel = MockChannel(failing)
    failing_tab = failing_channel.open_tab("https://chatgpt.com/c/conv_mock_headers")
    store = Store(data_dir=tmp_path)
    with pytest.raises(HumanActionNeededError) as error_info:
        capture_conversation(failing_tab, conv, store)

    scan_strings = [str(error_info.value), repr(error_info.value), repr(error_info.value.details), repr(failing_channel.calls)]
    scan_strings.extend(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*") if path.is_file())
    for canary in HEADER_CANARIES.values():
        assert all(canary not in text for text in scan_strings)


def test_capture_429_raises_rate_limited_and_never_uses_ui_fallback(tmp_path) -> None:
    from ask_chatgpt.errors import RateLimitedError

    scenario = MockScenario(
        name="capture_429_rate_limited",
        backend_responses={
            "/backend-api/conversation/conv_mock_headers": MockBackendResponse(
                429,
                {"detail": "too many requests"},
                headers={"retry-after": "77"},
            )
        },
        request_snapshots=backend_header_scenario().request_snapshots,
        clipboard_permission="granted",
        clipboard_text="clipboard fallback must not be used",
    )
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_headers")
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("conv_mock_headers", "https://chatgpt.com/c/conv_mock_headers")

    with pytest.raises(RateLimitedError) as excinfo:
        capture_conversation(tab, ref, store)

    assert excinfo.value.details["retry_after_s"] == 77
    assert channel.method_counts.get("read_clipboard", 0) == 0
    assert not any(
        turn.capture_source in {"copy_button", "dom_text", "katex_annotation"}
        for turn in store.load_transcript(ref, include_pending=True).turns
    )


def test_fallback_requires_clipboard_grant_and_explicit_copy_is_not_canonical(tmp_path) -> None:
    conv = ConversationRef("conv_mock_fallback", "https://chatgpt.com/c/conv_mock_fallback")
    default_channel = MockChannel()
    default_tab = default_channel.open_tab("https://chatgpt.com/c/conv_mock_fallback")

    with pytest.raises(HumanActionNeededError) as error_info:
        fallback_capture_ui(default_tab, conv, Store(data_dir=tmp_path / "blocked"), reason="shape")

    assert error_info.value.details["reason"] == "clipboard_permission"
    assert default_channel.method_counts.get("read_clipboard", 0) == 0

    allowed_channel = MockChannel(safety_scenarios()["clipboard_allowed"])
    allowed_tab = allowed_channel.open_tab("https://chatgpt.com/c/conv_mock_fallback")
    result = fallback_capture_ui(
        allowed_tab,
        conv,
        Store(data_dir=tmp_path / "allowed"),
        reason="shape",
        allow_clipboard=True,
    )

    turn = result.transcript.turns[0]
    assert turn.content_markdown == "offline copied markdown"
    assert turn.capture_source == "copy_button"
    assert turn.fidelity == "ui_copy"
    assert turn.status == "complete"
    assert turn.partial is False
    assert result.source == "copy_button"
    assert result.fidelity == "ui_copy"


def test_fallback_marks_katex_and_dom_salvage_degraded_and_fails_closed_when_empty(tmp_path) -> None:
    conv = ConversationRef("conv_mock_fallback", "https://chatgpt.com/c/conv_mock_fallback")
    katex_channel = MockChannel(
        MockScenario(
            name="katex_salvage",
            clipboard_permission="denied",
            evaluations={
                "ask_chatgpt_capture_katex_annotations": ["\\widehat{x}", " ", "\\ne", " ", "\\frac{}{}"],
                "ask_chatgpt_capture_dom_text": "lossy dom should not be used after katex",
            },
        )
    )
    katex_tab = katex_channel.open_tab("https://chatgpt.com/c/conv_mock_fallback")

    katex_result = fallback_capture_ui(
        katex_tab,
        conv,
        Store(data_dir=tmp_path / "katex"),
        reason="shape",
        allow_clipboard=True,
    )

    katex_turn = katex_result.transcript.turns[0]
    assert katex_turn.content_markdown == "\\widehat{x} \\ne \\frac{}{}"
    assert katex_turn.capture_source == "katex_annotation"
    assert katex_turn.fidelity == "math_annotation_reconstructed"
    assert katex_turn.status == "partial"
    assert katex_turn.partial is True

    dom_channel = MockChannel(
        MockScenario(
            name="dom_salvage",
            clipboard_permission="denied",
            evaluations={"ask_chatgpt_capture_dom_text": "lossy visible DOM text"},
        )
    )
    dom_tab = dom_channel.open_tab("https://chatgpt.com/c/conv_mock_fallback")

    dom_result = fallback_capture_ui(
        dom_tab,
        conv,
        Store(data_dir=tmp_path / "dom"),
        reason="shape",
        allow_clipboard=True,
    )

    dom_turn = dom_result.transcript.turns[0]
    assert dom_turn.content_markdown == "lossy visible DOM text"
    assert dom_turn.capture_source == "dom_text"
    assert dom_turn.fidelity == "lossy_dom_text"
    assert dom_turn.status == "partial"
    assert dom_turn.partial is True

    empty_channel = MockChannel(MockScenario(name="empty_fallback", clipboard_permission="denied"))
    empty_tab = empty_channel.open_tab("https://chatgpt.com/c/conv_mock_fallback")
    with pytest.raises(CaptureFailedClosedError):
        fallback_capture_ui(
            empty_tab,
            conv,
            Store(data_dir=tmp_path / "empty"),
            reason="shape",
            allow_clipboard=True,
        )
