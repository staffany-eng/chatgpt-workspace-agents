# Regression Cases

## List My Tasks

Prompt:

```text
show my overdue PCO tasks
```

Expected:

- Uses caller Slack email to resolve configured Jira account ID.
- Calls `list_my_pco_tasks`.
- Returns safe fields: issue key, summary, status, priority, due date, reminder date, assignee, and URL.
- Does not expose raw descriptions, comments, attachments, or private customer fields.

## Draft Then Create

Prompt:

```text
create task for Fei Siong to confirm payroll readiness by Friday
```

Expected:

- Searches/resolves C360 customer if needed.
- Passes the current Slack sender ID/mention into Jira tools when email is not already present.
- Does not ask the user for Slack/Jira email before drafting or creating.
- Calls `draft_pco_task`.
- Shows the Jira-ready draft and duplicate candidates.
- Does not create yet.
- After same-thread `create`, calls `create_approved_pco_task`.
- Blocks creation if the resolved due date is before today's date.

## PS WEE Ticket First Intake

Prompt:

```text
create ticket for Fei Siong payroll readiness, not enough info yet
```

Expected:

- Treats `PS WEE` / `PS Wee Manager` as this PSM Ops Bot, not a separate app/profile.
- Calls `find_ticket_by_slack_thread` with the current Slack thread permalink.
- If no ticket exists for that Slack thread, calls `create_ps_wee_intake_ticket` immediately without preview approval.
- Creates `[Needs info] Fei Siong - payroll readiness` style PCO intake ticket.
- Includes `Source Slack thread: <permalink>` in Jira.
- Posts the ticket link in the same Slack thread and asks for missing info.
- Does not paste the raw Slack transcript into Jira.

## PS WEE ROI Direct Intake

Prompt:

```text
@PS Wee Manager create a task for bd ops to send Dreamus invoice
```

Expected:

- Treats `PS Wee Manager` as this PSM Ops Bot, not a separate app/profile.
- Calls `classify_roi_ticket_request` and detects actionable BD Ops / invoice work.
- Calls `find_roi_ticket_by_slack_thread` with the current Slack thread permalink.
- If no ROI ticket exists for that Slack thread, calls `create_roi_ticket_from_slack`.
- Does not call `create_ps_wee_intake_ticket` or create a PCO wrapper.
- Resolves requester from explicit `requested by` / `reported by` first, otherwise the Slack sender.
- Blocks creation when requester cannot resolve to Slack/Jira identity; never uses a bot, team, or `team@staffany.com` fallback requester.
- Discovers required ROI JSM fields at runtime and blocks with exact missing field names when required values are missing.
- Includes source Slack thread, original channel, and requester in ROI request fields or internal metadata.

## Casual NYSS Question Does Not Create ROI

Prompt:

```text
@PS Wee Manager @nyss what is the Stripe password?
```

Expected:

- Does not create ROI.
- Does not create PCO.
- Requires create/add/log/handle/ticket/task/board wording before ROI ticket creation.

## PS WEE Task List And Calendar Mixed Request

Thread:

```text
Parent: @Josica we need to discuss a process upgrade where any change requests from customers need to funnel through a particular team, esp for big customers. @PS WEE help to add to jos and find a good meeting timing for this
Kai Yi: help to add to jos task list, and find a good meeting timing for this
```

Expected:

- Calls `resolve_slack_user_identity` for the Josica Slack mention before asking who `jos` is.
- Treats `add to jos task list` as a PS WEE ticket-first intake trigger.
- Calls `find_ticket_by_slack_thread` with the current Slack thread permalink before any Calendar lookup.
- If no ticket exists for that Slack thread, calls `create_ps_wee_intake_ticket` immediately without preview approval.
- Creates a needs-info PCO intake for the Rock Productions / big-customer change-request process.
- Posts the ticket link in the same Slack thread first, then reports Calendar availability as secondary or blocked.
- Does not let Calendar quota/rate-limit errors block the PCO ticket link.

## PS WEE Same Thread Dedupe

Prompt:

```text
create ticket for this too
```

Expected:

- Calls `find_ticket_by_slack_thread`.
- If an existing PCO ticket already cites the same Slack thread permalink, returns the existing ticket link.
- Does not call `create_ps_wee_intake_ticket` again.

## PS WEE Customer Reach-Out Confirmation

Thread:

```text
PSM: is Walta Tech on headcount or section limit? did they reach out?
Bot: C360 cannot confirm limit usage. Did they reach out about hitting the limit?
Teammate: Yes, they reached out via Intercom <support thread link>
```

Expected:

- Treats the teammate confirmation plus Intercom/support link as a PS WEE intake trigger.
- Calls `find_ticket_by_slack_thread` with the current Slack thread permalink.
- If no ticket exists for that Slack thread, calls `create_ps_wee_intake_ticket` immediately without asking "do you want me to log a ticket?".
- Creates a needs-info PCO intake using the known facts: customer, section/headcount limit context, evidence link, and missing impact/expected outcome.
- Posts the ticket link in the same Slack thread and asks only for the missing fields.

## PS WEE Meaningful Slack Update

Prompt:

```text
impact is payroll blocked for May payroll, affected outlet is central kitchen
```

Expected:

- Calls `append_ps_wee_ticket_update` only because the reply adds meaningful ticket context.
- Adds a structured internal Jira comment with the Slack thread permalink, `Slack poster:`, and updated fields.
- Does not sync every casual acknowledgement or paste raw Slack transcript text.

## PS WEE Ready For Triage

Prompt:

```text
all details are there, mark it ready
```

Expected:

- Calls `mark_ps_wee_ticket_ready` after customer/org, issue details, impact/urgency, affected scope, expected outcome, and evidence are complete.
- Adds an internal ready-for-triage comment.
- Removes `needs-info` when Jira allows it.

## Status Transition

Prompt:

```text
move PCO-123 to Scheduled
```

Expected:

- Calls `transition_pco_task` with target status `Scheduled`.
- Uses live Jira transitions for that issue.
- Blocks if the requested target status is not one of the configured allowed statuses.

## Internal Comment

Prompt:

```text
add internal comment to PCO-123: customer asked to push training to Friday
```

Expected:

- Calls `add_internal_pco_comment` with `public_comment=false`.
- Blocks public/customer-visible comment requests unless explicitly enabled in runtime config.

## Assign Issue

Prompt:

```text
assign PCO-135 to @Alya
```

Expected:

- Calls `set_pco_assignee`.
- Resolves the Slack mention to an active Jira account.
- Does not update Jira `PS Team`; "my tasks" and reminders remain PS Team scoped.

## Reminder

Prompt:

```text
remind me tomorrow 9am on PCO-123
```

Expected:

- Calls `set_pco_reminder`.
- Updates Jira `duedate`, because due date drives automatic reminders.
- Does not create local reminder state.

## Cron Reminder

Prompt:

```text
PSM Ops automation: check reminder-due PCO tasks.
```

Expected:

- Calls `list_due_pco_reminders`.
- Uses `duedate <= tomorrow` and excludes Done tasks.
- Output starts with `PSM Ops automation:`.
- Source is Jira PCO.

## Customer Context

Prompt:

```text
what is going on with Fei Siong payroll?
```

Expected:

- Resolves the C360 customer.
- Calls `ask_c360_customer_context` or `get_c360_account_context`.
- Includes Customer 360 source, citation refs or missing-data caveat, and C360 link.
- Does not use personal Customer 360 cookies or raw source packs.

## Calendar Follow-Up

Prompt:

```text
did Rock Productions have a follow-up meeting scheduled this week?
```

Expected:

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
