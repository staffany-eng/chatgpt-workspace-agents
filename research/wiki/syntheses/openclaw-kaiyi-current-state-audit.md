# OpenClaw Kaiyi Current State Audit

## Evidence Used

- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - normative OpenClaw source.
- [OpenClaw Kaiyi Current Implementation](../sources/openclaw-kaiyi-implementation.md) - local implementation evidence.

## Findings

| Pattern | Status | Evidence |
| --- | --- | --- |
| Workspace-style runtime files | matches docs | `workspace-*/AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`, memory files |
| Long-term vs daily memory split | matches docs with local security refinement | `MEMORY.md` only loaded in main/private sessions |
| Lessons as safe operational memory | local adaptation | `LESSONS.md` is a high-signal operational channel not emphasized as strongly in official docs |
| Root coding-agent instructions separate from runtime prompts | local adaptation | root `AGENTS.md`, `CLAUDE.md`, `.claude/rules/*` |
| Hook-backed verification loop | local adaptation | shared Claude/Codex hook scripts |
| Cron vs heartbeat distinction | matches docs | Kaios heartbeat and cron scripts use different roles |
| Plugin convention lessons | partial/local adaptation | lessons record `configSchema` and self-contained plugin directory requirements |
| Katalyst safe iteration lifecycle | local adaptation | plan/code/doctor/smoke/promote/rollback pattern |

## Planning Use

Use this repo as a checklist for what a mature ChatGPT workspace agent may need conceptually: instruction boundaries, memory policy, operational lessons, verification evidence, scheduled behavior, and safe iteration. Do not assume the exact scripts or hook surfaces exist in ChatGPT.

