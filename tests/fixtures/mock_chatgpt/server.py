"""Stdlib loopback mock ChatGPT web UI for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen


LOOPBACK_HOST = "127.0.0.1"
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_FAILURE_MODES = frozenset(
    {
        "login_required",
        "session_not_found",
        "model_unavailable",
        "response_truncated",
        "rate_limited",
        "selector_unavailable",
    }
)
_COPY_MODES = frozenset({"ok", "missing", "wrong", "stale", "truncated"})
_LAYOUT_VARIANTS = frozenset({"stable", "virtualized"})
_DEFAULT_STREAM_READS = 2


@dataclass(slots=True)
class Turn:
    role: str
    text: str
    turn_id: str
    complete: bool = True
    streaming: bool = False
    truncated: bool = False
    stream_reads_remaining: int = 0

    def as_json(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "turn_id": self.turn_id,
            "complete": self.complete,
            "streaming": self.streaming,
            "truncated": self.truncated,
            "stream_reads_remaining": self.stream_reads_remaining,
        }


@dataclass(slots=True)
class Conversation:
    conversation_ref: str
    title: str
    turns: list[Turn] = field(default_factory=list)
    layout_variant: str = "stable"
    copy_mode: str = "ok"

    def as_json(self) -> dict[str, Any]:
        return {
            "conversation_ref": self.conversation_ref,
            "title": self.title,
            "turns": [turn.as_json() for turn in self.turns],
            "layout_variant": self.layout_variant,
            "copy_mode": self.copy_mode,
        }


@dataclass(slots=True)
class NextScript:
    text: str
    conversation_ref: str | None = None
    streaming: bool = False
    complete: bool = True
    stream_reads: int = _DEFAULT_STREAM_READS
    failure_mode: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "conversation_ref": self.conversation_ref,
            "streaming": self.streaming,
            "complete": self.complete,
            "stream_reads": self.stream_reads,
            "failure_mode": self.failure_mode,
            "extra": dict(self.extra),
        }


class MockChatGPTState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conversations: dict[str, Conversation] = {}
        self._conversation_counter = 0
        self._turn_counter = 0
        self._selected_ref: str | None = None
        self._last_prompt: str | None = None
        self._next_script: NextScript | None = None
        self._failure_mode: str | None = None
        self._unavailable_model = "mock-reasoning"

    def reset(self) -> None:
        with self._lock:
            self._conversations.clear()
            self._conversation_counter = 0
            self._turn_counter = 0
            self._selected_ref = None
            self._last_prompt = None
            self._next_script = None
            self._failure_mode = None
            self._unavailable_model = "mock-reasoning"

    def snapshot(self, *, advance_stream_ref: str | None = None) -> dict[str, Any]:
        with self._lock:
            if advance_stream_ref is not None:
                conversation = self._conversations.get(advance_stream_ref)
                if conversation is not None:
                    self._advance_streaming_turns(conversation)
            return {
                "conversations": {
                    ref: conversation.as_json()
                    for ref, conversation in self._conversations.items()
                },
                "conversation_refs": list(self._conversations),
                "selected_conversation_ref": self._selected_ref,
                "last_prompt": self._last_prompt,
                "next_script": self._next_script.as_json() if self._next_script else None,
                "failure_mode": self._failure_mode,
                "unavailable_model": self._unavailable_model,
            }

    def create_conversation(self, conversation_ref: str | None = None) -> str:
        with self._lock:
            if conversation_ref is None:
                while True:
                    self._conversation_counter += 1
                    candidate = f"conv-{self._conversation_counter}"
                    if candidate not in self._conversations:
                        conversation_ref = candidate
                        break
            conversation_ref = self._validate_ref(conversation_ref)
            if conversation_ref not in self._conversations:
                title = f"Mock conversation {conversation_ref}"
                self._conversations[conversation_ref] = Conversation(conversation_ref, title)
            self._selected_ref = conversation_ref
            return conversation_ref

    def select_or_create(self, conversation_ref: str) -> str:
        return self.create_conversation(conversation_ref)

    def apply_script(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a /__script__ payload.

        Text-only payloads preserve the T3 behavior: they script the next send.
        Payloads with turns seed a full conversation immediately for reader tests.
        Mode-only payloads set page/failure state.
        """
        with self._lock:
            mode = _optional_str(payload.get("failure_mode") or payload.get("failure") or payload.get("mode"))
            if mode is not None:
                self._set_failure_mode_unlocked(mode, payload)

            result: dict[str, Any] = {"failure_mode": self._failure_mode}
            if "turns" in payload:
                result["seeded_conversation_ref"] = self._seed_conversation_unlocked(payload)
                return result
            if mode == "response_truncated" and "text" in payload and payload.get("conversation_ref") not in (None, ""):
                result["seeded_conversation_ref"] = self._seed_response_truncated_unlocked(payload)
                return result
            if "text" in payload:
                script = self._next_script_from_payload(payload)
                self._next_script = script
                result["next_script"] = script.as_json()
                return result
            if mode is not None:
                result["next_script"] = None
                return result
            raise ValueError("text is required")

    def set_next_script(self, payload: dict[str, Any]) -> NextScript:
        result = self.apply_script(payload)
        script = result.get("next_script")
        if not isinstance(script, dict) or self._next_script is None:
            raise ValueError("text is required")
        return self._next_script

    def append_exchange(self, prompt: str, conversation_ref: str | None) -> str:
        prompt = str(prompt)
        with self._lock:
            if conversation_ref in (None, ""):
                conversation_ref = self.create_conversation()
            else:
                conversation_ref = self._validate_ref(conversation_ref)
                if conversation_ref not in self._conversations:
                    self._conversations[conversation_ref] = Conversation(
                        conversation_ref, f"Mock conversation {conversation_ref}"
                    )
                self._selected_ref = conversation_ref

            conversation = self._conversations[conversation_ref]
            self._last_prompt = prompt
            conversation.turns.append(Turn("user", prompt, self._next_turn_id()))

            script = self._script_for(conversation_ref)
            if script is None:
                assistant_turn = Turn(
                    "assistant",
                    f"[mock] you said: {prompt}",
                    self._next_turn_id(),
                    complete=True,
                    streaming=False,
                )
            else:
                self._next_script = None
                streaming = script.streaming
                truncated = script.failure_mode == "response_truncated" or _as_bool(
                    script.extra.get("truncated", script.extra.get("response_truncated")), default=False
                )
                complete = script.complete
                stream_reads_remaining = 0
                if streaming:
                    complete = False
                    stream_reads_remaining = max(0, script.stream_reads)
                if truncated:
                    streaming = False
                    complete = False
                    stream_reads_remaining = 0
                if "layout_variant" in script.extra or "dom_variant" in script.extra:
                    conversation.layout_variant = _validated_layout_variant(
                        script.extra.get("layout_variant", script.extra.get("dom_variant"))
                    )
                if "copy_mode" in script.extra:
                    conversation.copy_mode = _validated_copy_mode(script.extra.get("copy_mode"))
                assistant_turn = Turn(
                    "assistant",
                    script.text,
                    self._next_turn_id(),
                    complete=complete,
                    streaming=streaming,
                    truncated=truncated,
                    stream_reads_remaining=stream_reads_remaining,
                )

            conversation.turns.append(assistant_turn)
            return conversation_ref

    def _next_script_from_payload(self, payload: dict[str, Any]) -> NextScript:
        if "text" not in payload:
            raise ValueError("text is required")
        raw_ref = payload.get("conversation_ref")
        conversation_ref = None if raw_ref in (None, "") else self._validate_ref(str(raw_ref))
        core_keys = {
            "text",
            "conversation_ref",
            "streaming",
            "complete",
            "stream_reads",
            "failure_mode",
            "failure",
            "mode",
        }
        return NextScript(
            text=str(payload["text"]),
            conversation_ref=conversation_ref,
            streaming=_as_bool(payload.get("streaming"), default=False),
            complete=_as_bool(payload.get("complete"), default=True),
            stream_reads=_as_int(payload.get("stream_reads"), default=_DEFAULT_STREAM_READS),
            failure_mode=_optional_str(payload.get("failure_mode") or payload.get("failure") or payload.get("mode")),
            extra={key: value for key, value in payload.items() if key not in core_keys},
        )

    def _seed_conversation_unlocked(self, payload: dict[str, Any]) -> str:
        turns = payload.get("turns")
        if not isinstance(turns, list):
            raise ValueError("turns must be a list")
        conversation_ref = self._conversation_ref_from_payload_unlocked(payload)
        conversation = self._conversations[conversation_ref]
        conversation.layout_variant = _validated_layout_variant(payload.get("layout_variant", payload.get("dom_variant")))
        conversation.copy_mode = _validated_copy_mode(payload.get("copy_mode"))
        default_stream_reads = _as_int(payload.get("stream_reads"), default=_DEFAULT_STREAM_READS)
        conversation.turns = [
            self._turn_from_payload_unlocked(turn_payload, default_stream_reads=default_stream_reads)
            for turn_payload in turns
        ]
        return conversation_ref

    def _seed_response_truncated_unlocked(self, payload: dict[str, Any]) -> str:
        conversation_ref = self._conversation_ref_from_payload_unlocked(payload)
        conversation = self._conversations[conversation_ref]
        conversation.layout_variant = _validated_layout_variant(payload.get("layout_variant", payload.get("dom_variant")))
        conversation.copy_mode = _validated_copy_mode(payload.get("copy_mode"))
        conversation.turns = [
            Turn(
                "assistant",
                str(payload.get("text") or ""),
                self._next_turn_id(),
                complete=False,
                streaming=False,
                truncated=True,
            )
        ]
        return conversation_ref

    def _conversation_ref_from_payload_unlocked(self, payload: dict[str, Any]) -> str:
        raw_ref = payload.get("conversation_ref")
        conversation_ref = self.create_conversation(None if raw_ref in (None, "") else str(raw_ref))
        self._selected_ref = conversation_ref
        return conversation_ref

    def _turn_from_payload_unlocked(self, payload: Any, *, default_stream_reads: int) -> Turn:
        if not isinstance(payload, dict):
            raise ValueError("each turn must be an object")
        role = str(payload.get("role") or "assistant")
        if role not in {"user", "assistant"}:
            raise ValueError(f"unsupported turn role: {role!r}")
        streaming = _as_bool(payload.get("streaming"), default=False)
        truncated = _as_bool(payload.get("truncated", payload.get("response_truncated")), default=False)
        complete = _as_bool(payload.get("complete"), default=not streaming)
        stream_reads = _as_int(
            payload.get("stream_reads", payload.get("stream_reads_remaining")),
            default=default_stream_reads,
        )
        stream_reads_remaining = 0
        if streaming:
            complete = False
            stream_reads_remaining = max(0, stream_reads)
        if truncated:
            streaming = False
            complete = False
            stream_reads_remaining = 0
        turn_id = str(payload.get("turn_id") or self._next_turn_id())
        return Turn(
            role,
            str(payload.get("text") or ""),
            turn_id,
            complete=complete,
            streaming=streaming,
            truncated=truncated,
            stream_reads_remaining=stream_reads_remaining,
        )

    def _set_failure_mode_unlocked(self, mode: str, payload: dict[str, Any]) -> None:
        normalized = mode.strip().lower()
        if normalized in {"normal", "none", "ok", "clear"}:
            self._failure_mode = None
            return
        if normalized not in _FAILURE_MODES:
            raise ValueError(f"unsupported failure mode: {mode}")
        self._failure_mode = normalized
        if normalized == "model_unavailable":
            self._unavailable_model = str(payload.get("unavailable_model") or "mock-reasoning")

    @staticmethod
    def _advance_streaming_turns(conversation: Conversation) -> None:
        for turn in conversation.turns:
            if turn.role != "assistant" or not turn.streaming:
                continue
            if turn.stream_reads_remaining > 0:
                turn.stream_reads_remaining -= 1
            else:
                turn.streaming = False
                turn.complete = True

    def _script_for(self, conversation_ref: str) -> NextScript | None:
        if self._next_script is None:
            return None
        if self._next_script.conversation_ref in (None, conversation_ref):
            return self._next_script
        return None

    def _next_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn-{self._turn_counter}"

    @staticmethod
    def _validate_ref(value: str) -> str:
        ref = str(value)
        if not _SAFE_REF.fullmatch(ref):
            raise ValueError(f"invalid conversation_ref: {value!r}")
        return ref


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _as_int(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected integer value, got {value!r}") from exc


def _validated_layout_variant(value: Any) -> str:
    variant = "stable" if value in (None, "") else str(value).strip().lower()
    if variant not in _LAYOUT_VARIANTS:
        raise ValueError(f"unsupported layout variant: {value!r}")
    return variant


def _validated_copy_mode(value: Any) -> str:
    mode = "ok" if value in (None, "") else str(value).strip().lower()
    if mode not in _COPY_MODES:
        raise ValueError(f"unsupported copy_mode: {value!r}")
    return mode


def _selected_conversation(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    selected = snapshot.get("selected_conversation_ref")
    if selected is None:
        return None
    return snapshot["conversations"].get(selected)


def _render_chat_list(snapshot: dict[str, Any]) -> str:
    items = []
    for ref, conversation in snapshot["conversations"].items():
        safe_ref = escape(ref, quote=True)
        title = escape(str(conversation["title"]))
        items.append(
            '<li><a data-testid="mock-chat-item" '
            f'data-conversation-ref="{safe_ref}" href="/c/{quote(ref)}">{title}</a></li>'
        )
    return "\n".join(items)


def _latest_completed_assistant_index(turns: list[dict[str, Any]]) -> int | None:
    latest: int | None = None
    for index, turn in enumerate(turns):
        if (
            turn.get("role") == "assistant"
            and turn.get("complete")
            and not turn.get("streaming")
            and not turn.get("truncated")
        ):
            latest = index
    return latest


def _copy_text_for(conversation: dict[str, Any], latest_index: int, mode: str) -> str:
    turns = conversation["turns"]
    latest_text = str(turns[latest_index]["text"])
    if mode == "ok":
        return latest_text
    if mode == "wrong":
        for index, turn in enumerate(turns):
            if index != latest_index and turn.get("role") == "assistant":
                return str(turn["text"])
        return "BOOBYTRAP-WRONG-COPY"
    if mode == "truncated":
        return latest_text[: max(1, len(latest_text) // 2)] if latest_text else ""
    return ""


def _render_markers(turn: dict[str, Any]) -> str:
    if turn.get("role") != "assistant":
        return ""
    markers = ""
    if turn.get("streaming"):
        markers += '<span data-testid="assistant-streaming" aria-label="Assistant streaming">Streaming</span>'
    if turn.get("complete"):
        markers += '<span data-testid="assistant-turn-complete" aria-label="Assistant turn complete">Complete</span>'
    if turn.get("truncated"):
        markers += '<span data-testid="assistant-truncated" aria-label="Assistant response truncated">Truncated</span>'
    return markers


def _render_copy_button(conversation: dict[str, Any], latest_index: int) -> str:
    mode = str(conversation.get("copy_mode") or "ok")
    if mode == "missing":
        return ""
    copy_text = _copy_text_for(conversation, latest_index, mode)
    mode_attr = escape(mode, quote=True)
    text_attr = escape(copy_text, quote=True)
    return (
        '<button data-testid="mock-copy-button" type="button" '
        f'data-copy-mode="{mode_attr}" data-copy-text="{text_attr}" '
        'aria-label="Copy latest assistant response">Copy</button>'
    )


def _render_turns(conversation: dict[str, Any] | None) -> str:
    if conversation is None:
        return ""
    ref = escape(str(conversation["conversation_ref"]), quote=True)
    turns = conversation["turns"]
    layout_variant = str(conversation.get("layout_variant") or "stable")
    latest_completed = _latest_completed_assistant_index(turns)
    visible_virtualized_index = latest_completed if latest_completed is not None else (len(turns) - 1 if turns else None)
    rendered = []
    for index, turn in enumerate(turns):
        role = escape(str(turn["role"]), quote=True)
        turn_id = escape(str(turn["turn_id"]), quote=True)
        if layout_variant == "virtualized" and index != visible_virtualized_index:
            rendered.append(
                '<article data-testid="mock-virtualized-placeholder" data-virtualized="true" '
                f'data-turn-id="{turn_id}" data-conversation-ref="{ref}">Virtualized older turn</article>'
            )
            continue
        body = escape(str(turn["text"]))
        markers = _render_markers(turn)
        copy_button = _render_copy_button(conversation, latest_completed) if index == latest_completed else ""
        data_layout = ' data-layout="virtualized-latest"' if layout_variant == "virtualized" else ""
        body_testid = "mock-message-content" if layout_variant == "virtualized" else "mock-message-body"
        rendered.append(
            '<article data-testid="mock-turn" '
            f'data-message-author-role="{role}" data-turn-id="{turn_id}" '
            f'data-conversation-ref="{ref}"{data_layout}>'
            f'<div data-testid="{body_testid}">{body}</div>{markers}{copy_button}</article>'
        )
    return "\n".join(rendered)


def _render_model_options(snapshot: dict[str, Any]) -> str:
    unavailable = str(snapshot.get("unavailable_model") or "") if snapshot.get("failure_mode") == "model_unavailable" else ""
    options = []
    for value, label, selected in (
        ("mock-default", "Mock default", True),
        ("mock-reasoning", "Mock reasoning", False),
    ):
        selected_attr = " selected" if selected else ""
        disabled_attr = ""
        if value == unavailable:
            disabled_attr = ' disabled data-disabled="true" aria-disabled="true"'
        options.append(
            f'<option data-testid="mock-model-option" value="{escape(value, quote=True)}"{selected_attr}{disabled_attr}>'
            f'{escape(label)}</option>'
        )
    return "\n        ".join(options)


def _render_conversation_not_found(conversation_ref: str) -> str:
    safe_ref = escape(conversation_ref, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Conversation not found</title></head>
<body>
<main data-testid="conversation-not-found" data-conversation-ref="{safe_ref}" role="alert">
  Conversation not found
</main>
</body>
</html>"""


def _render_page(snapshot: dict[str, Any]) -> str:
    conversation = _selected_conversation(snapshot)
    selected_ref = "" if conversation is None else str(conversation["conversation_ref"])
    selected_attr = escape(selected_ref, quote=True)
    failure_mode = snapshot.get("failure_mode")
    failure_attr = escape(str(failure_mode or ""), quote=True)
    chat_list = _render_chat_list(snapshot)
    turns = _render_turns(conversation)
    model_options = _render_model_options(snapshot)
    login_wall = (
        '<section data-testid="login-wall" role="alert">Login required</section>'
        if failure_mode == "login_required"
        else ""
    )
    rate_limit = (
        '<div data-testid="rate-limit" data-retry-after-seconds="60" role="status">Rate limited; retry after 60 seconds</div>'
        if failure_mode == "rate_limited"
        else ""
    )
    selector_unavailable = (
        '<div data-testid="selector-unavailable" role="alert">Required composer selector unavailable</div>'
        if failure_mode == "selector_unavailable"
        else ""
    )
    composer = ""
    if failure_mode not in {"login_required", "selector_unavailable"}:
        composer = f"""
  <form data-testid="mock-composer-form" action="/__send__" method="post">
    <input type="hidden" name="conversation_ref" value="{selected_attr}">
    <label>Message
      <textarea data-testid="mock-composer" name="prompt" aria-label="Message composer"></textarea>
    </label>
    <button data-testid="mock-send-button" type="submit">Send</button>
  </form>"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mock ChatGPT</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1rem; }}
    textarea {{ display: block; width: min(48rem, 90vw); min-height: 6rem; }}
    [data-testid="mock-chat-list"] {{ min-height: 1rem; }}
    [data-testid="mock-turn"], [data-testid="mock-virtualized-placeholder"] {{ border: 1px solid #bbb; margin: 0.5rem 0; padding: 0.5rem; }}
    [data-testid="mock-virtualized-placeholder"] {{ color: #555; font-style: italic; }}
    [data-testid="mock-copy-button"] {{ margin-left: 0.5rem; }}
  </style>
</head>
<body>
<main data-testid="mock-ready-root" data-conversation-ref="{selected_attr}" data-failure-mode="{failure_attr}">
  <h1>Mock ChatGPT</h1>
  {login_wall}
  {rate_limit}
  {selector_unavailable}
  <nav aria-label="Conversations">
    <ol data-testid="mock-chat-list">
      {chat_list}
    </ol>
    <form action="/__new_chat__" method="post">
      <button data-testid="mock-new-chat-button" type="submit">New chat</button>
    </form>
  </nav>
  <section aria-label="Model">
    <label>Model
      <select data-testid="mock-model-menu" name="model">
        {model_options}
      </select>
    </label>
  </section>
  <section data-testid="mock-turn-list" aria-label="Conversation turns">
    {turns}
  </section>{composer}
</main>
<script>
(function () {{
  document.addEventListener('click', async function (event) {{
    const target = event.target;
    if (!(target instanceof Element)) {{ return; }}
    const button = target.closest('[data-testid="mock-copy-button"]');
    if (!button) {{ return; }}
    if (button.getAttribute('data-copy-mode') === 'stale') {{ return; }}
    if (!navigator.clipboard || !navigator.clipboard.writeText) {{ return; }}
    await navigator.clipboard.writeText(button.getAttribute('data-copy-text') || '');
  }});
}}());
</script>
</body>
</html>"""


def _json_bytes(payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, bytes, str]:
    return int(status), json.dumps(payload, sort_keys=True).encode("utf-8"), "application/json; charset=utf-8"


def _html_bytes(body: str, *, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, bytes, str]:
    return int(status), body.encode("utf-8"), "text/html; charset=utf-8"


class _LoopbackThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def _make_handler(state: MockChatGPTState) -> type[BaseHTTPRequestHandler]:
    class MockChatGPTHandler(BaseHTTPRequestHandler):
        server_version = "MockChatGPT/1"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("location", location)
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", "0")
            self.end_headers()

        def _payload(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length") or "0")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            content_type = (self.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            if content_type == "application/json":
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("JSON body must be an object")
                return value
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
            return {key: values[-1] if values else "" for key, values in parsed.items()}

        def do_GET(self) -> None:  # noqa: N802 - stdlib signature
            path = urlparse(self.path).path
            try:
                if path == "/":
                    status, body, content_type = _html_bytes(_render_page(state.snapshot()))
                elif path.startswith("/c/"):
                    ref = MockChatGPTState._validate_ref(unquote(path.removeprefix("/c/")))
                    if state.snapshot().get("failure_mode") == "session_not_found":
                        status, body, content_type = _html_bytes(
                            _render_conversation_not_found(ref), status=HTTPStatus.NOT_FOUND
                        )
                    else:
                        state.select_or_create(ref)
                        status, body, content_type = _html_bytes(_render_page(state.snapshot(advance_stream_ref=ref)))
                elif path == "/__inspect__":
                    status, body, content_type = _json_bytes(state.snapshot())
                elif path == "/favicon.ico":
                    status, body, content_type = int(HTTPStatus.NO_CONTENT), b"", "text/plain; charset=utf-8"
                else:
                    status, body, content_type = _json_bytes({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                status, body, content_type = _json_bytes({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            self._send(status, body, content_type)

        def do_POST(self) -> None:  # noqa: N802 - stdlib signature
            path = urlparse(self.path).path
            try:
                payload = self._payload()
                if path == "/__reset__":
                    state.reset()
                    status, body, content_type = _json_bytes({"ok": True, "state": state.snapshot()})
                    self._send(status, body, content_type)
                elif path == "/__script__":
                    result = state.apply_script(payload)
                    status, body, content_type = _json_bytes({"ok": True, **result})
                    self._send(status, body, content_type)
                elif path == "/__new_chat__":
                    ref = state.create_conversation()
                    self._redirect(f"/c/{quote(ref)}")
                elif path == "/__send__":
                    if state.snapshot().get("failure_mode") == "rate_limited":
                        status, body, content_type = _html_bytes(_render_page(state.snapshot()))
                        self._send(status, body, content_type)
                    else:
                        prompt = str(payload.get("prompt") or payload.get("prompt_text") or payload.get("text") or "")
                        ref_value = payload.get("conversation_ref")
                        ref = None if ref_value in (None, "") else str(ref_value)
                        conversation_ref = state.append_exchange(prompt, ref)
                        self._redirect(f"/c/{quote(conversation_ref)}")
                else:
                    status, body, content_type = _json_bytes({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
                    self._send(status, body, content_type)
            except (ValueError, json.JSONDecodeError) as exc:
                status, body, content_type = _json_bytes({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                self._send(status, body, content_type)

    return MockChatGPTHandler


class MockChatGPTServer:
    """Loopback-only ephemeral-port mock ChatGPT server."""

    def __init__(self, *, host: str = LOOPBACK_HOST) -> None:
        if host != LOOPBACK_HOST:
            raise ValueError("mock ChatGPT server binds 127.0.0.1 only")
        self.host = host
        self.requested_port = 0
        self.state = MockChatGPTState()
        self._server: _LoopbackThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int | None = None

    @property
    def base_url(self) -> str:
        if self.port is None:
            raise RuntimeError("mock ChatGPT server is not started")
        return f"http://{self.host}:{self.port}"

    def url(self, path: str = "/") -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def start(self) -> MockChatGPTServer:
        if self._server is not None:
            return self
        handler = _make_handler(self.state)
        server = _LoopbackThreadingHTTPServer((self.host, self.requested_port), handler)
        bound_host, bound_port = server.server_address[:2]
        if bound_host != LOOPBACK_HOST or int(bound_port) == 0:
            server.server_close()
            raise RuntimeError("mock ChatGPT server failed to bind loopback ephemeral port")
        self._server = server
        self.port = int(bound_port)
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.05},
            name="mock-chatgpt-server",
            daemon=False,
        )
        self._thread = thread
        thread.start()
        self._wait_until_accepting()
        return self

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("mock ChatGPT server thread did not stop")

    def _wait_until_accepting(self, *, timeout_seconds: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            try:
                with urlopen(self.url("/__inspect__"), timeout=0.5) as response:
                    if response.status == HTTPStatus.OK:
                        return
            except (OSError, URLError) as exc:
                last_error = exc
                time.sleep(0.025)
        self.stop()
        raise RuntimeError("mock ChatGPT server did not become ready") from last_error

    def make_handle(self) -> MockChatGPTHandle:
        if self.port is None:
            raise RuntimeError("mock ChatGPT server is not started")
        return MockChatGPTHandle(
            base_url=self.base_url,
            host=self.host,
            port=self.port,
            requested_port=self.requested_port,
        )

    def __enter__(self) -> MockChatGPTServer:
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()


@dataclass(frozen=True, slots=True)
class MockChatGPTHandle:
    """HTTP control-plane wrapper returned by the pytest fixture."""

    base_url: str
    host: str
    port: int
    requested_port: int = 0

    def reset(self) -> None:
        self._request("POST", "/__reset__", {})

    def inspect(self) -> dict[str, Any]:
        return self._request("GET", "/__inspect__")

    def script_next_response(
        self,
        text: str,
        *,
        conversation_ref: str | None = None,
        streaming: bool = False,
        complete: bool = True,
        **failure_fields: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "text": text,
            "conversation_ref": conversation_ref,
            "streaming": streaming,
            "complete": complete,
        }
        payload.update(failure_fields)
        self._request("POST", "/__script__", payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"accept": "application/json"}
        if data is not None:
            headers["content-type"] = "application/json"
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"mock ChatGPT control request failed: {exc.code} {body}") from exc
        if not raw:
            return {}
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("mock ChatGPT control response was not a JSON object")
        return value


__all__ = ["LOOPBACK_HOST", "MockChatGPTHandle", "MockChatGPTServer"]
