from __future__ import annotations

import pytest

from ask_chatgpt.errors import ConversationNotFoundError
from ask_chatgpt.store import Store
from ask_chatgpt.identity import (
    ConversationRef,
    backend_conversation_url,
    conversation_url,
    normalize_conversation_id,
    parse_conversation_address,
    parse_project_address,
    resolve_conv_or_alias,
)


def test_bare_conversation_id_becomes_canonical_ref() -> None:
    ref = parse_conversation_address("abc_DEF-123")

    assert ref == ConversationRef(
        conversation_id="abc_DEF-123",
        url="https://chatgpt.com/c/abc_DEF-123",
    )
    assert normalize_conversation_id("abc_DEF-123") == "abc_DEF-123"


def test_plain_conversation_url_strips_query_fragment_and_trailing_slash() -> None:
    ref = parse_conversation_address(
        "https://chatgpt.com/c/chat_123/?model=gpt-4#frag"
    )

    assert ref is not None
    assert ref.conversation_id == "chat_123"
    assert ref.project_id is None
    assert ref.url == "https://chatgpt.com/c/chat_123"
    assert conversation_url(ref) == "https://chatgpt.com/c/chat_123"


def test_project_conversation_url_round_trips_with_bare_project_id() -> None:
    url = "https://chatgpt.com/g/g-p-proj_789/c/chat_123?model=x#frag"

    ref = parse_conversation_address(url)

    assert ref is not None
    assert ref.conversation_id == "chat_123"
    assert ref.project_id == "proj_789"
    assert ref.url == "https://chatgpt.com/g/g-p-proj_789/c/chat_123"
    assert conversation_url(ref) == "https://chatgpt.com/g/g-p-proj_789/c/chat_123"
    assert parse_project_address(url) == "proj_789"
    assert parse_project_address("https://chatgpt.com/g/g-p-proj_789") == "proj_789"


def test_backend_conversation_url_uses_only_chat_id_not_project_shape() -> None:
    assert backend_conversation_url("chat_123") == (
        "https://chatgpt.com/backend-api/conversation/chat_123"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "/c/../../x",
        "https://chatgpt.com/c/../../x",
        "https://chatgpt.com/c/ok/extra",
        "https://chatgpt.com.evil.example/c/chat_123",
        "https://evil.example/g/g-p-proj/c/chat_123",
        "file:///c/chat_123",
        "javascript:https://chatgpt.com/c/chat_123",
    ],
)
def test_malformed_foreign_and_traversal_addresses_fail_closed(value: str) -> None:
    assert parse_conversation_address(value) is None
    with pytest.raises(ValueError):
        normalize_conversation_id(value)


def test_resolve_conv_or_alias_passthrough_stateless_ids_urls_and_unknown_alias(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    ref = ConversationRef("chat_123", "https://chatgpt.com/c/chat_123")

    assert resolve_conv_or_alias(ref, store=store) is ref
    assert resolve_conv_or_alias("chat_456", store=store) == ConversationRef(
        "chat_456", "https://chatgpt.com/c/chat_456"
    )
    assert resolve_conv_or_alias(
        "https://chatgpt.com/g/g-p-proj_789/c/chat_456?model=x#frag", store=store
    ) == ConversationRef(
        "chat_456",
        "https://chatgpt.com/g/g-p-proj_789/c/chat_456",
        project_id="proj_789",
    )
    with pytest.raises(ConversationNotFoundError):
        resolve_conv_or_alias("missing-alias", store=store)
