# Midas Karpathy Research Process

## Source Metadata

- Type: local repo research-process source
- Source class: Midas process
- Source URL or path: `/Users/leekaiyi/workspace/midas`
- Date ingested: 2026-04-30
- Context: research workflow template
- Default weight: 5
- Privacy: local repo, no secrets copied

## Context Caveat

Midas is a product-research repo for F&B scheduling. It is used here only for its research operating model, not for Agent Builder product conclusions.

## Evidence Used

- Raw record: [research/raw/midas/research-process.md](../../raw/midas/research-process.md)

## What They Said

- Midas preserves immutable evidence under `research/raw/` and maintained source notes under `research/wiki/sources/`.
- Midas requires evidence traces that map source-note observations back to raw source records.
- Midas uses weights, syntheses, decisions, logs, playbooks, and audit scripts as separate compounding surfaces.
- Midas audits source ingests across raw preservation, maintained note quality, compounding, auditability, and readability.

## Evidence Trace

- Claim: Midas preserves immutable evidence under `research/raw/` and maintained source notes under `research/wiki/sources/`. Evidence: The raw record lists the raw/wiki split and source-note structure. Source: `research/raw/midas/research-process.md:21`.
- Claim: Midas requires evidence traces that map source-note observations back to raw source records. Evidence: The raw record summarizes the Karpathy audit skill's one-trace-per-claim rule. Source: `research/raw/midas/research-process.md:32`.
- Claim: Midas uses weights, syntheses, decisions, logs, playbooks, and audit scripts as separate compounding surfaces. Evidence: The raw inventory lists these source-of-truth roles separately. Source: `research/raw/midas/research-process.md:24`.
- Claim: Midas audits source ingests across raw preservation, maintained note quality, compounding, auditability, and readability. Evidence: The raw record identifies the five audit dimensions. Source: `research/raw/midas/research-process.md:28`.

## Learning Summary

- The research corpus should preserve raw evidence and maintain readable notes separately.
- Auditability should be automated so future agents cannot skip evidence traces.
- Product truth should compound through syntheses and decisions, not direct source-note promotion.
- The first Agent Builder deliverable should be a source map and synthesis corpus before templates.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`
- Evidence weight check: default weight 5; use as operating process for the corpus.
- Decision: promoted as the repo research workflow pattern.

## Possible Agent Builder Relevance

- Agent-synthesized: Reuse Midas' raw/wiki/audit pattern for all OpenClaw, Hermes, ChatGPT, and local implementation sources.
- Agent-synthesized: Keep source notes short enough for future agents while preserving raw evidence pointers.
- Do-not-promote: Midas' F&B product decisions do not apply to workspace-agent design.

## Follow-Up Questions

- Should the audit later validate source line numbers against raw files more strictly?
- Should future ingests include a generated source manifest for every public docs site?

