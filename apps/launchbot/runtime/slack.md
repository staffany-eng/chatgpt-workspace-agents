# Slack Runtime

Launchbot's current surfaces are `#launch-bot-testing`, explicitly configured project channels, and read-only product-commitment / KER lookup in `#all-product-questions`.

## Required Behavior

- Require a mention.
- Restrict normal replies to configured channel IDs. Current allowed IDs:
  - `C0B32M34J3W` (`#launch-bot-testing`)
  - `C0AJAUNCEL8` (`#proj-cs-seonggong-seorae`) for Seorae KER lookup.
  - `C01RZ7SHC8K` (`#all-product-questions`) for read-only product-commitment / KER lookup.
  - `CF8PK6V4J` (`#input-features-ux`) for confirmed feature intake.
- Disable tool progress, streaming, interim assistant messages, and reactions.
- Suppress gateway lifecycle notices with `platforms.slack.gateway_restart_notification=false`; restarts should not post `Gateway shutting down` into active Slack threads.
- Slack Socket Mode event subscriptions must include bot events `app_mention` and `message.channels`. `message.channels` is required for channel thread/mention events to reach the Hermes gateway; without it, the service can be connected but never receive smoke messages.
- Slack OAuth scopes must include `app_mentions:read`, `channels:history`, `channels:read`, and `chat:write`.
- Visible operational replies must come from the Launchbot app identity.
- Only one `launchbot` gateway should be connected to Slack. `launchbot` is cloud-only on `hermes-data-bot-poc`; a Mac-local `~/.hermes/profiles/launchbot` profile or gateway should not exist for live smokes.
- Do not use Kai Yi's user token or the Slack connector for bot/runtime inspection when the Launchbot bot token exists.
- For ticket lookup in configured KER channels, read bounded Slack thread context with the bot token and call read-only Jira KER search. Do not post from the MCP tool and do not mutate Jira.
- For feature intake, read bounded Slack thread context with the bot token, preview the KER Idea payload, require exact `create intake` confirmation, then create only one Jira Product Discovery KER Idea. Do not post from the MCP tool, comment, transition, assign, delete, or bulk-update Jira.
- Feature intake Slack replies must start with `Launchbot automation:` and come from Launchbot's bot identity.

## Output Contract

```text
Answer: <direct answer or blocked reason>
Source: <repo packet, runbook, command, or runtime check>
Scope: <profile/channel/environment>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```
