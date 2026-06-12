"""ask-chatgpt: programmatic interaction with ChatGPT.com."""

from ask_chatgpt.api import ask_chatgpt
from ask_chatgpt.errors import (
    AskChatGPTError,
    BundleIntegrityError,
    DownloadUnsupportedError,
    LoginRequiredError,
    ModelUnavailableError,
    OversizedPayloadError,
    PatchApplyError,
    PatchBundleValidationError,
    PatchMalformedError,
    PathEscapeError,
    RateLimitedError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
    UploadUnsupportedError,
)

__version__ = "0.0.1"

__all__ = [
    "__version__",
    "ask_chatgpt",
    "AskChatGPTError",
    "LoginRequiredError",
    "SessionNotFoundError",
    "ModelUnavailableError",
    "ResponseTruncatedError",
    "RateLimitedError",
    "SelectorUnavailableError",
    "UploadUnsupportedError",
    "DownloadUnsupportedError",
    "PatchBundleValidationError",
    "PatchMalformedError",
    "BundleIntegrityError",
    "OversizedPayloadError",
    "PathEscapeError",
    "PatchApplyError",
]
