---
name: agent-builder-research-ingest-audit
description: Use when ingesting or auditing Agent Builder research sources to preserve raw evidence, source notes, traces, syntheses, and decisions.
---

# Agent Builder Research Ingest Audit

Use this for every Agent Builder source ingest.

## Required Loop

1. Read `docs/product-compass.md`, `docs/documentation-guide.md`, and `research/wiki/playbooks/ingest-source.md`.
2. Preserve source evidence or an inventory under `research/raw/`.
3. Create or update a maintained note under `research/wiki/sources/`.
4. Add `Evidence Trace` with one trace entry for every `What They Said` bullet.
5. Add `Learning Summary` and a completed or blocked `Synthesis Gate`.
6. Update `research/wiki/index.md` and `research/wiki/log.md`.
7. Run:

```bash
bun research/tools/audit-agent-ingest.ts --wiki <source-note.md> --fail-under 10
```

8. If any factor is below `10/10`, fix the source note, raw metadata, index, log, or trace issue and rerun.
9. Update or create synthesis pages when a source changes a cross-source pattern.

## Five Factors

- Raw preservation: raw source record or generated inventory exists with metadata and content policy.
- Maintained source note: required sections, no TODO residue, direct observations, source learning, and synthesis gate.
- Compounding: source indexed, logged, weighted, and not promoted directly as a decision.
- Auditability: every major claim traces to a raw path and line number.
- Readability: source note is concise, structured, wrapped, and useful to future agents.

## Evidence Trace Format

```md
- Claim: Short claim matching a `What They Said` bullet. Evidence: One-line paraphrase of the supporting raw evidence. Source: `research/raw/example/source.md:42`.
```

