# Product Ops Bot

Canonical Hermes app packet for a Product Operations assistant bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `productopsbot`
- Surface: Slack mentions in product operations channels
- Model: Anthropic provider, `claude-sonnet-4-6`
- Primary systems (safe defaults): Slack + Jira only
- Primary skill flow: `product-ops-intake-linking`
- Supporting workflow skill: `staffany-product-delivery-workflow`
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/productopsbot/`

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled profile soul prompt. |
| `profile/config.template.yaml` | Non-secret Hermes profile config template. |
| `profile/.env.template` | Runtime env template for Slack, Anthropic, Jira, and Notion keys. |
| `skills/product-ops-bot/` | Hermes skill and references. |
| `skills/product-ops-intake-linking/` | Main Product Ops intake and linking flow. |
| `skills/staffany-product-delivery-workflow/` | Supporting delivery workflow and agent routing. |
| `runtime/slack.md` | Slack gateway behavior and output contract. |
| `runtime/jira.md` | Jira read-first contract with direct execution for explicit single-ticket writes. |
| `runtime/health-checks.md` | Operational checks and expected silence. |
| `runtime/check-health.sh` | No-agent runtime health check scaffold. |
| `runtime/audit-live-profile.sh` | Live profile drift audit scaffold. |
| `runtime/mcp/README.md` | MCP adapter contracts and expected tools. |
| `deploy/gce-onboarding-runbook.md` | Cloud deployment runbook template. |
| `tests/regression-cases.md` | Manual/eval regression cases. |

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `productopsbot` profile.
3. Copy `profile/SOUL.md` into the profile `SOUL.md`.
4. Apply `profile/config.template.yaml` with local runtime paths.
5. Copy `skills/product-ops-bot/` into the profile skills directory.
6. Set profile `.env` from Secret Manager values only.
7. Configure Slack gateway and Jira adapter only.
8. Run health checks and regression cases before widening access.

## Verification

Run from repo root:

```bash
npm run product-ops-bot:verify
npm run product-ops-bot:deploy
```

## Canonical Source Rule

Runtime profile state is not durable until reviewed and copied back into this app packet. Do not commit secrets, raw Slack transcripts, raw issue exports, or private docs dumps.
