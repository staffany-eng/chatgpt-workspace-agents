# Instruction Surfaces

## Evidence Used

- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - weight 5.
- [OpenClaw Kaiyi Current Implementation](../sources/openclaw-kaiyi-implementation.md) - weight 5 for local audit.
- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.
- [ChatGPT Workspace Agent Official Docs](../sources/chatgpt-workspace-agent-docs.md) - weight 5.

## Synthesis

Instruction surfaces should stay narrow.

OpenClaw separates repo coding-agent instructions, runtime agent instructions, persona, user profile, tool notes, heartbeat notes, memory, and lessons.
Hermes has priority-ordered context files plus global `SOUL.md`; its prompt assembly keeps identity, frozen memory/profile snapshots, skills index, project context, platform hints, and ephemeral overlays as separate layers.
ChatGPT workspace agents have builder instructions, skills, files, channel settings, schedules, and app/tool settings.

## Planning Rules

- Put durable behavior and source hierarchy in the agent instructions.
- Put procedures in skills.
- Put examples and reference documents in files.
- Put runtime schedule prompts in schedules.
- Put channel-specific behavior in channel settings.
- For Hermes apps, use `SOUL.md` for identity and standing behavior, project/context files for repo rules, skills for reusable workflows, and ephemeral/channel prompts only for channel-local behavior that should not become durable source truth.
- Avoid duplicating the same rule in multiple surfaces unless each has a different audience.
