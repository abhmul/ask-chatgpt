from __future__ import annotations

import pytest

from ask_chatgpt.governor import Governor, GovernorConfig


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = float(start)
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(float(seconds))
        self.now += float(seconds)


def test_governor_token_bucket_sleeps_until_refill_when_exhausted(tmp_path) -> None:
    clock = FakeClock()
    governor = Governor(
        dir=tmp_path,
        clock=clock.time,
        sleeper=clock.sleep,
        config=GovernorConfig(
            account_capacity_tokens=2.0,
            account_refill_tokens_per_min=60.0,
            operator_reserve_tokens_per_min=0.0,
            safety_margin=0.0,
        ),
    )

    governor.acquire(2.0, action="send", path_kind="composer_submit")
    governor.acquire(1.0, action="backend_fetch", path_kind="completion")

    assert clock.sleeps == [pytest.approx(1.0)]
    assert governor.snapshot()["tokens"] == pytest.approx(0.0)


def test_governor_retry_after_blocks_next_acquire_for_shared_backoff(tmp_path) -> None:
    clock = FakeClock()
    governor = Governor(
        dir=tmp_path,
        clock=clock.time,
        sleeper=clock.sleep,
        config=GovernorConfig(
            account_capacity_tokens=5.0,
            account_refill_tokens_per_min=60.0,
            operator_reserve_tokens_per_min=0.0,
            safety_margin=0.0,
        ),
    )

    governor.note_rate_limited(retry_after_s=17.0)
    governor.acquire(1.0, action="page_load", path_kind="open_tab")

    assert clock.sleeps == [pytest.approx(17.0)]
    assert clock.time() == pytest.approx(17.0)
    assert governor.snapshot()["last_rate_limited_epoch"] == pytest.approx(0.0)
