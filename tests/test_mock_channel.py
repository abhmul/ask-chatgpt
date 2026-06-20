from __future__ import annotations

import importlib
import json
import sys

import pytest

from ask_chatgpt.channels.base import TurnDom, TurnDomSnapshot
from ask_chatgpt.channels.mock import (
    HEADER_CANARIES,
    MockChannel,
    MockScenario,
    REQUIRED_BACKEND_HEADERS,
    ScriptedClock,
)
from ask_chatgpt.errors import DomainNotAllowedError, HumanActionNeededError, SelectorNotFoundError
from ask_chatgpt.selectors import load_selector_map
from mock_scenarios import (
    CONTENT_PARTS_EXPECTED,
    backend_header_scenario,
    completion_scenarios,
    current_branch_ids,
    deep_research_scenarios,
    attachment_citation_raw,
    large_mapping_raw,
    malformed_mapping_variants,
    safety_scenarios,
    send_ui_scenarios,
)


def test_importing_mock_channel_is_offline_and_context_pages_raises() -> None:
    sys.modules.pop("ask_chatgpt.channels.mock", None)
    module = importlib.import_module("ask_chatgpt.channels.mock")

    assert not any(name == "playwright" or name.startswith("playwright.") for name in sys.modules)

    channel = module.MockChannel()
    with pytest.raises(RuntimeError, match="context.pages"):
        _ = channel.context.pages
    with pytest.raises(AttributeError, match="browser"):
        _ = channel.browser.pages


def test_fetch_requires_all_eight_backend_headers_and_redacts_values() -> None:
    scenario = backend_header_scenario()
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_headers")

    accept_only = channel.fetch_in_page(
        tab,
        "/backend-api/conversation/conv_mock_headers",
        headers={"accept": "application/json"},
    )
    accept_only_body = json.loads(accept_only.body_bytes or b"{}")

    assert accept_only.status == 404
    assert accept_only_body == {
        "detail": "required backend authorization/OAI headers were not present",
        "missing_headers": [
            "authorization",
            "oai-client-build-number",
            "oai-client-version",
            "oai-device-id",
            "oai-language",
            "oai-session-id",
            "x-openai-target-path",
            "x-openai-target-route",
        ],
    }

    required_headers = {"accept": "application/json", **HEADER_CANARIES}
    ok = channel.fetch_in_page(
        tab,
        "/backend-api/conversation/conv_mock_headers",
        headers=required_headers,
    )
    ok_body = json.loads(ok.body_bytes or b"{}")

    assert ok.status == 200
    assert set(REQUIRED_BACKEND_HEADERS) <= set(required_headers)
    assert ok_body["conversation_id"] == "conv_mock_headers"
    assert ok_body["current_node"] == "node_5000"
    assert channel.method_counts["fetch_in_page"] == 2
    call_repr = repr(channel.calls)
    for canary in HEADER_CANARIES.values():
        assert canary not in call_repr


def test_generated_large_mapping_fixture_has_out_of_order_current_branch_and_literal_markdown_expectations() -> None:
    raw = large_mapping_raw()
    branch = current_branch_ids(raw)
    mapping = raw["mapping"]

    assert len(branch) == 5001
    assert raw["current_node"] == "node_5000"
    assert branch[-1] == raw["current_node"]
    assert list(mapping.keys()) != sorted(mapping.keys())
    assert "side_assistant_1" not in set(branch)
    assert mapping["node_2500"]["message"]["content"]["content_type"] == "thoughts"
    assert CONTENT_PARTS_EXPECTED["empty"] == ""
    assert CONTENT_PARTS_EXPECTED["single"] == "Single visible string"
    assert CONTENT_PARTS_EXPECTED["multi"] == "alphabeta\ngamma"
    assert CONTENT_PARTS_EXPECTED["math_markdown"] == (
        "  Math tokens: \\widehat{x} \\ne y and a synonym \\neq z with \\frac{}{} .\n\n"
        "| left | right |\n| --- | --- |\n| α | β |\n\n"
        "```python\nprint('unicode π')\n```\n\nTrailing snowman ☃  "
    )

    malformed = malformed_mapping_variants()
    assert set(malformed) == {"broken_parent", "cycle", "invalid_current_node", "non_string_part"}
    assert malformed["invalid_current_node"]["current_node"] == "missing_current_node"
    assert malformed["non_string_part"]["mapping"]["bad_parts"]["message"]["content"]["parts"] == ["ok", 7]


def test_dr_attachment_send_completion_and_safety_fixture_inventory() -> None:
    dr = deep_research_scenarios()
    assert set(dr) == {
        "positive",
        "missing_citations",
        "missing_final_assistant",
        "missing_hidden_internals",
        "mismatched_exchange_ids",
        "synthetic_lone_deep_research_content_type",
    }
    positive_nodes = dr["positive"]["mapping"].values()
    hidden_positive = [
        node
        for node in positive_nodes
        if (node.get("message") or {}).get("metadata", {}).get("is_visually_hidden_from_conversation")
    ]
    assert len(hidden_positive) >= 30

    mixed = attachment_citation_raw()
    messages = [(node.get("message") or {}) for node in mixed["mapping"].values()]
    assert any(message.get("metadata", {}).get("attachments") for message in messages)
    assert any(
        ref.get("type") == "file"
        for message in messages
        for ref in message.get("metadata", {}).get("content_references", [])
    )
    assert any(asset.get("asset_pointer") == "asset_pointer_generated_asset_1" for message in messages for asset in message.get("content", {}).get("assets", []))
    assert any(message.get("metadata", {}).get("aggregate_result", {}).get("run_id") == "run_mock_code_1" for message in messages)
    assert any(message.get("metadata", {}).get("citations") for message in messages)
    assert any(
        ref.get("type") in {"grouped_webpages", "sources_footnote"}
        for message in messages
        for ref in message.get("metadata", {}).get("content_references", [])
    )
    assert any(message.get("metadata", {}).get("search_result_groups") for message in messages)
    assert any(message.get("metadata", {}).get("search_queries") == ["mock search query"] for message in messages)
    assert "https://invalid.invalid/mock-never-fetch" in mixed["mock_invalid_urls"]
    assert "/tmp/ask-chatgpt-mock-never-open" in mixed["mock_invalid_paths"]

    send = send_ui_scenarios()
    assert set(send) == {
        "composer_absent_then_visible",
        "composer_never_visible",
        "disabled_send_button",
        "existing_generation_then_idle",
        "fill_ignored",
        "fill_truncated",
        "global_enter_misuse",
        "new_wrong_user_turn",
        "no_op_submit",
        "required_selector_missing",
        "successful_new_user_turn",
    }
    assert send["successful_new_user_turn"].turn_timeline[-1].snapshot.users[-1].text == "literal prompt"

    completion = completion_scenarios()
    assert {
        "active_finalizing_unknown_statuses",
        "backend_shape_error_after_partial",
        "continuous_progress_to_1200s",
        "dom_stable_window_fallback",
        "explicit_total_cap",
        "independent_progress_tokens",
        "new_assistant_empty_then_growing",
        "no_progress_then_partial",
        "one_use_header_canaries",
        "same_length_text_hash_change",
    } <= set(completion)
    assert completion["continuous_progress_to_1200s"].turn_timeline[-1].at_s == 1200.0
    assert completion["one_use_header_canaries"].one_use_headers is True

    safety = safety_scenarios()
    assert safety["clipboard_prompt"].clipboard_permission == "prompt"
    assert safety["clipboard_allowed"].clipboard_text == "offline copied markdown"
    assert safety["status_selector_present_null"].status_fixture == {
        "ok": False,
        "selector_valid": True,
        "selectors": {"composer": {"present": None}},
    }


def test_query_turns_and_selector_timelines_follow_fake_clock_without_real_sleep() -> None:
    clock = ScriptedClock()
    scenario = send_ui_scenarios()["composer_absent_then_visible"]
    channel = MockChannel(scenario, monotonic=clock.monotonic, sleeper=clock.sleep)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_send")
    selectors = load_selector_map("real")

    first = channel.query_turns(tab, selectors)
    with pytest.raises(SelectorNotFoundError):
        channel.wait_for_selector(tab, selectors["composer"], timeout_s=0.1)
    clock.advance(2.0)
    second = channel.query_turns(tab, selectors)
    channel.wait_for_selector(tab, selectors["composer"], timeout_s=0.1)
    channel.sleep(3.0)

    assert first == TurnDomSnapshot(
        users=(TurnDom("baseline-user-1", "user", "baseline prompt"),),
        assistants=(TurnDom("baseline-assistant-1", "assistant", "baseline answer"),),
        stop_visible=False,
        composer_visible=False,
        model_labels=("Pro Extended",),
    )
    assert second.composer_visible is True
    assert clock.monotonic() == 5.0
    assert clock.sleeps == [3.0]
    assert channel.method_counts["query_turns"] == 2
    assert channel.method_counts["dom_polls"] == 2


def test_clipboard_default_prompt_blocks_and_granted_offline_text_is_scripted() -> None:
    default_channel = MockChannel()
    default_tab = default_channel.open_tab("https://chatgpt.com/")
    with pytest.raises(HumanActionNeededError, match="clipboard"):
        default_channel.read_clipboard(default_tab)

    allowed = MockChannel(safety_scenarios()["clipboard_allowed"])
    allowed_tab = allowed.open_tab("https://chatgpt.com/")
    assert allowed.read_clipboard(allowed_tab) == "offline copied markdown"


def test_disallowed_navigation_and_fetch_raise_before_side_effects() -> None:
    channel = MockChannel()
    tab = channel.open_tab("https://chatgpt.com/")

    with pytest.raises(DomainNotAllowedError):
        channel.open_tab("https://evil.example/c/private-canary")
    assert channel.method_counts["open_tab"] == 1

    with pytest.raises(DomainNotAllowedError):
        channel.fetch_in_page(tab, "https://evil.example/backend-api/conversation/conv_mock_headers")
    assert channel.method_counts.get("fetch_in_page", 0) == 0
    assert channel.call_order == ("open_tab",)


def test_completion_counters_and_one_use_header_canary_reuse_are_scripted() -> None:
    scenario = completion_scenarios()["one_use_header_canaries"]
    channel = MockChannel(scenario)
    tab = channel.open_tab("https://chatgpt.com/c/conv_mock_completion")
    selectors = load_selector_map("real")
    headers = dict(scenario.header_canaries)

    channel.query_turns(tab, selectors)
    first_fetch = channel.fetch_in_page(
        tab,
        "/backend-api/conversation/conv_mock_completion",
        headers=headers,
    )
    with pytest.raises(RuntimeError, match="reused"):
        channel.fetch_in_page(
            tab,
            "/backend-api/conversation/conv_mock_completion/stream_status",
            headers=headers,
        )

    assert first_fetch.status == 200
    assert channel.method_counts["dom_polls"] == 1
    assert channel.method_counts["full_raw_fetches"] == 1
    assert channel.method_counts.get("backend_checks", 0) == 0
    for canary in scenario.header_canaries.values():
        assert canary not in repr(channel.calls)
