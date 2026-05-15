# GCE Onboarding Runbook

This runbook sets up the Hermes runtime StaffAny Data Bot on company infra. For the full current multi-bot VM map, read `deploy/gcp-vm-topology.md` first.

## Target

- Project: `staffany-warehouse`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- Machine: `e2-small`
- Disk: 20-30GB balanced persistent disk
- OS: Debian or Ubuntu LTS
- Runtime profile: `staffanydatabot`
- Slack rollout: `#da-ta-hermz-testing` (`C0AU19E6T0C`), mention-only
- Selected public/source-thread reads: configured channel IDs only through `staffany_slack_context`, using the bot token.

## Current Multi-Bot VM Topology

The current GCP ownership map is maintained in `deploy/gcp-vm-topology.md`.

As of the latest verified topology, `hermes-data-bot-poc` hosts two active user-systemd gateway services:

- `hermes-gateway-staffanydatabot.service` for `staffanydatabot`
- `hermes-gateway-launchbot.service` for `launchbot`

Do not infer deployment from profile folders alone. Deployment means the matching `hermes-gateway-<profile>.service` is active or intentionally installed on that VM.

## Current POC Resources

- VM: `hermes-data-bot-poc`
- Status: `RUNNING`
- Machine: `e2-small`
- Disk: 30GB `pd-balanced`
- OS: Debian 12
- Internal IP: `10.148.0.3`
- External IP: `35.240.237.189`
- Service account: `hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com`
- Firewall allow: `hermes-data-bot-allow-iap-ssh`, priority `800`, source `35.235.240.0/20`, target tag `hermes-data-bot`, allow `tcp:22`
- Firewall deny: `hermes-data-bot-deny-public-ssh`, priority `900`, source `0.0.0.0/0`, target tag `hermes-data-bot`, deny `tcp:22`

The service account needs Secret Manager access to `bq-mcp-proxy-shared-secret`.

Required secret access also includes:

- `hermes-data-bot-slack-app-token`
- `hermes-data-bot-slack-bot-token`
- `hermes-data-bot-slack-allowed-users`

Model profile:

- Provider: `anthropic`
- Model: `claude-sonnet-4-6`
- Auth: Anthropic credential in the Hermes credential store or profile environment.
- API-key route: allowed for Anthropic only through the profile secret path; do not commit model credentials.
- Fallback: none. If Anthropic auth fails, the bot should block with an auth error instead of silently changing model/provider route.

Current gateway service:

- Unit: `hermes-gateway-staffanydatabot.service`
- Mode: user systemd service
- Env loading: drop-in `~/.config/systemd/user/hermes-gateway-staffanydatabot.service.d/env.conf` sets `EnvironmentFile=~/.hermes/profiles/staffanydatabot/.env`
- Slack busy input mode: `queue`
- Linger: enabled
- Status: running

## Secrets

Store these in Secret Manager, not in repo files:

- `hermes-data-bot-slack-bot-token`
- `hermes-data-bot-slack-app-token`
- `hermes-data-bot-slack-allowed-users`
- `bq-mcp-proxy-shared-secret`
- Jira API token for the release-feature sync operator, if the Jira sync runs on the VM
- Honcho server LLM provider key, if Honcho external memory is enabled

The profile `.env` must contain:

```bash
SLACK_BOT_TOKEN=<xoxb token>
SLACK_APP_TOKEN=<xapp token>
SLACK_ALLOWED_USERS=<comma-separated Slack member IDs>
MCP_STAFFANY_BIGQUERY_API_KEY=<bq-mcp-proxy-shared-secret value>
```

Selected Slack source-thread reads use non-secret channel allowlisting:

```bash
STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS=C0AU19E6T0C,C0A0V39AK44
```

If unset, the MCP falls back to `SLACK_HOME_CHANNEL`. Do not use this as an open-public-channel answering mode.

Use the source-packet helper for live-profile allowlist updates instead of hand-editing `.env`:

```bash
apps/hermes-data-bot/runtime/update-slack-allowlist.sh --restart <slack-user-id>
```

## VM Bootstrap

```bash
gcloud compute instances create hermes-data-bot-poc \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-balanced \
  --service-account=<least-privilege-service-account> \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=hermes-data-bot
```

Then SSH into the VM and install Hermes:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
hermes doctor
```

## Profile Setup

```bash
hermes profile create staffanydatabot --clone
hermes -p staffanydatabot config set terminal.cwd "$HOME/agent-builder"
```

Apply `SOUL.md` to:

```text
~/.hermes/profiles/staffanydatabot/SOUL.md
```

Copy the skill folder to:

```text
~/.hermes/profiles/staffanydatabot/skills/staffany-data-bot/
```

Authenticate the Anthropic provider, then set the main model to the intentional Anthropic route. Do not configure a custom OpenAI API fallback for this POC unless explicitly reverting model providers.

```bash
hermes -p staffanydatabot auth add anthropic
```

Complete the provider auth flow or install the Anthropic API key via the approved Secret Manager/profile-secret path. Do not paste credentials into repo files.

```yaml
model:
  default: claude-sonnet-4-6
  provider: anthropic
agent:
  api_max_retries: 3
```

## Model Resilience

The current POC intentionally has no model fallback:

- The primary provider is `anthropic:claude-sonnet-4-6`.
- `OPENAI_API_KEY` is absent from the profile `.env` so the gateway cannot accidentally route through OpenAI API billing.
- `fallback_providers` and `fallback_model` are absent. If Anthropic auth fails, re-authenticate it instead of falling back to another provider.

Current VM evidence:

```bash
hermes -p staffanydatabot fallback list
# Primary: claude-sonnet-4-6 (via anthropic)
# No fallback providers configured.
```

Verify model auth and the persisted model route:

```bash
hermes -p staffanydatabot auth status anthropic
CONFIG_PATH="$(hermes -p staffanydatabot config path)"
sed -n '1,4p' "$CONFIG_PATH"
```

Expected model config:

```yaml
model:
  default: claude-sonnet-4-6
  provider: anthropic
agent:
  api_max_retries: 3
```

If `hermes -p staffanydatabot auth status anthropic` reports logged out, check the profile credential state:

```bash
hermes -p staffanydatabot auth list
```

Then restart the gateway and check for fresh auth errors:

```bash
systemctl --user restart hermes-gateway-staffanydatabot.service
journalctl --user -u hermes-gateway-staffanydatabot.service --since "5 minutes ago" --no-pager \
  | grep -E 'AuthenticationError|HTTP 401|invalid.*credential|auth.*failed'
```

Restart after changing auth or model config:

```bash
systemctl --user restart hermes-gateway-staffanydatabot.service
hermes -p staffanydatabot auth status anthropic
hermes -p staffanydatabot fallback list
grep -q '^OPENAI_API_KEY=' ~/.hermes/profiles/staffanydatabot/.env && echo "unexpected api key"
```

For Slack, queue follow-up messages while the bot is busy. This avoids cancelling active BigQuery runs when someone adds context, tags a teammate, or says thanks in the same thread.

```yaml
display:
  busy_input_mode: queue
  busy_ack_enabled: true
  interim_assistant_messages: false
  platforms:
    slack:
      tool_progress: "off"
      streaming: false

slack:
  require_mention: true
  reactions: false
cron:
  max_parallel_jobs: 1
```

Install the user-systemd env drop-in after `hermes gateway install`, because Hermes may regenerate the main service file:

```ini
# ~/.config/systemd/user/hermes-gateway-staffanydatabot.service.d/env.conf
[Service]
EnvironmentFile=/home/leekaiyi/.hermes/profiles/staffanydatabot/.env
```

Then reload and restart:

```bash
systemctl --user daemon-reload
systemctl --user restart hermes-gateway-staffanydatabot.service
```

## MCP Config

Add this to `~/.hermes/profiles/staffanydatabot/config.yaml`:

```yaml
mcp_servers:
  staffany_bigquery:
    url: "https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp"
    headers:
      Authorization: "Bearer ${MCP_STAFFANY_BIGQUERY_API_KEY}"
    enabled: true
    timeout: 180
    connect_timeout: 60
    tools:
      include:
        - list_dataset_ids
        - list_table_ids
        - get_table_info
        - execute_sql_readonly
      resources: false
      prompts: false
  staffany_slack_context:
    command: "/home/leekaiyi/.hermes/hermes-agent/venv/bin/python"
    args:
      - "/home/leekaiyi/.hermes/profiles/staffanydatabot/source/hermes-data-bot/runtime/mcp/staffany_slack_context_server.py"
    env:
      SLACK_BOT_TOKEN: "${SLACK_BOT_TOKEN}"
      SLACK_HOME_CHANNEL: "${SLACK_HOME_CHANNEL}"
      STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS: "C0AU19E6T0C,C0A0V39AK44"
    tool_allowlist:
      - get_current_slack_thread_context
      - get_selected_slack_thread_context
```

Verify:

```bash
hermes -p staffanydatabot mcp test staffany_bigquery
```

Expected result: connected, 4 tools discovered.

## Jira Release Registry Sync

Jira is not a live Slack-answer source for this bot. Sync Jira release data into the reviewed registry first, then let Hermes answer from that registry plus BigQuery.

Discovery run:

```bash
JIRA_BASE_URL=<staffany-jira-url> \
JIRA_EMAIL=<sync-user-email> \
JIRA_API_TOKEN=<token-from-secret-store> \
apps/hermes-data-bot/runtime/sync-jira-release-registry.sh
```

Expected discovery result: the script prints launch-priority field candidates and exits with `sync:priority-mapping-needs-confirmation`.

After human review confirms the Jira custom field and high-priority values:

```bash
JIRA_BASE_URL=<staffany-jira-url> \
JIRA_EMAIL=<sync-user-email> \
JIRA_API_TOKEN=<token-from-secret-store> \
JIRA_LAUNCH_PRIORITY_FIELD_ID=customfield_12345 \
JIRA_LAUNCH_PRIORITY_FIELD_NAME="Launch Priority" \
JIRA_HIGH_PRIORITY_VALUES="P1 - High Reach Retention and Growth" \
apps/hermes-data-bot/runtime/sync-jira-release-registry.sh > /tmp/staffany-release-feature-registry.draft.md
```

Default JQL is `project = KER AND "Launch Priority" = "P1 - High Reach Retention and Growth" ORDER BY updated DESC`. Review the draft before copying safe rows into `skills/staffany-data-bot/references/staffany-release-feature-registry.md`. Mark high-priority rows as `track` only after `usage_metric_key` maps to a reviewed StaffAny metric.

## High-Priority Feature Usage Digest

Dry-run before enabling cron:

```bash
hermes -p staffanydatabot --skills staffany-data-bot \
  -z "$(cat apps/hermes-data-bot/runtime/prompts/high-priority-feature-usage-digest.md)"
```

Install the weekly Monday 9am SGT digest after the dry run is reviewed:

```bash
hermes -p staffanydatabot cron create "0 1 * * 1" \
  "$(cat apps/hermes-data-bot/runtime/prompts/high-priority-feature-usage-digest.md)" \
  --name "staffanydatabot high-priority release feature usage digest" \
  --skill staffany-data-bot \
  --deliver "slack:C0AU19E6T0C" \
  --workdir "$(pwd)/apps/hermes-data-bot"
hermes -p staffanydatabot cron list
```

The command above assumes a UTC deployment host. If `hermes cron list` shows next-run timestamps in `+08:00`, use `0 9 * * 1` instead. Use channel ID `C0AU19E6T0C` in the `--deliver` value and keep the cron name unchanged.

## Honcho Memory

Honcho is the external memory layer for confirmed reusable learning only. It does not replace StaffAny registries, BigQuery, Slack, GitHub, or Google Drive as sources of truth.

Runtime files stay outside the repo:

- Honcho server checkout and ignored `.env`
- `~/.hermes/profiles/staffanydatabot/honcho.json`
- Honcho Postgres and Redis volumes

Use profile-local Honcho config with:

```json
{
  "baseUrl": "http://127.0.0.1:8000",
  "hosts": {
    "hermes.staffanydatabot": {
      "workspace": "staffany-hermes-data-bot",
      "peerName": "kaiyi",
      "pinPeerName": true,
      "aiPeer": "staffanydatabot",
      "recallMode": "tools",
      "saveMessages": false,
      "sessionStrategy": "per-session"
    }
  }
}
```

Enable only after the self-hosted Honcho API and embeddings provider pass smoke checks:

```bash
curl -fsS http://localhost:8000/health
hermes -p staffanydatabot config set memory.provider honcho
hermes -p staffanydatabot memory status
```

If Honcho memory fails, disable the external provider and keep built-in memory active:

```bash
hermes -p staffanydatabot memory off
```

Review learned memories locally before promotion:

```bash
apps/hermes-data-bot/runtime/review-honcho-memory.sh --ids-only --limit 20
apps/hermes-data-bot/runtime/review-honcho-memory.sh --limit 20
```

Do not store the raw review output in this repo.

Install the Honcho backup watchdog:

```bash
cp apps/hermes-data-bot/runtime/backup-honcho.sh ~/.hermes/profiles/staffanydatabot/scripts/staffanydatabot-honcho-backup.sh
hermes -p staffanydatabot cron create "30 1 * * 1-5" \
  --name "staffanydatabot Honcho backup" \
  --script staffanydatabot-honcho-backup.sh \
  --no-agent
```

Backups are compressed Postgres dumps in `~/.hermes/backups/honcho/`.

## Slack Setup

Generate the Slack manifest:

```bash
hermes -p staffanydatabot slack manifest --write \
  --name "StaffAny Hermes Data Bot" \
  --description "StaffAny internal data analyst bot for Slack POC data questions."
```

Create or update the Slack app from the generated manifest, enable Socket Mode, install it, then store the Slack tokens in the profile `.env`.

Start gateway manually first:

```bash
hermes -p staffanydatabot gateway run
```

After manual Slack tests pass, install the service:

```bash
hermes -p staffanydatabot gateway install
hermes -p staffanydatabot gateway status
```

## Regression Checks

- `hermes -p staffanydatabot doctor`
- `hermes -p staffanydatabot skills list` shows `staffany-data-bot`
- `hermes -p staffanydatabot mcp test staffany_bigquery` discovers 4 tools
- `apps/hermes-data-bot/runtime/check-health.sh` prints nothing and exits 0 when gateway, MCP, redaction, and Honcho are healthy
- Direct MCP `execute_sql_readonly` probe with `SELECT 1 AS ok` returns a JSON-RPC result and no error
- `hermes -p staffanydatabot gateway status` is active after Slack and model auth are ready
- Slack first mention returns the plan-first message only
- Exact `run` executes the confirmed plan
- Secret request is refused
- Employee bank-account request is refused or requires explicit authorization and business purpose

## No-Agent Health Cron

Install the health script as a silent Hermes watchdog on the VM:

```bash
mkdir -p ~/.hermes/scripts
cp apps/hermes-data-bot/runtime/check-health.sh ~/.hermes/profiles/staffanydatabot/scripts/staffanydatabot-check-health.sh
hermes -p staffanydatabot cron create "0 1 * * 1-5" \
  --name "staffanydatabot health check" \
  --script staffanydatabot-check-health.sh \
  --no-agent
hermes -p staffanydatabot cron status
hermes -p staffanydatabot cron list
```

Healthy runs print nothing. Failures print only the failing subsystem, for example `mcp:staffany_bigquery-test-failed` or `memory:honcho-not-available`.

## Self-Improvement And GitHub

Hermes self-improvement is runtime-local by default. It can create or patch memories, skills, and profile files under `~/.hermes/profiles/staffanydatabot`, but those changes are not automatically in GitHub.

Use this operating model:

1. Prod can learn locally during conversations.
2. Treat local learning as a proposal, not the source of truth.
3. Promote durable changes manually into `apps/hermes-data-bot/`.
4. Commit and push the promoted packet to GitHub.
5. Rebuild prod from GitHub + Secret Manager when needed.

Do not let the Slack prod bot auto-push directly to `main`. For GitHub-backed self-improvement, use a controlled promotion job:

- Snapshot the profile first with `/snapshot create <label>`.
- Diff the runtime profile against the repo packet.
- Copy only non-secret, durable changes: `SOUL.md`, skill files, references, runbook notes, and safe config defaults.
- Run `npm run hermes-data-bot:verify` from the repo root.
- Open a PR, or commit a scoped change if the operator is allowed to land directly.
- After merge, pull the updated repo packet on the runtime host, re-sync the profile, restart the gateway, and run `apps/hermes-data-bot/runtime/audit-live-profile.sh`.

What belongs in GitHub:

- Instructions and `SOUL.md`
- Skills and reference files
- Manifest and non-secret config shape
- Restore/runbook decisions
- Regression cases

What stays out of GitHub:

- `.env` and API tokens
- Slack tokens and app tokens
- Model-provider credentials
- Raw session transcripts
- PII or employee-level data
- Temporary memories and one-off local state

Prod recovery rule: if the VM dies, recreate the VM, install Hermes, restore this packet, pull secrets from Secret Manager, and restart the gateway. Any runtime-only learning since the last promotion is considered disposable unless it was intentionally exported and committed.
