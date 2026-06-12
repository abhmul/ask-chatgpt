import socket

import pytest
from playwright.sync_api import Error as PlaywrightError

from ask_chatgpt.driver import BrowserSession


def test_autouse_socket_guard_blocks_deliberate_non_loopback_connect(socket_guard_active):
    assert socket_guard_active
    with pytest.raises(RuntimeError, match="NETWORK BLOCKED"):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_mock_browser_context_route_blocks_non_loopback_navigation(mock_chatgpt):
    mock_chatgpt.reset()
    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        assert session.page is not None
        assert session.page.url.startswith(mock_chatgpt.base_url)
        with pytest.raises(PlaywrightError):
            session.page.goto("http://93.184.216.34/", wait_until="load", timeout=2000)
        assert not session.page.url.startswith("http://93.184.216.34")
