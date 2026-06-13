"""Playwright browser-session controller for mock, real, and CDP-attached ChatGPT channels."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import quote, unquote, urlparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from ask_chatgpt.errors import (
    AskChatGPTError,
    CDPUnreachableError,
    ChallengePresentError,
    LoginRequiredError,
    ModelUnavailableError,
    ProfileLockedError,
    RateLimitedError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
)
from ask_chatgpt.real_allowlist import install_real_allowlist
from ask_chatgpt.selector_map import SelectorMap, load_selector_map


REAL_BASE_URL = "https://chatgpt.com"
_DEFAULT_CDP_ENDPOINT = "http://127.0.0.1:9222"
_DEFAULT_NAVIGATION_TIMEOUT_MS = 5_000
_READY_ROOT_TIMEOUT_MS = 30_000
_POLL_INTERVAL_S = 0.1
_REAL_REQUIRED_SELECTOR_KEYS = (
    "ready_root",
    "chat_list",
    "chat_item",
    "new_chat_button",
    "composer",
    "send_button",
    "assistant_message",
    "message_body",
    "streaming_marker",
    "completion_marker",
    "copy_button",
    "upload_input",
)
_REAL_REQUIRED_ATTRIBUTE_KEYS = ("turn_id",)


class BrowserSession:
    """Own a Playwright context/page plus a fail-closed selector map.

    ``channel="mock"`` is the tested path and only navigates to the caller-provided loopback fixture URL. ``channel="real"`` is built for operator-runbook use via a persistent profile path, while ``channel="cdp"`` attaches to an operator-owned browser and uses a new tab only.
    """

    def __init__(
        self,
        *,
        channel: str = "mock",
        base_url: str | None = None,
        profile_path: str | Path | None = None,
        executable_path: str | Path | None = None,
        maps_dir: Path | None = None,
        grant_clipboard: bool = True,
        cdp_endpoint: str | None = None,
    ) -> None:
        self.channel = channel
        self._base_url = self._resolve_base_url(channel=channel, base_url=base_url)
        selector_channel = self._selector_map_channel(channel=channel, base_url=self._base_url)
        self.selectors: SelectorMap = load_selector_map(selector_channel, maps_dir=maps_dir)
        self._profile_path = Path(profile_path) if profile_path is not None else None
        self._executable_path = Path(executable_path) if executable_path is not None else None
        self._grant_clipboard = bool(grant_clipboard)
        self._cdp_endpoint = _DEFAULT_CDP_ENDPOINT if channel == "cdp" and cdp_endpoint is None else cdp_endpoint
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None
        self._cdp_owned_pages: list[Page] = []
        self._active_conversation_ref: str | None = None
        self.aborted_off_domain_hosts: list[str] = []

    @property
    def active_conversation_ref(self) -> str | None:
        return self._active_conversation_ref

    def __enter__(self) -> BrowserSession:
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def start(self) -> BrowserSession:
        if self._playwright is not None:
            return self
        if self.channel == "real":
            self._ensure_real_selector_map_ready()
            self._preflight_profile_lock()
        self._playwright = sync_playwright().start()
        try:
            if self.channel == "mock":
                self._start_mock_context()
                page = self._new_or_existing_page()
            elif self.channel == "real":
                self._start_real_context()
                page = self._new_or_existing_page()
            elif self.channel == "cdp":
                self._start_cdp_context()
                page = self._new_cdp_page()
                self._install_cdp_route_guard(page)
            else:
                raise AskChatGPTError(
                    f"Unsupported channel '{self.channel}'. Operator action: choose 'mock' for tests, 'real' for operator-runbook launch, or 'cdp' for operator-owned browser attach."
                )
            self.page = page
            page.goto(self._base_url, wait_until="load", timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
            if self.channel in {"real", "cdp"}:
                self._raise_login_required_for_auth_redirect(page.url)
            if self.channel == "cdp":
                self._raise_challenge_present_if_detected()
            return self
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        page = self.page
        context = self._context
        browser = self._browser
        playwright = self._playwright
        owned_pages = list(self._cdp_owned_pages)
        is_cdp = self.channel == "cdp"
        self.page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._cdp_owned_pages = []
        self._active_conversation_ref = None

        if is_cdp:
            if page is not None and all(opened_page is not page for opened_page in owned_pages):
                owned_pages.append(page)
            for opened_page in owned_pages:
                try:
                    opened_page.close()
                except PlaywrightError:
                    pass
        else:
            if page is not None:
                try:
                    page.close()
                except PlaywrightError:
                    pass
            if context is not None:
                try:
                    context.close()
                except PlaywrightError:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except PlaywrightError:
                    pass
        if playwright is not None:
            try:
                playwright.stop()
            except PlaywrightError:
                pass

    def open_or_create_conversation(self, conversation_ref: str | None) -> str:
        """Open an existing conversation ref or create a new one, returning the active ref."""

        page = self._require_page()
        if conversation_ref:
            try:
                response = page.goto(
                    self._conversation_url(conversation_ref), wait_until="load", timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS
                )
            except PlaywrightError as exc:
                raise AskChatGPTError("Browser navigation failed while opening the conversation. Operator action: retry or inspect the UI.") from exc
            if response is not None and response.status == 404:
                raise SessionNotFoundError("conversation-not-found response while opening stored conversation")
            self._raise_open_failures()
            self._wait_for_ready_root()
            self._require_present("ready_root")
            self._require_present("composer")
            self._active_conversation_ref = self._read_active_conversation_ref()
            return self._active_conversation_ref

        self._raise_open_failures()
        self._wait_for_ready_root()
        self._require_present("ready_root")
        self._require_present("composer")
        self._require_present("new_chat_button").click(timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
        self._wait_for_load_state()
        self._raise_open_failures()
        self._wait_for_ready_root()
        self._require_present("ready_root")
        self._require_present("composer")
        self._active_conversation_ref = self._try_read_active_conversation_ref() or ""
        return self._active_conversation_ref

    def select_model(self, model_settings: dict | None) -> None:
        """Select a requested model; no-op for ``None`` or empty settings."""

        if not model_settings:
            return
        requested = model_settings.get("model") or model_settings.get("model_name") or model_settings.get("value")
        if requested in (None, ""):
            return
        requested = str(requested)
        self._raise_open_failures()
        menu = self._require_present("model_menu")
        option = self._find_model_option(requested)
        if option is None:
            raise ModelUnavailableError(f"model option '{requested}' is absent")
        disabled_selector = self.selectors.selector("model_option_disabled")
        try:
            disabled = bool(option.evaluate("(element, selector) => element.matches(selector)", disabled_selector))
        except PlaywrightError as exc:
            raise SelectorUnavailableError(
                f"selector 'model_option_disabled' unavailable for channel '{self.channel}'"
            ) from exc
        if disabled:
            raise ModelUnavailableError(f"model option '{requested}' is disabled")

        try:
            menu.click(timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
            tag_name = str(menu.evaluate("element => element.tagName")).lower()
            option_value = option.get_attribute("value")
            if tag_name == "select" and option_value:
                menu.select_option(value=option_value, timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
            else:
                option.click(timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
        except PlaywrightError as exc:
            raise ModelUnavailableError(f"model option '{requested}' could not be selected") from exc

    def send_prompt(self, text: str) -> None:
        """Fill the composer and submit the prompt; rate-limit markers raise ``RateLimitedError``."""

        self._raise_open_failures()
        composer = self._require_present("composer")
        try:
            composer.fill(text, timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector 'composer' unavailable for channel '{self.channel}'") from exc

        send_button_selector = self.selectors.selector("send_button")
        try:
            self._require_page().wait_for_selector(
                send_button_selector, timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS, state="attached"
            )
            send_button = self._require_present("send_button")
            send_button.click(timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector 'send_button' unavailable for channel '{self.channel}'") from exc
        self._wait_for_load_state(ignore_timeout=True)
        if self._rate_limit_visible():
            raise self._rate_limited_error()
        self._raise_open_failures()
        self._active_conversation_ref = self._try_read_active_conversation_ref() or self._active_conversation_ref

    def wait_for_completion(self, timeout_s: float = 10.0) -> Locator:
        """Return the latest completed assistant turn locator.

        Mock-channel strategy: poll for completion markers; when only streaming markers are present, reload ``/c/<ref>`` so the fixture advances scripted stream state, then re-check. Real-channel completion signals are an operator-runbook unknown (memo §7 item 6), so this mock-specific reload-poll behavior must not be treated as a real-site signal.
        """

        page = self._require_page()
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            self._raise_open_failures()
            if self._rate_limit_visible():
                raise self._rate_limited_error()
            if self._present("truncation_marker"):
                raise ResponseTruncatedError("truncation marker visible on assistant response")

            latest_assistant = self._latest_assistant_turn()
            latest_is_streaming = False
            if latest_assistant is not None:
                truncation_selector = self._optional_selector("truncation_marker")
                if truncation_selector is not None and latest_assistant.locator(truncation_selector).count() > 0:
                    raise ResponseTruncatedError("latest assistant turn has a truncation marker")
                if latest_assistant.locator(self.selectors.selector("completion_marker")).count() > 0:
                    return latest_assistant
                latest_is_streaming = latest_assistant.locator(self.selectors.selector("streaming_marker")).count() > 0

            now = time.monotonic()
            if now >= deadline:
                raise ResponseTruncatedError("completion marker did not appear before timeout")

            if (latest_is_streaming or (latest_assistant is None and self._present("streaming_marker"))) and self.channel == "mock":
                conversation_ref = self._active_conversation_ref or self._try_read_active_conversation_ref()
                if conversation_ref:
                    page.goto(self._conversation_url(conversation_ref), wait_until="load", timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
                    self._active_conversation_ref = conversation_ref
                    continue
            page.wait_for_timeout(int(min(_POLL_INTERVAL_S, max(0.0, deadline - now)) * 1000))

    def _start_mock_context(self) -> None:
        if self._base_url is None:
            raise AskChatGPTError("Mock channel requires a loopback base_url. Operator action: pass mock_chatgpt.base_url and retry.")
        if not _is_loopback_http_url(self._base_url):
            raise AskChatGPTError("Mock channel base_url must be loopback. Operator action: pass the loopback mock fixture URL and retry.")
        assert self._playwright is not None
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(accept_downloads=True)
        self._install_mock_route_guard()
        if self._grant_clipboard:
            self._context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self._base_url)

    def _install_mock_route_guard(self) -> None:
        if self._context is None:
            raise AskChatGPTError("Browser context is unavailable. Operator action: start the session and retry.")
        self._install_loopback_route_guard(self._context)

    def _install_cdp_route_guard(self, page: Page) -> None:
        if _is_loopback_http_url(self._base_url):
            self._install_loopback_route_guard(page)
        else:
            install_real_allowlist(page, on_abort=self.aborted_off_domain_hosts.append)

    def _install_loopback_route_guard(self, route_owner: Any) -> None:
        def guard(route: Any) -> None:
            if _is_loopback_request_url(route.request.url):
                route.continue_()
            else:
                route.abort("blockedbyclient")

        route_owner.route("**/*", guard)

    def _ensure_real_selector_map_ready(self) -> None:
        for key in _REAL_REQUIRED_SELECTOR_KEYS:
            self.selectors.selector(key)
        for key in _REAL_REQUIRED_ATTRIBUTE_KEYS:
            self.selectors.attribute(key)

    def _preflight_profile_lock(self) -> None:
        if self._profile_path is None:
            return
        if os.path.lexists(self._profile_path / "SingletonLock"):
            raise ProfileLockedError()

    def _raise_login_required_for_auth_redirect(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
        if (
            "auth.openai.com" in host
            or "auth0" in host
            or "accounts." in host
            or path.startswith("/auth/login")
            or path.startswith("/auth")
            or path.startswith("/login")
            or "/api/auth/" in path
        ):
            raise LoginRequiredError("browser redirected to a login/auth URL shape")

    def _raise_challenge_present_if_detected(self) -> None:
        page = self._require_page()
        try:
            title = page.title().strip().lower()
        except PlaywrightError:
            title = ""
        if "just a moment" in title or "verify you are human" in title or "checking your browser" in title:
            raise ChallengePresentError("CHALLENGE_PRESENT: challenge-like page title detected")

        for selector in ("#challenge-running", "iframe[src*='challenges.cloudflare.com']"):
            try:
                if page.locator(selector).count() > 0:
                    raise ChallengePresentError("CHALLENGE_PRESENT: challenge marker detected")
            except ChallengePresentError:
                raise
            except PlaywrightError:
                continue

    def _start_real_context(self) -> None:
        if self._profile_path is None:
            raise AskChatGPTError("Real channel requires an opaque profile_path directory. Operator action: pass the operator-owned profile path and retry.")
        assert self._playwright is not None
        try:
            launch_kwargs: dict[str, Any] = {
                "user_data_dir": str(self._profile_path),
                "headless": False,
                "accept_downloads": True,
            }
            if self._executable_path is not None:
                launch_kwargs["executable_path"] = str(self._executable_path)
            self._context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            install_real_allowlist(self._context, on_abort=self.aborted_off_domain_hosts.append)
        except Exception as exc:
            if _is_profile_lock_launch_error(exc):
                raise ProfileLockedError("browser launch reported an existing profile lock") from exc
            raise AskChatGPTError(
                "Real browser launch failed. Operator action: check the opaque profile directory and browser availability, then retry."
            ) from None

    def _start_cdp_context(self) -> None:
        assert self._playwright is not None
        endpoint = str(self._cdp_endpoint or _DEFAULT_CDP_ENDPOINT)
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(endpoint, timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
        except PlaywrightError as exc:
            raise CDPUnreachableError(f"CDP_UNREACHABLE: connect_over_cdp failed for endpoint {endpoint!r}") from exc
        if not self._browser.contexts:
            raise CDPUnreachableError(f"CDP_UNREACHABLE: endpoint {endpoint!r} exposed no browser contexts")
        self._context = self._browser.contexts[0]

    def _new_or_existing_page(self) -> Page:
        if self._context is None:
            raise AskChatGPTError("Browser context is unavailable. Operator action: start the session and retry.")
        return self._context.pages[0] if self._context.pages else self._context.new_page()

    def _new_cdp_page(self) -> Page:
        if self._context is None:
            raise AskChatGPTError("Browser context is unavailable. Operator action: start the session and retry.")
        page = self._context.new_page()
        self._cdp_owned_pages.append(page)
        return page

    @staticmethod
    def _resolve_base_url(*, channel: str, base_url: str | None) -> str:
        if channel in {"real", "cdp"} and base_url is None:
            return REAL_BASE_URL
        if base_url is None:
            return ""
        return str(base_url).rstrip("/")

    @staticmethod
    def _selector_map_channel(*, channel: str, base_url: str) -> str:
        if channel == "cdp":
            return "mock" if _is_loopback_http_url(base_url) else "real"
        return channel

    def _require_page(self) -> Page:
        if self.page is None:
            raise AskChatGPTError("BrowserSession is not started. Operator action: use it as a context manager or call start().")
        return self.page

    def _conversation_url(self, conversation_ref: str) -> str:
        ref = str(conversation_ref)
        return f"{self._base_url}/c/{quote(ref, safe='')}"

    def _conversation_ref_from_url(self, url: str) -> str | None:
        segments = [segment for segment in urlparse(url).path.split("/") if segment]
        if len(segments) >= 2 and segments[0] == "c" and segments[1]:
            return unquote(segments[1])
        return None

    def _locator(self, key: str) -> Locator:
        return self._require_page().locator(self.selectors.selector(key))

    def _optional_selector(self, key: str) -> str | None:
        try:
            return self.selectors.selector(key)
        except SelectorUnavailableError:
            return None

    def _present(self, key: str) -> bool:
        selector = self._optional_selector(key)
        if selector is None:
            return False
        try:
            return self._require_page().locator(selector).count() > 0
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector '{key}' unavailable for channel '{self.channel}'") from exc

    def _require_present(self, key: str) -> Locator:
        locator = self._locator(key)
        try:
            count = locator.count()
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector '{key}' unavailable for channel '{self.channel}'") from exc
        if count < 1:
            raise SelectorUnavailableError(f"selector '{key}' unavailable for channel '{self.channel}'")
        return locator.first

    def _wait_for_ready_root(self, *, timeout_ms: int = _READY_ROOT_TIMEOUT_MS) -> None:
        if self.channel not in {"real", "cdp"}:
            return
        page = self._require_page()
        selector = self.selectors.selector("ready_root")
        try:
            page.wait_for_selector(selector, timeout=timeout_ms, state="attached")
        except PlaywrightTimeoutError as exc:
            title = _page_title_for_error(page)
            path_shape = _url_path_shape(page.url)
            raise SelectorUnavailableError(
                "ChatGPT app did not become ready: selector 'ready_root' did not attach "
                f"within {timeout_ms} ms for channel '{self.channel}' "
                f"(title={title!r}, path_shape={path_shape!r}). Operator action: wait for SPA hydration, "
                "resolve any login/challenge UI, or update the ready_root selector map."
            ) from exc
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector 'ready_root' unavailable for channel '{self.channel}'") from exc

    def _raise_open_failures(self) -> None:
        if self._present("conversation_not_found"):
            raise SessionNotFoundError("conversation-not-found marker visible")
        if self._present("login_wall"):
            raise LoginRequiredError("login wall marker visible")

    def _read_active_conversation_ref(self) -> str:
        root = self._require_present("ready_root")
        try:
            attr = self.selectors.attribute("conversation_ref")
        except SelectorUnavailableError:
            attr = None
        if attr:
            ref = root.get_attribute(attr)
            if ref:
                return ref
        ref = self._conversation_ref_from_url(self._require_page().url)
        if ref:
            return ref
        raise SessionNotFoundError("active conversation reference attribute is empty")

    def _try_read_active_conversation_ref(self) -> str | None:
        try:
            return self._read_active_conversation_ref()
        except (SelectorUnavailableError, SessionNotFoundError, PlaywrightError):
            return None

    def _find_model_option(self, requested: str) -> Locator | None:
        options = self._locator("model_option")
        try:
            count = options.count()
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector 'model_option' unavailable for channel '{self.channel}'") from exc
        for index in range(count):
            option = options.nth(index)
            value = option.get_attribute("value")
            text = option.inner_text().strip()
            if requested in {value, text}:
                return option
        return None

    def _latest_assistant_turn(self) -> Locator | None:
        assistant_selector = self.selectors.selector("assistant_message")
        try:
            assistant_turns = self._require_page().locator(assistant_selector)
            count = assistant_turns.count()
        except PlaywrightError as exc:
            raise SelectorUnavailableError(f"selector 'assistant_message' unavailable for channel '{self.channel}'") from exc
        if count < 1:
            return None
        return assistant_turns.nth(count - 1)

    def _rate_limit_visible(self) -> bool:
        return self._present("rate_limit_marker")

    def _rate_limited_error(self) -> RateLimitedError:
        marker = self._locator("rate_limit_marker").first
        retry_after = marker.get_attribute("data-retry-after-seconds")
        detail = "rate-limit marker visible"
        if retry_after:
            detail += f"; retry after {retry_after} seconds"
        return RateLimitedError(detail)

    def _wait_for_load_state(self, *, ignore_timeout: bool = False) -> None:
        try:
            self._require_page().wait_for_load_state("load", timeout=_DEFAULT_NAVIGATION_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            if not ignore_timeout:
                raise AskChatGPTError("Browser load did not finish before timeout. Operator action: inspect the UI and retry.") from None


def _page_title_for_error(page: Page) -> str:
    try:
        title = " ".join(page.title().split())
    except PlaywrightError:
        return "<unavailable>"
    if not title:
        return "<empty>"
    if len(title) > 120:
        return title[:117] + "..."
    return title


def _url_path_shape(url: str) -> str:
    segments = [segment for segment in urlparse(str(url)).path.split("/") if segment]
    if not segments:
        return "/"
    public_route_segments = {"api", "auth", "backend-api", "c", "g", "gpts", "login", "share"}
    shaped = [segment.lower() if segment.lower() in public_route_segments else "<segment>" for segment in segments[:5]]
    if len(segments) > 5:
        shaped.append("...")
    return "/" + "/".join(shaped)


def _is_profile_lock_launch_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "singleton" in message
        or "already in use" in message
        or ("profile" in message and "lock" in message)
    )


def _is_loopback_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        return False
    return _is_loopback_host(parsed.hostname)


def _is_loopback_request_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        return True
    return _is_loopback_host(parsed.hostname)


def _is_loopback_host(host: str | None) -> bool:
    if host in {"127.0.0.1", "localhost", "::1"}:
        return True
    if host is None:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


__all__ = ["BrowserSession", "REAL_BASE_URL"]
