# Agent Builder

This repo now treats StaffAny Hermes Data Bot as the first app proper.

## Primary App

- Canonical app packet: `apps/hermes-data-bot/`
- Runtime: Hermes Agent profile `staffanydatabot`
- First surface: Slack POC in `#kaiyi-bot-testing`
- Data access: StaffAny BigQuery MCP proxy with a read-only tool allowlist
- Current GCP VM topology, including LaunchBot on `hermes-data-bot-poc`: `apps/hermes-data-bot/deploy/gcp-vm-topology.md`

Use the app packet as the source of truth for durable Hermes Data Bot behavior. The live Hermes profile can learn or drift during operations, but durable changes should be promoted back into this repo after review.

## Directory Map

| Path | Status | Purpose |
| --- | --- | --- |
| `apps/hermes-data-bot/` | primary | Source packet for StaffAny Hermes Data Bot. |
| `apps/nurtureany-sales-bot/` | app packet | Source packet for StaffAny NurtureAny Sales Bot. |
| `apps/bq-mcp-proxy/` | supporting | StaffAny-controlled BigQuery MCP proxy used by the bot. |
| `research/` | evidence | Raw notes, source notes, syntheses, decisions, and audits. |
| `agents/` | deprecated | Historical ChatGPT workspace-agent snapshots and migration evidence. |
| `skills/` | mixed | Repo-local planning/support skills; workspace-agent skills are legacy unless explicitly used. |
| `docs/` | repo docs | Product compass, documentation guide, and deprecation notes. |
| `infra/` | supporting | Infrastructure experiments and restore notes. |

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
