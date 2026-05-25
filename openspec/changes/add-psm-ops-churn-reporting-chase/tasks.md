# Tasks: Add PS Wee Manager Weekly Churn Reporting Chase

- [x] Create OpenSpec proposal, design, tasks, and spec files.
- [x] Delete local Codex automation `weekly-churn-reason-chase`.
- [x] Add deterministic `psm_ops_churn_reporting_chase.py` no-agent script.
- [x] Port Dashboard 292 card 2446 SQL into `runtime/sql/psm_ops_churn_projection_dashboard_292.sql`.
- [x] Add unit tests for quarter windows, Dashboard 292 actualized/non-actualized classification, upcoming exception dedupe, owner grouping, formatting, dry-run, and max-row caps.
- [x] Wire config template, manifest, deploy, heartbeat, audit, health checks, and profile inventory.
- [x] Add verifier guards against Core Meeting sheet / Google Sheets runtime access.
- [x] Run BigQuery dry-run for the final SQL.
- [x] Run script dry-run for `--as-of 2026-05-25` and confirm `26Q2`, `26Q3`, `26Q4`.
- [x] Run `openspec validate add-psm-ops-churn-reporting-chase --strict`.
- [x] Run `npm run psm-ops-bot:verify`.
- [x] Run `npm run slack-automation-identity:verify` because Slack automation delivery rules changed.
- [ ] Deploy to `hermes-psm-ops-bot-poc` and run live heartbeat/audit checks.
