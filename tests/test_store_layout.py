from __future__ import annotations

from pathlib import Path

from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.store import Store


def test_explicit_data_dir_layout_preserves_project_chat_key_and_existing_transcript(tmp_path) -> None:
    store = Store(data_dir=tmp_path / "store")
    ref = ConversationRef(
        conversation_id="chat_123",
        url="https://chatgpt.com/g/g-p-proj_789/c/chat_123",
        project_id="proj_789",
    )
    conv_dir = tmp_path / "store" / "conversations" / "chat_123"
    conv_dir.mkdir(parents=True)
    transcript = conv_dir / "transcript.jsonl"
    transcript.write_text("sentinel\n", encoding="utf-8")

    paths = store.ensure_conversation(ref)

    assert paths.root == conv_dir
    assert paths.transcript_jsonl.read_text(encoding="utf-8") == "sentinel\n"
    assert paths.raw_mapping_json == conv_dir / "raw-mapping.json"
    assert paths.attachments_dir.is_dir()
    assert paths.gitignore.read_text(encoding="utf-8") == "attachments/\n"
    assert not (tmp_path / "store" / "conversations" / "proj_789").exists()


def test_data_dir_resolution_precedence_and_repo_cache_default(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root / "tests")
    monkeypatch.setenv("ASK_CHATGPT_DATA_DIR", str(tmp_path / "env-store"))
    explicit = Store(data_dir=tmp_path / "explicit-store")
    from_env = Store()
    monkeypatch.delenv("ASK_CHATGPT_DATA_DIR")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from_default = Store()

    assert explicit.resolve_data_dir() == tmp_path / "explicit-store"
    assert from_env.resolve_data_dir() == tmp_path / "env-store"
    assert from_default.resolve_data_dir() == repo_root / "cache"
    assert from_default.resolve_data_dir() != tmp_path / "home" / ".local" / "state" / "ask-chatgpt"
