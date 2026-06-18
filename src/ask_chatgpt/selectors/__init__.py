"""Strict selector-map loading and validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from ask_chatgpt.errors import SelectorNotFoundError
from ask_chatgpt.models import SelectorMap

REQUIRED_SELECTOR_KEYS: tuple[str, ...] = (
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


def _load_json_from_name_or_path(name_or_path: str | Path) -> Any:
    if name_or_path == "real":
        try:
            text = resources.files(__package__).joinpath("real.json").read_text(
                encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover - packaged-resource failure
            raise SelectorNotFoundError(
                "selector map 'real' could not be read",
                details={"name": "real"},
            ) from exc
    else:
        path = Path(name_or_path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SelectorNotFoundError(
                f"selector map could not be read: {path}",
                details={"path": str(path)},
            ) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SelectorNotFoundError(
            "selector map is not valid JSON",
            details={"error": str(exc)},
        ) from exc


def _validate_selector_map(raw: Mapping[str, Any], *, strict: bool) -> SelectorMap:
    # M4 is fail-closed; strict=False is reserved for later compatibility but
    # still returns a complete SelectorMap rather than silently inventing keys.
    _ = strict
    for key in REQUIRED_SELECTOR_KEYS:
        if key not in raw:
            raise SelectorNotFoundError(
                f"selector map missing required key: {key}",
                details={"missing_key": key},
            )
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise SelectorNotFoundError(
                f"selector map key has invalid value: {key}",
                details={"key": key, "value_type": type(value).__name__},
            )
    return {key: str(raw[key]) for key in REQUIRED_SELECTOR_KEYS}  # type: ignore[return-value]


def load_selector_map(
    name_or_path: str | Path | Mapping[str, Any] = "real", *, strict: bool = True
) -> SelectorMap:
    """Load and strictly validate a selector map."""

    raw = (
        dict(name_or_path)
        if isinstance(name_or_path, Mapping)
        else _load_json_from_name_or_path(name_or_path)
    )
    if not isinstance(raw, Mapping):
        raise SelectorNotFoundError("selector map must be a JSON object")
    return _validate_selector_map(raw, strict=strict)


__all__ = ["REQUIRED_SELECTOR_KEYS", "load_selector_map"]
