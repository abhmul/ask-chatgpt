# Capture extracts rendered-DOM `textContent`, not raw markdown/LaTeX — drops `\widehat`/`\ne` accents (silent math corruption)

**Date:** 2026-06-14
**Severity:** High (silent corruption of load-bearing math; two confirmed CORRUPTED cases, not merely ambiguous)

---

## Summary

The tool captures a GPT response by reading the **rendered DOM text** (KaTeX/MathML `textContent`), not the **raw markdown/LaTeX source** that the web-UI "copy" affordance produces. As a result, math glyphs that KaTeX draws as *separate overlay elements with no `textContent`* — accents (`\widehat`, `\hat`, `\bar`, …) and the not-equal relation (`\ne`/`\neq`) — are **dropped entirely** from the capture. 2-D structure (fractions, sub/superscripts) is also flattened onto separate lines.

This was found in a FIDELITY audit comparing a real GPT Pro response captured by the tool (`tool-capture.md`) against the operator's copy-paste of the same response from the web UI (`webui.md`, raw `\frac{}{}`/`\widehat`/`_`/`^` markdown = ground truth). Completeness was confirmed separately; this issue is purely about silent corruption of meaning.

The dropped-accent case is the dangerous one: it does not just make the math *ambiguous*, it can make the capture assert something **definitively different or false**, because `\widehat D` and `D` are distinct objects and the hat is the only thing distinguishing them.

---

## Evidence (concrete side-by-side; ground truth = `webui.md` LaTeX, observed = `tool-capture.md`)

### CORRUPTED #1 — `\widehat` accent dropped (conflates two distinct objects)

The response defines *new scaled blow-up certificates* `\widehat D_i := (d^2)^2 D`, `\widehat D_\ell := m_\ell^3 D`, and `\widehat\Gamma_\ell := m_\ell^2 \Gamma_\ell`, `\widehat S_\ell := m_\ell S_\ell`. These are **deliberately different** from the un-hatted `D`, `\Gamma_\ell`, `S_\ell`.

In the capture the hat is gone — verified mechanically: the entire `tool-capture.md` contains **zero** combining diacritical marks (U+0300–U+036F) and zero precomposed hat/bar glyphs. So every `\widehat X` renders as bare `X`, glyph-identical to the unscaled `X`.

Worst instance — the §6 implication chain. Ground-truth `webui.md`:
```
\widehat\Gamma_\ell:=m_\ell^2\Gamma_\ell>0, \widehat S_\ell:=m_\ell S_\ell>0,
   which implies  D=m_\ell^{-3}\widehat\Gamma_\ell\widehat S_\ell>0.
```
Capture linearizes (zero-width chars removed) to:
```
certify Γ_ℓ := m_ℓ² Γ_ℓ > 0, S_ℓ := m_ℓ S_ℓ > 0, which implies D = m_ℓ^{−3} Γ_ℓ S_ℓ > 0.
```
The definition now reads `Γ_ℓ := m_ℓ² Γ_ℓ` — a **self-referential, false identity** (holds only if `m_ℓ = 1`), and the conclusion `D = m_ℓ^{−3} Γ_ℓ S_ℓ` silently conflates the scaled factors with the unscaled ones. A worker implementing from the capture alone would either be confused by the self-reference or, worse, implement the wrong (un-scaled) product formula.

### CORRUPTED #2 — `\ne` (≠) dropped, flipping a constraint to its negation

The not-equal sign renders to a Unicode Private-Use placeholder (U+E020) with no readable content. Two occurrences, both load-bearing predicates:

Ground truth `webui.md` line 115:
> "the Schur/pivot factorization only needs `(q_p\ne 0)`"

Capture (U+E020 shown as `␦`):
> "the factorization only needs `q_p ␦ = 0`"

If a reader/parser strips or ignores the unknown glyph, this reads `q_p = 0` — the **exact opposite** of the required `q_p ≠ 0`. Same flip for `Z\ne 0` → `Z ␦ = 0` (`webui.md` line 317).

### AMBIGUOUS — fraction flattening (numerator/denominator swapped, no bar)

`\frac{A}{B}` is emitted as a vertical token run with **denominator first, then numerator, with no division bar** (only a U+200B zero-width separator).

`\frac{\Delta_p}{q_p^2}` (`webui.md` line 33) → capture:
```
q
p
2      ← q_p^2  (DENOMINATOR appears first)
Δ
p      ← Δ_p    (numerator second)
```
i.e. the token stream `q p 2 Δ p`, readable as `q_p^2·Δ_p`, `Δ_p·q_p^2`, or even `q_p^{2Δ_p}`.

The large `J_0` fraction is worse — numerator and denominator interleave and the exponents strand on their own lines. Ground truth:
```
J_0 := L - a^3/3 = [3(V+S)V^2 - (1+x)(1+y)S^3] / [3(1+x)(1+y)V^3]
```
Capture:
```
3(1+x)(1+y)V
3                ← the V^3 exponent (denominator), now adjacent to...
3(V+S)V          ← ...the start of the numerator → reads as "V^3·3(V+S)" or "V·33(V+S)"
2
−(1+x)(1+y)S
3
```
Recoverable only by cross-checking the embedded Python (`J0 = (3*(V+S)*V**2 - den*S**3)/(3*den*V**3)`), not from the rendered text alone.

### RECOVERABLE — sub/superscript fragmentation, and (mostly) glyph fidelity

`K_{kk}W_j^2 - 2K_{jk}W_jW_k + K_{jj}W_k^2` flattens to `K kk W j 2 − 2K jk W j W k + K jj W k 2`. Structure survives via context, but `W_j^2` is line-for-line identical to how `W_{j2}` would render. Greek-vs-Latin fidelity is otherwise **good**: `ν`(U+03BD) stays distinct from `v`, `γ` is not collapsed to `y`/"gamma", and `≤ ≥ ≈ ∂ ∑ ∫ × ⋅ ∼ ∈ → ∞ ±` all survive. The only systematic operator casualties are the accents and `\ne` above. (Thin-spaces `\,` collapse harmlessly: `V+i\,dS` → `V+idS`.)

---

## Root cause

The capture path is reading `element.textContent` (or equivalent rendered-DOM text) of the assistant message. KaTeX renders accents (`\widehat`, `\hat`, `\bar`, `\vec`, `\dot`) and some relations (`\ne`) as **stretchy SVG / overlay spans that carry no text node**, and lays out fractions/scripts as absolutely-positioned 2-D boxes. `textContent` therefore (a) silently omits the accent/≠ glyphs and (b) serializes the 2-D layout top-to-bottom, losing numerator/denominator/script grouping.

The web-UI **"copy" button on a response copies the underlying markdown/LaTeX source** (the same content as `webui.md`), which has none of these problems.

---

## Bottom-line risk

For this particular response most damage is *recoverable* by a careful worker cross-checking the embedded mpmath script and repo formulas (the code spells out `Gamma = Delta/q[p]**2`, the `J0` fraction, etc., unambiguously). **But the two CORRUPTED classes are not guarded by the code:**
- the `\widehat` scaled certificates (`\widehat D_i`, `\widehat D_\ell`, `\widehat\Gamma_\ell`, `\widehat S_\ell`) appear **only in prose**, with no code counterpart — a worker building the singular-cap certificate from the capture has no cross-check and would implement the wrong (unscaled) object or trip on the `Γ_ℓ := m_ℓ² Γ_ℓ` self-reference;
- the `\ne 0 → = 0` flip silently inverts a safe-pivot/branch precondition.

Worst realistic failure: a worker implements the negative-axis blow-up certificate using unscaled `Γ_ℓ, S_ℓ` (because the hats are invisible) and/or enforces `q_p = 0` instead of `q_p ≠ 0`, producing an *incorrect* certificate that looks faithful to the captured text. Since these captures are treated as load-bearing math we implement and verify, that is a real correctness hazard.

---

## Suggested fix direction

**Capture the raw markdown/LaTeX source, not rendered-DOM `textContent`.** Concretely, in the response-extraction path, prefer (in order):

1. **The response "copy" affordance / raw message payload.** The web UI's per-message copy button yields the markdown source (matches `webui.md` exactly). If the capture can click that copy control and read the clipboard, or read the same source the button uses, the output becomes unambiguous and matches the web-UI copy byte-for-byte.
2. **The underlying message JSON** (the assistant turn's markdown `content` as delivered over the wire / `__NEXT_DATA__`/streaming payload), if reachable — this is the true source and avoids the DOM entirely.
3. **Fallback only:** if rendered-DOM scraping must remain, at minimum reconstruct math from the KaTeX annotation node `<annotation encoding="application/x-tex">…</annotation>` (KaTeX embeds the original TeX there) rather than from `textContent`, which recovers `\widehat`, `\ne`, and fraction/script structure.

Acceptance check: re-capture this same response and diff against `webui.md` — `\widehat`, `\ne`, and every `\frac{}{}` should round-trip.
