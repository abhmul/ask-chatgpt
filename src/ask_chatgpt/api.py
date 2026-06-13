"""Public ask_chatgpt API wiring registry, browser session, and response readers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from ask_chatgpt.bundle import build_bundle, generate_prompt_instructions, upload_bundle
from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import AskChatGPTError
from ask_chatgpt.patch import PatchBundle, retrieve_patch_bundle
from ask_chatgpt.readers import ResponseReader, read_response
from ask_chatgpt.session_registry import ConversationRef, SessionRegistry

Pathish = str | Path


@dataclass(frozen=True, slots=True)
class AskChatGPTResult:
    """UC2 response text plus an opaque unapplied patch-bundle handle."""

    text: str
    patch_bundle: PatchBundle | None


def ask_chatgpt(
    prompt: str,
    *,
    session_identifier: str | None = None,
    model_settings: dict[str, Any] | None = None,
    channel: str = "real",
    base_url: str | None = None,
    profile_path: str | Path | None = None,
    cdp_endpoint: str | None = None,
    registry: SessionRegistry | None = None,
    reader_order: Iterable[ResponseReader] | None = None,
    timeout_s: float = 30.0,
    files: Sequence[Pathish] | None = None,
    dirs: Sequence[Pathish] | None = None,
    bundle_root: str | Path | None = None,
) -> str | AskChatGPTResult:
    """Send ``prompt`` to ChatGPT and return text, or a UC2 result when bundling files.

    The default ``channel="real"`` is for operator-gated product use. Tests and scripted acceptance pass ``channel="mock"`` with a loopback ``base_url``. When no non-empty ``files`` or ``dirs`` are supplied, the UC1 plain-``str`` behavior is preserved.
    """

    if not _has_non_empty_paths(files) and not _has_non_empty_paths(dirs):
        resolved_registry = SessionRegistry() if registry is None else registry
        stored_ref = resolved_registry.get(session_identifier) if session_identifier is not None else None
        conversation_ref = stored_ref.conversation_ref if stored_ref is not None else None

        with BrowserSession(channel=channel, base_url=base_url, profile_path=profile_path, cdp_endpoint=cdp_endpoint) as session:
            active_ref = session.open_or_create_conversation(conversation_ref)
            session.select_model(model_settings)
            session.send_prompt(str(prompt))
            turn = session.wait_for_completion(timeout_s=timeout_s)
            if session.page is None:
                raise AskChatGPTError("Browser page is unavailable after completion. Operator action: retry or inspect the browser session.")
            session.refresh_active_conversation_ref()
            text = read_response(turn, session.page, session.selectors, order=reader_order)

            if session_identifier is not None:
                active_ref = session.active_conversation_ref or active_ref
                if active_ref:
                    resolved_registry.set(
                        session_identifier,
                        ConversationRef(
                            conversation_ref=active_ref,
                            url=session.page.url,
                            model_settings=deepcopy(model_settings),
                        ),
                    )
            return text

    return _ask_chatgpt_with_bundle(
        prompt,
        session_identifier=session_identifier,
        model_settings=model_settings,
        channel=channel,
        base_url=base_url,
        profile_path=profile_path,
        cdp_endpoint=cdp_endpoint,
        registry=registry,
        reader_order=reader_order,
        timeout_s=timeout_s,
        files=files,
        dirs=dirs,
        bundle_root=bundle_root,
    )


def _ask_chatgpt_with_bundle(
    prompt: str,
    *,
    session_identifier: str | None,
    model_settings: dict[str, Any] | None,
    channel: str,
    base_url: str | None,
    profile_path: str | Path | None,
    cdp_endpoint: str | None,
    registry: SessionRegistry | None,
    reader_order: Iterable[ResponseReader] | None,
    timeout_s: float,
    files: Sequence[Pathish] | None,
    dirs: Sequence[Pathish] | None,
    bundle_root: str | Path | None,
) -> AskChatGPTResult:
    bundle = build_bundle(files=files, dirs=dirs, root=bundle_root)
    prompt_with_instructions = generate_prompt_instructions(str(prompt), bundle_filename=bundle.filename)
    reader_sequence = tuple(reader_order) if reader_order is not None else None
    resolved_registry = SessionRegistry() if registry is None else registry
    stored_ref = resolved_registry.get(session_identifier) if session_identifier is not None else None
    conversation_ref = stored_ref.conversation_ref if stored_ref is not None else None

    with BrowserSession(channel=channel, base_url=base_url, profile_path=profile_path, cdp_endpoint=cdp_endpoint) as session:
        active_ref = session.open_or_create_conversation(conversation_ref)
        session.select_model(model_settings)
        upload_bundle(session, bundle, timeout_s=timeout_s)
        session.send_prompt(prompt_with_instructions)
        turn = session.wait_for_completion(timeout_s=timeout_s)
        if session.page is None:
            raise AskChatGPTError("Browser page is unavailable after completion. Operator action: retry or inspect the browser session.")
        text = read_response(turn, session.page, session.selectors, order=reader_sequence)
        retrieved = retrieve_patch_bundle(session, timeout_s=timeout_s, reader_order=reader_sequence)
        patch_bundle = None if retrieved is None else retrieved[1]
        session.refresh_active_conversation_ref()

        if session_identifier is not None:
            active_ref = session.active_conversation_ref or active_ref
            if active_ref:
                resolved_registry.set(
                    session_identifier,
                    ConversationRef(
                        conversation_ref=active_ref,
                        url=session.page.url,
                        model_settings=deepcopy(model_settings),
                    ),
                )
        return AskChatGPTResult(text=text, patch_bundle=patch_bundle)


def _has_non_empty_paths(value: Sequence[Pathish] | None) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, bytes, os.PathLike)):
        return os.fspath(value) != ""
    return len(value) > 0


__all__ = ["AskChatGPTResult", "Pathish", "ask_chatgpt"]
