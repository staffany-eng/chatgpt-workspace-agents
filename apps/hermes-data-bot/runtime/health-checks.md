# Health Checks

Hermes Data Bot needs deterministic runtime health checks because prompt correctness does not guarantee live connector scopes, gateway restarts, or MCP availability.

## Expected Checks

- Hermes gateway service for `staffanydatabot` is active.
- Secret redaction remains enabled.
- Slack gateway has effective `reactions:write` and `files:read` scopes.
- Slack `groups:read` is not required; missing-scope warnings for private-channel directory enumeration are accepted in this POC.
- `staffany_bigquery` MCP lists only the expected read-only tools.
- A tiny read-only BigQuery smoke query succeeds.
- `hermes -p staffanydatabot auth status openai-codex` reports logged in.
- `hermes -p staffanydatabot auth list` has no `openai-codex` credential entries marked `auth failed`, `token_invalidated`, or `re-auth`.
- Gateway logs since the current service start contain no Codex OAuth 401/auth-invalidated errors.
- Honcho API health returns OK when external memory is enabled.
- `hermes -p staffanydatabot memory status` reports `Provider: honcho` and `Status: available` when Honcho is expected to be active.
- Healthy checks print nothing and exit 0.

## Script

Use the packet script for no-agent health checks:

```bash
apps/hermes-data-bot/runtime/check-health.sh
```

Default checks:

- `hermes -p staffanydatabot gateway status`
- `hermes -p staffanydatabot auth status openai-codex`
- `hermes -p staffanydatabot auth list` credential-pool failure markers for `openai-codex`
- recent `hermes-gateway-staffanydatabot.service` logs for Codex OAuth 401/auth-invalidated errors
- `hermes -p staffanydatabot mcp test staffany_bigquery` with 4 expected tools
- `curl -fsS http://localhost:8000/health`
- `hermes -p staffanydatabot memory status`
- `redact_secrets: true` in the live profile config

Useful overrides:

```bash
HERMES_PROFILE=staffanydatabot EXPECT_HONCHO=0 apps/hermes-data-bot/runtime/check-health.sh
EXPECT_MODEL_AUTH=0 CHECK_GATEWAY_AUTH_LOGS=0 apps/hermes-data-bot/runtime/check-health.sh
HONCHO_HEALTH_URL=http://127.0.0.1:8000/health apps/hermes-data-bot/runtime/check-health.sh
```

## Cron Pattern

Prefer a Hermes `no_agent` cron for operational checks. Healthy runs should consume no model tokens and create no Slack noise.

For the `staffanydatabot` profile, install cron scripts under the profile-local scripts directory:

```bash
mkdir -p ~/.hermes/profiles/staffanydatabot/scripts
cp apps/hermes-data-bot/runtime/check-health.sh ~/.hermes/profiles/staffanydatabot/scripts/staffanydatabot-check-health.sh
hermes -p staffanydatabot cron create "0 1 * * 1-5" \
  --name "staffanydatabot health check" \
  --script staffanydatabot-check-health.sh \
  --no-agent
```

Current deployed pattern from research evidence:

```text
0 1 * * 1-5 UTC
```

That is weekdays 9am SGT.

## Failure Behavior

On failure, print only the concrete failing subsystem and next check. Do not print secrets, env values, raw logs, Slack messages, query rows, or Honcho memory contents.
