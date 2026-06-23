"""Verified prompt submission over the BrowserChannel seam."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ask_chatgpt.channels.base import TabLease, TurnDom, TurnDomSnapshot
from ask_chatgpt.errors import (
    AttachmentUploadError,
    PromptNotSubmittedError,
    SelectorNotFoundError,
)
from ask_chatgpt.models import AttachmentRef, AttachmentSpec, SelectorMap, SendTimeouts

_SEND_BUTTON_STATE_KEY = "ask_chatgpt_send_button_state"
_SEND_BUTTON_SETTLE_TIMEOUT_S = 2.0
_SEND_BUTTON_ATTACHMENT_SETTLE_TIMEOUT_S = 60.0
_SEND_BUTTON_POLL_INTERVAL_S = 0.25
_SEND_BUTTON_CLICK_RETRY_INTERVAL_S = 0.25
_ATTACHMENT_CHIP_TIMEOUT_S = 30.0
_ATTACHMENT_CHIP_POLL_INTERVAL_S = 0.25


@dataclass(frozen=True)
class TurnBaseline:
    latest_user_id: str | None
    user_count: int
    latest_assistant_id: str | None
    assistant_count: int


@dataclass(frozen=True)
class SubmittedTurn:
    baseline: TurnBaseline
    user_message_id: str
    user_count: int
    normalized_prompt: str


def normalize_prompt(prompt: str) -> str:
    """Return M4's public prompt-normalized form."""

    return prompt.replace("\r\n", "\n").replace("\r", "\n").strip()


def wait_for_idle_and_reload_if_needed(
    tab: TabLease, selectors: SelectorMap, *, timeout_s: float
) -> None:
    deadline = _monotonic(tab) + timeout_s
    observed_inflight_generation = False
    while True:
        snapshot = tab.channel.query_turns(tab, selectors)
        if not snapshot.stop_visible:
            if observed_inflight_generation:
                tab.channel.reload(tab)
                tab.channel.wait_for_load_state(tab, timeout_s=timeout_s)
            return
        observed_inflight_generation = True
        if _monotonic(tab) >= deadline:
            raise PromptNotSubmittedError(
                "existing generation did not become idle before send",
                details={"reason": "idle_timeout"},
            )
        _sleep_until(tab, min(deadline, _monotonic(tab) + 1.0))


def read_turn_baseline(tab: TabLease, selectors: SelectorMap) -> TurnBaseline:
    snapshot = tab.channel.query_turns(tab, selectors)
    latest_user = _latest(snapshot.users)
    latest_assistant = _latest(snapshot.assistants)
    return TurnBaseline(
        latest_user_id=latest_user.message_id if latest_user else None,
        user_count=len(snapshot.users),
        latest_assistant_id=latest_assistant.message_id if latest_assistant else None,
        assistant_count=len(snapshot.assistants),
    )


def wait_for_composer(tab: TabLease, selectors: SelectorMap, *, timeout_s: float) -> None:
    selector = selectors["composer"]
    deadline = _monotonic(tab) + timeout_s
    last_error: BaseException | None = None
    while True:
        try:
            tab.channel.wait_for_selector(tab, selector, state="visible", timeout_s=0.0)
            snapshot = tab.channel.query_turns(tab, selectors)
            if snapshot.composer_visible:
                return
        except SelectorNotFoundError as exc:
            last_error = exc
        if _monotonic(tab) >= deadline:
            raise SelectorNotFoundError(
                "composer did not become visible",
                details={"selector": selector},
            ) from last_error
        _sleep_until(tab, min(deadline, _monotonic(tab) + 0.5))


def upload_attachments(
    tab: TabLease, selectors: SelectorMap, files: Sequence[AttachmentSpec]
) -> tuple[AttachmentRef, ...]:
    refs: list[AttachmentRef] = []
    paths: list[Path] = []
    for index, spec in enumerate(files):
        path = Path(spec.path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        paths.append(path)
        refs.append(
            AttachmentRef(
                source_kind="user_upload",
                source_ref=None,
                raw_path=f"local_upload:{index}",
                filename=spec.display_name or path.name,
                mime=spec.mime,
                bytes=path.stat().st_size,
                sha256=None,
                local_path=None,
                download_state="pending",
                metadata={},
            )
        )
    if paths:
        tab.channel.upload_files(tab, selectors["file_input"], paths)
        _wait_for_attachment_chip(
            tab,
            selectors["attachment_chip"],
            file_count=len(paths),
        )
    return tuple(refs)


def _wait_for_attachment_chip(
    tab: TabLease,
    selector: str,
    *,
    file_count: int,
) -> None:
    deadline = _monotonic(tab) + _ATTACHMENT_CHIP_TIMEOUT_S
    last_error: BaseException | None = None
    while True:
        remaining_s = deadline - _monotonic(tab)
        if remaining_s <= 0:
            break
        try:
            tab.channel.wait_for_selector(
                tab,
                selector,
                state="visible",
                timeout_s=min(_ATTACHMENT_CHIP_POLL_INTERVAL_S, remaining_s),
            )
            return
        except Exception as exc:  # noqa: BLE001 - channel absence errors differ by backend.
            last_error = exc
        if _monotonic(tab) >= deadline:
            break
        _sleep_until(
            tab,
            min(deadline, _monotonic(tab) + _ATTACHMENT_CHIP_POLL_INTERVAL_S),
        )
    raise AttachmentUploadError(
        "attachment upload was not confirmed (no composer attachment chip appeared)",
        details={"file_count": file_count},
    ) from last_error


def fill_composer(tab: TabLease, selectors: SelectorMap, prompt: str) -> None:
    selector = selectors["composer"]
    normalized = normalize_prompt(prompt)
    tab.channel.fill(tab, selector, normalized)
    actual = _read_composer_text(tab, selector)
    if normalize_prompt(actual) != normalized:
        raise PromptNotSubmittedError(
            "composer did not retain the normalized prompt",
            details={"reason": "composer_text_mismatch"},
        )


def submit_composer(
    tab: TabLease,
    selectors: SelectorMap,
    *,
    settle_timeout_s: float = _SEND_BUTTON_SETTLE_TIMEOUT_S,
) -> None:
    selector = selectors["send_button_unverified_no_input"]
    _wait_for_enabled_send_button(
        tab,
        selector,
        timeout_s=settle_timeout_s,
        interval_s=_SEND_BUTTON_POLL_INTERVAL_S,
    )
    try:
        tab.channel.click(tab, selector)
        return
    except SelectorNotFoundError:
        _sleep_until(tab, _monotonic(tab) + _SEND_BUTTON_CLICK_RETRY_INTERVAL_S)
        _wait_for_enabled_send_button(
            tab,
            selector,
            timeout_s=_SEND_BUTTON_CLICK_RETRY_INTERVAL_S,
            interval_s=_SEND_BUTTON_POLL_INTERVAL_S,
        )
        try:
            tab.channel.click(tab, selector)
            return
        except SelectorNotFoundError as exc:
            raise SelectorNotFoundError(
                "send button did not remain visible and enabled",
                details={"selector": selector},
            ) from exc


def verify_prompt_submitted(
    tab: TabLease,
    selectors: SelectorMap,
    baseline: TurnBaseline,
    prompt: str,
    *,
    timeout_s: float,
    has_attachments: bool = False,
) -> SubmittedTurn:
    normalized = normalize_prompt(prompt)
    deadline = _monotonic(tab) + timeout_s
    last_seen_user_id = baseline.latest_user_id
    last_seen_count = baseline.user_count
    while True:
        snapshot = tab.channel.query_turns(tab, selectors)
        latest_user = _latest(snapshot.users)
        if latest_user is not None:
            last_seen_user_id = latest_user.message_id
            last_seen_count = len(snapshot.users)
            newer = (
                len(snapshot.users) > baseline.user_count
                or latest_user.message_id != baseline.latest_user_id
            )
            latest_text = normalize_prompt(latest_user.text)
            carries_prompt = (
                normalized in latest_text if has_attachments else latest_text == normalized
            )
            if newer and carries_prompt:
                return SubmittedTurn(
                    baseline=baseline,
                    user_message_id=latest_user.message_id,
                    user_count=len(snapshot.users),
                    normalized_prompt=normalized,
                )
        if _monotonic(tab) >= deadline:
            raise PromptNotSubmittedError(
                "submit did not produce a new user turn carrying the prompt",
                details={
                    "baseline_user_id": baseline.latest_user_id,
                    "last_seen_user_id": last_seen_user_id,
                    "baseline_user_count": baseline.user_count,
                    "last_seen_user_count": last_seen_count,
                },
            )
        _sleep_until(tab, min(deadline, _monotonic(tab) + 0.5))


def send_prompt(
    tab: TabLease,
    selectors: SelectorMap,
    prompt: str,
    *,
    model: str | None,
    tools: Sequence[str],
    attach: Sequence[AttachmentSpec],
    timeouts: SendTimeouts,
) -> SubmittedTurn:
    if model is not None:
        from ask_chatgpt.menus import assert_reflected_model

        assert_reflected_model(tab, selectors, model)
    if tools:
        from ask_chatgpt.menus import assert_reflected_tools

        assert_reflected_tools(tab, selectors, tools)
    wait_for_idle_and_reload_if_needed(tab, selectors, timeout_s=timeouts.idle_wait_s)
    baseline = read_turn_baseline(tab, selectors)
    wait_for_composer(tab, selectors, timeout_s=timeouts.composer_wait_s)
    upload_attachments(tab, selectors, attach)
    fill_composer(tab, selectors, prompt)
    submit_composer(
        tab,
        selectors,
        settle_timeout_s=(
            _SEND_BUTTON_ATTACHMENT_SETTLE_TIMEOUT_S
            if attach
            else _SEND_BUTTON_SETTLE_TIMEOUT_S
        ),
    )
    return verify_prompt_submitted(
        tab,
        selectors,
        baseline,
        prompt,
        timeout_s=timeouts.submit_verify_s,
        has_attachments=bool(attach),
    )


def _latest(turns: Sequence[TurnDom]) -> TurnDom | None:
    return turns[-1] if turns else None


def _read_composer_text(tab: TabLease, selector: str) -> str:
    value = tab.channel.evaluate(
        tab,
        "ask_chatgpt_send_read_composer_text",
        arg={"selector": selector},
        timeout_s=5.0,
    )
    return value if isinstance(value, str) else ""


def _wait_for_enabled_send_button(
    tab: TabLease,
    selector: str,
    *,
    timeout_s: float,
    interval_s: float,
) -> None:
    deadline = _monotonic(tab) + max(0.0, float(timeout_s))
    visible = False
    enabled = False
    while True:
        visible, enabled = _send_button_visible_enabled(tab, selector)
        if visible and enabled:
            return
        if _monotonic(tab) >= deadline:
            raise SelectorNotFoundError(
                "send button did not become visible and enabled",
                details={"selector": selector, "visible": visible, "enabled": enabled},
            )
        _sleep_until(tab, min(deadline, _monotonic(tab) + max(0.0, float(interval_s))))


def _send_button_visible_enabled(tab: TabLease, selector: str) -> tuple[bool, bool]:
    state = tab.channel.evaluate(
        tab,
        _SEND_BUTTON_STATE_KEY,
        arg={"selector": selector},
        timeout_s=0.0,
    )
    if not isinstance(state, Mapping):
        return False, False
    visible_enabled = state.get("visible_enabled") is True
    visible = state.get("visible") is True or visible_enabled
    enabled = state.get("enabled") is True or visible_enabled
    return visible, enabled


def _monotonic(tab: TabLease) -> float:
    monotonic = getattr(tab.channel, "monotonic", None)
    if callable(monotonic):
        return float(monotonic())
    return 0.0


def _sleep_until(tab: TabLease, target_s: float) -> None:
    delay = max(0.0, target_s - _monotonic(tab))
    sleeper = getattr(tab.channel, "sleep", None)
    if callable(sleeper):
        sleeper(delay)


__all__ = [
    "SubmittedTurn",
    "TurnBaseline",
    "fill_composer",
    "normalize_prompt",
    "read_turn_baseline",
    "send_prompt",
    "submit_composer",
    "upload_attachments",
    "verify_prompt_submitted",
    "wait_for_composer",
    "wait_for_idle_and_reload_if_needed",
]
