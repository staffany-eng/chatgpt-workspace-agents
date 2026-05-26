# PSM Ops Hermes Bot

Canonical Hermes app packet for StaffAny PSM task and Customer 360 operations.

Alias note: `PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` refer to this existing `psmopsbot` app. Do not create a separate profile for those names.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `psmopsbot` on cloud host only; do not create or run a Mac-local `psmopsbot` profile.
- Slack surface: mention-required usage in public/open StaffAny Slack channels
- Model: Anthropic provider, `claude-sonnet-4-6`
- Jira scope: PCO Jira Service Management for PS/customer work; ROI Jira Service Management for RevOps, BD Ops, NYSS, and ROI-board work
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
| `runtime/mcp/psm_jira_server.py` | PCO and ROI Jira MCP adapter. |
| `runtime/mcp/psm_c360_server.py` | Customer 360 MCP adapter. |
| `runtime/mcp/psm_google_calendar_server.py` | Read-only Google Calendar adapter using `team@staffany.com`. |
| `runtime/mcp/psm_slack_notifier.py` | Bot-owned central Slack audit notifier for PS WEE lifecycle and blocked events. |
| `runtime/hooks/psm-ops-adoption-telemetry/` | Hermes gateway hook for adoption metrics. |
| `runtime/hooks/psm-ops-mention-guard/` | Post-hoc Hermes hook that pings the central audit channel when a Slack reply mentions a non-tagger (SCHE-19904). |
| `runtime/psm_ops_adoption_digest.py` | No-agent cron script for adoption digest delivery. |
| `runtime/scripts/psm_ops_due_date_reminders.py` | No-agent Jira PCO due-date reminder digest script. |
| `runtime/scripts/psm_ops_pco_assignment_hygiene.py` | No-agent Jira PCO assignee, PS Team, and due-date hygiene digest script. |
| `runtime/scripts/psm_ops_roi_tracker_sync.py` | No-agent ROI-to-PCO customer-loop tracker sync script. |
| `runtime/scripts/psm_ops_churn_reporting_chase.py` | No-agent BigQuery churn reporting cleanup chase script for account management. |
| `runtime/sql/psm_ops_churn_projection_dashboard_292.sql` | Repo-owned BigQuery SQL port of Metabase Dashboard 292 churn classification. |
| `runtime/scripts/psm_ops_join_public_channels.py` | Bot-owned public/open Slack channel membership repair script. |
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
| `tests/prompt-evals.json` | Machine-readable static, tool-trace, answer-contract, and live-smoke prompt eval specs. |

## Runtime Secrets

ROI-direct Jira config is durable in Secret Manager as:

```text
projects/1093387803298/secrets/psm-ops-bot-roi-jira-env
```

The secret is in project `staffany-warehouse`, uses dotenv format, and is labeled
`app=psm-ops-bot`, `env=prod`, `format=dotenv`, `scope=roi-jira`. It contains only
`PSM_OPS_ROI_*` runtime config. Do not copy secret values into this repo.

Hydrate it on `hermes-psm-ops-bot-poc` after the base profile `.env` exists:

```bash
gcloud secrets versions access latest \
  --project=staffany-warehouse \
  --secret=psm-ops-bot-roi-jira-env \
  >> ~/.hermes/profiles/psmopsbot/.env
chmod 600 ~/.hermes/profiles/psmopsbot/.env
```

## Restore Order

1. Provision or access the GCE cloud host. Do not run the production gateway from a laptop.
2. Create or select Hermes profile `psmopsbot` on `hermes-psm-ops-bot-poc` only. If a Mac-local `~/.hermes/profiles/psmopsbot` exists, delete or archive it before testing so Slack cannot hit stale local state.
3. Copy `profile/SOUL.md` into the profile `SOUL.md`.
4. Apply `profile/config.template.yaml` with real runtime paths and configured Jira field IDs.
5. Copy `skills/psm-ops-bot/` into the profile skills directory.
6. Set profile `.env` from Secret Manager values only, including `psm-ops-bot-roi-jira-env` for ROI-direct routing.
7. Configure Slack, `psm_jira`, `psm_c360`, and `psm_google_calendar` MCP servers.
8. Copy `runtime/sql/` into the profile runtime directory for no-agent BigQuery scripts.
9. Install health, audit, reminder, assignment hygiene, ROI tracker sync, and churn reporting cron jobs on the cloud host.
10. Run health checks and regression cases before widening access.

## Verification

Run from repo root:

```bash
npm run psm-ops-bot:verify
```

## Canonical Source Rule

Runtime profile state is not durable until reviewed and copied back into this app packet. Do not commit secrets, raw Slack transcripts, Jira comments, customer source packs, or personal session cookies.
