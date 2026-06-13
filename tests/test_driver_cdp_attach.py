from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import pytest
from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import CDPUnreachableError, ChallengePresentError, LoginRequiredError


_CDP_LAUNCH_COMMAND = "chromium --profile-directory='Profile 1' --remote-debugging-port=9222"
_LOOPBACK_HOST = "127.0.0.1"


@dataclass(frozen=True)
class ThrowawayChromium:
    endpoint: str
    port: int
    process: subprocess.Popen
    user_data_dir: Path


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((_LOOPBACK_HOST, 0))
        return int(sock.getsockname()[1])


def _chromium_executable() -> str:
    for env_name in ("CHROMIUM", "CHROME_BIN"):
        value = os.environ.get(env_name)
        if value and Path(value).exists():
            return value
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        value = shutil.which(name)
        if value:
            return value
    try:
        with sync_playwright() as playwright:
            value = playwright.chromium.executable_path
    except PlaywrightError as exc:
        pytest.skip(f"Chromium executable unavailable: {exc}")
    if not Path(value).exists():
        pytest.skip(f"Chromium executable unavailable: {value}")
    return value


def _cdp_json(endpoint: str, path: str, *, method: str = "GET") -> Any:
    request = Request(endpoint.rstrip("/") + path, method=method)
    with urlopen(request, timeout=1.0) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else None


def _wait_for_cdp_endpoint(endpoint: str, process: subprocess.Popen, *, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"throwaway Chromium exited before CDP was ready with code {process.returncode}")
        try:
            payload = _cdp_json(endpoint, "/json/version")
            if isinstance(payload, dict) and payload.get("webSocketDebuggerUrl"):
                return
        except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError("throwaway Chromium CDP endpoint did not become ready") from last_error


def _page_targets(endpoint: str) -> list[dict[str, Any]]:
    payload = _cdp_json(endpoint, "/json/list")
    assert isinstance(payload, list)
    return [target for target in payload if target.get("type") == "page"]


def _target_ids(endpoint: str) -> set[str]:
    return {str(target["id"]) for target in _page_targets(endpoint)}


def _wait_for_page_target(endpoint: str, predicate: Callable[[dict[str, Any]], bool], *, timeout_s: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for target in _page_targets(endpoint):
            if predicate(target):
                return target
        time.sleep(0.05)
    raise AssertionError("matching CDP page target did not appear")


def _new_cdp_tab(endpoint: str, url: str) -> dict[str, Any]:
    payload = _cdp_json(endpoint, "/json/new?" + quote(url, safe=":/"), method="PUT")
    assert isinstance(payload, dict)
    assert payload.get("type") == "page"
    return payload


def _terminate_throwaway(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


@pytest.fixture
def throwaway_chromium(tmp_path):
    port = _free_loopback_port()
    endpoint = f"http://{_LOOPBACK_HOST}:{port}"
    user_data_dir = tmp_path / "throwaway-chromium-profile"
    user_data_dir.mkdir()
    command = [
        _chromium_executable(),
        f"--remote-debugging-port={port}",
        f"--remote-debugging-address={_LOOPBACK_HOST}",
        f"--user-data-dir={user_data_dir}",
        "--headless=new",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-features=Translate,MediaRouter",
        "--disable-popup-blocking",
        "--disable-sync",
        "--metrics-recording-only",
        "--password-store=basic",
        "--safebrowsing-disable-auto-update",
        "--use-mock-keychain",
        "about:blank",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        _wait_for_cdp_endpoint(endpoint, process)
        yield ThrowawayChromium(endpoint=endpoint, port=port, process=process, user_data_dir=user_data_dir)
    finally:
        _terminate_throwaway(process)
        shutil.rmtree(user_data_dir, ignore_errors=True)


class _LoopbackFixtureServer:
    def __init__(self) -> None:
        self._server = ThreadingHTTPServer((_LOOPBACK_HOST, 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=False)
        self.host = _LOOPBACK_HOST
        self.port = int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def start(self) -> "_LoopbackFixtureServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("loopback fixture server did not stop")

    @staticmethod
    def _handler() -> type[BaseHTTPRequestHandler]:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
                return

            def _send_html(self, body: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
                payload = body.encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("cache-control", "no-store")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/challenge":
                    self._send_html(
                        "<!doctype html><title>Just a moment…</title><main id='challenge-running'>Checking your browser</main>"
                    )
                    return
                if path == "/login-redirect":
                    self.send_response(HTTPStatus.FOUND)
                    self.send_header("location", "/auth/login")
                    self.send_header("cache-control", "no-store")
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return
                if path == "/auth/login":
                    self._send_html("<!doctype html><title>Login</title><main>Login required</main>")
                    return
                self._send_html("<!doctype html><title>Not found</title>", status=HTTPStatus.NOT_FOUND)

        return Handler


@pytest.fixture
def loopback_fixture_server():
    server = _LoopbackFixtureServer().start()
    try:
        yield server
    finally:
        server.stop()


def test_cdp_unreachable_raises_actionable_error_on_closed_port():
    closed_port = _free_loopback_port()
    session = BrowserSession(channel="cdp", cdp_endpoint=f"http://{_LOOPBACK_HOST}:{closed_port}")

    with pytest.raises(CDPUnreachableError) as excinfo:
        session.start()

    assert _CDP_LAUNCH_COMMAND in str(excinfo.value)


def test_cdp_attach_opens_new_tab_and_drives_mock_uc1(mock_chatgpt, throwaway_chromium):
    answer = "CDP attach happy path answer 4b81d5"
    prompt = "hello through cdp"
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(answer, streaming=True, stream_reads=1)
    before_ids = _target_ids(throwaway_chromium.endpoint)

    with BrowserSession(
        channel="cdp",
        base_url=mock_chatgpt.base_url,
        cdp_endpoint=throwaway_chromium.endpoint,
    ) as session:
        conversation_ref = session.open_or_create_conversation(None)
        assert conversation_ref.startswith("conv-")
        session.send_prompt(prompt)
        latest = session.wait_for_completion(timeout_s=6)

        expect(latest.locator(session.selectors.selector("message_body"))).to_have_text(answer, timeout=1000)
        assert mock_chatgpt.inspect()["last_prompt"] == prompt
        assert session.page is not None
        assert session.page.url.startswith(mock_chatgpt.base_url + "/c/")
        assert "chatgpt.com" not in session.page.url
        _wait_for_page_target(
            throwaway_chromium.endpoint,
            lambda target: str(target.get("id")) not in before_ids and str(target.get("url", "")).startswith(mock_chatgpt.base_url),
        )


def test_cdp_close_detaches_without_closing_preexisting_tabs_or_browser(mock_chatgpt, throwaway_chromium):
    preexisting = _new_cdp_tab(throwaway_chromium.endpoint, "about:blank")
    preexisting_id = str(preexisting["id"])
    before_ids = _target_ids(throwaway_chromium.endpoint)
    answer = "CDP tab hygiene answer 9317a2"
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(answer, streaming=True, stream_reads=1)
    session = BrowserSession(channel="cdp", base_url=mock_chatgpt.base_url, cdp_endpoint=throwaway_chromium.endpoint)
    tool_ids: set[str] = set()

    try:
        session.start()
        session.open_or_create_conversation(None)
        session.send_prompt("prove tab hygiene")
        latest = session.wait_for_completion(timeout_s=6)
        expect(latest.locator(session.selectors.selector("message_body"))).to_have_text(answer, timeout=1000)
        tool_target = _wait_for_page_target(
            throwaway_chromium.endpoint,
            lambda target: str(target.get("id")) not in before_ids and str(target.get("url", "")).startswith(mock_chatgpt.base_url),
        )
        tool_ids.add(str(tool_target["id"]))
    finally:
        session.close()

    assert throwaway_chromium.process.poll() is None
    _cdp_json(throwaway_chromium.endpoint, "/json/version")
    after_targets = _page_targets(throwaway_chromium.endpoint)
    after_ids = {str(target["id"]) for target in after_targets}
    assert preexisting_id in after_ids
    preexisting_after = next(target for target in after_targets if str(target["id"]) == preexisting_id)
    assert preexisting_after.get("url") == "about:blank"
    assert tool_ids
    assert tool_ids.isdisjoint(after_ids)


def test_cdp_detects_challenge_and_login_states_on_loopback(throwaway_chromium, loopback_fixture_server):
    challenge_session = BrowserSession(
        channel="cdp",
        base_url=loopback_fixture_server.url("/challenge"),
        cdp_endpoint=throwaway_chromium.endpoint,
    )
    with pytest.raises(ChallengePresentError, match="CHALLENGE_PRESENT"):
        challenge_session.start()

    login_session = BrowserSession(
        channel="cdp",
        base_url=loopback_fixture_server.url("/login-redirect"),
        cdp_endpoint=throwaway_chromium.endpoint,
    )
    with pytest.raises(LoginRequiredError):
        login_session.start()
