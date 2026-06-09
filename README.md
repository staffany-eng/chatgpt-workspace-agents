# Agent Builder

This repo now treats StaffAny Hermes Data Bot as the first app proper.

## Primary App

- Canonical app packet: `apps/hermes-data-bot/`
- Runtime: Hermes Agent profile `staffanydatabot`
- First surface: Slack POC in `#da-ta-hermz-testing`
- Data access: StaffAny BigQuery MCP proxy with a read-only tool allowlist
- Current GCP VM topology, including LaunchBot on `hermes-data-bot-poc`: `apps/hermes-data-bot/deploy/gcp-vm-topology.md`

Use the app packet as the source of truth for durable Hermes Data Bot behavior. The live Hermes profile can learn or drift during operations, but durable changes should be promoted back into this repo after review.

## Directory Map

| Path | Status | Purpose |
| --- | --- | --- |
| `apps/hermes-data-bot/` | primary | Source packet for StaffAny Hermes Data Bot. |
| `apps/product-ops-bot/` | app packet | Source packet scaffold for Product Ops Bot workflows. |
| `apps/nurtureany-sales-bot/` | app packet | Source packet for StaffAny NurtureAny Sales Bot. |
| `apps/launchbot/` | app packet | Source packet for Launchbot, including the help article, review, and Intercom draft workflow skill. |
| `apps/psm-ops-bot/` | moved | Tombstone only. PS WEE / PS Wee Manager / PSM Ops Bot is owned by `staffany-eng/customer-360` under `apps/psm-ops-bot/`. |
| `apps/hermes-shared/` | shared packet | Shared Hermes skills and MCPs reused by multiple StaffAny bots. |
| `apps/bq-mcp-proxy/` | supporting | StaffAny-controlled BigQuery MCP proxy used by the bot. |
| `research/` | evidence | Raw notes, source notes, syntheses, decisions, and audits. |
| `agents/` | deprecated | Historical ChatGPT workspace-agent snapshots and migration evidence. |
| `skills/` | mixed | Repo-local planning/support skills; workspace-agent skills are legacy unless explicitly used. |
| `docs/` | repo docs | Product compass, documentation guide, and deprecation notes. |
| `infra/` | supporting | Infrastructure experiments and restore notes. |
| `ops/hermes/` | operations | Hermes profile registry, channel map, and caretaker watchdog. |

## Slack Test Channels

The live smoke-test channel map lives in `ops/hermes/channels.md`.

- Da Ta Hermz: `#da-ta-hermz-testing` (`C0AU19E6T0C`)
- NurtureAny: `#nurtureany-testing` (`C0B2UGK4DB6`)
- PSM Ops / PS WEE: `#ps-weeman-bot-test` (`C0B2VT50YT1`)
- Launchbot: `#launch-bot-testing` (`C0B32M34J3W`); read-only KER lookup also runs in `#all-product-questions` (`C01RZ7SHC8K`)

`PS WEE` / `PS Wee Manager` is the PSM Ops Bot profile `psmopsbot`, now owned by Customer 360. Do not edit PS WEE behavior in Agent Builder; use `staffany-eng/customer-360` `apps/psm-ops-bot/`. Sales-manager and manager-chase workflow tests use NurtureAny in `#nurtureany-testing`.

## Verification

Run the focused app verification before treating the Hermes Data Bot packet as ready:

```bash
npm run hermes-data-bot:verify
```

Run the broader repo checks when changing research notes or MCP code:

```bash
npm run verify
```

## Safety

Do not commit secrets, `.env` files, OAuth tokens, Slack tokens, WhatsApp sessions, raw Slack transcripts, raw BigQuery query rows, or employee-level sensitive data.
