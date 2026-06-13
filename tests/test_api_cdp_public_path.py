from __future__ import annotations

from types import SimpleNamespace

import ask_chatgpt.api as api
from ask_chatgpt import cli
from ask_chatgpt.session_registry import SessionRegistry


class _CapturingBrowserSession:
    captured_kwargs: list[dict[str, object]] = []
    open_conversation_refs: list[str | None] = []
    settled_ref: str | None = "settled-ref"

    @classmethod
    def reset(cls, *, settled_ref: str | None = "settled-ref") -> None:
        cls.captured_kwargs = []
        cls.open_conversation_refs = []
        cls.settled_ref = settled_ref

    def __init__(self, **kwargs):
        type(self).captured_kwargs.append(dict(kwargs))
        self.page = SimpleNamespace(url="http://127.0.0.1:9/")
        self.selectors = object()
        self.active_conversation_ref = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def open_or_create_conversation(self, conversation_ref):
        type(self).open_conversation_refs.append(conversation_ref)
        self.active_conversation_ref = conversation_ref or ""
        return self.active_conversation_ref

    def select_model(self, model_settings):
        return None

    def send_prompt(self, prompt):
        return None

    def wait_for_completion(self, *, timeout_s):
        if type(self).settled_ref is not None:
            self.page.url = f"http://127.0.0.1:9/c/{type(self).settled_ref}"
        return object()

    def refresh_active_conversation_ref(self):
        if "/c/" not in self.page.url:
            return None
        ref = self.page.url.rsplit("/c/", 1)[1].split("?", 1)[0].strip("/")
        if not ref:
            return None
        self.active_conversation_ref = ref
        return ref


def test_ask_chatgpt_forwards_cdp_endpoint_plain_and_bundle_paths(monkeypatch, tmp_path):
    _CapturingBrowserSession.reset()
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


def test_ask_chatgpt_persists_settled_cdp_ref_and_reuses_it_on_plain_path(monkeypatch, tmp_path):
    _CapturingBrowserSession.reset()
    monkeypatch.setattr(api, "BrowserSession", _CapturingBrowserSession)
    monkeypatch.setattr(api, "read_response", lambda *_args, **_kwargs: "api response")
    registry = SessionRegistry(store_path=tmp_path / "sessions.json")

    first = api.ask_chatgpt(
        "plain prompt",
        session_identifier="plain-continuity",
        channel="cdp",
        base_url="http://127.0.0.1:9",
        registry=registry,
    )
    second = api.ask_chatgpt(
        "second prompt",
        session_identifier="plain-continuity",
        channel="cdp",
        base_url="http://127.0.0.1:9",
        registry=registry,
    )

    assert first == "api response"
    assert second == "api response"
    assert registry.get("plain-continuity").conversation_ref == "settled-ref"
    assert _CapturingBrowserSession.open_conversation_refs == [None, "settled-ref"]


def test_ask_chatgpt_persists_settled_cdp_ref_and_reuses_it_on_bundle_path(monkeypatch, tmp_path):
    _CapturingBrowserSession.reset()
    monkeypatch.setattr(api, "BrowserSession", _CapturingBrowserSession)
    monkeypatch.setattr(api, "read_response", lambda *_args, **_kwargs: "api response")
    monkeypatch.setattr(api, "upload_bundle", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "retrieve_patch_bundle", lambda *_args, **_kwargs: None)
    registry = SessionRegistry(store_path=tmp_path / "sessions.json")
    bundle_file = tmp_path / "input.txt"
    bundle_file.write_text("bundle input\n", encoding="utf-8")

    first = api.ask_chatgpt(
        "bundle prompt",
        session_identifier="bundle-continuity",
        channel="cdp",
        base_url="http://127.0.0.1:9",
        registry=registry,
        files=[bundle_file.name],
        bundle_root=tmp_path,
    )
    second = api.ask_chatgpt(
        "second bundle prompt",
        session_identifier="bundle-continuity",
        channel="cdp",
        base_url="http://127.0.0.1:9",
        registry=registry,
        files=[bundle_file.name],
        bundle_root=tmp_path,
    )

    assert first.text == "api response"
    assert second.text == "api response"
    assert registry.get("bundle-continuity").conversation_ref == "settled-ref"
    assert _CapturingBrowserSession.open_conversation_refs == [None, "settled-ref"]


def test_ask_chatgpt_skips_registry_persistence_when_cdp_url_never_settles(monkeypatch, tmp_path):
    _CapturingBrowserSession.reset(settled_ref=None)
    monkeypatch.setattr(api, "BrowserSession", _CapturingBrowserSession)
    monkeypatch.setattr(api, "read_response", lambda *_args, **_kwargs: "api response")
    registry = SessionRegistry(store_path=tmp_path / "sessions.json")

    result = api.ask_chatgpt(
        "plain prompt",
        session_identifier="unsettled-continuity",
        channel="cdp",
        base_url="http://127.0.0.1:9",
        registry=registry,
    )

    assert result == "api response"
    assert registry.get("unsettled-continuity") is None


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
