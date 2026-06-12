"""Fail-closed selector-map loading for supported ChatGPT channels."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from ask_chatgpt.errors import SelectorUnavailableError


_DEFAULT_MAPS_DIR = Path(__file__).with_name("selector_maps")


@dataclass(frozen=True)
class SelectorMap:
    """Channel-scoped selectors and DOM attributes.

    Access is intentionally fail-closed: absent, non-string, empty, or whitespace-only values are treated as unavailable so callers stop instead of guessing or broadening selectors.
    """

    channel: str
    selectors: Mapping[str, Any]
    attributes: Mapping[str, Any]
    version: int | None = None
    path: Path | None = None

    def selector(self, key: str) -> str:
        value = self.selectors.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SelectorUnavailableError(f"selector '{key}' unavailable for channel '{self.channel}'")
        return value

    def attribute(self, key: str) -> str:
        value = self.attributes.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SelectorUnavailableError(f"attribute '{key}' unavailable for channel '{self.channel}'")
        return value


def load_selector_map(channel: str, *, maps_dir: Path | None = None) -> SelectorMap:
    """Load ``selector_maps/<channel>.json`` without fallback selectors.

    Missing files, malformed JSON, unsupported shapes, and unavailable keys all raise ``SelectorUnavailableError``. The loader never falls back to another channel map.
    """

    if not isinstance(channel, str) or not channel.strip() or any(part in channel for part in ("/", "\\")):
        raise SelectorUnavailableError("selector map channel is unavailable; operator action: pass a simple channel name")

    root = _DEFAULT_MAPS_DIR if maps_dir is None else Path(maps_dir)
    path = root / f"{channel}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SelectorUnavailableError(f"selector map unavailable for channel '{channel}'") from None
    except json.JSONDecodeError as exc:
        raise SelectorUnavailableError(f"selector map JSON invalid for channel '{channel}': {exc.msg}") from None
    except OSError as exc:
        raise SelectorUnavailableError(f"selector map could not be read for channel '{channel}': {exc.strerror}") from None

    if not isinstance(payload, dict):
        raise SelectorUnavailableError(f"selector map has unsupported shape for channel '{channel}'")
    selectors = payload.get("selectors")
    attributes = payload.get("attributes")
    if not isinstance(selectors, dict) or not isinstance(attributes, dict):
        raise SelectorUnavailableError(f"selector map has unsupported shape for channel '{channel}'")
    version = payload.get("version")
    return SelectorMap(channel=channel, selectors=selectors, attributes=attributes, version=version, path=path)


__all__ = ["SelectorMap", "load_selector_map"]
