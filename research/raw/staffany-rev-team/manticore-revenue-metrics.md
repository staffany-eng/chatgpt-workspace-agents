# Manticore Revenue Metrics And BigQuery Aggregates

## Source Metadata

- Source path: `/Users/leekaiyi/workspace/manticore`
- Source type: private dbt repo plus read-only BigQuery aggregates
- Date checked: 2026-05-10
- Checked with: `rg`, `nl -ba`, and hardened read-only BigQuery wrapper
- Warehouse project: `staffany-warehouse`
- Warehouse dataset: `analytics`
- BigQuery dry-run authenticated successfully with the current local Google Cloud account.

## Raw Content Policy

- Private internal analytics evidence. Do not copy raw deal rows, company rows, employee rows, HubSpot contacts, phone numbers, emails, or secret-like values.
- Preserve metric lineage, table/column names, query shapes, and monthly aggregate outputs only.
- BigQuery query outputs below are aggregate month-level metrics; no deal ids, company ids, owner ids, or personal data are copied.

## Source Inventory

- Manticore repo has `AGENTS.md` describing it as the dbt analytics transformation layer.
- Metric files inspected: `models/marts/core/fct_sales_points.sql`, `models/marts/core/fct_deal_metrics_with_pilot_conversion.sql`, `models/marts/core/fct_mrr_movements.sql`, `models/marts/core/fct_company_revenue_snapshot.sql`, `models/intermediate/core/int_deal_line_item_values.sql`, and `models/marts/core/core.yml`.
- BigQuery tables queried: `analytics.fct_sales_points`, `analytics.fct_deal_metrics_with_pilot_conversion`, `analytics.fct_mrr_movements`, and `analytics.fct_company_revenue_snapshot`.
- BigQuery `INFORMATION_SCHEMA.COLUMNS` found no `qr` column; the only `qr`/`qo` match in analytics columns was `fct_sales_points.qo_set`.

## Evidence Extracts

- `fct_sales_points` computes `qo_set` as `count(distinct deal_id)` for deals with `appointment_owner_id`, selected employee-size ranges, non-null `date_entered_appointment_set`, and `dealtype = 'newbusiness'`.
- `fct_sales_points` counts calls, connected calls, WhatsApp, LinkedIn, ABM met, new appointment met, follow-up appointment met, QO set, and partnership met by activity date and owner.
- `fct_deal_metrics_with_pilot_conversion` builds deal-level ARR from `int_deal_line_item_values`, then adds pilot, conversion, and outbound flags.
- `fct_deal_metrics_with_pilot_conversion` computes `signed_converted_arr` as pilot ARR, conversion delta, or deal ARR depending on pilot/conversion status.
- `fct_deal_metrics_with_pilot_conversion` computes `paid_converted_arr` only for `Invoice Paid - New Sub`, using pilot ARR, conversion delta, or deal ARR.
- `fct_deal_metrics_with_pilot_conversion` computes `eligible_revenue` as 50 percent for inbound or conversion deals and 100 percent for outbound deals.
- `fct_mrr_movements` is a consolidated ledger for Monthly Recurring Revenue movements and classifies events as New, Upsell, Cross-sell, Contraction, Churn, Pilot Conversion, and Pilot Churn.
- `fct_mrr_movements` derives MRR from non-one-off line-item ARR divided by 12 and includes product splits for StaffAny, EngageAny, and Payroll.
- `fct_company_revenue_snapshot` creates monthly company snapshots, excludes one-off items, includes pilots, and keeps contracts active at month end to avoid renewal-month double counting.
- `int_deal_line_item_values` filters subscription pipelines/stages, excludes test package names, flags one-off onboarding/training/professional services, maps package names to product lines, and handles IDR/MYR conversion rules.
- BigQuery dry-run for the monthly aggregate metric query succeeded on 2026-05-10, with row-level security applied.
- Monthly aggregate output, January to May 2026 as of 2026-05-10: QO set was 122, 116, 78, 83, and 16.
- Monthly aggregate output, January to May 2026 as of 2026-05-10: signed converted ARR was 357648.11, 271843.93, 487406.29, 658847.98, and 302364.59.
- Monthly aggregate output, January to May 2026 as of 2026-05-10: paid converted ARR was 41949.30, 66837.44, 27503.17, 13880.09, and 876.33.
- Monthly aggregate output, January to May 2026 as of 2026-05-10: new ARR from MRR movements was 64596.92, 31491.60, 36705.48, 55919.15, and 58240.50.
- Monthly aggregate output, January to May 2026 as of 2026-05-10: net ARR movement was 55132.88, -34056.87, 14772.36, 60718.19, and 36400.84.
- Latest company revenue snapshot query returned snapshot month 2026-04-01, 521 active revenue companies, total ARR 2298457.98, total MRR 191538.17, StaffAny MRR 136163.62, EngageAny MRR 7251.36, and Payroll MRR 47997.21.
- Query path used: `PATH=/opt/homebrew/bin:$PATH CLOUDSDK_CONFIG=/Users/leekaiyi/.config/gcloud /Users/leekaiyi/.codex/skills/bigquery-query/scripts/query-bigquery.sh`.
