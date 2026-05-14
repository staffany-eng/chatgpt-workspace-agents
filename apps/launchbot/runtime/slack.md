# Slack Runtime

Launchbot's current surfaces are `#launch-bot-testing` and explicitly configured project channels.

## Required Behavior

- Require a mention.
- Restrict normal replies to configured channel IDs. Current allowed IDs:
  - `C0B32M34J3W` (`#launch-bot-testing`)
  - `C0AJAUNCEL8` (`#proj-cs-seonggong-seorae`) for Seorae KER lookup.
- Disable tool progress, streaming, interim assistant messages, and reactions.
- Slack Socket Mode event subscriptions must include bot events `app_mention` and `message.channels`. `message.channels` is required for channel thread/mention events to reach the Hermes gateway; without it, the service can be connected but never receive smoke messages.
- Slack OAuth scopes must include `app_mentions:read`, `channels:history`, `channels:read`, and `chat:write`.
- Visible operational replies must come from the Launchbot app identity.
- Only one `launchbot` gateway should be connected to Slack. `launchbot` is cloud-only on `hermes-data-bot-poc`; a Mac-local `~/.hermes/profiles/launchbot` profile or gateway should not exist for live smokes.
- Do not use Kai Yi's user token or the Slack connector for bot/runtime inspection when the Launchbot bot token exists.
- For ticket lookup, read bounded Slack thread context with the bot token and call read-only Jira KER search. Do not post from the MCP tool and do not mutate Jira.

## Output Contract

```text
Answer: <direct answer or blocked reason>
Source: <repo packet, runbook, command, or runtime check>
Scope: <profile/channel/environment>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```
