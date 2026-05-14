# Jira Field Contract

The PSM Ops bot writes only to the dedicated PCO Jira Service Management project.

## Project

- Project key: `PCO`
- Project name: `PCO - PSM Customer Ops`
- Source of truth: Jira Service Management

## Preconfigured Runtime Values

The live profile must configure these environment variables before the gateway is healthy:

| Purpose | Environment variable |
| --- | --- |
| Jira base URL | `JIRA_BASE_URL` |
| Jira API user email | `JIRA_EMAIL` |
| Jira API token | `JIRA_API_TOKEN` |
| PCO service desk ID | `PSM_OPS_JIRA_SERVICE_DESK_ID` |
| Slack/Jira access policy | `PSM_OPS_ACCESS_POLICY_PATH` |
| Customer Next Action request type | `PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION` |
| Onboarding Task request type | `PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK` |
| Data Hygiene request type | `PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE` |
| Handoff Package request type | `PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE` |
| Customer field | `PSM_OPS_JIRA_FIELD_CUSTOMER` |
| StaffAny Org(s) field | `PSM_OPS_JIRA_FIELD_STAFFANY_ORGS` |
| Owner PSM field | `PSM_OPS_JIRA_FIELD_OWNER_PSM` |
| Contributor CSE field | `PSM_OPS_JIRA_FIELD_CONTRIBUTOR_CSE` |
| Action type field | `PSM_OPS_JIRA_FIELD_ACTION_TYPE` |
| Risk reason field | `PSM_OPS_JIRA_FIELD_RISK_REASON` |
| Source links field | `PSM_OPS_JIRA_FIELD_SOURCE_LINKS` |
| Reminder at field | `PSM_OPS_JIRA_FIELD_REMINDER_AT` only if a separate reminder field is introduced later |
| PS Team field | `PSM_OPS_JIRA_FIELD_PS_TEAM`; in thin POC this defaults to `customfield_10876` |

Do not discover or guess these at answer time. `validate_jira_configuration` must fail closed when required values are missing.

## PS Team Routing

- Jira `PS Team` is the task-owner source of truth for "my tasks" and scoped reminders.
- Thin POC fetches Slack users, canonicalizes profile email/name, and auto-matches the caller to the configured `PS Team` option.
- Do not trust model-guessed email spelling; use Slack profile data before matching Jira.
- Use `resolve_slack_user_identity` to resolve one Slack mention, email, or exact name before asking who an abbreviated owner such as `Jo`, `Jos`, or `Josica` means.
- If no `PS Team` option matches the caller, fail closed with `Confidence: blocked`.
- `CS duty`, `cs duty`, and equivalent spelling variants mean Jira `PS Team = CS Duty`.
- `Eng duty` means Jira `PS Team = Eng Duty`.
- These are PS Team values, not Jira person assignees. Do not ask who is on duty when the user asked for `CS duty`.

## Jira Assignee

- Jira assignee is still available for explicit person-assignment requests such as `assign PCO-135 to @Alya`.
- Use `set_pco_assignee` for existing issues. Resolve the target through Slack profile data or Jira user search, then call Jira Cloud's issue assignee API.
- Do not use assignee for "my tasks", reminders, or duty routing; those remain scoped by Jira `PS Team`.

## Statuses

Allowed target statuses:

- Open
- Waiting Customer
- Waiting Internal
- Scheduled
- Done
- Cancelled

The MCP adapter must retrieve available transitions for the issue and choose the transition whose name or target status matches the requested status.

## Comment Policy

- Internal comments: allowed.
- Public customer-visible comments: blocked unless `PSM_OPS_JIRA_PUBLIC_COMMENTS_ENABLED=true`.

## Reminder Policy

- Use Jira `duedate` as the thin POC reminder source of truth.
- Automatic reminder queries include tasks due tomorrow, due today, and overdue tasks until they are Done.
- Do not store reminders in files, memory, cron prompts, Slack messages, or local databases.
