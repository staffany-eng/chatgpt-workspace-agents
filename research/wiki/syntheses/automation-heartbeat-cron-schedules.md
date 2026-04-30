# Automation, Heartbeat, Cron, And Schedules

## Evidence Used

- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - weight 5.
- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.
- [ChatGPT Workspace Agent Official Docs](../sources/chatgpt-workspace-agent-docs.md) - weight 5.
- [OpenClaw Kaiyi Current Implementation](../sources/openclaw-kaiyi-implementation.md) - weight 5 for local audit.

## Synthesis

OpenClaw distinguishes heartbeat, cron, hooks, standing orders, tasks, and Task Flow. Hermes supports cron and webhooks with script pre-processing and delivery targets. ChatGPT workspace agents expose schedules in the ChatGPT channel and Slack channel behavior through product settings.

## Planning Rules

- Use ChatGPT schedules for repeatable timed runs.
- Use skills for the method a scheduled run should follow.
- Use apps/MCPs for the systems the scheduled run must inspect or update.
- Use write approvals for actions that send, edit, post, delete, or mutate business data.
- Keep "heartbeat-style" monitoring quiet by default: only notify when there is meaningful change.

