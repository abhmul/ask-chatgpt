from __future__ import annotations

import json
from pathlib import Path

import pytest

from ask_chatgpt.errors import SelectorNotFoundError
from ask_chatgpt.selectors import load_selector_map


REQUIRED_KEYS = (
    "composer",
    "tools_button",
    "message_turn",
    "user_turn",
    "assistant_turn",
    "copy_button",
    "stop_button",
    "send_button_unverified_no_input",
    "radix_portal",
    "model_picker_trigger_candidates",
)


def valid_map() -> dict[str, str]:
    return {key: f"[data-test='{key}']" for key in REQUIRED_KEYS}


def write_map(tmp_path: Path, mapping: dict[str, object]) -> Path:
    path = tmp_path / "selectors.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return path


def test_packaged_real_selector_map_loads_with_exact_required_keys() -> None:
    selector_map = load_selector_map()

    assert tuple(selector_map.keys()) == REQUIRED_KEYS
    assert selector_map["composer"] == "#prompt-textarea"
    assert selector_map["send_button_unverified_no_input"] == (
        'button[data-testid="send-button"], #composer-submit-button, button[aria-label="Send prompt"]'
    )
    assert selector_map["radix_portal"] == "[data-radix-popper-content-wrapper]"
    assert selector_map["model_picker_trigger_candidates"] == (
        'form button[aria-haspopup="menu"]:not([data-testid])'
    )
    assert "model_picker_trigger" not in selector_map


def test_real_model_picker_selector_uses_live_form_pill_not_legacy_composer_footer() -> None:
    # Falsifiability: reverting real.json to the old composer-footer selector makes this fail.
    selector_map = load_selector_map("real")

    assert selector_map["model_picker_trigger_candidates"] == 'form button[aria-haspopup="menu"]:not([data-testid])'
    assert selector_map["model_picker_trigger_candidates"] != 'composer-footer button[aria-haspopup="menu"]'


@pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
def test_missing_any_required_key_raises_selector_not_found(tmp_path: Path, missing_key: str) -> None:
    mapping = valid_map()
    del mapping[missing_key]

    with pytest.raises(SelectorNotFoundError) as excinfo:
        load_selector_map(write_map(tmp_path, mapping))

    assert excinfo.value.code == "SELECTOR_NOT_FOUND"
    assert missing_key in str(excinfo.value)


@pytest.mark.parametrize("bad_value", [None, [], ["#x"], True, "", "   \t\n"])
def test_null_array_boolean_and_whitespace_values_are_rejected(tmp_path: Path, bad_value: object) -> None:
    mapping: dict[str, object] = valid_map()
    mapping["copy_button"] = bad_value

    with pytest.raises(SelectorNotFoundError):
        load_selector_map(write_map(tmp_path, mapping))


def test_model_picker_candidates_key_cannot_be_replaced_by_typo_or_single_selector(tmp_path: Path) -> None:
    mapping: dict[str, object] = valid_map()
    del mapping["model_picker_trigger_candidates"]
    mapping["model_picker_trigger_candidate"] = "button"
    mapping["model_picker_trigger"] = "button[data-testid='model-picker']"

    with pytest.raises(SelectorNotFoundError):
        load_selector_map(write_map(tmp_path, mapping))
