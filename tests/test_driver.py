import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from ask_chatgpt.driver import BrowserSession, REAL_BASE_URL
from ask_chatgpt.errors import (
    LoginRequiredError,
    ModelUnavailableError,
    RateLimitedError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
)
from ask_chatgpt.selector_map import load_selector_map


EMPTY_REAL_SELECTOR_MAPS_DIR = Path(__file__).parent / "fixtures" / "selector_maps" / "empty"


def test_driver_happy_path_returns_latest_completed_turn(mock_chatgpt):
    answer = "Driver happy path answer 8b85df"
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(answer)

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        conversation_ref = session.open_or_create_conversation(None)
        assert conversation_ref.startswith("conv-")

        session.select_model({"model": "mock-default"})
        session.send_prompt("hello driver")
        latest = session.wait_for_completion(timeout_s=3)

        expect(latest.locator(session.selectors.selector("message_body"))).to_have_text(answer, timeout=1000)
        assert mock_chatgpt.inspect()["last_prompt"] == "hello driver"
        assert session.page.url.startswith(mock_chatgpt.base_url + "/c/")


def test_driver_streaming_completion_reload_polls_until_complete(mock_chatgpt):
    answer = "Driver streamed answer 42c80b"
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(answer, streaming=True, stream_reads=2)

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        session.send_prompt("stream this")
        latest = session.wait_for_completion(timeout_s=5)

        expect(latest.locator(session.selectors.selector("message_body"))).to_have_text(answer, timeout=1000)
        assert mock_chatgpt.inspect()["conversations"][session.active_conversation_ref]["turns"][-1]["complete"] is True


def test_selector_map_missing_and_empty_keys_fail_closed(tmp_path):
    maps_dir = tmp_path
    (maps_dir / "bad.json").write_text(
        json.dumps(
            {
                "channel": "bad",
                "version": 1,
                "selectors": {"composer": ""},
                "attributes": {"conversation_ref": ""},
            }
        ),
        encoding="utf-8",
    )

    selector_map = load_selector_map("bad", maps_dir=maps_dir)

    with pytest.raises(SelectorUnavailableError, match="selector 'composer' unavailable for channel 'bad'"):
        selector_map.selector("composer")
    with pytest.raises(SelectorUnavailableError, match="selector 'missing' unavailable for channel 'bad'"):
        selector_map.selector("missing")
    with pytest.raises(SelectorUnavailableError, match="attribute 'conversation_ref' unavailable for channel 'bad'"):
        selector_map.attribute("conversation_ref")
    with pytest.raises(SelectorUnavailableError, match="attribute 'missing' unavailable for channel 'bad'"):
        selector_map.attribute("missing")


def test_selector_unavailable_fixture_mode_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="selector_unavailable")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(SelectorUnavailableError):
            session.open_or_create_conversation(None)


def test_login_required_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="login_required")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(LoginRequiredError):
            session.open_or_create_conversation(None)


def test_session_not_found_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="session_not_found")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        with pytest.raises(SessionNotFoundError):
            session.open_or_create_conversation("missing-driver-session")


def test_model_unavailable_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(
        "unused", failure_mode="model_unavailable", unavailable_model="mock-reasoning"
    )

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        with pytest.raises(ModelUnavailableError):
            session.select_model({"model": "mock-reasoning"})


def test_response_truncated_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("partial truncated answer", failure_mode="response_truncated")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        session.send_prompt("truncate this")
        with pytest.raises(ResponseTruncatedError):
            session.wait_for_completion(timeout_s=1)


def test_rate_limited_maps_to_named_error(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("unused", failure_mode="rate_limited")

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        with pytest.raises(RateLimitedError):
            session.send_prompt("rate limit this")


def test_tests_use_loopback_only_while_real_constant_exists(mock_chatgpt):
    assert REAL_BASE_URL == "https://chatgpt.com"

    mock_chatgpt.reset()
    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        assert session.page.url.startswith(mock_chatgpt.base_url)
        assert "chatgpt.com" not in session.page.url


def test_empty_real_selector_map_fixture_fails_closed():
    fixture_path = EMPTY_REAL_SELECTOR_MAPS_DIR / "real.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert payload["channel"] == "real"
    assert payload["selectors"]
    assert payload["attributes"]
    assert all(value == "" for value in payload["selectors"].values())
    assert all(value == "" for value in payload["attributes"].values())

    selector_map = load_selector_map("real", maps_dir=EMPTY_REAL_SELECTOR_MAPS_DIR)
    first_selector_key = next(iter(payload["selectors"]))
    with pytest.raises(SelectorUnavailableError):
        selector_map.selector(first_selector_key)
    with pytest.raises(SelectorUnavailableError):
        selector_map.attribute("conversation_ref")
