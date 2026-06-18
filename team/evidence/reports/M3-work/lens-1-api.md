STATUS: DONE
Produced the Lens 1 design for the public `Session` API, return objects, module seams, browser channel abstraction, verified-send flow, and Radix menu abstraction.
Key decisions: `Session` is the only owner of managed tabs and send-rate budget; all browser work goes through `channels`; canonical reads use backend capture with page-request auth/OAI headers; CLI stdout is never suppressed by `--out`.
Blockers/open items are limited to M5/M7 verification gaps: project create/send, `stream_status`, attachment byte-fetch routes, send-button-on-input selector, and numeric rate defaults.

## 0. Sources and non-negotiable invariants

This design treats `docs/REWRITE-SPEC.md`, `team/evidence/handoffs/M2-ground-truth-probe.md`, `team/charter.md`, and `.claude/skills/manager/references/agent-rigor.md` as the ground-truth inputs, with M2 overriding pre-M2 hypotheses where they diverge. It also uses `issues/cdp-send-repro/controller.mjs` only as a read-only send/completion mechanics reference. Non-obvious live-site facts below cite `M2 handoff`; architectural facts cite `REWRITE-SPEC §N`.

Hard invariants encoded in this API: CDP attach only, no Playwright-launched browser, no stealth, inspect only tool-opened tabs, never quit the browser, preflight CDP before real CDP work, login/Cloudflare stops as `HUMAN-ACTION-NEEDED`, domain allowlist before navigation/fetch, no bearer/OAI header persistence or logging, modest shared-browser concurrency, no arbitrary message cap, no hidden completion ceiling, eager write plus partial salvage, and stdout plus `--out` for CLI `ask`/`scrape` (`REWRITE-SPEC §13`, `M3 common §2`, `team/charter.md`).

## 1. `Session` object — full public API

Public type aliases used by signatures:

```python
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
ChannelName = Literal["mock", "cdp"]
ConvAddress = str | "ConversationRef"          # bare conversation id, URL, alias, or ConversationRef
ProjectAddress = str | "ProjectRef" | None      # project id as stored or URL project component; M5 must verify create/send behavior
AttachmentInput = str | Path | "AttachmentSpec"
AttachmentAddress = str | "AttachmentRef"
TurnStatus = Literal["complete", "partial", "error"]
TurnKind = Literal["normal", "deep_research", "image", "code_execution", "file_reference", "unknown"]
```

Constructor and lifecycle:

```python
class Session:
    def __init__(
        self,
        *,
        cdp_endpoint: str = "http://127.0.0.1:9222",
        data_dir: str | Path | None = None,
        channel: ChannelName = "cdp",
        selector_map: str | Path | Mapping[str, str] | None = None,
        max_tabs: int = 3,
        default_activity_timeout_s: float = 600.0,
        default_max_total_wait_s: float | None = None,
        send_verify_timeout_s: float = 30.0,
        composer_wait_timeout_s: float = 20.0,
        hydrate_timeout_s: float = 60.0,
        poll_interval_s: float = 2.0,
        send_politeness_floor_s: float | None = None,
        strict_selectors: bool = True,
    ) -> None: ...

    def attach(self) -> "Session": ...
    def detach(self, *, close_managed_tabs: bool = True) -> None: ...
    def __enter__(self) -> "Session": ...
    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None: ...
```

`data_dir=None` resolves to `$ASK_CHATGPT_DATA_DIR` or `~/.local/state/ask-chatgpt/` (`REWRITE-SPEC §8`). `channel="cdp"` preflights `GET http://127.0.0.1:9222/json/version` before attaching or any real browser leg; failure raises `CDPUnreachableError(code="CDP_UNREACHABLE")` (`M3 common §2`). `attach()` never launches a browser and never scans existing operator tabs; `detach()` closes only tabs this `Session` opened unless `close_managed_tabs=False`, and never calls browser quit (`REWRITE-SPEC §13`). `max_tabs=3` reflects the documented modest shared-browser concurrency target, not a message cap (`M3 common §2`). `send_politeness_floor_s=None` means use the final rate-budget default from the concurrency cluster; any positive value is a human-paced safety floor, not an arbitrary hard cap.

Public methods:

| Method | Signature | Browser? | Semantics |
|---|---|---:|---|
| `create` | `def create(self, project: ProjectAddress = None) -> ConversationRef` | yes | Open a tool-owned new chat, optionally under a project URL/id, persist the conversation ref before any send, and return the canonical conversation id/url. Project create is a near-term M5 verification item because M2 did not probe project URLs (`M2 handoff`). |
| `ask` | `def ask(self, conv_or_url: ConvAddress | None, prompt: str, *, model: str | None = None, tools: Sequence[str] = (), attach: Sequence[AttachmentInput] = (), timeout: float | None = None, max_total_wait: float | None = None, out: str | Path | None = None) -> TurnResult` | yes | Resolve/open a tool-owned conversation tab, idle-reload, verify model/tools, eager-write the pending prompt, send via UI, verify a new user turn, wait for a newer assistant completion, capture canonical backend markdown, persist/upsert transcript, optionally write `out`, and return the assistant `TurnResult`. `timeout` is a no-activity window; `max_total_wait=None` is unbounded (`REWRITE-SPEC §6-§8`). |
| `scrape` | `def scrape(self, conv_or_url: ConvAddress, *, with_attachments: bool = False, out: str | Path | None = None) -> Transcript` | yes, read-only | Open/reuse a tool-owned tab for the conversation, acquire page-request auth/OAI headers, capture backend JSON, linearize the current branch, persist `raw-mapping.json` plus JSONL records, optionally lazy-fetch attachments only if requested, optionally write `out`, and return `Transcript` (`REWRITE-SPEC §5`, `M2 handoff`). |
| `history` | `def history(self, conv_or_url: ConvAddress) -> Transcript` | no | Resolve id/alias from local `index.json` and read the local JSONL transcript/export state only; never preflights or touches a browser (`REWRITE-SPEC §3`, §8). |
| `fetch` | `def fetch(self, conv_or_url: ConvAddress, attachment_ref: AttachmentAddress) -> Path` | maybe | Resolve an attachment record and lazily download bytes into `attachments/` only for downloadable attachment/asset refs, applying allowlist and signed-in fetch if required; citations are not downloaded (`REWRITE-SPEC §8`, `M2 handoff`). |
| `status` | `def status(self, conv_or_url: ConvAddress | None = None) -> StatusReport` | preflight/maybe owned tab | Report global diagnostics and optional conversation diagnostics. For `cdp`, global status preflights `/json/version`; it may inspect only already managed tabs or a newly opened diagnostic tab, never operator tabs (`REWRITE-SPEC §12`, `M3 common §2`). |
| `loop` | `def loop(self, conv_or_url: ConvAddress, *, message: str = "keep pushing!!", model: str | None = None, tools: Sequence[str] = (), attach: Sequence[AttachmentInput] = (), timeout: float | None = None, max_total_wait: float | None = None, max_iterations: int | None = None, stop: Callable[[TurnResult], bool] | None = None, out_dir: str | Path | None = None) -> Iterator[TurnResult]` | yes | Hold one attached `Session`, repeatedly call the same verified-send/wait/capture path as `ask`, yield each result, and stop on `max_iterations`, `stop(result)`, or external error. This is a convenience over agent-driven repeated `ask`, not a daemon (`REWRITE-SPEC §2-§4`). |

Methods that touch the browser call `attach()` implicitly if needed for atomic CLI use; library callers that need concurrency should use `with Session(...) as s:` and keep the same `Session` open. Every browser-touching method uses `identity.require_allowed_url()` before navigation/fetch and refuses non-allowlisted domains (`REWRITE-SPEC §13`).

## 2. Result/return object model and JSONL alignment

The public dataclasses live in `session.py` and are imported by `store.py`, `capture.py`, and `cli.py`; `store.py` owns JSON serialization/deserialization. They intentionally mirror the JSONL field names so implementers do not need a second schema (`REWRITE-SPEC §8`).

```python
@dataclass(frozen=True)
class ConversationRef:
    conversation_id: str
    url: str
    project_id: str | None = None
    title: str | None = None
    current_node: str | None = None
    default_model_slug: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass(frozen=True)
class ModelRef:
    slug: str | None
    display: str | None

@dataclass(frozen=True)
class AttachmentSpec:
    path: Path
    display_name: str | None = None
    mime: str | None = None

@dataclass(frozen=True)
class AttachmentRef:
    source_kind: Literal["user_upload", "file_reference", "generated_asset", "code_execution_output"]
    source_ref: str                         # file id, asset_pointer, run id, or stable metadata id
    filename: str | None
    mime: str | None
    bytes: int | None
    sha256: str | None
    local_path: str | None
    download_state: Literal["pending", "downloaded", "not_downloadable", "error"]
    metadata: Mapping[str, JsonValue]       # sanitized; never auth/OAI headers

@dataclass(frozen=True)
class CitationRef:
    title: str | None
    url: str | None
    start_ix: int | None = None
    end_ix: int | None = None
    citation_format_type: str | None = None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

@dataclass(frozen=True)
class TurnResult:
    conversation_id: str
    message_id: str                         # canonical backend/DOM message id when known
    parent_id: str | None
    turn_index: int
    role: Literal["user", "assistant"]
    content_markdown: str
    model: ModelRef | None
    active_tools: tuple[str, ...]
    kind: TurnKind
    created_at: datetime | None             # from backend-api timestamp when available
    attachments: tuple[AttachmentRef, ...]
    citations: tuple[CitationRef, ...]
    status: TurnStatus
    partial: bool
    conversation_url: str
    project_id: str | None = None
    user_message_id: str | None = None      # populated on assistant result returned by ask()
    client_send_id: str | None = None       # links pre-send durable record to canonical user/assistant records
    error: str | None = None                # redacted actionable error code/message, no secrets

@dataclass(frozen=True)
class Transcript:
    conversation: ConversationRef
    turns: tuple[TurnResult, ...]           # visible current-branch user/assistant records
    raw_mapping_path: Path | None
    transcript_jsonl_path: Path
    attachments_dir: Path
    partial: bool = False

@dataclass(frozen=True)
class StatusReport:
    ok: bool
    code: str
    cdp_reachable: bool | None
    attached: bool
    signed_in: bool | None
    data_dir: Path
    conversations: int
    managed_tabs: int
    pending_attachments: int
    last_error: str | None
    conversation: Mapping[str, JsonValue] | None = None
```

JSONL record alignment is exact for the canonical fields: `conversation_id: str`, `message_id: str`, `parent_id: str|null`, `turn_index: int`, `role: "user"|"assistant"`, `content_markdown: str`, `model: {"slug": str|null, "display": str|null}|null`, `active_tools: list[str]`, `kind: str`, `created_at: str|null`, `attachments: list[AttachmentRef-json]`, `citations: list[CitationRef-json]`, `status: "complete"|"partial"|"error"`, `partial: bool`, plus optional seam fields `project_id`, `conversation_url`, `user_message_id`, `client_send_id`, and `error`. `scrape()` returns a `Transcript` made from the same records persisted to JSONL; `ask()` returns the newly completed assistant `TurnResult` from that transcript and also persists the user record. Hidden tool/thought/code nodes stay in `raw-mapping.json` unless they materialize visible text, attachments, citations, or execution artifacts (`REWRITE-SPEC §8`, `M2 handoff`).

The pre-send eager-write record uses `client_send_id="send:<uuid>"`, `message_id="client:<uuid>"`, `role="user"`, `content_markdown=prompt`, `status="partial"`, and `partial=True`; once the DOM/backend reveals the canonical user `message_id`, `store.commit_send(...)` appends the canonical user record and an update for the client record. `history()`/export collapses a resolved client record behind the canonical record by `client_send_id`, but an unresolved client record remains visible as partial salvage. This preserves the prompt/conversation ref across crashes before ChatGPT returns an id while keeping canonical backend ids as the normal idempotency key (`REWRITE-SPEC §8`, gotcha #3).

`AttachmentRef` covers all M2 shapes: `metadata.attachments[]` user uploads, `metadata.content_references[type="file"]` file refs, `content.assets[].asset_pointer` generated/image assets, and `metadata.aggregate_result` code-exec outputs. `CitationRef` covers DR/search citation offsets and nested metadata. Web citations are not attachment downloads (`M2 handoff`, `REWRITE-SPEC §8`).

## 3. Atomic operations vs persistent `Session` composition

Atomic CLI verbs are thin wrappers that create a short-lived `Session`, attach, perform one operation, detach, print to stdout, and additionally write `--out` when supplied (`REWRITE-SPEC §2-§4`). Pattern:

```python
def cli_ask(args: argparse.Namespace) -> int:
    with Session(cdp_endpoint=args.cdp_endpoint, data_dir=args.data_dir, channel=args.channel) as s:
        result = s.ask(args.conv, args.prompt, model=args.model, tools=args.tool, attach=args.attach, timeout=args.timeout, max_total_wait=args.max_total_wait, out=args.out)
    print(result.content_markdown)
    return 0
```

Persistent use holds one `Session` open for `loop()` or multi-tab concurrency. That single `Session` owns the managed tab pool and send-rate budget because independent per-operation limiters cannot coordinate a shared operator account/browser (`REWRITE-SPEC §2`, §10; `agent-rigor.md` shared-resource ceiling). `send.py`, `capture.py`, `completion.py`, and `menus.py` receive an opaque `BrowserTab` acquired from `Session`; none of those modules may create global browser connections, iterate existing pages, or maintain their own rate limiter. Lens 4 can replace the internal tab-pool/rate algorithms without changing this API boundary.

Atomic calls are safe for one-shot agent invocations because durable truth lives in the browser and on-disk transcript, not in a daemon (`REWRITE-SPEC §2`). Concurrency across multiple independent OS processes is intentionally not promised; if an agent wants coordinated concurrency, it must keep one persistent `Session` in-process so one owner accounts for all sends.

## 4. Complete module list and public signatures

### `session.py`

Responsibility: Public API facade, dataclasses, lifecycle, orchestration, and ownership of `Store`, `BrowserChannel`, tab pool, and rate budget. It resolves identity, enforces allowlist at the top of each browser-touching operation, delegates to focused modules, and never lets lower modules inspect unmanaged browser state (`REWRITE-SPEC §2-§3`).

Key public signatures: `class Session(...)`; `Session.attach() -> Session`; `Session.detach(close_managed_tabs: bool = True) -> None`; `Session.create(project: ProjectAddress = None) -> ConversationRef`; `Session.ask(...) -> TurnResult`; `Session.scrape(...) -> Transcript`; `Session.history(...) -> Transcript`; `Session.fetch(...) -> Path`; `Session.status(...) -> StatusReport`; `Session.loop(...) -> Iterator[TurnResult]`; dataclasses from §2.

### `capture.py`

Responsibility: Canonical read path and fail-closed fallback. It obtains backend auth/OAI headers from the page's own `/backend-api/conversation/<id>` request, forwards only the required header names for one in-page fetch, streams/spools the JSON response to `raw-mapping.json`, linearizes the current branch, extracts visible markdown/citations/attachment refs, and falls back copy-button → KaTeX annotation → DOM text only if backend capture is unavailable or shape-invalid (`REWRITE-SPEC §5`; `M2 handoff`). It must never log/persist `authorization` or OAI header values.

Key public signatures:

```python
SAFE_BACKEND_HEADER_NAMES: frozenset[str] = frozenset({
    "authorization", "oai-client-build-number", "oai-client-version", "oai-device-id", "oai-language", "oai-session-id", "x-openai-target-path", "x-openai-target-route",
})

@dataclass(frozen=True, repr=False)
class HeaderBundle:
    values: Mapping[str, str]
    def redacted(self) -> Mapping[str, str]: ...

@dataclass(frozen=True)
class CaptureResult:
    transcript: Transcript
    async_status: str | None
    raw_top_level_keys: tuple[str, ...]


def acquire_backend_headers(tab: BrowserTab, conv: ConversationRef, *, timeout_s: float = 30.0) -> HeaderBundle: ...
def fetch_backend_conversation(tab: BrowserTab, conv: ConversationRef, headers: HeaderBundle, *, raw_out: Path) -> Mapping[str, JsonValue]: ...
def capture_conversation(tab: BrowserTab, conv: ConversationRef, store: Store, *, with_attachments: bool = False) -> CaptureResult: ...
def iter_current_branch_records(raw_mapping_path: Path, conv: ConversationRef) -> Iterator[TurnResult]: ...
def fallback_capture_ui(tab: BrowserTab, conv: ConversationRef, store: Store) -> CaptureResult: ...
```

### `send.py`

Responsibility: UI-only actions for prompt submission and attachment upload. It implements the verified-send gotcha fix: baseline latest user id/count, fill `#prompt-textarea`, submit, verify a new user turn carrying the prompt, and raise `PromptNotSubmittedError` on no-op instead of returning stale content (`REWRITE-SPEC §6`; `controller.mjs`). It waits through transient composer unmounts and reloads only when the conversation is idle.

Key public signatures:

```python
@dataclass(frozen=True)
class TurnBaseline:
    latest_user_id: str | None
    user_count: int
    latest_assistant_id: str | None
    assistant_count: int

@dataclass(frozen=True)
class SubmittedTurn:
    baseline: TurnBaseline
    user_message_id: str
    user_count: int
    normalized_prompt: str


def read_turn_baseline(tab: BrowserTab, selectors: SelectorMap) -> TurnBaseline: ...
def wait_for_composer(tab: BrowserTab, selectors: SelectorMap, *, timeout_s: float) -> None: ...
def fill_composer(tab: BrowserTab, selectors: SelectorMap, prompt: str) -> None: ...
def submit_composer(tab: BrowserTab, selectors: SelectorMap) -> None: ...
def verify_prompt_submitted(tab: BrowserTab, selectors: SelectorMap, baseline: TurnBaseline, prompt: str, *, timeout_s: float) -> SubmittedTurn: ...
def send_prompt(tab: BrowserTab, selectors: SelectorMap, prompt: str, *, model: str | None, tools: Sequence[str], attach: Sequence[AttachmentInput], timeouts: SendTimeouts) -> SubmittedTurn: ...
```

### `completion.py`

Responsibility: Wait for a response newer than the send baseline, with backend-api polling primary and DOM consensus fallback. `timeout` is a no-activity window that resets on progress; `max_total_wait=None` is unbounded. On timeout/error it returns or raises with enough partial state for `Session` to salvage visible text and persist `partial=true` (`REWRITE-SPEC §7`, gotcha #3).

Key public signatures:

```python
@dataclass(frozen=True)
class CompletionState:
    complete: bool
    assistant_message_id: str | None
    async_status: str | None
    node_status: str | None
    activity_token: str
    partial_markdown: str
    source: Literal["backend", "dom"]


def poll_backend_completion(tab: BrowserTab, conv: ConversationRef, baseline: TurnBaseline, headers: HeaderBundle | None = None) -> CompletionState: ...
def poll_dom_completion(tab: BrowserTab, selectors: SelectorMap, baseline: TurnBaseline) -> CompletionState: ...
def wait_for_completion(tab: BrowserTab, conv: ConversationRef, selectors: SelectorMap, baseline: TurnBaseline, *, activity_timeout_s: float, max_total_wait_s: float | None, poll_interval_s: float = 2.0) -> CompletionState: ...
def wait_until_idle(tab: BrowserTab, selectors: SelectorMap, *, activity_timeout_s: float) -> None: ...
```

### `menus.py`

Responsibility: One label-driven Radix menu abstraction for model picker and tools/`+` menu. It opens a trigger, enumerates visible options in `[data-radix-popper-content-wrapper]`, selects by display label and role, verifies reflected state, and fails closed if absent/unverified (`REWRITE-SPEC §11`, `M2 handoff`). It must not open `Recent files` or `Projects` submenus because M2 identified private-name leak risk.

Key public signatures:

```python
@dataclass(frozen=True)
class MenuOption:
    label: str
    role: str | None
    checked: bool | None
    disabled: bool
    path: tuple[str, ...]

@dataclass(frozen=True)
class SelectionResult:
    requested: str
    reflected: str | None
    verified: bool


def open_radix_menu(tab: BrowserTab, trigger_selector: str) -> None: ...
def enumerate_radix_options(tab: BrowserTab) -> tuple[MenuOption, ...]: ...
def select_radix_label(tab: BrowserTab, label: str, *, role: str | None = None, submenu_path: Sequence[str] = ()) -> MenuOption: ...
def select_model(tab: BrowserTab, selectors: SelectorMap, label: str) -> SelectionResult: ...
def set_tools(tab: BrowserTab, selectors: SelectorMap, labels: Sequence[str]) -> tuple[SelectionResult, ...]: ...
def assert_reflected_model(tab: BrowserTab, selectors: SelectorMap, label: str) -> None: ...
def assert_reflected_tools(tab: BrowserTab, selectors: SelectorMap, labels: Sequence[str]) -> None: ...
```

### `store.py`

Responsibility: Durable per-conversation state under `data_dir`, append-only JSONL with last-writer-wins reads by `message_id`, index/alias handling, raw mapping storage, markdown export, attachment directory creation, pending-send collapse, and atomic writes. It never stores auth/OAI header values and never treats citations as downloads (`REWRITE-SPEC §8`).

Key public signatures:

```python
class Store:
    def __init__(self, data_dir: str | Path) -> None: ...
    def resolve_data_dir(self) -> Path: ...
    def conversation_dir(self, conversation_id: str) -> Path: ...
    def put_conversation_ref(self, ref: ConversationRef) -> None: ...
    def resolve_conversation(self, address: ConvAddress) -> ConversationRef: ...
    def begin_send(self, ref: ConversationRef, prompt: str, *, model: ModelRef | None, active_tools: Sequence[str]) -> TurnResult: ...
    def commit_send(self, client_send_id: str, canonical_user: TurnResult) -> None: ...
    def upsert_turn(self, record: TurnResult) -> None: ...
    def upsert_many(self, records: Iterable[TurnResult]) -> None: ...
    def write_raw_mapping(self, conversation_id: str, body: bytes | Iterable[bytes]) -> Path: ...
    def load_transcript(self, address: ConvAddress) -> Transcript: ...
    def export_markdown(self, transcript: Transcript, out: str | Path) -> Path: ...
    def record_partial(self, ref: ConversationRef, *, client_send_id: str | None, partial_markdown: str, error: BaseException) -> TurnResult: ...
    def attachment_path(self, conversation_id: str, ref: AttachmentRef) -> Path: ...
```

### `identity.py`

Responsibility: Stateless URL/id/alias parsing and canonical conversation/project metadata. It parses plain `/c/<conversation_id>` and project `/g/g-p-<project_id>/c/<conversation_id>` URLs, accepts bare conversation ids, and consults `Store` only for aliases (`REWRITE-SPEC §9`; project live behavior not confirmed by M2).

Key public signatures:

```python
CONVERSATION_RE: Pattern[str]
PROJECT_CONVERSATION_RE: Pattern[str]

def parse_conversation_address(value: str) -> ConversationRef | None: ...
def parse_project_address(value: str) -> ProjectRef | None: ...
def conversation_url(ref: ConversationRef) -> str: ...
def backend_conversation_url(conversation_id: str) -> str: ...
def normalize_conversation_id(value: str) -> str: ...
def resolve_conv_or_alias(value: ConvAddress, store: Store) -> ConversationRef: ...
```

### `channels/base.py`

Responsibility: The browser seam Protocol used by all modules; it is the only layer allowed to know Playwright/CDP details. It defines opaque tab handles, DOM snapshots, request snapshots, and fetch results for both `mock` and `cdp` (`REWRITE-SPEC §14`). See §5 for the full interface.

Key public signatures: `class BrowserChannel(Protocol)`; `class BrowserTab(Protocol)`; `class TurnDomSnapshot`; `class FetchResult`; `class RequestSnapshot`; `class ClipboardPermissionError`.

### `channels/mock.py`

Responsibility: Deterministic offline browser simulator and acceptance substrate. It simulates conversations, backend JSON, header requirement failures, verified send/no-op paths, transient composer unmounts, long-running completion progress, Radix menus, selector failures, clipboard permission `prompt`, login/Cloudflare stops, and allowlist rejections without network (`REWRITE-SPEC §14`, §18).

Key public signatures: `class MockChannel(BrowserChannel)`; `MockChannel(seed: int = 0, fixtures: Mapping[str, JsonValue] | None = None)`; `MockChannel.add_conversation(raw_backend_json: Mapping[str, JsonValue]) -> ConversationRef`; `MockChannel.set_send_behavior(kind: Literal["success", "noop", "stall", "composer_unmounted"]) -> None`; `MockChannel.advance_time(seconds: float) -> None`.

### `channels/cdp.py`

Responsibility: Attended real channel that attaches to the operator-launched Chromium at the configured endpoint, creates only tool-owned tabs, enforces allowlist, captures own-tab requests, evaluates/fills/clicks DOM, and detaches without quitting the browser. It must not call Playwright browser launch and must not iterate `context.pages` (`REWRITE-SPEC §13-§14`, `M3 common §2`).

Key public signatures: `class CdpChannel(BrowserChannel)`; `CdpChannel(cdp_endpoint: str, allowlist: Allowlist, selector_map: SelectorMap)`; `CdpChannel.preflight(timeout_s: float = 5.0) -> PreflightResult`.

### `selectors/` (`mock.json`, `real.json`)

Responsibility: Fail-closed selector maps loaded by channel/session. Missing required keys are startup errors in `strict_selectors=True`; selector drift should produce `SelectorNotFoundError`, not silent fallback to broad DOM scraping (`REWRITE-SPEC §2`, `M2 handoff`).

`selectors/real.json` must contain the M2-observed selectors exactly, with the model picker represented as a heuristic entry rather than a false stable id:

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
  "radix_portal": "[data-radix-popper-content-wrapper]",
  "model_picker_heuristic": "composer-footer button[aria-haspopup=\"menu\"] showing the current-model label; no stable data-testid/aria-label"
}
```

`selectors/mock.json` uses stable selectors implemented by `MockChannel`; tests must also run against `real.json` shape validation so production-required keys cannot disappear.

### `errors.py`

Responsibility: Named actionable exceptions with redacted messages and stable codes for CLI/status. Error formatting must never include bearer tokens, OAI header values, transcript text unless explicitly a partial salvage output, or private operator tab data (`M3 common §2`).

Key public signatures:

```python
class AskChatGPTError(Exception): code: str
class CDPUnreachableError(AskChatGPTError): code = "CDP_UNREACHABLE"
class HumanActionNeededError(AskChatGPTError): code = "HUMAN-ACTION-NEEDED"
class DomainNotAllowedError(AskChatGPTError): code = "DOMAIN_NOT_ALLOWED"
class SelectorNotFoundError(AskChatGPTError): code = "SELECTOR_NOT_FOUND"
class PromptNotSubmittedError(AskChatGPTError): code = "PROMPT_NOT_SUBMITTED"
class CompletionTimeoutError(AskChatGPTError): code = "COMPLETION_TIMEOUT"
class MaxTotalWaitExceededError(AskChatGPTError): code = "MAX_TOTAL_WAIT_EXCEEDED"
class BackendAuthUnavailableError(AskChatGPTError): code = "BACKEND_AUTH_UNAVAILABLE"
class BackendCaptureShapeError(AskChatGPTError): code = "BACKEND_CAPTURE_SHAPE"
class MenuOptionNotFoundError(AskChatGPTError): code = "MENU_OPTION_NOT_FOUND"
class MenuVerificationError(AskChatGPTError): code = "MENU_VERIFICATION_FAILED"
class AttachmentFetchError(AskChatGPTError): code = "ATTACHMENT_FETCH_FAILED"
class StoreError(AskChatGPTError): code = "STORE_ERROR"
```

### `allowlist.py`

Responsibility: Central URL/domain allowlist for all navigation and fetches. It permits chatgpt.com/openai.com auth and app hosts plus OAI content/static hosts required by the web app, and rejects everything else before the channel acts (`REWRITE-SPEC §13`).

Key public signatures:

```python
DEFAULT_ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (
    "chatgpt.com", ".chatgpt.com", "openai.com", ".openai.com", "oaiusercontent.com", ".oaiusercontent.com", "oaistatic.com", ".oaistatic.com",
)

@dataclass(frozen=True)
class Allowlist:
    host_suffixes: tuple[str, ...] = DEFAULT_ALLOWED_HOST_SUFFIXES
    def is_allowed_url(self, url: str) -> bool: ...
    def require_allowed_url(self, url: str) -> None: ...
    def sanitize_for_log(self, url: str) -> str: ...
```

Exact auth/content host suffixes may need expansion from real CDP telemetry in M5; expansion must be explicit and reviewed, not wildcard-all (`M3 common §2`).

### `cli.py`

Responsibility: Thin argparse/Typer wrapper over `Session`; no business logic beyond argument parsing, stdout/`--out`, exit codes, and redacted error display. `ask` and `scrape` always print markdown to stdout and additionally write `--out` when provided, fixing the v1 stdout suppression gotcha (`REWRITE-SPEC §4`, §17).

Key public signatures: `def main(argv: Sequence[str] | None = None) -> int`; command handlers `cmd_create(args)`, `cmd_ask(args)`, `cmd_scrape(args)`, `cmd_history(args)`, `cmd_export(args)`, `cmd_fetch(args)`, `cmd_loop(args)`, `cmd_status(args)`; all construct or receive a `Session` and otherwise delegate.

## 5. Channel abstraction: the browser seam

`Session` and modules call this Protocol only; they never import Playwright directly. `mock` and `cdp` implement the same methods, which is what makes the offline suite capable of proving no-op send detection, no hidden total timeout, stdout/`--out`, store behavior, and selector drift failures (`REWRITE-SPEC §14`, §18).

```python
@dataclass(frozen=True)
class BrowserTab:
    tab_id: str
    url: str

@dataclass(frozen=True)
class TurnDom:
    message_id: str
    role: Literal["user", "assistant"]
    text: str

@dataclass(frozen=True)
class TurnDomSnapshot:
    users: tuple[TurnDom, ...]
    assistants: tuple[TurnDom, ...]
    stop_visible: bool
    composer_visible: bool
    model_labels: tuple[str, ...]

@dataclass(frozen=True)
class RequestSnapshot:
    url: str
    method: str
    headers: Mapping[str, str]

@dataclass(frozen=True)
class FetchResult:
    status: int
    headers: Mapping[str, str]
    body: bytes | None
    body_path: Path | None

class BrowserChannel(Protocol):
    def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult: ...
    def attach(self) -> None: ...
    def detach(self) -> None: ...
    def open_tab(self, url: str) -> BrowserTab: ...
    def close_tab(self, tab: BrowserTab) -> None: ...
    def reload(self, tab: BrowserTab) -> None: ...
    def wait_for_load_state(self, tab: BrowserTab, *, timeout_s: float) -> None: ...
    def evaluate(self, tab: BrowserTab, js: str, *, arg: JsonValue | None = None, timeout_s: float | None = None) -> JsonValue: ...
    def wait_for_selector(self, tab: BrowserTab, selector: str, *, state: Literal["attached", "visible"] = "visible", timeout_s: float) -> None: ...
    def fill(self, tab: BrowserTab, selector: str, text: str) -> None: ...
    def insert_text(self, tab: BrowserTab, selector: str, text: str) -> None: ...
    def click(self, tab: BrowserTab, selector: str) -> None: ...
    def hover(self, tab: BrowserTab, selector: str) -> None: ...
    def query_turns(self, tab: BrowserTab, selectors: SelectorMap) -> TurnDomSnapshot: ...
    def wait_for_request(self, tab: BrowserTab, predicate: Callable[[RequestSnapshot], bool], *, timeout_s: float) -> RequestSnapshot: ...
    def fetch_in_page(self, tab: BrowserTab, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, body: bytes | str | None = None, stream_to: Path | None = None, timeout_s: float | None = None) -> FetchResult: ...
    def read_clipboard(self, tab: BrowserTab) -> str: ...
    def upload_files(self, tab: BrowserTab, selector: str, paths: Sequence[Path]) -> None: ...
```

`CdpChannel` constraints: `preflight()` is an HTTP GET to `/json/version`; `attach()` uses CDP connect to an already-running browser; `open_tab()` creates a new target/tab and records it as owned; no method enumerates or scores existing `context.pages`; `detach()` closes only owned targets or disconnects; `fetch_in_page()` runs from the page context so cookies/session apply but still requires explicit forwarded auth/OAI headers for backend conversation capture; every URL is allowlist-checked first (`M3 common §2`, `M2 handoff`).

`MockChannel` deterministic simulation requirements: missing backend auth headers return a 404-shaped JSON with top-level `detail`; forwarded `authorization`/OAI headers return a fixture with top-level keys including `conversation_id`, `mapping`, `current_node`, and `async_status`; visible assistant markdown fixtures include `\widehat`, `\frac`, `\ne`/`\neq`, `\(`, `\[`, and tables; DR/pro turns are large `turn_exchange_id` groups with hidden nodes plus one visible `assistant:text` report; send scenarios include success, no-op stale response, composer unmounted/remounted, no enabled send button, and stalled completion; menus include M2 labels and Radix portal roles; clipboard permission defaults to prompt/error (`M2 handoff`). A parametrized scale fixture should exercise the measured ~17.1 MB/~5k-node capture path without requiring production network.

## 6. `send.py` mechanics: verified send gotcha #2

Verified-send algorithm for `Session.ask()` and each `loop()` iteration:

1. Resolve `conv_or_url` to a `ConversationRef`, open/acquire a tool-owned tab, and navigate only to an allowlisted ChatGPT URL (`REWRITE-SPEC §9`, §13).
2. Wait until any existing generation is idle using `completion.wait_until_idle(..., require_newer=False)`. If idle between turns, reload the conversation and wait up to `hydrate_timeout_s` for `#prompt-textarea`, visible message turns, absent stop control, and non-contradicting model label; transient empty labels are tolerated, contradictory labels fail (`controller.mjs`, `REWRITE-SPEC §6`).
3. If `model` or `tools` are requested, call `menus.select_model`/`menus.set_tools` and verify reflected UI state before any prompt is sent. Deep Research is a tool in `active_tools`, not a model (`REWRITE-SPEC §11`; `M2 handoff`).
4. Read `TurnBaseline` from `[data-message-author-role="user"][data-message-id]` and `[data-message-author-role="assistant"][data-message-id]`: latest user id, user count, latest assistant id, assistant count (`REWRITE-SPEC §6`; `M2 handoff`).
5. Call `store.begin_send(...)` to durably write conversation id/url, prompt, requested model/tools, and `client_send_id` just before touching the composer. This is the crash-resume anchor for truncation/timeouts (`REWRITE-SPEC §8`, gotcha #3).
6. Wait/retry up to `composer_wait_timeout_s` for `#prompt-textarea`; absence during turn transitions is not fatal until the timeout expires (`REWRITE-SPEC §6`).
7. Fill the composer: focus `#prompt-textarea`, select/delete existing content, use normal fill where possible, then `document.execCommand("insertText", false, prompt)`/`InputEvent` fallback for the contenteditable editor. Verify normalized composer text equals normalized prompt before submission (`controller.mjs`).
8. Submit by clicking an enabled button matching `button[data-testid="send-button"], #composer-submit-button`; if no enabled button is found after input, use an Enter-key fallback only while the composer is focused and no multiline modifier is requested. Failure here is retryable and redacted (`REWRITE-SPEC §6`; M2 notes send button was not observed without input).
9. Poll for up to `send_verify_timeout_s` for a new user turn where `(latest_user_id != baseline.latest_user_id or user_count > baseline.user_count)` and `normalize_space(latest_user_text) == normalize_space(prompt)`. If not found, raise `PromptNotSubmittedError` with baseline/current ids and counts only; never return a stale assistant response (`REWRITE-SPEC §6`, gotcha #2).
10. After `SubmittedTurn`, call `store.commit_send(...)` with the canonical user message id, then `completion.wait_for_completion(...)` gated on the same baseline. Completion must return an assistant id different from the baseline latest assistant id and newer than the submitted user turn, or it is not valid (`REWRITE-SPEC §6-§7`).
11. On completion, run `capture.capture_conversation(...)`; use backend canonical markdown as the returned/persisted content. On error or no-activity timeout, salvage `CompletionState.partial_markdown` or visible DOM/copy fallback into a `TurnResult(status="partial"|"error", partial=True)` and keep stdout/out behavior alive at the CLI layer (`REWRITE-SPEC §7-§8`, gotcha #3/#4).

This flow fixes `cdp-send-noop-returns-stale-response` by making a new user turn the send acknowledgement and a newer assistant turn the completion acknowledgement. It also avoids treating transient composer unmounts as fatal and reloads only when idle to clear SPA staleness (`REWRITE-SPEC §6`; `controller.mjs`).

## 7. `menus.py`: label-driven Radix mechanism

All model/tool actions use one mechanism (`REWRITE-SPEC §11`; `M2 handoff`):

1. Find the trigger. Tools use `button[data-testid="composer-plus-btn"]`. Model picker uses the composer-footer `button[aria-haspopup="menu"]` whose visible label matches/contains the current model; M2 observed no stable test id or aria label, so this remains heuristic and fail-closed.
2. Click the trigger, then enumerate visible options only inside `[data-radix-popper-content-wrapper]`.
3. Normalize labels by collapsing whitespace and stripping keyboard-hint suffixes where necessary, but preserve display labels for verification/logging.
4. For model tiers, select `role="menuitemradio"` labels such as `Instant`, `Medium`, `High`, `Extra High`, `Pro Extended`. For model families, select a `role="menuitem"` submenu label such as `GPT-5.5`, then a submenu radio such as `5.5`, `5.4`, `5.3`, `4.5 Leaving on June 26`, or `o3` (observed labels from M2).
5. For tools, select labels such as `Deep research` or `Web search` from the `+` menu. The `More` submenu may expose `Agent mode`, `Create task`, `Figma`, `Finances`, `GitHub`, and `OpenAI Platform`; do not open `Recent files` or `Projects` submenus because those may reveal private names (`M2 handoff`).
6. Verify reflected state before returning: model label must equal/include the requested display label; tool state must be visible as an active chip/state or re-enumerated checked/toggled state. If verification cannot prove the requested state, raise `MenuVerificationError` and do not send.

This makes Pro Extended and Deep Research normal labels, not hard-coded workflows. Deep Research is recorded as `active_tools=["deep_research"]` and `kind="deep_research"` only when capture evidence shows a DR/pro-style turn group or metadata; there is no `content_type == "deep_research"` (`M2 handoff`).

## Cross-cluster interfaces & dependencies

Exposed to all clusters: `Session` signatures in §1; dataclasses/JSON field names in §2; `BrowserChannel` Protocol in §5; selector keys in §4; stable error codes in `errors.py`; and the rule that only `Session` owns tab pool/rate budget. Other modules receive `BrowserTab`, `Store`, `SelectorMap`, and `ConversationRef`, never raw Playwright browser/context objects.

Needed from persistence/lens 2: final JSONL handling for `client_send_id` pending-send collapse, atomic append/upsert semantics, markdown export ordering, sidecar/index exact schema, attachment path hashing, and recovery behavior for corrupt/partial JSONL. Lens 1 requires that `TurnResult.to_json()` field names stay aligned with §2.

Needed from capture/lens 3: exact backend header-acquisition implementation, streaming/spooling strategy for measured ~17.1 MB/~5k-node responses, current-branch linearization rules, DR/pro `kind` inference, citation normalization, attachment-ref extraction, and fail-closed fidelity tests against UI copy/KaTeX/DOM (`M2 handoff`).

Needed from concurrency/lens 4: internal tab-pool algorithms, idle eviction, LRU reclaim, adaptive send-rate/backoff, numeric politeness default, and how `Session.loop()` coordinates concurrent sends while preserving the single owner boundary (`REWRITE-SPEC §10`).

Needed from CLI/testing/later clusters: exact CLI flag names and stdout/`--out` ordering, mock fixtures that exercise no-op send and long completion, M5 real-site verification of project create/send, send-button-after-input selector, and any `stream_status` endpoint.

## Open questions / assumptions

Project behavior is an assumption: this design parses `/g/g-p-<project_id>/c/<conversation_id>` and exposes `create(project=...)`, but M2 explicitly deferred project probing, so M5 must verify project create/send before claiming support (`M2 handoff`).

`GET /backend-api/conversation/<id>/stream_status` is only a completion hypothesis; `completion.py` must rely first on the authenticated conversation endpoint fields M2 observed (`async_status`, metadata `is_complete`/`is_finalizing`/`pro_progress`, node `status`) until M5 verifies any stream-status endpoint (`M2 handoff`).

The exact numeric send politeness floor and adaptive backoff triggers are not measured in M2. The API leaves the knob explicit and assigns ownership to the concurrency/rate design; there must be no hard message cap (`M3 common §2`).

Attachment byte-download routes were not observed; M2 saw ids, asset pointers, and metadata but no literal `/backend-api/files/...`, `sandbox:`, or `attachment:` URLs. `fetch()` must remain lazy and fail closed until M5/later verifies concrete byte routes (`M2 handoff`).

Clipboard copy fallback cannot be unattended because permission state was `prompt`; it may be used only with explicit permission/user gesture or as an operator-attended fallback, never as a required automation path (`M2 handoff`).

The model picker trigger is heuristic because M2 found no stable data-testid/aria label. Selector drift must fail closed, and M5 should update `selectors/real.json` if a stable trigger appears (`M2 handoff`).

The send button selector was not directly observed after entering text in M2; `send_button_unverified_no_input` is the best observed selector family and must be verified during M5 send work before declaring real send support (`M2 handoff`).

Using `default_activity_timeout_s=600.0` is an explicit no-activity default, not a total wall-clock ceiling; if backend progress for DR/Pro can pause longer than this without observable changes, M5/M7 should adjust the default or require CLI callers to set `--timeout` for those runs.
