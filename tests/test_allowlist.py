from __future__ import annotations

import pytest

from ask_chatgpt.allowlist import DEFAULT_ALLOWED_HOST_SUFFIXES, Allowlist
from ask_chatgpt.errors import DomainNotAllowedError


EXPECTED_SUFFIXES = (
    "chatgpt.com",
    ".chatgpt.com",
    "openai.com",
    ".openai.com",
    "oaiusercontent.com",
    ".oaiusercontent.com",
    "oaistatic.com",
    ".oaistatic.com",
)


def test_default_allowed_host_suffixes_are_exact_m3_tuple() -> None:
    assert DEFAULT_ALLOWED_HOST_SUFFIXES == EXPECTED_SUFFIXES


@pytest.mark.parametrize(
    "url",
    [
        "https://chatgpt.com/c/chat_123",
        "https://sub.chatgpt.com/path",
        "https://openai.com/research",
        "https://api.openai.com/v1",
        "https://oaiusercontent.com/blob",
        "https://files.oaiusercontent.com/blob",
        "https://oaistatic.com/assets/app.js",
        "https://cdn.oaistatic.com/assets/app.js",
        "http://chatgpt.com/c/chat_123",
    ],
)
def test_allowlist_accepts_apex_and_subdomains(url: str) -> None:
    assert Allowlist().is_allowed_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://chatgpt.com.evil.example/c/chat_123",
        "https://evilchatgpt.com/c/chat_123",
        "https://openai.com.evil.example",
        "https://oaiusercontent.com.evil.example",
        "",
        "   ",
        "/relative/c/chat_123",
        "file:///tmp/secret",
        "javascript:https://chatgpt.com/c/chat_123",
        "data:text/html,https://chatgpt.com",
        "ftp://chatgpt.com/file",
    ],
)
def test_allowlist_rejects_suffix_confusion_relative_and_unsafe_schemes(url: str) -> None:
    allowlist = Allowlist()

    assert allowlist.is_allowed_url(url) is False
    with pytest.raises(DomainNotAllowedError) as excinfo:
        allowlist.require_allowed_url(url)
    assert excinfo.value.code == "DOMAIN_NOT_ALLOWED"


def test_sanitize_for_log_strips_credentials_query_fragment_and_token_canaries() -> None:
    raw = (
        "https://user:SECRET_CANARY@chatgpt.com/c/chat_123"
        "?access_token=SECRET_CANARY&ok=1#SECRET_CANARY"
    )

    sanitized = Allowlist().sanitize_for_log(raw)

    assert sanitized == "https://chatgpt.com/c/chat_123"
    assert "SECRET_CANARY" not in sanitized
    assert "access_token" not in sanitized
    assert "user:" not in sanitized


def test_require_allowed_url_uses_sanitized_error_details() -> None:
    raw = "https://user:SECRET_CANARY@evil.example/path?access_token=SECRET_CANARY#frag"

    with pytest.raises(DomainNotAllowedError) as excinfo:
        Allowlist().require_allowed_url(raw)

    assert "evil.example" in repr(excinfo.value.details)
    assert "SECRET_CANARY" not in str(excinfo.value)
    assert "SECRET_CANARY" not in repr(excinfo.value.details)
