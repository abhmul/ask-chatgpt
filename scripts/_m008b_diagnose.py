#!/usr/bin/env python3
"""M-008b read-only page-state diagnostic (NO prompt sent).

Attaches over CDP, opens a fresh conversation, and reports composer
actionability + any overlay intercepting it. Detach (never quit browser).
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ask_chatgpt.driver import BrowserSession  # noqa: E402

REDACT = re.compile(r"/c/[^/?#\s]+")


def red(s: object) -> str:
    return REDACT.sub("/c/<redacted>", str(s))


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else None
    session = BrowserSession(channel="cdp", base_url="https://chatgpt.com")
    session.start()
    try:
        page = session.page
        if url:
            page.goto(url, wait_until="load", timeout=60_000)
            page.wait_for_selector("main:has(#prompt-textarea)", timeout=30_000, state="attached")
        else:
            session.open_or_create_conversation(None)
            page = session.page
        print("TITLE:", red(page.title()))
        print("URL:", red(page.url))
        # Temp-chat heuristic: look for the temporary-chat indicator text/affordance.
        try:
            temp_hint = page.evaluate(
                """() => {
                    const body = document.body ? document.body.innerText : '';
                    const hasTemp = /temporary chat/i.test(body);
                    const toggles = Array.from(document.querySelectorAll('[data-testid],[aria-label]'))
                        .map(e => (e.getAttribute('data-testid')||e.getAttribute('aria-label')||''))
                        .filter(s => /temporary/i.test(s)).slice(0,5);
                    return {temporaryChatTextPresent: hasTemp, temporaryAffordances: toggles};
                }"""
            )
            print("TEMP_HINT:", red(temp_hint))
        except Exception as exc:  # noqa: BLE001
            print("temp_hint ERROR:", type(exc).__name__, red(exc))
        ta = page.locator("#prompt-textarea")
        print("composer.count:", ta.count())
        try:
            print("composer.is_visible:", ta.first.is_visible())
            print("composer.is_enabled:", ta.first.is_enabled())
            print("composer.bbox:", ta.first.bounding_box())
        except Exception as exc:  # noqa: BLE001
            print("composer.state ERROR:", type(exc).__name__, red(exc))
        # What element sits at the composer center?
        try:
            info = page.evaluate(
                """() => {
                    const el = document.querySelector('#prompt-textarea');
                    if (!el) return {found:false};
                    const r = el.getBoundingClientRect();
                    const cx = r.left + r.width/2, cy = r.top + r.height/2;
                    const top = document.elementFromPoint(cx, cy);
                    const dialogs = document.querySelectorAll('[role=dialog],[aria-modal=true]');
                    const dlist = Array.from(dialogs).slice(0,5).map(d => (d.getAttribute('data-testid')||d.className||d.tagName).toString().slice(0,80));
                    return {
                        found:true,
                        topTag: top ? top.tagName : null,
                        topTestid: top ? top.getAttribute('data-testid') : null,
                        topClass: top ? (top.className||'').toString().slice(0,120) : null,
                        composerContainsTop: el.contains(top),
                        dialogCount: dialogs.length,
                        dialogs: dlist,
                    };
                }"""
            )
            print("ELEMENT_AT_CENTER:", red(info))
        except Exception as exc:  # noqa: BLE001
            print("evaluate ERROR:", type(exc).__name__, red(exc))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
