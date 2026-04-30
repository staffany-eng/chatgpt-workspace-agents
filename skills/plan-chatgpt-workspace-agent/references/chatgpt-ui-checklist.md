# ChatGPT UI Checklist

Use this as a manual checklist for the ChatGPT agent builder. Product behavior can change, so verify against official OpenAI docs before production changes.

Official docs checked for this skill:

- https://help.openai.com/en/articles/20001143-chatgpt-workspace-agents-for-enterprise-and-business
- https://help.openai.com/en/articles/20001066-skills-in-chatgpt

## Create A Workspace Agent

1. Open ChatGPT.
2. Open `Agents` from the left sidebar.
3. Select `Create`, or browse templates and select `Use template`.
4. Enter a prompt describing the target workflow, or select `Start blank` / `Skip to builder` when available.
5. Review the draft plan.
6. Select `Build this agent`.
7. In the agent builder, configure instructions, tools/apps/MCPs, skills, files, memory, channels, access, appearance, and starter prompts.
8. Select `Preview`.
9. Run the planned preview tests.
10. Select `Create` only after tests pass.

## Update A Workspace Agent

1. Open the existing agent from ChatGPT or the `Agents` page.
2. Select `Edit agent`.
3. Apply the change packet section by section.
4. Select `Preview`.
5. Run regression prompts and risk prompts.
6. Select `Update` to save the live agent changes.
7. Check version history after major updates.

## Browser-Assisted Application

- Use Browser Use only when the user explicitly asks Codex to apply the packet in ChatGPT.
- Open ChatGPT and use the visible UI; do not rely on undocumented APIs or hidden endpoints.
- Paste or select only values from the approved change packet.
- Pause for explicit confirmation before final actions: `Create`, `Update`, `Publish`, `Add schedule`, `Connect Slack`, `Delete`, or equivalent.
- Verify the visible UI state after each major section and after the final saved action.
- If login, admin permission, workspace availability, or UI drift blocks the flow, stop and report the blocker plus the last safe manual step.

## Add Tools, Apps, Custom MCPs, Skills, And Files

- Use the `Tools` section to add apps, custom MCPs, and built-in tools, such as Google Drive, Google Sheets, Slack, Calendar, SharePoint, web search, or image generation when enabled in the workspace.
- Choose auth type per app connection: end-user account or agent-owned account.
- Use the `Skills` section to create a skill, upload a skill file, or select an available skill.
- Use the `Files` section to upload durable reference files.
- Keep app scopes and uploaded files to the minimum needed for the workflow.

## Manage Access And Channels

- Use the ChatGPT channel settings to set access: private, link-shared inside the organization, or organization directory publishing.
- Add a short description, starter prompts, and appearance details in the ChatGPT channel settings.
- Use `Add schedule` to configure timed runs; keep schedule instructions narrow and output-specific.
- Use `Add channel` / Slack connection only when the agent and all needed app connections are safe for shared use.

## Slack-Specific Checks

- Ensure the Slack bot for ChatGPT Agents is enabled by admins when required.
- Use shared or agent-owned connections for app access needed in Slack.
- Avoid personal shared auth unless the risk is understood and accepted.
- Choose whether the agent responds to every channel message or only mentions.
- Add Slack channel instructions distinct from base agent instructions.

## Risk Checks Before Create Or Update

- Publishing to the organization directory broadens access.
- Agent-owned auth can let other users act through shared credentials.
- Slack channels can expose app data to all channel participants.
- Schedules can repeatedly perform actions without fresh user context.
- Disabling write confirmations can send, edit, post, delete, or mutate data without a per-run approval.
- Deleting an agent is permanent.
