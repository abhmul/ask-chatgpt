#!/usr/bin/env python3
"""Attended read-only M6-T3 attachment byte-route probe.

Uses one own ChatGPT tab, observes the target conversation request to acquire the web
app header NAMES/values in memory, then performs read-only in-page GET/HEAD probes.
The JSON printed by this script is sanitized: no header values, file ids, filenames,
conversation text, signed URLs, or response bodies are emitted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

# Allow importing the sibling offline enumerator when this file is executed as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_attachment_enumerate import (  # noqa: E402
    KINDS,
    _scheme_or_prefix,
    enumerate_refs,
    representative_refs,
)

from ask_chatgpt.capture import REQUIRED_CAPTURE_HEADERS, acquire_backend_headers  # noqa: E402
from ask_chatgpt.channels.cdp import CdpChannel  # noqa: E402
from ask_chatgpt.identity import parse_conversation_address  # noqa: E402

TARGET_ID = "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"
FILE_TOKEN_RE = re.compile(r"file[-_][A-Za-z0-9_-]+")


def _json_keys(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return sorted(str(key) for key in value.keys())
    if isinstance(value, list):
        return ["<list>"]
    if value is None:
        return []
    return [f"<{type(value).__name__}>"]


def _loads_json_safely(body: bytes | None) -> Any | None:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001 - never print response bodies.
        return None


def _find_allowed_url(value: Any) -> str | None:
    if isinstance(value, str):
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme in {"http", "https"} and (
            host == "oaiusercontent.com"
            or host.endswith(".oaiusercontent.com")
            or host == "chatgpt.com"
            or host.endswith(".chatgpt.com")
            or host == "openai.com"
            or host.endswith(".openai.com")
        ):
            return value
        return None
    if isinstance(value, Mapping):
        for key in ("download_url", "url", "downloadUrl"):
            found = _find_allowed_url(value.get(key))
            if found:
                return found
        for nested in value.values():
            found = _find_allowed_url(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_allowed_url(item)
            if found:
                return found
    return None


def _safe_host(url: str | None) -> str | None:
    if not url:
        return None
    return (urlsplit(url).hostname or "").lower() or None


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return str(value)
    return None


def _fetch_json(tab: Any, url: str, headers: Mapping[str, str], *, timeout_s: float = 20.0) -> dict[str, Any]:
    try:
        result = tab.channel.fetch_in_page(tab, url, method="GET", headers=headers, timeout_s=timeout_s)
    except Exception:  # noqa: BLE001 - exception may contain sensitive URLs; do not emit it.
        return {"status": None, "fetch_error": "FETCH_FAILED", "json_keys": [], "download_host": None}
    parsed = _loads_json_safely(result.body_bytes)
    found_url = _find_allowed_url(parsed)
    return {
        "status": result.status,
        "content_type": _header_value(result.headers, "content-type"),
        "json_keys": _json_keys(parsed),
        "download_host": _safe_host(found_url),
        "_download_url": found_url,
    }


def _probe_head_credentials_omit(tab: Any, signed_url: str) -> dict[str, Any]:
    try:
        meta = tab.channel.evaluate(
            tab,
            """
            async ({url, timeoutMs}) => {
              const controller = new AbortController();
              const timer = setTimeout(() => controller.abort(), timeoutMs);
              try {
                const response = await fetch(url, {method: 'HEAD', credentials: 'omit', cache: 'no-store', signal: controller.signal});
                return {status: response.status, headers: Object.fromEntries(response.headers.entries())};
              } finally {
                clearTimeout(timer);
              }
            }
            """,
            arg={"url": signed_url, "timeoutMs": 20000},
        )
    except Exception:  # noqa: BLE001 - never emit signed URL/error text.
        return {"method": "HEAD", "credentials": "omit", "status": None, "fetch_error": "FETCH_FAILED"}
    headers = meta.get("headers") if isinstance(meta, Mapping) else {}
    return {
        "method": "HEAD",
        "credentials": "omit",
        "status": meta.get("status") if isinstance(meta, Mapping) else None,
        "content_type": _header_value(headers, "content-type") if isinstance(headers, Mapping) else None,
        "content_length": _header_value(headers, "content-length") if isinstance(headers, Mapping) else None,
    }


def _probe_bytes(tab: Any, signed_url: str | None) -> dict[str, Any] | None:
    if not signed_url:
        return None
    host = _safe_host(signed_url)
    omit_probe = _probe_head_credentials_omit(tab, signed_url)
    # Do not send backend auth headers to the signed URL. credentials: include is
    # part of the channel's fetch implementation, but no auth/oai header values are supplied.
    for method, headers in (("HEAD", {}), ("GET", {"range": "bytes=0-0"})):
        try:
            result = tab.channel.fetch_in_page(tab, signed_url, method=method, headers=headers, timeout_s=20.0)
        except Exception:  # noqa: BLE001 - never emit signed URL/error text.
            continue
        return {
            "method": method,
            "request_header_names": sorted(headers.keys()),
            "status": result.status,
            "download_host": host,
            "content_type": _header_value(result.headers, "content-type"),
            "content_length": _header_value(result.headers, "content-length"),
            "content_range_present": _header_value(result.headers, "content-range") is not None,
            "backend_auth_headers_supplied": False,
            "credentials_omit_probe": omit_probe,
            "pre_signed_without_cookies": omit_probe.get("status") in {200, 206},
        }
    return {
        "method": "HEAD_then_GET_range",
        "request_header_names": ["range"],
        "status": None,
        "download_host": host,
        "fetch_error": "FETCH_FAILED",
        "backend_auth_headers_supplied": False,
        "credentials_omit_probe": omit_probe,
        "pre_signed_without_cookies": omit_probe.get("status") in {200, 206},
    }


def _file_route(tab: Any, file_id: str, backend_headers: Mapping[str, str]) -> dict[str, Any]:
    escaped = quote(file_id, safe="")
    fetch_headers = {"accept": "application/json", **backend_headers}
    download_json = _fetch_json(tab, f"/backend-api/files/{escaped}/download", fetch_headers)
    byte_probe = _probe_bytes(tab, download_json.get("_download_url") if isinstance(download_json.get("_download_url"), str) else None)
    download_json.pop("_download_url", None)
    metadata_json = _fetch_json(tab, f"/backend-api/files/{escaped}", fetch_headers)
    metadata_json.pop("_download_url", None)
    return {
        "download_endpoint": {
            "method": "GET",
            "endpoint_template": "/backend-api/files/<file_id>/download",
            "request_header_names": sorted(fetch_headers.keys()),
            **download_json,
        },
        "metadata_endpoint": {
            "method": "GET",
            "endpoint_template": "/backend-api/files/<file_id>",
            "request_header_names": sorted(fetch_headers.keys()),
            **metadata_json,
        },
        "byte_probe": byte_probe,
        "download_url_pre_signed_without_backend_headers": bool(byte_probe and byte_probe.get("status") in {200, 206} and not byte_probe.get("backend_auth_headers_supplied")),
        "download_url_pre_signed_without_cookies": bool(byte_probe and byte_probe.get("pre_signed_without_cookies")),
    }


def _encoded_pointer_route(tab: Any, pointer: str, backend_headers: Mapping[str, str]) -> dict[str, Any]:
    escaped = quote(pointer, safe="")
    fetch_headers = {"accept": "application/json", **backend_headers}
    download_json = _fetch_json(tab, f"/backend-api/files/{escaped}/download", fetch_headers)
    byte_probe = _probe_bytes(tab, download_json.get("_download_url") if isinstance(download_json.get("_download_url"), str) else None)
    download_json.pop("_download_url", None)
    return {
        "download_endpoint": {
            "method": "GET",
            "endpoint_template": "/backend-api/files/<urlencoded_pointer>/download",
            "request_header_names": sorted(fetch_headers.keys()),
            **download_json,
        },
        "byte_probe": byte_probe,
        "download_url_pre_signed_without_backend_headers": bool(byte_probe and byte_probe.get("status") in {200, 206} and not byte_probe.get("backend_auth_headers_supplied")),
        "download_url_pre_signed_without_cookies": bool(byte_probe and byte_probe.get("pre_signed_without_cookies")),
    }


def _route_for_ref(tab: Any, kind: str, source_ref: str, backend_headers: Mapping[str, str]) -> dict[str, Any]:
    shape = _scheme_or_prefix(source_ref)
    result: dict[str, Any] = {"source_ref_format": shape}
    if kind in {"user_upload", "file_reference"}:
        result["strategy"] = "source_ref_as_file_id"
        result.update(_file_route(tab, source_ref, backend_headers))
        return result
    if kind == "code_execution_output":
        result["strategy"] = "run_id_as_file_id_fail_closed_probe"
        result.update(_file_route(tab, source_ref, backend_headers))
        return result
    if kind == "generated_asset":
        if source_ref.startswith("file-service://"):
            result["strategy"] = "file_service_pointer_payload_as_file_id"
            result.update(_file_route(tab, source_ref.removeprefix("file-service://"), backend_headers))
            return result
        matches = FILE_TOKEN_RE.findall(source_ref)
        if matches:
            result["strategy"] = "embedded_file_token_from_pointer"
            result.update(_file_route(tab, matches[0], backend_headers))
            if not result.get("byte_probe") or result.get("download_endpoint", {}).get("status") not in {200, 201, 202}:
                result["encoded_pointer_fallback"] = _encoded_pointer_route(tab, source_ref, backend_headers)
            return result
        result["strategy"] = "urlencoded_pointer_as_file_id_fail_closed_probe"
        result.update(_encoded_pointer_route(tab, source_ref, backend_headers))
        return result
    result["strategy"] = "unsupported_kind"
    return result


def _page_blocker_state(tab: Any) -> dict[str, bool]:
    raw = tab.channel.evaluate(
        tab,
        """
        () => {
          const title = document.title || '';
          const body = document.body ? (document.body.innerText || '') : '';
          const path = location.pathname || '';
          return {
            cloudflare: title.includes('Just a moment') || body.includes('Just a moment'),
            login: path.includes('/auth') || !!document.querySelector('input[type=password], input[name=email], input[name=username]')
          };
        }
        """,
    )
    if not isinstance(raw, Mapping):
        return {"cloudflare": False, "login": False}
    return {"cloudflare": bool(raw.get("cloudflare")), "login": bool(raw.get("login"))}


def _safe_stop_playwright(channel: CdpChannel) -> None:
    # Avoid CdpChannel.detach()/browser.close() ambiguity for a shared remote browser.
    playwright = getattr(channel, "_playwright", None)
    setattr(channel, "_context", None)
    setattr(channel, "_browser", None)
    setattr(channel, "_playwright", None)
    if playwright is not None:
        try:
            playwright.stop()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only attended probe for M6-T3 attachment byte routes.")
    parser.add_argument("--conversation", default=TARGET_ID)
    parser.add_argument("--raw-mapping", type=Path, default=Path(f"cache/conversations/{TARGET_ID}/raw-mapping.json"))
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    parser.add_argument("--scope", choices=("current-branch", "all-mapping"), default="current-branch")
    args = parser.parse_args()

    if args.conversation != TARGET_ID:
        raise SystemExit("Refusing to read any conversation except the authorized target")
    conv = parse_conversation_address(args.conversation)
    if conv is None or conv.conversation_id != TARGET_ID:
        raise SystemExit("Authorized target parse failed")

    refs, node_count = enumerate_refs(args.raw_mapping, scope=args.scope)
    reps = representative_refs(refs)

    channel = CdpChannel(cdp_endpoint=args.cdp_endpoint)
    preflight = channel.preflight(timeout_s=5.0)
    if not preflight.ok:
        print(json.dumps({"status": "CDP_UNREACHABLE", "browser_alive_before": False}, sort_keys=True))
        return 2

    tab = None
    started = time.monotonic()
    try:
        channel.attach()
        tab = channel.open_tab(conv.url)
        blockers = _page_blocker_state(tab)
        if blockers.get("cloudflare") or blockers.get("login"):
            print(
                json.dumps(
                    {
                        "status": "HUMAN-ACTION-NEEDED",
                        "browser_alive_before": True,
                        "blocker": "cloudflare" if blockers.get("cloudflare") else "login",
                    },
                    sort_keys=True,
                )
            )
            return 3
        bundle = acquire_backend_headers(tab, conv, timeout_s=30.0)
        backend_headers = dict(bundle.for_single_fetch())
        findings: dict[str, Any] = {}
        for kind in KINDS:
            rep = reps.get(kind)
            if not rep or not rep.get("source_ref"):
                findings[kind] = {"present": False, "probed": False}
                continue
            findings[kind] = {
                "present": True,
                "probed": True,
                **_route_for_ref(tab, kind, str(rep["source_ref"]), backend_headers),
            }
        output = {
            "status": "DONE",
            "browser_alive_before": True,
            "conversation_target_checked": True,
            "scope": args.scope,
            "node_count": node_count,
            "header_names_observed": sorted(REQUIRED_CAPTURE_HEADERS),
            "source_kinds_probed": [kind for kind in KINDS if kind in reps],
            "findings": findings,
            "elapsed_s": round(time.monotonic() - started, 3),
        }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    finally:
        if tab is not None:
            try:
                channel.close_tab(tab)
            except Exception:
                pass
        _safe_stop_playwright(channel)


if __name__ == "__main__":
    raise SystemExit(main())
