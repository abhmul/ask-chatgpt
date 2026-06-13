#!/usr/bin/env python3
"""Read-only: is the copy-turn-action button a DESCENDANT of the assistant turn element?

Sends ONE short prompt, waits via sleep (not the driver's wait), then inspects DOM ancestry.
Detach (never quit browser). Confirms whether the E6 latest-turn scoping is valid on the real DOM.
"""
from __future__ import annotations

from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ask_chatgpt.driver import BrowserSession  # noqa: E402


def main() -> int:
    session = BrowserSession(channel="cdp", base_url="https://chatgpt.com")
    session.start()
    try:
        session.open_or_create_conversation(None)
        session.send_prompt("Reply with exactly the word PONG and nothing else.")
        time.sleep(8)  # well past completion for a 1-word reply; no driver wait
        page = session.page
        info = page.evaluate(
            """() => {
                const copies = Array.from(document.querySelectorAll('button[data-testid="copy-turn-action-button"]'));
                const assistants = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
                const lastAssistant = assistants[assistants.length-1] || null;
                const copiesInsideLastAssistant = lastAssistant ? lastAssistant.querySelectorAll('button[data-testid="copy-turn-action-button"]').length : -1;
                const lastCopy = copies[copies.length-1] || null;
                const copyHasAssistantAncestor = lastCopy ? !!lastCopy.closest('[data-message-author-role="assistant"]') : null;
                return {
                    globalCopyCount: copies.length,
                    assistantTurnCount: assistants.length,
                    copiesInsideLastAssistant,
                    copyHasAssistantAncestor,
                };
            }"""
        )
        print("COPYBTN_STRUCTURE:", info)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
