# Hermes Agent Docs And Patterns

## Source Metadata

- Type: public repo docs and architecture source
- Source class: Hermes Agent
- Source URL or path: `https://github.com/NousResearch/hermes-agent`
- Date ingested: 2026-04-30
- Context: alternate agent architecture source
- Default weight: 4
- Privacy: public MIT repo

## Context Caveat

Hermes is a self-hosted agent runtime, not ChatGPT workspace agents. Use it for architecture vocabulary and proven abstraction patterns, not direct product behavior.

## Evidence Used

- Raw record: [research/raw/hermes/hermes-docs-and-patterns.md](../../raw/hermes/hermes-docs-and-patterns.md)
- Generated docs inventory: [research/raw/hermes/docs-inventory.md](../../raw/hermes/docs-inventory.md)

## What They Said

- Hermes emphasizes a closed learning loop with agent-curated memory, autonomous skill creation, skill improvement, session search, and user modeling.
- Hermes splits memory into bounded `MEMORY.md` and `USER.md` stores, with frozen prompt snapshots at session start.
- Hermes skills use progressive disclosure and can include references, templates, scripts, assets, platform filters, env setup, and config settings.
- Hermes context files have explicit priority and progressive subdirectory discovery.
- Hermes supports external memory provider plugins alongside built-in memory.
- Hermes automations combine cron, webhooks, script pre-processing, skill chaining, and multi-platform delivery.
- Hermes migration docs map OpenClaw workspace files and runtime config into Hermes equivalents or archives.

## Evidence Trace

- Claim: Hermes emphasizes a closed learning loop with agent-curated memory, autonomous skill creation, skill improvement, session search, and user modeling. Evidence: The raw record summarizes README positioning. Source: `research/raw/hermes/hermes-docs-and-patterns.md:28`.
- Claim: Hermes splits memory into bounded `MEMORY.md` and `USER.md` stores, with frozen prompt snapshots at session start. Evidence: The raw record captures the memory docs. Source: `research/raw/hermes/hermes-docs-and-patterns.md:29`.
- Claim: Hermes skills use progressive disclosure and can include references, templates, scripts, assets, platform filters, env setup, and config settings. Evidence: The raw record summarizes Hermes skills docs. Source: `research/raw/hermes/hermes-docs-and-patterns.md:30`.
- Claim: Hermes context files have explicit priority and progressive subdirectory discovery. Evidence: The raw record captures context-file docs. Source: `research/raw/hermes/hermes-docs-and-patterns.md:31`.
- Claim: Hermes supports external memory provider plugins alongside built-in memory. Evidence: The raw record summarizes memory-provider behavior. Source: `research/raw/hermes/hermes-docs-and-patterns.md:32`.
- Claim: Hermes automations combine cron, webhooks, script pre-processing, skill chaining, and multi-platform delivery. Evidence: The raw record captures Hermes automation notes. Source: `research/raw/hermes/hermes-docs-and-patterns.md:33`.
- Claim: Hermes migration docs map OpenClaw workspace files and runtime config into Hermes equivalents or archives. Evidence: The raw record summarizes migration mapping. Source: `research/raw/hermes/hermes-docs-and-patterns.md:34`.

## Learning Summary

- Hermes gives strong vocabulary for procedural memory, bounded durable memory, and progressive disclosure.
- Hermes helps distinguish agent runtime infrastructure from reusable skill and memory abstractions.
- Hermes' OpenClaw migration doc is a useful bridge for understanding what OpenClaw surfaces are portable versus runtime-specific.
- Hermes should influence the Agent Builder rubric through abstraction patterns, not through runtime requirements.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, active syntheses
- Evidence weight check: default weight 4; strong architecture source with ChatGPT-context caveat.
- Decision: promoted into skills, memory, context, and automation syntheses as architecture guidance.

## Possible Agent Builder Relevance

- Agent-synthesized: ChatGPT workspace-agent skills should use progressive disclosure and clear triggers.
- Agent-synthesized: Memory should be bounded, curated, and separated from files and instructions.
- Do-not-promote: ChatGPT workspace agents do not inherit Hermes' runtime plugin, provider, or gateway mechanics.

## Follow-Up Questions

- Which Hermes skills should be studied individually for reusable skill-authoring patterns?
- Should the final builder produce Agent Skills-compatible skill folders for portability?

