STATUS: DONE
Produced the Lens 5 design for CLI verbs, loop ergonomics, named errors, status JSON, and atomic/persistent Session wiring.
Key decisions: the CLI is thin; `ask`/`scrape` stdout is payload-only and never suppressed by `--out`; `loop` emits one JSONL turn envelope per iteration; all browser verbs use CDP attach with tool-owned tabs only.
Blockers: none for design; project `create`, authenticated attachment byte-download endpoints, and the final default no-activity timeout value remain explicit open questions.

# 1. Verb surface

## 1.1 Common CLI contract

Entrypoint: `ask-chatgpt <verb> ...`. The implementation should use a thin parser layer (`argparse` is sufficient; no CLI framework requirement) whose handlers do only argument normalization, `Session` construction, output formatting, and exception-to-exit-code mapping. Core behavior lives in the library (`Session`, store, capture, send, completion). This follows the library-core + thin CLI architecture in REWRITE-SPEC §2/§3/§4.

Common options used by browser verbs unless a verb says otherwise: `--data-dir PATH` defaults to `$ASK_CHATGPT_DATA_DIR` or `~/.local/state/ask-chatgpt/` (REWRITE-SPEC §8); `--cdp-endpoint URL` defaults to `http://127.0.0.1:9222` (REWRITE-SPEC §13); `--selector-channel real|mock` defaults to `real` for CDP and `mock` for tests (REWRITE-SPEC §14); `--json` is reserved for commands with structured stdout (`status`, and optionally `create`/`fetch`). Diagnostics/progress always go to stderr, never stdout, so stdout remains payload/machine output.

Conversation arguments accept: a full plain URL `https://chatgpt.com/c/<conversation_id>`, a project URL `https://chatgpt.com/g/g-p-<project_id>/c/<chat_id>`, a bare conversation id, or an alias in `index.json`. Canonical identity is always the conversation id/chat id; `project_id` is metadata and routing context (REWRITE-SPEC §9; M2 handoff says project behavior was deferred and must be confirmed in M5).

All user-supplied URLs are normalized through `identity.parse_conversation_ref(...)` and then checked with `allowlist.assert_allowed_url(...)` before any browser navigation or download. Allowed domains are chatgpt.com/openai.com/auth/oaiusercontent-family domains only; violations raise `DisallowedDomainError` (REWRITE-SPEC §13; charter safety invariants).

No command may persist or log the web-app `Authorization` bearer token or OAI headers. Capture code may obtain them transiently from the page's own request and forward them for the single backend fetch; errors and status reports must redact header names/values that could identify secrets (M2 handoff; common constraints §2/§3).

Real selector map entries required by CLI-visible browser actions/status checks are exactly the M2-observed selectors below; they belong in `selectors/real.json` and are fail-closed (M2 handoff):

```json
{
  "composer": "#prompt-textarea",
  "tools_button": "button[data-testid=\"composer-plus-btn\"]",
  "message_turn": "[data-message-id][data-message-author-role]",
  "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
  "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
  "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
  "stop_button": "button[data-testid=\"stop-button\"], #composer-submit-button[aria-label*=\"Stop\" i]",
  "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button",
  "model_picker_heuristic": "composer-footer button[aria-haspopup=\"menu\"] showing the current-model label; enumerate Radix portal options by label"
}
```

The model/tools menus are label-driven Radix menus: open the trigger, enumerate `[data-radix-popper-content-wrapper]`, select exact visible labels, then verify reflected UI state before sending; do not open `Recent files` or `Projects` submenus merely for enumeration because M2 flagged private-name leak risk (M2 handoff; REWRITE-SPEC §11).

## 1.2 Library signatures the CLI calls

The CLI maps verbs to these library contracts. Types are design-level but concrete enough for M4/M5 implementation.

```python
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class ConversationRef:
    conversation_id: str | None
    url: str
    project_id: str | None = None
    alias: str | None = None
    is_draft: bool = False

@dataclass(frozen=True)
class AskResult:
    conversation_id: str
    conversation_url: str
    project_id: str | None
    user_message_id: str
    assistant_message_id: str | None
    content_markdown: str
    status: Literal["complete", "partial", "error"]
    partial: bool
    capture_method: Literal["backend", "copy_button", "katex_annotation", "dom_text"]
    model: dict[str, str | None]
    active_tools: list[str]
    attachments: list[dict]
    citations: list[dict]
    transcript_path: Path
    raw_mapping_path: Path | None

@dataclass(frozen=True)
class ScrapeResult:
    conversation_id: str
    conversation_url: str
    markdown: str
    turns_written: int
    mapping_nodes: int | None
    current_branch_nodes: int | None
    pending_attachments: int
    transcript_path: Path
    raw_mapping_path: Path | None
    export_path: Path | None
    capture_method: Literal["backend", "copy_button", "katex_annotation", "dom_text"]

@dataclass(frozen=True)
class FetchResult:
    conversation_id: str
    attachment_ref: str
    local_path: Path
    bytes: int | None
    sha256: str | None
    already_present: bool

@dataclass(frozen=True)
class StatusReport:
    schema_version: int
    ok: bool
    generated_at: str
    global_status: dict
    conversation: dict | None

class Session:
    def __init__(self, *, cdp_endpoint: str = "http://127.0.0.1:9222", data_dir: Path | None = None, selector_channel: str = "real", channel: Literal["cdp", "mock"] = "cdp") -> None: ...
    def __enter__(self) -> "Session": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...  # detach only; never quit browser
    def create(self, *, project: str | None = None) -> ConversationRef: ...
    def ask(self, conv_or_url: str | ConversationRef | None, prompt: str, *, model: str | None = None, tools: Sequence[str] = (), attach: Sequence[Path] = (), project: str | None = None, timeout_s: float | None = None, max_total_wait_s: float | None = None) -> AskResult: ...
    def scrape(self, conv_or_url: str | ConversationRef, *, with_attachments: bool = False) -> ScrapeResult: ...
    def history(self, conv_or_url: str | ConversationRef) -> str: ...  # store-only, no browser
    def fetch(self, conv_or_url: str | ConversationRef, attachment_ref: str) -> FetchResult: ...
    def loop(self, conv_or_url: str | ConversationRef, *, message: str, max_iterations: int | None = None, timeout_s: float | None = None, max_total_wait_s: float | None = None) -> Iterator[AskResult]: ...
    def status(self, conv_or_url: str | ConversationRef | None = None, *, probe_browser: bool = True) -> StatusReport: ...
```

`timeout_s` is a no-activity window that resets on progress; `max_total_wait_s=None` means unbounded total wait. This is the gotcha #3 fix from REWRITE-SPEC §7 and common constraints §4, not a hard completion cap.

## 1.3 Verb table

| Verb | Arguments and flags | Browser | Session mapping | Stdout on success |
|---|---|---:|---|---|
| `ask <conv?> "<prompt>"` | `--model LABEL`, `--tool LABEL` repeatable, `--attach FILE` repeatable, `--project ID`, `--timeout S`, `--max-total-wait S`, `--out FILE`, `--data-dir` | yes | `Session.ask(...)` | canonical markdown for the new assistant turn |
| `create` | `--project ID`, `--data-dir`, optional `--json` | yes | `Session.create(...)` | URL/id line, or JSON with `conversation_id` nullable if draft |
| `scrape <conv>` | `--with-attachments`, `--out FILE`, `--data-dir` | yes, read-only | `Session.scrape(...)` | rendered current-branch markdown export |
| `history <conv>` | `--out FILE`, `--data-dir` | no | `Session.history(...)` over store only | rendered local markdown transcript |
| `export <conv>` | alias of `history`; `--out FILE`, `--data-dir` | no | `Session.history(...)` | rendered local markdown transcript |
| `fetch <conv> <attachment>` | `--data-dir`, optional `--json` | maybe | `Session.fetch(...)` | local path, or JSON metadata |
| `loop <conv> --message "keep pushing!!"` | `--max-iterations N`, `--timeout S`, `--max-total-wait S`, `--data-dir` | yes, persistent | `Session.loop(...)` yielding `AskResult` | JSONL, one envelope per assistant turn/partial |
| `status [<conv>]` | `--json`, `--data-dir` | preflight; attach only if reachable and safe | `Session.status(...)` | human report or JSON report |

### `ask <conv?> "<prompt>"`

Behavior: if `<conv>` is omitted, call `Session.create(project=...)` first and then send into that new/draft conversation; if `<conv>` is supplied, resolve it statelessly from URL/id/alias. For a bare id plus `--project`, construct/navigate the project URL shape only after normalizing `project_id`; if a supplied project URL and `--project` disagree, fail closed with a usage/config error rather than guessing (REWRITE-SPEC §9; M2 handoff says project send remains near-term/unverified).

Browser behavior: CDP attach only. Preflight with `GET http://127.0.0.1:9222/json/version`; if unreachable, raise `CdpUnreachableError`. Open or reuse only a tool-owned tab; never iterate `context.pages`; detach on exit; never quit the browser (REWRITE-SPEC §13; charter safety invariants).

Algorithm inside `Session.ask`: (1) resolve and allowlist the conversation URL; (2) open a tool-owned tab; (3) if idle, reload the conversation to clear SPA staleness; (4) detect login/Cloudflare wall and stop with `HumanActionNeededError`; (5) capture latest user-turn id/count baseline using `[data-message-author-role="user"][data-message-id]`; (6) select requested model/tools through Radix label enumeration and verify reflected labels before send; (7) upload `--attach` files through the UI and verify attachment chips/refs before send; (8) eager-write a pending user record with conversation ref and prompt before/at send, using a pending attempt id until the backend/UI message id is known; (9) fill `#prompt-textarea` with rich-editor insertion and submit via verified send control/Enter fallback; (10) poll briefly for a new user turn carrying the prompt and raise `PromptNotSubmittedError` if absent; (11) wait for completion using backend-api poll first and DOM consensus fallback, gated on the new-turn baseline; (12) capture the backend JSON using transient web-app auth/OAI headers from the page's own request, never logged; (13) stream/linearize current branch, update transcript/raw mapping, salvage partial on error/timeout; (14) return `AskResult`. Steps (5), (10), and (11) implement gotcha #2; steps (8) and (13) implement gotcha #3 write discipline; backend capture requirements are from M2 handoff and REWRITE-SPEC §5/§6/§7/§8.

Output: on complete success, stdout is exactly `AskResult.content_markdown` plus a final newline if missing. No banners, JSON, progress, or file paths are mixed into stdout. With `--out FILE`, write the same markdown bytes to `FILE` atomically in addition to stdout. On `CompletionTimeoutError`, if salvaged partial text exists, print/write that partial markdown, mark the persisted turn `status="partial"` and `partial=true`, then exit with the timeout code.

### `create`

Behavior: start a new ChatGPT conversation, optionally inside `--project ID`, and print the conversation reference. Browser behavior is CDP attach with a tool-owned new-chat tab only. It never sends a prompt and never automates login. Project creation is a near-term assumption because M2 did not live-verify project URLs/create behavior (M2 handoff; common constraints §3).

Return/output shape: human stdout should be one line `url=<url> id=<conversation_id-or-null> project_id=<project_id-or-null>`. With `--json`, stdout should be:

```json
{
  "schema_version": 1,
  "conversation_id": "string|null",
  "url": "string",
  "project_id": "string|null",
  "is_draft": "boolean"
}
```

If the web UI does not allocate a conversation id until the first send, `Session.create` must return `conversation_id=null` and `is_draft=true`, persist an alias/draft ref if needed, and surface this as an explicit open-state rather than fabricating an id. `ask` remains the preferred create-and-send path because it can update the store once the real id appears.

### `scrape <conv>`

Behavior: read-only capture of an existing conversation into the store and one rendered markdown export. It must not send, select models/tools, upload, or mutate the remote conversation. It opens a tool-owned tab to the resolved conversation URL, obtains the page's own backend-api auth/OAI headers from that tab's request, fetches `GET https://chatgpt.com/backend-api/conversation/<conversation_id>`, streams/persists the mapping, linearizes the current branch, writes/updates `transcript.jsonl`, writes `raw-mapping.json`, and renders markdown. M2 measured a successful response at about 17.1 MB and about 5.0k mapping/current-branch nodes, so the design must stream/process without gratuitous parse-everything-then-process peak memory (M2 handoff; agent-rigor complexity rule).

`--with-attachments` means: record all attachment refs as usual, then attempt supported lazy downloads for downloadable attachment refs using allowlisted/authenticated handlers; citations/search web sources are not downloaded. If a byte-download shape is unsupported, leave the ref pending and report `pending_attachments`; do not guess endpoints (REWRITE-SPEC §8; M2 attachment shapes).

Output: stdout is the full rendered current-branch markdown export, payload-only. With `--out FILE`, write the same markdown to `FILE` as well. Capture fallback order is backend → copy button → KaTeX annotation → DOM textContent; DOM text is marked lossy/partial and should not satisfy the math-fidelity bar by itself (REWRITE-SPEC §5/§17; common constraints §4).

### `history <conv>` / `export <conv>`

Behavior: browser-free rendering from local store only. These commands must not preflight CDP, attach, navigate, or contact the network. They read `index.json`, `conversations/<id>/transcript.jsonl`, and optional `raw-mapping.json` branch metadata under `--data-dir`, then render the current stored transcript to markdown.

Output: stdout is the rendered markdown. `--out FILE` writes the same bytes in addition to stdout. If the conversation is absent locally, raise `ConversationNotFoundError` with action `run scrape <conv> first or check the id/alias`.

### `fetch <conv> <attachment>`

Behavior: resolve `<attachment>` against stored refs by id/name/asset pointer/source ref. If bytes are already present under `conversations/<id>/attachments/`, return the path without browser attach. If bytes are not present and the ref has a supported authenticated download recipe, attach over CDP, open a tool-owned tab for the conversation if needed to obtain transient headers, enforce the domain allowlist, download to a temp file in `attachments/`, verify size/hash when known, then atomic-rename.

Browser behavior: no browser for cached/local refs; CDP attach for authenticated downloads only. Because M2 observed refs by ids/asset pointers/metadata and no literal `/backend-api/files/...` or `sandbox:`/`attachment:` URLs, the exact byte-download handlers are an M5 design/verification dependency rather than something CLI should invent (M2 handoff).

Output: default stdout is the local path only. With `--json`, stdout is `{"schema_version":1,"conversation_id":"...","attachment_ref":"...","local_path":"...","bytes":123,"sha256":"...","already_present":false}`.

### `status [<conv>]`

Behavior: diagnostics only. Always emits a report if possible. It may return a nonzero exit code when the report itself identifies a blocking condition such as CDP down or login wall, but stdout still contains the human/JSON status report. Details are in §5 below. Status must inspect only a tool-owned diagnostic tab when checking signed-in/login-wall/selector state; it must not inspect existing operator tabs (REWRITE-SPEC §12/§13; charter safety invariants).

# 2. Output rule for gotcha #4

`ask` and `scrape` always write their primary payload to stdout and additionally write `--out FILE` when provided. There is no branch where `--out` redirects/suppresses stdout (REWRITE-SPEC §4/§17; common constraints §4).

Payload formats: `ask` stdout is the canonical markdown of the newly completed assistant turn, or salvaged partial markdown on `CompletionTimeoutError`; `scrape` stdout is the rendered canonical markdown export of the scraped current branch. Both are UTF-8 text and end with exactly one newline added if the payload lacks one. Progress, warnings, status summaries, and errors go to stderr so agents can safely pipe stdout into files/tools.

`tee_payload(payload: str, out: Path | None) -> None` should attempt both sinks independently: write stdout and atomic-write `out` (temp file in same directory, flush/fsync as appropriate, rename). If one sink fails, still attempt the other, then raise an output error after the durable transcript/store write has already happened. This preserves stdout as fallback and store as durable truth (gotcha #4 plus REWRITE-SPEC §8 write discipline).

For `loop`, raw markdown from repeated turns is not safely delimiter-free. Therefore `loop` stdout is JSON Lines by default, one object per iteration, with `content_markdown` carrying the canonical markdown. No progress lines appear on stdout. Example:

```jsonl
{"schema_version":1,"type":"turn","iteration":1,"conversation_id":"6a...","conversation_url":"https://chatgpt.com/c/6a...","user_message_id":"msg_user_...","assistant_message_id":"msg_asst_...","status":"complete","partial":false,"capture_method":"backend","content_markdown":"...","transcript_path":"/home/.../transcript.jsonl"}
```

# 3. Keep-pushing loop

## 3.1 Primary form: agent-driven repeated `ask`

The primary ergonomic loop is stateless-by-URL: an autonomous agent repeatedly runs `ask-chatgpt ask <url-or-id> "keep pushing!!"`, consumes stdout, inspects the persisted transcript if needed, and decides externally whether the problem is solved. This matches REWRITE-SPEC §4 and avoids embedding a fake solver/termination oracle in the tool.

Prompt-design guardrail: the loop message must not encode its own answer or predetermine the desired artifact. If the agent wants a file, it must ask for a file explicitly rather than using a recall/leading prompt. This follows the charter and REWRITE-SPEC §18 prompt-quality rule.

Each atomic `ask` is crash-resumable: it persists the conversation ref and pending prompt at/before send, verifies a new user turn before waiting, captures/persists the response, prints stdout, and detaches. Re-running after `PromptNotSubmittedError` is retryable because the tool proved no new submitted user turn appeared within the verification window; re-running after completion timeout should first inspect/scrape the partial turn rather than blindly submitting another prompt.

## 3.2 Convenience form: `loop <conv> --message "keep pushing!!" [--max-iterations N]`

`loop` is a single process with one persistent `Session`; it exists for efficiency and stateful rate/tab ownership, not different semantics. It attaches once, opens/reuses a tool-owned tab, and yields one `AskResult` per iteration.

Control flow inside `Session.loop`:

1. Preflight CDP once; attach over CDP; never launch a browser; never quit on exit.
2. Resolve `<conv>` and enforce the allowlist.
3. Open a tool-owned conversation tab; do not inspect existing tabs or iterate `context.pages`.
4. For `iteration = 1..max_iterations` if bounded, otherwise until SIGINT/error: call idle-reload before the turn; call `Session.ask(..., prompt=message, timeout_s=..., max_total_wait_s=...)` using the already-owned tab/session; let `Session.ask` perform baseline, send, new-turn verification, completion, capture, and persistence.
5. After each result, immediately emit one JSONL turn envelope to stdout and flush. If `status="partial"`, include `partial=true` and the salvaged `content_markdown`.
6. Respect the persistent session's account rate budget/politeness floor/backoff between sends; do not implement an independent per-loop limiter that can conflict with lens 4's shared-resource design (REWRITE-SPEC §10; agent-rigor shared-resource ceiling).
7. Stop with exit 0 when `--max-iterations` is reached. Stop nonzero on `PromptNotSubmittedError`, `HumanActionNeededError`, `CdpUnreachableError`, `DisallowedDomainError`, selection-not-reflected, capture fail-closed without usable fallback, or `CompletionTimeoutError` after emitting any partial envelope. Stop with 130 on SIGINT after attempting partial salvage if a turn is in progress.

`--max-iterations` omitted means unbounded until interrupt/error, subject to the same rate budget and no-spam safety nets. This is not an arbitrary hard account cap; agents should normally pass an explicit bound for batch jobs. There is no hidden total-time cap; `--max-total-wait` is the only total wait bound and defaults to unbounded (REWRITE-SPEC §7; common constraints §4).

# 4. Error taxonomy

All errors inherit from `AskChatGptError` and carry stable machine fields. Error messages are actionable and sanitized; never include bearer tokens, OAI header values, cookies, raw response headers, or private tab titles.

```python
class AskChatGptError(Exception):
    code: str
    exit_code: int
    retryable: bool
    retry_action: str | None
    message: str
    details: dict[str, object]

class CdpUnreachableError(AskChatGptError): ...
class HumanActionNeededError(AskChatGptError): ...  # login wall / Cloudflare
class DisallowedDomainError(AskChatGptError): ...
class ConversationNotFoundError(AskChatGptError): ...
class PromptNotSubmittedError(AskChatGptError): ...
class SelectionNotReflectedError(AskChatGptError): ...
class ModelSelectionNotReflectedError(SelectionNotReflectedError): ...
class ToolSelectionNotReflectedError(SelectionNotReflectedError): ...
class CaptureFailedClosedError(AskChatGptError): ...
class AuthHeadersUnavailableError(CaptureFailedClosedError): ...
class BackendShapeUnrecognizedError(CaptureFailedClosedError): ...
class CompletionTimeoutError(AskChatGptError): ...
class AttachmentNotFoundError(AskChatGptError): ...
class StoreError(AskChatGptError): ...
class InternalError(AskChatGptError): ...
```

| Class | `code` | Exit | Retryable? | Raised when | Actionable message |
|---|---:|---:|---|---|---|
| `CdpUnreachableError` | `CDP_UNREACHABLE` | 20 | yes, after operator action | Preflight `GET /json/version` fails/times out | `Start or expose the operator-signed-in Chromium at http://127.0.0.1:9222, then retry. Do not launch a new Playwright browser.` |
| `HumanActionNeededError` | `HUMAN_ACTION_NEEDED` | 21 | not autonomously; yes after human login/challenge resolution | Login wall or Cloudflare challenge on a tool-owned tab | `STOP. Human must sign in/clear challenge in the existing browser. Tool will not automate login; status may poll read-only.` |
| `DisallowedDomainError` | `DISALLOWED_DOMAIN` | 22 | no, unless input corrected | URL/download target outside allowlist | `Refusing to navigate/fetch <redacted-url-host>; use a chatgpt.com/openai.com/oaiusercontent allowed URL or local attachment ref.` |
| `ConversationNotFoundError` | `CONVERSATION_NOT_FOUND` | 23 | no, unless id/permissions corrected | Authenticated backend/UI says conversation is absent, or local-only command lacks store entry | `Check the conversation id/URL/account, or run scrape first for local history/export.` |
| `PromptNotSubmittedError` | `PROMPT_NOT_SUBMITTED` | 30 | yes | Submit action produced no new user turn matching the prompt within the verification window | `No new user turn was verified; stale assistant replies were not returned. Idle-reload and retry the same prompt is safe after confirming no new turn exists.` |
| `ModelSelectionNotReflectedError` | `MODEL_SELECTION_NOT_REFLECTED` | 31 | yes after reload/menu retry | Requested model label was selected but UI did not reflect it | `Requested model '<label>' was not verified in the composer; no prompt was sent. Check label/options and retry.` |
| `ToolSelectionNotReflectedError` | `TOOL_SELECTION_NOT_REFLECTED` | 32 | yes after reload/menu retry | Requested tool label was not reflected/toggled | `Requested tool '<label>' was not verified; no prompt was sent. Check label/options and retry.` |
| `AuthHeadersUnavailableError` | `CAPTURE_AUTH_HEADERS_UNAVAILABLE` | 40 | maybe after reload/login | Could not obtain transient web-app auth/OAI headers from the page's own backend request | `Backend capture could not authenticate safely. Fallback was attempted; if no faithful fallback succeeded, retry after reload or human login.` |
| `BackendShapeUnrecognizedError` | `CAPTURE_BACKEND_SHAPE_UNRECOGNIZED` | 41 | no until code/selector update | Backend JSON lacks expected `mapping`/message shape or content fields | `Backend shape changed. Fallback was attempted and result is flagged; update capture parser before trusting fidelity.` |
| `CompletionTimeoutError` | `COMPLETION_TIMEOUT` | 50 | retry wait/scrape, not blind resend | No-activity window elapsed, or explicit `max_total_wait` elapsed | `No progress for <timeout_s>s. Partial text was salvaged with partial=true; inspect/scrape before sending another prompt.` |
| `AttachmentNotFoundError` | `ATTACHMENT_NOT_FOUND` | 60 | no, unless ref corrected | `fetch` attachment ref not found in local metadata | `Run scrape to populate refs or pass an attachment id/name/asset_pointer from status/history metadata.` |
| `StoreError` | `STORE_ERROR` | 70 | depends on filesystem | Data-dir read/write/atomic-rename failure | `Fix data-dir permissions/disk/path; transcript may still be recoverable from browser/store temp files.` |
| `InternalError` | `INTERNAL_ERROR` | 99 | unknown | Unexpected bug | `Unexpected ask-chatgpt bug; no secrets logged. Inspect traceback only in debug logs with redaction.` |

`CompletionTimeoutError.details` must include `conversation_id`, `conversation_url`, `assistant_message_id` if known, `partial_text` or `partial_path`, `partial=true`, `last_progress_at`, `timeout_s`, and `max_total_wait_s`. The CLI prints salvaged partial stdout for `ask` and emits a partial JSONL envelope for `loop` before exiting 50.

`CaptureFailedClosedError.details` must include `fallback_attempted: bool`, `fallback_method: "copy_button"|"katex_annotation"|"dom_text"|null`, `fidelity: "canonical"|"lossy"|"unknown"`, and `partial: bool`; it must not include auth/header values. If fallback reaches canonical copy-button markdown, the command may succeed with `capture_method="copy_button"`; if only DOM text is available, the result is flagged partial/lossy.

CLI error formatting: stderr first line is `ERROR <CODE>: <message>`. If `--json` is active for the command, stderr additionally receives one JSON object `{"schema_version":1,"ok":false,"error":{"code":"...","exit_code":30,"retryable":true,"retry_action":"...","details":{...}}}`. stdout remains reserved for payload/status and never receives error prose except documented salvaged partial payload.

# 5. `status` command contents

`status` is both a human diagnostic and an agent-readable health probe. It reads local store state even if CDP is down; it only attaches/probes the browser after the required CDP preflight succeeds. The required preflight is semantically `curl -s --max-time 5 http://127.0.0.1:9222/json/version`, implemented in Python HTTP with the same timeout or by a subprocess-free equivalent (REWRITE-SPEC §12/§13; common constraints §2).

Global human report fields: version; CDP endpoint reachable/unreachable plus browser/protocol from `/json/version`; browser attached true/false; profile label/configured dir when safely known (`agent` / `Profile 1` from charter, marked `verified=false` if CDP cannot expose it without unsafe `chrome://` probing); signed-in/login-wall/cloudflare/unknown from a tool-owned diagnostic tab only; selector-map channel and validity; data-dir path; conversation count; total turn count; pending attachment downloads; concurrency/rate state from lens 4; last error from the store/rate state.

Per-conversation human report fields for `status <conv>`: normalized conversation id/url/project id; model `{slug, display}` from latest stored/backend turn; active tools list; total/user/assistant/partial/error turn counts; last-turn `{message_id, created_at, role, status, partial}`; pending/downloaded attachment counts; branch info `{current_node, mapping_nodes, current_branch_nodes, has_branches}`; paths to transcript/raw mapping/export if present.

`status --json` stdout schema:

```json
{
  "schema_version": 1,
  "ok": true,
  "generated_at": "2026-06-18T00:00:00Z",
  "version": "string",
  "global": {
    "data_dir": "string",
    "store": {
      "conversation_count": 0,
      "total_turn_count": 0,
      "pending_attachment_downloads": 0,
      "index_path": "string"
    },
    "cdp": {
      "endpoint": "http://127.0.0.1:9222",
      "reachable": true,
      "preflight_status": "ok|cdp_unreachable|skipped",
      "browser": "Chrome/149...|null",
      "protocol_version": "1.3|null",
      "websocket_endpoint_present": true,
      "attached": true,
      "profile": {
        "configured_name": "agent|null",
        "configured_dir": "Profile 1|null",
        "verified": false,
        "source": "charter|cdp|unknown"
      },
      "login_state": "signed_in|login_wall|cloudflare_challenge|unknown|not_checked",
      "human_action_needed": false
    },
    "selectors": {
      "channel": "real|mock",
      "valid": true,
      "map_version": "string|null",
      "required": {
        "composer": {"selector": "#prompt-textarea", "present": true, "required_for": ["ask", "loop"]},
        "tools_button": {"selector": "button[data-testid=\"composer-plus-btn\"]", "present": true, "required_for": ["ask --tool", "ask --attach"]},
        "message_turn": {"selector": "[data-message-id][data-message-author-role]", "present": true, "required_for": ["ask", "scrape fallback", "completion fallback"]},
        "user_turn": {"selector": "[data-message-author-role=\"user\"][data-message-id]", "present": true, "required_for": ["send baseline"]},
        "assistant_turn": {"selector": "[data-message-author-role=\"assistant\"][data-message-id]", "present": true, "required_for": ["completion fallback"]},
        "copy_button": {"selector": "button[data-testid=\"copy-turn-action-button\"]", "present": null, "required_for": ["capture fallback"]},
        "stop_button": {"selector": "button[data-testid=\"stop-button\"], #composer-submit-button[aria-label*=\"Stop\" i]", "present": false, "required_for": ["completion fallback"]},
        "send_button": {"selector": "button[data-testid=\"send-button\"], #composer-submit-button", "present": null, "required_for": ["send"]}
      }
    },
    "rate": {
      "state": "idle|sending|backing_off|unknown",
      "active_sessions": 0,
      "active_tabs": 0,
      "max_tabs": 3,
      "politeness_floor_s": null,
      "backoff_until": null,
      "last_send_at": null,
      "last_rate_signal": null
    },
    "last_error": {
      "code": "string|null",
      "message": "string|null",
      "at": "string|null",
      "retryable": true
    }
  },
  "conversation": {
    "conversation_id": "string",
    "url": "string",
    "project_id": "string|null",
    "model": {"slug": "string|null", "display": "string|null"},
    "active_tools": ["deep_research"],
    "turns": {"total": 0, "user": 0, "assistant": 0, "partial": 0, "error": 0},
    "last_turn": {"message_id": "string|null", "created_at": "string|null", "role": "user|assistant|null", "status": "complete|partial|error|null", "partial": false},
    "attachments": {"pending": 0, "downloaded": 0, "refs": [{"id": "string", "name": "string|null", "source_ref": "string", "local_path": "string|null", "status": "pending|downloaded|unsupported"}]},
    "branch": {"current_node": "string|null", "mapping_nodes": 0, "current_branch_nodes": 0, "has_branches": false, "raw_mapping_path": "string|null"},
    "paths": {"transcript_jsonl": "string|null", "raw_mapping_json": "string|null", "attachments_dir": "string|null"}
  }
}
```

`present` is `null` when status did not safely check a selector, for example because CDP is down or no diagnostic tab was opened. `status` should not fail merely because selectors for optional fallbacks such as copy button are not currently visible; it should set `valid=false` only when a required selector map entry is missing/malformed or a required visible state for the chosen diagnostic scope fails.

Exit-code policy: `status` exits 0 when it can emit a report and no blocking condition is present. It exits 20 for CDP unreachable, 21 for login/challenge, 22 for allowlist/refusal, 23 for per-conversation not found, while still printing the report. Store-only fields remain populated when possible.

# 6. Atomic-verb plumbing

Browser atomic verbs that require a healthy browser before they can produce their primary payload (`ask`, `create`, `scrape`, uncached authenticated `fetch`) use this wrapper:

```python
def run_browser_atomic(args, operation):
    session = Session(cdp_endpoint=args.cdp_endpoint, data_dir=args.data_dir, selector_channel=args.selector_channel, channel="cdp")
    try:
        with session:  # preflight + attach; __exit__ detaches only
            return operation(session)
    except AskChatGptError as exc:
        return render_error_and_exit(exc, json_mode=getattr(args, "json", False))
```

The `Session` constructor must not attach by itself if the command is store-only. `__enter__` performs preflight, attaches over CDP, initializes tool-owned tab tracking, loads selector maps, and initializes process-local rate/tab state. `__exit__` closes only tool-owned tabs if the pool policy says to close them, then detaches; it never closes/quits the browser (REWRITE-SPEC §13; charter safety invariants).

`status` is intentionally special: it should call a non-throwing `build_status_report(probe_browser=True)` path that records `CDP_UNREACHABLE`/`HUMAN_ACTION_NEEDED` inside the report and still prints stdout before returning the corresponding exit code. It may create a temporary `Session` only after preflight succeeds.

Store-only verbs (`history`, `export`, cached `fetch`) instantiate the store/identity layer directly or use `Session(..., channel="mock")` with `probe_browser=False`; they must not call CDP preflight and must not touch the network.

`loop` and library consumers that need concurrency hold one `Session` open:

```python
with Session(cdp_endpoint=..., data_dir=...) as session:
    for result in session.loop(conv, message=message, max_iterations=n, timeout_s=timeout_s, max_total_wait_s=max_total_wait_s):
        write_jsonl_turn(result)
```

The persistent `Session` is the single owner of its tab pool and account send-rate budget. Multiple independent atomic CLI processes cannot share in-memory rate state; if lens 4 provides an advisory data-dir lock/rate file, the CLI should call it through `Session` rather than implementing a second limiter. This preserves the shared-resource-ceiling rule from agent-rigor and REWRITE-SPEC §10.

# Cross-cluster interfaces & dependencies

Session/API cluster (lens 1): exposes the `Session` methods and result dataclasses above; CLI depends on `Session.ask` to enforce baseline/new-turn verification, eager write, completion wait, capture, and partial salvage, rather than duplicating those rules.

Store/persistence cluster (lens 2): provides `index.json`, `transcript.jsonl`, `raw-mapping.json`, attachment metadata, last-error records, atomic writes, markdown rendering for `history/export`, and status counts/paths. CLI needs a pending-attempt representation for eager-write before real message ids exist.

Capture/CDP/send cluster (lens 3): provides own-tab CDP attach/navigation, allowlist enforcement, login/challenge detection, backend-api capture with transient web-app auth/OAI headers, fail-closed fallback chain, selector map validation, model/tool Radix selection verification, and send/new-turn verification. CLI supplies labels/flags and formats results only.

Concurrency/rate cluster (lens 4): provides persistent `Session` tab pool, politeness floor, adaptive backoff/rate state, optional advisory cross-process coordination, and status fields under `global.rate`. CLI must not add an independent limiter except through this API.

Error taxonomy is shared across all modules: every module raises `AskChatGptError` subclasses with stable `code`, `exit_code`, `retryable`, `retry_action`, and sanitized `details`; CLI is the only layer mapping those to process exits and stderr/stdout formatting.

Status reads across all clusters: version/build info from package metadata; CDP/browser/login/selector state from lens 3; store counts and per-conversation branch/attachment data from lens 2; rate/concurrency from lens 4; last error from shared error/store plumbing.

# Open questions / assumptions

Assumption: `create` may not receive a server conversation id until the first send. The design therefore allows `conversation_id=null`/`is_draft=true`; M5 should verify plain and project create behavior before making `conversation_id` non-null mandatory.

Assumption: project send/create use the URL shape `/g/g-p-<project_id>/c/<chat_id>` and otherwise behave like plain conversations. M2 explicitly deferred project probing, so implementation must fail closed if project context cannot be verified.

Open question: final default value for `--timeout` when omitted. Semantics are fixed as a no-activity window and `--max-total-wait` defaults unbounded; this lens intentionally does not invent a measured safe default.

Open question: exact authenticated endpoints/recipes for downloading attachment bytes from M2-observed ids, asset pointers, and metadata refs. CLI `fetch` should expose the path/ref behavior now and leave unsupported refs pending rather than guessing.

Open question: safe profile verification over CDP. The charter names profile `agent` / dir `Profile 1`, but CDP `/json/version` may not expose profile identity; status should report configured profile and mark `verified=false` unless a safe, allowlisted, own-tab method is designed.

Open question: whether `loop` should later accept pass-through `--model`/`--tool` flags. MVP keeps loop as repeated `Session.ask` with an existing conversation state; agents needing per-turn model/tool selection can use repeated atomic `ask`.
