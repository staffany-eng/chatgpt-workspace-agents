# Memory Models

## Evidence Used

- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - weight 5.
- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.
- [ChatGPT Workspace Agent Official Docs](../sources/chatgpt-workspace-agent-docs.md) - weight 5.
- [OpenClaw Kaiyi Current Implementation](../sources/openclaw-kaiyi-implementation.md) - weight 5 for local audit.

## Synthesis

Memory should be scoped and deliberate.

OpenClaw uses workspace Markdown files: daily notes, long-term memory, and optional dream summaries. Hermes uses bounded `MEMORY.md` and `USER.md`, frozen at session start, plus session search and optional memory providers. ChatGPT workspace agents expose memory and files through product surfaces, but official docs should be re-checked before assuming exact persistence semantics.

## Planning Rules

- Put stable public operating rules in instructions or files, not memory.
- Put user-specific preferences in memory when the product supports it.
- Put reusable examples and templates in files or skills.
- Do not store secrets in memory.
- For shared agents, explicitly decide whether context is per-user, agent-owned, or shared.

