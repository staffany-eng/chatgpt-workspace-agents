# Agent Builder Research Wiki Index

This directory is the maintained research wiki for designing ChatGPT workspace agents. The pattern follows Midas: raw sources live under `research/raw/`, source notes live under `research/wiki/sources/`, cross-source syntheses live under `research/wiki/syntheses/`, and accepted learnings live in `research/wiki/decisions.md`.

## Source Of Truth

- `docs/product-compass.md` defines current purpose, thesis, guardrails, and unknowns.
- `docs/documentation-guide.md` defines writing and research rules.
- `research/raw/` stores source evidence, inventories, metadata, and short extracts.
- `research/wiki/sources/` stores maintained source notes.
- `research/wiki/syntheses/` stores cross-source patterns.
- `research/wiki/weights.md` defines evidence weights.
- `research/wiki/decisions.md` stores accepted learnings.
- `research/wiki/log.md` records ingests and syntheses.
- `research/tools/` stores local helper scripts.

## Source Notes

- [Midas Karpathy Research Process](./sources/midas-research-process.md)
- [OpenClaw Official Docs](./sources/openclaw-official-docs.md)
- [OpenClaw Kaiyi Current Implementation](./sources/openclaw-kaiyi-implementation.md)
- [Hermes Agent Docs And Patterns](./sources/hermes-agent-docs.md) - refreshed from live docs on 2026-05-10
- [ChatGPT Workspace Agent Official Docs](./sources/chatgpt-workspace-agent-docs.md)
- [BigQuery MCP Proxy](./sources/bigquery-mcp-proxy.md)
- [StaffAny Hermes Data Bot POC](./sources/staffany-hermes-data-bot-poc.md)
- [NurtureAny Leadership Tactical Pause](./sources/nurtureany-leadership-tactical-pause.md)
- [NurtureAny Sales Training Materials](./sources/nurtureany-sales-training-materials.md)
- [NurtureAny Sales Onboarding Master Template](./sources/nurtureany-sales-onboarding-master-template.md)

## Syntheses

- [Workspace Agent Abstraction Boundaries](./syntheses/workspace-agent-abstraction-boundaries.md)
- [Memory Models](./syntheses/memory-models.md)
- [Instruction Surfaces](./syntheses/instruction-surfaces.md)
- [Skills vs Apps vs MCP](./syntheses/skills-vs-apps-vs-mcp.md)
- [Automation, Heartbeat, Cron, And Schedules](./syntheses/automation-heartbeat-cron-schedules.md)
- [OpenClaw Kaiyi Current State Audit](./syntheses/openclaw-kaiyi-current-state-audit.md)
- [ChatGPT Workspace Agent Build Rubric](./syntheses/chatgpt-workspace-agent-build-rubric.md)
- [NurtureAny Sales Best Practices](./syntheses/nurtureany-sales-best-practices.md)

## Maintenance

- Run `bun research/tools/build-source-inventories.ts` after source repos or docs change.
- Run `bun research/tools/audit-agent-ingest.ts --wiki <source-note.md> --fail-under 10` for every maintained source note.
- Keep raw/source notes split even when a synthesis summarizes multiple sources.
