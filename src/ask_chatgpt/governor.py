"""Cross-process request rate governor for account-shared traffic."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ask_chatgpt.errors import RateLimitedError
from ask_chatgpt.store import Store

try:  # pragma: no cover - Linux in CI; fallback is for portability only.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

DEFAULT_BACKOFF_S = 1800.0
_MIN_REFILL_RATE_TOKENS_PER_S = 1e-6
_STATE_FILENAME = "bucket.json"
_SAFE_LABEL_RE = re.compile(r"[^a-z0-9_.-]+")

# THE REAL ACCOUNT RATE CEILING IS OPERATOR-OWNED — these defaults are conservative placeholders to be confirmed/measured with the operator, NEVER assumed as fact (see M16 §6, memory verify-inherited-resource-claims).
DEFAULT_TOKEN_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "page_load": 3.0,
        "reload": 3.0,
        "send": 5.0,
        "backend_fetch": 1.0,
        "upload": 3.0,
    }
)


@dataclass(frozen=True)
class GovernorConfig:
    """Configurable, operator-owned token-bucket allocation."""

    account_capacity_tokens: float = 120.0
    account_refill_tokens_per_min: float = 30.0
    operator_reserve_tokens_per_min: float = 15.0
    safety_margin: float = 0.50
    token_weights: Mapping[str, float] = field(default_factory=lambda: DEFAULT_TOKEN_WEIGHTS)

    @property
    def capacity_tokens(self) -> float:
        return max(1.0, _finite_float(self.account_capacity_tokens, 120.0))

    @property
    def refill_rate_tokens_per_s(self) -> float:
        account = max(0.0, _finite_float(self.account_refill_tokens_per_min, 30.0))
        reserve = max(0.0, _finite_float(self.operator_reserve_tokens_per_min, 15.0))
        margin = min(0.99, max(0.0, _finite_float(self.safety_margin, 0.50)))
        usable_per_min = max(0.0, account - reserve) * (1.0 - margin)
        return max(_MIN_REFILL_RATE_TOKENS_PER_S, usable_per_min / 60.0)

    def cost(self, action: str, default: float = 1.0) -> float:
        value = self.token_weights.get(action, default)
        return max(0.0, _finite_float(value, default))


class Governor:
    """File-lock token bucket shared by all tool processes.

    ``acquire`` uses wait-not-fail semantics: if a prior 429 set
    ``blocked_until`` or the bucket is empty, this process sleeps with the file
    lock held, then persists the debited state. Holding the lock intentionally
    serializes concurrent consumers against the shared account budget.
    """

    def __init__(
        self,
        *,
        dir: str | Path | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        config: GovernorConfig | None = None,
    ) -> None:
        self.dir = Path(dir) if dir is not None else Store().resolve_data_dir() / "governor"
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.config = config or GovernorConfig()
        self._state_path = self.dir / _STATE_FILENAME

    def cost(self, action: str, default: float = 1.0) -> float:
        return self.config.cost(action, default)

    def acquire(self, cost: float, *, action: str, path_kind: str) -> None:
        cost = max(0.0, _finite_float(cost, 0.0))
        if cost > self.config.capacity_tokens:
            raise ValueError("governor acquire cost exceeds bucket capacity")
        safe_action = _safe_label(action)
        safe_path_kind = _safe_label(path_kind)
        with self._locked_state_file() as handle:
            now = float(self.clock())
            state = self._load_state(handle, now)
            state = self._refill(state, now)
            blocked_until = _optional_float(state.get("blocked_until"))
            if blocked_until is not None and now < blocked_until:
                self.sleeper(blocked_until - now)
                now = float(self.clock())
                state = self._refill(state, now)
            tokens = _finite_float(state.get("tokens"), self.config.capacity_tokens)
            while tokens + 1e-9 < cost:
                delay = (cost - tokens) / self.config.refill_rate_tokens_per_s
                self.sleeper(delay)
                now = float(self.clock())
                state = self._refill(state, now)
                tokens = _finite_float(state.get("tokens"), 0.0)
            state["tokens"] = max(0.0, tokens - cost)
            state["last_action"] = safe_action
            state["last_path_kind"] = safe_path_kind
            self._write_state(handle, state)

    def note_rate_limited(self, retry_after_s: float | None) -> None:
        delay = _rate_limit_delay_s(retry_after_s)
        with self._locked_state_file() as handle:
            now = float(self.clock())
            state = self._refill(self._load_state(handle, now), now)
            blocked_until = now + delay
            existing = _optional_float(state.get("blocked_until"))
            state["blocked_until"] = max(existing or 0.0, blocked_until)
            state["last_rate_limited_epoch"] = now
            state["last_action"] = "rate_limited"
            state["last_path_kind"] = "shared_backoff"
            self._write_state(handle, state)

    def snapshot(self) -> Mapping[str, Any]:
        with self._locked_state_file() as handle:
            now = float(self.clock())
            state = self._refill(self._load_state(handle, now), now)
            self._write_state(handle, state)
            return MappingProxyType(dict(state))

    def _locked_state_file(self):  # noqa: ANN202 - contextmanager protocol is enough here.
        return _LockedStateFile(self._state_path)

    def _initial_state(self, now: float) -> dict[str, Any]:
        return {
            "tokens": self.config.capacity_tokens,
            "refill_epoch": now,
            "blocked_until": None,
            "last_rate_limited_epoch": None,
            "last_action": None,
            "last_path_kind": None,
        }

    def _load_state(self, handle: Any, now: float) -> dict[str, Any]:
        handle.seek(0)
        raw = handle.read()
        if not raw:
            return self._initial_state(now)
        try:
            loaded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._initial_state(now)
        if not isinstance(loaded, Mapping):
            return self._initial_state(now)
        state = self._initial_state(now)
        state["tokens"] = min(
            self.config.capacity_tokens,
            max(0.0, _finite_float(loaded.get("tokens"), self.config.capacity_tokens)),
        )
        state["refill_epoch"] = _finite_float(loaded.get("refill_epoch"), now)
        state["blocked_until"] = _optional_float(loaded.get("blocked_until"))
        state["last_rate_limited_epoch"] = _optional_float(loaded.get("last_rate_limited_epoch"))
        state["last_action"] = _safe_optional_label(loaded.get("last_action"))
        state["last_path_kind"] = _safe_optional_label(loaded.get("last_path_kind"))
        return state

    def _refill(self, state: dict[str, Any], now: float) -> dict[str, Any]:
        refill_epoch = _finite_float(state.get("refill_epoch"), now)
        tokens = _finite_float(state.get("tokens"), self.config.capacity_tokens)
        elapsed = max(0.0, now - refill_epoch)
        state["tokens"] = min(
            self.config.capacity_tokens,
            max(0.0, tokens) + elapsed * self.config.refill_rate_tokens_per_s,
        )
        state["refill_epoch"] = now
        blocked_until = _optional_float(state.get("blocked_until"))
        if blocked_until is not None and now >= blocked_until:
            state["blocked_until"] = None
        return state

    def _write_state(self, handle: Any, state: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(state), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        handle.seek(0)
        handle.truncate()
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


class _LockedStateFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any | None = None

    def __enter__(self) -> Any:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.handle = self.path.open("a+b")
        if fcntl is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self.handle

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        if self.handle is None:
            return
        try:
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def raise_for_rate_limit(result: object) -> None:
    if int(getattr(result, "status", 0)) != 429:
        return
    retry_after_s = _parse_retry_after_seconds(getattr(result, "headers", {}))
    raise RateLimitedError("rate limited", details={"retry_after_s": retry_after_s})


def _parse_retry_after_seconds(headers: object) -> int | None:
    if not isinstance(headers, Mapping):
        return None
    value: object | None = None
    for key, candidate in headers.items():
        if str(key).lower() == "retry-after":
            value = candidate
            break
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]+", text):
        return None
    return int(text)


def _rate_limit_delay_s(retry_after_s: float | None) -> float:
    if retry_after_s is None:
        return DEFAULT_BACKOFF_S
    value = _finite_float(retry_after_s, DEFAULT_BACKOFF_S)
    return value if value > 0 else DEFAULT_BACKOFF_S


def _safe_label(value: object) -> str:
    text = _SAFE_LABEL_RE.sub("_", str(value).lower()).strip("_")
    while "__" in text:
        text = text.replace("__", "_")
    return (text or "unspecified")[:80]


def _safe_optional_label(value: object) -> str | None:
    if value is None:
        return None
    return _safe_label(value)


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    result = _finite_float(value, math.nan)
    return result if math.isfinite(result) else None


__all__ = [
    "DEFAULT_BACKOFF_S",
    "DEFAULT_TOKEN_WEIGHTS",
    "Governor",
    "GovernorConfig",
    "raise_for_rate_limit",
]
