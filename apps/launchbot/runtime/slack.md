# Slack Runtime

Launchbot's current surface is `#launch-bot-testing`.

## Required Behavior

- Require a mention.
- Restrict the pilot to channel ID `C0B32M34J3W`.
- Disable tool progress, streaming, interim assistant messages, and reactions.
- Visible operational replies must come from the Launchbot app identity.
- Do not use Kai Yi's user token or the Slack connector for bot/runtime inspection when the Launchbot bot token exists.

## Output Contract

```text
Answer: <direct answer or blocked reason>
Source: <repo packet, runbook, command, or runtime check>
Scope: <profile/channel/environment>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```
