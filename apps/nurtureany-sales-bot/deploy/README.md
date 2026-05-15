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

Routine deploys should use the source-controlled deploy script from the repo root. Without `--apply`, it performs preflight and prints the target/SHA without uploading, syncing, restarting, or running prod checks.

```bash
cd /Users/khaidarsyah/Developer/Works/staffany/chatgpt-workspace-agents
npm run nurtureany-sales-bot:deploy
```

Deploy exact `origin/main` to production:

```bash
npm run nurtureany-sales-bot:deploy -- --apply
```

The script:

- fetches and deploys exact `origin/main`
- runs `npm run nurtureany-sales-bot:verify` locally and again on the VM archive
- uploads `/private/tmp/nurtureany-origin-main.tar.gz` and `/private/tmp/nurtureany-origin-main.sha`
- syncs only deploy-owned packet paths into `/home/leekaiyi/.hermes/profiles/nurtureanysalesbot`
- preserves runtime secrets/state, including `.env`, OAuth files, access policy, cron, logs, sessions, daily-runs, and operation-ledger
- optionally hydrates the live `.env` from the latest Secret Manager dotenv version when `--hydrate-secrets` is passed
- idempotently mirrors missing non-secret MCP server stanzas and tool allowlist entries from `profile/config.template.yaml` into live `config.yaml`
- restarts only `hermes-gateway-nurtureanysalesbot.service`
- runs live profile audit, health check, cloud doctor, and service status
- stamps `$profile/VERSION` with the deployed SHA, branch, and UTC timestamp

Useful options:

```bash
npm run nurtureany-sales-bot:deploy -- --apply --verbose
npm run nurtureany-sales-bot:deploy -- --apply --hydrate-secrets
npm run nurtureany-sales-bot:deploy -- --apply --hydrate-secrets --secret-name nurtureany-sales-bot-prod-env
npm run nurtureany-sales-bot:deploy -- --apply --skip-upload
npm run nurtureany-sales-bot:deploy -- --apply --skip-restart
```

Manual SSH fallback, if the script itself cannot run:

```bash
gcloud compute ssh nurtureany-sales-bot-prod \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --tunnel-through-iap
```

Use the repo helper for repeatable runtime checks. It resolves `gcloud` from common local install paths, handles GCP OS Login landing as a different user, and switches to the real Hermes runtime user `leekaiyi` with `XDG_RUNTIME_DIR` set:

```bash
node scripts/nurtureany-prod-ssh.mjs --status
node scripts/nurtureany-prod-ssh.mjs --health
node scripts/nurtureany-prod-ssh.mjs --socket
node scripts/nurtureany-prod-ssh.mjs --doctor
```

`check-health.sh` should print nothing on success. `audit-live-profile.sh` should end with `live-profile:audit-ok`.

## What Deploy Syncs

- `profile/SOUL.md` to the live profile `SOUL.md`
- `skills/nurtureany-sales-bot/` and `skills/target-account-news-scout/` to the live profile skill directory
- the app packet to `~/.hermes/profiles/nurtureanysalesbot/source/nurtureany-sales-bot/`
- runtime health/audit/watchdog/cloud-doctor scripts and HubSpot Task reminder scripts to the live profile `scripts/`

## What Deploy Must Not Touch

- `~/.hermes/profiles/nurtureanysalesbot/.env`, except when `--hydrate-secrets` explicitly replaces it from Secret Manager latest
- Secret Manager values
- Slack bot/app tokens
- HubSpot private app token
- Google OAuth token/client secret files
- Eazybe, Luma, Exa, Lusha, Prospeo, Tavily, Google Places, or Anthropic keys
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
- If a newly added env var is missing after a deploy, rerun with `--hydrate-secrets` after confirming the latest Secret Manager version contains the key. The script prints only `deploy:secrets=hydrated-latest` metadata and never prints dotenv values.
- If a newly added MCP server is missing in live `config.yaml`, deploy should print `deploy:config-added-mcp-server:<name>` and copy the non-secret template stanza before restart.
