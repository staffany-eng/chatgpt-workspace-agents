# StaffAny BigQuery MCP

Hermes Data Bot reaches BigQuery only through the StaffAny-controlled MCP proxy.

## Contract

- Server name: `staffany_bigquery`
- URL: `https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp`
- Auth env var: `MCP_STAFFANY_BIGQUERY_API_KEY`
- Secret source: Secret Manager secret `bq-mcp-proxy-shared-secret`
- Dataset default: `staffany-warehouse.analytics`

## Allowed Tools

Only these tools should be visible to the profile:

- `list_dataset_ids`
- `list_table_ids`
- `get_table_info`
- `execute_sql_readonly`

Do not expose generic HTTP fetch, write SQL, export, load, grant, revoke, DDL, DML, or admin tools.

## Runtime Rules

- Inspect schema before writing SQL when table, column, grain, date field, or join path is unclear.
- Run read-only, bounded queries only.
- Prefer Manticore mart tables: `fct_*`, `dim_*`, and `rpt_*`.
- Discover actual categorical values before filtering by status, section, pay item, department, business entity, organization name, or custom field.
- Return `Confidence: blocked` when MCP auth, schema access, or table access fails.

## Adjacent Slack Context Boundary

Slack thread interpretation belongs to the separate read-only `staffany_slack_context` MCP. Do not add Slack read, Slack write, generic fetch, or workspace search capability to the BigQuery MCP.

## Adjacent Customer 360 Boundary

Current-customer universe checks belong to the separate read-only `staffany_c360` MCP. When the user asks for current customers, C360 definition, or a C360 correction, call `staffany_c360.list_current_customer_orgs` first and filter BigQuery metric queries to the returned linked StaffAny org IDs. Do not recreate Customer 360 renewal/billing definitions inside ad hoc BigQuery prompts.

## Smoke Check

From the live profile, verify the MCP server lists only the allowed tools and can run a bounded read-only query such as `SELECT 1 AS ok`.
