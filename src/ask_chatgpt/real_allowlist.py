"""Browser-level domain allowlist for real-channel sessions."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from urllib.parse import urlparse

DEFAULT_REAL_ALLOWED_DOMAINS: tuple[str, ...] = (
    "chatgpt.com",
    "openai.com",
    "oaistatic.com",
    "oaiusercontent.com",
)

_LOGGER = logging.getLogger("ask_chatgpt.real_allowlist")
_NETWORK_SCHEMES = {"http", "https", "ws", "wss"}


def _normalize_host(host: str | None) -> str | None:
    if host is None:
        return None
    normalized = host.strip().lower().rstrip(".")
    return normalized or None


def host_allowed(host: str | None, allowed_domains: Iterable[str]) -> bool:
    """Return true when host exactly matches, or is a subdomain of, an allowed base domain."""

    normalized_host = _normalize_host(host)
    if normalized_host is None:
        return False
    for domain in allowed_domains:
        normalized_domain = _normalize_host(str(domain))
        if normalized_domain is None:
            continue
        if normalized_host == normalized_domain or normalized_host.endswith(f".{normalized_domain}"):
            return True
    return False


def install_real_allowlist(
    context,
    allowed_domains: Iterable[str] = DEFAULT_REAL_ALLOWED_DOMAINS,
    on_abort: Callable[[str], None] | None = None,
) -> None:
    """Install a Playwright route guard that aborts real-channel off-domain requests."""

    allowed_domains = tuple(allowed_domains)

    def guard(route) -> None:
        parsed = urlparse(route.request.url)
        scheme = parsed.scheme.lower()
        if scheme not in _NETWORK_SCHEMES:
            route.continue_()
            return

        host = _normalize_host(parsed.hostname)
        if host_allowed(host, allowed_domains):
            route.continue_()
            return

        recorded_host = host or ""
        _LOGGER.warning(
            "Blocked real-channel request outside allowlist: scheme=%s host=%s",
            scheme or "<empty>",
            recorded_host or "<empty>",
        )
        if on_abort is not None:
            on_abort(recorded_host)
        route.abort("blockedbyclient")

    context.route("**/*", guard)


__all__ = ["DEFAULT_REAL_ALLOWED_DOMAINS", "host_allowed", "install_real_allowlist"]
