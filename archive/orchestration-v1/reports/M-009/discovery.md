# M-009 — Discovery (ground truth before driving)

Manager: headless Opus. Started 2026-06-13. CDP preflight **PASS** (`curl http://127.0.0.1:9222/json/version` → Chrome/149.0.7827.53, attach-only; never launched).

Charter/constraints honored: CDP attach only, no stealth, login never automated, own tabs only (`close()`=detach), human-paced, no message cap, per-message audit log, redact `/c/<id>`, default tier mock-only, never `git push`. Single pi editor for package-source edits; manager authors probe scripts + reports.

## Production path (verified by reading source)

UC1 (`ask_chatgpt(prompt, channel="cdp") -> str`): `open_or_create_conversation(None)` → `select_model(None)` no-op → `send_prompt` → `wait_for_completion` → `read_response`. (api.py:51-77)

UC2 (`files=`/`dirs=` → `AskChatGPTResult`): `build_bundle` → `generate_prompt_instructions` → open → `select_model` → `upload_bundle` → `send_prompt` → `wait_for_completion` → `read_response` → **`retrieve_patch_bundle`** → returns `patch_bundle`. (api.py:96-143) Caller then `apply_patch(bundle, root, dry_run=...)`.

## T1 — Real UC2: BLOCKER discovered (mission spec-gap)

The mission assumes "populate `real.json:download_artifact` and the production path works." **This is false.** Evidence:

- **Real download affordance** (M-008b `T4-download-capture.json`): bare `<button>Download the patch bundle</button>` inside the latest assistant turn. **No** `href`, `data-source-turn-id`, `data-filename`, `data-byte-count`, or `data-sha256`. Bytes were capturable (146-byte valid zip, `example.txt`) via the M-008b **bespoke** probe (plain click + `expect_download`).
- **Production `_scan_download_artifacts`** (patch.py:301-359) REQUIRES, per matched element: `data-source-turn-id` (==latest turn id) → else `PatchMalformedError`; `data-byte-count` (decimal) + `data-sha256` (hex64) → else `PatchMalformedError`. (patch.py:328-342)
- **Production `_validate_zip_bytes`** (patch.py:585-606) requires `expected_byte_count` + `expected_sha256` and raises `BundleIntegrityError` on mismatch — i.e. the artifact must self-declare integrity.
- **The mock fixture** (`tests/fixtures/mock_chatgpt/server.py:973-976`) emits an `<a … data-byte-count data-sha256 data-source-turn-id download>` — the production scan is shaped to the **mock's** self-describing artifact, which the **real site never emits**.
- **Prompt template** (bundle.py:138,171,195) instructs ChatGPT to "create exactly one actual downloadable `.zip` … do not represent the patch as inline text." So the real channel yields a **download button**, not a fenced base64 block; the fenced fallback (`BEGIN_PATCH_BUNDLE`) is actively discouraged and won't normally be present.

**Consequence:** populating `download_artifact` with `button:has-text("Download the patch bundle")` makes the production path raise `PatchMalformedError("missing data-source-turn-id")` — it cannot capture the real bundle. Closing real UC2 apply+diff requires a minimal **opaque-real download mode**: when the matched download element has NONE of the integrity metadata (real site), click → capture bytes → validate the zip **structurally** (`_validate_open_zip`, self-consistent sha/byte-count) → apply. Mock path (full metadata) stays strict & unchanged; mixed/partial metadata still = malformed. RED-first, single pi editor.

Plan: (1) empirically confirm the production path fails as predicted (probe w/ temp maps_dir, no package edit); (2) if confirmed, pi implements opaque-real mode RED-first; (3) pi populates real.json; (4) re-probe production path → capture → apply+diff → content check (favorite_color red→blue, siblings unchanged) on REAL bytes; (5) honest fail-closed if the real button is no longer reproducible.

## T2 — Short-response completion edge

Driver real/cdp completion (driver.py:343-410) returns only when `streaming_seen AND not streaming_visible AND completion_visible AND stop-absent ≥3s AND text-stable ≥3s`. `streaming_seen` flips True only if a 0.1s poll catches the stop-button. Theoretical edge: a reply that streams+finishes inside one poll window → `streaming_seen` stays False → completion branch unreachable → `ResponseTruncatedError` at deadline (line 410) = spurious truncation.

**Empirical (M-008b `T2-completion-observations.json`):** for all 4 prompts incl. one-word "PING", `stop_count=1` from t≈0.04s through t≈7s, `all_wait_returned: true`, `any_false_truncation: false`. The stop button stays up ~7s for the whole turn lifecycle → edge did NOT bite. Must re-probe live via PRODUCTION `ask_chatgpt()->text` with short prompts; fix RED-first ONLY if it bites (candidate fix: add never-saw-streaming completion path gated on completion_marker + stop-absent ≥3s + text-stable ≥3s; keep `_MicroPauseCompletionState` + `_PrematureGlobalMarkerState` tests passing + a new short-response unit test; keep all 209 mock tests green).

## T3 — Real model-selection

`select_model` (driver.py:226-259) requires `model_menu` present, iterates `model_option` matching requested by `value`/`inner_text`; checks `model_option_disabled`; clicks. `real.json` has `model_menu`/`model_option`/`model_option_disabled` all EMPTY → fail-closed today (`_require_present("model_menu")` raises `SelectorUnavailableError`). Need CDP discovery of the real picker (trigger + per-model entries), populate real.json, prove selection via UI STATE (header/trigger reflects choice), fail-closed (`ModelUnavailableError`) if requested model absent. Document operator-plan-dependent model availability.

## Named errors (errors.py, for T4)

`AskChatGPTError` (base), `CDPUnreachableError`, `ChallengePresentError`, `LoginRequiredError`, `ProfileLockedError`, `SessionNotFoundError`, `ModelUnavailableError`, `ResponseTruncatedError`, `RateLimitedError`, `SelectorUnavailableError`, `UploadUnsupportedError`, `DownloadUnsupportedError`, `PatchBundleValidationError`(+`PatchMalformedError`/`BundleIntegrityError`/`OversizedPayloadError`/`PathEscapeError`), `PatchApplyError`.
