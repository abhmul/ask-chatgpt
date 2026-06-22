# `--out FILE` suppresses stdout: reply goes to file only, not to both

**Date:** 2026-06-14
**Severity:** Low-Medium

---

## Observed behavior

With `--out FILE` set and `--channel cdp`, the reply is written to `FILE` but **stdout is empty**. Lead-verified by two smoke tests:

1. `--model-settings '{"model":"Instant"}'` → `--out` contained `PLUMBING_OK_4` (13 bytes); redirected stdout file was **empty**.
2. `--model-settings '{"model":"Medium"}'` → `--out` contained `Using ad−bc, the determinant is 2⋅3−1⋅1=5. DET=5` (56 bytes); redirected stdout file was **empty**.

Both calls exited 0 and created their session registries correctly. The text was delivered — but only to the `--out` file, not to stdout.

---

## Expected behavior (per docs)

`docs/PARALLEL-GPT-RECIPE.md` describes the default (no `--out`) behavior as:
> "Prints GPT's reply text to stdout."

This implies `--out` adds file output on top of stdout ("also" save). The `--out FILE` CLI help text says "write assistant response text to FILE", which is ambiguous about whether stdout is also written.

`docs/bundle-protocol.md` line 393 says:
> "`--out FILE` | optional path | Writes assistant response text to `FILE` **instead of stdout**."

And line 404:
> "default ask mode writes assistant response text, and only that text, to stdout **unless `--out` is set**"

So `bundle-protocol.md` correctly documents "instead of", but `PARALLEL-GPT-RECIPE.md` creates the impression that stdout is always active. The behaviour itself is consistent with "instead of" — the discrepancy is in `PARALLEL-GPT-RECIPE.md`.

Note: no `GPT-PRO-ACCESS.md` file exists in this repo; `PARALLEL-GPT-RECIPE.md` (`docs/PARALLEL-GPT-RECIPE.md`) is the closest analogue.

---

## Root cause in source

`cli.py`, lines 148–152 (`_write_default_response`):
```python
def _write_default_response(out_path: Path | None, text: str) -> None:
    if out_path is None:
        sys.stdout.write(text)
    else:
        _write_text(out_path, text)
```

When `out_path` is set, the function writes to the file and does NOT write to stdout. There is no "also" path. This is called at `cli.py` line 88:
```python
_write_default_response(args.out, text)
```

The `--apply`/`--dry-run` path (lines 77–86) handles `--out` separately and always emits JSON to stdout instead of text; that path's behavior is documented and expected.

---

## Cross-reference

This matters for the `ResponseTruncatedError` truncation bug (`2026-06-14-response-truncated-drops-out-file-and-session.md`): capturing stdout is **not** a viable robustness fallback when `--out` is set, because stdout is empty. Any caller relying on stdout as a backup to recover a partial reply on truncation will receive nothing.

---

## Suggested fix direction

**Option A (behavior fix — make "also" true):** In `_write_default_response`, write to both the file and stdout when `out_path` is set. Echo the reply to stdout even when `--out` is given; keep the file write. This matches the spirit of `PARALLEL-GPT-RECIPE.md` and makes stdout a viable robustness fallback.

**Option B (docs fix — make "instead of" clear everywhere):** Keep the current behavior (file only) and update `PARALLEL-GPT-RECIPE.md` to note that `--out FILE` suppresses stdout ("writes reply text to FILE; stdout is empty"). `bundle-protocol.md` already documents this correctly; `PARALLEL-GPT-RECIPE.md` does not.

Either way: cross-reference the truncation issue — even with Option A, partial-reply salvage on `ResponseTruncatedError` requires the exception to carry partial text (see fix direction 1 in the truncation issue), because `_write_default_response` is only reached on the success path.
