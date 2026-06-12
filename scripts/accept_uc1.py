#!/usr/bin/env python3
"""Scripted UC1 acceptance against the loopback mock ChatGPT server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import traceback
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ask_chatgpt import LoginRequiredError, ask_chatgpt  # noqa: E402
from ask_chatgpt.session_registry import SessionRegistry  # noqa: E402
from tests.fixtures.mock_chatgpt import MockChatGPTServer  # noqa: E402

SESSION_ID = "accept-s1"
PROMPT_1 = "accept UC1 prompt one"
PROMPT_2 = "accept UC1 prompt two"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "step"


def _user_prompts(snapshot: dict[str, Any], conversation_ref: str) -> list[str]:
    return [
        str(turn["text"])
        for turn in snapshot["conversations"][conversation_ref]["turns"]
        if turn["role"] == "user"
    ]


def _run_step(out_dir: Path, steps: list[dict[str, Any]], name: str, func: Callable[[], dict[str, Any]]) -> None:
    print(f"STEP {name}: start", flush=True)
    try:
        data = func()
        step = {"name": name, "status": "pass", "detail": data.get("detail", "ok"), "data": data}
        print(f"STEP {name}: pass", flush=True)
    except Exception as exc:  # noqa: BLE001 - acceptance must preserve raw failure detail.
        step = {
            "name": name,
            "status": "fail",
            "detail": str(exc),
            "error_type": exc.__class__.__name__,
            "traceback": traceback.format_exc(),
        }
        print(f"STEP {name}: fail: {exc.__class__.__name__}: {exc}", flush=True)
    (out_dir / f"{_safe_name(name)}.json").write_text(json.dumps(step, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    steps.append(step)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="artifact output directory")
    args = parser.parse_args(argv)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    steps: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    registry = SessionRegistry(store_path=out_dir / "sessions.json")
    server = MockChatGPTServer().start()
    try:
        handle = server.make_handle()
        handle.reset()
        print(f"artifact_dir={out_dir}", flush=True)
        print(f"mock_base_url={handle.base_url}", flush=True)
        print(f"mock_port={handle.port}", flush=True)

        def first_call() -> dict[str, Any]:
            expected = "accept UC1 answer one"
            handle.script_next_response(expected)
            text = ask_chatgpt(
                PROMPT_1,
                session_identifier=SESSION_ID,
                channel="mock",
                base_url=handle.base_url,
                registry=registry,
                timeout_s=5,
            )
            if text != expected:
                raise AssertionError(f"unexpected first response: {text!r}")
            ref = registry.get(SESSION_ID)
            if ref is None:
                raise AssertionError("registry did not store first session mapping")
            context["s1_ref"] = ref.conversation_ref
            return {"detail": "first same-session call returned scripted text", "returned_text": text, "conversation_ref": ref.conversation_ref}

        def second_call_continuity() -> dict[str, Any]:
            expected = "accept UC1 answer two"
            handle.script_next_response(expected)
            text = ask_chatgpt(
                PROMPT_2,
                session_identifier=SESSION_ID,
                channel="mock",
                base_url=handle.base_url,
                registry=registry,
                timeout_s=5,
            )
            if text != expected:
                raise AssertionError(f"unexpected second response: {text!r}")
            ref = registry.get(SESSION_ID)
            if ref is None:
                raise AssertionError("registry lost same-session mapping")
            if ref.conversation_ref != context.get("s1_ref"):
                raise AssertionError(f"same session id changed conversations: {context.get('s1_ref')!r} -> {ref.conversation_ref!r}")
            snapshot = handle.inspect()
            prompts = _user_prompts(snapshot, ref.conversation_ref)
            if prompts != [PROMPT_1, PROMPT_2]:
                raise AssertionError(f"same conversation does not contain both prompts in order: {prompts!r}")
            return {
                "detail": "same session id reused the same conversation",
                "returned_text": text,
                "conversation_ref": ref.conversation_ref,
                "user_prompts": prompts,
            }

        def model_settings_success() -> dict[str, Any]:
            expected = "accept UC1 model-settings answer"
            handle.script_next_response(expected)
            text = ask_chatgpt(
                "accept UC1 model settings prompt",
                session_identifier="accept-model",
                model_settings={"model": "mock-default"},
                channel="mock",
                base_url=handle.base_url,
                registry=registry,
                timeout_s=5,
            )
            if text != expected:
                raise AssertionError(f"unexpected model-settings response: {text!r}")
            ref = registry.get("accept-model")
            if ref is None or ref.model_settings != {"model": "mock-default"}:
                raise AssertionError("registry did not store model settings for model success")
            return {"detail": "available model setting succeeded", "returned_text": text, "conversation_ref": ref.conversation_ref, "model_settings": ref.model_settings}

        def honest_failure_login_required() -> dict[str, Any]:
            handle.script_next_response("unused login-required response", failure_mode="login_required")
            try:
                ask_chatgpt(
                    "accept UC1 login required prompt",
                    session_identifier="accept-login-required",
                    channel="mock",
                    base_url=handle.base_url,
                    registry=registry,
                    timeout_s=5,
                )
            except LoginRequiredError as exc:
                return {"detail": "LoginRequiredError raised as expected", "error_type": exc.__class__.__name__, "message": str(exc)}
            raise AssertionError("LoginRequiredError was not raised")

        _run_step(out_dir, steps, "same-session-call-1", first_call)
        _run_step(out_dir, steps, "same-session-call-2-continuity", second_call_continuity)
        _run_step(out_dir, steps, "model-settings-available", model_settings_success)
        _run_step(out_dir, steps, "honest-failure-login-required", honest_failure_login_required)
    finally:
        server.stop()

    overall = "pass" if all(step["status"] == "pass" for step in steps) else "fail"
    result = {"overall": overall, "steps": steps}
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"overall={overall}", flush=True)
    print(f"results_json={out_dir / 'results.json'}", flush=True)
    return 0 if overall == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
