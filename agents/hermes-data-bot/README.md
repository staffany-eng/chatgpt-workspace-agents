# Hermes Data Bot

Local source-controlled setup packet for a Hermes runtime version of StaffAny Da Ta Bot.

- Target runtime: Hermes Agent.
- Target profile name: `staffanydatabot`.
- First rollout surface: Slack POC in `#kaiyi-bot-testing`.
- Infra target: company GCP, GCE `e2-small`, persistent disk, systemd-managed Hermes gateway.
- BigQuery access: existing StaffAny BigQuery MCP proxy, read-only tool allowlist.

## Current POC Deployment

- VM: `hermes-data-bot-poc` in `staffany-warehouse/asia-southeast1-a`.
- Machine: `e2-small`, Debian 12, 30GB `pd-balanced`.
- Service account: `hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com`.
- Network: `hermes-data-bot` tag, IAP SSH allow plus tag-scoped public SSH deny.
- VM profile path: `~/.hermes/profiles/staffanydatabot`.
- VM repo packet path: `~/agent-builder/agents/hermes-data-bot`.
- Model auth: `OPENAI_API_KEY` from Secret Manager `hermes-data-bot-openai-api-key`.
- Model: `gpt-5.5` through Hermes `custom` provider at `https://api.openai.com/v1`.
- Gateway service: `hermes-gateway-staffanydatabot.service`, enabled and running.
- Gateway env: systemd drop-in `~/.config/systemd/user/hermes-gateway-staffanydatabot.service.d/env.conf` loads the profile `.env`.
- Slack busy mode: `display.busy_input_mode: queue`, so follow-up messages wait instead of interrupting long BigQuery runs.

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or restore the `staffanydatabot` profile.
3. Apply `SOUL.md` to the profile.
4. Install `skills/staffany-data-bot/`.
5. Copy files from `files/` into the skill `references/`.
6. Configure the `staffany_bigquery` MCP server with env-var backed auth.
7. Generate and apply the Slack manifest.
8. Set Slack tokens and allowed users in the profile `.env`.
9. Run MCP, CLI, and Slack regression tests before broader rollout.
