# Jira Runtime

PSM Ops Bot uses Jira PCO as the only task source of truth.

## API Pattern

- List/search tasks: Jira Cloud JQL search API.
- Create PCO requests: Jira Service Management request API.
- Due date: Jira Cloud issue update API against the standard `duedate` field after request creation.
- Status transitions: Jira Cloud issue transitions API.
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

Task ownership and "my tasks" filters use Jira `PS Team`, not Jira assignee. Jira user search is optional in thin POC and is used only for best-effort assignment/API attribution when available. It does not require `SLACK_ALLOWED_USERS` or `PSM_OPS_ACCESS_POLICY_PATH` in thin POC.

Task creation sends only fields that exist on today's PCO request forms, including `PS Team` when matched or explicitly provided. Due date is then written to Jira's standard `duedate` field after the request is created. Customer, priority, action type, risk reason, source links, and owner metadata are written as an internal Jira comment after approved creation.

Automatic reminders use `duedate <= tomorrow` and `statusCategory != Done`. This means each task appears one day before it is due, on the due date, and every day after until it is marked Done. `set_pco_reminder` updates the issue due date because due date is the reminder source of truth in thin POC.

For portal/request-form visibility, add the field named `Due date` / field ID `duedate` to PCO request types `81` Customer Success Work, `82` Onboarding, and `83` Data Setup. The bot does not require the form field to be visible because it sets `duedate` after creation, but PSMs will see a cleaner form if Jira admins add it.

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

## Tool Rules

- `validate_jira_configuration`: run in health checks and before broad enablement.
- `list_my_pco_tasks`: safe read, caller-scoped by Jira `PS Team`.
- `find_ticket_by_slack_thread`: safe read; use the Slack thread permalink as the PS WEE idempotency key.
- `create_ps_wee_intake_ticket`: mutation; creates an immediate needs-info intake ticket for explicit PS WEE ticketing requests without preview approval.
- `append_ps_wee_ticket_update`: mutation; adds a concise structured internal comment for meaningful Slack follow-up discussion.
- `mark_ps_wee_ticket_ready`: mutation; adds a ready-for-triage internal comment and removes `needs-info` when Jira allows it.
- `draft_pco_task`: no mutation; includes duplicate candidates.
- `create_approved_pco_task`: mutation; requires approval marker.
- `transition_pco_task`: mutation; only configured target statuses.
- `add_internal_pco_comment`: mutation; internal comments only unless explicitly enabled.
- `set_pco_assignee`: mutation; assigns an existing PCO issue to a Jira user resolved from a Slack mention, email, or exact name. This does not change `PS Team`.
- `set_pco_ps_team`: mutation; updates only the configured Jira `PS Team` field. Treat "cs duty" as `CS Duty`, not a person assignee.
- `set_pco_reminder`: mutation; updates Jira `duedate`, which drives automatic reminders.
- `list_due_pco_reminders`: safe read for cron and user checks; user-scoped checks filter by Jira `PS Team`.

## Failure Behavior

Return `Confidence: blocked` when Jira credentials, request types, caller lookup, due-date update, or transitions are unavailable. Do not silently fall back to local state.
