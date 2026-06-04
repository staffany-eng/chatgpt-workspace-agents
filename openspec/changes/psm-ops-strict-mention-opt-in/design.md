# Design: PSM Ops Strict Mention Opt-In

## Approach

Use Hermes' built-in Slack `strict_mention` config instead of adding a prompt-only workaround. With `slack.strict_mention=true`, Hermes ignores remembered thread mentions, bot-message reply triggers, and active thread sessions unless the current channel message mentions the bot.

The app packet also keeps prompt and runtime docs aligned so the model does not voluntarily act on untagged same-thread context if a future gateway path changes.

## Runtime Shape

- `apps/psm-ops-bot/profile/config.template.yaml` sets `slack.strict_mention: true`.
- Deploy writes the config template into the live cloud profile, so the next deploy updates the gateway runtime config.
- `runtime/check-health.sh` fails if live config does not contain `strict_mention: true`.
- `scripts/verify-psm-ops-bot.mjs` fails if packet config, manifest, docs, or profile registry lose the strict opt-in contract.

## Safety

The change reduces Slack participation. It does not add new tools, credentials, write paths, or channel scopes.

Cron and audit outputs still identify as automation and are not reactive Slack replies. AA push flow remains bot-initiated and is not gated by the current human message mentioning the bot.
