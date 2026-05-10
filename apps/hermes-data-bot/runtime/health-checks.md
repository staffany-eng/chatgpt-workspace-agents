# Health Checks

Hermes Data Bot needs deterministic runtime health checks because prompt correctness does not guarantee live connector scopes, gateway restarts, or MCP availability.

## Expected Checks

- Hermes gateway service for `staffanydatabot` is active.
- Secret redaction remains enabled.
- Model route is the intentional Anthropic route: `model.provider=anthropic`, `model.default=claude-sonnet-4-6`.
- Slack gateway has effective `files:read` scope.
- Slack `groups:read` is not required; missing-scope warnings for private-channel directory enumeration are accepted in this POC.
- Slack tool progress resolves to `off` through Hermes' native Slack display default, so internal tool calls such as `skill_view` are not posted into Slack.
- Slack streaming is disabled, so partial model drafts are not posted before the final answer.
- Slack interim assistant messages are disabled, so draft text is not posted before the final answer.
- Slack status reactions are disabled; the bot should not add success/failure emoji to user messages.
- Kanban gateway dispatch remains disabled, so completed data-answer threads do not get `:question:` action-needed follow-up loops.
- `staffany_bigquery` MCP lists only the expected read-only tools.
- A tiny read-only BigQuery smoke query succeeds.
- `hermes -p staffanydatabot auth status anthropic` reports logged in.
- For Codex fallback experiments only, `hermes -p staffanydatabot auth list` should have no `openai-codex` credential entries marked `auth failed`, `token_invalidated`, or `re-auth`.
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
- `model.provider=anthropic`
- `model.default=claude-sonnet-4-6`
- `hermes -p staffanydatabot auth status anthropic`
- Slack display config resolves `tool_progress=off`
- Slack display config resolves `streaming=false`
- Slack `interim_assistant_messages=false`
- Slack `reactions=false`
- `kanban.dispatch_in_gateway=false`
- recent model-auth gateway errors when `EXPECT_MODEL_PROVIDER=openai-codex`
- `hermes -p staffanydatabot mcp test staffany_bigquery` with 4 expected tools
- `curl -fsS http://localhost:8000/health`
- `hermes -p staffanydatabot memory status`
- `redact_secrets: true` in the live profile config

Useful overrides:

```bash
HERMES_PROFILE=staffanydatabot EXPECT_HONCHO=0 apps/hermes-data-bot/runtime/check-health.sh
EXPECT_MODEL_AUTH=0 CHECK_GATEWAY_AUTH_LOGS=0 apps/hermes-data-bot/runtime/check-health.sh
EXPECT_MODEL_PROVIDER=openai-codex EXPECT_MODEL_DEFAULT=gpt-5.3-codex apps/hermes-data-bot/runtime/check-health.sh
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

## Live Profile Drift Audit

Run the packet audit after profile edits, script sync, model-route changes, or gateway maintenance:

```bash
apps/hermes-data-bot/runtime/audit-live-profile.sh
```

It checks the live `SOUL.md`, StaffAny skill folder, health-check script sync, Anthropic model route, Slack quiet settings, secret redaction, BigQuery MCP allowlist, installed health cron, and MCP tool count.

## Lightweight Behavioural Eval Harness

The live profile also has an on-demand lightweight eval script at:

```text
~/.hermes/profiles/staffanydatabot/scripts/staffany_data_bot_eval_check.py
```

It intentionally avoids warehouse queries and checks:

- static Slack plan-first invariants in the skill/eval references;
- product lookup contract for missing package mappings;
- PPh “on us” candidate logic and `NETTO`-alone warning;
- sensitive payroll/NRIC/bank refusal with `Confidence: blocked`;
- ClaimsAny paid-account line-item definition when no BigQuery query is allowed.

Do not put this script in the silent weekday cron because it invokes Hermes/model calls. Use it manually after skill or model-route changes.

## Failure Behavior

On failure, print only the concrete failing subsystem and next check. Do not print secrets, env values, raw logs, Slack messages, query rows, or Honcho memory contents.
