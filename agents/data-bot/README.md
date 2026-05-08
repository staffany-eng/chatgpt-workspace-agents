# Data Bot

> Deprecated: this is a historical ChatGPT Agent Studio packet. The canonical StaffAny data-bot app is now `apps/hermes-data-bot/`.

Local source-controlled snapshot of the ChatGPT Agent Studio agent named `Da Ta Bot`.

- Agent Studio URL: `https://chatgpt.com/agents/studio/edit/agt_69f311eb8c688191ac24e5edeb038967`
- Previous captured agent URL: `https://chatgpt.com/agents/studio/edit/agt_69f1bae700648191895541694209d4ac`
- Latest local version: `versions/2026-04-30T090405Z`
- Purpose: StaffAny internal data analyst agent for BigQuery warehouse questions, Pantheon/GitHub context checks, Slack forwarded-thread context, and confirmed memory learning.
- BigQuery MCP setup runbook: `bigquery-mcp-setup.md`

## Versioning Rule

Every time the Agent Studio bot is changed, create a new folder under `versions/` instead of editing older snapshots in place. Older versions are evidence, not scratch space.

## Restore Order

1. Apply `instructions.md` to the Agent Studio instructions field.
2. Configure `surface-map.md`, especially BigQuery MCP and GitHub. Use `bigquery-mcp-setup.md` to recreate the BigQuery connector.
3. Upload files from `files/`.
4. Upload skills from `skills/`.
5. Recreate channels and memory behavior from `surface-map.md`.
6. Run the preview tests listed in the skill and uploaded file.
