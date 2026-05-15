# Jira Runtime

PSM Ops Bot uses Jira PCO as the PS/customer-ops task source of truth and Jira ROI as the RevOps/BD Ops/NYSS task source of truth.

## API Pattern

- List/search tasks: Jira Cloud JQL search API.
- Create PCO requests: Jira Service Management request API.
- Create ROI requests: Jira Service Management request API for the configured ROI service desk and request type.
- Due date: Jira Cloud issue update API against the standard `duedate` field after request creation.
- Status transitions: Jira Cloud issue transitions API.
- Engineering links: Jira Cloud issue link API, restricted to existing `PCO-*` issues linked to `KER-*` or `SCHE-*`.
- Comments: Jira Service Management request comment API with `public=false` by default.
- Reminders: Jira JQL over the standard `duedate` field. No separate reminder database or custom reminder field is required for thin POC.

## Thin POC Runtime Config

Thin POC mode is enabled with:

- `PSM_OPS_JIRA_MODE=thin_poc`

It uses the current PCO setup discovered on 2026-05-13:

- `PSM_OPS_JIRA_SERVICE_DESK_ID=70`
- Customer Next Action: request type `81` / Customer Success Work
- Onboarding Task: request type `82` / Onboarding
- Data Hygiene: request type `83` / Data Setup
- Handoff Package: disabled until a PCO request type exists
- StaffAny Org(s): `customfield_10667`
- PS Team: `customfield_10876`
- Due date: standard Jira field `duedate`

Required env vars in thin POC:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `CUSTOMER360_INTERNAL_API_TOKEN`
- `SLACK_BOT_TOKEN` for Slack `users.list` identity matching

The bot resolves the caller by fetching Slack users, canonicalizing the caller's Slack profile email/name, and matching that identity to the Jira `PS Team` option. It must not trust model-guessed email spelling. For example, `kai.yi@staffany.com` can be canonicalized to the Slack profile email `kaiyi@staffany.com`, then matched to the `PS Team` option `Kai Yi`.

MCP tool parameters named `slack_user_email` accept a Slack sender user ID, Slack mention, or Slack profile email. In Slack gateway requests, pass the current sender ID/mention when email is not already present. Do not ask the user to type their email before creating, listing, or updating PCO work.

Task ownership and "my tasks" filters use Jira `PS Team`, not Jira assignee. Jira user search is optional in thin POC and is used only for best-effort assignment/API attribution when available. It does not require `SLACK_ALLOWED_USERS` or `PSM_OPS_ACCESS_POLICY_PATH` in thin POC.

Task creation sends only fields that exist on today's PCO request forms, including `PS Team` when matched or explicitly provided. Due date is then written to Jira's standard `duedate` field after the request is created. Customer, priority, action type, risk reason, source links, and owner metadata are written as an internal Jira comment after approved creation.

Task creation blocks past due dates before writing to Jira. Today is evaluated in `Asia/Singapore` by default, or `PSM_OPS_TIMEZONE` if configured. If a draft date is before today's date, ask for a corrected future due date.

Automatic reminders use `duedate` and `statusCategory != Done`. The 09:00 SGT morning digest includes overdue, due-today, and due-tomorrow tasks. The 17:00 SGT EOD catch-up digest includes overdue and due-today tasks so same-day follow-ups created after the morning run still surface. `set_pco_reminder` updates the issue due date because due date is the reminder source of truth in thin POC; it does not create a separate Slack-thread reminder or local reminder record.

Reminder Slack formatting is deterministic mrkdwn in the central digest only. `PSM_OPS_REMINDER_MENTION_MAP_PATH` may point to a reviewed runtime JSON map from Jira `PS Team` values to Slack user or usergroup targets. Unmapped `PS Team` values are not guessed; the digest should list them under `Mention gaps`. When `PSM_OPS_JIRA_FIELD_SOURCE_LINKS` is configured and a source Slack permalink belongs to a reviewed channel in `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH`, the central row may include `Customer team: <#CHANNEL_ID|channel-name>`. Do not infer customer channels from summary text or customer names.

For portal/request-form visibility, add the field named `Due date` / field ID `duedate` to PCO request types `81` Customer Success Work, `82` Onboarding, and `83` Data Setup. The bot does not require the form field to be visible because it sets `duedate` after creation, but PSMs will see a cleaner form if Jira admins add it.

## Engineering Release Watch Pattern

For customer follow-up that is blocked by engineering shipment, keep PCO as the PS task and link it to the product/engineering issues:

- Link `PCO-*` to `KER-*` for product context.
- Link `PCO-*` directly to the confirmed `SCHE-*` shipment tickets because `fixVersion` is expected on the shipment tickets.
- Use `Blocks` so the PCO appears blocked by the engineering issue. Use `Relates` only if the Jira site does not support `Blocks`.

Recommended Jira Automation for a specific watch ticket:

```text
Trigger: scheduled daily, 09:00 Asia/Singapore
Lookup issues JQL:
project = SCHE
AND issue in linkedIssues("PCO-XXX")
AND statusCategory = Done
AND fixVersion in releasedVersions()

PCO condition:
key = PCO-XXX
AND status = "Waiting Internal"

Actions:
- add internal comment listing released linked SCHE tickets and fixVersions
- transition PCO to Open
- set duedate to today
```

Do not use Slack or the Release Checklist as the primary shipped signal. The Release Checklist is version-level supporting evidence after `fixVersion` identifies the release.

## Full Runtime Config

All full-contract IDs are preconfigured. The bot must not guess field IDs or request type IDs from user text.

Required env vars:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `PSM_OPS_JIRA_SERVICE_DESK_ID`
- `PSM_OPS_ACCESS_POLICY_PATH`
- `PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION`
- `PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK`
- `PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE`
- `PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE`
- `PSM_OPS_JIRA_FIELD_CUSTOMER`
- `PSM_OPS_JIRA_FIELD_STAFFANY_ORGS`
- `PSM_OPS_JIRA_FIELD_OWNER_PSM`
- `PSM_OPS_JIRA_FIELD_CONTRIBUTOR_CSE`
- `PSM_OPS_JIRA_FIELD_ACTION_TYPE`
- `PSM_OPS_JIRA_FIELD_RISK_REASON`
- `PSM_OPS_JIRA_FIELD_SOURCE_LINKS`
- `PSM_OPS_JIRA_FIELD_REMINDER_AT` if a separate reminder field is introduced later
- `PSM_OPS_REMINDER_MENTION_MAP_PATH` for optional central-digest PS Team Slack mentions

The access policy file maps Slack email to Jira account ID:

```json
{
  "users": [
    {
      "slack_email": "psm@example.com",
      "jira_account_id": "account-id",
      "ps_team": "PS Team option value",
      "display_name": "PSM Name",
      "active": true
    }
  ]
}
```

## ROI Direct Runtime Config

ROI-direct is for RevOps, BD Ops, NYSS, and ROI-board requests. It does not create a PCO wrapper ticket. The ROI ticket is the source of truth; the Slack thread permalink is evidence and the idempotency key.

Required env vars:

- `PSM_OPS_ROI_JIRA_PROJECT_KEY`
- `PSM_OPS_ROI_JIRA_SERVICE_DESK_ID`
- `PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID`

Optional but recommended field env vars:

- `PSM_OPS_ROI_JIRA_FIELD_CUSTOMER`
- `PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS`
- `PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY`
- `PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS`
- `PSM_OPS_ROI_JIRA_FIELD_REQUESTER`
- `PSM_OPS_ROI_JIRA_FIELD_REQUESTER_SLACK`
- `PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL`
- `PSM_OPS_ROI_JIRA_FIELD_PRIORITY`

`validate_roi_jira_configuration` reads the JSM request-type metadata at runtime. If required fields cannot be mapped deterministically, or multiple request types/field mappings are configured, the adapter fails closed.

Requester rules:

- Explicit `requested by` / `reported by` wins.
- Otherwise the current Slack sender is requester.
- Resolve requester through Slack identity and Jira account mapping before creation.
- No bot, team, or `team@staffany.com` requester fallback is allowed.
- Unresolved requester blocks creation and asks for the missing requester only.

Field rules:

- Fill deterministic fields only: requester, customer/org, StaffAny Organization object, request category, summary/title, details/context, source Slack thread, original channel, and priority/urgency when stated.
- For ROI, fill both the text `Company Name` field and the object-backed `StaffAny Organization` field when the request type exposes both. A valid ticket with only `Company Name` is lower-quality because the board loses the clickable StaffAny org object.
- If the ROI form uses a required `Urgent?` Yes/No field and the Slack request does not state urgency, use `No`; do not send `Normal`, `Medium`, or a boolean for that field.
- If the ROI form requires priority and has a `Medium` or `Normal` option, the adapter may use that as the default.
- If any required field remains missing, `create_roi_ticket_from_slack` blocks with exact missing field names and does not write to Jira.

## Tool Rules

- `validate_jira_configuration`: run in health checks and before broad enablement.
- `validate_roi_jira_configuration`: run after ROI env setup and before broad ROI enablement.
- `resolve_customer_channel_org`: safe read; resolve a Slack thread permalink to a reviewed customer-channel mapping before auto-tagging Jira `StaffAny Org(s)`.
- `resolve_slack_user_identity`: safe read; resolve one Slack mention, email, or exact name through `users.list` before asking avoidable owner questions.
- `classify_roi_ticket_request`: safe read; route actionable ROI/RevOps/BD Ops/NYSS requests to ROI only when create/add/log/handle/task wording is present.
- `list_my_pco_tasks`: safe read, caller-scoped by Jira `PS Team`.
- `find_ticket_by_slack_thread`: safe read; use the Slack thread permalink as the PS WEE idempotency key.
- `find_roi_ticket_by_slack_thread`: safe read; use the Slack thread permalink as the ROI idempotency key.
- `create_roi_ticket_from_slack`: mutation; creates direct ROI JSM tickets for actionable RevOps/BD Ops/NYSS/ROI-board requests with first-class requester, required-field checks, source Slack thread, and no PCO wrapper.
- `create_ps_wee_intake_ticket`: mutation; creates an immediate needs-info intake ticket for explicit PS WEE ticketing requests without preview approval.
- `append_ps_wee_ticket_update`: mutation; adds a concise structured internal comment for meaningful Slack follow-up discussion, including `Slack poster:` when the Slack poster display name, user ID, or email is available.
- `mark_ps_wee_ticket_ready`: mutation; adds a ready-for-triage internal comment and removes `needs-info` when Jira allows it.
- These three PS WEE lifecycle tools also emit bot-owned central ops audit copies when the central Slack channel is configured. The Jira issue itself remains structured; raw-ish ops detail belongs in the private central Slack audit copy only.
- `draft_pco_task`: no mutation; includes duplicate candidates.
- `create_approved_pco_task`: mutation; requires approval marker.
- `transition_pco_task`: mutation; only configured target statuses.
- `add_internal_pco_comment`: mutation; internal comments only unless explicitly enabled.
- `set_pco_assignee`: mutation; assigns an existing PCO issue to a Jira user resolved from a Slack mention, email, or exact name. This does not change `PS Team`.
- `set_pco_ps_team`: mutation; updates only the configured Jira `PS Team` field. Treat "cs duty" as `CS Duty`, not a person assignee.
- `link_pco_to_engineering_issue`: mutation; links an existing `PCO-*` issue to a `KER-*` or `SCHE-*` engineering issue. Default `Blocks` direction makes the PCO show as blocked by the engineering issue. `Relates` is allowed only as fallback when Jira lacks Blocks.
- `set_pco_reminder`: mutation; updates Jira `duedate`, which drives central 09:00 SGT and 17:00 SGT reminders.
- `list_due_pco_reminders`: safe read for cron and user checks; user-scoped checks filter by Jira `PS Team`.

## Failure Behavior

Return `Confidence: blocked` when Jira credentials, request types, caller lookup, due-date update, or transitions are unavailable. Do not silently fall back to local state.
