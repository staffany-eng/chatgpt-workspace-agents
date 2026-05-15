# StaffAny Hermes Data Bot

Canonical app packet for StaffAny's Hermes runtime data bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `staffanydatabot` on `hermes-data-bot-poc` only; do not create or run a Mac-local `staffanydatabot` profile.
- First surface: Slack POC in `#da-ta-hermz-testing`
- Selected source-thread reads: explicit public Slack permalinks from configured channel IDs only, using the Da Ta Hermz bot token
- Model: Anthropic provider, `claude-sonnet-4-6`, configured in the live profile
- BigQuery access: StaffAny BigQuery MCP proxy, read-only allowlist
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/staffanydatabot/` on `hermes-data-bot-poc`
- Slack scope policy: `groups:read` is intentionally not required for the POC.

## Current GCP Topology

See `deploy/gcp-vm-topology.md` before changing deployed bot placement or answering where a bot runs. Current live topology includes:

- `staffanydatabot` on `hermes-data-bot-poc`
- `launchbot` on `hermes-data-bot-poc`
- `psmopsbot` on `hermes-psm-ops-bot-poc`
- `nurtureanysalesbot` on `nurtureany-sales-bot-prod`

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled copy of the profile soul prompt. |
| `profile/config.template.yaml` | Non-secret profile config template. |
| `skills/staffany-data-bot/` | Hermes skill and progressive-disclosure references. |
| `runtime/mcp/staffany-bigquery.md` | BigQuery MCP contract and restore notes. |
| `runtime/mcp/staffany_slack_context_server.py` | Read-only selected Slack thread context MCP using `SLACK_BOT_TOKEN`. |
| `runtime/jira-release-sync.md` | Jira release-feature registry sync and review workflow. |
| `runtime/high-priority-feature-digest.md` | Weekly high-priority release-feature usage digest setup. |
| `runtime/memory-honcho.md` | Honcho external-memory contract and boundaries. |
| `runtime/slack.md` | Slack gateway behavior, scopes, and run gate. |
| `runtime/update-slack-allowlist.sh` | Safe live-profile helper for adding Slack POC users. |
| `runtime/health-checks.md` | No-agent operational checks and expected silence. |
| `runtime/check-cloud-heartbeat.sh` | VM-local no-agent heartbeat for StaffAny Data Bot, LaunchBot, and cron metadata. |
| `runtime/staffanydatabot-cloud-doctor.sh` | Redacted VM/profile doctor for service state, cron metadata, MCP counts, and selected Slack-thread access. |
| `deploy/gcp-vm-topology.md` | Current GCP VM/profile/service ownership, including LaunchBot. |
| `deploy/gce-onboarding-runbook.md` | GCE restore and bootstrap runbook. |
| `tests/regression-cases.md` | Manual/eval regression cases for app behavior. |
| `tests/prompt-evals.json` | Machine-readable static, tool-trace, answer-contract, and live-smoke prompt eval specs. |

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `staffanydatabot` profile on `hermes-data-bot-poc` only. If a Mac-local `~/.hermes/profiles/staffanydatabot` exists, archive/delete it before live Slack testing.
3. Copy `profile/SOUL.md` into the profile's `SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Copy `skills/staffany-data-bot/` into the profile skills directory.
6. Set profile `.env` from Secret Manager values only; do not commit model, Slack, or MCP credentials.
7. Ensure Anthropic model auth is logged in, then configure Slack gateway and StaffAny BigQuery MCP.
8. Configure the `staffany_slack_context` MCP only for selected public/source channel IDs; default to the home channel unless an explicit source-read channel is reviewed.
9. Run the Jira release sync discovery and confirm the launch-priority field/value mapping before enabling feature usage tracking.
10. Configure the weekly high-priority feature usage digest only after the registry dry run is reviewed.
11. Configure Honcho only after its self-hosted API, embeddings provider, and profile-local config are healthy.
12. Run the health checks and regression cases before widening access.

## Deploy Flow

Routine deploys use the exact-ref wrapper from the repo root:

```bash
npm run hermes-data-bot:deploy
npm run hermes-data-bot:deploy -- --apply --ref HEAD
```

Without `--apply`, the wrapper performs local verification and prints the target SHA only. With `--apply`, it uploads an exact git archive, verifies the packet on the VM, syncs source-owned files into `~/.hermes/profiles/staffanydatabot/`, restarts only `hermes-gateway-staffanydatabot.service`, stamps `VERSION`, then runs live audit, health, heartbeat, and cloud doctor.

## Canonical Source Rule

The live Hermes profile may accumulate local state and runtime learning. Treat that as unreviewed drift until the specific useful change is copied back here and committed.
