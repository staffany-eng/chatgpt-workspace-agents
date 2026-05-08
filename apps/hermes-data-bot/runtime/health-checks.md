# Health Checks

Hermes Data Bot needs deterministic runtime health checks because prompt correctness does not guarantee live connector scopes, gateway restarts, or MCP availability.

## Expected Checks

- Hermes gateway service for `staffanydatabot` is active.
- Secret redaction remains enabled.
- Slack gateway has effective `reactions:write` and `files:read` scopes.
- Slack `groups:read` is not required; missing-scope warnings for private-channel directory enumeration are accepted in this POC.
- `staffany_bigquery` MCP lists only the expected read-only tools.
- A tiny read-only BigQuery smoke query succeeds.
- Healthy checks print nothing and exit 0.

## Cron Pattern

Prefer a Hermes `no_agent` cron for operational checks. Healthy runs should consume no model tokens and create no Slack noise.

Current deployed pattern from research evidence:

```text
0 1 * * 1-5 UTC
```

That is weekdays 9am SGT.

## Failure Behavior

On failure, print only the concrete failing subsystem and next check. Do not print secrets, env values, raw logs, Slack messages, or query rows.
