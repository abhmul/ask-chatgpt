# M-008a / T5 Lens B — prompt-quality + falsifiability (MANDATORY, operator-required). READ-ONLY.

You are a pi (GPT-5.5) worker acting as an INDEPENDENT non-producer verifier. You inherit NOTHING except this file and what you read. You did NOT write these prompts; review them adversarially and cold — do not rubber-stamp a green suite.

## Rules (MANDATORY)
- Repo root: `/home/abhmul/dev/ask-chatgpt`. `uv run` from root for any python; NEVER bare `python`; NEVER touch `~/.local/share/agent-python/.venv`.
- **READ-ONLY:** no edit/commit/checkout/stash. Do NOT set `ASK_CHATGPT_REAL`; do NOT touch `127.0.0.1:9222`. Do NOT re-run the full suite (read `orchestration/reports/M-008a/authoritative-pytest.txt` if you need the suite result). Targeted greps/reads are fine.

## Why this lens exists (operator mandate, 2026-06-13)
The prior GPT-facing prompts were "horrible for testing": (1) the bundle prompt asked ChatGPT to emit a fenced BASE64URL **text** blob, so GPT returned text and no downloadable file appeared — the "downloads don't work" conclusion was CIRCULAR; (2) the continuity recall prompt CONTAINED the answer, so it proved nothing. A GREEN SUITE IS NOT SUFFICIENT — you must inspect the wording and the falsifiability of each test.

## Your lens — adversarially read EVERY GPT-facing prompt and verify falsifiability. Sources of truth:
- Bundle prompt + catalogue: `src/ask_chatgpt/bundle.py` (`_PROMPT_INSTRUCTIONS_TEMPLATE`, `_CATALOGUE_TEMPLATE`).
- Continuity + truncation prompts: `tests/test_continuity_mock.py` (the `_plant_prompt`, `RECALL_PROMPT`, `_truncation_elicitation_prompt`).
- The manager's review under audit: `orchestration/reports/M-008a/PROMPTS-FOR-REVIEW.md` (verify its claims independently; do not just echo it).

Verify, independently:
1. **Zero base64/marker wording in the bundle prompt** (and catalogue): run `grep -niE 'base64|begin_patch_bundle|end_patch_bundle|fenced|marker block|5-line block' src/ask_chatgpt/bundle.py` yourself. Expect NO matches in the model-facing templates. Confirm the prompt instead asks for one actual downloadable `.zip` file with a download link and explicitly forbids inline text.
2. **Continuity recall prompt does NOT contain the nonce:** read `RECALL_PROMPT` and the plant prompt; confirm the recall/control prompt has no nonce, no `ASKCG-NONCE-` prefix, no hex suffix; confirm the test asserts this (`_assert_recall_prompt_does_not_leak_nonce`).
3. **Each real-site test CAN fail (falsifiability):**
   - Continuity: confirm there is a CONTROL (identical recall prompt sent to a FRESH conversation/session) that must NOT produce the nonce, and that the mock recall is conversation-scoped (so the control genuinely fails — returns `NO_TOKEN_RECALLED`). Confirm a same-session recall returns the EXACT nonce derived from history (not handed to the model).
   - Truncation: confirm the elicitation prompt + verifier require every `LINE-k` in order AND a terminal sentinel, so a clipped/truncated/miscounted response fails.
4. **Adversarial read of each prompt:** for the bundle, continuity (plant/recall/control), and truncation prompts — how could a chatbot misread it? what outcome does the wording predetermine? Is there any residual escape hatch that re-enables the circular failure (e.g., an invitation to return inline/base64 text)? Note any real-site (M-008b) caveats (e.g., the bundle prompt presumes a file-tool-capable surface).

## Deliverable — write `orchestration/reports/M-008a/T5-lensB.md`:
- Per-prompt adversarial findings (misread risk / predetermined outcome / can-it-fail).
- Explicit results for checks 1-3 (with the grep output for check 1).
- Any defects or "none".
- Final line exactly: `VERDICT: PASS` (or `PARTIAL` / `FAIL`) with a one-clause reason.
Do NOT edit anything. Stop when the report is written.
