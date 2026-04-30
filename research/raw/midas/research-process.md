# Midas Research Process Raw Record

## Source Metadata

- Type: local repo research-process source
- Source class: Midas process
- Source paths:
  - `/Users/leekaiyi/workspace/midas/AGENTS.md`
  - `/Users/leekaiyi/workspace/midas/docs/documentation-guide.md`
  - `/Users/leekaiyi/workspace/midas/research/wiki/index.md`
  - `/Users/leekaiyi/workspace/midas/research/wiki/playbooks/ingest-source.md`
  - `/Users/leekaiyi/workspace/midas/research/wiki/weights.md`
  - `/Users/leekaiyi/workspace/midas/skills/karpathy-research-ingest-audit/SKILL.md`
- Date checked: 2026-04-30
- Privacy: local repo, no secrets copied

## Raw Content Policy

This record stores source metadata and short extracts from the local Midas research workflow. It does not copy the full Midas corpus. Midas remains the process template, not a product-domain source for Agent Builder.

## Source Inventory

- Midas uses `research/raw/` for immutable evidence.
- Midas uses `research/wiki/sources/` for maintained source notes.
- Midas uses `research/wiki/syntheses/` for cross-source patterns.
- Midas uses `research/wiki/weights.md` for evidence weights.
- Midas uses `research/wiki/decisions.md` for accepted learnings before product promotion.
- Midas uses `research/tools/audit-karpathy-ingest.ts` to audit raw preservation, maintained notes, compounding, auditability, and readability.

## Evidence Extracts

- `AGENTS.md` routes agents to `docs/product-compass.md`, `docs/documentation-guide.md`, and the Karpathy audit skill before research ingest completion.
- The Karpathy audit skill requires preserving raw source evidence under `research/raw/`, creating maintained notes under `research/wiki/sources/`, adding one `Evidence Trace` entry per `What They Said` bullet, and iterating the audit until every factor scores `10/10`.
- The Midas wiki index says raw sources, source notes, syntheses, weights, decisions, logs, playbooks, and tools each have separate source-of-truth roles.
- The ingest playbook requires `Source Metadata`, `Context Caveat`, `Evidence Used`, `What They Said`, `Evidence Trace`, `Learning Summary`, `Synthesis Gate`, `Possible Midas Relevance`, and `Follow-Up Questions`.
- The weights file says high-weight evidence can influence planning, while weak evidence should remain as observations, prompts, risks, or questions.
- The documentation guide warns against promoting weak or source-specific relevance as product truth.

## First-Pass Learning

Midas is useful here because it already solved the operating problem for a growing research corpus: preserve raw evidence, maintain readable notes, audit traceability, and let synthesis compound without losing source boundaries.

