# Health Checks

PSM Ops Bot needs deterministic cloud health checks because prompt correctness does not prove Slack, Jira, C360, cron, or gateway wiring.

## Expected Checks

- Hermes gateway service `hermes-gateway-psmopsbot.service` is active on the GCE host.
- Hermes gateway service `hermes-gateway-psmopsbot.service` is enabled on the GCE host.
- Secret redaction remains enabled.
- Model route is pinned to `anthropic` / `claude-sonnet-4-6`.
- Slack gateway is mention-required and not restricted to a single public/open channel.
- Slack bot token can call `users.list` with profile emails for `PS Team` identity matching.
- `psm_jira` MCP lists exactly the expected tools.
- `psm_c360` MCP lists exactly the expected tools.
- `psm_google_calendar` MCP lists exactly `read_customer_calendar_context` when Google Calendar is enabled.
- Google Calendar OAuth is configured for `team@staffany.com` with `calendar.readonly`, returns bounded event metadata, and exposes no mutation or attendee-export tools.
- `validate_jira_configuration` reports thin POC defaults or full configured fields and request types, including `PS Team`.
- C360 internal API token is configured.
- Rock Productions C360 lookup smoke passes for `proj-cs-rockproductions`, including normalized variants, HubSpot company `8051493928`, and StaffAny org `Rock Productions`.
- Cron concurrency is capped with `cron.max_parallel_jobs: 1`.
- Reminder cron is enabled in cloud and uses Jira `duedate` only.
- VM-local cloud heartbeat cron is enabled every 15 minutes with local delivery disabled.
- PS WEE adoption digest cron is enabled as a no-agent weekday Slack automation with the `PSM Ops automation:` prefix.
- Healthy no-agent checks print nothing and exit 0.

## Commands

Run source-packet verification from the repo root:

```bash
npm run psm-ops-bot:verify
```

Run live health check on the cloud host:

```bash
apps/psm-ops-bot/runtime/check-health.sh
```

Run VM-local cloud heartbeat on the cloud host:

```bash
apps/psm-ops-bot/runtime/check-cloud-heartbeat.sh
```

It checks local systemd user service state and Hermes cron metadata only. It does not call Jira, C360, Slack, or model paths.

Run live profile drift audit after syncing packet files:

```bash
apps/psm-ops-bot/runtime/audit-live-profile.sh
```

Run the live Rock Productions C360 lookup smoke after deploy:

```bash
apps/psm-ops-bot/runtime/smoke-rock-productions-c360.sh
```

Expected success output:

```text
c360:rock-productions:ok:hubspot=8051493928:org=Rock Productions
```

## Cron Pattern

Install automatic due-date reminders under the cloud profile:

```bash
hermes -p psmopsbot cron create "0 1 * * *" \
  --name "psmopsbot due-date reminders" \
  --prompt "PSM Ops automation: Check Jira PCO tasks due tomorrow, due today, and overdue as of now. Use list_due_pco_reminders with lead_days=1. Return only safe issue summaries and do not call Slack post APIs directly." \
  --deliver "slack:#ps-weeman-bot-test"

cp apps/psm-ops-bot/runtime/check-cloud-heartbeat.sh ~/.hermes/profiles/psmopsbot/scripts/psmopsbot-check-cloud-heartbeat.sh
hermes -p psmopsbot cron create "*/15 * * * *" \
  --name "psmopsbot local cloud heartbeat" \
  --script psmopsbot-check-cloud-heartbeat.sh \
  --no-agent

cp apps/psm-ops-bot/runtime/psm_ops_adoption_digest.py ~/.hermes/profiles/psmopsbot/scripts/psm_ops_adoption_digest.py
hermes -p psmopsbot cron create "0 2 * * 1-5" \
  --name "psmopsbot adoption digest" \
  --script psm_ops_adoption_digest.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"
```

The GCE host runs UTC, so `0 1 * * *` is 09:00 Asia/Singapore daily.

## Failure Behavior

On failure, print only the failing subsystem and next check. Do not print secrets, env values, raw logs, raw Slack messages, raw Jira comments, raw customer source data, phone numbers, or bulk exports. The Rock Productions C360 smoke may print `searched_variants`, `match_count`, `missing_mapping`, `confidence`, and `caveat` only.
