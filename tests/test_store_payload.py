from __future__ import annotations

import os

import pytest

from ask_chatgpt.errors import StoreError
from ask_chatgpt.store import Store


def test_emit_payload_writes_stdout_and_out_with_identical_string_bytes(tmp_path, capsys) -> None:
    store = Store(data_dir=tmp_path / "store")
    out = tmp_path / "payload.md"

    result = store.emit_payload("héllo\nline", out=out)

    captured = capsys.readouterr()
    assert captured.out == "héllo\nline"
    assert captured.err == ""
    assert result == out
    assert out.read_bytes() == "héllo\nline".encode("utf-8")


def test_emit_payload_bytes_with_nul_round_trips_exactly_to_stdout_and_out(tmp_path, capsysbinary) -> None:
    store = Store(data_dir=tmp_path / "store")
    out = tmp_path / "payload.bin"

    store.emit_payload(b"abc\x00def", out=out)

    captured = capsysbinary.readouterr()
    assert captured.out == b"abc\x00def"
    assert captured.err == b""
    assert out.read_bytes() == b"abc\x00def"


def test_emit_payload_prints_stdout_before_out_write_failure(tmp_path, capsys, monkeypatch) -> None:
    store = Store(data_dir=tmp_path / "store")
    out = tmp_path / "payload.md"
    out.write_text("old", encoding="utf-8")
    real_replace = os.replace

    def fail_payload_replace(src, dst):
        if os.fspath(dst) == os.fspath(out):
            raise OSError("injected out failure")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_payload_replace)

    with pytest.raises(StoreError):
        store.emit_payload("VISIBLE STDOUT FIRST", out=out)

    captured = capsys.readouterr()
    assert captured.out == "VISIBLE STDOUT FIRST"
    assert out.read_text(encoding="utf-8") == "old"
