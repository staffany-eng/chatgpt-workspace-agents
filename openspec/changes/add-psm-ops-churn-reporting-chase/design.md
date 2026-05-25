# Design: PS Wee Manager Weekly Churn Reporting Chase

## Approach

Add a deterministic no-agent script to `apps/psm-ops-bot/runtime/scripts/` and install it as a cloud-only Hermes cron on the existing `psmopsbot` profile. Hermes cron delivery posts the script output to Slack; the script itself does not use Slack APIs or human tokens.

## Data Source Ladder

1. `runtime/sql/psm_ops_churn_projection_dashboard_292.sql` is the repo-owned BigQuery port of Metabase card 2446, which backs Dashboard 292. This is the source for `churn_class`, weighted churn MRR, renewal assessment fields, and company churn reason fields.
2. `staffany-warehouse.analytics.fct_upcoming_renewal_cycles` is the safety-net source for upcoming renewal rows that are risky/overdue and do not already appear in Dashboard 292 with a non-null `churn_class`.
3. `staffany-warehouse.analytics.fct_company_revenue_snapshot` provides current MRR context from the latest snapshot.
4. `staffany-warehouse.analytics.fct_churnmrrbymonth` remains available as renewal/churn context for upcoming renewal rows.
5. Metabase dashboards 292 and 5029 are documented references for business interpretation. Runtime queries BigQuery directly.

Dashboard 5029 maps directly to upcoming renewal cycles. Dashboard 292 exposes a `churn_class` filter that is not present as a physical column in the checked analytics metadata; the implementation keeps the equivalent dashboard SQL in `runtime/sql/` and should be updated if the Metabase source card changes.

## Chase Rules

- Window: current quarter plus next two quarters, based on `Asia/Singapore`.
- Chase owner: `deal_psm_name`; blank owner goes to `Owner missing`.
- Dashboard 292 section includes only rows where `churn_class IS NOT NULL`.
- For `churn_class = '1-Actualized'`, chase missing/generic `company_churn_reason` and `company_churn_reason_bucket`.
- For all other non-null `churn_class` rows, chase missing/generic `renewal_assessment` and `renewal_assessment_reason`.
- Missing owner rows are surfaced in the Dashboard 292 section and ask who owns the account.
- Upcoming renewal exceptions dedupe against Dashboard 292 by canonical company ID first and raw company ID fallback. If a company appears in Dashboard 292 with non-null `churn_class`, suppress it from upcoming renewal exceptions.
- Upcoming renewal exceptions include only rows whose status/bucket/billing/stage contains overdue, unpaid, delinquent, late payment, not started, no renewal deal yet, or at risk.
- Sort by quarter, owner, churn class / highest value, then company.
- Output shows row-level examples for both sections with capped rows per section, and asks the team to reply with renewal status, churn reason/category, evidence link, source-field update confirmation, and owner confirmation when missing.

## Runtime Shape

- Script: `psm_ops_churn_reporting_chase.py`.
- Cron name: `psmopsbot churn reporting chase`.
- Schedule: `0 1 * * 1` UTC, Monday 09:00 SGT.
- Delivery: `slack:#team-rev-account-management`.
- Channel ID env: `PSM_OPS_CHURN_REPORTING_CHANNEL_ID=C019RVCR4S1`.
- Query envs: `PSM_OPS_CHURN_REPORTING_BQ_PROJECT`, `PSM_OPS_CHURN_REPORTING_BQ_DATASET`, optional `BQ_BIN`.
- SQL artifact: `runtime/sql/psm_ops_churn_projection_dashboard_292.sql`.

## Safety

- Script SQL is fixed and read-only; there is no user-supplied SQL argument.
- Script does not reference the Core Meeting spreadsheet ID, Google Sheets APIs, or Slack user tokens.
- Dry-run prints the same Slack-safe output with a dry-run marker.
- BigQuery failures return a concise blocked automation message without secrets or raw exports.
