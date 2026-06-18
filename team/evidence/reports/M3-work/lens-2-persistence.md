STATUS: DONE
Produced the Lens 2 persistence/schema design: data-dir layout, transcript JSONL schema, raw tree retention, DR/Pro grouping, attachment/citation mapping, index schema, and atomic write lifecycle.
Key decision: `raw-mapping.json` is the lossless backend snapshot; `transcript.jsonl` is the current-branch visible transcript with append-only last-writer-wins records keyed by canonical `message_id`.
Design tension surfaced: strict canonical-only `message_id` conflicts with eager-write-before-send; this design uses a minimal `local:` pending id until the real DOM/backend id is verified.

# M3 Lens 2 — Persistence + transcript schema design

## Scope and source anchors

This document designs only the on-disk persistence layer and transcript schema for the v2 rewrite; it does not modify production source and assumes no browser/CDP/network leg is run by this worker. The storage design follows the approved per-conversation layout and append-only transcript contract (REWRITE-SPEC §8), canonical conversation-id addressing (REWRITE-SPEC §9), backend capture as canonical markdown source (REWRITE-SPEC §5), verified-send/eager-write/partial-salvage gotcha fixes (REWRITE-SPEC §6-§8, §17), and the M2 observed backend JSON shapes: ~17.1 MB one-response capture, ~5.0k mapping nodes, tree-shaped `mapping`, text bodies in `message.content.parts`, DR/Pro represented by large `turn_exchange_id` groups, citation/search metadata fields, and the four attachment-reference shapes (M2 handoff).

Implementation module target: `store.py` owns the filesystem layout, atomic appends/replacements, transcript/index reads, attachment local-path updates, and conversion from normalized capture records into JSONL. It must never receive, persist, or log backend request `authorization`/OAI header values; capture code may pass only the response JSON/body plus sanitized per-turn metadata (M2 handoff; REWRITE-SPEC §13).

## 1. Data-dir layout

Data root resolution is deterministic: CLI `--data-dir` wins, then `ASK_CHATGPT_DATA_DIR`, then default `~/.local/state/ask-chatgpt/` (REWRITE-SPEC §8). All directories should be created mode `0700` where the platform permits, because transcripts and raw backend JSON contain operator conversation data (safety invariant from team charter).

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

File semantics:

| Path | Semantics | Write mode | Source |
|---|---|---|---|
| `index.json` | Convenience index mapping aliases/session ids and known conversations to `conversation_id`, `model`, `project_id`, `title`, and `last_updated`; never required to address a known chat because URL/bare id addressing is stateless. | Atomic replace under an index lock. | REWRITE-SPEC §8-§9 |
| `conversations/<conversation-id>/transcript.jsonl` | Append-only normalized transcript, one JSON object per visible current-branch message plus pending/salvage updates; reads collapse by last-writer-wins per `message_id`. | Append line + fsync under a per-conversation lock. | REWRITE-SPEC §8 |
| `conversations/<conversation-id>/raw-mapping.json` | Latest full backend conversation response JSON, including all top-level keys and the complete `mapping` tree, not just current branch; no auth/request headers. This is the lossless source for hidden nodes, branches, citations, attachment refs, and any fields not normalized into transcript records. | Stream/write to temp file, fsync, rename, fsync directory. | REWRITE-SPEC §8; M2 handoff |
| `conversations/<conversation-id>/attachments/` | Lazy local cache for downloaded/generated artifacts. Empty until `fetch` is requested. | Each artifact writes `*.partial` then renames; transcript is updated by appending a replacement record with `local_path`, `bytes`, `sha256`. | REWRITE-SPEC §8; M2 handoff |
| `conversations/<conversation-id>/.gitignore` | Contains exactly `attachments/` so lazy artifact bytes are ignored if a user places the data dir under a repository. | Create-if-missing. | REWRITE-SPEC §8 |

Concrete store API signatures for M4/M5:

```python
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal

@dataclass(frozen=True)
class ConversationPaths:
    data_dir: Path
    conversation_dir: Path
    transcript_jsonl: Path
    raw_mapping_json: Path
    attachments_dir: Path
    gitignore: Path

@dataclass(frozen=True)
class ConversationRef:
    conversation_id: str
    project_id: str | None
    url: str | None

VisibilityDecision = Literal["visible", "hidden", "salvage_only"]

def resolve_data_dir(cli_data_dir: str | Path | None, env: Mapping[str, str]) -> Path: ...
def ensure_conversation_store(data_dir: Path, conversation_id: str) -> ConversationPaths: ...
def write_raw_mapping(paths: ConversationPaths, raw_json_bytes: Iterable[bytes] | BinaryIO) -> None: ...
def materialize_current_branch(paths: ConversationPaths, *, visibility_classifier: "VisibilityClassifier") -> list[dict[str, Any]]: ...
def append_transcript_records(paths: ConversationPaths, records: Sequence[dict[str, Any]]) -> None: ...
def read_transcript(paths: ConversationPaths, *, include_pending: bool = False) -> list[dict[str, Any]]: ...
def update_index(data_dir: Path, patch: dict[str, Any]) -> None: ...
def update_attachment_local_path(paths: ConversationPaths, message_id: str, source_ref: dict[str, Any], local_path: str, bytes: int, sha256: str) -> None: ...
```

Memory discipline: capture should stream the backend response body to `raw-mapping.json` before normalization and should not concatenate multiple full copies in memory. Normalization may build a compact in-memory node index for the measured ~17.1 MB/~5.0k-node response, but it must process records incrementally and append them promptly; if captures grow materially beyond M2 scale, the same API supports replacing `json.load` with an event parser without changing the on-disk contract (M2 handoff; agent-rigor empirical scale rule).

## 2. `transcript.jsonl` per-turn record — full schema

Each line is one UTF-8 JSON object with stable field names. Required fields are present on every line; some values may be `null` only for a pending eager-write stub before ChatGPT has exposed the canonical backend/DOM id or timestamp. Any complete backend-derived record must use the canonical `message_id` and backend timestamp; agent wall-clock time is never a substitute for `created_at` (REWRITE-SPEC §8; M2 handoff).

```jsonc
{
  "conversation_id": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31",
  "message_id": "<backend-or-dom-message-id>",
  "parent_id": "<raw-parent-node-id-or-null>",
  "turn_index": 0,
  "role": "user",
  "content_markdown": "canonical markdown, untruncated",
  "model": {"slug": "<model-slug-or-null>", "display": "Pro Extended"},
  "active_tools": ["deep_research"],
  "kind": "normal",
  "created_at": "2026-06-18T00:00:00.000000Z",
  "attachments": [],
  "citations": [],
  "status": "complete",
  "partial": false,
  "turn_exchange_id": "<optional backend turn_exchange_id>",
  "client_op_id": "<optional local send operation id>",
  "supersedes_message_id": "<optional local: pending id>"
}
```

Field table:

| Field | Type | Semantics | Source |
|---|---|---|---|
| `conversation_id` | `string` | Canonical conversation key and directory name; parsed from `/c/<id>` or `/g/g-p-<project-id>/c/<chat-id>`. | REWRITE-SPEC §9 |
| `message_id` | `string` | Idempotency key and send-verification baseline. For backend-derived records use `message.id` if present, otherwise the `mapping` node id; M5 must verify this matches DOM `data-message-id` for visible turns. For eager-write before the id exists, the only allowed non-canonical value is `local:<client_op_id>`. | REWRITE-SPEC §6, §8; M2 handoff; pending-id exception is a design assumption |
| `parent_id` | `string|null` | Raw tree parent id from `mapping[node_id].parent`; it may point to a hidden node, not necessarily the previous visible transcript record. | REWRITE-SPEC §8; M2 handoff |
| `turn_index` | `integer|null` | Zero-based order among visible records on the current branch after reversing the `current_node` parent walk. `null` is allowed only for pending local stubs before the current branch is known. | REWRITE-SPEC §8 |
| `role` | `"user"|"assistant"|"tool"|"system"` | Author role from `message.author.role`; current UI transcripts normally emit visible `user`/`assistant` records, but the enum admits observed roles if Lens 3 classifies one visible. | M2 handoff |
| `content_markdown` | `string` | Canonical, untruncated markdown for the visible message. For `message.content.content_type == "text"`, capture/lens-3 extracts string parts from `message.content.parts`; one-part reports use `parts[0]` exactly. If multiple string parts occur, join with `"\n\n"` and rely on `raw-mapping.json` for exact part boundaries. | REWRITE-SPEC §5, §8; M2 handoff; multi-part join is an assumption |
| `model` | `object` | Model state independent of tools: `{slug: string|null, display: string|null}`. `slug` comes from per-message metadata if present, else top-level `default_model_slug` for scrape-only records; `display` comes from verified UI/model-picker state on sends when known, else `null`. | REWRITE-SPEC §8, §11; M2 handoff |
| `active_tools` | `string[]` | Stable tool slugs active for the turn, orthogonal to model; current expected slugs include `deep_research`, `web_search`, `create_image`, `agent_mode`, and implementation-defined connector slugs. | REWRITE-SPEC §8, §11; M2 handoff |
| `kind` | `"normal"|"deep_research"|"image"|"code_execution"|"file_reference"|string` | Coarse visible product type for routing/export. Use `deep_research` for the visible final report of a DR/Pro `turn_exchange_id` group, `image` for generated image/asset turns, `code_execution` when the visible turn is primarily code-exec output, else `normal`; open string enum avoids schema churn. | REWRITE-SPEC §8; M2 handoff |
| `created_at` | RFC3339 UTC `string|null` | Backend message timestamp normalized from `message.create_time` or equivalent backend field. Never an agent self-report. `null` only for pending local stubs or malformed legacy records that must remain readable. | REWRITE-SPEC §8; M2 handoff |
| `attachments` | `AttachmentRecord[]` | Downloadable or locally materializable artifacts associated with this visible record; bytes are lazy and may have `local_path:null`. Web citations are excluded. | REWRITE-SPEC §8; M2 handoff |
| `citations` | `CitationRecord[]` | Web/source citations and search references for the visible assistant report; never downloaded by `fetch`. File refs go to `attachments`, not `citations`, unless Lens 3 later needs a separate rendered footnote. | REWRITE-SPEC §8; M2 handoff |
| `status` | `"complete"|"partial"|"error"` | `complete` means backend/canonical capture finished; `partial` means salvage or pending work; `error` means the record exists to preserve prompt/partial text after a failed operation. | REWRITE-SPEC §8, §17 |
| `partial` | `boolean` | Redundant but convenient flag for CLI/API consumers; must be `false` iff `status == "complete"`. | REWRITE-SPEC §8 |
| `turn_exchange_id` | `string|null` optional | Backend grouping key tying one user prompt, hidden assistant/tool internals, and the visible final report together; stored because DR/Pro is represented by groups rather than a `deep_research` content type. | M2 handoff |
| `client_op_id` | `string|null` optional | Local UUID/ULID generated for one `ask` send attempt; lets recovery link the pre-send pending stub to the later canonical user-turn record without relying on prompt text alone. | Required by eager-write invariant; design assumption |
| `supersedes_message_id` | `string|null` optional | Set on a canonical replacement record when it supersedes a `local:<client_op_id>` pending stub. Readers hide superseded local records by default. | Required by eager-write invariant; design assumption |

Read semantics are deterministic: parse lines in file order, ignore at most one trailing invalid partial line after a crash with a warning, group by `message_id`, keep the last valid record for each id, then hide records whose `message_id` is referenced by a later `supersedes_message_id` unless `include_pending=True`. Sort visible history by `(turn_index is null, turn_index, created_at or "", message_id)`.

## 3. Tree → current-branch linearization

The backend response is a message tree: top-level `mapping` is keyed by node id, each node has `parent`/`children` and optional `message`, and top-level `current_node` identifies the current UI branch leaf (REWRITE-SPEC §8; M2 handoff). `raw-mapping.json` stores the full response so branch history and hidden internals are not thrown away; `transcript.jsonl` emits only Lens-3-visible messages on the current branch. Branch-aware history is deferred until a later feature because the raw tree is retained meanwhile (REWRITE-SPEC §15).

Algorithm:

```python
def linearize_current_branch(raw: dict[str, Any], classify: "VisibilityClassifier") -> list[dict[str, Any]]:
    mapping = raw["mapping"]
    node_id = raw["current_node"]
    branch: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    while node_id:
        if node_id in seen:
            raise RawMappingShapeError("cycle in mapping parent chain")
        seen.add(node_id)
        node = mapping[node_id]
        branch.append((node_id, node))
        node_id = node.get("parent")
    branch.reverse()

    groups = index_by_turn_exchange_id(branch, mapping)
    records = []
    visible_index = 0
    for node_id, node in branch:
        msg = node.get("message")
        if msg is None:
            continue
        decision = classify(node_id=node_id, node=node, raw=raw)
        if decision != "visible":
            continue
        record = normalize_visible_message(
            raw=raw,
            node_id=node_id,
            node=node,
            visible_turn_index=visible_index,
            exchange_group=groups.get(turn_exchange_id(msg)),
        )
        records.append(record)
        visible_index += 1
    return records
```

Important details:

1. Use `current_node` parent links, not DOM order, to choose the branch; DOM is a fallback capture surface only (REWRITE-SPEC §5, §8).
2. Do not discard unknown top-level fields, unknown message metadata, hidden tool nodes, or side branches; all remain in `raw-mapping.json` (M2 handoff).
3. Visibility is not defined in this lens. `classify(...)` is supplied by Lens 3 and must decide visible-vs-hidden for observed roles/content types such as `assistant:thoughts`, `assistant:code`, `assistant:reasoning_recap`, `assistant:model_editable_context`, `tool:tether_browsing_display`, `tool:execution_output`, `tool:multimodal_text`, and `system:text` (M2 handoff).
4. `parent_id` in transcript is the raw parent id even if hidden. This avoids inventing a new parent relation and lets a consumer jump back into `raw-mapping.json` exactly.
5. Attachments/citations are collected from the visible message itself and, for a visible final assistant report, from hidden same-`turn_exchange_id` nodes that contain asset/code/file refs; the raw path of every collected ref points back to `raw-mapping.json`.

## 4. Deep-Research / Pro turn representation

M2 observed no `content_type == "deep_research"`; DR/Pro appears as a large `turn_exchange_id` group containing one user message, many hidden assistant/tool nodes, and one visible final `assistant:text` report whose body is `message.content.parts[0]` (M2 handoff). Therefore persistence records DR/Pro as a normal visible transcript plus explicit grouping metadata, not as a separate tree.

Mapping rules:

| Backend shape | Transcript effect | Source |
|---|---|---|
| User message in a DR/Pro `turn_exchange_id` group | Emit a visible user record if Lens 3 says visible; set `turn_exchange_id`; set `active_tools` to include `deep_research` when send/capture can verify that the group is DR; `kind` may be `deep_research` for the user prompt if the synthesizer wants turn-level labeling, otherwise `normal`. | M2 handoff; REWRITE-SPEC §11 |
| Hidden `assistant:thoughts`, `assistant:code`, `assistant:reasoning_recap`, tool `execution_output`, `tether_browsing_display`, `multimodal_text` | Do not emit standalone transcript records unless Lens 3 later classifies one visible; retain losslessly in `raw-mapping.json`; extract only attachment refs needed on the visible final report. | M2 handoff |
| Visible final `assistant:text` report | Emit one assistant record with `content_markdown = parts[0]` when there is a single string part, `kind="deep_research"`, `active_tools` containing `deep_research`, and `turn_exchange_id` set. | M2 handoff; REWRITE-SPEC §8, §11 |
| Citation/search metadata on final assistant message (`content_references`, `citations`, `search_result_groups`, `search_queries`) | Normalize web/source citations into `citations[]`; file refs into `attachments[]`; leave complete metadata in raw. | M2 handoff |

DR detection precedence: verified UI tool state from send context wins for new `ask` calls; for scrape-only existing turns, classify as `deep_research` when the same `turn_exchange_id` group has the M2-observed pattern of one user message, hidden reasoning/tool/code nodes, and a visible final `assistant:text` report with citation/search metadata. This heuristic must be marked as scrape-derived and verified in M5; it should fail to `kind="normal"` rather than invent `deep_research` when the pattern is absent (agent-rigor falsifiability; M2 handoff).

## 5. Attachment representation — all M2 shapes

Attachment and citation are intentionally separate. Attachments are downloadable or locally materializable artifacts; citations are web/source references and are never downloaded by `fetch` (REWRITE-SPEC §8; M2 handoff). M2 observed no literal `/backend-api/files/...`, `sandbox:`, or `attachment:` URL strings, so persistence stores ids, asset pointers, and raw JSON paths; byte download is a later lazy fetch step.

`AttachmentRecord` schema:

```jsonc
{
  "filename": "plot.png",
  "mime": "image/png",
  "bytes": 12345,
  "sha256": null,
  "source_ref": {
    "kind": "asset_pointer",
    "raw_path": "/mapping/<node-id>/message/content/assets/0",
    "node_id": "<node-id>",
    "message_id": "<message-id-or-null>",
    "turn_exchange_id": "<turn-exchange-id-or-null>",
    "ref_id": null,
    "asset_pointer": "<asset-pointer>",
    "run_id": null,
    "input_pointer": null,
    "metadata": {}
  },
  "local_path": null
}
```

Attachment fields:

| Field | Type | Semantics | Source |
|---|---|---|---|
| `filename` | `string|null` | Display or safe target filename when known. Use user/file `name`; for generated assets use metadata name if present else a sanitized pointer-derived name; for aggregate results use `run_<run_id>_aggregate.json` if materialized. | M2 handoff |
| `mime` | `string|null` | MIME/content type when provided; use `message.content.assets[].content_type` for generated assets; otherwise `null` until fetch/sniff if needed. | M2 handoff |
| `bytes` | `integer|null` | Source-declared size (`size` or `size_bytes`) when present, or local file size after fetch/materialization; `null` if unknown. | M2 handoff |
| `sha256` | lowercase hex `string|null` | Hash of local bytes after lazy fetch/materialization; `null` before bytes exist. Never hash remote metadata. | REWRITE-SPEC §8 |
| `source_ref` | `object` | Structured pointer to the raw backend reference and enough stable ids for a future downloader. Must never contain auth/OAI headers. | M2 handoff; REWRITE-SPEC §13 |
| `local_path` | relative path `string|null` | Relative path under the conversation dir, normally `attachments/<sha256>__<safe-filename>`; `null` until lazy fetch succeeds. Absolute paths are not stored. | REWRITE-SPEC §8 |

`source_ref` common fields:

| Field | Type | Semantics |
|---|---|---|
| `kind` | `"user_upload"|"file_content_reference"|"asset_pointer"|"code_execution_aggregate"|string` | Source shape discriminator. |
| `raw_path` | JSON Pointer `string` | Exact path inside `raw-mapping.json`, with node ids escaped per JSON Pointer rules. |
| `node_id` | `string` | Mapping node containing the reference. |
| `message_id` | `string|null` | Backend message id if present. |
| `turn_exchange_id` | `string|null` | Group id if present. |
| `ref_id` | `string|null` | File/reference id such as `file_...` or content-reference `id`. |
| `asset_pointer` | `string|null` | Generated/image asset pointer when present. |
| `run_id` | `string|null` | Code execution run id when present. |
| `input_pointer` | `object|null` | File-reference input pointer with file index, line range, message id, and message index when present. |
| `metadata` | `object` | Small non-secret fields needed for fetch/display, e.g. `source`, `is_big_paste`, dimensions, status, timing booleans. Full raw object remains in `raw-mapping.json`. |

Mapping table for every M2 attachment shape:

| M2 shape | Transcript attachment mapping |
|---|---|
| `message.metadata.attachments[]` user uploads with keys `id`, `size`, `name`, `file_token_size`, `source`, `is_big_paste` | Create `AttachmentRecord` on the visible user message. `filename=name`, `mime=null`, `bytes=size`, `sha256=null`, `local_path=null`, `source_ref.kind="user_upload"`, `source_ref.ref_id=id`, `source_ref.metadata={"source": source, "file_token_size": file_token_size, "is_big_paste": is_big_paste}`. |
| `message.metadata.content_references[]` where `type == "file"`, with keys such as `id`, `name`, `source`, `snippet`, `cloud_doc_url`, `library_file_id`, `library_artifact_type`, `medical_file_reference`, `drug_file_reference`, `page_range_start`, `page_range_end`, `input_pointer`, `fff_metadata`, `connector_id` | Create `AttachmentRecord` on the visible message carrying the file reference, or on the visible final assistant report for same-`turn_exchange_id` hidden refs. `filename=name`, `mime=null`, `bytes=null`, `source_ref.kind="file_content_reference"`, `source_ref.ref_id=id`, `source_ref.input_pointer=input_pointer`, and `source_ref.metadata` stores the listed non-secret fields except large snippets may be truncated for display only while full snippet remains raw. |
| `message.content.assets[]` on tool `tether_browsing_display`, with `content_type`, `asset_pointer`, `size_bytes`, `width`, `height`, `fovea`, `metadata` | Attach to the nearest visible assistant report in the same `turn_exchange_id`; if no group exists, attach to the visible record Lens 3 associates with that tool node. `filename` from metadata or sanitized `asset_pointer`, `mime=content_type`, `bytes=size_bytes`, `source_ref.kind="asset_pointer"`, `source_ref.asset_pointer=asset_pointer`, `source_ref.metadata={"width": width, "height": height, "fovea": fovea, "metadata": metadata}`. |
| `message.metadata.aggregate_result` on tool `execution_output`, with `code`, `messages`, `jupyter_messages`, `final_expression_output`, `run_id`, `status`, timing, exception fields | If it represents or references a downloadable/local artifact, create `AttachmentRecord` on the visible assistant report in the same `turn_exchange_id`; otherwise raw retention is sufficient and no transcript attachment is required. When materialized, use `filename="run_<run_id>_aggregate.json"`, `mime="application/json"`, `bytes=null`, `source_ref.kind="code_execution_aggregate"`, `source_ref.run_id=run_id`, and `source_ref.metadata={"status": status, "has_exception": <bool>, "timing_keys": [...]}` while the full aggregate remains raw. |

`CitationRecord` schema:

```jsonc
{
  "title": "Source title",
  "url": "https://example.com/article",
  "source": "citations",
  "citation_type": "grouped_webpages",
  "start_ix": 10,
  "end_ix": 42,
  "citation_format_type": "<format-or-null>",
  "raw_path": "/mapping/<node-id>/message/metadata/citations/0"
}
```

`citations[]` should include DR web-source `{title,url}` entries from `message.metadata.citations`, web `content_references` such as `grouped_webpages`/`sources_footnote`, and any source groups Lens 3 decides are user-visible. Offsets (`start_ix`, `end_ix`) and `citation_format_type` are optional but stored when present because M2 observed them. `search_queries` are retained in raw and should not be promoted to citations unless linked to a displayed source; this avoids treating internal search telemetry as a citation (M2 handoff; Occam).

## 6. `index.json` schema

`index.json` is a convenience cache only; URL or bare id remains sufficient to address a chat even if the index is absent or stale (REWRITE-SPEC §9). It should be rebuilt opportunistically from conversation directories when corrupt or missing.

```jsonc
{
  "schema_version": 1,
  "aliases": {
    "math-long": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"
  },
  "sessions": {
    "last": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31"
  },
  "conversations": {
    "6a316aa8-5dc8-83ea-9014-b8ea38dabc31": {
      "conversation_id": "6a316aa8-5dc8-83ea-9014-b8ea38dabc31",
      "model": {"slug": "<default_model_slug-or-null>", "display": "Pro Extended"},
      "project_id": null,
      "title": "<backend title or null>",
      "last_updated": "2026-06-18T00:00:00.000000Z"
    }
  }
}
```

Field rules:

| Field | Type | Semantics | Source |
|---|---|---|---|
| `schema_version` | `integer` | Index schema version, starting at `1`; transcript records do not need this because each JSONL line is self-describing and append-only. | Design assumption |
| `aliases` | `object<string,string>` | Optional operator/user aliases to `conversation_id`; aliases are never canonical. | REWRITE-SPEC §9 |
| `sessions` | `object<string,string>` | Optional legacy/session-id convenience names to `conversation_id`; not required for stateless addressing. | REWRITE-SPEC §9 |
| `conversations` | `object<string,ConversationIndexEntry>` | Known conversations discovered by `ask`, `scrape`, `history`, or index rebuild. | REWRITE-SPEC §8-§9 |
| `conversation_id` | `string` | Redundant self-key for robust JSON object use. | REWRITE-SPEC §9 |
| `model` | `{slug:string|null, display:string|null}` | Latest known model metadata, independent of active tools. | REWRITE-SPEC §8, §11 |
| `project_id` | `string|null` | Parsed project id from `/g/g-p-<project-id>/c/<chat-id>` or backend metadata if later verified; `null` for plain `/c/<id>`. Project send/create remains not live-verified by M2. | REWRITE-SPEC §9; M2 handoff |
| `title` | `string|null` | Backend top-level `title` when available. | M2 handoff |
| `last_updated` | RFC3339 UTC `string|null` | Backend top-level `update_time` when available; not an agent wall-clock. `null` is allowed for a newly created/pending local conversation before capture. | REWRITE-SPEC §8; M2 handoff |

Identity parser contract:

```python
def parse_conversation_ref(ref: str) -> ConversationRef:
    """Accept bare conversation id, https://chatgpt.com/c/<id>, or https://chatgpt.com/g/g-p-<project-id>/c/<chat-id>. Return canonical conversation_id and nullable project_id; reject other hosts by allowlist before any browser action."""
```

## 7. Write discipline: lose nothing, atomicity, and idempotent re-scrape

Lifecycle for `ask`:

1. Resolve `ConversationRef` and ensure the store exists before touching the UI. If creating a new chat and the final conversation id is not known yet, the send cluster must persist the first URL/id as soon as the browser exposes it, then continue with the normal store path (REWRITE-SPEC §8-§9).
2. Before submitting the prompt, append a pending user stub with `message_id="local:<client_op_id>"`, `client_op_id`, `conversation_id`, `parent_id=<baseline latest user/assistant id if known>`, `turn_index=null`, `role="user"`, `content_markdown=<prompt>`, verified `model`/`active_tools`, `status="partial"`, `partial=true`, `created_at=null`. This is the minimal exception to canonical `message_id` needed to satisfy eager-write before send.
3. Send cluster captures the baseline from its own opened tab using M2 selectors `[data-message-author-role="user"][data-message-id]` and `[data-message-author-role="assistant"][data-message-id]`, fills `#prompt-textarea`, submits, and verifies a new user turn; persistence does not decide send success but stores the verified id it is given (REWRITE-SPEC §6; M2 handoff).
4. Once a new user turn id is verified, append the canonical user record with real `message_id`, `supersedes_message_id="local:<client_op_id>"`, backend `created_at` when capture is available, and `status="complete"` once backend scrape confirms it. If capture is not yet available, keep `status="partial"` but use the canonical id.
5. Completion/capture appends the new assistant record only when it is newer than the pre-send baseline. Full response capture appends `status="complete", partial=false`; timeout/error appends the best visible partial text with `status="partial"` or `status="error"`, `partial=true`, and no hidden hard total-wait ceiling (REWRITE-SPEC §7-§8, §17).
6. A later scrape is idempotent: write latest `raw-mapping.json`, materialize current branch, append normalized records. Reads keep the last record per `message_id`, so corrected `turn_index`, citations, attachments, `created_at`, and `status` replace older partial lines without in-place mutation.

Atomic mechanics:

| Operation | Mechanic | Crash result |
|---|---|---|
| Ensure directories | `mkdir(parents=True, exist_ok=True)` then create `.gitignore` if absent. | Existing transcript/raw files untouched. |
| Append transcript | Acquire advisory exclusive lock on `transcript.jsonl`; serialize each record as compact JSON with no embedded newlines; write one line; flush and `fsync`; release lock. | Prior complete lines survive. Reader may ignore one trailing invalid line after abrupt crash. |
| Replace `raw-mapping.json` | Write `raw-mapping.json.tmp.<pid>` in same dir; stream bytes; `fsync`; `os.replace`; `fsync` parent dir. | Old raw remains or new raw is complete; never half-replaced. |
| Replace `index.json` | Lock, read current or initialize empty, apply patch, write temp, `fsync`, `os.replace`, `fsync` parent. | Old index remains or new index is complete; index can be rebuilt from stores if lost. |
| Fetch attachment bytes | Write `attachments/<name>.partial`; verify size/hash; rename to final `attachments/<sha256>__<safe-name>`; append transcript replacement record with updated attachment `local_path`, `bytes`, `sha256`. | Partial file can be deleted on next fetch; transcript still points to `local_path:null` until success. |

No write path may log or persist web-app bearer/OAI headers, even inside exception strings. Store-level errors should include file path, conversation id, and safe record ids only (team charter safety invariant; M2 handoff).

## Cross-cluster interfaces & dependencies

Exposed to API/CLI/result-object cluster: `read_transcript(ref)` returns current visible history without browser access; `append_transcript_records(...)` supports `ask`/`scrape`; `update_attachment_local_path(...)` supports `fetch`; `index.json` provides alias/session convenience while `parse_conversation_ref(...)` allows stateless URL/id addressing. `Session.ask(...)` should print the latest new assistant record's `content_markdown` to stdout and optionally `--out`; `Session.scrape(...)` should populate `raw-mapping.json`/`transcript.jsonl` and render/export from `read_transcript` rather than from DOM (REWRITE-SPEC §3-§4, §8).

Required from capture/Lens 3: a sanitized backend response body for `raw-mapping.json`; a `VisibilityClassifier` for observed roles/content types; canonical markdown extraction rules for `message.content.parts`, code/text fallback, and lossy-fallback status; normalized citation extraction from `metadata.content_references`, `metadata.citations`, `metadata.search_result_groups`, and `metadata.search_queries`; attachment association rules for hidden same-`turn_exchange_id` nodes; and a guarantee that auth/OAI headers used to fetch `/backend-api/conversation/<id>` are never passed to store (M2 handoff; REWRITE-SPEC §5, §13).

Required from send/completion cluster: baseline and new-turn ids from tool-opened tabs only, using M2 selectors `[data-message-author-role="user"][data-message-id]`, `[data-message-author-role="assistant"][data-message-id]`, composer `#prompt-textarea`, stop button `button[data-testid="stop-button"], #composer-submit-button[aria-label*="Stop" i]`, and send control `button[data-testid="send-button"], #composer-submit-button` where applicable; verified model display/slug and active tool slugs before send; `client_op_id`; partial visible text on error/timeout; and completion status that is gated on a turn newer than the baseline (REWRITE-SPEC §6-§7; M2 handoff).

Required from identity/safety/channel cluster: host allowlist and URL parser for `/c/<id>` and `/g/g-p-<project-id>/c/<chat-id>`; CDP preflight and human-action-needed handling before real legs; no iteration over existing browser pages; and no browser quit. Store itself is browser-free, so `history/export` must work offline from JSONL alone (REWRITE-SPEC §9, §13-§14; team charter).

Required from attachment-fetch cluster: a downloader/materializer that accepts `conversation_id` plus `AttachmentRecord.source_ref`, obtains any required transient auth from a tool-opened page at fetch time, writes bytes only under `attachments/`, computes `sha256`, and returns `(local_path, bytes, sha256)` without treating citations as downloadable artifacts (REWRITE-SPEC §8; M2 handoff).

## Open questions / assumptions

1. Pending ids: strict canonical-only `message_id` is incompatible with an eager-write before the browser/backend exposes the new id. This design assumes `local:<client_op_id>` pending ids are acceptable as the minimal exception; if the synthesizer rejects this, it must add a separate outbox/pending-send file, which the current contract did not name.
2. Backend id equivalence: M5 must verify whether backend `message.id`, mapping node id, and DOM `data-message-id` are always identical for visible turns. Until verified, canonical selection is `message.id` when present else node id, and raw-mapping remains the authority.
3. DR classification for scrape-only history is heuristic because M2 observed group shape but no explicit `deep_research` content type. Verified UI tool state should be authoritative for new sends; scrape-only classification should prefer `normal` over overclaiming DR when the pattern is ambiguous.
4. Projects: URL parsing and `project_id` storage are designed for both `/c/<id>` and `/g/g-p-<project-id>/c/<chat-id>`, but M2 did not live-verify project send/create behavior. Store should accept project metadata without assuming project-specific send mechanics.
5. Raw snapshot history: the spec names a single `raw-mapping.json`. This design keeps only the latest full backend snapshot plus append-only transcript lines. If backend ever prunes side branches, preserving historical raw snapshots would require an additional file/dir not requested here.
6. Attachment fetching: M2 saw ids/pointers/metadata, not literal download URLs. `source_ref` is therefore a stable deferred-fetch pointer, not a proven download recipe; M5/fetch work must verify endpoint mechanics without persisting tokens.
7. Multi-part `content.parts`: M2 visible assistant reports used string parts and sampled reports lived in `parts[0]`; if multiple string parts become common, joining with blank lines is a transcript normalization assumption while exact boundaries remain in `raw-mapping.json`.
8. Potentially over-engineered fields: `turn_exchange_id`, citation offsets, and pending-send fields add schema surface. They are kept because M2 observed DR grouping/offsets and the lose-nothing invariant requires pre-id pending state; if later evidence shows they are unnecessary, readers can ignore them while raw remains lossless.
