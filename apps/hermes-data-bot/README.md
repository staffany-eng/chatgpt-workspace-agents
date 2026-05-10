# StaffAny Hermes Data Bot

Canonical app packet for StaffAny's Hermes runtime data bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `staffanydatabot`
- First surface: Slack POC in `#kaiyi-bot-testing`
- Model: Anthropic provider, `claude-sonnet-4-6`, configured in the live profile
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
| `runtime/jira-release-sync.md` | Jira release-feature registry sync and review workflow. |
| `runtime/high-priority-feature-digest.md` | Weekly high-priority release-feature usage digest setup. |
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
6. Set profile `.env` from Secret Manager values only; do not commit model, Slack, or MCP credentials.
7. Ensure Anthropic model auth is logged in, then configure Slack gateway and StaffAny BigQuery MCP.
8. Run the Jira release sync discovery and confirm the launch-priority field/value mapping before enabling feature usage tracking.
9. Configure the weekly high-priority feature usage digest only after the registry dry run is reviewed.
10. Configure Honcho only after its self-hosted API, embeddings provider, and profile-local config are healthy.
11. Run the health checks and regression cases before widening access.

## Canonical Source Rule

The live Hermes profile may accumulate local state and runtime learning. Treat that as unreviewed drift until the specific useful change is copied back here and committed.
