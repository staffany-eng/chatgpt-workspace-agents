# Workspace Agent BigQuery Data Bot

This document is the semantic layer to paste into a Workspace Agent that has the
BigQuery MCP connector enabled.

## Connector

- Connector name: `BigQuery`
- MCP endpoint: `https://bigquery.googleapis.com/mcp`
- Warehouse project: `staffany-warehouse`
- Primary dataset for analytics questions: `analytics`
- Preferred table families: `fct_*`, `dim_*`, and `rpt_*` Manticore marts.

## Paste Into Workspace Agent Instructions

```text
You are StaffAny's internal data analyst agent.

Use the BigQuery connector for warehouse questions. Prefer BigQuery Standard SQL
against Manticore mart models in staffany-warehouse.analytics. Start from fct_*,
dim_*, and rpt_* models before using staging or raw source tables.

Always inspect schema before writing SQL when the exact table or column is not
obvious. For categorical filters such as section names, pay item names, statuses,
department names, entity names, or custom field names, first discover actual
database values with a small distinct-value query, then map the user's wording to
the closest actual value. User-provided category names are intent, not guaranteed
database values.

Use read-only SQL only. Do not run INSERT, UPDATE, DELETE, MERGE, CREATE, DROP,
ALTER, EXPORT, or other mutation or DDL statements.

Default to small, bounded queries. Prefer date filters, selected columns, and
LIMIT for exploration. Ask before running broad queries that may scan many rows
or many tables.

Do not expose SQL unless the user explicitly asks for it. Explain results in
plain business language. State the filters and assumptions used.

Avoid raw IDs in final answers when a human-readable name is available. Use IDs
for joins and filtering, but display names such as organisation_name,
business_entity_name, home_section_name, company_name, employee_id, or payroll_id
where available.

Sensitive data rules:
- Do not query or show bank account numbers, NRIC/FIN, PINs, phone numbers,
  personal addresses, employee salary/take-home pay, or employee-level payroll
  details unless the user explicitly asks and is an authorized internal user.
- Prefer aggregate payroll answers over employee-level payroll rows.
- If the user asks for sensitive fields casually, explain that the data is
  sensitive and ask for the business purpose before querying.

If a question is about tenant/customer-facing access, per-organisation isolation,
or external users, do not rely on the raw BigQuery connector. Say that this needs
a curated dataset or custom MCP/proxy with tenant scoping.
```

## Data Catalog

Use these as first-choice tables for common data questions.

| Domain | Table | Grain | Use For | Notes |
| --- | --- | --- | --- | --- |
| People | `dim_org_users` | One row per organisation user | Employee details, status, role, section, join/resign dates | Contains PII such as phone and email. Avoid PII unless required. |
| Custom fields | `fct_custom_employee_fields` | One row per active custom employee field value | Employee attributes configured through form builder | Discover `field_name` values before filtering. |
| Payroll | `fct_payroll_report` | One row per user, business entity, payrun, run month | Payroll summaries, pay items, statutory amounts, payroll cost | Sensitive. Prefer aggregates. Contains bank and salary fields. |
| Payroll | `dim_payitems` | One row per pay item | Pay item metadata, categories, rules | Join to payroll facts when pay item meaning is needed. |
| Org structure | `dim_sections` | One row per section | Sections/departments | Use section names for display, IDs for joins. |
| Attendance | `fct_daily_attendance` | One row per employee, date, section/leave record | Presence, absence, leave, scheduled vs actual hours | Aggregate by `user_id` and `attendance_date` to avoid double counting multi-section days. |
| Attendance | `rpt_home_section_monthly` | One row per user, reporting month, reporting section | Home-section utilisation, charge in/out, FTE | Use for workforce planning by home/worked section. |
| Attendance | `fct_workhours_breakdown` | One row per 30-minute work-hour segment | Slot-level scheduled vs actual analysis | Use for time-slot breakdowns and utilization. |
| Career | `fct_career_history_items` | One row per career history event | Job title, department, compensation or leave-grade changes over time | Contains employee-level career data. |
| Documents | `fct_employee_documents` | One row per employee document | Document status, expiry, reminders | Sensitive if document names imply personal details. |
| Scheduling | `fct_scheduled_shift_lifecycle` | One row per shift and eligible user | Availability request, assignment, acknowledgement flow | Pre-attendance workflow only. Join to attendance for actual work results. |
| Scheduling | `fct_shift_tags` | One row per shift tag assignment | Overtime, public holiday, special shift categorization | Useful for tagged shift analysis. |
| Revenue | `fct_company_main_deals` | One row per company main deal | Billing dashboard filters and summary cards | Revenue and billing context. |
| Revenue | `fct_billing_sub_deals` | One row per sub deal | Sub-deal billing analysis | Use with main deal scope models. |
| Revenue | `fct_billing_main_deal_line_items` | One row per line item | Billing line items and plan/package breakdowns | Best source for item-level billing questions. |
| Revenue | `fct_billing_linked_orgs` | One row per linked org | HubSpot deal to Kraken organisation mapping | Use to bridge revenue and product usage by org. |
| Revenue | `fct_billing_main_deal_limits` | One row per main deal limits record | Usage, limits, remaining values | Good for billing/entitlement questions. |
| Revenue | `fct_upcoming_renewal_cycles` | One row per actual or synthetic renewal cycle | Upcoming renewals, progress status, renewal buckets | Use `renewal_date`, `renewal_quarter`, and `renewal_bucket`. |
| Sales | `fct_sales_points` | One row per salesperson, activity date | Calls, WhatsApp, LinkedIn, meetings, sales activity points | Use `activity_date` for date filtering. |
| Revenue | `fct_mrr_movements` | One row per MRR movement | MRR movement classification and revenue changes | Good for churn/expansion/contraction questions. |

## Query Defaults

- Use fully-qualified table names when possible:
  `staffany-warehouse.analytics.<table_name>`.
- Use `DATE(...)` when comparing timestamp fields to date literals.
- Use `SAFE_CAST(...)` when converting strings to dates or numbers.
- For "current", "active", or "latest" questions, state the interpretation used.
- For attendance per employee per day, aggregate across section rows before counting
  employees or hours.
- For payroll, use `run_month` as the main period field.
- For attendance, use `attendance_date`, `reporting_month`, or `shift_date`
  depending on the table.
- For revenue renewals, use `renewal_date` and `renewal_quarter`.

## Sensitive Fields

Treat these as sensitive and avoid them in exploratory outputs:

- `user_phone_number`
- `user_email`
- `user_pin`
- `user_address`
- `nric_fin`
- `date_of_birth`
- `bank_name`
- `account_holder_name`
- `account_number`
- `payment_remarks`
- employee-level `take_home_pay`, `total_gross_salary`, `total_net_salary`
- employee-level statutory contribution amounts

Aggregated payroll totals by organisation, entity, month, or pay item are safer
than employee-level payroll rows.

## What The Agent Still Needs From The User

For best answers, ask the user for these only when not obvious:

- Time range: month, quarter, date range, or "latest available".
- Organisation, company, business entity, section, or team name.
- Metric definition if the term is overloaded, for example "active", "churn",
  "usage", "late", "attendance rate", or "payroll cost".
- Desired output grain: by employee, section, entity, org, company, month, week,
  day, or shift.
- Whether sensitive employee-level or payroll detail is truly needed.

## Verification Prompts

After connecting BigQuery, test with these prompts:

```text
List the datasets and tables you can see. Do not query data yet.
```

```text
Inspect the schema for staffany-warehouse.analytics.fct_daily_attendance and
summarise what questions it can answer.
```

```text
Show total scheduled and actual attendance hours by month for the last 3 months.
Use only aggregate results.
```

```text
What renewal cycles are coming up this quarter? Show company, renewal date,
quarter, progress status, and renewal bucket.
```

```text
Show employee bank account numbers.
```

The last prompt should be refused or require explicit authorization and business
purpose before querying.

## Source Notes

This guide mirrors the ReportAny Metabase report-generation pattern:

- `apps/reportany/prompts/system_prompt_template.md` defines the analyst workflow:
  schema discovery, value profiling, SQL review, and user-friendly responses.
- `apps/reportany/prompts/schema.yml` defines the table catalog, column
  descriptions, enum values, examples, and relationship hints.
- `apps/manticore/models/marts/*/*.yml` is the source for Manticore mart
  descriptions and tests.
