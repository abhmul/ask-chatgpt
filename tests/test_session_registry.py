import json

import pytest

from ask_chatgpt.errors import AskChatGPTError
from ask_chatgpt.session_registry import ConversationRef, SessionRegistry


def test_round_trip_set_get_list_delete_with_explicit_store(tmp_path):
    store_path = tmp_path / "sessions.json"
    registry = SessionRegistry(store_path=store_path)
    ref = ConversationRef(
        conversation_ref="conv_123",
        url="https://chatgpt.com/c/conv_123",
        model_settings={"model": "test-model", "temperature": 0},
    )

    assert registry.get("missing") is None

    registry.set("work-session", ref)

    assert registry.get("work-session") == ref
    assert registry.list() == {"work-session": ref}
    assert json.loads(store_path.read_text(encoding="utf-8"))["sessions"]["work-session"]["conversation_ref"] == "conv_123"
    assert registry.delete("missing") is False
    assert registry.delete("work-session") is True
    assert registry.get("work-session") is None
    assert registry.list() == {}


def test_persists_across_fresh_registry_instance(tmp_path):
    store_path = tmp_path / "nested" / "sessions.json"
    ref = ConversationRef(conversation_ref="stable-ref", url=None, model_settings={"model": "gpt-test"})

    first = SessionRegistry(store_path=store_path)
    first.set("continuity", ref)

    second = SessionRegistry(store_path=store_path)
    assert second.get("continuity") == ref


def test_corrupt_json_raises_actionable_package_error(tmp_path):
    store_path = tmp_path / "sessions.json"
    store_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(AskChatGPTError) as excinfo:
        SessionRegistry(store_path=store_path)

    message = str(excinfo.value).lower()
    assert "session" in message
    assert "repair" in message or "replace" in message or "delete" in message
    assert "jsondecodeerror" not in message


def test_default_store_path_can_be_redirected_by_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ASK_CHATGPT_STATE_DIR", str(tmp_path / "state"))
    registry = SessionRegistry()
    ref = ConversationRef(conversation_ref="env-ref", url=None)

    registry.set("env-session", ref)

    expected_store = tmp_path / "state" / "sessions.json"
    assert expected_store.exists()
    assert SessionRegistry().get("env-session") == ref
