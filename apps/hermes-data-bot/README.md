# StaffAny Hermes Data Bot

Canonical app packet for StaffAny's Hermes runtime data bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `staffanydatabot`
- First surface: Slack POC in `#kaiyi-bot-testing`
- Model: ChatGPT subscription-backed model selected by runtime account auth
- BigQuery access: StaffAny BigQuery MCP proxy, read-only allowlist
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/staffanydatabot/`
- Slack scope policy: `groups:read` is intentionally not required for the POC.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled copy of the profile soul prompt. |
| `profile/config.template.yaml` | Non-secret profile config template. |
| `skills/staffany-data-bot/` | Hermes skill and progressive-disclosure references. |
| `runtime/mcp/staffany-bigquery.md` | BigQuery MCP contract and restore notes. |
| `runtime/memory-honcho.md` | Honcho external-memory contract and boundaries. |
| `runtime/slack.md` | Slack gateway behavior, scopes, and run gate. |
| `runtime/health-checks.md` | No-agent operational checks and expected silence. |
| `deploy/gce-onboarding-runbook.md` | GCE restore and bootstrap runbook. |
| `tests/regression-cases.md` | Manual/eval regression cases for app behavior. |

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `staffanydatabot` profile.
3. Copy `profile/SOUL.md` into the profile's `SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Copy `skills/staffany-data-bot/` into the profile skills directory.
6. Set profile `.env` from Secret Manager values only; do not add an OpenAI API key or model provider for model auth.
7. Ensure the runtime account auth is logged in, then configure Slack gateway and StaffAny BigQuery MCP.
8. Configure Honcho only after its self-hosted API, embeddings provider, and profile-local config are healthy.
9. Run the health checks and regression cases before widening access.

## Canonical Source Rule

The live Hermes profile may accumulate local state and runtime learning. Treat that as unreviewed drift until the specific useful change is copied back here and committed.
