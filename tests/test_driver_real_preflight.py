import json

import pytest

import ask_chatgpt.driver as driver
from ask_chatgpt.errors import LoginRequiredError, ProfileLockedError, SelectorUnavailableError


def write_populated_real_map(maps_dir):
    maps_dir.mkdir(parents=True, exist_ok=True)
    (maps_dir / "real.json").write_text(
        json.dumps(
            {
                "channel": "real",
                "version": 1,
                "selectors": {key: f"[data-test='{key}']" for key in driver._REAL_REQUIRED_SELECTOR_KEYS},
                "attributes": {key: f"data-{key.replace('_', '-')}" for key in driver._REAL_REQUIRED_ATTRIBUTE_KEYS},
            }
        ),
        encoding="utf-8",
    )
    return maps_dir


def install_fake_real_playwright(monkeypatch, redirected_url, launch_kwargs_log=None):
    goto_calls = []

    class FakePage:
        def __init__(self):
            self.url = "about:blank"

        def goto(self, url, **kwargs):
            goto_calls.append(url)
            self.url = redirected_url
            return None

        def close(self):
            pass

    class FakeContext:
        def __init__(self):
            self.pages = [FakePage()]
            self.routes = []

        def route(self, pattern, handler):
            self.routes.append((pattern, handler))

        def new_page(self):
            page = FakePage()
            self.pages.append(page)
            return page

        def close(self):
            pass

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            if launch_kwargs_log is not None:
                launch_kwargs_log.append(kwargs)
            return FakeContext()

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()

        def stop(self):
            pass

    class FakePlaywrightStarter:
        def start(self):
            return FakePlaywright()

    monkeypatch.setattr(driver, "sync_playwright", lambda: FakePlaywrightStarter())
    return goto_calls


def test_profile_lock_preflight_raises_named_error_without_deleting_lock(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    lock = profile / "SingletonLock"
    lock.touch()
    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=write_populated_real_map(tmp_path / "maps"))

    with pytest.raises(ProfileLockedError):
        session._preflight_profile_lock()
    assert lock.exists()

    lock.unlink()
    session._preflight_profile_lock()


def test_locked_profile_fails_after_real_selector_preflight_before_playwright_start(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "SingletonLock").touch()
    playwright_starts = []
    navigations = []

    class FakePlaywrightStarter:
        def start(self):
            playwright_starts.append(True)
            raise AssertionError("sync_playwright.start must not be called for a locked profile")

    monkeypatch.setattr(driver, "sync_playwright", lambda: FakePlaywrightStarter())

    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=write_populated_real_map(tmp_path / "maps"))
    with pytest.raises(ProfileLockedError):
        session.start()
    assert playwright_starts == []
    assert navigations == []


def test_empty_real_selector_map_still_fails_before_profile_lock_and_launch(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "SingletonLock").touch()
    playwright_starts = []

    class FakePlaywrightStarter:
        def start(self):
            playwright_starts.append(True)
            raise AssertionError("sync_playwright.start must not be called before D2 selector readiness")

    monkeypatch.setattr(driver, "sync_playwright", lambda: FakePlaywrightStarter())

    session = driver.BrowserSession(channel="real", profile_path=profile)
    with pytest.raises(SelectorUnavailableError):
        session.start()
    assert playwright_starts == []


def test_singleton_launch_failure_maps_to_profile_locked_error(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            raise RuntimeError("ProcessSingleton profile already in use: SingletonLock")

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()
            self.stopped = False

        def stop(self):
            self.stopped = True

    class FakePlaywrightStarter:
        def start(self):
            return FakePlaywright()

    monkeypatch.setattr(driver, "sync_playwright", lambda: FakePlaywrightStarter())

    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=write_populated_real_map(tmp_path / "maps"))
    with pytest.raises(ProfileLockedError):
        session.start()


def test_real_start_raises_login_required_on_auth_redirect_url(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    goto_calls = install_fake_real_playwright(monkeypatch, "https://auth.openai.com/authorize?state=SECRET")

    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=write_populated_real_map(tmp_path / "maps"))
    with pytest.raises(LoginRequiredError):
        session.start()
    assert goto_calls == [driver.REAL_BASE_URL]


def test_real_start_allows_normal_chatgpt_url_without_login_url_error(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    goto_calls = install_fake_real_playwright(monkeypatch, "https://chatgpt.com/")

    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=write_populated_real_map(tmp_path / "maps"))
    try:
        assert session.start() is session
        assert goto_calls == [driver.REAL_BASE_URL]
    finally:
        session.close()


def test_real_launch_passes_executable_path_when_configured(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    launch_kwargs = []
    install_fake_real_playwright(monkeypatch, "https://chatgpt.com/", launch_kwargs_log=launch_kwargs)

    session = driver.BrowserSession(
        channel="real",
        profile_path=profile,
        maps_dir=write_populated_real_map(tmp_path / "maps"),
        executable_path="/usr/bin/chromium",
    )
    try:
        session.start()
        assert launch_kwargs[0]["executable_path"] == "/usr/bin/chromium"
    finally:
        session.close()


def test_real_launch_omits_executable_path_when_unset(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    launch_kwargs = []
    install_fake_real_playwright(monkeypatch, "https://chatgpt.com/", launch_kwargs_log=launch_kwargs)

    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=write_populated_real_map(tmp_path / "maps"))
    try:
        session.start()
        assert launch_kwargs[0].get("executable_path") is None
    finally:
        session.close()
