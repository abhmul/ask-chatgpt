import json
from pathlib import Path

import pytest

import ask_chatgpt.driver as driver
from ask_chatgpt.errors import SelectorUnavailableError


REAL_SELECTOR_MAP = Path(__file__).resolve().parents[1] / "src" / "ask_chatgpt" / "selector_maps" / "real.json"
EMPTY_REAL_SELECTOR_MAPS_DIR = Path(__file__).parent / "fixtures" / "selector_maps" / "empty"


def test_real_selector_map_pins_verified_opaque_download_and_model_picker_selectors():
    payload = json.loads(REAL_SELECTOR_MAP.read_text(encoding="utf-8"))

    # M-009: the real download affordance is a bare <button>Download the patch bundle</button> carrying
    # no integrity metadata; retrieve_patch_bundle now captures and structurally validates it via the
    # opaque-real download path. This selector was verified against the real site (M-008b T4 capture +
    # M-009 CDP probe). It is text-dependent and fails closed if ChatGPT's button text drifts.
    assert payload["selectors"]["download_artifact"] == 'button:has-text("Download the patch bundle")'
    # M-010: the real model picker is a composer-toolbar Radix dropdown whose options render in a
    # portal only after opening the trigger. These selectors are intentionally narrow and fail closed
    # if the picker moves or changes semantics.
    assert payload["selectors"]["model_menu"] == (
        'form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])'
    )
    assert payload["selectors"]["model_option"] == '[data-radix-popper-content-wrapper] [role="menuitemradio"]'
    assert payload["selectors"]["model_option_disabled"] == (
        '[data-radix-popper-content-wrapper] [role="menuitemradio"][aria-disabled="true"], '
        '[data-radix-popper-content-wrapper] [role="menuitemradio"][data-disabled="true"], '
        '[data-radix-popper-content-wrapper] [role="menuitemradio"][disabled]'
    )
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
