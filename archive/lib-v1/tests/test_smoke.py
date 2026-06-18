import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from playwright.async_api import async_playwright

MARKER = "ask-chatgpt-loopback-smoke-marker-8d34b7"


class MarkerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"<!doctype html><html><body>{MARKER}</body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def test_import_package(socket_guard_active):
    import ask_chatgpt

    assert socket_guard_active
    assert ask_chatgpt.__version__ == "0.0.1"


def test_playwright_chromium_loopback(socket_guard_active):
    assert socket_guard_active
    server = ThreadingHTTPServer(("127.0.0.1", 0), MarkerHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()

    async def run_browser_smoke():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(f"http://127.0.0.1:{port}/", wait_until="load")
                assert MARKER in await page.content()
            finally:
                await browser.close()

    try:
        asyncio.run(run_browser_smoke())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
