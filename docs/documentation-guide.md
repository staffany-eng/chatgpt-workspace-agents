# Agent Builder Documentation Guide

Use this guide for research notes, syntheses, decisions, and future agent templates.

## Writing Rules

- Separate evidence from interpretation.
- Keep source notes readable by a future agent in under two minutes.
- Prefer concrete source paths and URLs over vague references.
- Label weak, source-specific, or platform-specific claims.
- Delete repeated explanation instead of adding another section.

## Research Rules

- Store source evidence under `research/raw/`.
- Store maintained notes under `research/wiki/sources/`.
- Store cross-source patterns under `research/wiki/syntheses/`.
- Put durable accepted learnings in `research/wiki/decisions.md`.
- Update `research/wiki/index.md` and `research/wiki/log.md` for every ingest.
- Add one `Evidence Trace` entry per `What They Said` bullet.

## Source Handling

- Official docs: store URL, retrieval date, short extracts, and local summaries.
- MIT or local repos: store inventories, hashes, and focused extracts rather than raw-copying everything by default.
- Private repos: never copy `.env`, tokens, credentials, auth profiles, or session transcripts.
- Memory files: summarize structure and policy first; inspect content only when explicitly useful.

## Promotion Rules

- Weight 1-2 evidence stays as observation or prompt.
- Weight 3 evidence can become a weak synthesis.
- Weight 4 evidence can guide planning with caveats.
- Weight 5 evidence can become a candidate decision after cross-checking.

