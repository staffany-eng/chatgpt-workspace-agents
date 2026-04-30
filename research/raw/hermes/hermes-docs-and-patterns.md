# Hermes Agent Docs And Patterns Raw Record

## Source Metadata

- Type: public repo docs and architecture source
- Source class: Hermes Agent
- Source URL: `https://github.com/NousResearch/hermes-agent`
- Local temp clone used during planning: `/tmp/hermes-agent-agent-builder`
- Date checked: 2026-04-30
- Privacy: public MIT repo

## Raw Content Policy

This record stores source metadata, inventory summaries, and short extracts. The generated inventory in `research/raw/hermes/docs-inventory.md` stores all discovered Hermes docs, skills, optional skills, and plugin docs with hashes.

## Source Inventory

- README and `AGENTS.md`
- Website docs under `website/docs/`
- Built-in skills under `skills/`
- Optional skills under `optional-skills/`
- Plugin docs and plugin manifests under `plugins/`
- Memory plugins under `plugins/memory/`
- Developer docs for architecture, agent loop, prompt assembly, tools runtime, session storage, gateway internals, cron internals, memory-provider plugins, and context-engine plugins.

## Evidence Extracts

- Hermes describes itself as a self-improving agent with a learning loop, agent-curated memory, autonomous skill creation, skill improvement, session search, and cross-session user modeling.
- Hermes separates `MEMORY.md` and `USER.md` with character limits, frozen prompt snapshots, and a `memory` tool for add, replace, and remove actions.
- Hermes treats skills as on-demand knowledge documents with progressive disclosure: skill list, full skill view, then specific reference file.
- Hermes skills support frontmatter, references, templates, scripts, assets, platform restrictions, conditional activation, secure environment variable setup, and config settings.
- Hermes context files prioritize `.hermes.md` or `HERMES.md`, then `AGENTS.md`, then `CLAUDE.md`, then Cursor rules, while `SOUL.md` is global to the Hermes instance.
- Hermes progressively discovers subdirectory context files during tool use to avoid startup prompt bloat.
- Hermes has external memory provider plugins and keeps external providers alongside built-in memory rather than replacing it.
- Hermes supports cron and webhook automations with script pre-processing, skill chaining, and multi-platform delivery.
- Hermes' OpenClaw migration docs explicitly map OpenClaw workspace files, memories, skills, model/provider config, messaging settings, command allowlists, MCP servers, TTS, hooks, plugins, and archived files.
- Hermes highlights that imported OpenClaw `IDENTITY.md`, `TOOLS.md`, `HEARTBEAT.md`, and `BOOTSTRAP.md` may not have direct equivalents and need manual review.

## First-Pass Learning

Hermes is valuable because it makes agent abstractions explicit and operational: bounded memory, progressive skills, context-file priority, pluginized memory providers, cron/webhook automation, and migration mapping from OpenClaw. For ChatGPT workspace agents, use Hermes as an architecture vocabulary source, not as a product behavior source.

