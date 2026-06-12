"""Autouse socket guard: tests may connect only to loopback or AF_UNIX."""
import ipaddress
import socket

import pytest

from tests.fixtures.mock_chatgpt import MockChatGPTServer

_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
_GUARD_ACTIVE = False


def _allowed(address):
    if not isinstance(address, tuple) or not address:
        return True  # AF_UNIX paths / non-TCP shapes are not external TCP.
    raw_host = address[0]
    host = raw_host.decode("ascii", "ignore") if isinstance(raw_host, bytes) else str(raw_host)
    if host in _ALLOWED_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _network_guard():
    """Patch TCP connect APIs; Playwright loopback/unix traffic remains allowed."""
    global _GUARD_ACTIVE
    orig_connect, orig_connect_ex = socket.socket.connect, socket.socket.connect_ex
    orig_create_connection = socket.create_connection

    def block(sock, address):
        if sock.family != socket.AF_UNIX and not _allowed(address):
            raise RuntimeError(f"NETWORK BLOCKED: {address}")

    def checked_connect(sock, address):
        block(sock, address); return orig_connect(sock, address)

    def checked_connect_ex(sock, address):
        block(sock, address); return orig_connect_ex(sock, address)

    def checked_create_connection(address, *args, **kwargs):
        if not _allowed(address):
            raise RuntimeError(f"NETWORK BLOCKED: {address}")
        return orig_create_connection(address, *args, **kwargs)

    socket.socket.connect = checked_connect
    socket.socket.connect_ex = checked_connect_ex
    socket.create_connection = checked_create_connection
    _GUARD_ACTIVE = True
    try:
        yield
    finally:
        _GUARD_ACTIVE = False
        socket.create_connection = orig_create_connection
        socket.socket.connect_ex = orig_connect_ex
        socket.socket.connect = orig_connect


@pytest.fixture
def socket_guard_active():
    """Tests request this fixture to assert the autouse guard is active."""
    return _GUARD_ACTIVE


@pytest.fixture
def mock_chatgpt():
    """Start a loopback-only ephemeral-port mock ChatGPT server."""
    server = MockChatGPTServer().start()
    try:
        yield server.make_handle()
    finally:
        server.stop()
