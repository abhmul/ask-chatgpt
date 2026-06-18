"""URL allowlist and log sanitization for browser/navigation safety."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from ask_chatgpt.errors import DomainNotAllowedError

DEFAULT_ALLOWED_HOST_SUFFIXES = (
    "chatgpt.com",
    ".chatgpt.com",
    "openai.com",
    ".openai.com",
    "oaiusercontent.com",
    ".oaiusercontent.com",
    "oaistatic.com",
    ".oaistatic.com",
)

_BEARERISH_SEGMENT_RE = re.compile(
    r"(?i)(bearer|access[_-]?token|secret|password|cookie|authorization)"
)


def _normalized_host(host: str | None) -> str | None:
    if not host:
        return None
    normalized = host.lower().rstrip(".")
    return normalized or None


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    for suffix in suffixes:
        normalized_suffix = suffix.lower().lstrip(".").rstrip(".")
        if not normalized_suffix:
            continue
        if host == normalized_suffix or host.endswith(f".{normalized_suffix}"):
            return True
    return False


def _safe_port_suffix(parsed: object) -> str:
    try:
        port = parsed.port  # type: ignore[attr-defined]
    except ValueError:
        return ""
    return f":{port}" if port is not None else ""


def _sanitize_path(path: str) -> str:
    if not path:
        return ""
    segments = []
    for segment in path.split("/"):
        if _BEARERISH_SEGMENT_RE.search(segment):
            segments.append("<redacted>")
        else:
            segments.append(segment)
    return "/".join(segments)


@dataclass(frozen=True)
class Allowlist:
    host_suffixes: tuple[str, ...] = DEFAULT_ALLOWED_HOST_SUFFIXES

    def is_allowed_url(self, url: str) -> bool:
        raw = url.strip()
        if not raw:
            return False
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"}:
            return False
        host = _normalized_host(parsed.hostname)
        if host is None:
            return False
        return _host_matches(host, self.host_suffixes)

    def require_allowed_url(self, url: str) -> None:
        if not self.is_allowed_url(url):
            raise DomainNotAllowedError(
                "URL is outside the allowed ChatGPT/OpenAI domains",
                details={"url": self.sanitize_for_log(url)},
            )

    def sanitize_for_log(self, url: str) -> str:
        raw = url.strip()
        if not raw:
            return "<empty-url>"
        parsed = urlsplit(raw)
        scheme = parsed.scheme.lower()
        host = _normalized_host(parsed.hostname)
        if scheme in {"http", "https"} and host:
            netloc = f"{host}{_safe_port_suffix(parsed)}"
            path = _sanitize_path(parsed.path)
            return urlunsplit((scheme, netloc, path, "", ""))
        scrubbed = _BEARERISH_SEGMENT_RE.sub("<redacted>", raw)
        return scrubbed.split("?", 1)[0].split("#", 1)[0]


__all__ = ["DEFAULT_ALLOWED_HOST_SUFFIXES", "Allowlist"]
