# PSM Ops Bot Regression Cases

## Own Tasks

`@PSM Ops show my overdue PCO tasks`

- Fetches Slack users and canonicalizes profile email/name before matching the caller to Jira `PS Team`.
- Calls `list_my_pco_tasks`.
- Queries Jira by `PS Team`, not assignee.
- Shows safe issue summaries only.

## Create Task

`@PSM Ops create task for Fei Siong to confirm payroll readiness by Friday`

- Resolves customer through C360.
- Passes the current Slack sender ID/mention into Jira tools when email is not already present.
- Does not ask the user for Slack/Jira email before drafting or creating.
- Calls `draft_pco_task`.
- Shows a preview and waits for `create`.
- Calls `create_approved_pco_task` only after approval.
- Blocks creation if the resolved due date is before today's date.

## PS WEE Ticket First

`@PSM Ops create ticket for Fei Siong payroll readiness, info not complete yet`

- Treats PS WEE as the existing PSM Ops Bot.
- Calls `find_ticket_by_slack_thread`.
- Creates the PCO intake ticket immediately with `create_ps_wee_intake_ticket` when no same-thread ticket exists.
- Includes the Slack thread permalink in Jira.

## PS WEE Compact Missing Info

Thread:

`Can you help advise on the workaround if Tomoro Coffee is unable to add a new staff in HRAny using a phone number that has already been used in another organization? The same phone number is linked to affected staff HUI SHAN WENG in inactive I LOVE TAIMEI.`
`@PSM Ops please create a ticket for CS to follow up regarding Tomoro Coffee unable to add staff in HRAny.`

- Creates or reuses the PCO intake ticket first.
- Passes known customer, issue details, affected staff/profile, and workaround context into `create_ps_wee_intake_ticket`.
- Does not ask for customer/org or issue details again.
- Does not add a numbered questionnaire after the tool reply.
- Slack-facing missing info is capped at two fields; full needs-info metadata may stay in Jira/audit.

## PS WEE Customer Channel Auto-Tag

Expected:

- Customer-specific Slack channels use reviewed channel mappings only.
- `create_ps_wee_intake_ticket` auto-fills customer and `StaffAny Org(s)` from the Slack thread channel.
- Conflicting message customer vs mapped channel customer blocks before Jira creation.
- Unmapped general channels still create a needs-info intake without org auto-tagging.
- Posts the ticket link in-thread and asks for missing info.
- Posts a bot-owned `PSM Ops automation:` central audit copy with the source Slack thread permalink.

## PS WEE ROI Direct

`@PS Wee Manager create a task for bd ops to send Dreamus invoice`

- Treats PS Wee Manager as the existing PSM Ops Bot.
- Calls `classify_roi_ticket_request` and detects actionable BD Ops / invoice work.
- Calls `find_roi_ticket_by_slack_thread` using the current Slack thread permalink.
- Creates a direct ROI ticket with `create_roi_ticket_from_slack` when no same-thread ROI ticket exists.
- Does not create a duplicate PCO execution wrapper.
- Resolves requester from explicit `requested by` / `reported by` first, otherwise the Slack sender.
- Blocks creation if requester cannot resolve; no bot or `team@staffany.com` requester fallback.
- Discovers required ROI request fields from JSM metadata and blocks with exact missing field names if customer/org, category, requester, summary/details, source thread, or other required fields are missing.
- Fills both `Company Name` and `StaffAny Organization` when the ROI request type exposes both fields.
- Includes source Slack thread, original channel, and requester in the ROI payload or internal metadata.

## PS WEE Billing ROI Tracker By Default

`@PS Wee Manager Dreamus renewal invoice has MRR mismatch`

- Treats the caller as trackable only after resolving the Slack sender to a Jira `PS Team`.
- Calls `classify_roi_ticket_request` and returns `pco_tracker_default=true` for billing/invoice/MRR terms even without "track this" wording.
- Calls `find_roi_ticket_by_slack_thread` and creates or reuses ROI through `create_roi_ticket_from_slack`.
- Calls `create_or_link_pco_roi_tracker` after ROI create/reuse.
- The PCO tracker is a Customer Success Work issue, labelled `ps-wee-roi-tracker`, linked so ROI blocks PCO, and moved to `Waiting Internal`.
- Caveat says ROI is source of truth and PCO is only the customer-loop tracker.

## PS WEE Casual NYSS Question

`@PS Wee Manager @nyss what is the Stripe password?`

- Does not create ROI.
- Does not create PCO.
- Requires create/add/log/handle/ticket/task/board wording before ROI ticket creation.

## PS WEE Task List Plus Calendar

Thread:

`@Josica we need to discuss a process upgrade where any change requests from customers need to funnel through a particular team, esp for big customers. @PSM Ops help to add to jos and find a good meeting timing for this`
`@PSM Ops help to add to jos task list, and find a good meeting timing for this`

- Calls `resolve_slack_user_identity` for Josica from the nearby Slack mention.
- Treats `add to jos task list` as ticket-first, not preview-first task drafting.
- Calls `find_ticket_by_slack_thread` before Calendar tools.
- Calls `search_pco_tickets` before creating when no same-thread ticket exists.
- Creates the PCO intake ticket immediately with `create_ps_wee_intake_ticket` only when no existing or likely PCO ticket exists.
- Posts the PCO ticket link before reporting Calendar lookup results or Calendar blockers.
- Does not ask who Jo/Jos/Josica is when Slack identity resolved it.
- Does not let Calendar rate limits block Jira ticket creation.

## PS WEE PCO Board Search

Thread:

`Customer asks about salaried staff without schedule/work for a month and whether payroll should count full attendance.`
`Teammate: isn't this proration?`
`Kai Yi: are we already tracking this in PCO`

- Calls `search_pco_tickets` with the current thread context before saying no ticket exists.
- Finds strong active PCO candidates by bounded keyword search even when the ticket has no Slack source link.
- Returns `PCO-78`-style safe fields only: issue key, URL, summary, status, issue type, PS Team, due date, and updated.
- If multiple plausible candidates exist, returns `needs-check` and asks the user to choose the PCO key before updating or creating.
- Does not expose raw descriptions, comments, attachments, or Jira bulk exports.

## PS WEE Customer Reach-Out Confirmation

Thread:

`@PSM Ops is Walta Tech on headcount or section limit? did they reach out?`
`Yes, they reached out via Intercom <support thread link>`

- Treats the support confirmation as a ticket-first PS WEE intake trigger.
- Calls `find_ticket_by_slack_thread`.
- Creates the PCO needs-info intake immediately with `create_ps_wee_intake_ticket` when no same-thread ticket exists.
- Includes the Slack thread permalink and support evidence link in Jira.
- Does not ask "do you want me to log a ticket?" before creating the intake.

## PS WEE Slack Follow-Up Sync

`@PSM Ops impact is payroll blocked for May payroll, affected outlet is central kitchen`

- Calls `append_ps_wee_ticket_update` only for meaningful ticket context.
- Adds a structured internal Jira comment with the Slack thread permalink and `Slack poster:`.
- Posts a central audit copy with update summary and source Slack thread permalink.
- Does not sync every reply or paste raw Slack transcripts.

## PS WEE Ready

`@PSM Ops all info is complete, mark the ticket ready for triage`

- Calls `mark_ps_wee_ticket_ready`.
- Adds a ready-for-triage internal comment.
- Removes `needs-info` when Jira allows it.
- Posts a central audit copy with the source Slack thread permalink.

## PS WEE Blocked Routing

`@PSM Ops create ticket for Fei Siong but no Slack thread permalink is available`

- Returns `Confidence: blocked`.
- Posts a central audit copy when a source Slack thread permalink exists in tool scope.
- Does not use Kai Yi's user token or the Slack connector for visible Slack delivery.

## Transition

`@PSM Ops move PCO-123 to Scheduled`

- Calls `transition_pco_task`.
- Uses live Jira transitions.

## Comment

`@PSM Ops add internal comment to PCO-123: training moved to Friday`

- Calls `add_internal_pco_comment`.
- Uses internal comment mode.

## Assign Issue

`@PSM Ops assign PCO-135 to @Alya`

- Calls `set_pco_assignee`.
- Resolves `@Alya` through Slack/Jira identity before assignment.
- Does not change Jira `PS Team`.

## Link Engineering Issue

`@PSM Ops link PCO-123 to KER-2109 as blocked by engineering release`

- Calls `link_pco_to_engineering_issue`.
- Requires source issue key to be `PCO-*`.
- Allows only `KER-*` or `SCHE-*` as the engineering target.
- Defaults to Jira `Blocks` direction so the PCO shows as blocked by the engineering issue.
- Does not read or expose raw engineering issue descriptions, comments, or attachments.

`@PSM Ops is there a home page ticket in KER? If yes, link it to PCO-146`

- Calls read-only `find_engineering_issue` with KER scope before linking.
- If there is one clear match such as `KER-2117`, calls `link_pco_to_engineering_issue` with that key.
- If multiple plausible KER matches are returned, asks the user to choose the issue key.
- Does not use Slack history, memory, descriptions, comments, attachments, or Jira bulk exports for KER discovery.

## Reminder

`@PSM Ops remind me tomorrow 9am on PCO-123`

- Calls `set_pco_reminder`.
- Updates Jira `duedate` only.
- Explains that the issue appears in the central 09:00 SGT / 17:00 SGT reminder digest while not Done.

## Customer Context

`@PSM Ops what is going on with Fei Siong payroll?`

- Calls C360 tools.
- Includes C360 source, citation refs or missing-data caveat, and customer link.

## Calendar Follow-Up

`@PSM Ops did Rock Productions have a follow-up meeting scheduled this week?`

- Resolves the customer and relevant StaffAny owner context through Customer 360 when needed.
- Calls `read_customer_calendar_context` with `intent="find_existing_followup"` through `team@staffany.com` with a bounded time window.
- Reports the calendars checked.
- Returns only safe event metadata.
- Does not expose descriptions, attendee emails, raw guest lists, conference links, phone numbers, or private calendar metadata.
- If the selected owner calendar is inaccessible to `team@staffany.com`, reports `Confidence: blocked` instead of saying no follow-up exists.

## Calendar Slot Suggestion Guard

`@PSM Ops find a good meeting timing for this`

- Does not call Calendar when attendees are missing.
- Asks for explicit attendees before suggesting slots.

```text
find a good meeting timing for this
```

Expected:

- No `read_customer_calendar_context` call.
- Asks for attendee emails or named attendees needed for availability lookup.
- Keeps the PCO ticket path Jira-first if the same request also asks to create/add a task.

## AppFollow Review Identity Follow-up

`@PS Wee Manager triage this AppFollow review alert`

- Uses the Slack alert as the trigger and does not poll AppFollow constantly.
- Replies with `PSM Ops automation: AppFollow review triage`.
- Keeps runtime state keyed by `store + ext_id + review_id`.
- Draft reply asks the reviewer to email `support@staffany.com` privately with StaffAny account email or phone number plus company/outlet.
- Does not ask the reviewer to post email or phone in the public review.
- Does not make `REV-<review_id>` the main customer action.
- Suggests internal tag `identity_requested_private` when reviewer identity is unknown.

`@PS Wee Manager match this reviewer: they emailed support from ops@example.com and said Example Cafe`

- Calls `suggest_appfollow_review_identity_candidates`.
- Treats exact private email match against Customer 360/HubSpot candidate evidence as verified.
- Treats phone-only or company/outlet-only matches as `needs-check`.
- Uses `confirm_appfollow_review_identity` only after PS confirms the customer/contact mapping.
- Stores only redacted contact hints in runtime state.
