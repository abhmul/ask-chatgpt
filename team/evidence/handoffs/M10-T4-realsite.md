STATUS: PARTIAL

## Run result
- Preconditions: CDP `/json/version` returned a Browser/version JSON; branch `fix/m10-light-read-scrape`; `uv run ask-chatgpt --version` = `0.2.0`; `stable` = `bbbe027`.
- Single scrape run: `uv run ask-chatgpt scrape <target> --data-dir cache >/dev/null 2>/tmp/m10-t4-stderr.log`; exit code `0`; elapsed `5s`; retry count `0`.
- CRASH: no. Evidence: exit 0, `transcript.jsonl` present, `raw-mapping.json` present, stderr crash-pattern count 0, login/Cloudflare pattern count 0.
- Renderer-crash verdict: FIXED for this conversation. Handoff status is PARTIAL only because the contract-expected `transcript.md` cache artifact was absent.
- RSS: unavailable; the one permitted scrape was not run under an RSS-measuring wrapper. Elapsed cost signal: `5s`.

## Cache artifact check
- `transcript.jsonl`: true; file bytes `5540094`.
- `transcript.md`: false; file bytes `0`. This is the only contract mismatch observed; I did not create a markdown export or run an extra scrape.
- `raw-mapping.json`: true; file bytes `5719155`.

## Fidelity counts from cache, no content printed
- JSONL records: `44`; deduped by `message_id` keep-last turn count: `44`.
- Deduped canonical content size: `114502` chars; `116321` UTF-8 bytes.
- Mapping node count: `1915`.
- Capture source: `backend_api` count `44`; all capture sources are `backend_api`: true.
- Fidelity marker: `canonical` count `44`; all fidelity markers are `canonical`: true.
- Math counts over deduped canonical text: `\\widehat` = `25`; `\\ne` command = `39`; `\\neq` command = `0`; `\\frac` = `355`; flattened-frac signature `\\frac\s*/` = `0`; literal U+2260 `≠` = `0`.

## U1/U2 interpretation
- U1: PASS. Successful scrape with no `BackendAuthUnavailableError` means ambient root-page header harvest supplied the required header names; no header values were printed.
- U2: PASS. Successful backend conversation fetch means the verbatim `x-openai-target-route` was accepted; no fetch/HTTP/route error class observed.
- Exact error class: none.

## Safety attestation
- ZERO sends: only `scrape` was run; no `ask`, `loop`, `create`, or send path.
- Own-tab-only: I never inspected, listed, closed, or touched operator tabs; I never quit the browser; I did not call `/json/list` or any `/json/*` endpoint except `/json/version`.
- Leak discipline: scrape stdout went to `/dev/null`; handoff contains counts/booleans only, no conversation content, auth tokens, cookies, OAI header values, file ids, or attachment bytes.
- Tooling: used only `uv run ask-chatgpt`; never used bare installed `ask-chatgpt`; no `uv tool install/upgrade/reinstall`.
- Git safety: `stable` unchanged at `bbbe027`; cache not staged or committed; post-handoff `git diff --cached --name-only` count `0`; post-handoff staged cache/source count `0`; cache absent from `git status --short`.
