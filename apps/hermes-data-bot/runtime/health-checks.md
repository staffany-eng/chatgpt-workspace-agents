# Health Checks

Hermes Data Bot needs deterministic runtime health checks because prompt correctness does not guarantee live connector scopes, gateway restarts, or MCP availability.

## Expected Checks

- Hermes gateway service for `staffanydatabot` is active.
- Secret redaction remains enabled.
- Model route avoids known-bad aliases: `model.default=all@staffany` against `https://api.openai.com/v1` causes `model_not_found` and fallback churn; current safe route is `model.provider=custom`, `model.default=gpt-5.5`, `model.base_url=https://api.openai.com/v1`.
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

On failure, print only the concrete failing subsystem and next check. Do not print secrets, env values, raw logs, Slack messages, or query rows.
