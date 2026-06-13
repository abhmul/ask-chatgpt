from __future__ import annotations

from types import SimpleNamespace

import ask_chatgpt.api as api
from ask_chatgpt import cli


class _CapturingBrowserSession:
    captured_kwargs: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.captured_kwargs.append(dict(kwargs))
        self.page = SimpleNamespace(url="http://127.0.0.1:9/c/api-ref")
        self.selectors = object()
        self.active_conversation_ref = "api-ref"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def open_or_create_conversation(self, conversation_ref):
        return conversation_ref or "api-ref"

    def select_model(self, model_settings):
        return None

    def send_prompt(self, prompt):
        return None

    def wait_for_completion(self, *, timeout_s):
        return object()


def test_ask_chatgpt_forwards_cdp_endpoint_plain_and_bundle_paths(monkeypatch, tmp_path):
    _CapturingBrowserSession.captured_kwargs = []
    endpoint = "http://127.0.0.1:9333"
    monkeypatch.setattr(api, "BrowserSession", _CapturingBrowserSession)
    monkeypatch.setattr(api, "read_response", lambda *_args, **_kwargs: "api response")
    monkeypatch.setattr(api, "upload_bundle", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "retrieve_patch_bundle", lambda *_args, **_kwargs: None)

    plain = api.ask_chatgpt("plain prompt", channel="cdp", base_url="http://127.0.0.1:9", cdp_endpoint=endpoint)
    bundle_file = tmp_path / "input.txt"
    bundle_file.write_text("bundle input\n", encoding="utf-8")
    bundle = api.ask_chatgpt(
        "bundle prompt",
        channel="cdp",
        base_url="http://127.0.0.1:9",
        cdp_endpoint=endpoint,
        files=[bundle_file.name],
        bundle_root=tmp_path,
    )

    assert plain == "api response"
    assert bundle.text == "api response"
    assert [kwargs["cdp_endpoint"] for kwargs in _CapturingBrowserSession.captured_kwargs] == [endpoint, endpoint]
    assert [kwargs["channel"] for kwargs in _CapturingBrowserSession.captured_kwargs] == ["cdp", "cdp"]


def test_cli_accepts_cdp_channel_and_forwards_endpoint(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_ask_chatgpt(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return "cli response"

    monkeypatch.setattr(cli, "ask_chatgpt", fake_ask_chatgpt)

    code = cli.main([
        "--channel",
        "cdp",
        "--cdp-endpoint",
        "http://127.0.0.1:9444",
        "--base-url",
        "http://127.0.0.1:9",
        "hello cdp",
    ])

    output = capsys.readouterr()
    assert code == 0
    assert output.out == "cli response"
    assert output.err == ""
    assert captured["prompt"] == "hello cdp"
    assert captured["channel"] == "cdp"
    assert captured["cdp_endpoint"] == "http://127.0.0.1:9444"


def test_cli_cdp_endpoint_default_is_loopback():
    args = cli._build_parser().parse_args(["--channel", "cdp", "hello"])

    assert args.channel == "cdp"
    assert args.cdp_endpoint == "http://127.0.0.1:9222"
