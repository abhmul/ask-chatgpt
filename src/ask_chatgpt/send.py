"""Verified prompt submission over the BrowserChannel seam."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ask_chatgpt.channels.base import TabLease, TurnDom, TurnDomSnapshot
from ask_chatgpt.errors import PromptNotSubmittedError, SelectorNotFoundError
from ask_chatgpt.models import AttachmentRef, AttachmentSpec, SelectorMap, SendTimeouts


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
    while True:
        snapshot = tab.channel.query_turns(tab, selectors)
        if not snapshot.stop_visible:
            tab.channel.reload(tab)
            tab.channel.wait_for_load_state(tab, timeout_s=timeout_s)
            return
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
    del tab, selectors
    refs: list[AttachmentRef] = []
    for index, spec in enumerate(files):
        path = Path(spec.path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(str(path))
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
    return tuple(refs)


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


def submit_composer(tab: TabLease, selectors: SelectorMap) -> None:
    tab.channel.click(tab, selectors["send_button_unverified_no_input"])


def verify_prompt_submitted(
    tab: TabLease,
    selectors: SelectorMap,
    baseline: TurnBaseline,
    prompt: str,
    *,
    timeout_s: float,
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
            if newer and normalize_prompt(latest_user.text) == normalized:
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
    submit_composer(tab, selectors)
    return verify_prompt_submitted(
        tab,
        selectors,
        baseline,
        prompt,
        timeout_s=timeouts.submit_verify_s,
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
