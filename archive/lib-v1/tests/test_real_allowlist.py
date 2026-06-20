import logging

from ask_chatgpt.real_allowlist import DEFAULT_REAL_ALLOWED_DOMAINS, host_allowed, install_real_allowlist


class FakeRequest:
    def __init__(self, url):
        self.url = url


class FakeRoute:
    def __init__(self, url):
        self.request = FakeRequest(url)
        self.continued = False
        self.abort_reason = None

    def continue_(self):
        self.continued = True

    def abort(self, reason):
        self.abort_reason = reason


class FakeContext:
    def __init__(self):
        self.pattern = None
        self.handler = None

    def route(self, pattern, handler):
        self.pattern = pattern
        self.handler = handler


def test_host_allowed_matches_domain_or_dot_boundary_case_insensitive():
    assert host_allowed("chatgpt.com", DEFAULT_REAL_ALLOWED_DOMAINS)
    assert host_allowed("cdn.oaistatic.com", DEFAULT_REAL_ALLOWED_DOMAINS)
    assert not host_allowed("evil.com", DEFAULT_REAL_ALLOWED_DOMAINS)
    assert not host_allowed("notchatgpt.com", DEFAULT_REAL_ALLOWED_DOMAINS)
    assert not host_allowed(None, DEFAULT_REAL_ALLOWED_DOMAINS)


def test_real_allowlist_aborts_off_domain_records_host_only_and_continues_allowed(caplog):
    context = FakeContext()
    aborted_hosts = []
    install_real_allowlist(context, on_abort=aborted_hosts.append)
    assert context.pattern == "**/*"

    caplog.set_level(logging.WARNING, logger="ask_chatgpt.real_allowlist")
    off_domain = FakeRoute("https://evil.example/x?token=SECRET")
    context.handler(off_domain)
    assert off_domain.abort_reason == "blockedbyclient"
    assert not off_domain.continued
    assert aborted_hosts == ["evil.example"]
    assert "evil.example" in caplog.text
    assert "token" not in caplog.text
    assert "SECRET" not in caplog.text
    assert all("token" not in host and "SECRET" not in host for host in aborted_hosts)

    on_domain = FakeRoute("https://chatgpt.com/backend-api/conversation?token=SECRET")
    context.handler(on_domain)
    assert on_domain.continued
    assert on_domain.abort_reason is None
    assert aborted_hosts == ["evil.example"]
