from ask_chatgpt import __version__
from ask_chatgpt.cli import main


def test_package_exposes_non_empty_version() -> None:
    assert isinstance(__version__, str)
    assert __version__


def test_version_flag_prints_version(capsys) -> None:
    assert main(["--version"]) == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == __version__
    assert captured.err == ""


def test_help_flag_describes_rewrite_scaffold(capsys) -> None:
    assert main(["--help"]) == 0

    captured = capsys.readouterr()
    assert "usage: ask-chatgpt" in captured.out
    assert "docs/REWRITE-SPEC.md" in captured.out
    assert captured.err == ""


def test_unimplemented_command_is_actionable_and_nonzero(capsys) -> None:
    assert main(["ask", "hello"]) != 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not yet implemented" in captured.err
    assert "docs/REWRITE-SPEC.md" in captured.err
