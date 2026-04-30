# Ingest Source Playbook

Use this when adding a source to the Agent Builder research wiki.

## Steps

1. Decide source class: `official docs`, `local implementation`, `repo docs`, `research process`, or `public article`.
2. Create or update a raw record under `research/raw/<source-class>/`.
3. Preserve retrieval metadata: URL or local path, date checked, commit SHA when applicable, and privacy/copyright policy.
4. Add short source extracts or an inventory manifest. Do not copy secrets or raw private credentials.
5. Create a maintained note under `research/wiki/sources/`.
6. Add direct observations under `What They Said`.
7. Add one `Evidence Trace` entry per observation, pointing to a raw file line.
8. Add a source-only `Learning Summary`.
9. Run the `Synthesis Gate` against `docs/product-compass.md`, `research/wiki/weights.md`, and active syntheses.
10. Add `Possible Agent Builder Relevance` with labels such as `Agent-synthesized`, `Do-not-promote`, or `Open question`.
11. Update `research/wiki/index.md` and `research/wiki/log.md`.
12. Run the audit tool until all factors pass.

## Source Note Template

```md
# Title

## Source Metadata

- Type:
- Source class:
- Source URL or path:
- Date ingested:
- Context:
- Default weight:
- Privacy:

## Context Caveat

## Evidence Used

## What They Said

## Evidence Trace

## Learning Summary

## Synthesis Gate

## Possible Agent Builder Relevance

## Follow-Up Questions
```

