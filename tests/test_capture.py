from __future__ import annotations

import json
from pathlib import Path

import pytest

from ask_chatgpt.capture import (
    acquire_backend_headers,
    capture_conversation,
    fallback_capture_ui,
    iter_current_branch_records,
    validate_backend_shape,
)
from ask_chatgpt.channels.mock import HEADER_CANARIES, MockBackendResponse, MockChannel, MockScenario
from ask_chatgpt.errors import (
    BackendAuthUnavailableError,
    BackendCaptureShapeError,
    CaptureFailedClosedError,
    HumanActionNeededError,
)
from ask_chatgpt.identity import ConversationRef
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
