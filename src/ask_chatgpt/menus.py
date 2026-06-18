"""M4 fail-closed menu selection stubs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ask_chatgpt.channels.base import TabLease
from ask_chatgpt.errors import ModelSelectionNotReflectedError, ToolSelectionNotReflectedError
from ask_chatgpt.models import SelectorMap
from ask_chatgpt.send import normalize_prompt


@dataclass(frozen=True)
class MenuOption:
    label: str
    role: str | None
    checked: bool | None
    disabled: bool
    path: tuple[str, ...]


@dataclass(frozen=True)
class SelectionResult:
    requested: str
    reflected: str | None
    verified: bool


def open_radix_menu(tab: TabLease, trigger_selector: str) -> None:
    del tab, trigger_selector
    raise ModelSelectionNotReflectedError("M4 does not perform Radix menu mutation")


def enumerate_radix_options(tab: TabLease) -> tuple[MenuOption, ...]:
    del tab
    return ()


def select_radix_label(
    tab: TabLease,
    label: str,
    *,
    role: str | None = None,
    submenu_path: Sequence[str] = (),
) -> MenuOption:
    del tab, role, submenu_path
    raise ModelSelectionNotReflectedError(
        "M4 does not perform Radix menu mutation",
        details={"requested_label": label},
    )


def select_model(tab: TabLease, selectors: SelectorMap, label: str) -> SelectionResult:
    reflected = _reflected_model(tab, selectors, label)
    if reflected is None:
        raise ModelSelectionNotReflectedError(
            "requested model is not reflected before send",
            details={"requested_model": label},
        )
    return SelectionResult(requested=label, reflected=reflected, verified=True)


def set_tools(
    tab: TabLease, selectors: SelectorMap, labels: Sequence[str]
) -> tuple[SelectionResult, ...]:
    if not labels:
        return ()
    del tab, selectors
    first = labels[0]
    raise ToolSelectionNotReflectedError(
        "requested tools are not reflected before send",
        details={"requested_tool": first, "tool_count": len(labels)},
    )


def assert_reflected_model(tab: TabLease, selectors: SelectorMap, label: str) -> None:
    select_model(tab, selectors, label)


def assert_reflected_tools(
    tab: TabLease, selectors: SelectorMap, labels: Sequence[str]
) -> None:
    set_tools(tab, selectors, labels)


def _reflected_model(tab: TabLease, selectors: SelectorMap, label: str) -> str | None:
    snapshot = tab.channel.query_turns(tab, selectors)
    requested = normalize_prompt(label)
    for candidate in snapshot.model_labels:
        if normalize_prompt(candidate) == requested:
            return candidate
    return None


__all__ = [
    "MenuOption",
    "SelectionResult",
    "assert_reflected_model",
    "assert_reflected_tools",
    "enumerate_radix_options",
    "open_radix_menu",
    "select_model",
    "select_radix_label",
    "set_tools",
]
