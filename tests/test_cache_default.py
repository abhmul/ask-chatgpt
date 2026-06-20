from __future__ import annotations

from ask_chatgpt.channels.base import RequestSnapshot
from ask_chatgpt.channels.mock import HEADER_CANARIES, MockChannel, MockScenario
from ask_chatgpt.cli import main as cli_main
from ask_chatgpt.identity import ConversationRef, conversation_url
from ask_chatgpt.models import TurnRecord
from ask_chatgpt.session import Session
from ask_chatgpt.store import Store
from mock_scenarios import large_mapping_raw


CONV_ID = "conv_cache_123"


class NoBrowserChannel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):  # noqa: ANN204 - dynamically fails any browser method.
        def fail(*args: object, **kwargs: object) -> None:
            del args, kwargs
            self.calls.append(name)
            raise AssertionError(f"browser channel method must not be called: {name}")

        return fail


class ExplodingMockChannel:
    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("export must not construct a browser channel")


def _turn(ref: ConversationRef, *, role: str, message_id: str, turn_index: int, text: str) -> TurnRecord:
    return TurnRecord(
        conversation_id=ref.conversation_id or "",
        conversation_url=conversation_url(ref),
        project_id=ref.project_id,
        message_id=message_id,
        parent_id=None if role == "user" else "user-cache-1",
        turn_index=turn_index,
        role=role,  # type: ignore[arg-type]
        content_markdown=text,
        model=None,
        active_tools=(),
        kind="normal",
        created_at=None,
        attachments=(),
        citations=(),
        status="complete",
        partial=False,
        user_message_id="user-cache-1" if role == "assistant" else None,
        capture_source="backend_api",
        fidelity="canonical",
        error=None,
    )


def _seed_cached_transcript(data_dir) -> ConversationRef:  # noqa: ANN001
    ref = ConversationRef(CONV_ID, f"https://chatgpt.com/c/{CONV_ID}")
    Store(data_dir=data_dir).upsert_many(
        [
            _turn(ref, role="user", message_id="user-cache-1", turn_index=0, text="USER-CACHE-SENTINEL"),
            _turn(ref, role="assistant", message_id="assistant-cache-1", turn_index=1, text="ASSISTANT-CACHE-SENTINEL"),
        ]
    )
    return ref


def test_history_and_export_read_cached_transcript_without_browser(tmp_path, capsys, monkeypatch) -> None:
    ref = _seed_cached_transcript(tmp_path)
    channel = NoBrowserChannel()

    transcript = Session(data_dir=tmp_path, channel=channel).history(ref.conversation_id or "")

    assert channel.calls == []
    assert [turn.message_id for turn in transcript.turns] == ["user-cache-1", "assistant-cache-1"]

    import ask_chatgpt.channels.mock as mock_module

    monkeypatch.setattr(mock_module, "MockChannel", ExplodingMockChannel)
    code = cli_main([
        "export",
        ref.conversation_id or "",
        "--selector-channel",
        "mock",
        "--data-dir",
        str(tmp_path),
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        "## User",
        "",
        "USER-CACHE-SENTINEL",
        "",
        "## Assistant",
        "",
        "ASSISTANT-CACHE-SENTINEL",
    ]


def _scrape_scenario(answer_text: str) -> MockScenario:
    raw = large_mapping_raw(conversation_id=CONV_ID, leaf_index=2)
    raw["mapping"]["node_0002"]["message"]["content"]["parts"] = [answer_text]
    return MockScenario(
        name=f"refresh_{answer_text}",
        backend_conversations={CONV_ID: raw},
        request_snapshots=(
            RequestSnapshot(
                url=f"https://chatgpt.com/backend-api/conversation/{CONV_ID}",
                method="GET",
                headers=dict(HEADER_CANARIES),
            ),
        ),
    )


def test_rescrape_refreshes_cached_transcript_last_writer_wins(tmp_path) -> None:
    ref = ConversationRef(CONV_ID, f"https://chatgpt.com/c/{CONV_ID}")

    first = Session(data_dir=tmp_path, channel=MockChannel(_scrape_scenario("FIRST-CACHE-SENTINEL"))).scrape(ref)
    initially_cached = Store(data_dir=tmp_path).load_transcript(ref)
    refreshed = Session(data_dir=tmp_path, channel=MockChannel(_scrape_scenario("REFRESHED-CACHE-SENTINEL"))).scrape(ref)
    cached = Store(data_dir=tmp_path).load_transcript(ref)

    assert [turn.message_id for turn in first.turns] == ["msg_user_1", "msg_assistant_single"]
    assert [turn.message_id for turn in initially_cached.turns] == ["msg_user_1", "msg_assistant_single"]
    assert initially_cached.turns[1].content_markdown == "FIRST-CACHE-SENTINEL"
    assert [turn.message_id for turn in refreshed.turns] == ["msg_user_1", "msg_assistant_single"]
    assert [turn.message_id for turn in cached.turns] == ["msg_user_1", "msg_assistant_single"]
    assert cached.turns[1].content_markdown == "REFRESHED-CACHE-SENTINEL"
