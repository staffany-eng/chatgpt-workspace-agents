# GCE Onboarding Runbook

This runbook deploys PSM Ops Bot on company cloud infrastructure. Do not run the production Slack gateway from a laptop.

## Target

- Project: `staffany-warehouse`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- VM: `hermes-psm-ops-bot-poc`
- Profile: `psmopsbot`
- Gateway service: `hermes-gateway-psmopsbot.service`
- Slack channel mode: public/open channels, mention required
- Local profile policy: cloud-only. Do not create or run `~/.hermes/profiles/psmopsbot` on a Mac operator host.

## Secrets

Store these in Secret Manager and load them into the profile `.env` on the cloud host:

- `psm-ops-bot-slack-bot-token`
- `psm-ops-bot-slack-app-token`
- `customer-360-jira-email`
- `customer-360-jira-api-token`
- `customer-360-internal-api-token`
- `hermes-data-bot-anthropic-api-key`
- Google Calendar OAuth JSON for `team@staffany.com` with `https://www.googleapis.com/auth/calendar.readonly`
- Google Calendar OAuth client secret JSON for the same StaffAny OAuth client

Thin POC does not require `SLACK_ALLOWED_USERS`, `SLACK_ALLOWED_CHANNELS`, or a PSM Ops access-policy file. The bot resolves the caller by fetching Slack users, canonicalizing profile email/name, and matching that identity to Jira `PS Team`. Jira user search is optional best-effort attribution, not the task-owner filter. Keep `slack.require_mention=true` so public/open-channel usage does not become free-response mode.

Thin POC Jira IDs must also be present in the profile `.env`:

- `PSM_OPS_JIRA_MODE=thin_poc`
- `PSM_OPS_JIRA_SERVICE_DESK_ID`
- `PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION`
- `PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK`
- `PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE`
- `PSM_OPS_JIRA_FIELD_STAFFANY_ORGS`
- `PSM_OPS_JIRA_FIELD_PS_TEAM`
- `GOOGLE_CALENDAR_TOKEN_FILE=/home/leekaiyi/.hermes/profiles/psmopsbot/google-calendar-token.json`
- `GOOGLE_CALENDAR_CLIENT_SECRET_FILE=/home/leekaiyi/.hermes/profiles/psmopsbot/google-calendar-client-secret.json`
- `GOOGLE_CALENDAR_ACCOUNT_EMAIL=team@staffany.com`
- `PSM_OPS_CENTRAL_SLACK_CHANNEL_ID` for bot-owned PS WEE central audit copies
- `PSM_OPS_CENTRAL_FETCH_SLACK_THREAD=true` if bounded source-thread transcript excerpts should be included
- `PSM_OPS_ADOPTION_METRICS_ENABLED=true` or `PSM_OPS_ADOPTION_METRICS_PATH` for adoption telemetry

ROI-direct Jira IDs must also be present before enabling RevOps / BD Ops / NYSS routing:

- `PSM_OPS_ROI_JIRA_PROJECT_KEY`
- `PSM_OPS_ROI_JIRA_SERVICE_DESK_ID`
- `PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID`
- `PSM_OPS_ROI_JIRA_FIELD_CUSTOMER`
- `PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY`
- `PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS`
- `PSM_OPS_ROI_JIRA_FIELD_REQUESTER`
- `PSM_OPS_ROI_JIRA_FIELD_REQUESTER_SLACK`
- `PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL`
- `PSM_OPS_ROI_JIRA_FIELD_PRIORITY`

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
mkdir -p ~/.hermes/profiles/psmopsbot/skills ~/.hermes/profiles/psmopsbot/hooks ~/.hermes/profiles/psmopsbot/scripts
cp apps/psm-ops-bot/profile/SOUL.md ~/.hermes/profiles/psmopsbot/SOUL.md
rsync -a --delete apps/psm-ops-bot/skills/psm-ops-bot/ ~/.hermes/profiles/psmopsbot/skills/psm-ops-bot/
rsync -a apps/psm-ops-bot/runtime/mcp/ ~/.hermes/profiles/psmopsbot/runtime/mcp/
rsync -a apps/psm-ops-bot/runtime/hooks/psm-ops-adoption-telemetry/ ~/.hermes/profiles/psmopsbot/hooks/psm-ops-adoption-telemetry/
cp apps/psm-ops-bot/runtime/scripts/psm_ops_adoption_digest.py ~/.hermes/profiles/psmopsbot/scripts/psm_ops_adoption_digest.py
```

Write the approved `team@staffany.com` OAuth files from Secret Manager to the paths configured above. Do not commit or paste those JSON files into the repo.

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

## Routine Deploy Flow

Routine deploys should use the source-controlled deploy script from the repo root. Without `--apply`, it performs preflight and prints the target/SHA without uploading, syncing, restarting, or running prod checks.

```bash
npm run psm-ops-bot:deploy
```

Deploy exact `origin/main` to the PSM Ops cloud host:

```bash
npm run psm-ops-bot:deploy -- --apply
```

The script:

- fetches and deploys exact `origin/main`
- runs `node scripts/verify-psm-ops-bot.mjs` locally before upload
- uploads SHA-scoped `/tmp/psm-ops-origin-main-<sha>.tar.gz` and `/tmp/psm-ops-origin-main-<sha>.sha` artifacts
- syncs only deploy-owned source packet paths into `/home/leekaiyi/agent-builder` and `~/.hermes/profiles/psmopsbot`
- preserves runtime secrets/state, including `.env`, auth, cron, logs, sessions, state DB, and gateway state
- restarts only `hermes-gateway-psmopsbot.service`
- runs live profile audit, health check, cloud heartbeat, and service status
- runs the Rock Productions C360 lookup smoke against the live Customer 360 API
- preserves and verifies the PS WEE no-agent adoption digest cron
- stamps `$profile/VERSION` with the deployed SHA, branch, and UTC timestamp

Useful options:

```bash
npm run psm-ops-bot:deploy -- --apply --verbose
npm run psm-ops-bot:deploy -- --apply --skip-upload
npm run psm-ops-bot:deploy -- --apply --skip-restart
```

## Cron

Install automatic due-date reminders on the cloud host only:

```bash
hermes -p psmopsbot cron create "0 1 * * *" \
  --name "psmopsbot due-date reminders" \
  --prompt "PSM Ops automation: Check Jira PCO tasks due tomorrow, due today, and overdue as of now for #ps-weeman-bot-test. Use list_due_pco_reminders with lead_days=1. Return only safe issue summaries and do not call Slack post APIs directly." \
  --deliver "slack:#ps-weeman-bot-test"

hermes -p psmopsbot cron create "0 2 * * 1-5" \
  --name "psmopsbot adoption digest" \
  --script psm_ops_adoption_digest.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"
```

The GCE host runs UTC, so `0 1 * * *` is 09:00 Asia/Singapore daily.

Install the no-agent PS WEE adoption digest:

```bash
cp apps/psm-ops-bot/runtime/psm_ops_adoption_digest.py ~/.hermes/profiles/psmopsbot/scripts/psm_ops_adoption_digest.py
hermes -p psmopsbot cron create "0 2 * * 1-5" \
  --name "psmopsbot adoption digest" \
  --script psm_ops_adoption_digest.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"
```

## Verification

```bash
npm run psm-ops-bot:verify
apps/psm-ops-bot/runtime/check-health.sh
apps/psm-ops-bot/runtime/audit-live-profile.sh
apps/psm-ops-bot/runtime/smoke-rock-productions-c360.sh
```

Cloud smoke:

1. Mention the bot in `#ps-weeman-bot-test` and one additional public/open channel, then list own tasks.
2. Draft and approve-create one PCO test task.
3. Transition it to Scheduled.
4. Add an internal comment.
5. Ask for due-date reminders and verify `list_due_pco_reminders` returns due tomorrow, due today, and overdue tasks only while not Done.
6. Ask for Rock Productions from a channel-style hint such as `proj-cs-rockproductions`; verify the bot finds `Rock Productions Pte Ltd`, shows the searched variants safely, and does not say a generic customer cannot be found.
7. Ask one calendar follow-up question and verify `psm_google_calendar.read_customer_calendar_context` returns bounded event metadata from `team@staffany.com` without descriptions, attendee emails, raw guest lists, or conference links.
8. Ask one C360 customer question and verify a C360 link/citation appears.
9. Create a PS WEE intake ticket from a non-home public channel and verify the same Slack thread gets the ticket link while the central ops channel gets a `PSM Ops automation:` audit copy with the source thread permalink.
10. Run `hermes -p psmopsbot insights --days 30 --source slack` and `hermes -p psmopsbot sessions stats` for native Hermes adoption checks.
