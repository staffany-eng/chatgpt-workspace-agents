# GCE Onboarding Runbook

This runbook sets up the Hermes runtime StaffAny Data Bot on company infra.

## Target

- Project: `staffany-warehouse`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- Machine: `e2-small`
- Disk: 20-30GB balanced persistent disk
- OS: Debian or Ubuntu LTS
- Runtime profile: `staffanydatabot`
- Slack rollout: `#kaiyi-bot-testing`, mention-only

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

The service account currently has Secret Manager access to `bq-mcp-proxy-shared-secret`.

Current secret access also includes:

- `hermes-data-bot-slack-app-token`
- `hermes-data-bot-slack-bot-token`
- `hermes-data-bot-slack-allowed-users`
- `hermes-data-bot-openai-api-key`

Current model profile:

- Provider: `custom`
- Base URL: `https://api.openai.com/v1`
- Model: `gpt-5.5`
- Env var: `OPENAI_API_KEY`
- Verification: VM Responses API probe returned HTTP 200 for `gpt-5.5`; Hermes one-shot returned `hermes-openai-ok`.

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
- `hermes-data-bot-openai-api-key`

The profile `.env` must contain:

```bash
SLACK_BOT_TOKEN=<xoxb token>
SLACK_APP_TOKEN=<xapp token>
SLACK_ALLOWED_USERS=<comma-separated Slack member IDs>
MCP_STAFFANY_BIGQUERY_API_KEY=<bq-mcp-proxy-shared-secret value>
OPENAI_API_KEY=<OpenAI service-account key>
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

Set the main model to route directly to OpenAI. Do not leave `provider: auto` for `gpt-5.5`; Hermes may route that model through OpenRouter, which requires `OPENROUTER_API_KEY`.

```yaml
model:
  default: gpt-5.5
  provider: custom
  base_url: https://api.openai.com/v1
```

For Slack, queue follow-up messages while the bot is busy. This avoids cancelling active BigQuery runs when someone adds context, tags a teammate, or says thanks in the same thread.

```yaml
display:
  busy_input_mode: queue
  busy_ack_enabled: true
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
```

Verify:

```bash
hermes -p staffanydatabot mcp test staffany_bigquery
```

Expected result: connected, 4 tools discovered.

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
- Direct MCP `execute_sql_readonly` probe with `SELECT 1 AS ok` returns a JSON-RPC result and no error
- `hermes -p staffanydatabot gateway status` is active after Slack and model auth are ready
- Slack first mention returns the plan-first message only
- Exact `run` executes the confirmed plan
- Secret request is refused
- Employee bank-account request is refused or requires explicit authorization and business purpose
