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

Known C360 tables from the current enrichment flow:

- `fct_upcoming_renewal_cycles`
- `fct_company_revenue_snapshot`
- `fct_company_main_deals`

Inspect schema before relying on table or column names. The existing Luma events platform uses these tables for C360 customer enrichment, but NurtureAny must support Singapore, Malaysia, and Indonesia instead of Singapore-only logic.

## Query Rules

- Run only bounded read-only SQL.
- Never run DDL, DML, export, load, grant, revoke, or mutation statements.
- Join back to HubSpot company IDs or stable canonical company IDs when available.
- Aggregate or summarize before returning Slack output.
- Return `Confidence: needs-check` when HubSpot and C360 ownership or renewal evidence conflicts.
- Return `Confidence: blocked` when schema, auth, or table access fails.

