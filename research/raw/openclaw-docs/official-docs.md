# OpenClaw Official Docs Raw Record

## Source Metadata

- Type: official documentation cluster
- Source class: OpenClaw official docs
- Base URL: `https://docs.openclaw.ai/`
- Date checked: 2026-04-30
- Privacy: public docs

## Raw Content Policy

This record stores citation-safe extracts and summaries from official OpenClaw docs. It does not mirror the full docs site. The generated URL inventory in `research/raw/openclaw-docs/url-inventory.md` stores broader coverage.

## Source Inventory

- Home: `https://docs.openclaw.ai/`
- Agent workspace: `https://docs.openclaw.ai/concepts/agent-workspace`
- Memory: `https://docs.openclaw.ai/concepts/memory`
- Skills: `https://docs.openclaw.ai/tools/skills`
- Gateway CLI: `https://docs.openclaw.ai/cli/gateway`
- Agents CLI: `https://docs.openclaw.ai/cli/agents`
- Automation: `https://docs.openclaw.ai/automation/`
- Security: `https://docs.openclaw.ai/gateway/security`
- FAQ: `https://docs.openclaw.ai/start/faq/`

## Evidence Extracts

- OpenClaw docs describe the Gateway as the source of truth for sessions, routing, and channel connections.
- The agent workspace is the agent's home and default working directory for file tools and workspace context, but it is not a hard sandbox unless sandboxing is enabled.
- Standard workspace files include `AGENTS.md`, `SOUL.md`, `USER.md`, `IDENTITY.md`, `TOOLS.md`, `HEARTBEAT.md`, `BOOT.md`, `BOOTSTRAP.md`, `memory/YYYY-MM-DD.md`, optional `MEMORY.md`, optional `skills/`, and optional `canvas/`.
- The docs say config, credentials, auth profiles, session transcripts, and managed skills live under `~/.openclaw/` and should not be committed to the workspace repo.
- OpenClaw memory is plain Markdown in the workspace: long-term `MEMORY.md`, daily `memory/YYYY-MM-DD.md`, and optional `DREAMS.md`.
- OpenClaw skills are AgentSkills-compatible folders. Skill precedence is workspace skills first, then project agent skills, personal skills, managed OpenClaw skills, bundled skills, and extra dirs.
- OpenClaw automation separates scheduled cron tasks, background tasks, Task Flow, standing orders, hooks, and heartbeat.
- The security docs frame OpenClaw as a single trusted operator boundary, not a hostile multi-tenant security boundary.
- The security docs recommend least access, explicit auth, command policy, browser isolation, careful plugin trust, and `openclaw security audit`.
- The gateway docs describe the Gateway as the WebSocket server for channels, nodes, sessions, and hooks, with `openclaw gateway probe` available to inspect local or remote mode.

## First-Pass Learning

OpenClaw's core abstraction is a self-hosted gateway plus per-agent workspaces. Workspace files are memory and instructions; `~/.openclaw/` is runtime/config state. This split is the strongest OpenClaw lesson for ChatGPT workspace-agent planning.

