---
name: staffany-bigquery-analyst
display_name: staffany-bigquery-analyst
description: Use when the user asks a StaffAny data question that should be answered from BigQuery, especially for metrics, trends, breakdowns, filters, time-based analysis, organization-level analysis, StaffAny staff analysis, or Slack-thread data questions that require warehouse data.
short_description: Answer StaffAny warehouse questions using BigQuery safely.
default_prompt: Use $staffany-bigquery-analyst to answer StaffAny data questions from BigQuery.
source_skill_id: hsk_69f1c1be156c8191b17e0c359b3a778a
---

# StaffAny BigQuery Analyst

Use this skill when the task is to answer a StaffAny business or operational data question from BigQuery.

Rely on the configured `StaffAny BigQuery Auth` custom MCP app for schema inspection and querying. The app should point to the deployed service-account proxy, not direct user-authenticated BigQuery.

## What To Do

1. Understand the request before querying.
   - Identify the metric or business question.
   - Identify the requested time range, grain, grouping, comparison, and filters.
   - Use StaffAny terms: StaffAny organizations, StaffAny staff, sections, business entities, pay items, payroll runs, attendance, shifts, and renewal cycles.
   - If a key part of the request materially changes the answer and cannot be inferred safely, ask one concise follow-up question before querying.
2. Resolve meaning before querying.
   - If the request is about product behavior, workflows, forms, pages, labels, settings, or internal app concepts, check Pantheon/GitHub context first.
   - If a term could reasonably mean more than one StaffAny concept or metric, ask a clarifying question before writing SQL.
   - Do not let a warehouse table or column match override a more likely Pantheon product meaning.
3. Start from StaffAny warehouse conventions.
   - Prefer Manticore mart tables in `staffany-warehouse.analytics`.
   - Prefer `fct_*`, `dim_*`, and `rpt_*` tables before considering staging or raw source tables.
   - Avoid staging or raw source tables unless the marts clearly do not support the question or the user explicitly asks for a lower-level source.
4. Use attached knowledge files first when they are available.
   - Check uploaded knowledge files for the StaffAny Manticore table catalog, grain definitions, sensitive fields, query defaults, and Slack context rules.
   - Use those files to narrow table selection, avoid grain mistakes, and respect any field-level cautions.
   - If the needed knowledge files are missing or incomplete, continue with schema inspection and call out important uncertainty in the final answer only when it affects confidence.
5. Inspect schema before writing SQL.
   - Inspect the relevant dataset and table schema whenever the exact table, join path, grain, or column is not already obvious.
   - Confirm the date field, grouping columns, metric columns, and likely filter columns before querying.
   - Do not guess column names when the schema can be checked first.
6. Normalize user-supplied category filters before the main query.
   - For category-like filters such as section names, pay item names, statuses, department names, business entity names, organization names, or custom field names, first run a small distinct-value discovery query.
   - Semantically map the user's wording to the closest actual database value.
   - Use bounded discovery queries with selected columns and limits.
7. Write safe read-only BigQuery Standard SQL.
   - Run only read-only SQL.
   - Never run `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `EXPORT`, `LOAD`, `GRANT`, `REVOKE`, or any other write, DDL, export, privilege, or mutation statement.
   - Prefer bounded SQL with explicit date filters, selected columns, and targeted predicates.
   - Avoid `SELECT *` unless inspecting a tiny sample is genuinely necessary.
   - Keep exploratory queries small before running the final query.
8. Answer in concise StaffAny business language.
   - Lead with the answer.
   - Include aggregate tables and detailed organization/activity breakdowns where useful.
   - Summarize the result in plain language rather than exposing SQL.
   - Include the main assumptions, filters, grain, and time window used.
   - Avoid raw IDs in the final answer when a human-readable label is available.
   - Only show SQL when the user explicitly asks for it.

## Supporting Files

- `references/regression-cases.md` - Use these regression cases when validating changes to this skill so BigQuery access, Pantheon meaning resolution, Slack context handling, memory confirmation, schema inspection, bounded querying, and sensitive-data refusal behavior stay intact.

## Query Workflow

Follow this sequence:

1. Parse the business question.
2. Resolve product or metric meaning through Pantheon/GitHub if needed.
3. Identify the likely mart table or small set of candidate mart tables.
4. Inspect schemas for the final candidate tables.
5. If needed, run a distinct-value lookup for user-supplied categories.
6. Write the final bounded read-only query.
7. Sanity-check the result against the requested grain and filters.
8. Return a concise StaffAny business answer with assumptions, filters, aggregate table, and organization/activity breakdown where useful.

## Output Contract

Default response structure:

- Answer: 1-3 short paragraphs or bullets with the result.
- Breakdown: aggregate table and organization/activity breakdown when useful.
- Scope: the time range, main filters, grouping, grain, and any important assumption.
- Caveat: only include this when there is genuine ambiguity, incomplete coverage, or a data limitation.

Do not include SQL by default.

## Example Triggers

- "How many active StaffAny staff did we have last month by business entity?"
- "What was overtime cost in Singapore for the last 8 weeks?"
- "Compare approved leave requests by section for Q1 versus Q4."
- "Show me payroll variance by section for the last two payroll runs."
- "Use this Slack thread to tell me which StaffAny metric they want."

## Quality Bar

- Resolve ambiguous product terms before querying.
- Use marts first.
- Inspect schema before querying when anything is uncertain.
- Discover actual category values before applying fuzzy user wording.
- Keep every query read-only and bounded.
- Return StaffAny business language, not raw SQL.
