"""Minimal command-line entry point for the v2 rewrite scaffold."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from ask_chatgpt import __version__

_HELP = """usage: ask-chatgpt [--help] [--version] <command> [args...]

ask-chatgpt v2 rewrite scaffold.

The full CLI is not yet implemented; see docs/REWRITE-SPEC.md.
"""


_NOT_IMPLEMENTED = (
    "ask-chatgpt: not yet implemented "
    "(rewrite in progress; see docs/REWRITE-SPEC.md)"
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the minimal v2 rewrite CLI scaffold."""
    args = list(sys.argv[1:] if argv is None else argv)

    if args == ["--version"]:
        print(__version__)
        return 0

    if not args or args == ["--help"] or args == ["-h"]:
        print(_HELP, end="")
        return 0

    print(_NOT_IMPLEMENTED, file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
