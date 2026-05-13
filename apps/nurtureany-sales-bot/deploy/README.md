# NurtureAny Production Deploy

NurtureAny deploys by syncing this repo packet into the live Hermes profile on the production VM, then restarting the NurtureAny Hermes gateway. There is no GitHub Actions deploy for this app.

## Production Target

- GCP project: `staffany-warehouse`
- Zone: `asia-southeast1-a`
- VM: `nurtureany-sales-bot-prod`
- Hermes profile: `nurtureanysalesbot`
- Gateway service: `hermes-gateway-nurtureanysalesbot.service`
- Live profile path: `~/.hermes/profiles/nurtureanysalesbot/`

## Routine Deploy Flow

Run locally first:

```bash
cd /Users/khaidarsyah/Developer/Works/staffany/chatgpt-workspace-agents
npm run nurtureany-sales-bot:verify
```

SSH to prod:

```bash
gcloud compute ssh nurtureany-sales-bot-prod \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --tunnel-through-iap
```

On the VM, from the repo checkout:

```bash
cd ~/agent-builder
git status --short --branch
git pull --ff-only origin main
npm run nurtureany-sales-bot:verify

mkdir -p ~/.hermes/profiles/nurtureanysalesbot/scripts
mkdir -p ~/.hermes/profiles/nurtureanysalesbot/source

rsync -a --delete apps/nurtureany-sales-bot/ \
  ~/.hermes/profiles/nurtureanysalesbot/source/nurtureany-sales-bot/

cp apps/nurtureany-sales-bot/profile/SOUL.md \
  ~/.hermes/profiles/nurtureanysalesbot/SOUL.md

rsync -a --delete apps/nurtureany-sales-bot/skills/nurtureany-sales-bot/ \
  ~/.hermes/profiles/nurtureanysalesbot/skills/nurtureany-sales-bot/

cp apps/nurtureany-sales-bot/runtime/check-health.sh \
  ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-health.sh
cp apps/nurtureany-sales-bot/runtime/audit-live-profile.sh \
  ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-audit-live-profile.sh
cp apps/nurtureany-sales-bot/runtime/check-slack-socket-health.sh \
  ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-slack-socket-health.sh
cp apps/nurtureany-sales-bot/runtime/nurtureany-cloud-doctor.sh \
  ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-cloud-doctor.sh

systemctl --user restart hermes-gateway-nurtureanysalesbot.service
```

Verify after restart:

```bash
apps/nurtureany-sales-bot/runtime/audit-live-profile.sh
apps/nurtureany-sales-bot/runtime/check-health.sh
apps/nurtureany-sales-bot/runtime/nurtureany-cloud-doctor.sh
systemctl --user status hermes-gateway-nurtureanysalesbot.service --no-pager
```

`check-health.sh` should print nothing on success. `audit-live-profile.sh` should end with `live-profile:audit-ok`.

## What Deploy Syncs

- `profile/SOUL.md` to the live profile `SOUL.md`
- `skills/nurtureany-sales-bot/` to the live profile skill directory
- the app packet to `~/.hermes/profiles/nurtureanysalesbot/source/nurtureany-sales-bot/`
- runtime health/audit/watchdog/cloud-doctor scripts to the live profile `scripts/`

## What Deploy Must Not Touch

- `~/.hermes/profiles/nurtureanysalesbot/.env`
- Secret Manager values
- Slack bot/app tokens
- HubSpot private app token
- Google OAuth token/client secret files
- Eazybe, Luma, Exa, Lusha, Tavily, Google Places, or Anthropic keys
- the runtime-only access policy file pointed to by `NURTUREANY_ACCESS_POLICY_PATH`
- raw Slack transcripts, HubSpot rows, contact exports, or other private runtime data

## First-Time Setup

Routine deploy assumes the VM and profile are already bootstrapped. First-time setup also needs:

- live `.env` / Secret Manager values
- `NURTUREANY_ACCESS_POLICY_PATH` pointing to a runtime-only policy file
- Slack Socket Mode app and bot token
- Anthropic model auth
- HubSpot and BigQuery credentials
- optional Calendar, Drive, Luma, Eazybe, Exa, Lusha, Tavily, and Google Places credentials for enabled tools
- no-agent cron jobs from `runtime/health-checks.md`

Do not put real secrets or the real sales roster in this repo.

## Troubleshooting

- If SSH fails, verify `gcloud auth list`, project `staffany-warehouse`, IAP access, and OS Login.
- If `git pull --ff-only` fails, do not deploy; resolve the VM checkout state first.
- If local changes are not merged to `main`, the VM cannot deploy them through the normal `git pull` path.
- If gateway restart succeeds but health fails, use the first failing subsystem from `check-health.sh` or the redacted output from `nurtureany-cloud-doctor.sh`.
- If Slack does not reply after a healthy service restart, check the gateway service and Slack Socket Mode health before changing source code.
