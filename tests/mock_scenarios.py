"""Reusable offline MockChannel scenarios for M4-E3 and later E4/E5 tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ask_chatgpt.channels.base import RequestSnapshot, TurnDom, TurnDomSnapshot
from ask_chatgpt.channels.mock import (
    HEADER_CANARIES,
    MockBackendResponse,
    MockScenario,
    TimedBackendResponse,
    TimedSelectorPresence,
    TimedTurnSnapshot,
)

COMPOSER_SELECTOR = "#prompt-textarea"
SEND_BUTTON_SELECTOR = "button[data-testid=\"send-button\"], #composer-submit-button"
CONVERSATION_URL = "https://chatgpt.com/c/conv_mock_headers"

CONTENT_PARTS_EXPECTED: dict[str, str] = {
    "empty": "",
    "single": "Single visible string",
    "multi": "alphabeta\ngamma",
    "math_markdown": (
        "  Math tokens: \\widehat{x} \\ne y and a synonym \\neq z with \\frac{}{} .\n\n"
        "| left | right |\n| --- | --- |\n| α | β |\n\n"
        "```python\nprint('unicode π')\n```\n\nTrailing snowman ☃  "
    ),
}


def _message(
    message_id: str,
    role: str,
    content: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
    status: str = "finished_successfully",
) -> dict[str, Any]:
    return {
        "id": message_id,
        "author": {"role": role},
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "content": content,
        "metadata": metadata or {},
        "status": status,
    }


def _node(
    node_id: str,
    parent: str | None,
    *,
    message: dict[str, Any] | None = None,
    children: list[str] | None = None,
) -> dict[str, Any]:
    return {"id": node_id, "parent": parent, "children": children or [], "message": message}


def _text_message(
    message_id: str,
    role: str,
    parts: list[Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _message(
        message_id,
        role,
        {"content_type": "text", "parts": parts},
        metadata=metadata,
    )


def _hidden_metadata(exchange_id: str | None = None, **extra: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {"is_visually_hidden_from_conversation": True}
    if exchange_id is not None:
        metadata["turn_exchange_id"] = exchange_id
    metadata.update(extra)
    return metadata


def large_mapping_raw(
    *, conversation_id: str = "conv_mock_headers", leaf_index: int = 5000
) -> dict[str, Any]:
    """Generate a deterministic ~5k-node current branch with out-of-order keys."""

    nodes: dict[str, dict[str, Any]] = {}
    for index in range(leaf_index + 1):
        node_id = f"node_{index:04d}"
        parent = f"node_{index - 1:04d}" if index else None
        children = [f"node_{index + 1:04d}"] if index < leaf_index else []
        message: dict[str, Any] | None = None
        if index == 1:
            message = _text_message("msg_user_1", "user", ["Fixture prompt"])
        elif index == 2:
            message = _text_message(
                "msg_assistant_single",
                "assistant",
                [CONTENT_PARTS_EXPECTED["single"]],
            )
        elif index == 3:
            message = _text_message("msg_user_empty", "user", [])
        elif index == 4:
            message = _text_message(
                "msg_assistant_multi",
                "assistant",
                ["alpha", "", "beta", "\n", "gamma"],
            )
        elif index == 5:
            message = _text_message(
                "msg_assistant_math",
                "assistant",
                [CONTENT_PARTS_EXPECTED["math_markdown"]],
            )
        elif index == 2500:
            message = _message(
                "msg_hidden_thoughts_2500",
                "assistant",
                {"content_type": "thoughts", "thoughts": "hidden current-branch reasoning"},
                metadata=_hidden_metadata("exchange_large"),
            )
        elif index in {1000, 2000, 3000, 4000}:
            message = _message(
                f"msg_hidden_code_{index}",
                "assistant",
                {"content_type": "code", "text": f"print({index})"},
                metadata=_hidden_metadata("exchange_large"),
            )
        nodes[node_id] = _node(node_id, parent, message=message, children=children)

    nodes["node_0002"]["children"].append("side_user_1")
    nodes["side_user_1"] = _node(
        "side_user_1",
        "node_0002",
        message=_text_message("msg_side_user", "user", ["side branch prompt"]),
        children=["side_assistant_1"],
    )
    nodes["side_assistant_1"] = _node(
        "side_assistant_1",
        "side_user_1",
        message=_text_message("msg_side_assistant", "assistant", ["side branch answer"]),
    )

    out_of_order_keys = [
        f"node_{leaf_index:04d}",
        "side_assistant_1",
        "side_user_1",
        *[f"node_{index:04d}" for index in range(0, leaf_index)],
    ]
    mapping = {key: nodes[key] for key in out_of_order_keys}
    return {
        "conversation_id": conversation_id,
        "title": "Mock 5k mapping",
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_001_200.0,
        "mapping": mapping,
        "current_node": f"node_{leaf_index:04d}",
        "default_model_slug": "gpt-5.5-pro",
        "async_status": None,
    }


def current_branch_ids(raw: dict[str, Any]) -> list[str]:
    mapping = raw["mapping"]
    node_id = raw["current_node"]
    branch: list[str] = []
    seen: set[str] = set()
    while node_id:
        if node_id in seen:
            raise ValueError("cycle in fixture parent chain")
        seen.add(node_id)
        branch.append(node_id)
        node_id = mapping[node_id].get("parent")
    return list(reversed(branch))


def malformed_mapping_variants() -> dict[str, dict[str, Any]]:
    return {
        "cycle": {
            "conversation_id": "conv_mock_cycle",
            "mapping": {
                "cycle_a": _node("cycle_a", "cycle_b", message=_text_message("msg_cycle_a", "user", ["a"])),
                "cycle_b": _node("cycle_b", "cycle_a", message=_text_message("msg_cycle_b", "assistant", ["b"])),
            },
            "current_node": "cycle_b",
        },
        "broken_parent": {
            "conversation_id": "conv_mock_broken_parent",
            "mapping": {
                "broken_child": _node(
                    "broken_child",
                    "missing_parent",
                    message=_text_message("msg_broken", "assistant", ["broken"]),
                )
            },
            "current_node": "broken_child",
        },
        "invalid_current_node": {
            "conversation_id": "conv_mock_invalid_current",
            "mapping": {"root": _node("root", None)},
            "current_node": "missing_current_node",
        },
        "non_string_part": {
            "conversation_id": "conv_mock_non_string_part",
            "mapping": {
                "root": _node("root", None, children=["bad_parts"]),
                "bad_parts": _node(
                    "bad_parts",
                    "root",
                    message=_text_message("msg_bad_parts", "assistant", ["ok", 7]),
                ),
            },
            "current_node": "bad_parts",
        },
    }


def backend_header_scenario() -> MockScenario:
    raw = large_mapping_raw(conversation_id="conv_mock_headers")
    return MockScenario(
        name="backend_header_requirements",
        backend_conversations={"conv_mock_headers": raw},
        request_snapshots=(
            RequestSnapshot(
                url="https://chatgpt.com/backend-api/conversation/conv_mock_headers",
                method="GET",
                headers=dict(HEADER_CANARIES),
            ),
        ),
    )


def _dr_raw(
    name: str,
    *,
    hidden_count: int = 32,
    include_hidden: bool = True,
    include_citations: bool = True,
    include_final: bool = True,
    mismatch_exchange: bool = False,
) -> dict[str, Any]:
    exchange_id = f"exchange_{name}"
    nodes: dict[str, dict[str, Any]] = {
        "root": _node("root", None, children=["dr_user"]),
        "dr_user": _node(
            "dr_user",
            "root",
            message=_text_message(
                "msg_dr_user",
                "user",
                ["Please perform deep research."],
                metadata={"turn_exchange_id": exchange_id},
            ),
            children=[],
        ),
    }
    previous = "dr_user"
    if include_hidden:
        for index in range(hidden_count):
            node_id = f"dr_hidden_{index:02d}"
            nodes[previous]["children"].append(node_id)
            hidden_exchange = f"other_exchange_{index}" if mismatch_exchange else exchange_id
            if index == 1:
                content = {
                    "content_type": "tether_browsing_display",
                    "assets": [
                        {
                            "content_type": "image/png",
                            "asset_pointer": "asset_pointer_dr_generated",
                            "size_bytes": 12345,
                            "width": 640,
                            "height": 480,
                            "metadata": {"SANITIZED_METADATA_CANARY": "visible-only-after-redaction"},
                        }
                    ],
                }
                role = "tool"
                metadata = _hidden_metadata(hidden_exchange, turn_exchange_id=hidden_exchange)
            elif index == 2:
                content = {"content_type": "execution_output", "text": "execution result"}
                role = "tool"
                metadata = _hidden_metadata(
                    hidden_exchange,
                    aggregate_result={"run_id": "run_dr_code", "status": "success", "messages": []},
                )
            elif index % 3 == 0:
                content = {"content_type": "code", "text": "print('analysis')"}
                role = "assistant"
                metadata = _hidden_metadata(hidden_exchange)
            else:
                content = {"content_type": "thoughts", "thoughts": "hidden reasoning"}
                role = "assistant"
                metadata = _hidden_metadata(hidden_exchange)
            nodes[node_id] = _node(
                node_id,
                previous,
                message=_message(f"msg_{node_id}", role, content, metadata=metadata),
                children=[],
            )
            previous = node_id
    if include_final:
        nodes[previous]["children"].append("dr_final")
        metadata: dict[str, Any] = {"turn_exchange_id": exchange_id}
        if include_citations:
            metadata.update(
                {
                    "citations": [
                        {
                            "start_ix": 0,
                            "end_ix": 10,
                            "citation_format_type": "webpage",
                            "metadata": {"url": "https://example.invalid/dr-citation"},
                        }
                    ],
                    "content_references": [
                        {"type": "grouped_webpages", "items": [{"url": "https://example.invalid/dr-source"}]},
                        {"type": "sources_footnote", "sources": [{"title": "Source"}]},
                    ],
                    "search_result_groups": [{"title": "Displayed source group", "entries": []}],
                    "search_queries": ["deep research mock query"],
                }
            )
        nodes["dr_final"] = _node(
            "dr_final",
            previous,
            message=_text_message(
                "msg_dr_final",
                "assistant",
                ["Final deep research report with visible citations."],
                metadata=metadata,
            ),
        )
        current_node = "dr_final"
    else:
        current_node = previous
    return {
        "conversation_id": f"conv_{name}",
        "mapping": nodes,
        "current_node": current_node,
        "default_model_slug": "gpt-5.5-pro",
    }


def deep_research_scenarios() -> dict[str, dict[str, Any]]:
    synthetic = {
        "conversation_id": "conv_synthetic_lone_deep_research_content_type",
        "mapping": {
            "root": _node("root", None, children=["synthetic"]),
            "synthetic": _node(
                "synthetic",
                "root",
                message=_message(
                    "msg_synthetic_deep_research",
                    "assistant",
                    {"content_type": "deep_research", "parts": ["label alone is not enough"]},
                ),
            ),
        },
        "current_node": "synthetic",
    }
    return {
        "positive": _dr_raw("dr_positive"),
        "missing_citations": _dr_raw("dr_missing_citations", include_citations=False),
        "missing_final_assistant": _dr_raw("dr_missing_final", include_final=False),
        "missing_hidden_internals": _dr_raw("dr_missing_hidden", include_hidden=False),
        "mismatched_exchange_ids": _dr_raw("dr_mismatched_exchange", mismatch_exchange=True),
        "synthetic_lone_deep_research_content_type": synthetic,
    }


def attachment_citation_raw() -> dict[str, Any]:
    exchange_id = "exchange_mixed_attachment"
    user_upload = {
        "id": "file_user_upload_1",
        "size": 42,
        "name": "visible-upload.txt",
        "file_token_size": 9,
        "source": "user_upload",
        "is_big_paste": False,
        "SANITIZED_METADATA_CANARY": "metadata-canary-visible-user",
        "raw_path": "/tmp/ask-chatgpt-mock-never-open",
    }
    file_ref = {
        "type": "file",
        "id": "file_reference_1",
        "name": "reference.pdf",
        "source": "library",
        "snippet": "long snippet retained in raw",
        "cloud_doc_url": "https://invalid.invalid/mock-never-fetch",
        "library_file_id": "library_file_1",
        "library_artifact_type": "document",
        "input_pointer": {"file_index": 0, "line_start": 1, "line_end": 5},
        "fff_metadata": {"SANITIZED_METADATA_CANARY": "file-ref-canary"},
        "connector_id": "connector_mock",
    }
    grouped_webpages = {
        "type": "grouped_webpages",
        "items": [{"title": "Grouped webpage", "url": "https://invalid.invalid/mock-never-fetch"}],
    }
    sources_footnote = {"type": "sources_footnote", "sources": [{"title": "Footnote source"}]}
    nodes = {
        "root": _node("root", None, children=["mixed_user"]),
        "mixed_user": _node(
            "mixed_user",
            "root",
            message=_text_message(
                "msg_mixed_user",
                "user",
                ["Please use the attached file."],
                metadata={"turn_exchange_id": exchange_id, "attachments": [user_upload]},
            ),
            children=["hidden_file_ref"],
        ),
        "hidden_file_ref": _node(
            "hidden_file_ref",
            "mixed_user",
            message=_message(
                "msg_hidden_file_ref",
                "assistant",
                {"content_type": "thoughts", "thoughts": "hidden file reasoning"},
                metadata=_hidden_metadata(exchange_id, content_references=[deepcopy(file_ref)]),
            ),
            children=["hidden_generated_asset"],
        ),
        "hidden_generated_asset": _node(
            "hidden_generated_asset",
            "hidden_file_ref",
            message=_message(
                "msg_hidden_generated_asset",
                "tool",
                {
                    "content_type": "tether_browsing_display",
                    "assets": [
                        {
                            "content_type": "image/png",
                            "asset_pointer": "asset_pointer_generated_asset_1",
                            "size_bytes": 2048,
                            "width": 320,
                            "height": 200,
                            "fovea": {"x": 0.5, "y": 0.5},
                            "metadata": {"SANITIZED_METADATA_CANARY": "generated-asset-canary"},
                        }
                    ],
                },
                metadata=_hidden_metadata(exchange_id),
            ),
            children=["hidden_code_output"],
        ),
        "hidden_code_output": _node(
            "hidden_code_output",
            "hidden_generated_asset",
            message=_message(
                "msg_hidden_code_output",
                "tool",
                {"content_type": "execution_output", "text": "aggregate result emitted"},
                metadata=_hidden_metadata(
                    exchange_id,
                    aggregate_result={
                        "run_id": "run_mock_code_1",
                        "status": "success",
                        "code": "print('mock')",
                        "messages": [],
                        "final_expression_output": "42",
                    },
                ),
            ),
            children=["mixed_final"],
        ),
        "mixed_final": _node(
            "mixed_final",
            "hidden_code_output",
            message=_text_message(
                "msg_mixed_final",
                "assistant",
                ["Visible answer with attachment refs and citations."],
                metadata={
                    "turn_exchange_id": exchange_id,
                    "content_references": [deepcopy(file_ref), grouped_webpages, sources_footnote],
                    "citations": [
                        {
                            "start_ix": 7,
                            "end_ix": 18,
                            "citation_format_type": "webpage",
                            "metadata": {"url": "https://invalid.invalid/mock-never-fetch"},
                        }
                    ],
                    "search_result_groups": [{"title": "Displayed search result", "entries": []}],
                    "search_queries": ["mock search query"],
                    "raw_path": "/tmp/ask-chatgpt-mock-never-open",
                    "SANITIZED_METADATA_CANARY": "visible-final-canary",
                },
            ),
        ),
    }
    return {
        "conversation_id": "conv_mock_mixed_attachments",
        "mapping": nodes,
        "current_node": "mixed_final",
        "mock_invalid_urls": ["https://invalid.invalid/mock-never-fetch"],
        "mock_invalid_paths": ["/tmp/ask-chatgpt-mock-never-open"],
    }


def _baseline_snapshot(*, stop_visible: bool = False, composer_visible: bool = True) -> TurnDomSnapshot:
    return TurnDomSnapshot(
        users=(TurnDom("baseline-user-1", "user", "baseline prompt"),),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=stop_visible,
        composer_visible=composer_visible,
        model_labels=("Pro Extended",),
    )


def send_ui_scenarios() -> dict[str, MockScenario]:
    absent = _baseline_snapshot(composer_visible=False)
    visible = _baseline_snapshot(composer_visible=True)
    successful = TurnDomSnapshot(
        users=(
            TurnDom("baseline-user-1", "user", "baseline prompt"),
            TurnDom("user-new-2", "user", "literal prompt"),
        ),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=True,
        composer_visible=True,
        model_labels=("Pro Extended",),
    )
    wrong = TurnDomSnapshot(
        users=(
            TurnDom("baseline-user-1", "user", "baseline prompt"),
            TurnDom("user-new-wrong", "user", "wrong text"),
        ),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=True,
        composer_visible=True,
        model_labels=("Pro Extended",),
    )
    return {
        "required_selector_missing": MockScenario(
            name="required_selector_missing",
            selector_presence={COMPOSER_SELECTOR: False},
            turn_timeline=(TimedTurnSnapshot(0.0, visible),),
        ),
        "composer_absent_then_visible": MockScenario(
            name="composer_absent_then_visible",
            selector_timeline={
                COMPOSER_SELECTOR: (
                    TimedSelectorPresence(0.0, False),
                    TimedSelectorPresence(2.0, True),
                )
            },
            turn_timeline=(
                TimedTurnSnapshot(0.0, absent),
                TimedTurnSnapshot(1.0, absent),
                TimedTurnSnapshot(2.0, visible),
            ),
        ),
        "composer_never_visible": MockScenario(
            name="composer_never_visible",
            selector_timeline={
                COMPOSER_SELECTOR: (
                    TimedSelectorPresence(0.0, False),
                    TimedSelectorPresence(100.0, False),
                )
            },
            turn_timeline=(TimedTurnSnapshot(0.0, absent), TimedTurnSnapshot(100.0, absent)),
        ),
        "fill_ignored": MockScenario(name="fill_ignored", fill_behavior="ignored", turn_timeline=(TimedTurnSnapshot(0.0, visible),)),
        "fill_truncated": MockScenario(
            name="fill_truncated",
            fill_behavior="truncated",
            fill_truncate_to=5,
            turn_timeline=(TimedTurnSnapshot(0.0, visible),),
        ),
        "disabled_send_button": MockScenario(
            name="disabled_send_button",
            disabled_click_selectors=(SEND_BUTTON_SELECTOR,),
            turn_timeline=(TimedTurnSnapshot(0.0, visible),),
        ),
        "global_enter_misuse": MockScenario(
            name="global_enter_misuse",
            disallow_global_enter=True,
            turn_timeline=(TimedTurnSnapshot(0.0, visible),),
        ),
        "existing_generation_then_idle": MockScenario(
            name="existing_generation_then_idle",
            turn_timeline=(
                TimedTurnSnapshot(0.0, _baseline_snapshot(stop_visible=True)),
                TimedTurnSnapshot(3.0, _baseline_snapshot(stop_visible=False)),
            ),
        ),
        "no_op_submit": MockScenario(
            name="no_op_submit",
            turn_timeline=(TimedTurnSnapshot(0.0, visible), TimedTurnSnapshot(5.0, visible)),
        ),
        "new_wrong_user_turn": MockScenario(
            name="new_wrong_user_turn",
            turn_timeline=(TimedTurnSnapshot(0.0, visible), TimedTurnSnapshot(3.0, wrong)),
        ),
        "successful_new_user_turn": MockScenario(
            name="successful_new_user_turn",
            turn_timeline=(TimedTurnSnapshot(0.0, visible), TimedTurnSnapshot(3.0, successful)),
        ),
    }


def _completion_raw(conversation_id: str, *, text: str = "assistant partial", status: str = "in_progress") -> dict[str, Any]:
    raw = {
        "conversation_id": conversation_id,
        "update_time": 1_700_000_100.0,
        "async_status": status,
        "mapping": {
            "root": _node("root", None, children=["user"]),
            "user": _node("user", "root", message=_text_message("msg_user", "user", ["prompt"]), children=["assistant"]),
            "assistant": _node(
                "assistant",
                "user",
                message=_text_message(
                    "msg_assistant_new",
                    "assistant",
                    [text],
                    metadata={
                        "is_complete": status == "complete",
                        "is_finalizing": status == "finalizing",
                        "pro_progress": text,
                    },
                ),
            ),
        },
        "current_node": "assistant",
    }
    raw["mapping"]["assistant"]["message"]["status"] = status
    return raw


def completion_scenarios() -> dict[str, MockScenario]:
    baseline = _baseline_snapshot(stop_visible=False)
    empty_new = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new", "assistant", "")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    growing = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new", "assistant", "hello")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    final = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new", "assistant", "hello world")),
        stop_visible=False,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    same_len_a = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new", "assistant", "abcd")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    same_len_b = TurnDomSnapshot(
        users=baseline.users,
        assistants=(*baseline.assistants, TurnDom("assistant-new", "assistant", "wxyz")),
        stop_visible=True,
        composer_visible=True,
        model_labels=baseline.model_labels,
    )
    long_progress = tuple(
        TimedTurnSnapshot(
            float(seconds),
            TurnDomSnapshot(
                users=baseline.users,
                assistants=(*baseline.assistants, TurnDom("assistant-long", "assistant", f"progress {seconds}")),
                stop_visible=True,
                composer_visible=True,
                model_labels=baseline.model_labels,
            ),
        )
        for seconds in (0, 300, 600, 900, 1200)
    )
    one_use = MockScenario(
        name="one_use_header_canaries",
        backend_conversations={"conv_mock_completion": _completion_raw("conv_mock_completion", status="complete")},
        one_use_headers=True,
        turn_timeline=(TimedTurnSnapshot(0.0, baseline),),
    )
    active_statuses = MockScenario(
        name="active_finalizing_unknown_statuses",
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="active", status="active"))),
            TimedBackendResponse(2.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="finalizing", status="finalizing"))),
            TimedBackendResponse(4.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="unknown", status="mystery_active"))),
        ),
        turn_timeline=(TimedTurnSnapshot(0.0, growing), TimedTurnSnapshot(2.0, growing), TimedTurnSnapshot(4.0, growing)),
    )
    independent_progress = MockScenario(
        name="independent_progress_tokens",
        backend_timeline=(
            TimedBackendResponse(0.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="hash-a", status="in_progress"))),
            TimedBackendResponse(2.0, MockBackendResponse(200, {**_completion_raw("conv_mock_completion", text="hash-a", status="in_progress"), "update_time": 1_700_000_102.0})),
            TimedBackendResponse(4.0, MockBackendResponse(200, {**_completion_raw("conv_mock_completion", text="hash-a", status="in_progress"), "current_node": "assistant_progress_node"})),
            TimedBackendResponse(6.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="hash-b", status="in_progress"))),
            TimedBackendResponse(8.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="longer-hash-b", status="in_progress"))),
            TimedBackendResponse(10.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="longer-hash-b", status="finalizing"))),
        ),
        turn_timeline=(TimedTurnSnapshot(0.0, same_len_a), TimedTurnSnapshot(6.0, same_len_b), TimedTurnSnapshot(8.0, growing)),
    )
    return {
        "active_finalizing_unknown_statuses": active_statuses,
        "independent_progress_tokens": independent_progress,
        "new_assistant_empty_then_growing": MockScenario(
            name="new_assistant_empty_then_growing",
            backend_timeline=(
                TimedBackendResponse(0.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="", status="in_progress"))),
                TimedBackendResponse(2.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="hello", status="in_progress"))),
                TimedBackendResponse(4.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="hello world", status="complete"))),
            ),
            turn_timeline=(TimedTurnSnapshot(0.0, empty_new), TimedTurnSnapshot(2.0, growing), TimedTurnSnapshot(4.0, final)),
        ),
        "same_length_text_hash_change": MockScenario(
            name="same_length_text_hash_change",
            turn_timeline=(TimedTurnSnapshot(0.0, same_len_a), TimedTurnSnapshot(2.0, same_len_b)),
        ),
        "continuous_progress_to_1200s": MockScenario(
            name="continuous_progress_to_1200s",
            turn_timeline=long_progress,
            backend_timeline=tuple(
                TimedBackendResponse(float(seconds), MockBackendResponse(200, _completion_raw("conv_mock_completion", text=f"progress {seconds}")))
                for seconds in (0, 300, 600, 900, 1200)
            ),
        ),
        "explicit_total_cap": MockScenario(name="explicit_total_cap", turn_timeline=long_progress[:3]),
        "no_progress_then_partial": MockScenario(
            name="no_progress_then_partial",
            turn_timeline=(TimedTurnSnapshot(0.0, growing), TimedTurnSnapshot(60.0, growing)),
        ),
        "backend_shape_error_after_partial": MockScenario(
            name="backend_shape_error_after_partial",
            backend_timeline=(
                TimedBackendResponse(0.0, MockBackendResponse(200, _completion_raw("conv_mock_completion", text="partial"))),
                TimedBackendResponse(10.0, MockBackendResponse(200, {"conversation_id": "conv_mock_completion", "detail": "shape error after partial"})),
            ),
            turn_timeline=(TimedTurnSnapshot(0.0, growing),),
        ),
        "dom_stable_window_fallback": MockScenario(
            name="dom_stable_window_fallback",
            backend_responses={
                "/backend-api/conversation/conv_mock_completion": MockBackendResponse(404, {"detail": "backend unavailable for DOM fallback"})
            },
            turn_timeline=(TimedTurnSnapshot(0.0, final), TimedTurnSnapshot(5.0, final)),
        ),
        "one_use_header_canaries": one_use,
    }


def safety_scenarios() -> dict[str, MockScenario]:
    return {
        "clipboard_prompt": MockScenario(name="clipboard_prompt", clipboard_permission="prompt"),
        "clipboard_allowed": MockScenario(
            name="clipboard_allowed",
            clipboard_permission="granted",
            clipboard_text="offline copied markdown",
        ),
        "login_wall": MockScenario(name="login_wall", login_wall=True),
        "cloudflare_challenge": MockScenario(name="cloudflare_challenge", challenge=True),
        "foreign_private_page_canary": MockScenario(
            name="foreign_private_page_canary",
            private_page_canary="PRIVATE_OPERATOR_PAGE_CANARY_DO_NOT_LEAK",
        ),
        "status_selector_present_null": MockScenario(
            name="status_selector_present_null",
            status_fixture={
                "ok": False,
                "selector_valid": True,
                "selectors": {"composer": {"present": None}},
            },
        ),
    }
