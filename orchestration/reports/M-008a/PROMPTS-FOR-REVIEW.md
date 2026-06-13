# M-008a — PROMPTS FOR REVIEW (adversarial prompt-quality + falsifiability deliverable)

**Purpose.** Every GPT-facing prompt produced by M-008a (the mock/build half), pasted **verbatim from ground truth** (the committed source — not a worker's paraphrase), each with an adversarial annotation: how a chatbot could misread it, what outcome the wording predetermines, and why the corresponding test *can fail*. This document is consumed by (a) the T5 prompt-quality + falsifiability lens (Lens B) and (b) the team-lead pre-real spot check. Operator WAIVED manual sign-off 2026-06-13 — adversarial verifiers + a team-lead spot check are the gate.

**Root cause this mission addresses (operator, 2026-06-13).** The prior prompts were "horrible for testing": (1) the bundle prompt told ChatGPT to emit a fenced **BASE64URL text** blob, so GPT returned text and no downloadable file affordance ever appeared — the "downloads don't work" conclusion was therefore **circular**; (2) the continuity recall prompt **contained the answer** (`"…Reply exactly: GAP15_RECALL N5C85C"`), so a zero-history conversation would reply identically — proving nothing.

**Design rule applied:** *want a file → ask for a file*; *test recall → never include the thing being recalled*. **base64 = PARSER-ONLY:** the model-facing prompt contains **zero** base64 wording; the parser keeps base64 tolerance as a *silent* code-side fallback for the case where a model spontaneously emits base64 (never surfaced as an instruction).

**Sources (all committed, verified by `git`):**
- Bundle prompt + catalogue: `src/ask_chatgpt/bundle.py` (`_PROMPT_INSTRUCTIONS_TEMPLATE`, `_CATALOGUE_TEMPLATE`) — commit `c71c96a`.
- Continuity + truncation prompts: `tests/test_continuity_mock.py` — commit `484cacf`.

**Mandatory operator-required checks (re-derived from ground truth by the manager):**
| Check | Method | Result |
|---|---|---|
| Zero base64/marker wording in the bundle prompt (and catalogue) | `grep -niE 'base64\|begin_patch_bundle\|end_patch_bundle\|fenced' src/ask_chatgpt/bundle.py` | **NONE** (zero matches) |
| Continuity recall prompt does NOT contain the nonce (or its prefix/suffix) | read prompt + `_assert_recall_prompt_does_not_leak_nonce` (asserts nonce, random suffix, AND `ASKCG-NONCE-` prefix all absent) | **Confirmed absent** |
| Each real-site test can fail | continuity has a fresh-conversation CONTROL; truncation has an all-lines-in-order + terminal-sentinel verifier | **Both can fail** |

---

## 1. Bundle patch-return prompt — `_PROMPT_INSTRUCTIONS_TEMPLATE` (sent with the uploaded zip)

> Verbatim (`{{BUNDLE_FILENAME}}`, `{{USER_TASK}}` are substituted at send time):

```text
I uploaded a zip project-context bundle named `{{BUNDLE_FILENAME}}`. First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip. Then complete this task:

{{USER_TASK}}

If no file edits are needed, reply exactly `NO_CHANGES_NEEDED` and nothing else. Do not create a downloadable file in that case.

If file edits are needed, create exactly one actual downloadable `.zip` file and provide the download link to that file in your reply. Use your file/output tools to create the `.zip`; do not represent the patch as inline text. The `.zip` file is the patch bundle.

The `.zip` must contain only changed or added file payloads at repo-root-relative forward-slash paths, with no wrapping directory. Do not return the whole tree. Do not include unchanged files, `ASK_CHATGPT_BUNDLE_README.md`, absolute paths, `..`, backslashes, drive letters, symlinks, or files outside the project root.

A top-level `manifest.json` is optional for added or modified files; the tool reconstructs per-file metadata from verified zip entries after checking the whole-zip SHA-256. If you must delete files, additionally include a top-level `manifest.json` with deletion entries and omit payloads for deleted paths.

Deletion manifest schema, only when needed:
{ "version": 1, "files": [ … {"path":…, "status":"deleted","operation":"deleted","size":0,"sha256":null} … ], "total_byte_count": … }

For added and modified files, include the new file bytes in the zip at exactly `path`. For deleted files, set `status` and `operation` to `deleted`, set `size` to `0`, set `sha256` to `null`, and omit the deleted file payload from the zip. Do not use `status: "unchanged"` in real patch bundles.

Patch caps: zip < 25 MiB, each file < 5 MiB, and at most 1000 files.

Return exactly one downloadable `.zip` file per response.
```
(The in-zip `_CATALOGUE_TEMPLATE` "## If edits are needed: create one downloadable patch `.zip`…" section repeats the same instruction with the same wording; verbatim in `bundle.py:136-162`.)

**Adversarial annotation**
- **What the old wording predetermined (the bug):** "return exactly one fenced patch bundle … `BASE64URL <…>`" *forced* a text reply. The model complied with text, so no file/download affordance was ever produced. The new wording deletes that escape hatch entirely: "create exactly one actual downloadable `.zip` file and provide the download link … **do not represent the patch as inline text**."
- **What the new wording predetermines:** exactly two legitimate outcomes — the literal `NO_CHANGES_NEEDED` sentinel, or one downloadable `.zip` artifact with a download link. There is no third "paste it in chat" path offered to the model.
- **Misread risks (honest):**
  1. **Tool-less model.** A model with no file-creation capability cannot produce a downloadable file; it may emit prose or inline content and fail. *This is acceptable and intended:* the prompt asks for the best path; the parser's silent base64 tolerance is a safety net only if the model happens to emit base64. **M-008b implication:** the real run must use a ChatGPT surface that *has* file-output tools; if it cannot produce a file, the honest failure is `DownloadUnsupportedError`, not a clipped base64 blob. This is the correct, non-circular behavior.
  2. **Wrapping directory / multiple archives / unchanged files.** Explicitly forbidden ("no wrapping directory", "Do not include unchanged files", "Do not return the whole tree", "Return exactly one downloadable `.zip` file per response").
  3. **Manifest confusion.** The prompt states `manifest.json` is optional for add/modify and required only for deletions, matching the parser (manifest-optional reconstruction). Low risk.
- **Why the test can fail (falsifiability):** the mock UC2 round-trip exercises the **download** path (`source == "download"`) end-to-end (upload → affordance → validate → apply → diff-match); if the affordance, validation, zip-slip, or diff break, it fails. A dedicated guard test (`test_model_facing_bundle_outputs_request_downloadable_zip_without_parser_fallback_terms`) **fails** if any of `base64/base64url/begin_patch_bundle/end_patch_bundle/fenced/marker block/5-line block/paste` reappears in either generated model-facing output, or if the downloadable-zip ask disappears. Confirmed it fails against the *old* templates.
- **Verdict:** PASS. Zero base64 wording; asks for a file; payload rules and caps preserved; failure modes are honest, not circular.

---

## 2. Continuity — Turn-1 plant prompt

> Verbatim (`{nonce}` = freshly generated `ASKCG-NONCE-<32 hex>` per run, ≥ 32 chars):

```text
Remember this token for later: {nonce}. Reply with ACK only.
```

**Adversarial annotation**
- **Predetermined outcome:** an `ACK` reply; the nonce is planted but turn 1's *reply* is not asserted on for recall (so even if the model echoes the nonce here, the continuity proof is unaffected — recall is judged in turn 2).
- **Misread risks:** the model could echo the nonce instead of `ACK` (harmless), or ignore the "remember" instruction (then turn-2 recall legitimately fails — a true-negative, not a false pass).
- **Critical property:** the nonce appears in **turn 1 only**. It is full-length and high-entropy (`secrets.token_hex(16)`), so it cannot be guessed and (being long) also exercises the read path against truncation.
- **Verdict:** PASS.

## 3. Continuity — Turn-2 recall prompt (and the CONTROL, byte-identical)

> Verbatim (used for both the same-session recall AND the fresh-session control):

```text
What was the token I asked you to remember? Reply with only the token.
```

**Adversarial annotation**
- **Fixes the circular flaw:** the prompt contains **no nonce, no nonce prefix, no nonce suffix** (asserted by `_assert_recall_prompt_does_not_leak_nonce`). It does not hand the model the answer; the only way to produce the exact nonce is to have it in conversation memory.
- **Predetermined outcome:** none. The model must recall from prior-turn context or it cannot produce the exact nonce.
- **Misread risks:** the model could reply with prose, hedge, or hallucinate a token-shaped string — but it cannot reproduce the *exact* fresh nonce without genuine history, so a wrong/absent recall is detectable (assert `text.strip() == nonce`).
- **Why the test can fail (the CONTROL is the falsifiability mechanism):** the **identical** prompt is sent to a **fresh** conversation with no turn-1 plant. On the mock this returns `NO_TOKEN_RECALLED` (the opt-in recall mode derives the answer *only* from the current conversation's stored history, which is empty for a fresh conversation), and the test asserts the nonce is absent. The control coexists with the continuity conversation in the same mock server, so its failure also proves recall is **conversation-scoped**, not a global lookup. On real (M-008b), a fresh ChatGPT conversation likewise cannot know the nonce. **A continuity test with no failing control proves nothing; this one has one.**
- **Cross-process:** the same prompts drive two separate CLI subprocesses sharing `ASK_CHATGPT_STATE_DIR`; the JSON registry carries the conversation_ref across processes; the test verifies both prompts landed in the *same* registry conversation, and the different-session control lands in a *distinct* conversation and fails to recall.
- **Verdict:** PASS. Non-circular; nonce absent; control genuinely fails.

---

## 4. Truncation / long-response elicitation prompt

> Verbatim (`{line_count}` = 180, `{token}` = freshly generated per run):

```text
Output exactly {line_count} numbered lines, then exactly one completion marker line. For k=1 through {line_count}, line k must be exactly `LINE-<k> {token}` with <k> replaced by decimal k and no zero padding. After line {line_count}, output exactly `__ELICIT_COMPLETE__` on its own line and nothing after it.
```

**Adversarial annotation**
- **Predetermined outcome:** a deterministic, fully checkable structure — 180 ordered lines `LINE-1 <tok> … LINE-180 <tok>` followed by exactly `__ELICIT_COMPLETE__`. The body is ≥ 4 KB, so it stresses the read/completion path that previously clipped (`…1F3845_`).
- **Misread risks:** the model could miscount, zero-pad indices, omit/relocate the sentinel, or append trailing text. Each of these is *detected* by the verifier (`splitlines() == expected_lines` exact-match in order + `endswith(__ELICIT_COMPLETE__)` + length ≥ 4096), so a malformed or **truncated** response cannot pass.
- **Why the test can fail (falsifiability):** the terminal sentinel + exact ordered line list is the failure detector. A clipped response (the exact M-007 failure mode) is missing late lines and/or the sentinel → assertion fails. This is the end-to-end (`ask_chatgpt()->text`) complement to T1's driver-level reproduction (which failed pre-fix by returning a clipped 5359-char body without its terminal sentinel).
- **M-008b note:** this prompt + the channel-agnostic verifier flip to the real channel without rewriting the assertions; only the channel/fixture changes.
- **Verdict:** PASS.

---

## Summary

| # | Prompt | Zero base64? | Hands the answer? | Has a failing control / failure detector? | Verdict |
|---|---|---|---|---|---|
| 1 | Bundle patch-return | Yes (grep NONE) | n/a | Yes (download round-trip + guard test) | PASS |
| 2 | Continuity turn-1 plant | n/a | No (nonce planted, not recalled here) | n/a | PASS |
| 3 | Continuity turn-2 recall / control | n/a | **No** (nonce/prefix/suffix absent) | **Yes** (fresh-conversation control fails) | PASS |
| 4 | Truncation elicitation | n/a | No | Yes (ordered-lines + terminal sentinel) | PASS |

**Residual real-site consideration for M-008b (not a defect of these prompts):** the bundle prompt presumes the real ChatGPT surface can create a downloadable file; if it cannot, the honest outcome is `DownloadUnsupportedError` (the parser's silent base64 tolerance is a safety net, not a fallback the prompt invites). M-008b must (a) run on a ChatGPT surface with file-output tools and discover/populate the real `download_artifact` selector, and (b) flip the continuity + truncation harnesses to `channel="cdp"` reusing the channel-agnostic helpers.
