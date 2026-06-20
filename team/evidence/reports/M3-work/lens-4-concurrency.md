STATUS: DONE
Produced a concrete Lens 4 design for the persistent `Session`-owned managed tab pool and adaptive account send-rate budget.
Key decisions: tabs are a disposable cache keyed by `conversation_id`; sends are globally governed by one Session limiter using politeness spacing plus AIMD/backoff; backend reads may run in parallel but still use only tool-opened tabs.
Blockers: the real ChatGPT account ceiling and exact live backoff/challenge markers were not measured in M2 and must be confirmed in M5/M7.

## Scope and source anchors

This design covers only concurrency: the managed tab pool and adaptive send-rate/account budget owned by the persistent `Session`. It does not design capture parsing, send verification, persistence, or menu mechanics beyond their interface to the pool/budget. It honors the architecture decision that atomic CLI calls attach→act→detach while loops/multi-tab concurrency hold a persistent `Session` that owns the tab pool and rate budget (REWRITE-SPEC §2, §3, §10; charter Rework spec).

Hard invariants encoded here: attach only to the operator's already-running Chromium over CDP; never launch a browser; inspect only tabs the tool opens; never iterate `context.pages`; never quit the browser; stop on login/Cloudflare challenge with `HUMAN-ACTION-NEEDED`; no stealth; only allowlisted domains; no hard message cap; modest approximately 3-way browser concurrency (REWRITE-SPEC §13; M3 common constraints §2; charter Shared-resource ceilings). M2 did not stress account rate behavior, so every numeric limiter default below is an assumption to be measured, not a claimed account ceiling (M2 handoff; agent-rigor Shared-resource ceiling).

## 1. Managed tab pool

### Ownership and model

The persistent `Session` owns exactly one `TabPool`. Tabs are a cache, not durable state: the durable identifiers are `conversation_id`, optional `project_id`, URL, and on-disk transcript/store records. If a tab is evicted, crashes, or is closed, reopening `https://chatgpt.com/c/<conversation_id>` or `https://chatgpt.com/g/g-p-<project_id>/c/<conversation_id>` is the recovery path (REWRITE-SPEC §9, §10; M2 project behavior is not live-verified).

The pool records only pages it created via the attached CDP browser context. It must never discover pages by enumerating an existing browser context. Implementation rule: a mock CDP context used in tests should make `context.pages` raise so any accidental enumeration fails fast. Own-page tracking is `conversation_id -> ManagedTab` plus `page_id -> ManagedTab`, both populated only from `context.new_page()` return values (M3 common constraints §2; charter Shared-resource ceilings).

### Config defaults

Defaults reflect the charter's modest approximately 3-way shared-browser guidance while keeping the cache generous enough to avoid needless reloads (charter Shared-resource ceilings; REWRITE-SPEC §10). All values are configurable via `Session(..., concurrency=ConcurrencyConfig(...))` and surfaced by `status`.

```python
@dataclass(frozen=True)
class ConcurrencyConfig:
    max_active_tab_ops: int = 3              # active leased tabs/operations, assumption from charter ~3-way
    pool_max_tabs: int = 6                   # cached own tabs, generous relative to active ops; assumption
    pool_idle_ttl_s: float = 900.0           # close unleased tabs idle for 15 min; assumption
    page_open_timeout_s: float = 30.0
    lru_wait_timeout_s: float = 30.0         # wait for an unleased tab before TabPoolExhaustedError
```

`max_active_tab_ops` limits concurrent page work inside this Session; `pool_max_tabs` limits cached open pages. Reads are not send-rate limited, but they still lease tabs and therefore respect `max_active_tab_ops` so the shared CDP browser is not flooded.

### Data structures

```python
@dataclass
class ManagedTab:
    conversation_id: str
    project_id: str | None
    url: str
    page: Page                              # Playwright Page created by this pool only
    lease_count: int                        # 0 or 1; same-conversation operations serialize
    last_used_monotonic: float
    opened_at_monotonic: float
    generation: int
    closing: bool = False
    last_error: str | None = None

@dataclass(frozen=True)
class TabLease:
    tab: ManagedTab
    lease_id: str
```

`lease_count` is intentionally exclusive (`0` or `1`). Two operations on the same conversation must not interleave composer, navigation, header-capture, or DOM actions. Different conversations can proceed concurrently up to `max_active_tab_ops`.

### Required pool API

Use async signatures because Playwright/CDP operations are asynchronous.

```python
class TabPool:
    async def acquire(self, conv_id: str) -> ManagedTab: ...
    async def release(self, tab: ManagedTab) -> None: ...
    async def evict_idle(self) -> list[str]: ...          # returns closed conversation_ids
    async def close_all(self) -> None: ...                # close own tabs only, then Session detaches
```

The implementation may internally expose `async with pool.lease(conv_id) -> ManagedTab` as a safer wrapper, but the four API operations above are the stable cross-cluster interface.

### `acquire(conv_id) -> tab` algorithm

1. Normalize and validate the conversation reference through the identity layer: canonical key is bare `conversation_id`; optional `project_id` selects project URL shape; reject malformed ids before navigation (REWRITE-SPEC §9).
2. Build the target URL: `https://chatgpt.com/c/<conversation_id>` or, if known, `https://chatgpt.com/g/g-p-<project_id>/c/<conversation_id>`. Pass it through `allowlist.py` before use; only chatgpt/openai/auth/oaiusercontent domains are permitted (REWRITE-SPEC §13; M3 common constraints §2).
3. Under the pool condition lock, run idle eviction for unleased tabs whose `now - last_used_monotonic >= pool_idle_ttl_s`.
4. If `conversation_id` is already in the map and the tab is alive and not closing, wait until `lease_count == 0` and `active_leases < max_active_tab_ops`; mark it leased (`lease_count = 1`), update `last_used_monotonic`, and return it.
5. If absent and `len(open_tabs) >= pool_max_tabs`, close the least-recently-used unleased own tab. If every cached tab is leased, wait up to `lru_wait_timeout_s` for a release; if still none, raise `TabPoolExhaustedError(max_tabs=..., active_leases=...)` rather than touching operator tabs.
6. Create a new own page with `context.new_page()`. Do not inspect any pre-existing page. Attach only page-local event handlers needed by this tool, such as response classifiers for rate/backoff signals.
7. Navigate the own page to the validated URL. If the page resolves to login or Cloudflare challenge markers, classify it as `HUMAN_ACTION_NEEDED`, release/close the page if safe, pause sends in the rate budget, and surface an actionable error; do not automate login/challenge (REWRITE-SPEC §13; M2 handoff selectors caveats).
8. Insert the resulting page into `conversation_id -> ManagedTab`, mark it leased, and return.

### `release(tab)` algorithm

1. Verify object identity: `tab` must be the same object currently recorded for `tab.conversation_id`; otherwise raise `ForeignTabError` and do not close anything.
2. Set `lease_count = 0`, update `last_used_monotonic = now`, decrement `active_leases`, and notify waiters.
3. If the page closed/crashed while leased, remove it from the map and notify waiters; the next `acquire` reopens by URL.

### `evict_idle()` algorithm

Close only unleased own pages whose idle age exceeds `pool_idle_ttl_s`. Return the `conversation_id` list that was closed for status/audit. Do not evict in-use tabs, and do not infer or close tabs outside the pool. Eviction is safe because tabs carry no durable state; send/capture clusters persist conversation refs and turn records before risky actions (REWRITE-SPEC §8, §10).

### `close_all()` and detach

On `Session.detach()` or process shutdown, call `TabPool.close_all()` to close only pages in the pool maps, clear the maps, and detach the CDP connection. Do not call any API that terminates the operator's Chromium process or closes the whole browser/profile. If the Playwright Python API's exact safe-detach method is ambiguous, wrap it in a channel method named `CdpConnection.detach()` whose contract is "disconnect client transport only; never quit remote browser" and verify in M5 before real use (assumption/open question; safety invariant from REWRITE-SPEC §13).

### Pool status JSON

`Session.status()` should expose pool state without prompts, tokens, OAI headers, or page contents:

```json
{
  "tab_pool": {
    "max_active_tab_ops": "int",
    "pool_max_tabs": "int",
    "pool_idle_ttl_s": "number",
    "open_tabs": "int",
    "leased_tabs": "int",
    "entries": [
      {
        "conversation_id": "string",
        "project_id": "string|null",
        "url": "string",
        "leased": "boolean",
        "idle_s": "number",
        "opened_age_s": "number",
        "last_error": "string|null"
      }
    ]
  }
}
```

## 2. Adaptive send-rate, not an artificial low cap

### Ownership and lifecycle

The persistent `Session` owns exactly one `AdaptiveSendBudget`. Every send path must call it immediately before UI submission; backend reads, scrape, history/export, and completion polling do not consume send tokens. The limiter gates only the moment a prompt is submitted, not the completion wait, so long Pro/Deep Research runs are not killed by a hidden ceiling (REWRITE-SPEC §7, §10; M3 common constraints gotcha fixes).

```python
class AdaptiveSendBudget:
    def register_consumer(self, consumer_id: str, *, weight: float = 1.0) -> None: ...
    def unregister_consumer(self, consumer_id: str) -> None: ...
    async def before_send(self, consumer_id: str, conv_id: str) -> "SendPermit": ...
    async def after_send(self, permit: "SendPermit", outcome: "SendOutcome") -> None: ...
    def record_backoff_signal(self, signal: "BackoffSignal") -> None: ...
    def snapshot(self) -> dict[str, object]: ...
```

`before_send` is called after the send cluster has acquired the tab and baseline user-turn id, and immediately before clicking/pressing submit. `after_send` is called after the send cluster either verifies a new user turn, raises `PromptNotSubmittedError`, detects a rate/challenge signal, or aborts before submission. Completion success/failure is reported separately only if it reveals rate/account signals.

### Default limiter config

The account ceiling is unknown: M2 confirmed selectors/capture but did not stress rate behavior (M2 handoff). Defaults below are conservative assumptions, not hard caps or claims about ChatGPT limits. They must be reported by `status` and adjusted after M5/M7 measurements.

```python
@dataclass(frozen=True)
class SendRateConfig:
    politeness_floor_s: float = 5.0          # minimum time between any two Session sends; assumption
    initial_rate_per_min: float = 3.0        # one send every 20s at startup; assumption
    min_rate_per_min: float = 0.5            # severe backoff lower bound, not total cap; assumption
    ramp_successes: int = 5                  # additive increase after N accepted sends; assumption
    additive_step_per_min: float = 1.0
    backoff_factor: float = 0.5              # AIMD multiplicative decrease
    cooldown_floor_s: float = 60.0
    reserve_fraction: float = 0.20           # margin for operator/other consumers; assumption
    hard_pause_on_challenge: bool = True
```

There is no total-message cap. A user-requested loop bound such as `loop --max-iterations N` is workflow control, not account safety. Account safety comes from global spacing, single-owner allocation, challenge/login stops, backoff, and operator-attended real-site use (charter Shared-resource ceilings; M3 common constraints §2).

### Limiter mechanics

Use a single global, non-bursting token bucket plus AIMD rate adaptation:

1. `current_rate_per_min` starts at `initial_rate_per_min` and is bounded above by `60 / politeness_floor_s` unless the operator explicitly configures a smaller floor. With the default floor this upper bound is 12 sends/minute, but the real safe ceiling is unknown and must be measured.
2. The bucket capacity is `1` token. This intentionally prevents bursts; concurrent consumers queue and are released one send at a time.
3. `global_next_send_at = last_send_at + politeness_floor_s`. A permit cannot be granted before both a token is available and `global_next_send_at` has passed.
4. On each accepted send (`SendOutcome.kind == "submitted_verified"`), increment `consecutive_successes`. After `ramp_successes` accepted sends with no backoff signal, set `current_rate_per_min = min(current_rate_per_min + additive_step_per_min, 60 / politeness_floor_s)` and reset the success counter. This is the additive increase half of AIMD.
5. On a soft backoff signal, set `current_rate_per_min = max(current_rate_per_min * backoff_factor, min_rate_per_min)`, clear the token bucket, reset successes, and set `cooldown_until = now + max(retry_after_s or 0, cooldown_floor_s)`.
6. On a hard challenge/login signal, set `paused = true`, `pause_reason = "HUMAN_ACTION_NEEDED"`, and reject further `before_send` calls until the operator resolves the issue and explicitly resumes. During pause, read-only polling/status may continue only on own tabs.

This discovers capacity by increasing after verified accepted sends and decreasing on authoritative rejection signals. Backoff is a safety net, not the primary control: the primary control is that all sends in the persistent process pass through one queue/rate allocator (agent-rigor Shared-resource ceiling; REWRITE-SPEC §10).

### Backoff trigger signals

Backoff classification must avoid logging secrets, bearer tokens, OAI headers, prompt text, or full response bodies. Log only timestamp, own `conversation_id`, signal type, HTTP status, `retry_after_s`, and a short classifier string (M3 common constraints §2, §3).

```python
class BackoffSignalKind(StrEnum):
    HTTP_429 = "http_429"
    RETRY_AFTER = "retry_after"
    RATE_LIMIT_TOAST = "rate_limit_toast"
    ACCOUNT_LIMIT_MESSAGE = "account_limit_message"
    SEND_NOOP_REPEATED = "send_noop_repeated"
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    LOGIN_WALL = "login_wall"
    NETWORK_THROTTLE = "network_throttle"
```

Soft triggers:

- HTTP `429` on an own-page request/response to `https://chatgpt.com/backend-api/*`, `https://chatgpt.com/*`, or `https://*.openai.com/*`; respect `Retry-After` when present (REWRITE-SPEC §10; assumption that exact endpoints/statuses need M5 confirmation).
- HTTP `403`/`503` with response/title/text classifier indicating throttling or temporary block; classify carefully and prefer hard pause if it looks like Cloudflare (assumption).
- Error toast/alert text on an own tab matching case-insensitive regex: `rate limit|too many requests|try again later|temporarily unavailable|unusual activity|reached.*limit` (assumption; M2 did not capture error toasts).
- A visible assistant/app account-limit message on the newly-created turn matching the same regex; report as `ACCOUNT_LIMIT_MESSAGE` and back off (assumption).
- Repeated `PromptNotSubmittedError` after idle reload and composer retry: trigger after `2` consecutive failures or `3` failures in `10` minutes for the same Session, because a single no-op can be SPA staleness while repeated no-op may indicate quota/rate UI refusal (REWRITE-SPEC §6 gotcha fix; thresholds assumption).

Hard pause triggers:

- Cloudflare/challenge markers on an own tab: page title/body containing `Just a moment`, `Checking your browser`, `Verify you are human`, or `Attention Required`; CSS markers `iframe[src*="challenges.cloudflare.com"]`, `input[name="cf-turnstile-response"]`, `#challenge-stage`, `[data-cf-beacon]` (generic assumption; exact live markers need M5 confirmation).
- Login wall or auth redirect on an own tab: URL path containing `/auth/login` or visible login/signup wall. Login is never automated; return/log `HUMAN-ACTION-NEEDED` (REWRITE-SPEC §13; charter Shared-resource ceilings).

Relevant known selectors from M2 for safe send/baseline integration:

```json
{
  "composer": "#prompt-textarea",
  "message_turn": "[data-message-id][data-message-author-role]",
  "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
  "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
  "stop_button": "button[data-testid=\"stop-button\"], #composer-submit-button[aria-label*=\"Stop\" i]",
  "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button",
  "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
  "toast_or_alert_assumption": "[role=\"alert\"], [data-testid*=\"toast\"], [data-sonner-toast]",
  "cloudflare_marker_assumption": "iframe[src*=\"challenges.cloudflare.com\"], input[name=\"cf-turnstile-response\"], #challenge-stage, [data-cf-beacon]"
}
```

### Send outcome schema

```json
{
  "send_outcome": {
    "kind": "submitted_verified|not_submitted|rate_limited|challenge|aborted_before_submit|internal_error",
    "conversation_id": "string",
    "consumer_id": "string",
    "baseline_user_message_id": "string|null",
    "new_user_message_id": "string|null",
    "submitted_at": "iso8601|null",
    "backoff_signal": "string|null",
    "retry_after_s": "number|null"
  }
}
```

`submitted_verified` requires the send cluster's new-user-turn check, not just a click. `not_submitted` maps to `PromptNotSubmittedError` and is retryable. `challenge` pauses all future sends until human action (REWRITE-SPEC §6, §13; M3 common constraints gotcha fixes).

### Rate status JSON

```json
{
  "rate_budget": {
    "paused": "boolean",
    "pause_reason": "string|null",
    "current_rate_per_min": "number",
    "politeness_floor_s": "number",
    "effective_interval_s": "number",
    "cooldown_until": "iso8601|null",
    "consecutive_successes": "int",
    "registered_consumers": [
      {"consumer_id": "string", "weight": "number", "assigned_rate_per_min": "number"}
    ],
    "last_backoff": {
      "at": "iso8601",
      "kind": "string",
      "conversation_id": "string|null",
      "http_status": "int|null",
      "retry_after_s": "number|null"
    },
    "last_known_good_rate_per_min": "number|null",
    "suspected_ceiling_per_min": "number|null",
    "ceiling_empirically_measured": false
  }
}
```

`ceiling_empirically_measured` remains `false` until a later attended mission deliberately measures rate behavior. This prevents `status` from presenting AIMD's current safe rate as a proven account ceiling (M2 handoff; agent-rigor Measure complexity empirically).

## 3. Single-owner rate budget and shared-resource ceiling

The persistent `Session` is the single owner of the send budget for all in-process concurrent consumers. Do not instantiate per-loop/per-conversation independent limiters inside one Session; that would multiply account load. The invariant is:

```text
sum(assigned_send_rate_per_min for all registered in-Session consumers) + reserve_per_min <= current_safe_account_budget_per_min
```

`current_safe_account_budget_per_min` is the AIMD-controlled `current_rate_per_min` after applying the politeness floor. `reserve_per_min = reserve_fraction * current_safe_account_budget_per_min` by default. `allocatable_per_min = current_safe_account_budget_per_min - reserve_per_min`. For equal-weight consumers, each gets `allocatable_per_min / consumer_count`; for weighted consumers, `allocatable_per_min * weight_i / sum(weights)`.

Concrete allocation algorithm on `register_consumer`/`unregister_consumer` and after every AIMD rate change:

1. Compute `budget = min(current_rate_per_min, 60 / politeness_floor_s)`.
2. Compute `reserve = budget * reserve_fraction`.
3. Compute `allocatable = max(0, budget - reserve)`.
4. For each active consumer with weight `w_i`, set `assigned_rate_i = allocatable * w_i / sum(w)`.
5. Set `consumer_next_send_at[consumer_id]` so a consumer cannot exceed its assigned interval `60 / assigned_rate_i`. Also enforce the global `global_next_send_at` so aggregate sends cannot exceed the global budget.

If there is one consumer, it can use the full allocatable rate; if there are three consumers, the same global budget is shared rather than tripled. The queue should be FIFO among currently eligible consumers; if a consumer has no pending sends, its unused share is opportunistically usable by others only if doing so still respects the global interval and reserve. This keeps the design simple while avoiding badly under-using the budget (agent-rigor Shared-resource ceiling; Occam).

Backoff is not the allocation strategy. It is the safety net when the unknown real ceiling or external load is lower than the current estimate. Because the operator or another agent may also use the same account/browser outside this process, the Session cannot prove the true global sum; the reserve and modest defaults are the in-process mitigation, and the operational guidance is to route real concurrency through one persistent Session whenever possible (charter Shared-resource ceilings).

## 4. Atomic-op vs persistent-Session budget coordination

Atomic CLI operations (`ask`, `scrape`, `status`) each construct a short-lived `Session`, attach, act, and detach (REWRITE-SPEC §2, §3). Therefore an atomic `ask` process has its own fresh limiter and no shared budget with a simultaneously running persistent Session or another atomic process. There is no cross-process shared limiter unless the project deliberately builds one.

This is an honest gap, but not a reason to add a daemon/IPC coordinator now. Occam and the approved architecture reject a daemon; atomic ops are intended to be one-shot/sparse, while real loops and multi-tab concurrency live in a persistent Session (REWRITE-SPEC §2; agent-rigor Occam). The immediate guidance should be:

- Do not fan out many concurrent atomic `ask` OS processes against the same operator account.
- For fan-out, loops, or multi-conversation work, use one persistent `Session` so the tab pool and send budget have a single owner.
- Atomic `scrape` and `status` are read-only and do not consume send budget, but they still attach to the shared CDP browser and must inspect only their own tabs.
- If M7 finds real collisions between multiple processes, add the simplest explicit coordinator then, such as an opt-in per-data-dir advisory lock around send submission. Do not prebuild distributed rate machinery in M4/M5 without evidence.

Atomic `ask` should still apply a local `politeness_floor_s` before its single submit and honor hard challenge/login stops, but this local limiter must not be documented as a global guarantee.

## 5. Concurrency profile

Default profile for the persistent Session:

```json
{
  "max_active_tab_ops": 3,
  "pool_max_tabs": 6,
  "pool_idle_ttl_s": 900,
  "send_token_bucket_capacity": 1,
  "send_politeness_floor_s": 5,
  "send_initial_rate_per_min": 3,
  "send_reserve_fraction": 0.2
}
```

Interpretation:

- Up to three active tab operations at once, matching the charter's modest approximately 3-way browser guidance. This includes send UI work, capture header acquisition, backend capture fetches issued from an own page, and status checks.
- Up to six cached own tabs, so a 3-way workload can keep recently used conversations warm while idle eviction/LRU prevent unbounded page growth.
- Reads/scrapes/backend-api captures run in parallel subject to tab leases and `max_active_tab_ops`; they are not serialized by the send-rate budget. M2 measured a successful backend response at about 17.1 MB and about 5.0k mapping nodes, so capture itself should stream/persist rather than accumulate gratuitous full in-memory state, but that streaming design belongs to the capture/store lenses (M2 handoff; M3 common constraints §3).
- Sends are globally serialized by a non-bursting bucket and spaced by the politeness floor. Multiple completions can be waiting concurrently; submitting new prompts is what is rate-governed.
- All defaults are configurable and should be tuned only from attended real measurements. They are safety defaults, not a hard message cap and not a statement of the account ceiling.

## Falsifiable acceptance checks for M4/M5/M7

- Mock `context.pages` raises if accessed; tab-pool tests must still pass using only `new_page()` and pool-owned page records. This verifies the "inspect only own tabs" rule.
- Fake-clock pool tests cover lazy open, same-conversation serialization, idle eviction, LRU reclaim, all-tabs-leased `TabPoolExhaustedError`, page crash removal, and `close_all()` closing only own pages.
- Fake-clock limiter tests cover politeness spacing, no bursts, additive increase after `ramp_successes`, multiplicative decrease on 429, `Retry-After` cooldown, hard pause on Cloudflare/login, and no total-message cap.
- Shared-resource tests register 1, 2, and 3 consumers and verify `sum(assigned_rate) + reserve <= current_safe_account_budget` after each add/remove/rate change.
- Integration tests assert send cluster calls `before_send` immediately before submit and reports `submitted_verified` only after a new user turn is observed. A click without new turn must produce `PromptNotSubmittedError`, not a stale answer.
- Real attended M5/M7 probes must classify actual rate-limit/toast/challenge signals and update the marker list; until then, those strings remain assumptions.

## Cross-cluster interfaces & dependencies

Exposed by this lens to `Session`/lifecycle: `TabPool.acquire(conv_id) -> ManagedTab`, `TabPool.release(tab)`, `TabPool.evict_idle()`, `TabPool.close_all()`, and `AdaptiveSendBudget.register_consumer`, `unregister_consumer`, `before_send`, `after_send`, `record_backoff_signal`, `snapshot`. `Session.status()` should merge the pool and rate JSON schemas above.

Needed from Lens 1/session lifecycle: CDP attach/preflight, an own-page creation primitive that never enumerates operator tabs, a safe detach primitive that never quits Chromium, and lifecycle hooks to call `close_all()` before detach (REWRITE-SPEC §2, §13).

Needed from identity/allowlist: canonical parsing for bare conversation ids, `/c/<id>`, and `/g/g-p-<project_id>/c/<chat_id>`; project metadata when known; URL allowlist enforcement before any navigation (REWRITE-SPEC §9, §13; M2 projects not verified).

Needed from send/completion lenses: baseline user-turn capture before send, verified-new-user-turn outcome after submit, `PromptNotSubmittedError` on no-op, no hidden completion ceiling, and classification of UI toasts/account-limit messages on own tabs (REWRITE-SPEC §6, §7; M3 common gotcha fixes).

Needed from capture/lens 3: backend reads run in parallel through own pages; capture must never persist/log Authorization/OAI headers; HTTP 429/Retry-After on own-page backend requests should be reported to `AdaptiveSendBudget.record_backoff_signal` even if the request was read-only, because it may indicate account pressure (M2 handoff; M3 common constraints §3).

Needed from selectors/menus: real selector map includes `#prompt-textarea`, `[data-message-id][data-message-author-role]`, `[data-message-author-role="user"][data-message-id]`, `[data-message-author-role="assistant"][data-message-id]`, `button[data-testid="stop-button"], #composer-submit-button[aria-label*="Stop" i]`, `button[data-testid="send-button"], #composer-submit-button`, and fail-closed Radix menu enumeration (M2 handoff).

Needed from store: eager-write the conversation ref and user turn record at/just-before send; on error/timeout, salvage partial with `status` and `partial=true`; status/audit logs must omit bearer tokens, OAI headers, prompt secrets beyond intended transcript content, and browser page bodies (REWRITE-SPEC §8; M3 common constraints §4).

## Open questions / assumptions

- The numeric ChatGPT account send ceiling is unknown. M2 did not stress rate behavior. `initial_rate_per_min=3`, `politeness_floor_s=5`, `reserve_fraction=0.20`, and AIMD thresholds are assumptions requiring attended M5/M7 measurement.
- Exact live rate-limit/error toast strings and Cloudflare selectors were not observed in M2. The marker regexes and CSS selectors above are generic assumptions and must be replaced/confirmed from own-tab real signals.
- The exact Playwright Python method that safely detaches from a CDP-attached browser without quitting the operator's Chromium must be verified in the channel implementation. The design requires a safe `CdpConnection.detach()` abstraction.
- Project conversation URL behavior for send/create was deferred in M2. The pool supports project URL shape if identity supplies `project_id`, but live send/create in projects remains near-term unverified.
- Reads are not rate-governed by default. If attended probes show backend-api capture itself triggers meaningful throttling, add a separate lightweight read limiter; do not conflate read throttling with send budget unless evidence requires it.
- There is no cross-process limiter by design. If users run many atomic `ask` processes concurrently, account load can exceed one Session's budget. Current recommendation is operational guidance rather than daemon/IPC machinery; revisit only with evidence.
