# Hermes StaffAny Data Bot Current Hardening State

## Source Metadata

- Type: local deployed Hermes profile artifact
- Source class: StaffAny Hermes deployment evidence
- Source path: `/home/leekaiyi/.hermes/profiles/staffanydatabot/`
- Date checked: 2026-05-08
- Evidence weight: 4 for the current StaffAny Hermes deployment; 3 for general workspace-agent design claims
- Privacy: private internal operational note

## Raw Content Policy

This raw note records selected non-secret operational facts from the deployed `staffanydatabot` profile. No `.env`, token, credential, raw query row, raw Slack transcript, employee-level data, memory dump, or session transcript was copied.

## Source Inventory

| Path | Purpose | Copied |
| --- | --- | --- |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/` | Hermes profile root | no |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/config.yaml` | Profile config check | no |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/logs/gateway.log` | Gateway scope/status evidence | no |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/skills/staffany-data-bot/SKILL.md` | StaffAny data-bot skill evidence | no |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/skills/staffany-data-bot/references/staffany-data-bot-eval-pack.md` | Eval pack evidence | no |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/scripts/staffany_data_bot_health_check.py` | Runtime health-check evidence | no |
| `/home/leekaiyi/.hermes/profiles/staffanydatabot/scripts/staffany_data_bot_eval_check.py` | On-demand lightweight behavioural eval evidence | no |

## Evidence Extracts

- Active Hermes profile: `staffanydatabot`.
- Gateway service: `hermes-gateway-staffanydatabot.service`.
- Secret redaction config: `security.redact_secrets = true`.
- Model route config after cleanup: `model.provider = custom`, `model.default = gpt-5.5`, `model.base_url = https://api.openai.com/v1`. The previous `all@staffany` default against the OpenAI endpoint produced `model_not_found` and fallback churn.
- Slack effective scopes observed in recent gateway logs include `reactions:write` and `files:read`.
- StaffAny BigQuery MCP server `staffany_bigquery` connects and exposes four selected tools:
  `list_dataset_ids`, `list_table_ids`, `get_table_info`, and `execute_sql_readonly`.
- Read-only smoke query `SELECT 1 AS ok` succeeded with 0 bytes processed/billed.
- Silent health check script exits 0 and prints nothing when healthy.
- Weekday health check cron exists with `no_agent: true` on `0 1 * * 1-5` UTC, equivalent to weekdays 9am SGT.
- Operational artifacts include `staffany_data_bot_health_check.py`, `staffany_data_bot_eval_check.py`, `restart_staffany_gateway_silent.sh`, and `staffany-data-bot-eval-pack.md`.
- The eval pack covers Slack plan-first behaviour, source order, confidence labels, sensitive-data refusal, org-name preference, and StaffAny metric caveats.
- The lightweight eval script passed on 2026-05-08 after skill fixes for sensitive-data `Confidence: blocked` and Slack first-mention static invariants.

## Design Observations

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
- Model-route cleanup came from live profile config and Hermes smoke tests that succeeded with `gpt-5.5` as the profile default.
- Lightweight eval evidence came from executing `/home/leekaiyi/.hermes/profiles/staffanydatabot/scripts/staffany_data_bot_eval_check.py` and observing all checks pass without querying the warehouse.
