"""Fail-closed Radix menu selection over the BrowserChannel seam."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ask_chatgpt.channels.base import TabLease
from ask_chatgpt.errors import (
    ModelSelectionNotReflectedError,
    SelectorNotFoundError,
    ToolSelectionNotReflectedError,
)
from ask_chatgpt.models import JsonValue, SelectorMap
from ask_chatgpt.send import _monotonic, _sleep_until, normalize_prompt

_MENU_ENUMERATE_KEY = "ask_chatgpt_menu_enumerate"
_MENU_CLICK_LABEL_KEY = "ask_chatgpt_menu_click_label"
_OPEN_RADIX_TRIGGER_KEY = "ask_chatgpt_open_radix_trigger"
_RADIX_PORTAL_SELECTOR = "[data-radix-popper-content-wrapper]"
_FORBIDDEN_SUBMENUS = {normalize_prompt("Recent files"), normalize_prompt("Projects")}
_MODEL_LABEL_ATTEMPTS = 6
_MODEL_LABEL_INTERVAL_S = 2.0
_TOOL_CHIP_REFLECTION_TIMEOUT_S = 1.0


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
    result = tab.channel.evaluate(
        tab,
        _OPEN_RADIX_TRIGGER_KEY,
        arg={"selector": trigger_selector},
        timeout_s=5.0,
    )
    if not _ok_result(result):
        raise SelectorNotFoundError(
            "radix trigger did not open",
            details={"selector": trigger_selector},
        )
    tab.channel.wait_for_selector(tab, _RADIX_PORTAL_SELECTOR, state="visible", timeout_s=5.0)


def enumerate_radix_options(tab: TabLease) -> tuple[MenuOption, ...]:
    raw = tab.channel.evaluate(tab, _MENU_ENUMERATE_KEY, arg={"portal_selector": _RADIX_PORTAL_SELECTOR}, timeout_s=5.0)
    if not isinstance(raw, list | tuple):
        return ()
    parsed: list[MenuOption] = []
    for item in raw:
        option = _option_from_raw(item)
        if option is not None:
            parsed.append(option)
    return tuple(parsed)


def select_radix_label(
    tab: TabLease,
    label: str,
    *,
    role: str | None = None,
    submenu_path: Sequence[str] = (),
) -> MenuOption:
    path = tuple(submenu_path)
    for depth, submenu_label in enumerate(path):
        _ensure_not_forbidden_submenu(submenu_label)
        submenu = _exactly_one_enabled(
            enumerate_radix_options(tab),
            submenu_label,
            role="menuitem",
            error_type=ModelSelectionNotReflectedError,
        )
        _click_menu_label(tab, submenu, action="open_submenu", path=path[:depth])
    option = _exactly_one_enabled(
        enumerate_radix_options(tab),
        label,
        role=role,
        error_type=ModelSelectionNotReflectedError,
    )
    _ensure_not_forbidden_submenu(option.label)
    _click_menu_label(tab, option, action="select", path=path)
    return option


def select_model(tab: TabLease, selectors: SelectorMap, label: str) -> SelectionResult:
    try:
        _require_unambiguous_model_trigger(tab, selectors)
        open_radix_menu(tab, selectors["model_picker_trigger_candidates"])
        options = enumerate_radix_options(tab)
        requested = normalize_prompt(label)
        direct = _enabled_matches(options, requested, role="menuitemradio")
        family = _enabled_matches(options, requested, role="menuitem")
        if len(direct) == 1:
            selected = select_radix_label(tab, label, role="menuitemradio")
        elif len(direct) > 1 or len(family) > 1:
            raise ModelSelectionNotReflectedError(
                "requested model label is ambiguous",
                details={"requested_model": label},
            )
        elif len(family) == 1:
            selected = select_radix_label(tab, label, role="menuitemradio", submenu_path=(family[0].label,))
        else:
            selected = _select_model_from_family_submenus(tab, selectors, label, options)
        reflected = _reflected_model(tab, selectors, label)
        if reflected is None:
            raise ModelSelectionNotReflectedError(
                "requested model was selected but not reflected",
                details={"requested_model": label, "selected_label": selected.label},
            )
        return SelectionResult(requested=label, reflected=reflected, verified=True)
    except ModelSelectionNotReflectedError:
        raise
    except Exception as exc:  # noqa: BLE001 - browser/menu failures fail closed through the public error.
        raise ModelSelectionNotReflectedError(
            "model selection failed closed",
            details={"requested_model": label, "reason": type(exc).__name__},
        ) from exc


def _select_model_from_family_submenus(
    tab: TabLease,
    selectors: SelectorMap,
    label: str,
    top_level_options: Sequence[MenuOption],
) -> MenuOption:
    requested = normalize_prompt(label)
    families = [
        option
        for option in top_level_options
        if option.role == "menuitem"
        and not option.disabled
        and normalize_prompt(option.label) not in _FORBIDDEN_SUBMENUS
    ]
    matches: list[tuple[MenuOption, MenuOption]] = []
    for family in families:
        _close_radix_menu(tab)
        open_radix_menu(tab, selectors["model_picker_trigger_candidates"])
        current_family = _exactly_one_enabled(
            enumerate_radix_options(tab),
            family.label,
            role="menuitem",
            error_type=ModelSelectionNotReflectedError,
        )
        _click_menu_label(tab, current_family, action="open_submenu", path=())
        submenu_matches = _enabled_matches(enumerate_radix_options(tab), requested, role="menuitemradio")
        if len(submenu_matches) > 1:
            _close_radix_menu(tab)
            raise ModelSelectionNotReflectedError(
                "requested model label is ambiguous in family submenu",
                details={"requested_model": label, "family": family.label, "match_count": len(submenu_matches)},
            )
        if len(submenu_matches) == 1:
            matches.append((current_family, submenu_matches[0]))
    _close_radix_menu(tab)
    if len(matches) != 1:
        reason = "absent" if not matches else "ambiguous"
        details: dict[str, JsonValue] = {"requested_model": label}
        if matches:
            details["match_count"] = len(matches)
        raise ModelSelectionNotReflectedError(
            f"requested model label is {reason}",
            details=details,
        )
    family, _submenu_option = matches[0]
    open_radix_menu(tab, selectors["model_picker_trigger_candidates"])
    return select_radix_label(tab, label, role="menuitemradio", submenu_path=(family.label,))


def set_tools(
    tab: TabLease, selectors: SelectorMap, labels: Sequence[str]
) -> tuple[SelectionResult, ...]:
    if not labels:
        return ()
    results: list[SelectionResult] = []
    try:
        for label in labels:
            open_radix_menu(tab, selectors["tools_button"])
            selected = select_radix_label(tab, label)
            try:
                reflected = _reflected_tool_by_reopen(tab, selectors, label)
            finally:
                _close_radix_menu(tab)
            if reflected is None:
                reflected = _reflected_tool_by_chip(tab, selectors, selected.label)
            if reflected is None:
                raise ToolSelectionNotReflectedError(
                    "requested tool was selected but not reflected",
                    details={"requested_tool": label, "selected_label": selected.label},
                )
            results.append(SelectionResult(requested=label, reflected=reflected, verified=True))
        return tuple(results)
    except ToolSelectionNotReflectedError:
        raise
    except ModelSelectionNotReflectedError as exc:
        raise ToolSelectionNotReflectedError(
            "tool selection failed closed",
            details={"requested_tool": labels[0], "reason": exc.code},
        ) from exc
    except Exception as exc:  # noqa: BLE001 - browser/menu failures fail closed through the public error.
        raise ToolSelectionNotReflectedError(
            "tool selection failed closed",
            details={"requested_tool": labels[0], "reason": type(exc).__name__},
        ) from exc


def assert_reflected_model(tab: TabLease, selectors: SelectorMap, label: str) -> None:
    select_model(tab, selectors, label)


def assert_reflected_tools(
    tab: TabLease, selectors: SelectorMap, labels: Sequence[str]
) -> None:
    set_tools(tab, selectors, labels)


def _option_from_raw(item: object) -> MenuOption | None:
    if not isinstance(item, Mapping):
        return None
    label_value = item.get("label")
    if not isinstance(label_value, str):
        return None
    label = normalize_prompt(" ".join(label_value.split()))
    if not label:
        return None
    role_value = item.get("role")
    role = role_value if isinstance(role_value, str) else None
    checked_value = item.get("checked")
    checked = checked_value if isinstance(checked_value, bool) else None
    path_raw = item.get("path")
    path = tuple(str(part) for part in path_raw) if isinstance(path_raw, list | tuple) else ()
    return MenuOption(
        label=label,
        role=role,
        checked=checked,
        disabled=bool(item.get("disabled")),
        path=path,
    )


def _enabled_matches(options: Sequence[MenuOption], normalized_label: str, *, role: str | None) -> list[MenuOption]:
    return [
        option
        for option in options
        if not option.disabled
        and normalize_prompt(option.label) == normalized_label
        and (role is None or option.role == role)
    ]


def _exactly_one_enabled(
    options: Sequence[MenuOption],
    label: str,
    *,
    role: str | None,
    error_type: type[ModelSelectionNotReflectedError],
) -> MenuOption:
    matches = _enabled_matches(options, normalize_prompt(label), role=role)
    if len(matches) != 1:
        reason = "absent" if not matches else "ambiguous"
        raise error_type(
            f"menu label is {reason}",
            details={"label": label, "role": role, "match_count": len(matches)},
        )
    return matches[0]


def _click_menu_label(tab: TabLease, option: MenuOption, *, action: str, path: Sequence[str]) -> None:
    result = tab.channel.evaluate(
        tab,
        _MENU_CLICK_LABEL_KEY,
        arg={
            "label": option.label,
            "role": option.role,
            "path": list(path),
            "action": action,
        },
        timeout_s=5.0,
    )
    if not _ok_result(result):
        raise ModelSelectionNotReflectedError(
            "menu label click failed closed",
            details={"label": option.label, "role": option.role, "action": action},
        )


def _ok_result(result: object) -> bool:
    return isinstance(result, Mapping) and result.get("ok") is True


def _require_unambiguous_model_trigger(tab: TabLease, selectors: SelectorMap) -> None:
    labels = _sustained_model_labels(tab, selectors, want=None)
    if len(labels) != 1:
        raise ModelSelectionNotReflectedError(
            "model picker trigger is absent or ambiguous",
            details={"model_trigger_count": len(labels)},
        )


def _reflected_model(tab: TabLease, selectors: SelectorMap, label: str) -> str | None:
    labels = _sustained_model_labels(tab, selectors, want=label)
    requested = normalize_prompt(label)
    for candidate in labels:
        if normalize_prompt(candidate) == requested:
            return candidate
    return None


def _sustained_model_labels(
    tab: TabLease,
    selectors: SelectorMap,
    *,
    want: str | None,
    attempts: int = _MODEL_LABEL_ATTEMPTS,
    interval_s: float = _MODEL_LABEL_INTERVAL_S,
) -> tuple[str, ...]:
    requested = normalize_prompt(want) if want is not None else None
    last_labels: tuple[str, ...] = ()
    for _attempt in range(max(1, int(attempts))):
        snapshot = tab.channel.query_turns(tab, selectors)
        labels = tuple(label for label in snapshot.model_labels if normalize_prompt(label))
        last_labels = labels
        if requested is not None:
            if any(normalize_prompt(candidate) == requested for candidate in labels):
                return labels
        elif len(labels) == 1:
            return labels
        _sleep_until(tab, _monotonic(tab) + max(0.0, float(interval_s)))
    return last_labels


def _reflected_tool_by_reopen(tab: TabLease, selectors: SelectorMap, label: str) -> str | None:
    open_radix_menu(tab, selectors["tools_button"])
    return _reflected_tool(tab, label)


def _reflected_tool_by_chip(
    tab: TabLease, selectors: SelectorMap, reflected_label: str
) -> str | None:
    if not normalize_prompt(reflected_label):
        return None
    try:
        tab.channel.wait_for_selector(
            tab,
            _tool_chip_selector(selectors["active_tool_chip"], reflected_label),
            state="visible",
            timeout_s=_TOOL_CHIP_REFLECTION_TIMEOUT_S,
        )
    except SelectorNotFoundError:
        return None
    return reflected_label


def _tool_chip_selector(active_tool_chip_selector: str, reflected_label: str) -> str:
    label = _css_attr_string(normalize_prompt(reflected_label))
    return f":is({active_tool_chip_selector})[aria-label*={label} i]"


def _css_attr_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _close_radix_menu(tab: TabLease) -> None:
    try:
        tab.channel.press(tab, "body", "Escape")
    except Exception:  # noqa: BLE001 - best-effort cleanup must not mask selection failures.
        return


def _reflected_tool(tab: TabLease, label: str) -> str | None:
    matches = [
        option
        for option in _enabled_matches(enumerate_radix_options(tab), normalize_prompt(label), role=None)
        if option.checked is True
    ]
    if len(matches) == 1:
        return matches[0].label
    return None


def _ensure_not_forbidden_submenu(label: str) -> None:
    if normalize_prompt(label) in _FORBIDDEN_SUBMENUS:
        raise ModelSelectionNotReflectedError(
            "forbidden privacy-sensitive submenu was not opened",
            details={"label": label},
        )


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
