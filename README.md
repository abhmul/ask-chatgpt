# ask-chatgpt — programmatic interaction with ChatGPT.com

A focused tool that exposes the operator's ChatGPT.com (browser UI) as a callable function. Successor to the archived `control-plane` system (see `orchestration/handoffs/SEED-from-control-plane.md`); this repo deliberately starts smaller and tool-shaped.

## Specification (operator, 2026-06-11)

Three use cases define done:

1. **`ask_chatgpt(prompt, session_identifier, model_settings...) -> text`** — expose the chatgpt.com interaction as a function. `session_identifier` names a persistent chat session (continuity across calls: the same identifier returns to the same conversation). `model_settings` selects model/options where the UI allows. Returns the assistant's response text.
2. **Basic local-filesystem interaction for `ask_chatgpt`** — read-write support is sufficient via a bundle workflow:
   - the caller passes a list of relevant files and/or directories;
   - the tool zips them into a bundle that includes a README / informational catalogue file for GPT (what's inside, how to respond);
   - when GPT needs to make edits, it is asked to return a **patch bundle** — a bundle containing only the files that changed — which the tool retrieves and can apply locally.
3. **CLI entry point** — `ask_chatgpt` callable from the command line (e.g. an `ask-chatgpt` CLI wrapping the function: prompt, session, file args, output to stdout/file).

## Acceptance shape (binding intent; the team refines into per-mission criteria)

- Each use case has an automated end-to-end acceptance against a **local mock ChatGPT** (loopback fixture; the DEFAULT test suite never contacts chatgpt.com/openai), plus a **real-site half** proving it against chatgpt.com on the operator's account. Since 2026-06-12 (operator consent; `docs/DECISIONS.md` D-002) the real-site half may be agent-driven via an opt-in `real_site` test tier — marker + `ASK_CHATGPT_REAL=1` double-gated, hard message budget, headed, audited; the manual runbooks remain the operator-run alternative.
- Round-trip file test: bundle out → (mock) GPT edits → patch bundle back → applied locally → diff matches expectation.
- Honest failure modes: login required, session not found, upload/download unsupported, response truncated — each named actionably.

## Design constraints & posture

- The predecessor's **Level B rule (seed prompts only, never DOM extraction)** conflicts with `-> text` and patch-bundle retrieval. Resolving this is **design decision #1** — made deliberately, recorded, with the archive's reasoning read first (`SEED-from-control-plane.md` §delta).
- Operator owns the ChatGPT account, browser profile, credentials, and quota. The tool never touches credentials (the profile path is opaque config; login is never automated); real-site automation runs only with operator consent (granted 2026-06-12 within D-002 bounds); the default test tier uses local fakes.
- Library-first: the function is the product; the CLI wraps it. No daemons/registries/multi-project frameworks unless a use case forces one.
- Python, `uv`-managed project in this repo; zero-dependency bias beyond what the browser layer needs.

## Archive (read-only)

The full predecessor system, its verification record, mission history, and real-ChatGPT runbooks: `/home/abhmul/Documents/weak-simplex-conjecture/` (`control-plane/` + `orchestration/`). Useful for how problems were solved; not a template to re-import.
