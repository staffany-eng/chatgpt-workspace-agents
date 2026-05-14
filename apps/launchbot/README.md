# Launchbot

Minimal canonical Hermes app packet for the Launchbot Slack profile.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `launchbot`
- Surface: Slack mentions in `#launch-bot-testing` and explicitly configured project channels
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/launchbot/`
- Status: experimental until it has real tools, owner, runbooks, and passing health cron.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled profile instruction. |
| `profile/config.template.yaml` | Non-secret profile config template. |
| `runtime/slack.md` | Slack channel and identity rules. |
| `runtime/health-checks.md` | Expected health checks and cron pattern. |
| `runtime/check-health.sh` | Silent no-agent health check. |
| `runtime/audit-live-profile.sh` | Live profile drift audit. |
| `runtime/mcp/launchbot_ker_server.py` | Read-only Slack thread to Jira KER lookup tool. |

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `launchbot` profile.
3. Copy `profile/SOUL.md` to `~/.hermes/profiles/launchbot/SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Set Slack and model secrets from the approved secret store only.
6. Set Jira read-only env vars (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) in the live profile `.env` before enabling KER lookup.
7. Copy runtime scripts into `~/.hermes/profiles/launchbot/scripts/`.
8. Start the managed gateway and install the no-agent health cron.
9. Keep it experimental until the health check passes and the Slack smoke replies from `#launch-bot-testing`.
