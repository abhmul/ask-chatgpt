import json
from pathlib import Path

import pytest

import ask_chatgpt.driver as driver
from ask_chatgpt.errors import LoginRequiredError, ProfileLockedError, SelectorUnavailableError


EMPTY_REAL_SELECTOR_MAPS_DIR = Path(__file__).parent / "fixtures" / "selector_maps" / "empty"


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


def install_fake_real_playwright(monkeypatch, redirected_url, launch_kwargs_log=None, goto_kwargs_log=None):
    goto_calls = []

    class FakePage:
        def __init__(self):
            self.url = "about:blank"

        def goto(self, url, **kwargs):
            goto_calls.append(url)
            if goto_kwargs_log is not None:
                goto_kwargs_log.append(dict(kwargs))
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


class _StartFakeLocator:
    def count(self):
        return 0


class _StartFakePage:
    def __init__(self, goto_calls, redirected_url):
        self.url = "about:blank"
        self._goto_calls = goto_calls
        self._redirected_url = redirected_url
        self.routes = []

    def goto(self, url, **kwargs):
        self._goto_calls.append((url, dict(kwargs)))
        self.url = self._redirected_url
        return None

    def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    def locator(self, _selector):
        return _StartFakeLocator()

    def title(self):
        return "ChatGPT"

    def close(self):
        pass


class _StartFakeContext:
    def __init__(self, goto_calls, redirected_url):
        self._goto_calls = goto_calls
        self._redirected_url = redirected_url
        self.pages = []
        self.routes = []
        self.permissions = []

    def new_page(self):
        page = _StartFakePage(self._goto_calls, self._redirected_url)
        self.pages.append(page)
        return page

    def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    def grant_permissions(self, permissions, *, origin):
        self.permissions.append((tuple(permissions), origin))

    def close(self):
        pass


class _StartFakeBrowser:
    def __init__(self, context):
        self.contexts = [context]
        self._context = context

    def new_context(self, **_kwargs):
        return self._context

    def close(self):
        pass


def install_fake_start_playwright(monkeypatch, redirected_url):
    goto_calls = []
    contexts = []

    class FakeChromium:
        def launch(self, **_kwargs):
            context = _StartFakeContext(goto_calls, redirected_url)
            contexts.append(context)
            return _StartFakeBrowser(context)

        def launch_persistent_context(self, **_kwargs):
            context = _StartFakeContext(goto_calls, redirected_url)
            contexts.append(context)
            return context

        def connect_over_cdp(self, _endpoint, **_kwargs):
            context = _StartFakeContext(goto_calls, redirected_url)
            contexts.append(context)
            return _StartFakeBrowser(context)

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


@pytest.mark.parametrize(
    ("channel", "expected_timeout_ms"),
    [("mock", 5_000), ("real", 60_000), ("cdp", 60_000)],
)
def test_start_navigation_timeout_is_long_only_for_real_and_cdp(tmp_path, monkeypatch, channel, expected_timeout_ms):
    redirected_url = driver.REAL_BASE_URL if channel == "real" else "http://127.0.0.1:9"
    goto_calls = install_fake_start_playwright(monkeypatch, redirected_url)
    if channel == "real":
        session = driver.BrowserSession(
            channel="real",
            profile_path=tmp_path / "profile",
            maps_dir=write_populated_real_map(tmp_path / "maps"),
        )
        expected_url = driver.REAL_BASE_URL
    elif channel == "cdp":
        session = driver.BrowserSession(
            channel="cdp",
            base_url="http://127.0.0.1:9",
            cdp_endpoint="http://127.0.0.1:9222",
        )
        expected_url = "http://127.0.0.1:9"
    else:
        session = driver.BrowserSession(channel="mock", base_url="http://127.0.0.1:9")
        expected_url = "http://127.0.0.1:9"

    try:
        session.start()
    finally:
        session.close()

    assert goto_calls == [(expected_url, {"wait_until": "load", "timeout": expected_timeout_ms})]


def test_sparse_real_selector_map_preflight_tolerates_unmapped_optional_keys(tmp_path):
    session = driver.BrowserSession(channel="real", profile_path=tmp_path / "profile")

    session._ensure_real_selector_map_ready()


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

    session = driver.BrowserSession(channel="real", profile_path=profile, maps_dir=EMPTY_REAL_SELECTOR_MAPS_DIR)
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
