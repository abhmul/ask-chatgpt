import pytest

import ask_chatgpt.driver as driver
from ask_chatgpt.errors import SelectorUnavailableError


def test_real_start_fails_closed_before_playwright_start_and_navigation(tmp_path, monkeypatch):
    navigations: list[str] = []
    playwright_starts: list[bool] = []

    class FakePage:
        def goto(self, url, **kwargs):
            navigations.append(url)
            return None

        def close(self):
            pass

    class FakeContext:
        def __init__(self):
            self.pages = [FakePage()]

        def new_page(self):
            page = FakePage()
            self.pages.append(page)
            return page

        def close(self):
            pass

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            return FakeContext()

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()

        def stop(self):
            pass

    class FakePlaywrightStarter:
        def start(self):
            playwright_starts.append(True)
            return FakePlaywright()

    def fake_sync_playwright():
        return FakePlaywrightStarter()

    monkeypatch.setattr(driver, "sync_playwright", fake_sync_playwright)

    session = driver.BrowserSession(channel="real", profile_path=tmp_path / "profile")
    try:
        with pytest.raises(SelectorUnavailableError):
            session.start()
        assert navigations == []
        assert playwright_starts == []
    finally:
        session.close()
