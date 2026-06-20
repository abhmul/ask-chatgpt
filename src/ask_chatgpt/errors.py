"""Stable redacted exception taxonomy for ask-chatgpt."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar

_SECRET_KEY_PARTS = (
    "authorization",
    "bearer",
    "cookie",
    "key",
    "oai",
    "password",
    "prompt",
    "response",
    "secret",
    "token",
)
_SECRET_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "cookie:",
    "oai-",
    "password",
    "secret",
    "token",
)


def _looks_sensitive_key(key: object) -> bool:
    return any(part in str(key).lower() for part in _SECRET_KEY_PARTS)


def _looks_sensitive_value(value: str) -> bool:
    lowered = value.lower()
    return any(part in lowered for part in _SECRET_VALUE_PARTS)


def _sanitize_detail_value(value: Any, *, sensitive_parent: bool = False) -> Any:
    if sensitive_parent:
        return "<redacted>"
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(key): _sanitize_detail_value(
                    nested_value,
                    sensitive_parent=_looks_sensitive_key(key),
                )
                for key, nested_value in value.items()
            }
        )
    if isinstance(value, tuple):
        return tuple(_sanitize_detail_value(item) for item in value)
    if isinstance(value, list):
        return tuple(_sanitize_detail_value(item) for item in value)
    if isinstance(value, str) and _looks_sensitive_value(value):
        return "<redacted>"
    return value


def _sanitize_details(details: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not details:
        return MappingProxyType({})
    return MappingProxyType(
        {
            str(key): _sanitize_detail_value(
                value,
                sensitive_parent=_looks_sensitive_key(key),
            )
            for key, value in details.items()
        }
    )


class AskChatGPTError(Exception):
    """Base exception carrying stable machine metadata and redacted details."""

    code: str
    exit_code: int
    retryable: bool
    retry_action: str
    message: str
    details: Mapping[str, Any]

    def __init__(
        self,
        code: str,
        exit_code: int,
        retryable: bool,
        retry_action: str,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.retryable = retryable
        self.retry_action = retry_action
        self.message = message
        self.details = _sanitize_details(details)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class _KnownAskChatGPTError(AskChatGPTError):
    default_code: ClassVar[str]
    default_exit_code: ClassVar[int]
    default_retryable: ClassVar[bool]
    default_retry_action: ClassVar[str]

    def __init__(
        self,
        message: str = "",
        *,
        details: Mapping[str, Any] | None = None,
        retryable: bool | None = None,
        retry_action: str | None = None,
    ) -> None:
        super().__init__(
            self.default_code,
            self.default_exit_code,
            self.default_retryable if retryable is None else retryable,
            self.default_retry_action if retry_action is None else retry_action,
            message,
            details,
        )


class CDPUnreachableError(_KnownAskChatGPTError):
    default_code = "CDP_UNREACHABLE"
    default_exit_code = 20
    default_retryable = True
    default_retry_action = "operator_action"


class HumanActionNeededError(_KnownAskChatGPTError):
    default_code = "HUMAN-ACTION-NEEDED"
    default_exit_code = 21
    default_retryable = True
    default_retry_action = "human_action"


class DomainNotAllowedError(_KnownAskChatGPTError):
    default_code = "DOMAIN_NOT_ALLOWED"
    default_exit_code = 22
    default_retryable = False
    default_retry_action = "fix_input_or_config"


class ConversationNotFoundError(_KnownAskChatGPTError):
    default_code = "CONVERSATION_NOT_FOUND"
    default_exit_code = 23
    default_retryable = True
    default_retry_action = "inspect_or_retry"


class SelectorNotFoundError(_KnownAskChatGPTError):
    default_code = "SELECTOR_NOT_FOUND"
    default_exit_code = 24
    default_retryable = True
    default_retry_action = "update_selectors"


class PromptNotSubmittedError(_KnownAskChatGPTError):
    default_code = "PROMPT_NOT_SUBMITTED"
    default_exit_code = 30
    default_retryable = True
    default_retry_action = "retry_send"


class ModelSelectionNotReflectedError(_KnownAskChatGPTError):
    default_code = "MODEL_SELECTION_NOT_REFLECTED"
    default_exit_code = 31
    default_retryable = True
    default_retry_action = "retry_model_selection"


class ToolSelectionNotReflectedError(_KnownAskChatGPTError):
    default_code = "TOOL_SELECTION_NOT_REFLECTED"
    default_exit_code = 32
    default_retryable = True
    default_retry_action = "retry_tool_selection"


class BackendAuthUnavailableError(_KnownAskChatGPTError):
    default_code = "BACKEND_AUTH_UNAVAILABLE"
    default_exit_code = 40
    default_retryable = True
    default_retry_action = "reauthenticate_or_retry"


class BackendCaptureShapeError(_KnownAskChatGPTError):
    default_code = "BACKEND_CAPTURE_SHAPE"
    default_exit_code = 41
    default_retryable = False
    default_retry_action = "parser_update_required"


class CaptureFailedClosedError(_KnownAskChatGPTError):
    default_code = "CAPTURE_FAIL_CLOSED"
    default_exit_code = 42
    default_retryable = True
    default_retry_action = "inspect_or_retry"


class CompletionTimeoutError(_KnownAskChatGPTError):
    default_code = "COMPLETION_TIMEOUT"
    default_exit_code = 50
    default_retryable = True
    default_retry_action = "inspect_or_scrape_before_resend"


class MaxTotalWaitExceededError(_KnownAskChatGPTError):
    default_code = "MAX_TOTAL_WAIT_EXCEEDED"
    default_exit_code = 51
    default_retryable = True
    default_retry_action = "increase_wait_or_retry"


class AttachmentNotFoundError(_KnownAskChatGPTError):
    default_code = "ATTACHMENT_NOT_FOUND"
    default_exit_code = 60
    default_retryable = False
    default_retry_action = "fix_attachment_ref"


class AttachmentFetchError(_KnownAskChatGPTError):
    default_code = "ATTACHMENT_FETCH_FAILED"
    default_exit_code = 61
    default_retryable = True
    default_retry_action = "retry_fetch"


class AttachmentUploadError(_KnownAskChatGPTError):
    default_code = "ATTACHMENT_UPLOAD_FAILED"
    default_exit_code = 63
    default_retryable = True
    default_retry_action = "retry_upload_or_update_selectors"


class TabPoolExhaustedError(_KnownAskChatGPTError):
    default_code = "TAB_POOL_EXHAUSTED"
    default_exit_code = 62
    default_retryable = True
    default_retry_action = "wait_or_reduce_concurrency"


class StoreError(_KnownAskChatGPTError):
    default_code = "STORE_ERROR"
    default_exit_code = 70
    default_retryable = False
    default_retry_action = "inspect_data_dir"


class InternalError(_KnownAskChatGPTError):
    default_code = "INTERNAL_ERROR"
    default_exit_code = 99
    default_retryable = False
    default_retry_action = "report_bug"


class StoreWarning(UserWarning):
    """Warning emitted for tolerated store recovery conditions."""


__all__ = [
    "AskChatGPTError",
    "AttachmentFetchError",
    "AttachmentNotFoundError",
    "AttachmentUploadError",
    "BackendAuthUnavailableError",
    "BackendCaptureShapeError",
    "CDPUnreachableError",
    "CaptureFailedClosedError",
    "CompletionTimeoutError",
    "ConversationNotFoundError",
    "DomainNotAllowedError",
    "HumanActionNeededError",
    "InternalError",
    "MaxTotalWaitExceededError",
    "ModelSelectionNotReflectedError",
    "PromptNotSubmittedError",
    "SelectorNotFoundError",
    "StoreError",
    "StoreWarning",
    "TabPoolExhaustedError",
    "ToolSelectionNotReflectedError",
]
