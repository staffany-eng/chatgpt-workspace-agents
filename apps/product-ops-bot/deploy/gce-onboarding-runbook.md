# GCE Onboarding Runbook (Template)

Use this template to deploy Product Ops Bot on GCE.

## Target

- Project: `staffany-warehouse`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- Runtime profile: `productopsbot`

## Steps

1. Provision VM with least-privilege service account.
2. Install Hermes and verify `hermes doctor`.
3. Create profile `productopsbot`.
4. Copy packet files (`SOUL.md`, config, skills) into profile.
5. Load secrets from Secret Manager to profile `.env`.
6. Configure gateway and MCP servers.
7. Install/enable `hermes-gateway-productopsbot.service`.
8. Run health checks and Slack smoke test.


## Automated Deploy

```bash
npm run product-ops-bot:deploy -- --apply \
  --project staffany-warehouse \
  --zone asia-southeast1-a \
  --vm hermes-product-ops-bot-poc \
  --profile productopsbot \
  --runtime-owner leekaiyi \
  --ref origin/main
```

For preview only (no remote changes):

```bash
npm run product-ops-bot:deploy
```
