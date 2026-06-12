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


@dataclass(slots=True)
class Turn:
    role: str
    text: str
    turn_id: str
    complete: bool = True
    streaming: bool = False

    def as_json(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "turn_id": self.turn_id,
            "complete": self.complete,
            "streaming": self.streaming,
        }


@dataclass(slots=True)
class Conversation:
    conversation_ref: str
    title: str
    turns: list[Turn] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "conversation_ref": self.conversation_ref,
            "title": self.title,
            "turns": [turn.as_json() for turn in self.turns],
        }


@dataclass(slots=True)
class NextScript:
    text: str
    conversation_ref: str | None = None
    streaming: bool = False
    complete: bool = True
    failure_mode: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "conversation_ref": self.conversation_ref,
            "streaming": self.streaming,
            "complete": self.complete,
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

    def reset(self) -> None:
        with self._lock:
            self._conversations.clear()
            self._conversation_counter = 0
            self._turn_counter = 0
            self._selected_ref = None
            self._last_prompt = None
            self._next_script = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "conversations": {
                    ref: conversation.as_json()
                    for ref, conversation in self._conversations.items()
                },
                "conversation_refs": list(self._conversations),
                "selected_conversation_ref": self._selected_ref,
                "last_prompt": self._last_prompt,
                "next_script": self._next_script.as_json() if self._next_script else None,
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

    def set_next_script(self, payload: dict[str, Any]) -> NextScript:
        if "text" not in payload:
            raise ValueError("text is required")
        text = str(payload["text"])
        raw_ref = payload.get("conversation_ref")
        conversation_ref = None if raw_ref in (None, "") else self._validate_ref(str(raw_ref))
        core_keys = {"text", "conversation_ref", "streaming", "complete", "failure_mode", "failure", "mode"}
        script = NextScript(
            text=text,
            conversation_ref=conversation_ref,
            streaming=_as_bool(payload.get("streaming"), default=False),
            complete=_as_bool(payload.get("complete"), default=True),
            failure_mode=_optional_str(payload.get("failure_mode") or payload.get("failure") or payload.get("mode")),
            extra={key: value for key, value in payload.items() if key not in core_keys},
        )
        with self._lock:
            self._next_script = script
        return script

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
                assistant_text = f"[mock] you said: {prompt}"
            else:
                assistant_text = script.text
                self._next_script = None

            # CORE always renders completed assistant turns immediately. The
            # script's requested streaming/complete/failure fields are accepted
            # and exposed through inspect() before consumption for T4 reuse.
            conversation.turns.append(
                Turn("assistant", assistant_text, self._next_turn_id(), complete=True, streaming=False)
            )
            return conversation_ref

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


def _render_turns(conversation: dict[str, Any] | None) -> str:
    if conversation is None:
        return ""
    ref = escape(str(conversation["conversation_ref"]), quote=True)
    rendered = []
    for turn in conversation["turns"]:
        role = escape(str(turn["role"]), quote=True)
        turn_id = escape(str(turn["turn_id"]), quote=True)
        body = escape(str(turn["text"]))
        markers = ""
        if turn["role"] == "assistant":
            if turn.get("streaming"):
                markers += '<span data-testid="assistant-streaming" aria-label="Assistant streaming">Streaming</span>'
            if turn.get("complete"):
                markers += '<span data-testid="assistant-turn-complete" aria-label="Assistant turn complete">Complete</span>'
        rendered.append(
            '<article data-testid="mock-turn" '
            f'data-message-author-role="{role}" data-turn-id="{turn_id}" data-conversation-ref="{ref}">'
            f'<div data-testid="mock-message-body">{body}</div>{markers}</article>'
        )
    return "\n".join(rendered)


def _render_page(snapshot: dict[str, Any]) -> str:
    conversation = _selected_conversation(snapshot)
    selected_ref = "" if conversation is None else str(conversation["conversation_ref"])
    selected_attr = escape(selected_ref, quote=True)
    chat_list = _render_chat_list(snapshot)
    turns = _render_turns(conversation)
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
    [data-testid="mock-turn"] {{ border: 1px solid #bbb; margin: 0.5rem 0; padding: 0.5rem; }}
  </style>
</head>
<body>
<main data-testid="mock-ready-root" data-conversation-ref="{selected_attr}">
  <h1>Mock ChatGPT</h1>
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
        <option data-testid="mock-model-option" value="mock-default" selected>Mock default</option>
        <option data-testid="mock-model-option" value="mock-reasoning">Mock reasoning</option>
      </select>
    </label>
  </section>
  <section data-testid="mock-turn-list" aria-label="Conversation turns">
    {turns}
  </section>
  <form data-testid="mock-composer-form" action="/__send__" method="post">
    <input type="hidden" name="conversation_ref" value="{selected_attr}">
    <label>Message
      <textarea data-testid="mock-composer" name="prompt" aria-label="Message composer"></textarea>
    </label>
    <button data-testid="mock-send-button" type="submit">Send</button>
  </form>
</main>
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
                    state.select_or_create(ref)
                    status, body, content_type = _html_bytes(_render_page(state.snapshot()))
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
                    script = state.set_next_script(payload)
                    status, body, content_type = _json_bytes({"ok": True, "next_script": script.as_json()})
                    self._send(status, body, content_type)
                elif path == "/__new_chat__":
                    ref = state.create_conversation()
                    self._redirect(f"/c/{quote(ref)}")
                elif path == "/__send__":
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
