from __future__ import annotations

import pytest

from ask_chatgpt.channels.mock import MockChannel, ScriptedClock
from ask_chatgpt.errors import HumanActionNeededError
from ask_chatgpt.session import AdaptiveSendBudget, PromptBudgetBusyError, Session


def test_send_budget_spaces_successive_submissions_with_fake_sleep() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(monotonic=clock.monotonic, sleeper=clock.sleep)

    with budget.submission():
        pass
    required_spacing = max(budget.politeness_floor_s, 60.0 / budget.current_rate_per_min)
    with budget.submission():
        pass

    assert clock.sleeps
    assert clock.sleeps[-1] >= required_spacing
    assert budget.successful_submissions == 2


def test_send_budget_politeness_floor_remains_hard_at_high_rate() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(
        politeness_floor_s=5.0,
        initial_rate_per_min=60.0,
        max_rate_per_min=120.0,
        additive_increase_per_min=20.0,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    for _ in range(5):
        with budget.submission():
            pass

    assert clock.sleeps
    assert all(delay >= 5.0 for delay in clock.sleeps)


def test_send_budget_aimd_increases_to_configured_cap() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(
        initial_rate_per_min=3.0,
        max_rate_per_min=6.0,
        additive_increase_per_min=2.0,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    with budget.submission():
        pass
    assert budget.current_rate_per_min == 5.0
    with budget.submission():
        pass
    assert budget.current_rate_per_min == 6.0
    with budget.submission():
        pass
    assert budget.current_rate_per_min == 6.0


def test_send_budget_soft_signal_backs_off_rate_and_grows_spacing() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(
        politeness_floor_s=0.0,
        initial_rate_per_min=12.0,
        max_rate_per_min=12.0,
        backoff_factor=0.5,
        min_rate_per_min=3.0,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )
    with budget.submission():
        pass
    clock.sleeps.clear()

    budget.record_soft_signal("HTTP 429")
    assert budget.current_rate_per_min == 6.0
    budget.record_soft_signal("rate limit toast")
    assert budget.current_rate_per_min == 3.0
    budget.record_soft_signal("more backoff")
    assert budget.current_rate_per_min == 3.0
    with budget.submission():
        pass

    assert budget.snapshot()["last_signal"] == "more_backoff"
    assert clock.sleeps[-1] >= 20.0


def test_send_budget_hard_pause_blocks_without_yielding_until_resume() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(monotonic=clock.monotonic, sleeper=clock.sleep)
    entered = False

    budget.hard_pause("Login / Cloudflare wall")
    with pytest.raises(HumanActionNeededError) as exc_info:
        with budget.submission():
            entered = True
    assert entered is False
    assert exc_info.value.details["reason"] == "login_cloudflare_wall"

    budget.resume()
    with budget.submission():
        entered = True
    assert entered is True
    assert budget.successful_submissions == 1


def test_send_budget_has_no_hard_message_cap() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(
        politeness_floor_s=0.0,
        initial_rate_per_min=60.0,
        max_rate_per_min=60.0,
        additive_increase_per_min=0.0,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    for _ in range(50):
        with budget.submission():
            pass

    assert budget.successful_submissions == 50
    assert budget.snapshot()["hard_message_cap"] is None


def test_send_budget_nested_submission_raises_busy() -> None:
    clock = ScriptedClock()
    budget = AdaptiveSendBudget(monotonic=clock.monotonic, sleeper=clock.sleep)

    with budget.submission():
        with pytest.raises(PromptBudgetBusyError):
            with budget.submission():
                pass


def test_session_wires_concrete_channel_clock_into_send_budget(tmp_path, monkeypatch) -> None:
    import ask_chatgpt.session as session_module

    clock = ScriptedClock()
    channel = MockChannel(monotonic=clock.monotonic, sleeper=clock.sleep)

    def real_sleep_forbidden(_seconds: float) -> None:
        raise AssertionError("session send budget must use channel sleeper")

    monkeypatch.setattr(session_module.time, "sleep", real_sleep_forbidden)
    session = Session(data_dir=tmp_path, channel=channel)

    with session.send_budget.submission():
        pass
    with session.send_budget.submission():
        pass

    assert clock.sleeps
