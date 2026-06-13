from __future__ import annotations

import pytest
from playwright.sync_api import Error as PlaywrightError

from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import LoginRequiredError, SelectorUnavailableError, SessionNotFoundError
from ask_chatgpt.selector_map import SelectorMap


_OPTIONAL_MARKERS = (
    "conversation_not_found",
    "login_wall",
    "truncation_marker",
    "rate_limit_marker",
)


class _FakeLocator:
    def __init__(
        self,
        *,
        count: int = 0,
        count_error: Exception | None = None,
        children: dict[str, "_FakeLocator"] | None = None,
        items: list["_FakeLocator"] | None = None,
    ) -> None:
        self._count = count
        self._count_error = count_error
        self._children = {} if children is None else children
        self._items = [] if items is None else items

    def count(self) -> int:
        if self._count_error is not None:
            raise self._count_error
        return self._count

    @property
    def first(self) -> "_FakeLocator":
        return self

    def nth(self, index: int) -> "_FakeLocator":
        return self._items[index]

    def locator(self, selector: str) -> "_FakeLocator":
        try:
            return self._children[selector]
        except KeyError as exc:
            raise AssertionError(f"unexpected nested selector: {selector}") from exc


class _FakePage:
    def __init__(self, locators: dict[str, _FakeLocator] | None = None) -> None:
        self.url = "http://127.0.0.1:9/c/unit"
        self._locators = {} if locators is None else locators
        self.locator_calls: list[str] = []
        self.wait_timeouts: list[int] = []

    def locator(self, selector: str) -> _FakeLocator:
        self.locator_calls.append(selector)
        try:
            return self._locators[selector]
        except KeyError as exc:
            raise AssertionError(f"unexpected selector: {selector}") from exc

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_timeouts.append(timeout_ms)


def _unit_session(selectors: dict[str, str], page: _FakePage | None = None) -> BrowserSession:
    session = BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
    session.selectors = SelectorMap(channel="unit", selectors=selectors, attributes={})
    session.page = _FakePage() if page is None else page
    return session


def test_optional_presence_markers_return_false_when_selector_is_empty() -> None:
    page = _FakePage()
    session = _unit_session({key: "" for key in _OPTIONAL_MARKERS}, page)

    for key in _OPTIONAL_MARKERS:
        assert session._present(key) is False

    assert page.locator_calls == []


def test_open_failures_do_not_raise_when_optional_markers_are_empty() -> None:
    page = _FakePage()
    session = _unit_session({"conversation_not_found": "", "login_wall": ""}, page)

    session._raise_open_failures()

    assert page.locator_calls == []


def test_rate_limit_visible_returns_false_when_optional_marker_is_empty() -> None:
    page = _FakePage()
    session = _unit_session({"rate_limit_marker": ""}, page)

    assert session._rate_limit_visible() is False
    assert page.locator_calls == []


def test_present_still_wraps_playwright_errors_for_configured_selector() -> None:
    page = _FakePage({"#rate-limit": _FakeLocator(count_error=PlaywrightError("count failed"))})
    session = _unit_session({"rate_limit_marker": "#rate-limit"}, page)

    with pytest.raises(SelectorUnavailableError, match="selector 'rate_limit_marker' unavailable"):
        session._present("rate_limit_marker")


def test_raise_open_failures_still_raises_login_wall_when_mock_marker_present(mock_chatgpt) -> None:
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="login_required")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(LoginRequiredError):
            session._raise_open_failures()


def test_raise_open_failures_still_raises_session_not_found_when_mock_marker_present(mock_chatgpt) -> None:
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="session_not_found")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        assert session.page is not None
        session.page.goto(f"{mock_chatgpt.base_url}/c/missing-optional-marker", wait_until="load")
        with pytest.raises(SessionNotFoundError):
            session._raise_open_failures()


def test_wait_for_completion_skips_unmapped_truncation_marker_on_completed_turn() -> None:
    latest_assistant = _FakeLocator(
        count=1,
        children={
            "[complete]": _FakeLocator(count=1),
            "[streaming]": _FakeLocator(count=0),
        },
    )
    page = _FakePage({"[assistant]": _FakeLocator(count=1, items=[latest_assistant])})
    session = _unit_session(
        {
            "conversation_not_found": "",
            "login_wall": "",
            "rate_limit_marker": "",
            "truncation_marker": "",
            "assistant_message": "[assistant]",
            "completion_marker": "[complete]",
            "streaming_marker": "[streaming]",
        },
        page,
    )

    assert session.wait_for_completion(timeout_s=0.01) is latest_assistant
    assert page.wait_timeouts == []
