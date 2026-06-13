import json
from pathlib import Path

import pytest

import ask_chatgpt.driver as driver
from ask_chatgpt.errors import SelectorUnavailableError


REAL_SELECTOR_MAP = Path(__file__).resolve().parents[1] / "src" / "ask_chatgpt" / "selector_maps" / "real.json"
EMPTY_REAL_SELECTOR_MAPS_DIR = Path(__file__).parent / "fixtures" / "selector_maps" / "empty"


def test_real_download_artifact_selector_is_fail_closed_to_force_fenced_fallback():
    payload = json.loads(REAL_SELECTOR_MAP.read_text(encoding="utf-8"))

    assert payload["selectors"]["download_artifact"] == ""
    assert len(payload["selectors"]) == 20
    assert len(payload["attributes"]) == 2


def test_real_start_fails_closed_on_missing_required_selector_before_playwright_start_and_navigation(tmp_path, monkeypatch):
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

    session = driver.BrowserSession(
        channel="real",
        profile_path=tmp_path / "profile",
        maps_dir=EMPTY_REAL_SELECTOR_MAPS_DIR,
    )
    try:
        with pytest.raises(SelectorUnavailableError):
            session.start()
        assert navigations == []
        assert playwright_starts == []
    finally:
        session.close()
