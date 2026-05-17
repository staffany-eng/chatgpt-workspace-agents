# Jira Field Contract

The PSM Ops bot writes PS/customer-ops work to PCO Jira Service Management and RevOps/BD Ops/NYSS work directly to ROI Jira Service Management.

## Project

- Project key: `PCO`
- Project name: `PCO - PSM Customer Ops`
- Source of truth: Jira Service Management

## ROI Direct Project

- Project key: configured by `PSM_OPS_ROI_JIRA_PROJECT_KEY`
- Source of truth: Jira Service Management ROI board
- Idempotency key: source Slack thread permalink
- No duplicate PCO execution wrapper for ROI-direct work
- Linked PCO customer-loop tracker: allowed for PS-facing customer follow-up visibility, default for resolved PS Team billing/invoice asks, label `ps-wee-roi-tracker`, status `Waiting Internal`

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
| ROI project key | `PSM_OPS_ROI_JIRA_PROJECT_KEY` |
| ROI service desk ID | `PSM_OPS_ROI_JIRA_SERVICE_DESK_ID` |
| ROI request type ID | `PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID` |
| ROI customer/org field | `PSM_OPS_ROI_JIRA_FIELD_CUSTOMER` |
| ROI StaffAny Organization object field | `PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS` |
| ROI request category field | `PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY` |
| ROI source links field | `PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS` |
| ROI requester field | `PSM_OPS_ROI_JIRA_FIELD_REQUESTER` |
| ROI requester Slack field | `PSM_OPS_ROI_JIRA_FIELD_REQUESTER_SLACK` |
| ROI original channel field | `PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL` |
| ROI priority/urgency field | `PSM_OPS_ROI_JIRA_FIELD_PRIORITY` |

Do not guess these environment-configured IDs at answer time. `validate_jira_configuration` must fail closed when required PCO values are missing.

For ROI, `validate_roi_jira_configuration` must discover required request fields from JSM request-type metadata at runtime. If a required field cannot be mapped deterministically, or if multiple ROI request types / ambiguous field mappings are configured, fail closed.

ROI ticket quality requires the text company/customer field and the object-backed StaffAny Organization field when the request type exposes both fields. Do not treat `Company Name` alone as enough when Jira shows an empty `StaffAny Organization` object slot.

ROI requester is mandatory. Explicit `requested by` / `reported by` wins; otherwise use the current Slack sender. Do not fall back to a bot, team, or `team@staffany.com` requester.

For ROI urgency fields, match the field's configured options exactly. If the required field is `Urgent?` with Yes/No options and the Slack request does not state urgency, use `No`; do not send `Normal`, `Medium`, or boolean values.

## PS Team Routing

- Jira `PS Team` is the task-owner source of truth for "my tasks" and scoped reminders.
- Thin POC fetches Slack users, canonicalizes profile email/name, and auto-matches the caller to the configured `PS Team` option.
- Do not trust model-guessed email spelling; use Slack profile data before matching Jira.
- Use `resolve_slack_user_identity` to resolve one Slack mention, email, or exact name before asking who an abbreviated owner such as `Jo`, `Jos`, or `Josica` means.
- If no `PS Team` option matches the caller, fail closed with `Confidence: blocked`.
- `CS duty`, `cs duty`, and equivalent spelling variants mean Jira `PS Team = CS Duty`.
- `Eng duty` means Jira `PS Team = Eng Duty`.
- These are PS Team values, not Jira person assignees. Do not ask who is on duty when the user asked for `CS duty`.

## Customer Channel Routing

- `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH` points to the reviewed Slack channel map in runtime/profile storage.
- Each reviewed mapping must include `channel_id`, `channel_name`, `customer_key`, `customer_name`, `staffany_orgs`, and `status=reviewed`.
- Use `resolve_customer_channel_org` for customer-specific Slack channels before creating a PS WEE intake ticket.
- If the message names a different customer from the reviewed channel mapping, fail closed and ask for confirmation before creating the ticket.
- Unmapped general Slack channels keep the existing needs-info intake behavior.

## Jira Assignee

- Jira assignee is still available for explicit person-assignment requests such as `assign PCO-135 to @Alya`.
- Use `set_pco_assignee` for existing issues. Resolve the target through Slack profile data or Jira user search, then call Jira Cloud's issue assignee API.
- Do not use assignee for "my tasks", reminders, or duty routing; those remain scoped by Jira `PS Team`.
- The assignment hygiene cron treats missing Jira assignee as a PS lead triage gap, not as task ownership truth.

## Engineering Issue Links

- Use `find_engineering_issue` for natural-language KER/SCHE lookup before linking. Search only allowlisted `KER` and `SCHE` projects and return only key, summary, status, issue type, updated timestamp, and URL.
- Use `link_pco_to_engineering_issue` only for existing `PCO-*` issues that need release tracking against `KER-*` or `SCHE-*`.
- Default link type is `Blocks`; the tool creates the link so the PCO shows as blocked by the engineering issue.
- `Relates` is allowed as a fallback only when Jira does not support the standard Blocks link type.
- Reject non-PCO source issues and non-KER/non-SCHE targets.
- Do not expose raw engineering issue descriptions, comments, attachments, or Jira bulk exports.

## ROI Customer-Loop Tracker Links

- Use `create_or_link_pco_roi_tracker` only after an ROI ticket has been created or reused.
- The PCO tracker must be a Customer Success Work issue, labelled `ps-wee-roi-tracker`, linked so the ROI issue blocks the PCO issue, and transitioned to `Waiting Internal`.
- The Slack thread permalink is the idempotency key for the PCO tracker. Reuse an existing same-thread `ps-wee-roi-tracker` issue instead of creating duplicates.
- ROI remains execution source of truth. The PCO tracker exists only so PS can see pending billing/internal-team work and close the customer loop.

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
- The weekday 09:00 SGT central digest queries tasks due tomorrow, due today, and overdue tasks until they are Done.
- The weekday 17:00 SGT EOD catch-up digest queries due-today and overdue tasks until they are Done.
- The weekday 09:15 SGT assignment hygiene digest queries active PCO issues missing Jira assignee, `PS Team`, or `duedate`.
- Missing assignee or missing `PS Team` appears under `Needs PS lead triage` for Josica. Missing `duedate` with a known `PS Team` appears under that `PS Team`, including `CS Duty`.
- Do not store reminders in files, memory, cron prompts, Slack messages, or local databases.
