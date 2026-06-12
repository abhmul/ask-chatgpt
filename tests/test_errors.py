import re

from ask_chatgpt.errors import (
    AskChatGPTError,
    DownloadUnsupportedError,
    LoginRequiredError,
    ModelUnavailableError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
    UploadUnsupportedError,
)


ERROR_CLASSES = (
    AskChatGPTError,
    LoginRequiredError,
    SessionNotFoundError,
    ModelUnavailableError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    UploadUnsupportedError,
    DownloadUnsupportedError,
)

ACTION_WORDS = (
    "operator",
    "sign in",
    "inspect",
    "retry",
    "choose",
    "refresh",
    "repair",
    "update",
    "recreate",
    "check",
)

SENSITIVE_PATTERNS = (
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"cookie\s*[:=]", re.IGNORECASE),
    re.compile(r"token\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"bearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{8,}"),
)


def test_named_errors_subclass_package_base():
    for cls in ERROR_CLASSES:
        assert issubclass(cls, AskChatGPTError)


def test_default_messages_are_static_non_empty_and_actionable():
    for cls in ERROR_CLASSES:
        message = str(cls())
        assert isinstance(cls.default_message, str)
        assert message == cls.default_message
        assert len(message) >= 40
        assert any(word in message.lower() for word in ACTION_WORDS)
        assert not any(pattern.search(message) for pattern in SENSITIVE_PATTERNS)


def test_optional_detail_is_composed_into_message_without_dropping_default():
    detail = "synthetic UI condition for tests"
    for cls in ERROR_CLASSES:
        message = str(cls(detail))
        assert cls.default_message in message
        assert detail in message
        assert not any(pattern.search(message) for pattern in SENSITIVE_PATTERNS)
