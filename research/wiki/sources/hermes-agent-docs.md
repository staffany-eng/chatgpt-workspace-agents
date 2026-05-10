# Hermes Agent Docs And Patterns

## Source Metadata

- Type: public repo docs and live architecture docs
- Source class: Hermes Agent
- Source URL or path: `https://github.com/NousResearch/hermes-agent`; `https://hermes-agent.nousresearch.com/docs/`
- Date ingested: 2026-04-30
- Date refreshed: 2026-05-10
- Context: primary Hermes runtime architecture source for this repo, alternate source for non-Hermes agent patterns
- Default weight: 4
- Privacy: public MIT repo and public docs

## Context Caveat

Hermes is a self-hosted agent runtime, not ChatGPT workspace agents. Use it for architecture vocabulary and proven abstraction patterns, not direct product behavior.

## Evidence Used

- Raw record: [research/raw/hermes/hermes-docs-and-patterns.md](../../raw/hermes/hermes-docs-and-patterns.md)
- Generated docs inventory: [research/raw/hermes/docs-inventory.md](../../raw/hermes/docs-inventory.md)
- Live docs refresh: [research/raw/hermes/live-docs-refresh-2026-05-10.md](../../raw/hermes/live-docs-refresh-2026-05-10.md)

## What They Said

- Hermes publishes machine-readable docs entry points, and the May 10 full bundle covers 147 source pages across setup, runtime, features, messaging, integrations, guides, developer docs, and reference.
- Hermes profiles are separate runtime homes with their own config, secrets file, identity, memory, sessions, skills, cron jobs, and gateway state.
- Hermes prompt assembly separates identity, memory snapshots, user profile snapshots, skills index, context files, timestamp/session data, platform hints, and ephemeral overlays.
- Hermes context files use priority ordering, load `SOUL.md` from `HERMES_HOME` as identity, and progressively discover subdirectory context during tool use.
- Hermes skills are progressive-disclosure procedural memory, with support for references, templates, scripts, assets, environment prompts, config settings, platform filters, and conditional activation.
- Hermes can create or update skills through its self-improvement loop, while Curator reviews agent-created skills for staleness, narrowness, and duplication.
- Hermes memory is bounded into `MEMORY.md` and `USER.md`, snapshotted at session start, and should skip raw dumps, session ephemera, context-file content, and secrets.
- Hermes external memory providers are additive to built-in memory rather than replacements.
- Hermes MCP support covers local stdio and remote HTTP servers, startup discovery, prefixed tool registration, per-server filtering, utility wrappers, dynamic refresh, and stdio environment filtering.
- Hermes Slack support uses Socket Mode, mention-first channel starts, thread continuation, per-channel prompts and skill bindings, and reinstall-after-scope-change operations.
- Hermes cron jobs support recurring work, skill attachment, workdir binding, multi-target delivery, `[SILENT]` quiet success suppression, and script-only no-agent checks.
- Hermes distinguishes in-turn subagent delegation from durable Kanban work queues with named profiles, comments, run history, and gateway-embedded dispatch.
- Hermes security guidance layers user authorization, command approval, container isolation, MCP credential filtering, context-file scanning, cross-session isolation, input sanitization, and checkpoints/rollback.
- Hermes persistent goals keep a session objective alive across turns with a judge loop and explicit pause, resume, and clear controls.

## Evidence Trace

- Claim: Hermes publishes machine-readable docs entry points, and the May 10 full bundle covers 147 source pages. Evidence: The live raw record stores retrieval metadata, category counts, and source count. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:198`.
- Claim: Hermes profiles are separate runtime homes with their own config, secrets file, identity, memory, sessions, skills, cron jobs, and gateway state. Evidence: The live raw record summarizes profile boundaries. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:199`.
- Claim: Hermes prompt assembly separates identity, memory snapshots, user profile snapshots, skills index, context files, timestamp/session data, platform hints, and ephemeral overlays. Evidence: The live raw record summarizes prompt assembly layers. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:200`.
- Claim: Hermes context files use priority ordering, load `SOUL.md` from `HERMES_HOME` as identity, and progressively discover subdirectory context during tool use. Evidence: The live raw record summarizes context-file behavior. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:201`.
- Claim: Hermes skills are progressive-disclosure procedural memory with rich packaging and activation metadata. Evidence: The live raw record summarizes the skills docs. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:202`.
- Claim: Hermes can create or update skills through its self-improvement loop, while Curator reviews agent-created skills for staleness, narrowness, and duplication. Evidence: The live raw record summarizes skill self-improvement and Curator. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:203`.
- Claim: Hermes memory is bounded into `MEMORY.md` and `USER.md`, snapshotted at session start, and should skip raw dumps, session ephemera, context-file content, and secrets. Evidence: The live raw record summarizes memory boundaries. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:204`.
- Claim: Hermes external memory providers are additive to built-in memory rather than replacements. Evidence: The live raw record summarizes memory-provider layering. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:205`.
- Claim: Hermes MCP support covers stdio/HTTP servers, discovery, prefixed tools, filtering, utilities, dynamic refresh, and env filtering. Evidence: The live raw record summarizes MCP behavior. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:206`.
- Claim: Hermes Slack support uses Socket Mode, mention-first channel starts, thread continuation, per-channel prompts and skill bindings, and reinstall-after-scope-change operations. Evidence: The live raw record summarizes Slack behavior. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:207`.
- Claim: Hermes cron jobs support recurring work, skill attachment, workdir binding, multi-target delivery, `[SILENT]` quiet success suppression, and script-only no-agent checks. Evidence: The live raw record summarizes cron behavior. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:208`.
- Claim: Hermes distinguishes in-turn subagent delegation from durable Kanban work queues with named profiles, comments, run history, and gateway-embedded dispatch. Evidence: The live raw record summarizes delegation versus Kanban. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:209`.
- Claim: Hermes security guidance layers authorization, approvals, isolation, credential filtering, scanning, sanitization, and rollback. Evidence: The live raw record summarizes security layers. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:210`.
- Claim: Hermes persistent goals keep a session objective alive across turns with a judge loop and explicit pause, resume, and clear controls. Evidence: The live raw record summarizes persistent goals. Source: `research/raw/hermes/live-docs-refresh-2026-05-10.md:211`.

## Learning Summary

- Hermes supports the app-packet split this repo is already using: source-controlled profile, skill, MCP, Slack, health-check, and runbook files guide durable behavior while the live profile owns runtime state.
- Hermes gives current vocabulary for prompt-layer boundaries: identity, memory, user profile, skills index, project context, platform hints, and ephemeral overlays are separate surfaces.
- Hermes reinforces a narrow-tool philosophy for business data work: MCP servers should be filtered, utility surfaces should be deliberate, and stdio env leakage should be controlled.
- Hermes automation is plural: cron, no-agent checks, persistent goals, subagent delegation, and Kanban solve different durability and coordination problems.
- Hermes should influence StaffAny Hermes Data Bot plans as weight-4 runtime architecture evidence, with StaffAny app packet behavior remaining the stronger local source.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, active syntheses, `apps/hermes-data-bot/`
- Evidence weight check: default weight 4; strong Hermes runtime source, but not universal product truth outside Hermes.
- Decision: refresh promoted into app-boundary, instruction, memory, skills/MCP, and automation syntheses as Hermes runtime guidance.

## Possible Agent Builder Relevance

- Agent-synthesized: Future Hermes Data Bot features should state whether they belong in `SOUL.md`, a skill, a reference file, an MCP contract, runtime config, memory, cron, Kanban, or health checks.
- Agent-synthesized: StaffAny data features should prefer filtered MCP tool surfaces and explicit no-agent health checks over broad tool exposure.
- Agent-synthesized: Slack channel-specific prompts and skill bindings are a Hermes-native design option, but StaffAny POC behavior should still follow the canonical app packet first.
- Do-not-promote: Do not copy Hermes' model/provider/plugin mechanics into ChatGPT workspace-agent templates without a ChatGPT-native source.
- Open question: Should StaffAny Hermes Data Bot adopt Kanban for explicit task workflows, while keeping ordinary data Q&A out of task-state machinery?

## Follow-Up Questions

- Which Hermes docs pages should become deeper source notes when a specific feature touches them: Slack, MCP config, cron, Kanban, or prompt assembly?
- Should StaffAny Hermes Data Bot define channel skill bindings for dedicated Slack channels after the POC widens?
- Should explicit StaffAny task workflows use Hermes Kanban while data Q&A remains answer-only?
