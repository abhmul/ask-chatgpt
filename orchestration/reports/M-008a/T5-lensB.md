# M-008a / T5 Lens B — prompt-quality + falsifiability verifier

Scope read cold: `src/ask_chatgpt/bundle.py`, `tests/test_continuity_mock.py`, `tests/fixtures/mock_chatgpt/server.py` recall implementation, `tests/test_bundle_out.py` guard assertions, `tests/test_uc2_roundtrip.py` download round-trip, `orchestration/reports/M-008a/PROMPTS-FOR-REVIEW.md`, and the authoritative pytest report. I did not run the full suite and did not touch `ASK_CHATGPT_REAL` or `127.0.0.1:9222`.

## Check 1 — bundle prompt/catalogue have zero base64/marker wording

Command run from repo root:

```text
$ grep -niE 'base64|begin_patch_bundle|end_patch_bundle|fenced|marker block|5-line block' src/ask_chatgpt/bundle.py || true
```

Output:

```text
```

Result: PASS. The model-facing bundle templates contain no base64, `BEGIN_PATCH_BUNDLE`/`END_PATCH_BUNDLE`, fenced-bundle, marker-block, or 5-line-block wording. The prompt and in-zip catalogue instead ask for exactly one actual downloadable `.zip` file plus a download link, and explicitly say to use file/output tools and not represent the patch as inline text.

## Check 2 — continuity recall prompt does not contain the nonce

Result: PASS. `RECALL_PROMPT` is exactly `What was the token I asked you to remember? Reply with only the token.` The nonce appears only in `_plant_prompt(nonce)`: `Remember this token for later: {nonce}. Reply with ACK only.` `_assert_recall_prompt_does_not_leak_nonce` asserts the recall prompt contains neither the full nonce, nor the nonce suffix, nor the `ASKCG-NONCE-` prefix.

## Check 3 — falsifiability of real-site-shaped tests

Result: PASS. Continuity has a same-session recall and a byte-identical fresh-session control (`control_prompt == recall_prompt`); the mock recall mode scans only the current conversation's prior turns (`conversation.turns[:-1]`) and returns `NO_TOKEN_RECALLED` when the token is absent, so the control genuinely fails to recall rather than reading a global fixture. Same-session recall is asserted as `text.strip() == nonce`, so an approximate, leaked-in-prompt, or hallucinated answer cannot pass. Truncation uses a deterministic prompt for 180 ordered `LINE-k <token>` lines followed by `__ELICIT_COMPLETE__`; the verifier requires UTF-8 length >= 4096, exact `splitlines()` equality to every expected line in order, and terminal sentinel ending, so clipped, miscounted, reordered, or extra-text responses fail.

## Per-prompt adversarial findings

### Bundle prompt and catalogue

Misread risk: a tool-less or file-output-disabled ChatGPT surface may be unable to create an actual downloadable file and may fall back to prose or inline text. That is an honest M-008b environment failure (`DownloadUnsupportedError`/no artifact), not the previous circular test design, because the prompt no longer invites base64 or inline patch text. The deletion-manifest JSON schema and `NO_CHANGES_NEEDED` example are code-block examples, but the surrounding instructions repeatedly forbid inline payload content for edit cases and require exactly one `.zip` artifact. Predetermined outcome: either exact `NO_CHANGES_NEEDED` for no-edit tasks or one downloadable zip artifact for edit tasks. Can fail: yes, if no artifact appears, if multiple/stale/corrupt/truncated artifacts appear, if the zip layout or diff is wrong, or if forbidden fallback wording reappears; `test_model_facing_bundle_outputs_request_downloadable_zip_without_parser_fallback_terms` guards the wording and UC2 exercises `source == "download"` through apply/diff.

### Continuity plant prompt

Misread risk: the model could echo the nonce instead of `ACK`, or fail to remember it. Neither creates a false pass; it either remains in conversation history or causes recall to fail. Predetermined outcome: only an ACK acknowledgement on turn 1, not the recall answer. Can fail: yes, if the conversation state is not preserved or if the model/session does not retain the planted token.

### Continuity recall/control prompt

Misread risk: a model may answer with prose, say it cannot know, or hallucinate a token-shaped string. The exact nonce assertion catches this, and the fresh-control assertion catches prompt leakage or global/session leakage. Predetermined outcome: none; the prompt does not include the answer. Can fail: yes, same-session must return the exact high-entropy nonce, while the byte-identical fresh-session control must not return it. Real-site caveat: account-level memory or browser/session leakage would be detected by the control rather than hidden.

### Truncation elicitation prompt

Misread risk: a model may miscount, zero-pad, omit lines, omit or move the sentinel, append commentary, or include a trailing newline/text after the sentinel. The verifier is deliberately strict, so these are failures rather than false passes. Predetermined outcome: a deterministic long body with every line checkable and a terminal completion marker. Can fail: yes, any clipping or DOM/read truncation drops late lines or the sentinel and fails exact comparison.

## Defects

None found in the GPT-facing prompts for this lens. Residual M-008b caveat: the bundle test assumes a real ChatGPT surface capable of creating downloadable files and a populated artifact selector; if that surface lacks file-output support, the prompt will fail honestly rather than by circular inline/base64 design.

VERDICT: PASS — prompts are non-circular and falsifiable.