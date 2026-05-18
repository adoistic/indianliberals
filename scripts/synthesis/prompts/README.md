# Cross-link resolver prompts

Canonical prompt files for the Phase A cross-link audit (see
`docs/superpowers/specs/2026-05-18-cross-link-audit-design.md`).

The system is designed so the same prompt can be invoked two ways:

## Manual path (interactive Claude session)

When the headless `claude -p` lane is rate-limited or you want
human-supervised resolution, the prompts are read directly by an
interactive Claude operator in a chat session. The operator pastes
a batch from `data/synthesis/unlinked.jsonl` after the prompt and
emits `data/synthesis/resolutions.jsonl` line-by-line.

This is how the initial Phase A run was executed (2026-05-18).

## Automated path (`claude -p` headless)

`scripts/synthesis/resolve-unlinked.py` reads the same prompt files,
chunks the unlinked entries into batches, and dispatches each batch
through `claude -p` with the prompt as input. Output goes to the
same `resolutions.jsonl`. Same prompts → same output format → both
paths are interchangeable.

To re-run via the automated path:

    python3 scripts/synthesis/prepare-unlinked.py
    python3 scripts/synthesis/resolve-unlinked.py \
        --batches 10 --concurrency 2
    python3 scripts/synthesis/apply-resolutions.py

Requires the `claude` CLI on PATH with an authenticated Max plan.

## Files

- `system-resolver.txt` — the system message. Defines the role,
  the three-role model, the output JSON schema, and rules with
  examples. Both paths use this verbatim.
- (per-collection user prompts are derived programmatically in
  `resolve-unlinked.py` by concatenating the collection-specific
  payload to a short stub instruction)

## Design constraints

- **Single source of truth**: the prompt files are the spec. Code
  reads them; humans read them; if behaviour changes, edit here.
- **Deterministic output schema**: every resolution is exactly one
  JSON line. No prose, no fences. Trivially parseable.
- **Idempotence**: the apply step is no-op for entries with
  existing structured refs. Re-running is safe.
- **Reproducibility**: any contributor with the cleaned authority
  + the prompts + the unlinked JSONL can regenerate the resolutions
  identically (modulo non-determinism in LLM output, mitigated by
  the validation step in `apply-resolutions.py`).
