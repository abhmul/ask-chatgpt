STATUS: DONE — V2/V3 panel fixes applied

This design integrates the five M3 lenses into one implementable v2 contract: a Python library core with a thin CLI and a persistent `Session` that owns tool-opened tabs and the send budget; UI-only actions, backend-api canonical capture with transient web-app headers, JSONL persistence, verified send/completion, fail-closed fidelity fallbacks, and modest shared-browser concurrency are all specified as one coherent flow. The design honors M2's live-site facts, the four gotcha fixes, and the safety invariants from `REWRITE-SPEC §13`/team charter; the only remaining blockers are explicitly M5/M7 live-confirmation items such as project send/create, exact completion status vocabularies, attachment byte-download routes, `stream_status`, send-button-after-input behavior, and measured send-rate defaults.

# 1. Architecture overview

The rewrite is `library-core + thin CLI + persistent Session; no daemon` (`REWRITE-SPEC §2`). Atomic CLI calls construct a short-lived `Session`, preflight CDP, attach, perform one operation, detach, and never quit the operator browser; loops and multi-conversation/concurrent use hold one persistent `Session`, which is the single owner of the managed tab pool and account send-rate budget (`REWRITE-SPEC §2`, `§10`; agent-rigor shared-resource ceiling). Actions go through the real ChatGPT UI: send, create, model/tool selection, and file upload are never forged as backend requests. Reads/capture use the page's own authenticated backend conversation endpoint as the primary source of canonical markdown, because M2 confirmed `GET https://chatgpt.com/backend-api/conversation/<conversation_id>` returns faithful JSON only when the web-app request headers are forwarded; cookies-only/accept-only returned 404 (`M2 handoff`). Every real browser leg is operator-attended CDP attach to `http://127.0.0.1:9222`, uses only tool-opened tabs, never iterates operator tabs, never automates login/Cloudflare, applies the domain allowlist, and never persists/logs Authorization/OAI header values (`REWRITE-SPEC §13`; M3 common constraints).

Primary `ask` flow: resolve identity → acquire a tool-owned tab → idle-reload → verify requested model/tools → read send baseline → eager-write pending prompt → fill/submit composer → verify a new user turn carrying the prompt → wait for a newer assistant turn with backend polling primary and DOM consensus fallback → capture canonical backend markdown → append/upsert JSONL + raw mapping → print stdout and optionally `--out`. Primary `scrape` flow: resolve/open own tab → acquire the page's own backend headers → stream backend JSON to `raw-mapping.json` → linearize the current branch into `transcript.jsonl` → render markdown to stdout and optional `--out`. Store-only `history/export` never preflights or touches the browser.

# 2. Module list, responsibilities, and key signatures

## 2.1 Canonical public data model

The seam is one object: `TurnRecord`. `capture.py` emits it, `store.py` serializes one JSONL line from it, and `Session.ask` returns the new assistant `TurnRecord`; there is no separate `AskResult` field set to drift from persistence. The core seam fields required by the contract are mandatory on every backend-derived visible turn: `message_id`, `parent_id`, `content_markdown`, `model{slug,display}`, `active_tools`, `kind`, `created_at`, `attachments`, `citations`, `status`, and `partial`. Additional context/operation fields are also part of the same serialized/returned record, not a second schema.

```python
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
TurnStatus = Literal["complete", "partial", "error"]
TurnRole = Literal["user", "assistant"]
CaptureSource = Literal["backend_api", "copy_button", "katex_annotation", "dom_text"]
CaptureFidelity = Literal["canonical", "ui_copy", "math_annotation_reconstructed", "lossy_dom_text"]

@dataclass(frozen=True)
class ModelRef:
    slug: str | None
    display: str | None

@dataclass(frozen=True)
class AttachmentRef:
    source_kind: Literal["user_upload", "file_reference", "generated_asset", "code_execution_output", "unknown"]
    source_ref: str | None              # file id, content-reference id, asset_pointer, run_id, or null
    raw_path: str                       # JSON Pointer into raw-mapping.json
    filename: str | None
    mime: str | None
    bytes: int | None
    sha256: str | None
    local_path: str | None              # relative to conversation dir; null until lazy fetch succeeds
    download_state: Literal["pending", "downloaded", "not_downloadable", "unsupported", "error"]
    metadata: Mapping[str, JsonValue]   # sanitized; no auth/OAI headers

@dataclass(frozen=True)
class CitationRef:
    title: str | None
    url: str | None
    source: Literal["citations", "content_references", "search_result_groups", "unknown"]
    citation_type: str | None
    start_ix: int | None
    end_ix: int | None
    citation_format_type: str | None
    raw_path: str
    metadata: Mapping[str, JsonValue]   # sanitized nested citation metadata

@dataclass(frozen=True)
class TurnRecord:
    conversation_id: str
    conversation_url: str
    project_id: str | None
    message_id: str                     # backend/DOM id; only pending eager-write may use local:<client_send_id>
    parent_id: str | None               # raw mapping parent id; may point to a hidden node
    turn_index: int | None              # current-branch visible order; null only for pending local stubs
    role: TurnRole
    content_markdown: str
    model: ModelRef | None
    active_tools: tuple[str, ...]
    kind: str                           # normal, deep_research, image, code_execution, file_reference, unknown, ...
    created_at: datetime | None         # backend timestamp; never agent wall clock except null pending
    attachments: tuple[AttachmentRef, ...]
    citations: tuple[CitationRef, ...]
    status: TurnStatus
    partial: bool
    user_message_id: str | None = None  # populated on assistant records returned by ask
    turn_exchange_id: str | None = None
    client_send_id: str | None = None
    supersedes_message_id: str | None = None
    capture_source: CaptureSource = "backend_api"
    fidelity: CaptureFidelity = "canonical"
    error: Mapping[str, JsonValue] | None = None

@dataclass(frozen=True)
class Transcript:
    conversation: "ConversationRef"
    turns: tuple[TurnRecord, ...]
    raw_mapping_path: Path | None
    transcript_path: Path | None

class SelectorMap(TypedDict):
    composer: str
    tools_button: str
    message_turn: str
    user_turn: str
    assistant_turn: str
    copy_button: str
    stop_button: str
    send_button_unverified_no_input: str
    radix_portal: str
    model_picker_trigger_candidates: str

@dataclass(frozen=True)
class SendTimeouts:
    idle_wait_s: float
    composer_wait_s: float
    submit_verify_s: float
    attachment_upload_s: float

@dataclass(frozen=True)
class AttachmentSpec:
    path: Path
    display_name: str | None = None
    mime: str | None = None

@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    cdp_endpoint: str
    browser: str | None
    protocol_version: str | None
    websocket_url_present: bool
    error_code: str | None = None
    error: str | None = None

@dataclass(frozen=True)
class StatusReport:
    ok: bool
    cdp: PreflightResult | None
    signed_in: bool | None
    login_or_challenge: bool | None
    selector_valid: bool
    conversations: int | None
    blocking_code: str | None
    details: Mapping[str, JsonValue]
```

`partial` must be `False` iff `status == "complete"`. Backend-derived records use the canonical backend `message.id` when present, otherwise the mapping node id; M5 must verify equivalence with DOM `data-message-id` for visible turns. The only non-canonical `message_id` is a pending eager-write stub `local:<client_send_id>` before the browser/backend exposes the new user-turn id. Pending eager-write stubs use `turn_index=None`, `created_at=None`, `status="partial"`, and `partial=true`; they contain the prompt as a durable outbox/salvage record, not a verified ChatGPT turn. The later canonical user record sets `supersedes_message_id` so readers hide the stub by default; unsuperseded pending stubs are also hidden from default `history`/`export` reads and surfaced only by `include_pending=True`/`--include-pending`-style reads and `status` diagnostics, so an unsubmitted prompt never appears as a real turn. This is the simplest reconciliation of the canonical-id schema with the lose-nothing eager-write invariant (`REWRITE-SPEC §6`, `§8`; gotcha #3).

## 2.2 `session.py`

Responsibility: public facade, lifecycle, orchestration, and sole ownership of `Store`, `BrowserChannel`, `TabPool`, and `AdaptiveSendBudget`. Public API is synchronous for CLI/agent ergonomics; an implementation may run Playwright via sync APIs or a private event loop, but async machinery is not exposed in M4/M5.

```python
class Session:
    def __init__(self, *, cdp_endpoint: str = "http://127.0.0.1:9222", data_dir: str | Path | None = None, channel: Literal["mock", "cdp"] = "cdp", selector_map: str | Path | Mapping[str, str] | None = None, max_active_tab_ops: int = 3, max_tabs: int = 3, activity_timeout_s: float = 600.0, max_total_wait_s: float | None = None, send_verify_timeout_s: float = 30.0, composer_wait_timeout_s: float = 20.0, progress_poll_interval_s: float = 2.0, backend_check_interval_s: float | None = None, strict_selectors: bool = True) -> None: ...
    def attach(self) -> "Session": ...
    def detach(self, *, close_managed_tabs: bool = True) -> None: ...
    def __enter__(self) -> "Session": ...
    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None: ...
    def create(self, project: str | None = None) -> ConversationRef: ...
    def ask(self, conv_or_url: str | ConversationRef | None, prompt: str, *, model: str | None = None, tools: Sequence[str] = (), attach: Sequence[str | Path | AttachmentSpec] = (), timeout: float | None = None, max_total_wait: float | None = None, out: str | Path | None = None) -> TurnRecord: ...
    def scrape(self, conv_or_url: str | ConversationRef, *, with_attachments: bool = False, out: str | Path | None = None) -> Transcript: ...
    def history(self, conv_or_url: str | ConversationRef) -> Transcript: ...
    def fetch(self, conv_or_url: str | ConversationRef, attachment_ref: str) -> Path: ...
    def loop(self, conv_or_url: str | ConversationRef, *, message: str = "keep pushing!!", model: str | None = None, tools: Sequence[str] = (), attach: Sequence[str | Path | AttachmentSpec] = (), timeout: float | None = None, max_total_wait: float | None = None, max_iterations: int | None = None, out_dir: str | Path | None = None) -> Iterator[TurnRecord]: ...
    def status(self, conv_or_url: str | ConversationRef | None = None, *, probe_browser: bool = True) -> StatusReport: ...
```

`attach()` performs CDP preflight before real CDP use; `detach()` disconnects/optionally closes only tool-owned tabs and never quits Chromium (`REWRITE-SPEC §13`). Browser-touching methods implicitly attach for atomic CLI calls. `history()` is store-only and must not preflight CDP. `Session` passes channel-bound `TabLease` objects to lower modules; lower modules reach browser operations only through `tab.channel.*`. No lower module may create a connection, enumerate browser pages, or own a rate limiter.

## 2.3 `capture.py`

Responsibility: canonical backend capture, safe auth/OAI header harvesting, streaming raw response persistence, current-branch normalization, attachment/citation extraction, and fail-closed UI/annotation fallback.

```python
REQUIRED_CAPTURE_HEADERS: tuple[str, ...] = ("authorization", "oai-client-build-number", "oai-client-version", "oai-device-id", "oai-language", "oai-session-id", "x-openai-target-path", "x-openai-target-route")

@dataclass(frozen=True, repr=False)
class HeaderBundle:
    conversation_id: str
    source: Literal["web_app_request"]
    acquired_at_monotonic: float
    _headers: Mapping[str, str]
    def for_single_fetch(self) -> Mapping[str, str]: ...
    def redacted(self) -> Mapping[str, JsonValue]: ...

@dataclass(frozen=True)
class CaptureResult:
    transcript: Transcript
    async_status: str | None
    raw_top_level_keys: tuple[str, ...]
    source: CaptureSource
    fidelity: CaptureFidelity

@dataclass(frozen=True)
class BackendFetchMeta:
    raw_tmp: Path
    status: int
    content_type: str | None
    bytes_written: int
    elapsed_s: float | None

@dataclass(frozen=True)
class BackendTopLevel:
    raw_path: Path
    conversation_id: str
    current_node: str
    async_status: str | None
    update_time: str | int | float | None
    default_model_slug: str | None
    top_level_keys: tuple[str, ...]
    mapping_node_count: int

@dataclass(frozen=True)
class SendContext:
    client_send_id: str | None
    user_message_id: str | None
    model: ModelRef | None
    active_tools: tuple[str, ...]

def acquire_backend_headers(tab: TabLease, conv: ConversationRef, *, timeout_s: float = 30.0) -> HeaderBundle: ...
def stream_backend_conversation(tab: TabLease, conv: ConversationRef, headers: HeaderBundle, *, raw_tmp: Path) -> BackendFetchMeta: ...
def validate_backend_shape(raw_path: Path, expected_conversation_id: str) -> BackendTopLevel: ...
def iter_current_branch_records(raw_path: Path, conv: ConversationRef, *, send_context: SendContext | None = None) -> Iterator[TurnRecord]: ...
def capture_conversation(tab: TabLease, conv: ConversationRef, store: Store, *, with_attachments: bool = False, send_context: SendContext | None = None) -> CaptureResult: ...
def fallback_capture_ui(tab: TabLease, conv: ConversationRef, store: Store, *, reason: str, allow_clipboard: bool = False) -> CaptureResult: ...
```

`HeaderBundle` is a per-backend-request bearer/OAI container: acquire it, call `for_single_fetch()` for exactly one capture fetch or one sparse authoritative completion check, and discard the local copy immediately after that request returns or raises. No long-lived header reference is held across a `wait_for_completion` loop; only redacted progress state such as ids, text lengths, hashes, status flags, and timing tokens may persist across the wait. Reacquisition is non-intrusive: `acquire_backend_headers` reads from the tool's own already-registered same-tab request observer, the listener that first captured the page's `/backend-api/conversation/<id>` request and refreshes on subsequent same-origin backend calls from that tool-owned tab; it must not re-navigate or reload merely to refresh headers. Fine-grained progress checks use cheap own-tab DOM signals and need no headers. Values must never appear in `repr`, logs, exceptions, `raw-mapping.json`, `transcript.jsonl`, status reports, fixtures, or any file on disk. Capture obtains headers by observing only the tool-owned page's own matched `/backend-api/conversation/<id>` request; it does not scrape storage/app globals.

## 2.4 `send.py`

Responsibility: UI-only prompt submission and attachment upload, including baseline/new-turn verification and composer staleness handling.

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

def wait_for_idle_and_reload_if_needed(tab: TabLease, selectors: SelectorMap, *, timeout_s: float) -> None: ...
def read_turn_baseline(tab: TabLease, selectors: SelectorMap) -> TurnBaseline: ...
def wait_for_composer(tab: TabLease, selectors: SelectorMap, *, timeout_s: float) -> None: ...
def upload_attachments(tab: TabLease, selectors: SelectorMap, files: Sequence[AttachmentSpec]) -> tuple[AttachmentRef, ...]: ...
def fill_composer(tab: TabLease, selectors: SelectorMap, prompt: str) -> None: ...
def submit_composer(tab: TabLease, selectors: SelectorMap) -> None: ...
def verify_prompt_submitted(tab: TabLease, selectors: SelectorMap, baseline: TurnBaseline, prompt: str, *, timeout_s: float) -> SubmittedTurn: ...
def send_prompt(tab: TabLease, selectors: SelectorMap, prompt: str, *, model: str | None, tools: Sequence[str], attach: Sequence[AttachmentSpec], timeouts: SendTimeouts) -> SubmittedTurn: ...
```

`send_prompt` cannot return success until a new user turn with a different/latest id or increased user count carries the normalized prompt. If absent, raise `PromptNotSubmittedError` and never return a stale assistant reply (`REWRITE-SPEC §6`; gotcha #2).

## 2.5 `completion.py`

Responsibility: wait for a response newer than the send baseline, with cheap progress checks plus sparse backend-api authoritative checks, DOM consensus fallback, no hidden total ceiling, and salvage support.

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
    last_progress_monotonic: float

def poll_backend_completion(tab: TabLease, conv: ConversationRef, baseline: TurnBaseline, *, prefer_lightweight: bool = True) -> CompletionState: ...
def poll_dom_progress(tab: TabLease, selectors: SelectorMap, baseline: TurnBaseline) -> CompletionState: ...
def poll_dom_completion(tab: TabLease, selectors: SelectorMap, baseline: TurnBaseline, *, stable_window_s: float) -> CompletionState: ...
def wait_for_completion(tab: TabLease, conv: ConversationRef, selectors: SelectorMap, baseline: TurnBaseline, *, activity_timeout_s: float, max_total_wait_s: float | None, progress_poll_interval_s: float = 2.0, backend_check_interval_s: float | None = None) -> CompletionState: ...
def salvage_partial(tab: TabLease, conv: ConversationRef, baseline: TurnBaseline, *, backend_partial: CompletionState | None) -> TurnRecord | None: ...
```

`poll_backend_completion` acquires a fresh `HeaderBundle` internally for exactly one backend request and discards it immediately; callers never pass or retain header values across the loop. `activity_timeout_s` is a no-activity window reset by progress; `max_total_wait_s=None` is unbounded (`REWRITE-SPEC §7`; gotcha #3). `progress_poll_interval_s` drives only cheap own-tab progress checks; sparse backend checks use `backend_check_interval_s` after M5 measurement (`None` means the measured channel default/mock override), not the short DOM cadence. Completion is invalid unless the assistant id is newer than `baseline.latest_assistant_id`.

## 2.6 `menus.py`

Responsibility: general label-driven Radix menu interaction for model picker and tools, including verification before send.

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

def open_radix_menu(tab: TabLease, trigger_selector: str) -> None: ...
def enumerate_radix_options(tab: TabLease) -> tuple[MenuOption, ...]: ...
def select_radix_label(tab: TabLease, label: str, *, role: str | None = None, submenu_path: Sequence[str] = ()) -> MenuOption: ...
def select_model(tab: TabLease, selectors: SelectorMap, label: str) -> SelectionResult: ...
def set_tools(tab: TabLease, selectors: SelectorMap, labels: Sequence[str]) -> tuple[SelectionResult, ...]: ...
def assert_reflected_model(tab: TabLease, selectors: SelectorMap, label: str) -> None: ...
def assert_reflected_tools(tab: TabLease, selectors: SelectorMap, labels: Sequence[str]) -> None: ...
```

Selectors use M2 facts: tools trigger `button[data-testid="composer-plus-btn"]`; model picker has no stable data-testid/aria label, so the executable trigger selector is `composer-footer button[aria-haspopup="menu"]` plus a fail-closed visible-label match. `select_model` enumerates those candidate buttons, requires exactly one whose normalized text equals the known current-model label, clicks it, enumerates only `[data-radix-popper-content-wrapper]`, selects an exact `menuitemradio` or family `menuitem`→radio label, then verifies the composer-footer label reflects the target before any send. Do not open `Recent files` or `Projects` submenus because M2 identified private-name leak risk. Full menu exercise is M7; until then requested model/tool changes fail closed.

## 2.7 `store.py`

Responsibility: data-dir resolution, per-conversation layout, append-only JSONL, raw mapping atomic replace, index/alias handling, markdown rendering, attachment cache, eager-write pending stubs, partial salvage records, and last-writer-wins reads.

```python
@dataclass(frozen=True)
class ConversationPaths:
    root: Path
    transcript_jsonl: Path
    raw_mapping_json: Path
    attachments_dir: Path
    gitignore: Path

class Store:
    def __init__(self, data_dir: str | Path | None = None, *, env: Mapping[str, str] = os.environ) -> None: ...
    def resolve_data_dir(self) -> Path: ...
    def ensure_conversation(self, ref: ConversationRef) -> ConversationPaths: ...
    def put_conversation_ref(self, ref: ConversationRef) -> None: ...
    def resolve_conversation(self, address: str | ConversationRef) -> ConversationRef: ...
    def begin_send(self, ref: ConversationRef, prompt: str, *, model: ModelRef | None, active_tools: Sequence[str]) -> TurnRecord: ...
    def commit_send(self, client_send_id: str, canonical_user: TurnRecord) -> None: ...
    def upsert_turn(self, record: TurnRecord) -> None: ...
    def upsert_many(self, records: Iterable[TurnRecord]) -> None: ...
    def write_raw_mapping_atomic(self, conversation_id: str, raw_tmp: Path) -> Path: ...
    def load_transcript(self, address: str | ConversationRef, *, include_pending: bool = False) -> Transcript: ...
    def render_markdown(self, transcript: Transcript) -> str: ...
    def atomic_write_payload(self, out: str | Path, content: str | bytes) -> Path: ...
    def record_partial(self, ref: ConversationRef, *, client_send_id: str | None, partial_markdown: str, error: BaseException) -> TurnRecord: ...
    def attachment_path(self, conversation_id: str, ref: AttachmentRef) -> Path: ...
```

`store.py` never receives auth/OAI headers. It may store transcript content and raw backend JSON, which are user data, but must avoid logging prompt/response bodies except as intentional output/transcript.

## 2.8 `identity.py`

Responsibility: stateless parsing of bare ids, plain conversation URLs, project conversation URLs, aliases, and canonical backend/web URLs.

```python
@dataclass(frozen=True)
class ConversationRef:
    conversation_id: str | None          # null only for draft create before first server id
    url: str
    project_id: str | None = None
    title: str | None = None
    current_node: str | None = None
    default_model_slug: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_draft: bool = False

def parse_conversation_address(value: str) -> ConversationRef | None: ...
def parse_project_address(value: str) -> str | None: ...
def conversation_url(ref: ConversationRef) -> str: ...
def backend_conversation_url(conversation_id: str) -> str: ...
def normalize_conversation_id(value: str) -> str: ...
def resolve_conv_or_alias(value: str | ConversationRef, store: Store) -> ConversationRef: ...
```

Supported URL shapes are `https://chatgpt.com/c/<conversation_id>` and `https://chatgpt.com/g/g-p-<project_id>/c/<conversation_id>` (`REWRITE-SPEC §9`). Project send/create is treated as a near-term assumption because M2 did not probe project URLs.

## 2.9 `channels/{base,mock,cdp}.py`

Responsibility: the browser seam enabling mock-first tests and attended CDP real use. Production modules call only this Protocol, never Playwright directly.

```python
@dataclass(frozen=True)
class TabLease:
    tab_id: str
    url: str
    channel: "BrowserChannel"

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
    body_path: Path | None
    body_bytes: bytes | None

class BrowserChannel(Protocol):
    def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult: ...
    def attach(self) -> None: ...
    def detach(self) -> None: ...
    def open_tab(self, url: str) -> TabLease: ...
    def close_tab(self, tab: TabLease) -> None: ...
    def reload(self, tab: TabLease) -> None: ...
    def wait_for_load_state(self, tab: TabLease, *, timeout_s: float) -> None: ...
    def evaluate(self, tab: TabLease, js: str, *, arg: JsonValue | None = None, timeout_s: float | None = None) -> JsonValue: ...
    def wait_for_selector(self, tab: TabLease, selector: str, *, state: Literal["attached", "visible"] = "visible", timeout_s: float) -> None: ...
    def fill(self, tab: TabLease, selector: str, text: str) -> None: ...
    def insert_text(self, tab: TabLease, selector: str, text: str) -> None: ...
    def click(self, tab: TabLease, selector: str) -> None: ...
    def hover(self, tab: TabLease, selector: str) -> None: ...
    def press(self, tab: TabLease, selector: str, key: str) -> None: ...
    def query_turns(self, tab: TabLease, selectors: SelectorMap) -> TurnDomSnapshot: ...
    def wait_for_request(self, tab: TabLease, predicate: Callable[[RequestSnapshot], bool], *, timeout_s: float) -> RequestSnapshot: ...
    def fetch_in_page(self, tab: TabLease, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, body: bytes | str | None = None, stream_to: Path | None = None, timeout_s: float | None = None) -> FetchResult: ...
    def read_clipboard(self, tab: TabLease) -> str: ...
    def upload_files(self, tab: TabLease, selector: str, paths: Sequence[Path]) -> None: ...
```

`CdpChannel` attaches to an already-running browser only after `/json/version` succeeds, creates only tool-owned targets, returns `TabLease(channel=self, ...)` from `open_tab`, never calls Playwright launch, never iterates `context.pages`, allowlist-checks all navigation/fetches, and detaches without quitting Chromium. `MockChannel` simulates backend 404 without headers, 200 with required headers, M2 role/content shapes, large DR `turn_exchange_id` groups, math markdown tokens, selector drift, no-op send, composer unmount/remount, long-running completion progress, Radix menus, clipboard permission `prompt`, login/challenge stops, and allowlist rejection.

## 2.10 `selectors/`

Responsibility: fail-closed selector maps. `selectors/real.json` must include the M2-observed concrete selectors plus the Radix portal key and executable model-picker candidate selector; missing required keys are startup/config errors in strict mode.

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
  "model_picker_trigger_candidates": "composer-footer button[aria-haspopup=\"menu\"]"
}
```

M2 found no stable model-picker test id or aria label. The executable rule is therefore not a single trusted selector: enumerate `model_picker_trigger_candidates`, match the visible text to the known current model label, fail closed on zero/multiple matches, use only `radix_portal` for options, and verify the reflected footer label after selection.

## 2.11 `errors.py`, `allowlist.py`, and `cli.py`

`errors.py` defines named redacted exceptions and stable CLI/status codes. `allowlist.py` centralizes URL validation for navigation and fetch. `cli.py` is a thin parser/output/error-mapping layer over `Session` and contains no business logic.

```python
DEFAULT_ALLOWED_HOST_SUFFIXES = ("chatgpt.com", ".chatgpt.com", "openai.com", ".openai.com", "oaiusercontent.com", ".oaiusercontent.com", "oaistatic.com", ".oaistatic.com")

@dataclass(frozen=True)
class Allowlist:
    host_suffixes: tuple[str, ...] = DEFAULT_ALLOWED_HOST_SUFFIXES
    def is_allowed_url(self, url: str) -> bool: ...
    def require_allowed_url(self, url: str) -> None: ...
    def sanitize_for_log(self, url: str) -> str: ...

def main(argv: Sequence[str] | None = None) -> int: ...
```

# 3. JSONL transcript schema, data-dir layout, and linearization

## 3.1 Data-dir layout

Data root resolution: CLI `--data-dir` wins, then `ASK_CHATGPT_DATA_DIR`, then `~/.local/state/ask-chatgpt/` (`REWRITE-SPEC §8`). Directories should be created with user-private permissions where supported because transcripts and raw mapping contain conversation data.

```text
<data-dir>/
  index.json
  conversations/
    <conversation-id>/
      transcript.jsonl
      raw-mapping.json
      attachments/
      .gitignore
```

`index.json` is a convenience cache of aliases/session names and known conversation metadata; URL or bare id addressing remains stateless. `transcript.jsonl` is append-only visible current-branch history plus pending/salvage updates. `raw-mapping.json` is the latest complete backend response, including all top-level keys and full `mapping`, with no request headers. `attachments/` is lazy local byte cache and `.gitignore` contains `attachments/`.

## 3.2 `index.json`

```json
{
  "schema_version": 1,
  "aliases": {"math-long": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"},
  "sessions": {"last": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"},
  "conversations": {
    "6a316aa8-5dc8-83ea-9014-b8ea38dabc31": {
      "conversation_id": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31",
      "url": "https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31",
      "project_id": null,
      "title": "string|null",
      "model": {"slug": "string|null", "display": "string|null"},
      "current_node": "string|null",
      "last_updated": "backend update_time as RFC3339|null"
    }
  }
}
```

Index corruption is non-fatal; rebuild from conversation directories when possible. `last_updated` comes from backend `update_time` when available, not agent wall-clock.

## 3.3 `transcript.jsonl` record

Each line is UTF-8 JSON serialization of `TurnRecord`, with field names matching the dataclass. Required fields are always present; values may be null only where the type allows. Backend-derived records are complete only after canonical capture succeeds.

| Field | Type | Semantics |
|---|---|---|
| `conversation_id` | string | Canonical key, the `<id>` in `/c/<id>` or project `/g/g-p-<project_id>/c/<id>` (`REWRITE-SPEC §9`). |
| `conversation_url` | string | Canonical web URL used for reopening; project URL when `project_id` is known. |
| `project_id` | string|null | Parsed/stored project id; project send/create not M2-verified. |
| `message_id` | string | Backend/DOM id; `local:<client_send_id>` only for pending eager-write stubs. |
| `parent_id` | string|null | Raw mapping parent id, even if hidden. |
| `turn_index` | integer|null | Current-branch visible order; null only for pending stubs. |
| `role` | `user` or `assistant` | Only visible transcript roles; hidden tool/system/thought/code nodes remain raw. |
| `content_markdown` | string | Canonical untruncated markdown when backend source; lossy fallback content is marked by `capture_source`/`fidelity`/`partial`. |
| `model` | object|null | `{slug, display}`; slug from backend metadata/default where available, display from verified UI send state where known. |
| `active_tools` | string[] | Tools orthogonal to model, e.g. `deep_research`, `web_search`, `create_image`. |
| `kind` | string | `normal`, `deep_research`, `image`, `code_execution`, `file_reference`, `unknown`, or later string. |
| `created_at` | RFC3339 string|null | Backend message timestamp; never an agent self-report. |
| `attachments` | AttachmentRef[] | Downloadable/materializable refs from M2 shapes; bytes lazy. |
| `citations` | CitationRef[] | DR/web/source references; never fetched by `fetch`. |
| `status` | `complete`/`partial`/`error` | Completion/persistence status; pending eager-write stubs use `partial`. |
| `partial` | boolean | Redundant consumer convenience; true iff not complete, including pending stubs. |
| `user_message_id` | string|null | On assistant results returned by `ask`, the verified submitted user id. |
| `turn_exchange_id` | string|null | Backend grouping for DR/Pro and hidden internals. |
| `client_send_id` | string|null | Local UUID/ULID for one send attempt. |
| `supersedes_message_id` | string|null | Canonical record hides a pending local stub. |
| `capture_source` | string | `backend_api`, `copy_button`, `katex_annotation`, or `dom_text`. |
| `fidelity` | string | `canonical`, `ui_copy`, `math_annotation_reconstructed`, or `lossy_dom_text`. |
| `error` | object|null | Redacted code/details for partial/error records; no tokens/headers. |

Read semantics: parse lines in order, ignore at most one trailing invalid partial line after a crash with a warning, group by `message_id`, keep the last valid record for each id, hide pending local stubs (`message_id` starts `local:` and `turn_index is null`) from default `history`/`export` reads whether superseded by later `supersedes_message_id` or still unsuperseded, and surface them only when `include_pending=True`/`--include-pending`-style reads or `status` diagnostics explicitly ask. Then sort by `(turn_index is null, turn_index, created_at or "", message_id)`. Re-scrape is idempotent because it appends corrected complete records and reads are last-writer-wins.

## 3.4 Atomic writes and lose-nothing discipline

| Operation | Mechanic | Crash result |
|---|---|---|
| Ensure layout | `mkdir(parents=True, exist_ok=True)` and create `.gitignore` if absent. | Existing files untouched. |
| Append JSONL | Per-conversation advisory lock; one compact JSON object per line; flush and fsync before unlock. | Prior complete lines survive; reader ignores a trailing torn line. |
| Replace raw mapping | Stream to `raw-mapping.json.tmp.<pid>`, fsync, validate/parse shape, `os.replace`, fsync parent dir. | Old raw remains or new raw complete; never half-replaced. |
| Replace index | Lock, read/init, patch, write temp, fsync, rename, fsync parent. | Old or new index complete; index rebuildable. |
| Write `--out` | Temp file in same directory, flush/fsync, rename. | Stdout still printed; store already durable. |
| Fetch attachment bytes | Write `attachments/<name>.partial`, verify size/hash when known, rename to `attachments/<sha256>__<safe-name>`, append replacement record with `local_path`. | Partial file cleanup later; transcript points to pending until success. |

`ask` lifecycle: persist `ConversationRef` before send; append pending user stub immediately before UI submission; after new user turn verification append canonical user record superseding the stub; after completion/capture append complete assistant record; on timeout/error append salvaged assistant record with `partial=true` and a redacted error. This directly fixes the truncation/session-loss gotcha (`REWRITE-SPEC §8`, `§17`).

## 3.5 Current-branch linearization and visible-vs-hidden classification

Backend `mapping` is a message tree keyed by node id, and `current_node` identifies the UI branch leaf (`M2 handoff`). Linearization follows parent links from `current_node` to root, reverses the path, and emits only visible records; raw mapping retains side branches and hidden internals.

```python
def iter_current_branch_node_ids(raw: Mapping[str, JsonValue]) -> list[str]:
    mapping = raw["mapping"]
    node_id = raw.get("current_node")
    branch: list[str] = []
    seen: set[str] = set()
    while node_id:
        if node_id in seen:
            raise BackendShapeUnrecognizedError("cycle in mapping parent chain")
        seen.add(node_id)
        branch.append(node_id)
        node_id = mapping[node_id].get("parent")
    return list(reversed(branch))
```

Classification is deliberately small and matches M2 observations: `user:text` is visible and extracts string `content.parts`; `assistant:text` is visible and extracts string `content.parts`; `assistant:code`, `assistant:thoughts`, `assistant:reasoning_recap`, `assistant:model_editable_context`, all `tool:*`, and `system:text` are hidden in the linear transcript unless a later live probe proves a UI-visible counterexample. Hidden nodes may contribute attachment refs, citation refs, progress/status, `turn_exchange_id` grouping, and summaries, but not standalone transcript text. This keeps user-facing history faithful to what the UI shows while retaining all raw data (`REWRITE-SPEC §8`; M2 handoff).

For `content.parts`, exact rule is: if the list has one string, use `parts[0]`; if multiple strings, concatenate the strings without inserting separators and retain exact part boundaries in `raw-mapping.json`; non-string parts are a backend shape error and trigger fail-closed fallback. M5 must compare multi-part messages against UI copy if encountered. This chooses Lens 3's no-invented-separator rule over Lens 2's blank-line join assumption because M2 did not establish separators.

## 3.6 Deep Research / Pro turns

There is no `content_type == "deep_research"` (`M2 handoff`). DR/Pro is represented as a `turn_exchange_id` group containing one user message, many hidden assistant/tool/code/thought nodes, and one visible final `assistant:text` report whose body was observed in `message.content.parts[0]`. The transcript emits the visible user record and the visible final assistant record. The assistant record gets `kind="deep_research"` and `active_tools` including `deep_research` when either the send context verified the Deep research tool or scrape-only heuristics identify the M2 pattern: same `turn_exchange_id`, large hidden reasoning/tool group, citation/search metadata, and a visible final `assistant:text` report. Ambiguous scrape-only cases remain `kind="normal"` rather than overclaiming. Hidden same-exchange attachment refs attach to the visible final report; hidden text remains raw only.

## 3.7 Attachments and citations

Attachments are byte-downloadable or locally materializable artifacts; citations are web/source references and are never downloaded by `fetch` (`REWRITE-SPEC §8`; M2 handoff). M2 observed no literal `/backend-api/files/...`, `sandbox:`, or `attachment:` URLs, so `AttachmentRef` stores stable ids/pointers/raw paths for later lazy fetch and does not invent endpoints.

| M2 shape | Normalization |
|---|---|
| `message.metadata.attachments[]` with `id`, `size`, `name`, `file_token_size`, `source`, `is_big_paste` | `AttachmentRef(source_kind="user_upload", source_ref=id, filename=name, bytes=size, metadata={source,file_token_size,is_big_paste})` on the visible user message. |
| `message.metadata.content_references[]` where `type == "file"`, with `id`, `name`, `source`, `snippet`, `cloud_doc_url`, `library_file_id`, `library_artifact_type`, medical/drug refs, page ranges, `input_pointer`, `fff_metadata`, `connector_id` | `AttachmentRef(source_kind="file_reference", source_ref=id, filename=name, metadata=sanitized listed fields, raw_path=...)` on the visible message or final same-`turn_exchange_id` report. Large snippets stay full in raw; transcript metadata may truncate display snippets. |
| `message.content.assets[]` on tool `tether_browsing_display` with `content_type`, `asset_pointer`, `size_bytes`, dimensions, `fovea`, `metadata` | `AttachmentRef(source_kind="generated_asset", source_ref=asset_pointer, mime=content_type, bytes=size_bytes, metadata={width,height,fovea,metadata})` attached to the associated visible report. |
| `message.metadata.aggregate_result` on tool `execution_output` with `code`, messages, Jupyter output, `final_expression_output`, `run_id`, `status`, timing, exceptions | Keep full aggregate raw. Create `AttachmentRef(source_kind="code_execution_output", source_ref=run_id, filename="run_<run_id>_aggregate.json", mime="application/json")` only if materialized/downloadable or needed by visible final report. |

`CitationRef` records web/source refs from assistant `metadata.citations`, visible `content_references` such as `grouped_webpages`/`sources_footnote`, and source groups Lens 3 marks user-visible. Store offsets `start_ix`, `end_ix`, `citation_format_type`, nested sanitized metadata, and raw paths. `search_queries` are retained raw and promoted only when linked to a displayed source, avoiding internal telemetry as citations.

# 4. Capture pipeline

## 4.1 Header acquisition

Primary capture depends on the web app's own headers. M2 proved accept-only in-page fetch returned 404 with top-level `detail`, while forwarding the page request's `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route` returned 200 and a ~17.1 MB JSON (`M2 handoff`). Capture therefore registers request listeners before navigation/reload on the tool-owned page, waits for a matching `GET https://chatgpt.com/backend-api/conversation/<conversation_id>`, lower-cases headers, validates the required set, and removes listeners immediately after success/failure.

If Playwright request headers omit sensitive values, the only fallback is same-page CDP `Network.requestWillBeSent`/`Network.requestWillBeSentExtraInfo` correlated by URL/request id for the matched tool-owned request. Reading bearer/session data from JS globals, localStorage, sessionStorage, IndexedDB, cookies, or app internals is rejected as unsafe and fragile. If the request is not observed after fresh own-tab navigation plus one idle-safe reload, or required headers are missing, raise `BackendAuthUnavailableError` and enter the fail-closed fallback chain. Login/Cloudflare stops the current action, logs/raises `HumanActionNeededError` with code `HUMAN-ACTION-NEEDED`, and then only polls read-only from the tool's own diagnostic tab until the human resolves it or the caller gives up; no sends, credential entry, challenge solving, or login automation is attempted.

## 4.2 In-page streaming fetch and raw persistence

After acquiring `HeaderBundle`, `capture.py` performs a single in-page `fetch` from the same tool-owned tab with `credentials: "include"`, `cache: "no-store"`, `accept: "application/json"`, and the forwarded required header values. The response body is streamed in chunks through a unique temporary page binding to `raw-mapping.json.tmp.<pid>`; the token/header values are passed only as the fetch argument, never returned or logged. On non-2xx status, non-JSON content type, parse failure, conversation id mismatch, missing `mapping`, missing/invalid `current_node`, or incompatible visible `content.parts`, the temp file is discarded and capture fails closed.

M2 measured one successful response at ~17.1 MB and ~5.0k mapping/current-branch nodes, with counts changing during active generation. The implementation must stream body-to-disk first and avoid browser-side full JSON materialization or CDP-serializing the whole response from browser to Python. Initial normalization may parse from disk with `json.load` only if M5 measures peak memory within an explicit budget; keep the API as `iter_current_branch_records(raw_path)` so an event parser can replace it without changing store/API. Completion polling must not re-fetch or rewrite a full ~17 MB conversation on every short poll; only final capture and salvage snapshots are atomically promoted. During `wait_for_completion`, cheap own-tab progress checks run at the short cadence, while sparse authoritative backend-state checks use a measured coarse cadence or a lighter endpoint such as `stream_status` only after M5 confirmation.

## 4.3 Canonical extraction

Shape checks retain all unknown top-level keys in raw and normalize only known transcript fields. Top-level keys observed by M2 include `conversation_id`, `title`, `create_time`, `update_time`, `mapping`, `current_node`, `default_model_slug`, `async_status`, `moderation_results`, `safe_urls`, `blocked_urls`, `context_scopes`, `disabled_tool_ids`, `is_archived`, `is_temporary_chat`, `owner`, and `voice`. Visible markdown lives in `message.content.content_type == "text"` with `message.content.parts` as strings. `assistant:code` uses `message.content.text` and `assistant:thoughts` uses `message.content.thoughts`, but both are hidden unless later evidence shows visible UI content. Backend JSON is canonical for markdown/math when headers are safely acquired: M2 found `\widehat`, `\frac`, `\ne`/`\neq`, `\(`, `\[`, and markdown table pipes in assistant `content.parts`; `$` delimiter was false in the sample.

`capture.py` sets `capture_source="backend_api"`, `fidelity="canonical"`, `status="complete"`, `partial=false` for successful backend records. Model slug comes from per-message metadata when available, else top-level `default_model_slug`; display name comes from verified UI send context when known. `active_tools` comes from verified send context for new sends, plus scrape-derived DR/tool heuristics when evidence exists.

## 4.4 Fail-closed fallback chain

Fallback triggers: auth headers unobtainable, app request not observed after one reload, login/Cloudflare stop, backend `401/403/404`, non-JSON or parse failure, top-level shape mismatch, conversation id mismatch, invalid current-branch tree, visible `content.parts` shape not list of strings, or unknown backend state that would make math/markdown ambiguous. Failures are loud: do not silently emit DOM text as canonical.

Fallback order is exactly backend-api → per-turn copy button → KaTeX annotation reconstruction → DOM `textContent` last resort (`REWRITE-SPEC §5`, `§17`). Copy-button fallback hovers the specific assistant turn and uses `button[data-testid="copy-turn-action-button"]`; it requires explicit attended clipboard permission/user gesture because M2 found `navigator.clipboard.readText` permission state `prompt`. Without permission, raise `HumanActionNeededError(reason="clipboard_permission")` or continue to non-clipboard salvage only if the caller explicitly accepts degraded partial output. KaTeX fallback extracts `<annotation encoding="application/x-tex">` in document order and marks `fidelity="math_annotation_reconstructed"`, `partial=true`. DOM `textContent` marks `fidelity="lossy_dom_text"`, `partial=true`, and is acceptable only for salvage/status, not a fidelity pass.

M5/M6 fidelity acceptance is falsifiable: for a heavy-math turn and a DR turn, compare backend/copy/fallback output to web-UI copy and require `\widehat`, `\ne` or `\neq`, and `\frac{}{}` to round-trip without ambiguous corruption. M2 established backend token presence but did not perform full copy-output comparison.

# 5. Completion detection

Completion is called only after send verification proves a new user turn exists. The loop has two cost-bounded lanes: cheap fine-grained progress checks on the tool-owned tab at `progress_poll_interval_s` (streaming marker/stop-button presence, new assistant id, visible assistant text length+hash, composer state) and sparse authoritative backend-state checks at `backend_check_interval_s` using the same per-request safe header mechanism; cheap DOM progress checks need no headers. The exact real intervals and any full-vs-light backend choice are measured in M5; until then, real code must not do a full ~17 MB conversation fetch every short poll. The full backend conversation fetch is done once for final capture, plus explicit salvage snapshots when needed, not per progress tick. If `/backend-api/conversation/<id>/stream_status` is confirmed in M5, it can become the preferred lightweight authoritative check.

Backend checks parse top-level `async_status`, `update_time`, `current_node`, node `status`, message metadata `async_source`, `is_complete`, `is_finalizing`, `pro_progress`, and the new assistant visible text length/hash (`M2 handoff`). Each sparse backend check acquires a `HeaderBundle` non-intrusively from the tool's own already-registered same-tab request observer, uses `for_single_fetch()` for that one authoritative request, and discards the local copy immediately after the request returns or raises. `wait_for_completion` never stores a `HeaderBundle` between iterations; only redacted progress state persists across the loop: ids, text lengths, hashes, status flags, timing/activity tokens, and redacted error codes; header values never persist and never enter logs, exceptions, status reports, fixtures, or files. Reacquisition must not re-navigate or reload the operator's tab merely to refresh headers. Exact value vocabularies are unverified; conservative rule: incomplete if any relevant current-branch/new-turn signal is active, in-progress, finalizing, or `is_complete is False`; complete only when a new visible `assistant:text` after baseline exists, the text is non-empty or an explicit empty-complete signal exists, no relevant node is active/finalizing, and top-level async state is absent or known complete. Unknown active-looking values keep polling; unknown impossible shapes trigger DOM fallback/salvage, not success.

`timeout` is a no-activity window, not a wall-clock cap. It resets whenever authoritative progress changes: `update_time`, `current_node`, new node id, new assistant id/text hash/length, `async_status`, node `status`, `pro_progress`, or `is_finalizing`. `max_total_wait` defaults to `None`/unbounded and only applies when the caller explicitly opts in. Long Pro/DR runs must not be killed by a hidden 600s ceiling (`REWRITE-SPEC §7`; gotcha #3). If the no-activity window elapses, raise `CompletionTimeoutError` with salvage data and persist a partial assistant record.

DOM consensus fallback uses M2 selectors and is gated on baseline: a new assistant id different from `baseline.latest_assistant_id`, stop button absent for a stable window, text hash/length stable for the same stable window, and `(saw_streaming or non_empty_body)` true. DOM completion is only a completion signal; after it fires, run backend capture again for canonical markdown. If backend still fails, use the fail-closed fallback chain and mark fidelity honestly.

`GET /backend-api/conversation/<id>/stream_status` remains a hypothesis from M2. Include a feature-gated hook after M5 verification; do not rely on it before evidence.

Salvage order on timeout/error: latest backend partial `assistant:text` for the new turn if available; else copy-button output if explicit attended clipboard permission exists; else DOM textContent of the new assistant turn. Persist `status="partial"` or `"error"`, `partial=true`, `capture_source` and `fidelity` set to the actual salvage source, plus redacted error details.

# 6. Send and action strategy

Verified-send algorithm (`REWRITE-SPEC §6`; gotcha #2): resolve and allowlist the conversation URL; acquire a tool-owned tab; wait for any existing generation to be idle; reload when idle between turns to clear SPA staleness; verify/select requested model/tools; read `TurnBaseline` from `[data-message-author-role="user"][data-message-id]` and `[data-message-author-role="assistant"][data-message-id]`; call `Store.begin_send` to append the pending user record; wait/retry for `#prompt-textarea` because the composer transiently unmounts; fill using normal editor APIs with `insertText`/InputEvent fallback and verify normalized composer text; submit via an enabled `button[data-testid="send-button"], #composer-submit-button` after input, with Enter fallback only while composer is focused; poll briefly for a new user turn with new id or increased count and text matching the prompt; if absent, raise `PromptNotSubmittedError` and do not wait for/return any assistant response.

After `SubmittedTurn`, call `Store.commit_send` with the canonical user id, then `completion.wait_for_completion` requiring a newer assistant id. On completion, run backend capture and return the captured assistant `TurnRecord`. On timeout/error, salvage and persist partial; for CLI `ask`, stdout still receives the salvaged markdown if any.

File uploads are actions and must use the UI, not backend-forged uploads. M5/M7 must verify upload selectors/chip evidence before claiming support beyond local path validation. User-uploaded refs observed later in backend metadata become `AttachmentRef` records.

Model selection is a fail-closed enumeration algorithm, not prose: enumerate `composer-footer button[aria-haspopup="menu"]`, normalize visible text, require exactly one candidate matching the known current-model footer label, click it, enumerate only `[data-radix-popper-content-wrapper]`, select the exact target `menuitemradio` or family `menuitem`→radio label, then verify the composer-footer label reflects the requested model before proceeding. Tool selection uses the same Radix portal abstraction from `button[data-testid="composer-plus-btn"]` and verifies reflected state before send. If any trigger, label, submenu path, or reflected state is absent/ambiguous, no prompt is sent. Full model/tool menu exercise is M7; until then these paths remain fail-closed. Observed model tier labels: `Instant`, `Medium`, `High`, `Extra High`, `Pro Extended`; family submenu `GPT-5.5` with `5.5`, `5.4`, `5.3`, `4.5 Leaving on June 26`, `o3`. Observed tools: `Add photos & files`, `Create image`, `Deep research`, `Web search`, `More`; `More` submenu includes `Agent mode`, `Create task`, `Figma`, `Finances`, `GitHub`, `OpenAI Platform`. Do not open `Recent files`/`Projects` submenus for enumeration.

`create(project=None)` opens a tool-owned new chat and returns a `ConversationRef`. If no server id exists until first send, return `conversation_id=None`, `is_draft=True`, and persist/update when `ask` observes the real id. Project create/send uses the parsed `/g/g-p-<project_id>/c/<chat_id>` shape but is not live-verified by M2; fail closed if project context cannot be verified.

# 7. Concurrency model

The persistent `Session` owns exactly one `TabPool` and one `AdaptiveSendBudget`. Tabs are a disposable cache keyed by `conversation_id`, not durable state. The pool records only pages it created; mock tests should make `context.pages` unavailable so accidental operator-tab enumeration fails. Default concurrency is modest: `max_active_tab_ops=3`, `max_tabs=3`, `idle_ttl_s=900`; the Lens 4 proposed `pool_max_tabs=6` is cut as unmeasured over-capacity, though `max_tabs` remains configurable. Reads/captures may run in parallel subject to leases; sends are globally serialized/governed by the budget.

TabPool API and algorithm: `acquire(ref)` resolves identity, builds/allowlist-checks URL, evicts idle unleased tabs, returns an existing unleased own tab for the same conversation or opens a new own tab if under `max_tabs`, otherwise LRU-closes an unleased own tab or waits briefly before `TabPoolExhaustedError`. Same-conversation operations serialize with one lease. `release(tab)` verifies object identity, clears lease, records `last_used`, and removes crashed/closed own pages. `close_all()` closes only pages in the pool and then `CdpChannel.detach()` disconnects client transport without quitting Chromium.

AdaptiveSendBudget gates only prompt submission, not completion waiting. There is no hard message cap. Default unmeasured safety knobs for M4/M5 are `politeness_floor_s=5`, `initial_rate_per_min=3`, non-bursting bucket capacity 1, additive increase after verified successes, multiplicative backoff on soft signals, and hard pause on login/Cloudflare. These defaults are assumptions to be measured, not a claimed account ceiling. Backoff signals include own-tab HTTP 429/Retry-After, rate-limit/toast/account-limit classifiers, repeated `PromptNotSubmittedError`, and Cloudflare/login hard stops; logs include only sanitized classifier data, not prompts/tokens/page bodies.

Atomic OS processes do not share an in-memory budget. Do not add a daemon/IPC coordinator in M4/M5; operational guidance is to route fan-out/loops through one persistent `Session`. If M7 evidence shows cross-process collisions, add the simplest opt-in per-data-dir advisory lock around send submission then.

Safety invariants in concurrency: no Playwright-launched browser, no stealth, allowlist before navigation/fetch, own tabs only, never quit browser, CDP preflight before real legs, login/Cloudflare stop as `HUMAN-ACTION-NEEDED` with read-only polling only, real legs attended, modest shared-browser use (`REWRITE-SPEC §13`; team charter). Repo/install isolation is also load-bearing for developers and any build/test workflow: never `git push` or merge to a published branch; never check out, commit to, merge into, fast-forward, or otherwise move `stable`; never run `uv tool install`, `uv tool upgrade`, or `uv tool ... --reinstall`. Use `uv run ...` in the project venv only. Why: `stable` and `uv tool ...` can mutate the operator's separately installed running tool, while push/merge creates irreversible outbound effects reserved for the operator.

# 8. CLI verbs

Common options: `--data-dir PATH`, `--cdp-endpoint URL`, `--selector-channel real|mock`, and `--json` only for commands documented as structured. Diagnostics/progress/errors go to stderr; stdout is reserved for payload or status JSON. `ask` and `scrape` always print to stdout and additionally write `--out` when given, fixing gotcha #4 (`REWRITE-SPEC §4`, `§17`).

| Verb | Flags | Browser | Session mapping | Stdout |
|---|---|---:|---|---|
| `ask <conv?> "<prompt>"` | `--model LABEL`, repeat `--tool LABEL`, repeat `--attach FILE`, `--project ID`, `--timeout S`, `--max-total-wait S`, `--out FILE`, `--data-dir` | yes | `Session.ask` | New assistant `content_markdown` or salvaged partial markdown, exactly one trailing newline. |
| `create` | `--project ID`, `--json`, `--data-dir` | yes | `Session.create` | URL/id line or JSON; may report draft/null id if server id not allocated yet. |
| `scrape <conv>` | `--with-attachments`, `--out FILE`, `--data-dir` | yes read-only | `Session.scrape` | Rendered current-branch markdown export; also writes store/raw. |
| `history <conv>` | `--out FILE`, `--data-dir` | no | `Session.history` | Rendered local markdown transcript. |
| `export <conv>` | same as `history` | no | `Session.history` | Same as history. |
| `fetch <conv> <attachment>` | `--json`, `--data-dir` | maybe | `Session.fetch` | Local path or JSON metadata; cached refs do not attach. |
| `loop <conv>` | `--message TEXT`, `--model`, repeat `--tool`, repeat `--attach`, `--max-iterations N`, `--timeout S`, `--max-total-wait S`, `--data-dir` | yes persistent | `Session.loop` | JSONL, one turn envelope per iteration. |
| `status [<conv>]` | `--json`, `--data-dir`, `--no-browser-probe` | preflight/maybe own diagnostic tab | `Session.status` | Human report or JSON status; still prints report on blocking conditions. |

`loop` uses one persistent `Session` and emits JSONL because repeated raw markdown is not delimiter-safe. Each object includes `schema_version`, `type="turn"`, `iteration`, `conversation_id`, `conversation_url`, `user_message_id`, `message_id`, `status`, `partial`, `capture_source`, `fidelity`, `content_markdown`, and transcript/raw paths. `--max-iterations` is workflow control, not an account safety cap. SIGINT attempts partial salvage and exits 130.

`status --json` includes global store counts, CDP preflight result, attached/signed-in/login-wall/cloudflare state from a tool-owned diagnostic tab only, selector-map validity, tab-pool/rate snapshots, last redacted error, and optional per-conversation model/tools/turn counts/last turn/attachments/branch/paths. `present` for selectors is `null` when not safely checked. Exit 0 means no blocking condition; exits may be nonzero for CDP down/login/etc while stdout still contains the report.

# 9. Error taxonomy

All errors inherit `AskChatGPTError` and carry `code`, `exit_code`, `retryable`, `retry_action`, `message`, and redacted `details`. No error may include bearer/OAI headers, cookies, raw response headers, private operator tab data, or prompt/response text except explicitly intended partial salvage output.

| Class | Code | Exit | Retryable | Raised when |
|---|---:|---:|---|---|
| `CDPUnreachableError` | `CDP_UNREACHABLE` | 20 | yes after operator action | `/json/version` preflight fails/times out. |
| `HumanActionNeededError` | `HUMAN-ACTION-NEEDED` | 21 | only after human action | Login wall, Cloudflare/challenge, or required clipboard permission; action stops and only read-only polling on own diagnostic tabs may continue. |
| `DomainNotAllowedError` | `DOMAIN_NOT_ALLOWED` | 22 | no unless input/config fixed | URL/fetch outside allowlist. |
| `ConversationNotFoundError` | `CONVERSATION_NOT_FOUND` | 23 | maybe | Backend/UI/local store cannot resolve conversation. |
| `SelectorNotFoundError` | `SELECTOR_NOT_FOUND` | 24 | maybe after selector update | Required selector missing or selector map invalid. |
| `PromptNotSubmittedError` | `PROMPT_NOT_SUBMITTED` | 30 | yes | Submit produced no verified new user turn carrying the prompt. |
| `ModelSelectionNotReflectedError` | `MODEL_SELECTION_NOT_REFLECTED` | 31 | yes | Requested model not reflected before send; no prompt sent. |
| `ToolSelectionNotReflectedError` | `TOOL_SELECTION_NOT_REFLECTED` | 32 | yes | Requested tool not reflected before send; no prompt sent. |
| `BackendAuthUnavailableError` | `BACKEND_AUTH_UNAVAILABLE` | 40 | maybe | Required backend auth/OAI headers unobtainable from own page request. |
| `BackendCaptureShapeError` | `BACKEND_CAPTURE_SHAPE` | 41 | no until parser update | Backend JSON shape incompatible or math/markdown ambiguous. |
| `CaptureFailedClosedError` | `CAPTURE_FAIL_CLOSED` | 42 | maybe | Backend failed and no faithful fallback succeeded. |
| `CompletionTimeoutError` | `COMPLETION_TIMEOUT` | 50 | inspect/scrape before blind resend | No-activity window or explicit max-total wait elapsed; partial salvage recorded if available. |
| `MaxTotalWaitExceededError` | `MAX_TOTAL_WAIT_EXCEEDED` | 51 | maybe | Caller-set total wait cap elapsed. |
| `AttachmentNotFoundError` | `ATTACHMENT_NOT_FOUND` | 60 | no unless ref fixed | Requested attachment ref absent locally. |
| `AttachmentFetchError` | `ATTACHMENT_FETCH_FAILED` | 61 | maybe | Lazy byte fetch unsupported/failed. |
| `TabPoolExhaustedError` | `TAB_POOL_EXHAUSTED` | 62 | yes | All own tabs leased and no LRU reclaim within wait. |
| `StoreError` | `STORE_ERROR` | 70 | depends | Data-dir/atomic write/read failure. |
| `InternalError` | `INTERNAL_ERROR` | 99 | unknown | Unexpected bug. |

CLI stderr first line is `ERROR <CODE>: <message>`. JSON-mode commands also emit redacted error JSON on stderr. `ask` prints salvaged partial markdown to stdout before exiting on `CompletionTimeoutError` if salvage exists; `loop` emits a partial JSONL envelope before exiting.

# 10. Recommended M4-M7 build sequence

Build workflow caution: use `uv run ...` in the project venv only; never `git push`, never move/commit/merge/fast-forward `stable`, and never run `uv tool install`/`uv tool upgrade`/`uv tool ... --reinstall`, because those actions can mutate the operator's installed running tool or create irreversible outbound effects.

## M4: offline core TDD against `mock` — minimal single-tab spine

1. Scaffold modules and public data classes: `session.py`, `errors.py`, `identity.py`, `allowlist.py`, `selectors/`, and `channels/base.py` with a channel-bound `TabLease`. Acceptance: importable package, selector schema validation fails on missing M2 keys, allowlist unit tests reject non-allowed hosts, no production browser/network use.
2. Implement `store.py` layout, JSONL serialization of `TurnRecord`, index, atomic append/replace, pending `local:<client_send_id>` supersession, markdown rendering, and stdout+`--out` helper. Acceptance: crash/torn-line tests, last-writer-wins reads, history/export no CDP preflight, `ask`/`scrape` payload helper attempts stdout and `--out` independently.
3. Implement `MockChannel` fixtures for the core M2/backend/send spine: 404 without headers, 200 with required headers, ~5k-node synthetic mapping, DR `turn_exchange_id` group, math tokens, attachment/citation shapes, selector drift, clipboard permission prompt, composer unmount, no-op send, and long progress. Acceptance: no test touches network; mock `context.pages` access raises.
4. Implement capture parser/linearizer against raw fixture files. Acceptance: visible records are only `user:text`/`assistant:text`, hidden nodes retained raw, DR final report classified only with evidence, all four attachment shapes normalized, citations separate, empty-separator concatenation of multiple string parts tested, non-string parts fail closed.
5. Implement single-tab send/completion logic over mock. Acceptance: no-op send raises `PromptNotSubmittedError`, composer absence retries, completion requires newer assistant id, no-activity timeout resets on cheap progress, sparse backend checks are not tied to the short DOM interval, `max_total_wait=None` can run with fake-clock long progress, timeout salvages partial.
6. Implement `cli.py` verbs over mock/store. Acceptance: verb-to-Session mapping table tests, `ask`/`scrape` stdout never suppressed by `--out`, `status --json` machine schema, error exit codes/redaction. `loop`, full `menus.py`, `TabPool`, and `AdaptiveSendBudget` stay out of M4 except for minimal stubs needed by falsifiable core tests.

## M5: attended CDP capture/scrape capability + verified-send smoke

1. Implement `CdpChannel.preflight/attach/open_tab/detach` under attended conditions. Acceptance: `GET /json/version` gate, no Playwright launch, no `context.pages` enumeration, only own tabs closed, browser left running, allowlist enforced.
2. Implement own-page request header acquisition and streaming backend fetch. Acceptance: cookies-only/accept-only mock/attended check still fails 404, observed own request supplies required header names, values never logged/persisted, a successful capture streams to temp and atomically writes `raw-mapping.json`, top-level shape matches M2.
3. Prove `scrape` capability with an operator-approved non-target smoke conversation; do not run the long authorized target scrape here. Acceptance: JSONL current branch plus raw mapping written, measured RSS/tracemalloc recorded on the smoke scale, stdout and `--out` both receive rendered markdown, no browser/operator tabs inspected.
4. Build the fidelity verification harness. Acceptance: backend/copy/fallback comparison can be run against operator-approved heavy-math and DR samples; `\widehat`, `\ne`/`\neq`, `\frac{}{}` are checked against web-UI copy; the target conversation's full fidelity pass is M6.
5. Implement and verify real UI send path with a low-risk operator-approved prompt. Acceptance: baseline user id/count captured, composer fill verified, send button after input confirmed/selector updated, new user turn required, `PromptNotSubmittedError` demonstrably raised on mock/forced no-op, completion requires newer assistant, partial salvage on timeout.
6. Catalogue real completion status values and challenge/rate markers from own tabs only. Acceptance: documented observed `async_status`, node `status`, `is_complete`, `is_finalizing`, `pro_progress`; backend polling cadence and any lightweight endpoint are measured; `stream_status` either verified and feature-gated or left disabled; login/Cloudflare markers stop as `HUMAN-ACTION-NEEDED` with read-only polling.
7. Defer model/tool menu implementation to M7 unless needed for the low-risk send smoke; requested model/tool changes before then fail closed with no prompt sent.

## M6: run the pressing target scrape + verify fidelity

1. Run `scrape` for `https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31` in attended mode. Acceptance: JSONL current branch plus raw mapping written, ~17 MB/~5k scale handled with measured RSS/tracemalloc recorded, stdout and `--out` both receive rendered markdown, no browser/operator tabs inspected.
2. Record the fidelity pass for the target and representative DR/heavy-math samples. Acceptance: backend/copy/fallback output is compared to web-UI copy and `\widehat`, `\ne`/`\neq`, `\frac{}{}` round-trip; any failure blocks claiming canonical fidelity.

## M7: model/tools, keep-pushing loop, tab pool, and rate budget

1. Implement `menus.py` with the executable Radix enumeration algorithm. Acceptance: select/verify exact labels, absent/ambiguous labels fail closed, `Recent files`/`Projects` submenus are never opened.
2. Implement `TabPool` and `AdaptiveSendBudget` with fake clock and attended checks. Acceptance: lazy open, same-conversation serialization, idle eviction, LRU own-tab close only, close_all own tabs only, politeness spacing, non-bursting sends, AIMD/backoff, hard pause, shared-resource allocation, no hard message cap.
3. Implement `loop` over the persistent `Session`. Acceptance: attach once, verify each new turn, emit JSONL, handle SIGINT salvage, and keep account pacing human-safe without an arbitrary message cap.
4. Verify project create/send if prioritized. Acceptance: project URL/context reflected before send/create; otherwise project behavior remains a marked assumption.

# 11. Design decisions and rationale

The design keeps the spec's no-daemon architecture because durable truth is the browser plus on-disk transcript and a daemon would add coordination state without solving the key safety/fidelity issues (`REWRITE-SPEC §2`; agent-rigor Occam). It rejects JS/storage token scraping and request forging because M2 proved the required headers can be observed on the page's own request and safety requires minimal observation. It uses backend JSON as canonical capture but fail-closed fallbacks because rendered DOM caused silent math corruption and M2 confirmed backend markdown tokens only with safe headers. It emits only visible `user:text`/`assistant:text` records and keeps hidden internals raw because DR/Pro is a grouped tree, not a new content type. It stores citations separately from attachments because M2 observed web/source references and file/assets/code refs as different shapes. It uses a pending `local:<client_send_id>` stub rather than a separate outbox file because it satisfies eager-write with one append-only transcript contract; this is the smallest exception to canonical message ids. It concatenates multiple string `content.parts` without an inserted separator because adding blank lines would invent markdown absent M2 evidence. It defaults `max_tabs=3` instead of Lens 4's cache of 6 because the charter says modest ~3-way and 6 was not measured; configurability preserves future tuning. It keeps no cross-process limiter because the approved architecture has no daemon and real concurrency should run through one persistent `Session`; revisit only with evidence. It treats rate defaults as assumptions, not account ceilings, preserving the no-hard-message-cap invariant.

# 12. Open questions for the lead

1. Project behavior: M2 did not verify `/g/g-p-<project_id>/c/<chat_id>` send/create. Should M5 prioritize project create/send before M6 scrape, or allow address/scrape-only project support until M7?
2. Pending stub policy: this design uses `local:<client_send_id>` in `message_id` for eager-write before canonical ids exist. If the lead prefers strict canonical-only JSONL, the alternative is a separate `pending-sends.jsonl` outbox, which adds a file and read path.
3. Completion status vocabulary: exact live values for `async_status`, node `status`, `is_complete`, `is_finalizing`, and `pro_progress` need M5 cataloguing; until then the parser is conservative.
4. `stream_status`: only a hypothesis; use only after M5 verifies endpoint, auth, and semantics.
5. Attachment bytes: M2 saw ids/pointers/metadata but no download URLs. `fetch` should remain lazy/unsupported for unknown refs until byte routes are verified.
6. Clipboard fallback: M2 saw permission `prompt`. Should copy fallback require an explicit CLI flag such as `--allow-clipboard-fallback`, or always stop with `HUMAN-ACTION-NEEDED` when backend fails?
7. Send-rate defaults: `5s` floor and `3/min` initial rate are conservative assumptions. M5/M7 should measure real own-tab signals before documenting defaults as recommended.
8. Memory budget: M5 must measure RSS/tracemalloc for streaming download plus parse on the ~17 MB target and decide whether whole-file parse is acceptable or an event parser is required.
9. Safe profile verification: status can report configured profile from charter, but verifying profile identity over CDP without unsafe `chrome://`/operator-tab probing remains undecided.
10. Multi-part `content.parts`: the chosen no-separator join needs M5 copy comparison if live data contains multiple string parts.

# 13. Traceability by major decision

| Decision | Primary lens/source |
|---|---|
| Public synchronous `Session`, atomic vs persistent use, no daemon, Session owns tabs/rate | Lens 1, Lens 4, `REWRITE-SPEC §2`, `§10` |
| Single `TurnRecord` shared by API, JSONL, and capture | Lens 1 + Lens 2 seam reconciliation, M3 synth contract |
| Backend-api capture with own-request headers, no token persistence/logging | Lens 3, M2 handoff, M3 common constraints |
| Stream raw response to disk before normalization | Lens 2 + Lens 3, M2 ~17.1 MB/~5k measurement, agent-rigor empirical scale rule |
| Visible classification: current branch, `user:text`/`assistant:text` visible, hidden internals raw | Lens 2 + Lens 3, M2 role/content facts |
| DR/Pro as `turn_exchange_id` group with final visible `assistant:text` report | Lens 2 + Lens 3, M2 DR facts |
| Unified attachment refs and separate citations | Lens 2 + Lens 3, M2 attachment/citation facts |
| Pending `local:<client_send_id>` eager-write stub | Lens 2, gotcha #3; accepted by synthesis as simplest lose-nothing design |
| Fail-closed fallback chain copy-button → KaTeX annotation → DOM textContent | Lens 3, `REWRITE-SPEC §5`, gotcha #1 |
| Completion cheap progress checks plus sparse backend authoritative checks, DOM consensus fallback, no hidden ceiling | Lens 3, Lens 5, `REWRITE-SPEC §7`, gotcha #3 |
| Verified send baseline → new user turn → newer assistant, idle reload, wait-for-composer | Lens 1, Lens 5, `REWRITE-SPEC §6`, gotcha #2 |
| Label-driven Radix model/tool menus and no private submenu enumeration | Lens 1 + Lens 5, M2 selector/menu facts |
| Tab pool own-tabs-only, max active ~3, idle eviction/LRU | Lens 4, team charter shared CDP constraints |
| Adaptive send budget with politeness/backoff and no hard message cap | Lens 4, team charter, agent-rigor shared-resource ceiling |
| CLI verb table, stdout plus `--out`, loop JSONL, status schema | Lens 5, `REWRITE-SPEC §4`, `§12`, gotcha #4 |
| Error taxonomy and exit codes | Lens 1 + Lens 5, M3 synth seam requirements |
| M4/M5/M6/M7 build sequence | Lens 5 + all lenses, `REWRITE-SPEC §18`, `§19` |

## Revision log (M3 panel fixes)

- G1 (§7, §10): Added repo/install isolation invariants: never push/merge published branches, never move `stable`, never run `uv tool install`/upgrade/reinstall; noted why and kept build workflow on `uv run`.
- W1 (§4.1, §9): Encoded login/Cloudflare stop plus read-only polling on own diagnostic tabs until human resolution or caller give-up; login remains never automated.
- M1 (§2.1, §2.2–§2.6, §2.9, §2.10): Made browser tabs channel-bound `TabLease` objects and defined the missing seam types `Transcript`, `SelectorMap`, `SendTimeouts`, `AttachmentSpec`, `PreflightResult`, and `StatusReport`.
- M2 (§2.3, §2.5, §4.2, §5, §10): Bounded completion cost with cheap progress checks plus sparse measured backend checks, and specified in-memory per-operation `HeaderBundle` lifetime/discard rules.
- N1 (§10): Realigned the build sequence to M4 offline core, M5 capability/smoke, M6 target scrape, and M7 menus/loop/tab-pool/rate work.
- N2 (§2.6, §2.10, §6): Replaced model-picker prose with a fail-closed executable candidate enumeration, portal selection, and reflected-label verification algorithm.

### Revision 2

- A (§2.3, §2.5, §5): Tightened `HeaderBundle` to per-backend-request acquire/use/discard, with non-intrusive same-tab request-observer reacquisition and only redacted progress state across waits.
- B (§2.3, §2.7): Defined `BackendFetchMeta`, `BackendTopLevel`, `SendContext`, and `ConversationPaths`.
- C (§2.1, §3.3): Specified pending eager-write stubs as `status="partial"`, `partial=true`, hidden from default `history`/`export` unless explicitly included or shown in `status` diagnostics.
