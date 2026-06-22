# M10-T2 — Implement the light-page read fix (single editor, TDD, OFFLINE)

**FIRST read, in full, in this order — they are your complete instructions and inherited context:**
1. `team/contracts/M10-common.md` (shared context, ground truth, safety).
2. `team/evidence/handoffs/M10-T1-L1-readpath.md` (blast-radius map + exact touch list).
3. `team/evidence/handoffs/M10-T1-L2-authharvest.md` (the auth-harvest crux + minimal harvest change).
4. `team/evidence/handoffs/M10-T1-L3-fixdesign.md` (the design blueprint + falsifiable tests).
5. `issues/2026-06-22-read-ops-render-full-conversation-page.md` (the bug).

You are the SINGLE editing worker for this fix. Implement with **strict TDD**
(write a failing test, make it pass, refactor). OFFLINE only — no browser, no real
site. The diagnosis is already verified; build the fix the handoffs describe.

## The verified diagnosis (do not re-litigate; build on it)
- `scrape` (`session.py:512`) is the ONLY always-heavy READ: `tab_pool.acquire`
  (`session.py:521`) → `goto(https://chatgpt.com/c/<id>)` (`channels/cdp.py:650`)
  renders the whole SPA DOM, only to make a backend-API fetch. `history`/`fetch`/
  `status` use no tab; `ask`/`loop` are sends that MUST keep `/c/<id>`.
- The naive light-page fix breaks `acquire_backend_headers` (`capture.py:140`),
  which passively waits for the page's own `GET /backend-api/conversation/<id>`
  (exact matcher `capture.py:144-146`). A light root page never issues it →
  `BackendAuthUnavailableError` (the M7b gap-2 failure).
- `for_single_fetch()` (`capture.py:62-69`) passes headers VERBATIM; nothing
  recomputes `x-openai-target-path`/`-route` for the fetched URL.
- `fetch('/backend-api/conversation/<id>')` from `https://chatgpt.com/` IS
  same-origin and works: `_absolute_fetch_url` resolves the leading `/` against
  `tab.url` (`channels/cdp.py:327-336`). So the FETCH is light-page-ready; only the
  HARVEST must change.

## What to build (default behavior MUST stay unchanged; modes opt-in)
1. **Light-tab acquire.** Add `TabPool.acquire(ref, *, render: bool = True)`
   (`session.py:82`). `render=True` = today's behavior (open `conversation_url(ref)`).
   `render=False` = open a constant light page `https://chatgpt.com/`. **Fix the
   pool keying:** entries are cached by `entry.url` only (`session.py:85-90,96`) —
   key by `(mode, url)` (store the key on `_ManagedTab`) so a light tab and a heavy
   tab never collide or mis-reuse. One shared light tab may serve reads for ANY
   conversation in a Session.
2. **scrape → light + ambient harvest.** In `Session.scrape` ONLY
   (`session.py:521`), acquire with `render=False` and run capture in an
   "ambient/light" header mode. Leave `ask` (`:366`) and `loop` (`:579`) untouched.
3. **Generic harvest mode.** Give `acquire_backend_headers` a `mode`:
   - `conversation` (DEFAULT — current exact `/backend-api/conversation/<id>`
     matcher; preserves send/draft/completion/M7b behavior unchanged).
   - `ambient_backend` — match ANY same-origin `GET` whose path starts
     `/backend-api/` AND that carries ALL `REQUIRED_CAPTURE_HEADERS`. It MUST be
     header-aware: per L2, the current wait layer can return the first
     header-DEFICIENT matching request (`channels/cdp.py:774-793`) — your ambient
     matcher/wait must SKIP deficient matches and keep scanning until one carries
     all 8 (or timeout → `BackendAuthUnavailableError`, fail-closed).
4. **Retarget routing headers for the actual fetch.** Before the conversation
   fetch, set `x-openai-target-path` in the outgoing header dict to the path being
   fetched (`/backend-api/conversation/<id>`). For `x-openai-target-route`: keep
   the harvested value VERBATIM for now, but isolate this in a clearly-named,
   easily-overridable seam (e.g. a `retarget_headers(headers, fetch_path)` helper
   with a TODO noting the route-template rule is real-leg-gated, M10-T4). Do NOT
   guess a route template offline.
5. **completion.py** keeps the DEFAULT (`conversation`) harvest. If you change
   `for_single_fetch`/`acquire_backend_headers` signatures, update call sites
   mechanically with NO behavior change to the send/completion path.

## Falsifiable tests (mock tier — must FAIL before your change, PASS after)
Use the mock channel (`channels/mock.py`) + existing tests in `tests/`. At minimum:
- `scrape` opens `https://chatgpt.com/` and NEVER `/c/<id>`; capture still succeeds
  when the mock page's ONLY observed request is a generic `/backend-api/*` (e.g.
  `/backend-api/accounts/check`) — proving ambient harvest works without the
  conversation GET. (Before the fix this fails: scrape opens `/c/<id>` and the
  exact matcher rejects the generic request.)
- Pool keys don't collide: acquiring `render=False` then `render=True` for the same
  ref yields two distinct managed entries (light root vs `/c/<id>`). A mutation
  back to URL-only keying must break a test.
- Ambient harvest SKIPS a header-deficient first `/backend-api/*` request and picks
  a later all-headers one.
- `x-openai-target-path` is retargeted to the fetched conversation path (a mutation
  that passes the harvested value verbatim must fail a test).
- Regression guards: `history` and `fetch` remain tab-free local-store reads;
  `ask`/`loop`/draft capture still use the exact (`conversation`) harvest.
Update existing tests ONLY where they legitimately assert the old open-tab URL — do
NOT weaken backend/fidelity assertions to make things pass (that masks regressions).

## Acceptance / verification
- Run targeted tests first, then full **`uv run pytest`**. Baseline is **268
  passed**; you must end with **≥ 268 + your new tests**, all green. **Re-derive the
  verdict from the inspected pytest summary, NOT the exit code alone.** Paste the
  final summary line into your handoff.
- If you run ad-hoc Python, first read
  `~/Documents/vaults/agent-vault/agent-python/README` and use that venv. (You
  likely only need `uv run pytest`, which uses the project `.venv`.)

## Safety / scope (NON-NEGOTIABLE)
- Work on a NEW feature branch off `main`: `git switch -c fix/m10-light-read-scrape`
  (use `git switch`, not `checkout`). Commit ONLY your `src/` + `tests/` changes and
  your handoff — stage precisely (`git add src tests team/evidence/handoffs/M10-T2-implement.md`),
  NEVER `git add -A`. The working tree has unrelated dirty/untracked files
  (`issues/…`, `human/`, `controller.mjs`) — **do not stage, modify, or commit
  them.**
- Do NOT push, do NOT merge to main, do NOT move/commit the `stable` ref, do NOT run
  `uv tool install/upgrade/reinstall`. All local only.
- OFFLINE: no browser, no chatgpt.com/openai network, no `ask`/`scrape`/`history`/
  `export` real runs. Mock tests only.
- Do NOT also fix the CLI tab-leak or rate-limit issues — they are SEPARATE
  (orthogonal per L3). Stay scoped to the light-read fix.
- Never print/log auth tokens, OAI header VALUES, cookies, or conversation content.
- Keep it simple (Occam): no new channel API, no daemon, no DOM scraping, no
  per-conversation light tabs. Minimal modal change.

## Deliverable + handoff
Commit the change set to `fix/m10-light-read-scrape`. Write your handoff to
**`team/evidence/handoffs/M10-T2-implement.md`** per the handoff protocol in the
common file: STATUS token; the final `uv run pytest` summary line; exact files+
functions changed with line refs; the new test names and what each falsifies; the
commit hash(es); how `x-openai-target-route` is handled + where the seam is; and any
residual risk for the T3 verifiers and the T4 real leg.
