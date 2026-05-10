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

The service account needs Secret Manager access to `bq-mcp-proxy-shared-secret`.

Required secret access also includes:

- `hermes-data-bot-slack-app-token`
- `hermes-data-bot-slack-bot-token`
- `hermes-data-bot-slack-allowed-users`

Model profile:

- Provider: `openai-codex`
- Model: `gpt-5.3-codex`
- Auth: `all@staffany.com` ChatGPT/Codex OAuth
- API-key route: disabled; do not set `OPENAI_API_KEY` in this profile unless explicitly reverting to API billing.
- Fallback: none. If Codex OAuth is invalidated, the bot should block with an auth error instead of falling back to OpenAI API TPM.

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
- Honcho server LLM provider key, if Honcho external memory is enabled

The profile `.env` must contain:

```bash
SLACK_BOT_TOKEN=<xoxb token>
SLACK_APP_TOKEN=<xapp token>
SLACK_ALLOWED_USERS=<comma-separated Slack member IDs>
MCP_STAFFANY_BIGQUERY_API_KEY=<bq-mcp-proxy-shared-secret value>
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

Authenticate `all@staffany.com` for the Codex OAuth provider, then set the main model to use that ChatGPT subscription route. Do not configure a `custom` OpenAI API fallback for this POC unless explicitly reverting to API billing.

```bash
hermes -p staffanydatabot auth add openai-codex --type oauth --no-browser --label all-staffany-primary
```

Complete the browser/device login as `all@staffany.com`. If the command hangs without printing the login URL in a headless SSH session, run it with a TTY or from an interactive VM shell.

```yaml
model:
  default: gpt-5.3-codex
  provider: openai-codex
agent:
  api_max_retries: 0
```

## Model Resilience

The current POC intentionally has no model fallback:

- The primary provider is `openai-codex:gpt-5.3-codex` using `all@staffany.com` ChatGPT/Codex OAuth.
- `OPENAI_API_KEY` is absent from the profile `.env` so the gateway cannot burn OpenAI API TPM.
- `fallback_providers` and `fallback_model` are absent. If Codex OAuth fails, re-authenticate it instead of falling back to API.

Current VM evidence:

```bash
hermes -p staffanydatabot fallback list
# Primary: gpt-5.3-codex (via openai-codex)
# No fallback providers configured.
```

If Codex OAuth is invalidated, re-authenticate `all@staffany.com`:

```bash
hermes -p staffanydatabot auth add openai-codex --type oauth --no-browser --label all-staffany-primary
```

Do not copy a personal Codex auth file into the VM; verify the token belongs to `all@staffany.com`.

Choose the ChatGPT/Codex account path and complete the browser/device login as the StaffAny ChatGPT subscription account. If the command hangs without printing the login URL in a headless SSH session, run it from an interactive VM shell or first log in with Codex CLI on a trusted machine and copy only the intended StaffAny account auth into the VM.

Verify model auth and the persisted model route:

```bash
hermes -p staffanydatabot auth status openai-codex
CONFIG_PATH="$(hermes -p staffanydatabot config path)"
sed -n '1,4p' "$CONFIG_PATH"
```

Expected model config:

```yaml
model:
  default: gpt-5.3-codex
  provider: openai-codex
agent:
  api_max_retries: 0
```

If `hermes -p staffanydatabot auth status openai-codex` reports logged out while the global Hermes auth reports logged in, check for a stale profile-local credential:

```bash
hermes -p staffanydatabot auth list
```

If the profile has an `openai-codex` credential marked `token_invalidated`, remove that profile-local credential so the profile can fall back to the valid global credential:

```bash
hermes -p staffanydatabot auth remove openai-codex 1
hermes -p staffanydatabot auth status openai-codex
```

If Hermes immediately re-seeds the invalid profile-local credential, back up the profile auth file and remove only the profile-local `openai-codex` credential-pool entry. Do not edit the global `~/.hermes/auth.json` credential:

```bash
PROFILE_AUTH=~/.hermes/profiles/staffanydatabot/auth.json
cp "$PROFILE_AUTH" "$PROFILE_AUTH.bak.$(date -u +%Y%m%dT%H%M%SZ)"
python3 - <<'PY'
import json
from pathlib import Path

p = Path.home() / ".hermes/profiles/staffanydatabot/auth.json"
d = json.loads(p.read_text())
(d.get("credential_pool") or {}).pop("openai-codex", None)
suppressed = d.get("suppressed_sources")
if isinstance(suppressed, dict):
    suppressed.pop("openai-codex", None)
    if not suppressed:
        d.pop("suppressed_sources", None)
p.write_text(json.dumps(d, indent=2) + "\n")
p.chmod(0o600)
PY
hermes -p staffanydatabot auth status openai-codex
```

Then restart the gateway and check for fresh auth errors:

```bash
systemctl --user restart hermes-gateway-staffanydatabot.service
journalctl --user -u hermes-gateway-staffanydatabot.service --since "5 minutes ago" --no-pager \
  | grep -E 'token_invalidated|No Codex credentials|AuthenticationError|HTTP 401'
```

Restart after changing auth or model config:

```bash
systemctl --user restart hermes-gateway-staffanydatabot.service
hermes -p staffanydatabot auth status openai-codex
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
3. Promote durable changes manually into `agents/hermes-data-bot/`.
4. Commit and push the promoted packet to GitHub.
5. Rebuild prod from GitHub + Secret Manager when needed.

Do not let the Slack prod bot auto-push directly to `main`. For GitHub-backed self-improvement, use a controlled promotion job:

- Snapshot the profile first with `/snapshot create <label>`.
- Diff the runtime profile against the repo packet.
- Copy only non-secret, durable changes: `SOUL.md`, skill files, references, runbook notes, and safe config defaults.
- Open a PR or commit a scoped change.
- After merge, redeploy or re-sync the profile from the repo packet.

What belongs in GitHub:

- Instructions and `SOUL.md`
- Skills and reference files
- Manifest and non-secret config shape
- Restore/runbook decisions
- Regression cases

What stays out of GitHub:

- `.env` and API tokens
- Slack tokens and app tokens
- ChatGPT/Codex OAuth credentials
- Raw session transcripts
- PII or employee-level data
- Temporary memories and one-off local state

Prod recovery rule: if the VM dies, recreate the VM, install Hermes, restore this packet, pull secrets from Secret Manager, and restart the gateway. Any runtime-only learning since the last promotion is considered disposable unless it was intentionally exported and committed.
