import pytest

from ask_chatgpt import LoginRequiredError, ModelUnavailableError, ask_chatgpt
from ask_chatgpt.session_registry import SessionRegistry


def _tmp_registry(tmp_path):
    return SessionRegistry(store_path=tmp_path / "sessions.json")


def _turn_texts(snapshot, conversation_ref, role):
    return [
        turn["text"]
        for turn in snapshot["conversations"][conversation_ref]["turns"]
        if turn["role"] == role
    ]


def test_uc1_continuity_same_identifier_reuses_conversation_and_different_identifier_creates_new(
    mock_chatgpt, tmp_path
):
    mock_chatgpt.reset()
    registry = _tmp_registry(tmp_path)

    mock_chatgpt.script_next_response("UC1 first answer")
    first = ask_chatgpt(
        "UC1 continuity prompt one",
        session_identifier="s1",
        channel="mock",
        base_url=mock_chatgpt.base_url,
        registry=registry,
        timeout_s=3,
    )
    first_ref = registry.get("s1")
    assert first_ref is not None

    mock_chatgpt.script_next_response("UC1 second answer")
    second = ask_chatgpt(
        "UC1 continuity prompt two",
        session_identifier="s1",
        channel="mock",
        base_url=mock_chatgpt.base_url,
        registry=registry,
        timeout_s=3,
    )
    s1_ref = registry.get("s1")
    assert s1_ref is not None
    assert s1_ref.conversation_ref == first_ref.conversation_ref
    assert s1_ref.url and s1_ref.url.startswith(mock_chatgpt.base_url + "/c/")

    mock_chatgpt.script_next_response("UC1 different session answer")
    third = ask_chatgpt(
        "UC1 different session prompt",
        session_identifier="s2",
        channel="mock",
        base_url=mock_chatgpt.base_url,
        registry=registry,
        timeout_s=3,
    )
    s2_ref = registry.get("s2")
    assert s2_ref is not None
    assert s2_ref.conversation_ref != s1_ref.conversation_ref

    snapshot = mock_chatgpt.inspect()
    s1_user_texts = _turn_texts(snapshot, s1_ref.conversation_ref, "user")
    s2_user_texts = _turn_texts(snapshot, s2_ref.conversation_ref, "user")
    assert s1_user_texts == ["UC1 continuity prompt one", "UC1 continuity prompt two"]
    assert s2_user_texts == ["UC1 different session prompt"]
    assert first == "UC1 first answer"
    assert second == "UC1 second answer"
    assert third == "UC1 different session answer"


def test_uc1_returns_scripted_latest_text_without_older_sentinel(mock_chatgpt, tmp_path):
    mock_chatgpt.reset()
    registry = _tmp_registry(tmp_path)
    sentinel = "BOOBYTRAP-older-turn-uc1-8f0b29"

    mock_chatgpt.script_next_response(f"Older assistant trap {sentinel}")
    older = ask_chatgpt(
        "seed an older assistant turn",
        session_identifier="sentinel-session",
        channel="mock",
        base_url=mock_chatgpt.base_url,
        registry=registry,
        timeout_s=3,
    )
    assert sentinel in older

    latest_text = "UC1 latest scripted answer 8f0b29"
    mock_chatgpt.script_next_response(latest_text)
    result = ask_chatgpt(
        "return only the latest assistant turn",
        session_identifier="sentinel-session",
        channel="mock",
        base_url=mock_chatgpt.base_url,
        registry=registry,
        timeout_s=3,
    )

    assert result == latest_text
    assert sentinel not in result


def test_uc1_model_settings_available_succeeds_and_unavailable_raises(mock_chatgpt, tmp_path):
    mock_chatgpt.reset()
    registry = _tmp_registry(tmp_path)

    mock_chatgpt.script_next_response("UC1 model success")
    assert (
        ask_chatgpt(
            "select an available model",
            session_identifier="model-ok",
            model_settings={"model": "mock-default"},
            channel="mock",
            base_url=mock_chatgpt.base_url,
            registry=registry,
            timeout_s=3,
        )
        == "UC1 model success"
    )
    assert registry.get("model-ok").model_settings == {"model": "mock-default"}

    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(
        "unused unavailable model response",
        failure_mode="model_unavailable",
        unavailable_model="mock-reasoning",
    )
    with pytest.raises(ModelUnavailableError, match="mock-reasoning"):
        ask_chatgpt(
            "select an unavailable model",
            session_identifier="model-bad",
            model_settings={"model": "mock-reasoning"},
            channel="mock",
            base_url=mock_chatgpt.base_url,
            registry=registry,
            timeout_s=3,
        )


def test_uc1_honest_login_required_failure_is_named_and_actionable(mock_chatgpt, tmp_path):
    mock_chatgpt.reset()
    registry = _tmp_registry(tmp_path)
    mock_chatgpt.script_next_response("unused login response", failure_mode="login_required")

    with pytest.raises(LoginRequiredError) as excinfo:
        ask_chatgpt(
            "trigger login required",
            session_identifier="login-required",
            channel="mock",
            base_url=mock_chatgpt.base_url,
            registry=registry,
            timeout_s=3,
        )

    message = str(excinfo.value).lower()
    assert "sign in" in message
    assert "login" in message
