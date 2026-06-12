"""Public ask_chatgpt API wiring registry, browser session, and response readers."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import AskChatGPTError
from ask_chatgpt.readers import ResponseReader, read_response
from ask_chatgpt.session_registry import ConversationRef, SessionRegistry


def ask_chatgpt(
    prompt: str,
    *,
    session_identifier: str | None = None,
    model_settings: dict[str, Any] | None = None,
    channel: str = "real",
    base_url: str | None = None,
    profile_path: str | Path | None = None,
    registry: SessionRegistry | None = None,
    reader_order: Iterable[ResponseReader] | None = None,
    timeout_s: float = 30.0,
) -> str:
    """Send ``prompt`` to ChatGPT and return the latest assistant response text.

    The default ``channel="real"`` is for operator-gated product use. Tests and scripted acceptance pass ``channel="mock"`` with a loopback ``base_url``.
    """

    resolved_registry = SessionRegistry() if registry is None else registry
    stored_ref = resolved_registry.get(session_identifier) if session_identifier is not None else None
    conversation_ref = stored_ref.conversation_ref if stored_ref is not None else None

    with BrowserSession(channel=channel, base_url=base_url, profile_path=profile_path) as session:
        active_ref = session.open_or_create_conversation(conversation_ref)
        session.select_model(model_settings)
        session.send_prompt(str(prompt))
        turn = session.wait_for_completion(timeout_s=timeout_s)
        if session.page is None:
            raise AskChatGPTError("Browser page is unavailable after completion. Operator action: retry or inspect the browser session.")
        text = read_response(turn, session.page, session.selectors, order=reader_order)

        if session_identifier is not None:
            active_ref = session.active_conversation_ref or active_ref
            resolved_registry.set(
                session_identifier,
                ConversationRef(
                    conversation_ref=active_ref,
                    url=session.page.url,
                    model_settings=deepcopy(model_settings),
                ),
            )
        return text


__all__ = ["ask_chatgpt"]
