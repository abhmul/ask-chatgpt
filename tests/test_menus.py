from __future__ import annotations

import pytest

from ask_chatgpt.channels.base import TurnDomSnapshot
from ask_chatgpt.channels.mock import MockChannel, MockScenario, ScriptedClock, TimedTurnSnapshot
from ask_chatgpt.errors import ModelSelectionNotReflectedError, ToolSelectionNotReflectedError
from ask_chatgpt.menus import enumerate_radix_options, open_radix_menu, select_model, set_tools


SELECTORS = {
    "composer": "#prompt-textarea",
    "tools_button": "button[data-testid=\"composer-plus-btn\"]",
    "message_turn": "[data-message-id][data-message-author-role]",
    "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
    "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
    "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
    "stop_button": "button[data-testid=\"stop-button\"]",
    "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button, button[aria-label=\"Send prompt\"]",
    "radix_portal": "[data-radix-popper-content-wrapper]",
    "model_picker_trigger_candidates": "form button[aria-haspopup=\"menu\"]:not([data-testid])",
}


def _snapshot(*, model_labels: tuple[str, ...] = ("Medium",)) -> TurnDomSnapshot:
    return TurnDomSnapshot(
        users=(),
        assistants=(),
        stop_visible=False,
        composer_visible=True,
        model_labels=model_labels,
    )


def _tab(channel: MockChannel):
    return channel.open_tab("https://chatgpt.com/")


def _option(label: str, role: str | None = "menuitemradio", *, checked: bool | None = False, disabled: bool = False, path: tuple[str, ...] = ()) -> dict[str, object]:
    return {"label": label, "role": role, "checked": checked, "disabled": disabled, "path": list(path)}


def test_open_radix_menu_uses_pointer_activation_evaluate_not_click() -> None:
    # Falsifiability: reverting open_radix_menu to channel.click removes this evaluate call and increments click.
    channel = MockChannel(MockScenario(name="radix_open_path", menu_options={"model": (_option("High"),)}))
    tab = _tab(channel)

    open_radix_menu(tab, SELECTORS["model_picker_trigger_candidates"])

    assert channel.method_counts.get("click", 0) == 0
    assert any(
        call.method == "evaluate" and call.details.get("js_key") == "ask_chatgpt_open_radix_trigger"
        for call in channel.calls
    )
    assert channel.method_counts.get("wait_for_selector", 0) == 1


def test_select_model_opens_enumerates_selects_tier_and_verifies_reflected_label() -> None:
    channel = MockChannel(
        MockScenario(
            name="model_tier_happy_path",
            turn_timeline=(TimedTurnSnapshot(0.0, _snapshot()),),
            menu_options={"model": (_option("High"),)},
            menu_reflected_model_labels={"High": ("High",)},
        )
    )

    result = select_model(_tab(channel), SELECTORS, "High")

    assert result.requested == "High"
    assert result.reflected == "High"
    assert result.verified is True
    assert [click["label"] for click in channel.menu_clicks] == ["High"]
    assert channel.method_counts.get("fill", 0) == 0


def test_select_model_opens_family_submenu_then_radio_and_verifies_reflection() -> None:
    channel = MockChannel(
        MockScenario(
            name="model_family_submenu",
            turn_timeline=(TimedTurnSnapshot(0.0, _snapshot()),),
            menu_options={
                "model": (_option("GPT-5.5", "menuitem", checked=None),),
                "model>GPT-5.5": (_option("GPT-5.5", "menuitemradio"),),
            },
            menu_reflected_model_labels={"GPT-5.5": ("GPT-5.5",)},
        )
    )

    result = select_model(_tab(channel), SELECTORS, "GPT-5.5")

    assert result.verified is True
    assert result.reflected == "GPT-5.5"
    assert [(click["label"], click["action"]) for click in channel.menu_clicks] == [
        ("GPT-5.5", "open_submenu"),
        ("GPT-5.5", "select"),
    ]


def test_select_model_absent_label_fails_without_menu_selection_or_send() -> None:
    channel = MockChannel(
        MockScenario(
            name="model_absent",
            turn_timeline=(TimedTurnSnapshot(0.0, _snapshot()),),
            menu_options={"model": (_option("High"),)},
        )
    )

    with pytest.raises(ModelSelectionNotReflectedError):
        select_model(_tab(channel), SELECTORS, "Extra High")

    assert channel.menu_clicks == []
    assert channel.method_counts.get("fill", 0) == 0


def test_select_model_ambiguous_label_fails_without_menu_selection_or_send() -> None:
    channel = MockChannel(
        MockScenario(
            name="model_ambiguous",
            turn_timeline=(TimedTurnSnapshot(0.0, _snapshot()),),
            menu_options={"model": (_option("High"), _option("High"))},
        )
    )

    with pytest.raises(ModelSelectionNotReflectedError):
        select_model(_tab(channel), SELECTORS, "High")

    assert channel.menu_clicks == []
    assert channel.method_counts.get("fill", 0) == 0


def test_select_model_not_reflected_after_click_fails_closed() -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        MockScenario(
            name="model_not_reflected",
            turn_timeline=(TimedTurnSnapshot(0.0, _snapshot()),),
            menu_options={"model": (_option("High"),)},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with pytest.raises(ModelSelectionNotReflectedError):
        select_model(_tab(channel), SELECTORS, "High")

    assert [click["label"] for click in channel.menu_clicks] == ["High"]
    assert channel.method_counts.get("fill", 0) == 0


def test_select_model_sustained_tolerates_transient_model_label() -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        MockScenario(
            name="model_sustained_transient_then_reflected",
            model_label_sequence=(("Medium",), ("Extra High",), ("Extra High",), ("High",)),
            menu_options={"model": (_option("High"),)},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    result = select_model(_tab(channel), SELECTORS, "High")

    assert result.requested == "High"
    assert result.reflected == "High"
    assert result.verified is True
    assert [click["label"] for click in channel.menu_clicks] == ["High"]
    assert channel.method_counts["dom_polls"] >= 4


def test_select_model_sustained_absence_fails_closed_after_multiple_samples() -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        MockScenario(
            name="model_sustained_absence",
            model_label_sequence=(("Medium",), ("Extra High",), ("Extra High",), ("Extra High",), ("Extra High",), ("Extra High",), ("Extra High",)),
            menu_options={"model": (_option("High"),)},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with pytest.raises(ModelSelectionNotReflectedError):
        select_model(_tab(channel), SELECTORS, "High")

    assert [click["label"] for click in channel.menu_clicks] == ["High"]
    assert channel.method_counts["dom_polls"] >= 7
    assert channel.method_counts.get("fill", 0) == 0


def test_select_model_trigger_tolerates_transient_then_unambiguous_label() -> None:
    clock = ScriptedClock()
    channel = MockChannel(
        MockScenario(
            name="model_trigger_transient_then_unambiguous",
            model_label_sequence=((), ("Medium", "High"), ("Medium",), ("High",)),
            menu_options={"model": (_option("High"),)},
        ),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    result = select_model(_tab(channel), SELECTORS, "High")

    assert result.verified is True
    assert result.reflected == "High"
    assert [click["label"] for click in channel.menu_clicks] == ["High"]
    assert channel.method_counts["dom_polls"] >= 4


def test_forbidden_recent_files_and_projects_submenus_are_listed_but_never_opened() -> None:
    forbidden = {"Recent files", "Projects"}
    channel = MockChannel(
        MockScenario(
            name="forbidden_submenus_never_opened",
            turn_timeline=(TimedTurnSnapshot(0.0, _snapshot()),),
            menu_options={
                "model": (
                    _option("Recent files", "menuitem", checked=None),
                    _option("Projects", "menuitem", checked=None),
                    _option("High", "menuitemradio"),
                ),
                "tools": (
                    _option("Recent files", "menuitem", checked=None),
                    _option("Projects", "menuitem", checked=None),
                    _option("Web search", "menuitem", checked=False),
                ),
            },
            menu_reflected_model_labels={"High": ("High",)},
        )
    )
    tab = _tab(channel)

    assert select_model(tab, SELECTORS, "High").verified is True
    assert set_tools(tab, SELECTORS, ("Web search",))[0].verified is True
    open_radix_menu(tab, SELECTORS["model_picker_trigger_candidates"])
    labels = {option.label for option in enumerate_radix_options(tab)}

    assert forbidden <= labels
    assert all(click["label"] not in forbidden for click in channel.menu_clicks)
    assert not any(click["action"] == "open_submenu" and click["label"] in forbidden for click in channel.menu_clicks)


def test_set_tools_toggles_web_search_and_verifies_checked_state() -> None:
    channel = MockChannel(
        MockScenario(
            name="tool_toggle_happy",
            menu_options={"tools": (_option("Web search", "menuitem", checked=False),)},
        )
    )

    results = set_tools(_tab(channel), SELECTORS, ("Web search",))

    assert results == (results[0],)
    assert results[0].requested == "Web search"
    assert results[0].reflected == "Web search"
    assert results[0].verified is True
    assert [click["label"] for click in channel.menu_clicks] == ["Web search"]


def test_set_tools_reopens_tools_menu_after_select_when_menu_closes() -> None:
    channel = MockChannel(
        MockScenario(
            name="tool_menu_closes_on_select",
            menu_options={"tools": (_option("Web search", "menuitem", checked=False),)},
            menu_closes_on_select=True,
        )
    )

    results = set_tools(_tab(channel), SELECTORS, ("Web search",))

    # Falsifiability: reverting to the old immediate enumerate would see an empty portal after select and raise TOOL_SELECTION_NOT_REFLECTED instead of returning this result.
    assert results[0].requested == "Web search"
    assert results[0].reflected == "Web search"
    assert results[0].verified is True
    assert [click["label"] for click in channel.menu_clicks] == ["Web search"]
    assert sum(
        1
        for call in channel.calls
        if call.method == "evaluate" and call.details.get("js_key") == "ask_chatgpt_open_radix_trigger"
    ) == 2


def test_set_tools_clicked_tool_must_reflect_checked_state() -> None:
    channel = MockChannel(
        MockScenario(
            name="tool_clicked_but_not_checked",
            menu_options={"tools": (_option("Web search", "menuitem", checked=None),)},
        )
    )

    with pytest.raises(ToolSelectionNotReflectedError):
        set_tools(_tab(channel), SELECTORS, ("Web search",))

    assert [click["label"] for click in channel.menu_clicks] == ["Web search"]
    assert channel.method_counts.get("fill", 0) == 0


def test_set_tools_absent_tool_fails_without_menu_selection() -> None:
    channel = MockChannel(
        MockScenario(
            name="tool_absent",
            menu_options={"tools": (_option("Create image", "menuitem", checked=False),)},
        )
    )

    with pytest.raises(ToolSelectionNotReflectedError):
        set_tools(_tab(channel), SELECTORS, ("Web search",))

    assert channel.menu_clicks == []
