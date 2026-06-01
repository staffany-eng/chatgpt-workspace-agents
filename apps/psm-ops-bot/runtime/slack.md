# Slack Runtime

The Slack surface is strict @-mention opt-in usage in public/open StaffAny Slack channels.

`PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` are aliases for this same PSM Ops Bot Slack surface.

## Required Behavior

- Strict mention-only in public/open channels: every reactive channel message must directly @-mention PS WEE / this bot before Hermes may answer.
- Set `slack.strict_mention=true` so Hermes does not auto-engage from remembered thread mentions, bot-message replies, or active same-thread sessions.
- Untagged same-thread replies after a previous bot response are silent, including human follow-up context, thanks/ok acknowledgements, and questions directed at another human.
- If a user says "stay quiet", "stop commenting", "do not reply", or equivalent, stay silent in that thread until a later direct @-mention.
- Use the PSM Ops bot identity for all visible replies.
- Do not send Slack replies as Kai Yi or through a human user token.
- Keep Slack output quiet: no streaming drafts, no tool progress, no status reactions.
- Route non-critical `auxiliary.title_generation` through the pinned short-timeout Haiku auxiliary config so title-generation overloads do not become visible Slack follow-up noise.
- Suppress gateway lifecycle notices in the pilot channel with `platforms.slack.gateway_restart_notification=false`.
- Task creation is preview first. In public/open channels, approval must directly mention PS WEE, for example `@PS WEE create`, `@PS WEE approve create`, or `@PS WEE create this`, because strict mention mode ignores untagged same-thread replies.
- ROI-direct requests are ticket-first and must create or reuse ROI JSM first. When PS Wee is asked to create, add, log, handle, ticket, task, or board work for ROI, RevOps, BD Ops, bdops, NYSS, n y s s, invoice/billing, renewal invoices, discounts, HC/deal checks, Stripe invoices, HubSpot deals, ERP dashboards/data issues, linked BE, accessible invoices, MRR mismatch, SLA dashboards, or asset sync, call `classify_roi_ticket_request`, then `find_roi_ticket_by_slack_thread`, then `create_roi_ticket_from_slack` if no same-thread ROI ticket exists.
- For resolved PS Team callers, billing/invoice/renewal billing asks default to customer-loop tracking. If `classify_roi_ticket_request` returns `pco_tracker_default=true`, call `create_or_link_pco_roi_tracker` after ROI create/reuse so the linked PCO tracker appears in `Waiting Internal`.
- Do not trigger ROI creation for casual `@nyss`, BD Ops, or RevOps questions unless the user asks PS Wee to create, add, log, handle, ticket, task, or board the work.
- ROI requester is first-class. Explicit `requested by` / `reported by` wins; otherwise pass the current Slack sender ID/mention or email. If requester cannot resolve, block creation and ask for requester only. No bot, team, or `team@staffany.com` fallback.
- Do not create duplicate PCO execution wrappers for ROI work. The PCO ROI tracker is allowed only for customer-loop visibility; ROI remains internal-team execution truth.
- PS WEE ticketing requests are ticket-first. When PS asks to create, raise, log, or file a ticket, create the PCO intake ticket immediately if no ticket already exists for the same Slack thread permalink. Pass known facts into the Jira tool, paste its returned ticket reply exactly, and do not add numbered follow-up questionnaires.
- PCO tracking checks must use `search_pco_tickets` before saying no PCO ticket exists. The same rule applies before saying `not ticketed yet`. Exact Slack-thread lookup alone is not enough because manually-created board tickets may omit Slack source links.
- If `search_pco_tickets` returns `not_found` for a tracking-status question, do not auto-create. Return a create-ready offer with a compact ticket seed: customer, issue, impact/risk, and evidence/source thread. End with exactly `Reply "@PS WEE create ticket" to open the PS WEE intake ticket.` The caveat must say no ticket was created because the user asked for tracking status, not creation. Say `bounded keyword search`, never `full keyword search`.
- Same-thread replies that directly @-mention PS WEE with `create ticket`, `open ticket`, `log it`, or `yes, create it` after a create-ready offer count as explicit PS WEE ticketing approval. Untagged approvals are silent under strict mention mode. Run `find_ticket_by_slack_thread`, then `search_pco_tickets`, then `create_ps_wee_intake_ticket`, passing the prior ticket seed facts.
- For create/open/tag requests, run same-thread dedupe first, then use `search_pco_tickets` as the broader duplicate guard before creating a new PCO intake ticket. If the search returns `needs-check`, ask the user to choose the PCO key before updating or creating.
- Operational task-list requests are ticket-first. When PS asks to `add to <person/team> task list`, `add to Jo/Jos/Josica`, `put on backlog`, `add to follow-up list`, or equivalent, create or return the PCO intake ticket.
- A confirmed customer reach-out in a PS WEE/customer-ops thread is ticket-first even if nobody says "create ticket". Examples: "did they reach out?" followed by "yes, via Intercom", a support-thread permalink, an admin screenshot showing a limit hit, or a teammate confirming impact. Create or return the same-thread PCO intake ticket.
- Customer-specific Slack channels auto-tag only through reviewed channel mappings. If the mapped channel customer conflicts with the message customer, block ticket creation and ask for confirmation.
- If the same request asks for meeting timing, handle the Jira ticket first and treat Calendar lookup as best-effort follow-up. Calendar quota/rate-limit errors must not block the ticket link.
- Post the created or existing ticket link in the same Slack thread. Do not ask follow-up questions to fill ticket fields.
- For Jira tools that ask for `slack_user_email`, pass the current Slack sender ID/mention or profile email. Never ask the user to provide their email just to satisfy this parameter.
- Sync meaningful follow-up discussion as structured internal Jira comments only. Pass the Slack poster display name, user ID, and email when available; the Jira internal comment must include `Slack poster:` for traceability. Do not sync every Slack reply and do not paste raw Slack transcripts into Jira.
- Also post a `PSM Ops automation:` central audit copy for PS WEE ticket create/reuse/update events and blocked Jira/C360 tool results when `PSM_OPS_CENTRAL_SLACK_CHANNEL_ID` or `SLACK_HOME_CHANNEL` is configured. This is a private ops-channel exception: it may include a bounded current-thread excerpt, relevant Jira payload, and C360 API response, but no secrets, attachments, phone exports, bulk exports, or underlying raw C360 source packs.
- Status transitions, internal comments, PCO-to-KER/SCHE issue links, and reminders may execute directly when the issue keys and action are clear.
- Natural-language KER/SCHE lookup must use Jira through `find_engineering_issue`; do not use Slack channel history or memory as the source for engineering issue discovery.
- Automation reminders and assignment hygiene digests must start with `PSM Ops automation:` and deliver to the central PS WEE digest channel only in V1.
- Reminder digests use deterministic Slack mrkdwn over Jira `duedate`. PS Team mentions come only from the reviewed runtime `PSM_OPS_REMINDER_MENTION_MAP_PATH`; do not call Slack `users.list` or guess inverse mappings from Jira option names in the reminder cron.
- Assignment hygiene digests use deterministic Slack mrkdwn over safe Jira PCO fields only. Josica lead mention comes only from `ps_leads.Josica`; PS Team mentions come only from `ps_teams`. Missing mappings render `Lead mention gap` or `Mention gaps`.
- Customer-team tagging in reminders is central-channel-only. Render a customer channel mention only when a Jira source link contains a Slack permalink whose channel is reviewed in `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH`; do not cross-post to customer channels.
- Explicit customer scheduling or follow-up requests may use `read_customer_calendar_context` through the read-only `team@staffany.com` account. Do not call Calendar for vague names, task-list ownership, or missing attendee slot requests. Return only bounded safe metadata and never expose descriptions, attendee emails, raw guest lists, conference links, or phone numbers.

## Output Contracts

Task and context answers:

```text
Answer: <result or blocked reason>
Source: <Jira PCO | Customer 360 | tool used>
Scope: <caller, issue key, customer, time window>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```

Draft task output:

```text
Answer: Draft ready for PCO creation.
Draft: <customer, summary, due date, owner, action type, risk reason, source links>
Duplicate check: <candidate issues or none found>
Source: Jira PCO draft + Customer 360 context
Scope: <customer/caller>
Confidence: <verified | needs-check | blocked>
Caveat: Reply "@PS WEE create" to create this task.
```

ROI ticket output:

```text
Created ROI ticket: <url|ROI-key>. Requester: <resolved requester>.
Source: Jira ROI
Scope: <caller, Slack thread, customer/request category>
Confidence: verified
Caveat: ROI ticket is source of truth; Slack thread is evidence.
```

PCO ROI tracker output:

```text
Tracking customer loop on PCO: <url|PCO-key> linked to <url|ROI-key> and set to Waiting Internal.
Source: Jira ROI + Jira PCO tracker
Scope: <caller, Slack thread, customer>
Confidence: verified
Caveat: ROI ticket is source of truth; PCO tracker is only for customer-loop visibility.
```

## Slack Scopes

Use the minimum Hermes Slack gateway scopes required for app mentions, public-channel membership, thread reads, replies, and caller identity:

- `app_mentions:read`
- `channels:read`
- `channels:history`
- `channels:join`
- `chat:write`
- `users:read`
- `users:read.email`

The PSM Jira MCP needs `users:read` and `users:read.email` so it can fetch Slack users, canonicalize profile email/name, and match the caller to Jira `PS Team`.

Central audit copies need bot-owned `chat:write`. If raw source-thread excerpt fetch is enabled, the bot also needs `channels:history` for public channels it is in and `groups:history` only for private channels where the bot has explicitly been invited. Do not request broad private-channel enumeration for V1.

Open public-channel mode is not proven by `SLACK_ALLOWED_CHANNELS=""` alone. The Slack app must have `channels:join`, then the bot-owned public-channel join script must be run from the cloud profile:

```bash
~/.hermes/profiles/psmopsbot/scripts/psm_ops_join_public_channels.py --dry-run
~/.hermes/profiles/psmopsbot/scripts/psm_ops_join_public_channels.py --apply
```

If `conversations.join` returns `missing_scope`, reinstall the Slack app with the required bot scopes above before retrying. Do not use Kai Yi's user token or the Slack connector to invite or post as a workaround.

## Channel Access

Runtime config must allow open-channel usage:

```yaml
slack:
  require_mention: true
  strict_mention: true
  allowed_channels: ""

gateway:
  slack:
    channel: "#ps-weeman-bot-test"
```

Do not set `SLACK_ALLOWED_CHANNELS` for this app when it is expected to answer in any public/open channel. Keep both `require_mention=true` and `strict_mention=true`; private channels still require explicit membership and approved Slack scopes.
