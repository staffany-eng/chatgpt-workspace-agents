# Slack Runtime

The Slack surface is mention-required usage in public/open StaffAny Slack channels.

`PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` are aliases for this same PSM Ops Bot Slack surface.

## Required Behavior

- Mention-only in public/open channels.
- Use the PSM Ops bot identity for all visible replies.
- Do not send Slack replies as Kai Yi or through a human user token.
- Keep Slack output quiet: no streaming drafts, no tool progress, no status reactions.
- Suppress gateway lifecycle notices in the pilot channel with `platforms.slack.gateway_restart_notification=false`.
- Task creation is preview first. Same-thread `create`, `approve create`, or `create this` approves the previously shown draft.
- PS WEE ticketing requests are ticket-first. When PS asks to create, raise, log, or file a ticket, create the PCO intake ticket immediately if no ticket already exists for the same Slack thread permalink.
- Operational task-list requests are ticket-first. When PS asks to `add to <person/team> task list`, `add to Jo/Jos/Josica`, `put on backlog`, `add to follow-up list`, or equivalent, create or return the PCO intake ticket before asking for missing fields.
- A confirmed customer reach-out in a PS WEE/customer-ops thread is ticket-first even if nobody says "create ticket". Examples: "did they reach out?" followed by "yes, via Intercom", a support-thread permalink, an admin screenshot showing a limit hit, or a teammate confirming impact. Create or return the same-thread PCO intake ticket first, then ask for missing details.
- If the same request asks for meeting timing, handle the Jira ticket first and treat Calendar lookup as best-effort follow-up. Calendar quota/rate-limit errors must not block the ticket link.
- Post the created or existing ticket link in the same Slack thread, then ask for missing info there.
- Sync meaningful follow-up discussion as structured internal Jira comments only. Pass the Slack poster display name, user ID, and email when available; the Jira internal comment must include `Slack poster:` for traceability. Do not sync every Slack reply and do not paste raw Slack transcripts into Jira.
- Status transitions, internal comments, and reminders may execute directly when the issue key and action are clear.
- Automation reminders must start with `PSM Ops automation:`.

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
Caveat: Reply "create" to create this task.
```

## Slack Scopes

Use the minimum Hermes Slack gateway scopes required for app mentions and caller identity. The PSM Jira MCP needs `users:read` and `users:read.email` so it can fetch Slack users, canonicalize profile email/name, and match the caller to Jira `PS Team`. Do not request broad private-channel enumeration for V1.

## Channel Access

Runtime config must allow open-channel usage:

```yaml
slack:
  require_mention: true
  allowed_channels: ""

gateway:
  slack:
    channel: "#ps-weeman-bot-test"
```

Do not set `SLACK_ALLOWED_CHANNELS` for this app when it is expected to answer in any public/open channel. Keep `require_mention=true`; private channels still require explicit membership and approved Slack scopes.
