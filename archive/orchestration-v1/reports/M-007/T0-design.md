# M-007 T0-design — fenced-format alignment (best-of-N N=3 synthesis)

Authoritative implementation spec for the T1 single editor. Synthesizes 3 independent read-only design lenses (A=parser-robustness, B=safety-preservation, C=prompt-elicitation), all reasoning from the byte-exact M-006 ground truth. The lenses CONVERGED; conflicts resolved below. **This spec + the named source files are self-contained — the editor needs nothing else.**

## Ground truth (M-006 T3-uc2char, byte-exact real DOM capture)
Real GPT emitted (and the decoded 144-byte zip was verified: single member `example.txt`, regular file, unencrypted, sha `3dce3bc5…`, NO embedded `manifest.json`):
```
BEGIN_PATCH_BUNDLE
MANIFEST_JSON {"version":1,"change":"example.txt favorite_color red to blue"}
ZIP_BYTE_COUNT 144
ZIP_SHA256 3dce3bc5690138135aca9a04e04973c7f75f36e337e1579bf63230a69fbbd050
BASE64URL UEsDBBQAAAAAAAAAIQCdm2LOGAAAABgAAAALAAAAZXhhbXBsZS50eHRmYXZvcml0ZV9jb2xvciA9ICJibHVlIgpQSwECFAMUAAAAAAAAACEAnZtizhgAAAAYAAAACwAAAAAAAAAAAAAApIEAAAAAZXhhbXBsZS50eHRQSwUGAAAAAAEAAQA5AAAAQQAAAAAA
END_PATCH_BUNDLE
```
This rejects today's parser at 3 points: no colon after keys (`patch.py:446`), BASE64URL payload inline not standalone (`patch.py:452`), and the freeform outer manifest lacks `zip_byte_count`/`zip_sha256` (`patch.py:498-501`); the apply path then also rejects it for the missing embedded `manifest.json` (`patch.py:600-601`).

## CANONICAL ALIGNED FORMAT (the one target all three sides converge on)
Prompt REQUESTS exactly this; parser ACCEPTS this (and the legacy colon form for back-compat); mock EMITS this:
```
BEGIN_PATCH_BUNDLE
ZIP_BYTE_COUNT <decimal byte length of the zip>
ZIP_SHA256 <lowercase 64-hex sha256 of the exact zip bytes>
BASE64URL <unpadded base64url of the zip bytes, one unbroken token on THIS line>
END_PATCH_BUNDLE
```
- Keys are **space-separated, no colon** (GPT's natural output). BASE64URL payload **inline on its own key line**.
- The **fenced `MANIFEST_JSON` line is OPTIONAL/advisory** — parser tolerates it if present (parse for diagnostics only, do NOT cross-check), tolerates its absence. Prompt no longer requests it.
- The **embedded `manifest.json` file inside the zip is OPTIONAL** — present ⇒ strict schema path (+ deletions); absent ⇒ reconstruct-from-zip-entries (modified/added only). These are two DIFFERENT things; keep them distinct in code/comments.

## INVARIANTS — must hold after the change (verify, don't assume)
1. **Backward-compat:** the legacy colon form (`MANIFEST_JSON:`/`ZIP_BYTE_COUNT:`/`ZIP_SHA256:`/standalone `BASE64URL:` + payload-on-next-line) and manifest-bearing zips MUST still parse+apply. Existing default-tier tests stay green (≥169 passed / 1 deselected at HEAD).
2. **Safety invariant (PATCH APPLY):** validate ENTIRE bundle (byte-count, SHA-256, every path) BEFORE mutating ANY file; reject absolute paths, `..`, backslashes, drive letters, symlink entries/parents, encrypted entries, special files; write only within the caller root (+ `tmp/` in tests). Dry-run writes nothing.
3. **Fail-closed:** truncation/malformed/bad-alphabet/sha-mismatch/bytecount-mismatch all raise the existing errors (`ResponseTruncatedError`, `PatchMalformedError`, `OversizedPayloadError`, `BundleIntegrityError`). No new exception type is required.

---

## CHANGE 1 — parser tolerance (`src/ask_chatgpt/patch.py`, `_parse_fenced_patch_bundle` ~428-503)
Replace the colon-prefix constants (`patch.py:57-60`) with separator-tolerant, keyed regexes; keep `_HEX64_RE`,`_DECIMAL_RE`,`_BEGIN_PATCH_BUNDLE`,`_END_PATCH_BUNDLE` (52-56):
```python
_MANIFEST_LINE_RE   = re.compile(r"^MANIFEST_JSON\s*:?\s+(?P<value>.*\S)\s*$")
_ZIP_BYTE_COUNT_RE  = re.compile(r"^ZIP_BYTE_COUNT\s*:?\s+(?P<value>\S+)\s*$")
_ZIP_SHA256_RE      = re.compile(r"^ZIP_SHA256\s*:?\s+(?P<value>\S+)\s*$")
_BASE64URL_RE_LINE  = re.compile(r"^BASE64URL\s*:?\s*(?P<value>.*)$")   # value MAY be inline payload or empty
```
Tighten the alphabet validator `patch.py:54` `_BASE64URL_RE` `*`→`+` (empty payload must fail), optionally rename `_BASE64URL_ALPHABET_RE`.

Rewrite the body from ~443: **keyed scan, not positional.** Dispatch each non-empty `block` line by which uppercase keyword it `startswith`; once the `BASE64URL` line is seen, switch to payload mode and treat ALL remaining lines as payload. Then:
```python
payload_lines = [inline_payload, *raw_lines_after_base64url]
encoded = "".join("".join(line.split()) for line in payload_lines)   # strip ALL internal whitespace (soft-wrap tolerant)
```
- `MANIFEST_JSON` line OPTIONAL: if present, parse JSON for diagnostics; if absent, fine. A non-empty line before BASE64URL that matches no keyword ⇒ `PatchMalformedError` (commentary inside block).
- KEEP verbatim: one-BEGIN/one-END counting incl. `begin==1,end==0 ⇒ ResponseTruncatedError` and `begin==0,end==0 ⇒ return None` (`patch.py:429-436`); decimal/hex64 validation of the two values; size caps before decode (`469-476`); decode + `len==byte_count` + `sha256==digest` (`480-490`); manifest-line byte cap (`456-459`); MANIFEST_JSON-must-be-JSON-object only when present.
- **DELETE** `patch.py:498-501` (outer-manifest `zip_byte_count`/`zip_sha256` equality — redundant with the dedicated lines + decoded-bytes sha) and the `expected_fenced_manifest` pop/threading (`503-504`, the kwarg at `247`, and the embedded-vs-fenced cross-check at `624-625`). The fenced MANIFEST_JSON becomes advisory.

## CHANGE 2 — manifest-optional apply (`src/ask_chatgpt/patch.py`, `_validate_open_zip` ~579-664 + helpers)
Make embedded `manifest.json` OPTIONAL:
- **If `manifest.json` present in the zip:** run the EXISTING strict pipeline UNCHANGED — `_validate_manifest_schema` (717-791), `payload_paths == changed_paths` cross-check (627-637), per-file declared size/sha verification, `status:"deleted"` deletions. (Keeps maximal strictness + deletions whenever a manifest exists — mock/download paths.)
- **If `manifest.json` ABSENT:** new `_reconstruct_entries_from_zip` — for every non-dir member: run `_validate_zip_info_basic` (683-698, symlink/special/encrypted/oversize reject) AND `_validate_patch_rel_path` (794-799 → `validate_posix_relative_path` in `bundle.py:413-452`) on the RAW member name (reject absolute/`..`/`\`/drive/reserved); read bytes via `_read_zip_payload` (812-820, enforces per-file + expanded caps + CRC); build `_PatchFile(path, status="changed", operation="modified", size=len(data), sha256=sha256(data), data=data)`. NEVER `extractall`. Enforce file-count cap. Deletions unsupported on this path (acceptable for UC2 = modified+added). If reconstruction yields ZERO entries (no manifest, no members) ⇒ `PatchMalformedError` (fail closed; no silent no-op).
- Trust anchor: the whole-zip `ZIP_SHA256` over decoded bytes (verified in CHANGE 1) pins the member list+bytes before any are trusted. Downstream (`_resolve_target_plan` 859-914 realpath/no-follow containment, `_apply_transaction`) is UNTOUCHED — same `tuple[_PatchFile,…]` shape. Validate-before-mutate ordering is already correct: first disk write is staging in `_apply_transaction`, after all checks.

## CHANGE 3 — prompt + catalogue README (`src/ask_chatgpt/bundle.py`)
Rewrite `_PROMPT_INSTRUCTIONS_TEMPLATE` (~193-214) and the catalogue fenced section (~168-191) to request the CANONICAL format:
- Drop the download-channel paragraph (no Playwright Download event fires on the real site — M-006/T4c; leading with it invites the `PATCH_BUNDLE_DOWNLOAD_READY` dead-end T3 hit). The fenced block IS the real channel.
- Instruct: build a zip of ONLY changed/added files at repo-root-relative forward-slash paths; no unchanged files; no `ASK_CHATGPT_BUNDLE_README.md`; no absolute/`..`/backslash/drive.
- Emit exactly the 5-line block; **single space after each KEY, no colon**; BASE64URL payload **on the same line, one unbroken token**, unpadded base64url `A-Za-z0-9-_` only (no `+`/`/`/`=`); no triple backticks (BEGIN/END are the fence); no commentary inside the block; exactly one block. `ZIP_SHA256`/`ZIP_BYTE_COUNT` describe the exact encoded bytes.
- State: **no `manifest.json` required for added/modified files** (tool reconstructs per-file metadata from zip entries after verifying `ZIP_SHA256`); to DELETE files, additionally include a top-level `manifest.json` with `"status":"deleted"` entries.
- Include a worked example using the literal M-006 values (144 / `3dce3bc5…` / a real base64url prefix) — strongest few-shot anchor.
- Surface the three author-facing caps (zip < 25 MiB, each file < 5 MiB, ≤ 1000 files = `PATCH_BUNDLE_MAX_*`, patch.py:41-45). Do NOT mention derived caps (`_MAX_BASE64URL_CHARS`/`_MAX_EXPANDED_BYTES`). Keep `NO_CHANGES_NEEDED` path. Keep `docs/bundle-protocol.md` §7 cap table authoritative; update its protocol/format prose to the canonical format.

## CHANGE 4 — mock fixture (`tests/fixtures/mock_chatgpt/server.py`, `build_mock_fenced_patch_bundle` ~124-161)
- Default/`ok` fenced path emits the CANONICAL form: space-separated keys, BASE64URL inline, **no fenced MANIFEST_JSON line, and a manifest-LESS zip** (`build_mock_patch_zip(..., embed_manifest=False)`) — so the mock exercises the reconstruction path and faithfully mirrors real GPT. (Add the `embed_manifest` flag; default True elsewhere.)
- RESOLVED CONFLICT (lens A wanted mock to keep an embedded manifest; lens B/C wanted manifest-less): the canonical/`ok` path is **manifest-LESS**; KEEP manifest-bearing variants for the strict-schema + deletion + `changed_and_unchanged` tests. Both code paths stay covered.
- Map adversarial modes onto the new shape: `bad_hash` ⇒ wrong `ZIP_SHA256` ⇒ `BundleIntegrityError`; `missing_end` ⇒ omit `END_PATCH_BUNDLE` ⇒ `ResponseTruncatedError`; `oversized` ⇒ unchanged intent; `changed_and_unchanged` ⇒ keep embedded manifest (`embed_manifest=True`).

## CHANGE 5 — RED-first tests (deduped union; `tests/test_patch.py` unless noted)
Write these FIRST, watch them fail against current code, THEN implement CHANGES 1-4, watch them pass.
Pin a module constant `_REAL_M006_BUNDLE` = the byte-exact block above. Import `_parse_fenced_patch_bundle`, `PatchBundleCaps`.
- **Parser (grammar):** `test_parse_real_m006_space_keys_inline_base64_decodes` (byte_count 144, sha matches, decodes); `…_softwrapped_payload_is_whitespace_tolerant` (newline+space mid-payload still decodes); `…_truncated_missing_end_raises_truncated`; `…_bad_sha_raises_integrity`; `…_bad_byte_count_raises_integrity`; `…_bad_alphabet_raises_malformed` (`+` injected); `test_parse_colon_form_still_supported_backward_compat`.
- **Apply (reconstruction + security, manifest-less path):** add helper `_build_bare_patch_zip(members, entry_file_types=None)` (no manifest). `test_bare_zip_without_manifest_reconstructs_and_applies_modified_and_added`; `test_bare_zip_real_m006_payload_roundtrips` (decode the literal 144-byte payload, seed `example.txt`=`favorite_color = "red"\n`, apply, assert `…"blue"\n`); security REJECT-before-write (snapshot tree unchanged): `…member_parent_traversal_rejected` (`../escape.txt`), `…member_absolute_path_rejected`, `…member_symlink_entry_rejected` (S_IFLNK), `…symlink_parent_escape_rejected` (pre-created `link→outside`, member `link/evil.txt`), `…reserved_member_rejected` (`ASK_CHATGPT_BUNDLE_README.md` / `.ask-chatgpt-tmp/x`), `…encrypted_member_rejected`, `…member_over_file_cap_rejected`, `…empty_no_manifest_no_members_fails_closed`, `…bare_zip_dry_run_writes_nothing`.
- **Strict path regression (manifest present stays strict):** `test_manifest_present_still_enforces_declared_sha_mismatch` (wrong declared sha ⇒ `BundleIntegrityError`); `test_manifest_present_still_supports_deletions`.
- **End-to-end through mock:** `test_fenced_real_bare_format_roundtrips_via_reconstruction` (drive `_retrieve_scripted(..., fenced_mode=<canonical>)`, assert `bundle.source == "fenced"`, decoded zip reconstructs+applies).
- **Prompt:** update any existing assertion that pins the OLD prompt/format wording (search `tests/test_bundle_out.py`, `test_cli.py`, `docs/bundle-protocol.md`) to the canonical format; add a test asserting the prompt contains the canonical 5-line shape, "no colon", "same line", "no manifest required for added/modified".

## Execution order for the editor (RED-first)
1. Tests (CHANGE 5) — confirm RED. 2. Parser (CHANGE 1) + manifest-optional apply (CHANGE 2). 3. Prompt/README (CHANGE 3). 4. Mock fixture (CHANGE 4). 5. Full `uv run pytest` green (≥169 + the new tests). Update `docs/bundle-protocol.md` format prose. Keep the colon-form back-compat tests green throughout.
