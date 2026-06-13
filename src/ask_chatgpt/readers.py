"""Bounded assistant-response readers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from playwright.sync_api import Error as PlaywrightError, Locator, Page

from ask_chatgpt.errors import ResponseTruncatedError, SelectorUnavailableError
from ask_chatgpt.selector_map import SelectorMap

_READER_TIMEOUT_MS = 1_000


class ResponseReader(ABC):
    """Read a response from one latest completed assistant turn."""

    name: str

    @abstractmethod
    def read(self, turn_locator: Locator, page: Page, selectors: SelectorMap) -> str:
        """Return text extracted only from ``turn_locator`` or raise a named error."""


class DomReader(ResponseReader):
    """Primary reader: bounded rendered-text extraction inside one assistant turn."""

    name = "dom"

    def read(self, turn_locator: Locator, page: Page, selectors: SelectorMap) -> str:  # noqa: ARG002 - interface parity
        assistant_selector = selectors.selector("assistant_message")
        body_selector = selectors.selector("message_body")
        try:
            truncation_selector = selectors.selector("truncation_marker")
        except SelectorUnavailableError:
            truncation_selector = None
        try:
            _require_turn_locator(turn_locator, self.name)
            is_assistant = bool(
                turn_locator.first.evaluate("(element, selector) => element.matches(selector)", assistant_selector)
            )
            if not is_assistant:
                raise SelectorUnavailableError("DOM reader received a turn that does not match selector 'assistant_message'")
            if truncation_selector is not None and turn_locator.locator(truncation_selector).count() > 0:
                raise ResponseTruncatedError("latest assistant turn has a truncation marker")

            body = turn_locator.locator(body_selector)
            if body.count() < 1:
                raise SelectorUnavailableError("selector 'message_body' matched no element inside the latest assistant turn")
            text = body.first.inner_text(timeout=_READER_TIMEOUT_MS)
        except (ResponseTruncatedError, SelectorUnavailableError):
            raise
        except PlaywrightError as exc:
            raise SelectorUnavailableError(
                "DOM reader could not read selector-map-scoped message_body inside the latest assistant turn"
            ) from exc

        if not text.strip():
            raise SelectorUnavailableError("selector 'message_body' matched empty text inside the latest assistant turn")
        return text


class CopyButtonReader(ResponseReader):
    """Fallback reader: click the turn-local copy button and read the clipboard."""

    name = "copy_button"

    def read(self, turn_locator: Locator, page: Page, selectors: SelectorMap) -> str:
        button_selector = selectors.selector("copy_button")
        try:
            _require_turn_locator(turn_locator, self.name)
            button = turn_locator.locator(button_selector)
            if button.count() < 1:
                raise SelectorUnavailableError("selector 'copy_button' matched no element inside the latest assistant turn")
            button.first.click(timeout=_READER_TIMEOUT_MS)
            text = page.evaluate("() => navigator.clipboard.readText()")
        except SelectorUnavailableError:
            raise
        except PlaywrightError as exc:
            raise SelectorUnavailableError(
                "copy-button reader could not click the turn-local copy affordance or read clipboard text"
            ) from exc

        if not isinstance(text, str):
            raise SelectorUnavailableError("clipboard read did not return text after clicking the copy button")
        return text


DEFAULT_READER_ORDER: tuple[ResponseReader, ...] = (DomReader(), CopyButtonReader())


def read_response(
    turn_locator: Locator,
    page: Page,
    selectors: SelectorMap,
    order: Iterable[ResponseReader] | None = None,
) -> str:
    """Read response text with configurable order, falling through only on selector unavailability."""

    readers = DEFAULT_READER_ORDER if order is None else tuple(order)
    unavailable: list[str] = []
    for reader in readers:
        try:
            return reader.read(turn_locator, page, selectors)
        except SelectorUnavailableError as exc:
            name = getattr(reader, "name", reader.__class__.__name__)
            unavailable.append(f"{name}: {exc.detail or str(exc)}")

    detail = "no response readers configured" if not unavailable else "all response readers unavailable; " + "; ".join(unavailable)
    raise SelectorUnavailableError(detail)


def _require_turn_locator(turn_locator: Locator, reader_name: str) -> None:
    try:
        if turn_locator.count() < 1:
            raise SelectorUnavailableError(f"{reader_name} reader received an empty turn locator")
    except SelectorUnavailableError:
        raise
    except PlaywrightError as exc:
        raise SelectorUnavailableError(f"{reader_name} reader could not evaluate the latest assistant turn locator") from exc


__all__ = [
    "CopyButtonReader",
    "DEFAULT_READER_ORDER",
    "DomReader",
    "ResponseReader",
    "read_response",
]
