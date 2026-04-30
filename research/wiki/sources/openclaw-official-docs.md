# OpenClaw Official Docs

## Source Metadata

- Type: official documentation cluster
- Source class: OpenClaw official docs
- Source URL or path: `https://docs.openclaw.ai/`
- Date ingested: 2026-04-30
- Context: OpenClaw design intent
- Default weight: 5
- Privacy: public docs

## Context Caveat

Official OpenClaw docs describe OpenClaw, not ChatGPT workspace agents. Use these as design-source evidence for OpenClaw patterns, then translate into ChatGPT-native surfaces.

## Evidence Used

- Raw record: [research/raw/openclaw-docs/official-docs.md](../../raw/openclaw-docs/official-docs.md)
- Generated URL inventory: [research/raw/openclaw-docs/url-inventory.md](../../raw/openclaw-docs/url-inventory.md)

## What They Said

- OpenClaw centers on a Gateway that owns sessions, routing, channels, nodes, and hooks.
- OpenClaw treats the agent workspace as home, memory, and default working directory, but not as a hard sandbox by default.
- OpenClaw workspace files split instructions, persona, user profile, tool notes, heartbeat, bootstrap, daily memory, long-term memory, skills, and canvas.
- OpenClaw keeps runtime config, credentials, auth profiles, sessions, and managed skills under `~/.openclaw/`, outside the workspace repo.
- OpenClaw skills use AgentSkills-compatible folders with explicit precedence across workspace, project, personal, managed, bundled, and extra skill dirs.
- OpenClaw separates cron, tasks, Task Flow, standing orders, hooks, and heartbeat.
- OpenClaw's security model is a single trusted operator boundary, not hostile multi-tenant isolation.

## Evidence Trace

- Claim: OpenClaw centers on a Gateway that owns sessions, routing, channels, nodes, and hooks. Evidence: The raw record summarizes the home and gateway docs. Source: `research/raw/openclaw-docs/official-docs.md:37`.
- Claim: OpenClaw treats the agent workspace as home, memory, and default working directory, but not as a hard sandbox by default. Evidence: The raw record captures the workspace doc's workspace/sandbox distinction. Source: `research/raw/openclaw-docs/official-docs.md:28`.
- Claim: OpenClaw workspace files split instructions, persona, user profile, tool notes, heartbeat, bootstrap, daily memory, long-term memory, skills, and canvas. Evidence: The raw record lists the standard workspace file map. Source: `research/raw/openclaw-docs/official-docs.md:29`.
- Claim: OpenClaw keeps runtime config, credentials, auth profiles, sessions, and managed skills under `~/.openclaw/`, outside the workspace repo. Evidence: The raw record summarizes the not-in-workspace list. Source: `research/raw/openclaw-docs/official-docs.md:30`.
- Claim: OpenClaw skills use AgentSkills-compatible folders with explicit precedence across workspace, project, personal, managed, bundled, and extra skill dirs. Evidence: The raw record captures the skill precedence rule. Source: `research/raw/openclaw-docs/official-docs.md:32`.
- Claim: OpenClaw separates cron, tasks, Task Flow, standing orders, hooks, and heartbeat. Evidence: The raw record summarizes the automation taxonomy. Source: `research/raw/openclaw-docs/official-docs.md:33`.
- Claim: OpenClaw's security model is a single trusted operator boundary, not hostile multi-tenant isolation. Evidence: The raw record captures the security trust model. Source: `research/raw/openclaw-docs/official-docs.md:34`.

## Learning Summary

- OpenClaw's most reusable design lesson is separation between workspace memory/instructions and runtime config/credentials.
- OpenClaw has a mature vocabulary for agent operating surfaces: workspace files, skills, hooks, cron, heartbeat, standing orders, tasks, and Gateway.
- OpenClaw's security posture depends on a clear trust boundary, explicit auth, and least access.
- For ChatGPT workspace agents, OpenClaw should inform the mapping, not dictate the product UI.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, `research/wiki/syntheses/workspace-agent-abstraction-boundaries.md`
- Evidence weight check: default weight 5 for OpenClaw design intent; apply directly to OpenClaw analysis and indirectly to ChatGPT planning.
- Decision: promoted as normative OpenClaw source.

## Possible Agent Builder Relevance

- Agent-synthesized: Translate OpenClaw workspace files into ChatGPT surfaces: instructions, files, memory, skills, apps/tools, schedules, and channels.
- Agent-synthesized: Keep credentials/config outside reusable agent instruction packs.
- Do-not-promote: Do not assume ChatGPT workspace agents expose OpenClaw's Gateway, node, hook, or direct file layout semantics.

## Follow-Up Questions

- Which OpenClaw docs pages should become separate source notes after the first cluster pass?
- Which OpenClaw automation concepts map cleanly to ChatGPT schedules versus custom MCPs?

