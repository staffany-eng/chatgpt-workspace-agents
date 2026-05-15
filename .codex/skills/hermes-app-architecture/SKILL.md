---
name: hermes-app-architecture
description: "Apply StaffAny Hermes app-packet architecture guidance before changing this repo's Hermes bot packets, including NurtureAny, Da Ta Hermz, Launchbot, and PSM Ops. Use for plans or edits touching SOUL.md, AGENTS.md, skills, runtime docs, MCPs, config templates, manifests, health checks, deploy/runbooks, or regression cases."
---

# Hermes App Architecture

Use this skill when planning or editing Hermes bot packets in `staffany-eng/chatgpt-workspace-agents`.

## Grounding

Before deciding on architecture or file placement, read:

1. The affected app's `AGENTS.md`.
2. `research/wiki/sources/hermes-agent-docs.md`.
3. `research/wiki/syntheses/hermes-runtime-bot-operating-model.md`.

For cross-surface instruction changes, also inspect:

- `research/wiki/syntheses/instruction-surfaces.md`
- `research/wiki/syntheses/skills-vs-apps-vs-mcp.md`

## Source Boundaries

Classify each proposed change into one primary surface before editing:

- `SOUL.md`: identity, voice, short standing behavior, and high-priority safety or routing rules.
- `AGENTS.md`: repo/app maintainer workflow, pre-read rules, verification commands, and coding constraints.
- `SKILL.md`: repeatable procedures and workflow execution steps.
- `skills/.../references`: detailed business knowledge, SOPs, examples, reviewed lessons, and longer reference material.
- `runtime/*.md`: MCP/runtime contracts, env vars, scopes, safety limits, health checks, and runbooks.
- `tests/regression-cases.md`: expected behavior assertions, not duplicated workflow manuals.
- `profile/config.template.yaml` and `app.manifest.json`: wiring, allowlists, non-secret config shape, and MCP entrypoints.
- Live Hermes profile: runtime state only. Do not treat `.env`, sessions, memory, logs, cron state, gateway state, or temporary live fixes as durable product truth until promoted into repo files.

## Working Rules

- Prefer the existing app-packet shape over inventing new folders.
- Keep behavior rules in the narrowest durable surface that can enforce them.
- Do not duplicate the same long rule across `SOUL.md`, skills, runtime docs, and regression notes.
- Add or narrow MCP capabilities before writing skill instructions that depend on those tools.
- When adding a new MCP server, update every durable wiring surface in the same change: `profile/config.template.yaml`, `app.manifest.json`, health/cloud-heartbeat expected tool counts, runtime docs, verifier checks, and deploy/live-config migration behavior. Remember that live profile `config.yaml` is preserved runtime state, so deploy must either add the missing non-secret MCP server stanza from the template or document an explicit live migration before restart.
- Keep secrets, raw Slack transcripts, raw HubSpot rows, OAuth files, memory dumps, and runtime logs out of the repo.
- Treat runtime learning as unreviewed drift until it becomes a reviewed repo change with verification.

## Verification

Run the narrow verifier for the touched app packet when app files change:

- NurtureAny: `npm run nurtureany-sales-bot:verify`
- Hermes Data Bot: `npm run hermes-data-bot:verify`
- Launchbot: `npm run launch-superpower-bot:verify`
- PSM Ops: `npm run psm-ops-bot:verify`

For repo-wide guidance, shared scripts, or multiple app packets, run `npm run verify` when practical.
