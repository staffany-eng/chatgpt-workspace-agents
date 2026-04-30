# Workspace Agent Abstraction Boundaries

## Evidence Used

- [ChatGPT Workspace Agent Official Docs](../sources/chatgpt-workspace-agent-docs.md) - weight 5.
- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - weight 5 for OpenClaw design intent.
- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.

## Synthesis

ChatGPT workspace agents should be planned around ChatGPT-native surfaces:

- Instructions: mission, operating rules, source hierarchy, safety policy, output style.
- Apps/tools/custom MCPs: capabilities that reach external systems.
- Skills: repeatable workflows, output formats, examples, scripts, and procedural knowledge.
- Files: durable reference material, templates, examples, and source docs.
- Memory: per-user or per-agent continuity, not a dumping ground for public instructions.
- Schedules/channels: when and where the agent runs.
- Auth/write approvals: who acts, using whose credentials, with what confirmation rules.

## Planning Rule

When a future plan adds any capability, assign it to exactly one primary surface and name the supporting surfaces. If something seems to belong everywhere, it is probably too vague.

