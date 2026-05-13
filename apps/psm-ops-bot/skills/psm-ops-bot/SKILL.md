---
name: psm-ops-bot
description: Use when answering PSM Jira task, PCO, status transition, comment, reminder, or Customer 360 context questions.
version: 1.0.0
author: StaffAny
license: Internal
metadata:
  hermes:
    tags: [staffany, psm, jira, jsm, c360, slack]
    related_skills: [native-mcp]
---

# PSM Ops Bot

## Overview

Use this skill for StaffAny PSM operations in Slack. The bot manages PCO Jira Service Management tasks and answers Customer 360 context questions.

Alias rule: `PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` refer to this same PSM Ops Bot. Do not create or route to a separate bot/profile.

## Source Order

1. `references/jira-field-contract.md` for configured Jira request types, field IDs, status names, and write boundaries.
2. `references/regression-cases.md` for expected behavior.
3. `psm_jira` MCP for live PCO task reads and writes.
4. `psm_c360` MCP for live Customer 360 search/context/Q&A.

## Capabilities

- List the caller's own open, overdue, due-this-week, or automatic reminder-due PCO tasks.
- Create an immediate PS WEE intake ticket when PS asks to create, raise, log, or file a ticket.
- Find an existing ticket by Slack thread permalink and update it instead of creating duplicates.
- Append structured internal Jira comments from meaningful Slack follow-up discussion.
- Mark a PS WEE intake ticket ready for triage after required info is complete.
- Draft a Customer Next Action, Onboarding Task, Data Hygiene task, or Handoff Package.
- Create an approved PCO task after same-thread approval.
- Transition PCO task status to Open, Waiting Customer, Waiting Internal, Scheduled, Done, or Cancelled.
- Add an internal PCO comment.
- Set or update the Jira due date that drives automatic reminders.
- Ask Customer 360 for any customer context in V1.

## Jira Rules

- PCO is the only task system. Do not create duplicate local tasks.
- Caller task ownership is Jira `PS Team`. For "my tasks" and scoped reminders, the MCP must fetch Slack users, canonicalize the caller's Slack profile email/name, auto-match that identity to the configured `PS Team` option, and query Jira by `PS Team`.
- Do not trust model-guessed email spelling. A Slack/Jira account mismatch should not block task reads when `PS Team` can be matched.
- Task creation must be preview first. Do not call `create_approved_pco_task` until the same thread includes explicit create approval.
- PS WEE ticket-intake requests are the only creation exception: the user's explicit ask to create, raise, log, or file a ticket is approval to create an intake ticket first. Call `find_ticket_by_slack_thread`, then `create_ps_wee_intake_ticket` if no same-thread ticket exists.
- Slack thread permalink is the V1 idempotency key for PS WEE ticket intake and must be passed into the ticket.
- After creating the intake ticket, post the returned ticket link in the same Slack thread and ask for missing info there.
- Sync significant Slack discussion with `append_ps_wee_ticket_update` only when it answers missing fields, changes impact/urgency, adds affected scope, adds evidence, changes expected outcome, or records a decision/handoff. Do not sync every reply or paste raw Slack transcripts.
- When all required PS WEE info is complete, call `mark_ps_wee_ticket_ready`.
- Status transitions, internal comments, and due-date reminder updates may execute directly when issue key and action are clear.
- `CS duty` / `cs duty` means Jira `PS Team = CS Duty`; it is not a person-assignee request. Use `set_pco_ps_team` for existing issues, or pass `ps_team="CS Duty"` when drafting/creating a PCO task.
- Public customer-visible comments are blocked unless `PSM_OPS_JIRA_PUBLIC_COMMENTS_ENABLED=true`.
- Use configured Jira field IDs and request type IDs only. If `validate_jira_configuration` blocks, block the user request.
- In thin POC mode, Handoff Package is disabled until Jira adds the missing request type.
- In thin POC mode, task creation writes only current PCO request fields and stores missing metadata as an internal Jira comment.
- Do not expose raw Jira descriptions, raw comments, attachments, or bulk exports by default.

## Customer 360 Rules

- C360 access is all-customer in V1.
- Use `search_c360_customers` before answering when the customer key is ambiguous.
- Use `get_c360_account_context` for compact account facts and `ask_c360_customer_context` for natural-language wiki questions.
- Do not use a personal browser session or `customer360_session` cookie.
- Do not read raw GCS source packs, raw Slack, raw Intercom, or raw WhatsApp rows.

## Reminder Rules

- Reminder source of truth is Jira `duedate`.
- Automatic reminders include tasks due tomorrow, due today, and overdue tasks until they are Done.
- Reminder cron output must start with `PSM Ops automation:`.
- Do not create local reminder state or require a separate reminder field in thin POC.

## Slack Output

For PS WEE ticket-intake creation, if `create_ps_wee_intake_ticket` returns `answer.slack_reply`, paste that string exactly as the first line. Do not rewrite or reformat the Jira Slack link syntax (`<url|KEY>`).

Final answers must use plain labelled lines:

Answer: <result or blocked reason>
Source: <Jira PCO | Customer 360 | tool used>
Scope: <caller, issue key, customer, time window>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

## Common Pitfalls

1. Creating a Jira task without a preview and approval.
   - Exception: explicit PS WEE ticket-intake requests must create an intake ticket first through `create_ps_wee_intake_ticket`.
2. Treating Customer 360 as a task store. It is context only; PCO owns tasks.
3. Guessing Jira field IDs or transition IDs.
4. Posting public JSM customer comments by default.
5. Using local state for reminders.
6. Using personal Customer 360 cookies from Hermes.
7. Treating `PS WEE` as a separate app/profile instead of the existing PSM Ops Bot.
8. Using Jira assignee or a guessed Slack email as the source of truth for "my tasks" instead of Jira `PS Team`.
