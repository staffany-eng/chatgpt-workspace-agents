# Hermes StaffAny Data Bot Current Hardening State

Retrieval date: 2026-05-08
Source type: local deployed Hermes profile artifact
Evidence weight: 4 for the current StaffAny Hermes deployment; 3 for general workspace-agent design claims.

## Local source paths inspected

- Hermes profile: `/home/leekaiyi/.hermes/profiles/staffanydatabot/`
- Profile config: `/home/leekaiyi/.hermes/profiles/staffanydatabot/config.yaml`
- Gateway log: `/home/leekaiyi/.hermes/profiles/staffanydatabot/logs/gateway.log`
- StaffAny data bot skill: `/home/leekaiyi/.hermes/profiles/staffanydatabot/skills/staffany-data-bot/SKILL.md`
- Eval pack: `/home/leekaiyi/.hermes/profiles/staffanydatabot/skills/staffany-data-bot/references/staffany-data-bot-eval-pack.md`
- Health check script: `/home/leekaiyi/.hermes/profiles/staffanydatabot/scripts/staffany_data_bot_health_check.py`

No `.env`, token, credential, raw query row, raw Slack transcript, or employee-level data was copied.

## Observed setup

- Active Hermes profile: `staffanydatabot`.
- Gateway service: `hermes-gateway-staffanydatabot.service`.
- Secret redaction config: `security.redact_secrets = true`.
- Slack effective scopes observed in recent gateway logs include `reactions:write` and `files:read`.
- StaffAny BigQuery MCP server `staffany_bigquery` connects and exposes four selected tools:
  - `list_dataset_ids`
  - `list_table_ids`
  - `get_table_info`
  - `execute_sql_readonly`
- Read-only smoke query `SELECT 1 AS ok` succeeded with 0 bytes processed/billed.
- Silent health check script exits 0 and prints nothing when healthy.
- Weekday health check cron exists with `no_agent: true` on `0 1 * * 1-5` UTC, equivalent to weekdays 9am SGT.

## Operational artifacts created in the profile

- `staffany_data_bot_health_check.py`: deterministic no-agent health check; prints only on failure.
- `restart_staffany_gateway_silent.sh`: one-shot silent gateway restart helper.
- `staffany-data-bot-eval-pack.md`: regression cases for Slack plan-first behaviour, source order, confidence labels, sensitive-data refusal, org-name preference, and known StaffAny metric caveats.

## Design observations

- A data bot needs runtime health checks in addition to prompt/skill instructions because connector scopes, gateway restarts, and MCP availability can drift independently of the model prompt.
- For Slack data requests, plan-first gating should be treated as a product behaviour and regression-tested, not merely documented.
- Confidence labels are safer when backed by a local metric registry and eval pack; otherwise recurring caveats can silently regress.
- Silent no-agent cron is a good fit for health checks because healthy runs should consume no model tokens and create no Slack noise.

## Evidence Trace

- `security.redact_secrets = true` came from the deployed profile config check on 2026-05-08.
- Slack scope claims came from recent gateway log lines showing provided scopes containing `reactions:write` and `files:read`.
- BigQuery MCP tool claims came from `hermes --profile staffanydatabot mcp test staffany_bigquery` on 2026-05-08.
- Health-check behaviour came from executing `/home/leekaiyi/.hermes/profiles/staffanydatabot/scripts/staffany_data_bot_health_check.py` and observing exit code 0 with empty stdout.
- Eval-pack contents came from the local profile skill reference file created for `staffany-data-bot`.
