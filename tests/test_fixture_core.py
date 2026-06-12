import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


SELECTOR_MAP_PATH = Path("src/ask_chatgpt/selector_maps/mock.json")


def _mock_selector_map():
    return json.loads(SELECTOR_MAP_PATH.read_text(encoding="utf-8"))


def test_mock_chatgpt_control_plane(mock_chatgpt):
    mock_chatgpt.reset()

    empty = mock_chatgpt.inspect()
    assert empty["conversations"] == {}
    assert empty["last_prompt"] is None
    assert empty["next_script"] is None

    mock_chatgpt.script_next_response("hello-123")

    scripted = mock_chatgpt.inspect()
    assert scripted["conversations"] == {}
    assert scripted["next_script"]["text"] == "hello-123"
    assert scripted["next_script"]["conversation_ref"] is None
    assert scripted["next_script"]["streaming"] is False
    assert scripted["next_script"]["complete"] is True


def test_mock_chatgpt_browser_happy_path_uses_selector_map(mock_chatgpt):
    selector_map = _mock_selector_map()
    selectors = selector_map["selectors"]
    attrs = selector_map["attributes"]
    scripted_text = "scripted assistant says hello-123"
    prompt = "fixture core prompt 123"

    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(scripted_text)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(mock_chatgpt.base_url, wait_until="load")

            expect(page.locator(selectors["ready_root"])).to_be_visible(timeout=5000)
            expect(page.locator(selectors["chat_list"])).to_be_visible()
            expect(page.locator(selectors["model_menu"])).to_be_visible()
            expect(page.locator(selectors["model_option"]).first).to_be_attached()

            page.locator(selectors["new_chat_button"]).click()
            expect(page.locator(selectors["ready_root"])).to_be_visible(timeout=5000)
            expect(page.locator(selectors["chat_item"])).to_have_count(1)

            page.locator(selectors["composer"]).fill(prompt)
            page.locator(selectors["send_button"]).click()

            completed_assistant_turns = page.locator(selectors["assistant_message"]).filter(
                has=page.locator(selectors["completion_marker"])
            )
            expect(completed_assistant_turns).to_have_count(1, timeout=5000)
            latest = completed_assistant_turns.last
            expect(latest.locator(selectors["completion_marker"])).to_have_count(1)
            expect(latest.locator(selectors["streaming_marker"])).to_have_count(0)
            expect(latest.locator(selectors["message_body"])).to_have_text(scripted_text)

            assert latest.get_attribute(attrs["conversation_ref"]).startswith("conv-")
            assert latest.get_attribute(attrs["turn_id"]).startswith("turn-")
        finally:
            browser.close()

    inspected = mock_chatgpt.inspect()
    assert inspected["last_prompt"] == prompt
    conversation = next(iter(inspected["conversations"].values()))
    assert [turn["role"] for turn in conversation["turns"]] == ["user", "assistant"]
    assert conversation["turns"][1]["text"] == scripted_text


def test_mock_chatgpt_binds_loopback_ephemeral_nonfixed_port(mock_chatgpt):
    parsed = urlparse(mock_chatgpt.base_url)
    assert parsed.scheme == "http"
    assert parsed.hostname == "127.0.0.1"
    assert parsed.port == mock_chatgpt.port
    assert mock_chatgpt.host == "127.0.0.1"
    assert mock_chatgpt.requested_port == 0
    assert parsed.port not in {80, 443, 3000, 5000, 8000, 8080}
