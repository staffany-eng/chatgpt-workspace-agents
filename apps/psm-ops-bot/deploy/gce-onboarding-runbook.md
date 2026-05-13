# GCE Onboarding Runbook

This runbook deploys PSM Ops Bot on company cloud infrastructure. Do not run the production Slack gateway from a laptop.

## Target

- Project: `staffany-warehouse`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- VM: `hermes-psm-ops-bot-poc`
- Profile: `psmopsbot`
- Gateway service: `hermes-gateway-psmopsbot.service`
- Slack channel: `#ps-weeman-bot-test`

## Secrets

Store these in Secret Manager and load them into the profile `.env` on the cloud host:

- `psm-ops-bot-slack-bot-token`
- `psm-ops-bot-slack-app-token`
- `customer-360-jira-email`
- `customer-360-jira-api-token`
- `customer-360-internal-api-token`
- `hermes-data-bot-anthropic-api-key`

Thin POC does not require `SLACK_ALLOWED_USERS` or a PSM Ops access-policy file. The bot resolves the caller by Slack email through Jira user search. Keep the Slack gateway surface limited to `#ps-weeman-bot-test`.

Thin POC Jira IDs must also be present in the profile `.env`:

- `PSM_OPS_JIRA_MODE=thin_poc`
- `PSM_OPS_JIRA_SERVICE_DESK_ID`
- `PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION`
- `PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK`
- `PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE`
- `PSM_OPS_JIRA_FIELD_STAFFANY_ORGS`
- `PSM_OPS_JIRA_FIELD_PS_TEAM`

Handoff Package intentionally returns a blocked response until PCO has the missing request type. Reminder automation uses Jira `duedate`; no separate reminder field is required in thin POC.

## VM Bootstrap

```bash
gcloud compute instances create hermes-psm-ops-bot-poc \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-balanced \
  --service-account=<least-privilege-service-account> \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=hermes-psm-ops-bot
```

Use the dedicated service account:

```bash
hermes-psm-ops-bot@staffany-warehouse.iam.gserviceaccount.com
```

Install Hermes on the VM:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
hermes doctor
```

## Profile Setup

```bash
hermes profile create psmopsbot --clone
hermes -p psmopsbot config set terminal.cwd "$HOME/agent-builder/apps/psm-ops-bot"
```

Copy packet files:

```bash
mkdir -p ~/.hermes/profiles/psmopsbot/skills
cp apps/psm-ops-bot/profile/SOUL.md ~/.hermes/profiles/psmopsbot/SOUL.md
rsync -a --delete apps/psm-ops-bot/skills/psm-ops-bot/ ~/.hermes/profiles/psmopsbot/skills/psm-ops-bot/
```

Configure model:

```yaml
model:
  default: claude-sonnet-4-6
  provider: anthropic
agent:
  api_max_retries: 3
```

Install gateway as a user systemd service and load the profile `.env`:

```ini
# ~/.config/systemd/user/hermes-gateway-psmopsbot.service.d/env.conf
[Service]
EnvironmentFile=/home/leekaiyi/.hermes/profiles/psmopsbot/.env
```

Restart:

```bash
systemctl --user daemon-reload
systemctl --user restart hermes-gateway-psmopsbot.service
```

## Cron

Install automatic due-date reminders on the cloud host only:

```bash
hermes -p psmopsbot cron create "0 1 * * *" \
  --name "psmopsbot due-date reminders" \
  --prompt "PSM Ops automation: Check Jira PCO tasks due tomorrow, due today, and overdue as of now for #ps-weeman-bot-test. Use list_due_pco_reminders with lead_days=1. Return only safe issue summaries and do not call Slack post APIs directly." \
  --deliver "slack:#ps-weeman-bot-test"
```

The GCE host runs UTC, so `0 1 * * *` is 09:00 Asia/Singapore daily.

## Verification

```bash
npm run psm-ops-bot:verify
apps/psm-ops-bot/runtime/check-health.sh
apps/psm-ops-bot/runtime/audit-live-profile.sh
```

Cloud smoke:

1. Mention the bot in `#ps-weeman-bot-test` and list own tasks.
2. Draft and approve-create one PCO test task.
3. Transition it to Scheduled.
4. Add an internal comment.
5. Ask for due-date reminders and verify `list_due_pco_reminders` returns due tomorrow, due today, and overdue tasks only while not Done.
6. Ask one C360 customer question and verify a C360 link/citation appears.
