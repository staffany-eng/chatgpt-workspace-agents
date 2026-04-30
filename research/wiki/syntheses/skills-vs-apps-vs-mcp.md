# Skills vs Apps vs MCP

## Evidence Used

- [ChatGPT Workspace Agent Official Docs](../sources/chatgpt-workspace-agent-docs.md) - weight 5.
- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - weight 5.
- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.

## Synthesis

Skills and apps solve different problems.

- Use apps/connectors when the agent needs access to external systems such as Google Drive, Calendar, Slack, SharePoint, or other business tools.
- Use custom MCPs when the agent needs a custom tool surface or backend integration that official apps do not provide.
- Use skills when the agent needs a repeatable method, output format, examples, scripts, or domain procedure.
- Use files when the agent needs static references, templates, or policy documents.

## Planning Rules

- If the need is "do this process consistently", make a skill.
- If the need is "reach this system", use an app or MCP.
- If the need is "remember this reference", use a file.
- If the need is "act with a credential", decide end-user account versus agent-owned account and write approval behavior.

