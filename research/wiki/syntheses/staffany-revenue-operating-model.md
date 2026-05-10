# StaffAny Revenue Operating Model

## Sources

- [StaffAny Rev Team Planning And Metrics](../sources/staffany-rev-team-planning-and-metrics.md)
- [BigQuery MCP Proxy](../sources/bigquery-mcp-proxy.md)
- [StaffAny Hermes Data Bot POC](../sources/staffany-hermes-data-bot-poc.md)

## Synthesis

- StaffAny revenue questions have two different evidence classes: planning intent and actual metrics. Sheets and Slides explain targets, pacing, definitions, and sales operating rules. Manticore and BigQuery provide actual metric lineage and aggregate results.
- The bot should not answer "new ARR" with a single hardcoded metric. It should distinguish signed converted ARR, paid converted ARR, and New ARR from the MRR movement ledger.
- The current Manticore source for QO is `fct_sales_points.qo_set`.
- Revenue movement analysis should start from `fct_mrr_movements`; current ARR/MRR snapshots should start from `fct_company_revenue_snapshot`; activity/QO answers should start from `fct_sales_points`.
- Planning sheets are useful for target comparisons, pacing, and explaining how Rev Team thinks about QO and ARR, but they are not actuals.

## Data Bot Implication

- The answer contract should state source class: `planning target`, `training definition`, `dbt metric definition`, or `warehouse actual`.
- The bot should state the as-of date and snapshot month for revenue answers.
- When current month data is returned, mark it as month-to-date.
- When the user asks for sensitive row-level details, aggregate first or ask for the minimum required slice.
