# C360 BigQuery Runtime

NurtureAny uses StaffAny C360 data as read-only enrichment. HubSpot remains the queue source of truth.

## Contract

- Server name: `staffany_bigquery`
- Dataset default: `staffany-warehouse.analytics`
- Access mode: read-only MCP allowlist
- Allowed tools:
  - `list_dataset_ids`
  - `list_table_ids`
  - `get_table_info`
  - `execute_sql_readonly`

## Enrichment Signals

Use C360 only after the scoped HubSpot account set is known.

Useful signals:

- MRR / commercial value.
- Renewal cycle timing.
- Main deal start and end dates.
- Account owner and PSM context.
- Live customer status where available.
- QO sales points, converted ARR, MRR movement, and revenue snapshot actuals when the user asks for revenue pace or manager rollups.

Known C360 tables from the current enrichment flow:

- `fct_upcoming_renewal_cycles`
- `fct_company_revenue_snapshot`
- `fct_company_main_deals`
- `fct_sales_points`
- `fct_deal_metrics_with_pilot_conversion`
- `fct_mrr_movements`

Inspect schema before relying on table or column names. The existing Luma events platform uses these tables for C360 customer enrichment, but NurtureAny must support Singapore, Malaysia, and Indonesia instead of Singapore-only logic.

## Revenue Metrics

Use `skills/nurtureany-sales-bot/references/rev-planning-and-metrics.md` before querying revenue metrics.

- QO actuals should use `fct_sales_points.qo_set` after schema inspection.
- Direct QO count or pace prompts should resolve owner/team/date scope, call `hubspot_nurtureany.build_sales_metric_actuals_query` first, then run the returned SQL through `staffany_bigquery.execute_sql_readonly`. Do not route direct QO prompts through Friday review.
- `new ARR` is ambiguous. Ask whether the user wants signed converted ARR, paid converted ARR, or new MRR movement annualized.
- Signed and paid converted ARR come from `fct_deal_metrics_with_pilot_conversion`.
- New ARR movement and net ARR movement come from `fct_mrr_movements`; annualize MRR movement only when the queried source value is MRR.
- Current ARR/MRR snapshots come from the latest available `fct_company_revenue_snapshot` snapshot month.
- Rev planning Sheets/Slides provide target and definition context only. Do not use them as actuals.
- Friday review remains a HubSpot hygiene flow. If `build_friday_sales_review` returns `warehouse_metric_followups`, execute them as a second C360 BigQuery actuals source and keep the source classes separate.

## Known-Area Near-Me Customer Coverage

Near-me answers use two BigQuery reads: curated outlet matches and C360 current-customer coverage. This avoids requiring HubSpot custom-object permissions.

Curated outlet matches live in:

```text
staffany-warehouse.analytics.nurtureany_near_me_outlet_matches
```

Provisioning SQL lives at `runtime/sql/near-me-outlet-matches.sql`. Do not run that DDL through the read-only BigQuery MCP.

Use the SQL returned by `near_me_nurtureany.build_near_me_outlet_matches_query`, then run it through `staffany_bigquery.execute_sql_readonly`.

The outlet-match query contract is:

- Filter by matched `area_id`.
- Exclude `match_status='rejected'`.
- Return curated rows only; Google-only live restaurants are not auto-stored.
- Keep `hubspot_company_id`, `organisation_id`, `match_status`, `account_status`, `confidence`, owner snapshot, and distance when coordinates exist.

Near-me answers also require C360 current-customer coverage even when BigQuery has no outlet match yet.

Use the SQL returned by `near_me_nurtureany.build_near_me_c360_customer_query`, then run it through `staffany_bigquery.execute_sql_readonly`.

The query contract is:

- Anchor to the matched `known_area` center/radius.
- Source geofence coordinates from `kraken_rds.Locations`.
- Normalize swapped latitude/longitude defensively.
- Join `analytics.dim_sections` and exclude `isarchived` sections.
- Join `analytics.dim_org_section` for section and organisation context.
- Join `analytics.fct_deal_org_company` as the live/customer C360 layer.
- Left join `analytics.fct_company_org_mrr` only for optional MRR enrichment.
- Collapse to one row per `organisation_id`, keeping nearest section, nearest address, nearest distance, section count, HubSpot company ID, C360 company name, usage status, deal stage, and deal end date.
- Pass `hubspot_company_id`, optional `customer360_route_key`, and `organisation_id` through to `merge_near_me_sources` so current-customer rows can render stable Customer 360 links from route keys instead of dummy numeric routes.

Do not query person GPS, clock records, raw employee location rows, or employee movement data for this flow. The geofence section table is enough.

`fct_company_org_mrr` is too strict as the main filter for near-me customer coverage. Use it only as MRR context after `fct_deal_org_company` has selected current/customer orgs.

## Query Rules

- Run only bounded read-only SQL.
- Never run DDL, DML, export, load, grant, revoke, or mutation statements.
- Join back to HubSpot company IDs or stable canonical company IDs when available.
- Aggregate or summarize before returning Slack output.
- Include the time grain and as-of date or latest snapshot month in every revenue metric answer.
- State whether the answer uses HubSpot account scope, Rev planning targets/definitions, or C360 BigQuery actuals.
- For Friday review, use BigQuery QO actuals only as an additional aggregate source after the HubSpot review output; do not replace account-coverage, calls, meetings, or hygiene checks with warehouse metrics.
- Return `Confidence: needs-check` when HubSpot and C360 ownership or renewal evidence conflicts.
- Return `Confidence: blocked` when schema, auth, or table access fails.
