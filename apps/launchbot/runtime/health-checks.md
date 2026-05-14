# Health Checks

Launchbot needs a small no-agent health check before it can be treated as reliable.

Expected checks:

- Hermes gateway service for `launchbot` is active.
- Secret redaction remains enabled.
- Model route is `model.provider=anthropic`, `model.default=claude-sonnet-4-6`.
- Slack quiet settings are enabled: no streaming, no tool progress, no interim assistant messages, no reactions.
- `SLACK_HOME_CHANNEL` is `C0B32M34J3W`.
- Slack allowed channels include `C0B32M34J3W` and `C0AJAUNCEL8`.
- `launchbot_ker` MCP exposes only `find_ker_ticket_from_slack_thread` and `lookup_ker_ticket_by_key`.
- KER lookup has `SLACK_BOT_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` in the live profile env.
- Healthy checks print nothing and exit 0.

Install profile-local health script:

```bash
mkdir -p ~/.hermes/profiles/launchbot/scripts
cp apps/launchbot/runtime/check-health.sh ~/.hermes/profiles/launchbot/scripts/launchbot-check-health.sh
hermes -p launchbot cron create "*/5 * * * *" \
  --name "launchbot health check" \
  --script launchbot-check-health.sh \
  --no-agent
```

The current Hermes CLI uses the deployment host timezone for cron scheduling and does not expose a `--timezone` flag.
