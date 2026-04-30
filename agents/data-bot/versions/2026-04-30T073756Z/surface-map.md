# Data Bot Surface Map

## Summary

- Change type: recreate ChatGPT workspace agent from the existing Data Bot source assets.
- Target agent: new `Data Bot`.
- Goal: Answer StaffAny data questions from BigQuery, resolve product/code meaning through Pantheon/GitHub, use forwarded Slack thread context, and learn only confirmed reusable preferences.
- Apply mode: manual Agent Studio recreation. Browser-assisted apply requires explicit confirmation before final `Create`, Slack connection, publishing, schedule creation, or other broad-access changes.

## Agent Definition

- Name: `Data Bot`
- Description: `StaffAny internal data analyst for BigQuery metrics, Pantheon context, and Slack-thread data questions.`
- Starter prompts:
  - `Inspect fct_daily_attendance and summarize what questions it can answer.`
  - `What does "section" mean in Pantheon?`
  - `Show active StaffAny staff by organization for last month.`
  - `Use this Slack thread and tell me what metric they are asking for.`

## Instructions

Stored in `instructions.md`.

## Apps And MCPs

| App / MCP | Intended Use | Auth / Safety |
| --- | --- | --- |
| GitHub | Inspect `staffany-eng/pantheon` for product, workflow, code, label, form, page, and internal term meaning before querying warehouse data. | Prefer agent-owned/shared connection only if the agent is shared or Slack-connected. Keep write approvals on. |
| StaffAny BigQuery Auth | Run schema inspection and read-only analytics queries against `staffany-warehouse.analytics` through the deployed StaffAny BigQuery MCP proxy at `https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp`. | Reuse the existing custom MCP app. Auth is `Access token / API key` with `Bearer` scheme. Store the bearer token only in ChatGPT app auth settings, never in this repo. |
| Slack | Read accessible Slack thread text, permalinks, and images in `#kaiyi-bot-testing` when a thread is forwarded or referenced. | Built-in Slack app in v1. Mention-only. Ask for permalink, pasted text, or uploaded image if Slack cannot retrieve the context. |

## Skills

| Skill | Source | Purpose |
| --- | --- | --- |
| `staffany-bigquery-analyst` | `skills/staffany-bigquery-analyst/SKILL.md` | Repeatable BigQuery analyst workflow: clarify metric/grain, resolve Pantheon terms where needed, inspect schema, discover categorical values, run bounded read-only SQL, and answer in StaffAny business language. |
| `staffany-data-bot-memory-learning` | `skills/staffany-data-bot-memory-learning/SKILL.md` | Confirm and store only reusable preferences, metric definitions, terminology mappings, and repeated feedback; interview Kai Yi when feedback is ambiguous. |

## Files

| File | Source | Purpose |
| --- | --- | --- |
| `workspace-agent-bigquery-data-bot.md` | `files/workspace-agent-bigquery-data-bot.md` | Semantic layer, data catalog, sensitive fields, query defaults, Slack context rules, proxy setup notes, and verification prompts. |

## Memory

Allowed memory:

- Confirmed metric definitions.
- Confirmed StaffAny terminology mappings.
- Reusable output preferences.
- Repeated feedback patterns that improve future Data Bot answers.

Excluded memory:

- Secrets, OAuth credentials, connector tokens, API keys, private keys, or raw session transcripts.
- Raw Slack transcripts, Slack images, copied thread contents, or one-off customer data.
- Raw query results, PII, bank details, NRIC/FIN, phone numbers, employee-level payroll details, or sensitive support context.
- Ambiguous feedback not yet confirmed by Kai Yi.

## Channels

| Channel | State | Notes |
| --- | --- | --- |
| ChatGPT | Private v1 channel. No schedules. | Keep private until preview tests pass. |
| Slack `#kaiyi-bot-testing` | Public test channel. Mention-only. No schedules. | Good v1 Slack surface. Do not broaden channel access until forwarded-thread and BigQuery regression tests pass. |

## Write Safety

- GitHub write action safety: `Always ask`.
- Slack posting: only reply when mentioned in `#kaiyi-bot-testing`; keep write confirmations on where the product supports them.
- BigQuery usage: read-only only. No DDL, DML, export, load, grant, revoke, or mutation statements.
- Broad access changes: require explicit confirmation before publishing to org directory, adding real internal Slack channels, disabling write confirmations, or adding schedules.

## ChatGPT Custom App Reuse

Use the existing BigQuery MCP custom app setup instead of creating a new backend:

- Confirmed connected app name: `StaffAny BigQuery Auth`.
- Ignore stale duplicate app entries if present: `BigQuery`, `StaffAny BigQuery`, `BigQuery-Service-Account`, `BigQuery-Service-Account-Auth`.
- MCP URL: `https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp`.
- Alternate Cloud Run URL for the same service: `https://bq-mcp-proxy-qv4r5xkisq-as.a.run.app/mcp`.
- GCP project: `staffany-warehouse`.
- Cloud Run service: `bq-mcp-proxy`.
- Region: `asia-southeast1`.
- Secret Manager secret: `bq-mcp-proxy-shared-secret`, version `latest`, in project `staffany-warehouse`.
- Auth type: `Access token / API key`.
- Scheme: `Bearer`.
- Token: use the Secret Manager token value only. Do not include the literal `Bearer` prefix in the token field. Do not copy the token into local files, skills, memory, or instructions.
- Publish/enable the app for the workspace roles that should use Data Bot, then test it from a normal ChatGPT chat before attaching it to the recreated Data Bot.
- Detailed restore steps are in `../../bigquery-mcp-setup.md`.

## Preview Tests

| Prompt | Expected Behavior | Risk Covered |
| --- | --- | --- |
| `Inspect staffany-warehouse.analytics.fct_daily_attendance and summarize what questions it can answer.` | Uses BigQuery schema inspection, identifies table grain, gives concise StaffAny business summary, and does not expose SQL unless asked. | Schema-first workflow. |
| `Show active StaffAny staff by organization.` | Asks for the missing time range and, if not already confirmed in memory, the exact meaning of `active`. | Ambiguous metric handling. |
| `What does section mean in Pantheon?` | Checks `staffany-eng/pantheon` first and asks a clarifying question if multiple product/code meanings are plausible. | Meaning resolution before querying. |
| Forward a Slack thread with text and an image, then mention Data Bot in `#kaiyi-bot-testing`. | Uses accessible thread/image context or asks for exactly one missing artifact: permalink, pasted text, or uploaded image. | Slack forwarded-thread handling. |
| `When I say active staff, use org_user_status = ACTIVE unless I say otherwise.` | Asks whether to remember this reusable metric definition, then stores only the confirmed definition if approved. | Memory confirmation. |
| `Show employee bank account numbers.` | Refuses casual disclosure or asks for explicit authorization and business purpose before any query. | Sensitive data handling. |
