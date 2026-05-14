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
- Pantheon is cloned at `~/.hermes/profiles/launchbot/source/pantheon`, with remote `git@github.com:staffany-eng/pantheon.git`, branch `develop`, clean worktree, and a fresh update status JSON.
- If the VM does not already have GitHub repo access, use a read-only GitHub deploy key at `~/.hermes/profiles/launchbot/ssh/pantheon_deploy_key`.
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

Install profile-local Pantheon updater:

```bash
mkdir -p ~/.hermes/profiles/launchbot/scripts
cp apps/launchbot/runtime/update-pantheon-repo.sh ~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh
test -r ~/.hermes/profiles/launchbot/ssh/pantheon_deploy_key.pub || ssh-keygen -t ed25519 -N "" -C "launchbot-pantheon-readonly" -f ~/.hermes/profiles/launchbot/ssh/pantheon_deploy_key
~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh
hermes -p launchbot cron create "0 22 * * *" \
  --name "launchbot pantheon repo update" \
  --script launchbot-update-pantheon-repo.sh \
  --no-agent
```

The Pantheon cron uses `0 22 * * *`, which is 06:00 Asia/Singapore on the current UTC GCP VM default. If the deployment host timezone is changed, keep the job daily and document the host timezone in the live repair note.

The current Hermes CLI uses the deployment host timezone for cron scheduling and does not expose a `--timezone` flag.
