# Slack Runtime

The first surface is the Slack pilot channel `#ps-weeman-bot-test`.

`PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` are aliases for this same PSM Ops Bot Slack surface.

## Required Behavior

- Mention-only in the pilot channel.
- Use the PSM Ops bot identity for all visible replies.
- Do not send Slack replies as Kai Yi or through a human user token.
- Keep Slack output quiet: no streaming drafts, no tool progress, no status reactions.
- Suppress gateway lifecycle notices in the pilot channel with `platforms.slack.gateway_restart_notification=false`.
- Task creation is preview first. Same-thread `create`, `approve create`, or `create this` approves the previously shown draft.
- PS WEE ticketing requests are ticket-first. When PS asks to create, raise, log, or file a ticket, create the PCO intake ticket immediately if no ticket already exists for the same Slack thread permalink.
- Post the created or existing ticket link in the same Slack thread, then ask for missing info there.
- Sync meaningful follow-up discussion as structured internal Jira comments only. Do not sync every Slack reply and do not paste raw Slack transcripts into Jira.
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

Use the minimum Hermes Slack gateway scopes required for app mentions and caller identity. Do not request broad private-channel enumeration for V1.

## Pilot Channel

Runtime config must set:

```yaml
slack:
  require_mention: true
  allowed_channels: "<pilot channel ID>"

gateway:
  slack:
    channel: "#ps-weeman-bot-test"
```

For the current pilot workspace, `#ps-weeman-bot-test` resolves to channel ID `C0B2VT50YT1`. Keep `SLACK_ALLOW_ALL_USERS=true` only together with `SLACK_ALLOWED_CHANNELS=C0B2VT50YT1` until the explicit access policy is added.
