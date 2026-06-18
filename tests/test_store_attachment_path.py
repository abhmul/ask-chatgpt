from __future__ import annotations

import pytest

from ask_chatgpt.errors import StoreError
from ask_chatgpt.models import AttachmentRef
from ask_chatgpt.store import Store


def ref(filename: str | None, *, source_ref: str | None = "file_123", sha256: str | None = None) -> AttachmentRef:
    return AttachmentRef(
        source_kind="file_reference",
        source_ref=source_ref,
        raw_path="/mapping/node/content_references/0",
        filename=filename,
        mime="text/plain",
        bytes=7,
        sha256=sha256,
        local_path=None,
        download_state="pending",
        metadata={},
    )


def test_attachment_path_is_deterministic_under_conversation_attachments_and_collision_safe(tmp_path) -> None:
    store = Store(data_dir=tmp_path)
    first = ref("report.txt", source_ref="file_123")
    duplicate_name = ref("report.txt", source_ref="file_456")

    first_path = store.attachment_path("chat_123", first)
    repeat_path = store.attachment_path("chat_123", first)
    duplicate_path = store.attachment_path("chat_123", duplicate_name)

    assert first_path == repeat_path
    assert first_path.parent == tmp_path / "conversations" / "chat_123" / "attachments"
    assert first_path.name.endswith("__report.txt")
    assert duplicate_path.parent == first_path.parent
    assert duplicate_path != first_path
    assert first_path.resolve().is_relative_to((tmp_path / "conversations" / "chat_123" / "attachments").resolve())


@pytest.mark.parametrize("filename", ["../../secret", "/tmp/secret"])
def test_attachment_path_rejects_traversal_and_absolute_filenames(tmp_path, filename: str) -> None:
    store = Store(data_dir=tmp_path)

    with pytest.raises(StoreError):
        store.attachment_path("chat_123", ref(filename))
