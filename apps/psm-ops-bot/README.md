# PSM Ops Hermes Bot

Canonical Hermes app packet for StaffAny PSM task and Customer 360 operations.

Alias note: `PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` refer to this existing `psmopsbot` app. Do not create a separate profile for those names.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `psmopsbot`
- Slack surface: mention-required usage in public/open StaffAny Slack channels
- Model: Anthropic provider, `claude-sonnet-4-6`
- Jira scope: dedicated PCO Jira Service Management project only
- Task ownership: Jira `PS Team`, matched from Slack users/profile identity
- Customer context scope: Customer 360 internal API, all customers in V1
- Source packet: this directory
- Cloud host: GCE VM `hermes-psm-ops-bot-poc` in `staffany-warehouse` / `asia-southeast1`

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled profile soul prompt. |
| `profile/config.template.yaml` | Non-secret Hermes profile config template. |
| `skills/psm-ops-bot/` | Hermes skill and references. |
| `runtime/mcp/psm_jira_server.py` | PCO Jira MCP adapter. |
| `runtime/mcp/psm_c360_server.py` | Customer 360 MCP adapter. |
| `runtime/mcp/psm_google_calendar_server.py` | Read-only Google Calendar adapter using `team@staffany.com`. |
| `runtime/mcp/psm_slack_notifier.py` | Bot-owned central Slack audit notifier for PS WEE lifecycle and blocked events. |
| `runtime/hooks/psm-ops-adoption-telemetry/` | Hermes gateway hook for adoption metrics. |
| `runtime/scripts/psm_ops_adoption_digest.py` | No-agent cron script for adoption digest delivery. |
| `runtime/jira.md` | Jira field, workflow, and safety contract. |
| `runtime/c360.md` | Customer 360 internal API contract. |
| `runtime/google-calendar.md` | Google Calendar read-only access contract. |
| `runtime/slack.md` | Slack gateway behavior and output contracts. |
| `runtime/health-checks.md` | Health, drift, and cron verification. |
| `runtime/check-health.sh` | No-agent live health check. |
| `runtime/check-cloud-heartbeat.sh` | VM-local no-agent heartbeat for gateway and cron metadata. |
| `runtime/audit-live-profile.sh` | Source-packet drift audit. |
| `deploy/gce-onboarding-runbook.md` | Cloud deployment runbook. |
| `tests/regression-cases.md` | Manual/eval regression cases. |

## Restore Order

1. Provision or access the GCE cloud host. Do not run the production gateway from a laptop.
2. Create or select Hermes profile `psmopsbot`.
3. Copy `profile/SOUL.md` into the profile `SOUL.md`.
4. Apply `profile/config.template.yaml` with real runtime paths and configured Jira field IDs.
5. Copy `skills/psm-ops-bot/` into the profile skills directory.
6. Set profile `.env` from Secret Manager values only.
7. Configure Slack, `psm_jira`, `psm_c360`, and `psm_google_calendar` MCP servers.
8. Install health, audit, and reminder cron jobs on the cloud host.
9. Run health checks and regression cases before widening access.

## Verification

Run from repo root:

```bash
npm run psm-ops-bot:verify
```

## Canonical Source Rule

Runtime profile state is not durable until reviewed and copied back into this app packet. Do not commit secrets, raw Slack transcripts, Jira comments, customer source packs, or personal session cookies.
