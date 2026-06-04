# OpenSpec: Add PS Wee Manager Weekly Churn Reporting Chase

## Summary

Move weekly churn reporting cleanup from a local Codex cron into the existing PSM Ops Bot (`psmopsbot`) as a bot-owned Hermes no-agent cron. The workflow reads churn and renewal facts from BigQuery, not the Core Meeting sheet, and posts a concise weekly chase to `#team-rev-account-management`.

## Evidence Used

- PSM Ops app packet: `apps/psm-ops-bot`.
- Dashboard 292 source SQL: Metabase card 2446, ported into `runtime/sql/psm_ops_churn_projection_dashboard_292.sql`.
- BigQuery upcoming-renewal source table: `staffany-warehouse.analytics.fct_upcoming_renewal_cycles`.
- Supporting revenue/churn tables: `fct_company_revenue_snapshot`, `fct_alldealsmrr`, and `fct_churnmrrbymonth`.
- Business reference dashboards:
  - `https://metabase.staffany.com/dashboard/292-churn-projection-dashboard?churn_class=1-Actualized&churn_class=2-Non-Actualized+%2850%25+Confirmed%29&churn_class=2-Non-Actualized+%28Confirmed%29&churn_class=3-Non-Actualized+%28Overdue%29&churn_class=4-Non-Actualized+%28Red%29&churn_class=5-Non-Actualized+%28Orange%29&location=&renewal_date_filter=2026-01-01~2026-03-31`
  - `https://metabase.staffany.com/dashboard/5029-upcoming-renewals-dashboard?renewal_quarter=26Q2`

## Problem

The previous weekly cleanup lived as a local Codex automation and read from the 2026 Core Meeting Google Sheet. That made the process easy to duplicate, dependent on a reporting sheet, and not owned by the deployed PS Wee Manager runtime.

## Goals

- Run the weekly chase from PS Wee Manager (`psmopsbot`) every Monday 09:00 SGT.
- Use BigQuery as the direct data source for renewal/churn status and reason gaps.
- Chase Dashboard 292 churn-risk rows first, with exact actualized/non-actualized missing-field rules.
- Chase upcoming renewals only when they are risky/overdue and not already present in Dashboard 292.
- Cover current quarter plus the next two quarters from the run date.
- Post to `#team-rev-account-management` / `C019RVCR4S1` with `PSM Ops automation:` prefix.
- Group chases by quarter and owner, including an owner-missing bucket.
- Explicitly remove the local Codex automation `weekly-churn-reason-chase`.

## Non-Goals

- Do not create Jira PCO or ROI tickets in V1.
- Do not read the Core Meeting sheet or Google Sheets APIs.
- Do not scrape Metabase at runtime; Metabase dashboards are reference links.
- Do not invent churn reasons, owner mappings, or customer-channel mentions.
