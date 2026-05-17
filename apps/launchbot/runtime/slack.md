# Slack Runtime

Launchbot's current surfaces are `#launch-bot-testing`, explicitly configured project channels, read-only product-commitment / KER lookup in `#all-product-questions`, and weekly support-watch reports to `#all-bugs-production`.

## Required Behavior

- Require a mention.
- Restrict normal replies to configured channel IDs. Current allowed IDs:
  - `C0B32M34J3W` (`#launch-bot-testing`)
  - `C0AJAUNCEL8` (`#proj-cs-seonggong-seorae`) for Seorae KER lookup.
  - `C01RZ7SHC8K` (`#all-product-questions`) for read-only product-commitment / KER lookup.
  - `CF8PK6V4J` (`#input-features-ux`) for confirmed feature intake.
  - `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID` (`#all-bugs-production`) for weekly support-watch output after deploy resolution.
- Disable tool progress, streaming, interim assistant messages, and reactions.
- Suppress gateway lifecycle notices with `platforms.slack.gateway_restart_notification=false`; restarts should not post `Gateway shutting down` into active Slack threads.
- Slack Socket Mode event subscriptions must include bot events `app_mention` and `message.channels`. `message.channels` is required for channel thread/mention events to reach the Hermes gateway; without it, the service can be connected but never receive smoke messages.
- Slack OAuth scopes must include `app_mentions:read`, `channels:history`, `channels:read`, `channels:join`, and `chat:write`. Launchbot resolves support-watch public channels through `conversations.list` with `types=public_channel`; it uses bot-owned `conversations.join` to repair public-channel membership. Do not require `groups:read` unless a support-watch channel is intentionally private and configured by ID.
- Visible operational replies must come from the Launchbot app identity.
- Only one `launchbot` gateway should be connected to Slack. `launchbot` is cloud-only on `hermes-data-bot-poc`; a Mac-local `~/.hermes/profiles/launchbot` profile or gateway should not exist for live smokes.
- Do not use Kai Yi's user token or the Slack connector for bot/runtime inspection when the Launchbot bot token exists.
- For ticket lookup in configured KER channels, read bounded Slack thread context with the bot token and call read-only Jira KER search. Do not post from the MCP tool and do not mutate Jira.
- Existing Slack threads keep their Hermes session state across gateway restarts. After a SOUL-changing deploy, live-profile audit must pass without `sessions:stale-system-prompt`; reset only the affected Launchbot thread session before verifying that thread.
- For product commitment checks, read bounded Slack thread context with the bot token and call read-only Jira KER/JPD search. Count only explicit `fixVersions` or reviewed commitment field IDs from `LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS`; do not infer ETA, create intake, post from the MCP tool, or mutate Jira.
- For feature intake, read bounded Slack thread context with the bot token, preview the KER Idea payload, require exact `create intake` confirmation, then create only one Jira Product Discovery KER Idea. Do not post from the MCP tool, comment, transition, assign, delete, or bulk-update Jira.
- Feature intake Slack replies must start with `Launchbot automation:` and come from Launchbot's bot identity.
- For channel monitoring, keep `slack.require_mention=true` for the Hermes gateway. Use the no-agent `launchbot feature intake monitor` cron to poll configured public channels instead of sending every channel message through the agent.
- The monitor default channel is `CF8PK6V4J` (`#input-features-ux`) via `LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS`. It may post one `Launchbot automation:` preview per source permalink, then create only after exact `create intake` or `create KER intake` in the same thread.
- The monitor state path is `~/.hermes/profiles/launchbot/runtime/feature-intake-monitor-state.json`. It stores channel IDs, timestamps, source permalinks, safe summaries, status, and issue keys only; it must not persist raw Slack transcripts.
- The monitor needs Slack bot-token access to `conversations.history`, `conversations.replies`, and `chat.postMessage` for configured channels, plus the existing Jira read/create credentials.
- For weekly support watch, the MCP preview may read Slack history only for dedupe. It must not post Slack or mutate Jira/Linear. The no-agent `launchbot support watch` cron is the only support-watch lane allowed to call `chat.postMessage`.
- Support-watch output channel is `#all-bugs-production` through `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME=all-bugs-production`. `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID` is optional for private or pre-resolved channels; public channels are resolved by the Launchbot bot token.
- Support-watch dedupe reads recent `#team-cs-eng-duty` posts through `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES=team-cs-eng-duty` or explicit `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS`, EDT through `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL`, and prior state through `LAUNCHBOT_SUPPORT_WATCH_STATE_PATH`.
- Support-watch posts only when there are new, untracked findings. No new findings means no Slack post.
- Support-watch Slack reports must start with `Launchbot automation:` and state that no tickets, owners, or engineer tags were created.
- Support-watch state path is `~/.hermes/profiles/launchbot/runtime/support-watch-state.json`. It stores support-source IDs, safe summaries, source URLs, state, available team/admin assignee IDs, timestamps, signatures, and safe counters only; it must not persist raw support transcripts.

## Output Contract

```text
Answer: <direct answer or blocked reason>
Source: <repo packet, runbook, command, or runtime check>
Scope: <profile/channel/environment>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```
