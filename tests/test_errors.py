from __future__ import annotations

import pytest

from ask_chatgpt.errors import (
    AskChatGPTError,
    AttachmentFetchError,
    AttachmentNotFoundError,
    BackendAuthUnavailableError,
    BackendCaptureShapeError,
    CDPUnreachableError,
    CaptureFailedClosedError,
    CompletionTimeoutError,
    ConversationNotFoundError,
    DomainNotAllowedError,
    HumanActionNeededError,
    InternalError,
    MaxTotalWaitExceededError,
    ModelSelectionNotReflectedError,
    PromptNotSubmittedError,
    SelectorNotFoundError,
    StoreError,
    StoreWarning,
    TabPoolExhaustedError,
    ToolSelectionNotReflectedError,
)


ERROR_CASES = [
    (CDPUnreachableError, "CDP_UNREACHABLE", 20),
    (HumanActionNeededError, "HUMAN-ACTION-NEEDED", 21),
    (DomainNotAllowedError, "DOMAIN_NOT_ALLOWED", 22),
    (ConversationNotFoundError, "CONVERSATION_NOT_FOUND", 23),
    (SelectorNotFoundError, "SELECTOR_NOT_FOUND", 24),
    (PromptNotSubmittedError, "PROMPT_NOT_SUBMITTED", 30),
    (ModelSelectionNotReflectedError, "MODEL_SELECTION_NOT_REFLECTED", 31),
    (ToolSelectionNotReflectedError, "TOOL_SELECTION_NOT_REFLECTED", 32),
    (BackendAuthUnavailableError, "BACKEND_AUTH_UNAVAILABLE", 40),
    (BackendCaptureShapeError, "BACKEND_CAPTURE_SHAPE", 41),
    (CaptureFailedClosedError, "CAPTURE_FAIL_CLOSED", 42),
    (CompletionTimeoutError, "COMPLETION_TIMEOUT", 50),
    (MaxTotalWaitExceededError, "MAX_TOTAL_WAIT_EXCEEDED", 51),
    (AttachmentNotFoundError, "ATTACHMENT_NOT_FOUND", 60),
    (AttachmentFetchError, "ATTACHMENT_FETCH_FAILED", 61),
    (TabPoolExhaustedError, "TAB_POOL_EXHAUSTED", 62),
    (StoreError, "STORE_ERROR", 70),
    (InternalError, "INTERNAL_ERROR", 99),
]


@pytest.mark.parametrize(("error_type", "code", "exit_code"), ERROR_CASES)
def test_error_taxonomy_exact_codes_exit_codes_and_redaction(error_type, code, exit_code) -> None:
    err = error_type(
        "safe message",
        details={
            "Authorization": "Bearer SECRET_CANARY",
            "nested": {"cookie": "SECRET_CANARY"},
            "url": "https://chatgpt.com/c/abc?access_token=SECRET_CANARY#frag",
        },
    )

    assert isinstance(err, AskChatGPTError)
    assert err.code == code
    assert err.exit_code == exit_code
    assert isinstance(err.retryable, bool)
    assert isinstance(err.retry_action, str)
    assert "safe message" in str(err)
    assert code in str(err)
    assert "SECRET_CANARY" not in str(err)
    assert "SECRET_CANARY" not in repr(err)
    assert "SECRET_CANARY" not in repr(err.details)


def test_base_error_accepts_explicit_machine_metadata_without_leaking_details() -> None:
    err = AskChatGPTError(
        code="CUSTOM_CODE",
        exit_code=77,
        retryable=True,
        retry_action="operator may retry",
        message="visible message",
        details={"debug": "SECRET_CANARY", "count": 2},
    )

    assert err.code == "CUSTOM_CODE"
    assert err.exit_code == 77
    assert err.retryable is True
    assert err.retry_action == "operator may retry"
    assert err.details["debug"] == "<redacted>"
    assert err.details["count"] == 2
    assert str(err) == "CUSTOM_CODE: visible message"
    assert "SECRET_CANARY" not in repr(err)


def test_store_warning_is_shared_user_warning_type() -> None:
    assert issubclass(StoreWarning, UserWarning)
