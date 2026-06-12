"""Named, actionable exceptions raised by ask-chatgpt."""


class AskChatGPTError(Exception):
    default_message = (
        "ask-chatgpt failed. Operator action: inspect the specific error "
        "detail, resolve the reported condition, then retry."
    )

    def __init__(self, detail: str | None = None):
        self.detail = detail
        message = self.default_message
        if detail:
            message = f"{message} Detail: {detail}"
        super().__init__(message)


class LoginRequiredError(AskChatGPTError):
    default_message = (
        "ChatGPT is not logged in. Operator action: sign in through the "
        "browser UI and retry; this tool never reads or stores credentials."
    )


class SessionNotFoundError(AskChatGPTError):
    default_message = (
        "Stored conversation reference no longer opens a reachable ChatGPT "
        "conversation. Operator action: delete or recreate that session "
        "identifier, then retry."
    )


class ModelUnavailableError(AskChatGPTError):
    default_message = (
        "Requested model or option is not offered by the current ChatGPT UI. "
        "Operator action: choose an available model setting and retry."
    )


class ResponseTruncatedError(AskChatGPTError):
    default_message = (
        "Assistant response appears incomplete: end marker missing, turn still "
        "in progress, or payload truncated. Operator action: retry, reduce "
        "payload size, or inspect the UI."
    )


class RateLimitedError(AskChatGPTError):
    default_message = (
        "ChatGPT reported a rate limit or backoff condition. Operator action: "
        "wait for the indicated retry window, reduce request rate, then retry."
    )


class SelectorUnavailableError(AskChatGPTError):
    default_message = (
        "Required selector-map key is missing or stale. Operator action: "
        "update the selector map and retry; fail closed and never guess or "
        "broaden selectors."
    )


class UploadUnsupportedError(AskChatGPTError):
    default_message = (
        "Upload affordance is absent or rejected by the current ChatGPT UI. "
        "Operator action: disable upload-dependent workflow, inspect current "
        "UI support, or retry later."
    )


class DownloadUnsupportedError(AskChatGPTError):
    default_message = (
        "Download affordance is absent in the current ChatGPT UI. Operator "
        "action: use the text-channel fallback, inspect current UI support, "
        "or retry later."
    )


class PatchBundleValidationError(AskChatGPTError):
    default_message = (
        "Patch or upload bundle validation failed. Operator action: request a "
        "fresh changed-files-only bundle, reduce payload size, or inspect the "
        "safe detail; no local files were changed."
    )


class PatchMalformedError(PatchBundleValidationError):
    default_message = (
        "Patch bundle is malformed or is not a changed-files-only patch. "
        "Operator action: request a fresh patch bundle; no local files were changed."
    )


class BundleIntegrityError(PatchBundleValidationError):
    default_message = (
        "Bundle transfer integrity failed. Operator action: retry transfer, "
        "use an alternate return channel, or reduce the bundle; no local files were changed."
    )


class OversizedPayloadError(PatchBundleValidationError):
    default_message = (
        "Bundle payload exceeds a configured size/type guard. Operator action: "
        "reduce selected files, split the patch, or raise an explicit limit; no local files were changed."
    )


class PathEscapeError(PatchBundleValidationError):
    default_message = (
        "Bundle path is unsafe or escapes the project root. Operator action: "
        "use repo-root-relative file paths without traversal, symlinks, or special files; no local files were changed."
    )


class PatchApplyError(AskChatGPTError):
    default_message = (
        "Patch application failed after validation. Operator action: inspect "
        "the local filesystem and transaction journal; local mutation may need recovery."
    )


__all__ = [
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
