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
- Calls `draft_pco_task`.
- Shows a preview and waits for `create`.
- Calls `create_approved_pco_task` only after approval.

## PS WEE Ticket First

`@PSM Ops create ticket for Fei Siong payroll readiness, info not complete yet`

- Treats PS WEE as the existing PSM Ops Bot.
- Calls `find_ticket_by_slack_thread`.
- Creates the PCO intake ticket immediately with `create_ps_wee_intake_ticket` when no same-thread ticket exists.
- Includes the Slack thread permalink in Jira.
- Posts the ticket link in-thread and asks for missing info.

## PS WEE Task List Plus Calendar

Thread:

`@Josica we need to discuss a process upgrade where any change requests from customers need to funnel through a particular team, esp for big customers. @PSM Ops help to add to jos and find a good meeting timing for this`
`@PSM Ops help to add to jos task list, and find a good meeting timing for this`

- Calls `resolve_slack_user_identity` for Josica from the nearby Slack mention.
- Treats `add to jos task list` as ticket-first, not preview-first task drafting.
- Calls `find_ticket_by_slack_thread` before Calendar tools.
- Creates the PCO intake ticket immediately with `create_ps_wee_intake_ticket` when no same-thread ticket exists.
- Posts the PCO ticket link before reporting Calendar lookup results or Calendar blockers.
- Does not ask who Jo/Jos/Josica is when Slack identity resolved it.
- Does not let Calendar rate limits block Jira ticket creation.

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
- Adds a structured internal Jira comment with the Slack thread permalink.
- Does not sync every reply or paste raw Slack transcripts.

## PS WEE Ready

`@PSM Ops all info is complete, mark the ticket ready for triage`

- Calls `mark_ps_wee_ticket_ready`.
- Adds a ready-for-triage internal comment.
- Removes `needs-info` when Jira allows it.

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

## Reminder

`@PSM Ops remind me tomorrow 9am on PCO-123`

- Calls `set_pco_reminder`.
- Updates Jira `duedate` only.

## Customer Context

`@PSM Ops what is going on with Fei Siong payroll?`

- Calls C360 tools.
- Includes C360 source, citation refs or missing-data caveat, and customer link.
