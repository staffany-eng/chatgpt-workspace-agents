# Jira Runtime

PSM Ops Bot uses Jira PCO as the PS/customer-ops task source of truth and Jira ROI as the RevOps/BD Ops/NYSS task source of truth.

## API Pattern

- List/search tasks: Jira Cloud JQL search API.
- PCO board search: Jira Cloud JQL search API with bounded passes over exact `PCO-*` keys, Slack permalink variants, and safe keyword terms; output safe issue summaries only.
- Find engineering issue candidates: Jira Cloud JQL search API, restricted to KER/SCHE and safe fields only.
- Create PCO requests: Jira Service Management request API.
- Create ROI requests: Jira Service Management request API for the configured ROI service desk and request type.
- Due date: Jira Cloud issue update API against the standard `duedate` field after request creation.
- Status transitions: Jira Cloud issue transitions API.
- Engineering and internal-team links: Jira Cloud issue link API, restricted to existing `PCO-*` issues linked to `KER-*`/`SCHE-*`, plus `ROI-*` links created only by the PCO ROI tracker primitive.
- Comments: Jira Service Management request comment API with `public=false` by default.
- Reminders and assignment hygiene: Jira JQL over active PCO issues and the standard `duedate`, Jira assignee, and `PS Team` fields. No separate reminder database or custom reminder field is required for thin POC.

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

Task creation sends only fields that exist on today's PCO request forms, including `PS Team` when matched or explicitly provided. Due date is then written to Jira's standard `duedate` field after the request is created. Customer, priority, action type, risk reason, source links, and owner metadata are written as an internal Jira comment after approved creation. The source Slack permalink is additionally written as a Jira web link (remote link titled `Slack thread`) so it shows up front rather than only inside the comment; the link is idempotent on its permalink `globalId`, so reuse of an existing thread's ticket backfills the link without duplicating it.

Task creation blocks past due dates before writing to Jira. Today is evaluated in `Asia/Singapore` by default, or `PSM_OPS_TIMEZONE` if configured. If a draft date is before today's date, ask for a corrected future due date.

Event AA channel exception: `create_ps_wee_intake_ticket` defensively strips any supplied `due_date` when the source Slack thread is in `PSM_OPS_AA_CHANNEL_ID`. AA intakes never carry a Jira `duedate` — date phrases in the trigger message are descriptive context, not deadlines, and triage owns any real deadline. The strict past-date block still applies to `create_approved_pco_task` and every non-AA caller.

Automatic reminders use `duedate` and `statusCategory != Done`. The weekday 09:00 SGT morning digest includes overdue, due-today, and due-tomorrow tasks. The weekday 17:00 SGT EOD catch-up digest includes overdue and due-today tasks so same-day follow-ups created after the morning run still surface. `set_pco_reminder` updates the issue due date because due date is the reminder source of truth in thin POC; it does not create a separate Slack-thread reminder or local reminder record.

Reminder Slack formatting is deterministic mrkdwn in the central digest only. `PSM_OPS_REMINDER_MENTION_MAP_PATH` may point to a reviewed runtime JSON map from Jira `PS Team` values to Slack user or usergroup targets, plus optional `ps_leads.Josica` for assignment hygiene lead triage. Unmapped `PS Team` values are not guessed; the digest should list them under `Mention gaps`. Missing Josica lead mapping is listed as `Lead mention gap`. When `PSM_OPS_JIRA_FIELD_SOURCE_LINKS` is configured and a source Slack permalink belongs to a reviewed channel in `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH`, the central row may include `Customer team: <#CHANNEL_ID|channel-name>`. Do not infer customer channels from summary text or customer names.

Assignment hygiene runs as a weekday 09:15 SGT no-agent cron. It uses safe Jira fields only. Active PCO issues with missing Jira assignee or missing `PS Team` are grouped under `Needs PS lead triage` for Josica. Active PCO issues with missing `duedate` and a known `PS Team` are grouped by `PS Team`, including `CS Duty`.

For portal/request-form visibility, add the field named `Due date` / field ID `duedate` to PCO request types `81` Customer Success Work, `82` Onboarding, and `83` Data Setup. The bot does not require the form field to be visible because it sets `duedate` after creation, but PSMs will see a cleaner form if Jira admins add it.

## Engineering Release Watch Pattern

For customer follow-up that is blocked by engineering shipment, keep PCO as the PS task and link it to the product/engineering issues:

- Use read-only `find_engineering_issue` when the user names a feature instead of giving an exact `KER-*` or `SCHE-*` key.
- Link `PCO-*` to `KER-*` for product context.
- Link `PCO-*` directly to the confirmed `SCHE-*` shipment tickets because `fixVersion` is expected on the shipment tickets.
- Use `Blocks` so the PCO appears blocked by the engineering issue. Use `Relates` only if the Jira site does not support `Blocks`.

Engineering issue search returns only `key`, `summary`, `status`, `issue_type`, `updated`, and URL. It must not expose raw descriptions, comments, attachments, or bulk Jira exports. Default search scope is KER; include SCHE only when the request mentions shipment, release, or SCHE.

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
- `PSM_OPS_REMINDER_MENTION_MAP_PATH` for optional central-digest PS lead and PS Team Slack mentions

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

ROI-direct is for RevOps, BD Ops, NYSS, and ROI-board requests. It does not create a duplicate PCO execution wrapper. The ROI ticket is the source of truth; the Slack thread permalink is evidence and the idempotency key.

For resolved PS Team callers, billing/invoice/renewal billing asks default to a linked PCO customer-loop tracker. The tracker is not execution truth. It is a PCO Customer Success Work issue labelled `ps-wee-roi-tracker`, linked so ROI blocks PCO, transitioned to `Waiting Internal`, and used only so PS can close the customer loop after ROI resolves the internal work.

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

## Duplicate Merge Pattern

PS WEE can merge duplicate PCO tickets on demand. Merging is on-demand and human-triggered — there is no auto pre-create dedupe.

- Discovery: `find_duplicate_pco_candidates` is read-only. Seed it with the PCO issue the user is looking at, or a query / customer / Slack thread. It returns ranked active candidates, a mergeability flag per candidate, and a `suggested_merge` (`source_issue_key` into `target_issue_key`) with a ready `merge PCO-X into PCO-Y` command.
- Suggestion direction: when a seed issue is supplied it is treated as the canonical target and candidates merge into it. Without a seed, the older (lower-numbered) ticket is the target.
- Approval gate: never call `merge_pco_tickets` from a suggestion alone. Proceed only on an explicit `merge PCO-X into PCO-Y` command or a same-thread confirmation of a prior suggestion. The explicit command itself is approval.
- Execution: `merge_pco_tickets` records the source as a duplicate of the target via a `Duplicate` issue link (Relates fallback when the site lacks the type), copies the source's validated Slack permalink web links onto the target, adds an internal merge comment to the target, and transitions the source to `Cancelled`. It never deletes the source and is idempotent — re-running detects the existing link and a cancelled source.

## Onboarding Task Creator Pattern

The standalone `psm-ops-onboarding-task-creator` skill creates or links one parent onboarding PCO issue plus child onboarding tasks.

- Planning: `plan_pco_onboarding_tasks` is read-only. It searches for the parent, for each child task regardless of whether it is already linked, and returns a proposed create/reuse/link plan.
- Approval gate: the bot must not create or link anything from the first request. Same-thread direct-mention approval is required before writes.
- Execution: `apply_pco_onboarding_task_plan` is the only public write entrypoint. It creates only parent/child rows included in the approved plan and links child rows to the parent.
- Link direction: child `implements` parent; parent is `implemented by` child.
- Existing AA PCO-to-PCO linking remains unchanged: `link_pco_to_pco_issue` always creates `Relates`.

## Tool Rules

- `validate_jira_configuration`: run in health checks and before broad enablement.
- `validate_roi_jira_configuration`: run after ROI env setup and before broad ROI enablement.
- `resolve_customer_channel_org`: safe read; resolve a Slack thread permalink to a reviewed customer-channel mapping before auto-tagging Jira `StaffAny Org(s)`.
- `resolve_slack_user_identity`: safe read; resolve one Slack mention, email, or exact name through `users.list` before asking avoidable owner questions.
- `classify_roi_ticket_request`: safe read; route actionable ROI/RevOps/BD Ops/NYSS requests to ROI when create/add/log/handle/task wording is present, and treat PS Team billing/invoice operational asks as ROI + PCO tracker candidates by default.
- `list_my_pco_tasks`: safe read, caller-scoped by Jira `PS Team`.
- `search_pco_tickets`: safe read; use before saying a current Slack thread is not tracked in PCO or not ticketed yet, or before creating a likely duplicate when same-thread lookup misses. It returns only safe issue fields and uses deterministic scoring: exact key/source matches auto-match, one strong active keyword match auto-matches, ambiguous candidates return `needs-check`, and no match returns a bounded not-found result suitable for a create-ready offer.
- `plan_pco_onboarding_tasks`: safe read; plans parent onboarding ticket reuse/create, child task reuse/create, and child-to-parent Implements links without writing to Jira.
- `apply_pco_onboarding_task_plan`: mutation; the only public write entrypoint for approved onboarding parent/child task creator plans. Requires explicit same-thread approval and creates or links only rows included in the plan.
- `find_duplicate_pco_candidates`: safe read; given a seed PCO issue key, query, customer, or Slack thread, it runs the bounded board search, excludes the seed, flags mergeable candidates by score (>=75 strong, >=60 likely-confirm, below weak), and returns a `suggested_merge` plus a `merge PCO-X into PCO-Y` command. It does not mutate anything; the bot must surface the suggestion and get approval before merging.
- `merge_pco_tickets`: mutation; merges a confirmed duplicate `PCO-X` into `PCO-Y`. It records the source as a duplicate of the target via a Jira `Duplicate` issue link (falling back to `Relates` on sites without the type), copies the source's validated Slack permalink web links onto the target, adds an internal merge comment to the target, and transitions the source to `Cancelled`. It never deletes the source and is idempotent on re-run. Requires explicit approval: a `merge PCO-X into PCO-Y` command or same-thread confirmation after a `find_duplicate_pco_candidates` suggestion.
- `find_ticket_by_slack_thread`: safe read; use the Slack thread permalink as the PS WEE idempotency key.
- `find_roi_ticket_by_slack_thread`: safe read; use the Slack thread permalink as the ROI idempotency key.
- `create_roi_ticket_from_slack`: mutation; creates direct ROI JSM tickets for actionable RevOps/BD Ops/NYSS/ROI-board requests with first-class requester, required-field checks, source Slack thread, and no duplicate PCO execution wrapper.
- `create_or_link_pco_roi_tracker`: mutation; creates or reuses one linked PCO customer-loop tracker per Slack thread for PS Team billing/invoice asks or explicit customer-loop tracking requests. It labels the PCO issue `ps-wee-roi-tracker`, links ROI as blocking PCO, and moves the PCO tracker to `Waiting Internal`.
- `create_ps_wee_intake_ticket`: mutation; creates an immediate intake ticket for explicit PS WEE ticketing requests without preview approval. The Jira internal metadata comment keeps `Source Slack thread:`, `Slack poster:`, the triggering user's `authored_request` when supplied, and concise interpreted fields only. No required fields and no needs-info label — a Slack thread permalink alone is enough.
- `append_ps_wee_ticket_update`: mutation; adds a concise structured internal comment for meaningful direct-mention Slack follow-up discussion, including `Slack poster:` when the Slack poster display name, user ID, or email is available and `authored_update` when supplied. It must not mirror untagged replies, raw Slack transcripts, or whole-thread dumps.
- These three PS WEE lifecycle tools also emit bot-owned central ops audit copies when the central Slack channel is configured. The Jira issue itself remains structured; raw-ish ops detail belongs in the private central Slack audit copy only.
- `draft_pco_task`: no mutation; includes duplicate candidates.
- `create_approved_pco_task`: mutation; requires approval marker.
- `transition_pco_task`: mutation; only configured target statuses.
- `add_internal_pco_comment`: mutation; internal comments only unless explicitly enabled.
- `set_pco_assignee`: mutation; assigns an existing PCO issue to a Jira user resolved from a Slack mention, email, or exact name. This does not change `PS Team`.
- `set_pco_ps_team`: mutation; updates only the configured Jira `PS Team` field. Treat "cs duty" as `CS Duty`, not a person assignee.
- `find_engineering_issue`: safe read; searches only allowlisted KER/SCHE Jira projects and returns safe fields only. Use it before release-watch linking when the user supplies a feature name rather than an exact engineering issue key.
- `link_pco_to_engineering_issue`: mutation; links an existing `PCO-*` issue to a `KER-*` or `SCHE-*` engineering issue. Default `Blocks` direction makes the PCO show as blocked by the engineering issue. `Relates` is allowed only as fallback when Jira lacks Blocks.
- `set_pco_reminder`: mutation; updates Jira `duedate`, which drives central 09:00 SGT and 17:00 SGT reminders.
- `list_due_pco_reminders`: safe read for cron and user checks; user-scoped checks filter by Jira `PS Team`.

## Failure Behavior

Return `Confidence: blocked` when Jira credentials, request types, caller lookup, due-date update, or transitions are unavailable. Do not silently fall back to local state.
