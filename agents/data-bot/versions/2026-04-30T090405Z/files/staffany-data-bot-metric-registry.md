# StaffAny Data Bot Metric Registry

Use this file before answering known Da Ta Bot POC metrics. This registry is a contract of metric status, not proof that every definition is production-ready.

## Confidence Rules

- Use `confidence: verified` only when the metric definition is confirmed by a source/dashboard owner and the query succeeds.
- Use `confidence: needs-check` when the query uses candidate logic, inferred source fields, unvalidated dashboard parity, or a table that still needs owner confirmation.
- Use `confidence: blocked` when BigQuery auth/tooling fails, required Slack context is unreadable, or the source tables needed to answer cannot be inspected.
- Always state source table(s), filters/time window, and caveat.
- Hide SQL unless the user asks for it.

## Metric: Active New Joiner Form Usage

- Common questions:
  - Which StaffAny organizations have active new joiner forms?
  - How many organizations are using new joiner forms?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed by product/dashboard owner.
- Candidate source path:
  - Prefer an analytics mart or modeled table if one exists in `staffany-warehouse.analytics`.
  - If no mart exists, inspect warehouse tables that expose Kraken new joiner form data.
  - Pantheon implementation evidence references New Joiner form entities such as `NewJoinerForms`, `NewJoinerFormFields`, `NewJoinerEntries`, and `NewJoinerDocumentUploads`; do not assume these exact source names exist in analytics.
- Required discovery:
  - Inspect schemas first.
  - Discover actual status/enabled/published/deleted columns before filtering.
  - Confirm whether "active" means enabled, published, has at least one active form, has recent entries, or matches a dashboard filter.
- Default caveat:
  - "Definition of active new joiner form is not owner-verified; treating this as candidate usage."

## Metric: PPH On Us

- Common questions:
  - Which Indonesia payroll accounts have PPH on us?
  - How many ID payroll organizations use PPH on us?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until Abel or another payroll metric owner confirms the definition.
- Candidate source path:
  - Start with `staffany-warehouse.analytics.fct_payroll_report` for generated payroll evidence.
  - Relevant candidate fields include `id_pph21_method`, `id_pph21_allowance`, `id_pph21_deduction`, `id_taxable_income`, and payroll run fields after schema inspection.
- Important rule:
  - Do not define PPH on us as `id_pph21_method = NETTO`.
  - `id_pph21_method = NETTO` is only a candidate signal and may be wrong on its own.
  - Prefer actual generated payroll behavior and broader PPH setup logic once confirmed by Abel/metric owner.
- Required discovery:
  - Inspect schema and latest available payroll periods.
  - Check whether the question asks for configured accounts, payrolls already generated, or organizations with any historical payroll using candidate PPH-on-us signals.
  - If using candidate logic, explain which generated payroll fields were used.
- Default caveat:
  - "PPH-on-us definition is not owner-verified; `id_pph21_method = NETTO` alone is not treated as definitive."

## Metric: IR8A Submitted

- Common questions:
  - Which organizations submitted IR8A?
  - How many IR8A submissions were completed for a tax year?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed against source/dashboard owner.
- Candidate source path:
  - Prefer an analytics mart or modeled table if one exists.
  - If no mart exists, inspect warehouse tables for IR8A submission data.
  - Pantheon implementation evidence references IR8A submission entities with organization, business entity, year, status, and submitted timestamp fields; do not assume exact analytics table or column names without schema inspection.
- Required discovery:
  - Inspect schema for status values.
  - Discover submitted/completed status values before filtering.
  - Ask for tax year if absent and materially affects the answer.
- Default caveat:
  - "IR8A submitted status mapping is not owner-verified; treating discovered submitted/completed statuses as candidate logic."

## Metric: Red Accounts

- Common questions:
  - List red accounts.
  - Which customer accounts are red?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed by RevOps/CS/dashboard owner.
- Candidate source path:
  - Start with revenue/customer usage marts such as `staffany-warehouse.analytics.fct_company_org_mrr` and related company/org dimensions after schema inspection.
  - Candidate fields include `company_usage_status`, `company_usage_next_step`, and `company_low_usage_reason` if present.
- Required discovery:
  - Discover actual status/category values before filtering for "red".
  - Confirm whether "red" means health status, usage status, renewal risk, CS risk, or dashboard color.
  - Return organization/company display names rather than raw IDs where possible.
- Default caveat:
  - "Red-account definition is not owner-verified; using discovered customer usage status values as candidate logic."

## Metric: Fitness Customers

- Common questions:
  - List fitness customers.
  - Which StaffAny customers are in the fitness segment?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed by RevOps/CS/dashboard owner.
- Candidate source path:
  - Start with company/org revenue and usage marts such as `dim_companies`, `fct_company_org_mrr`, or linked-org revenue marts after schema inspection.
  - Candidate fields include `company_industry`, `company_industry_staffany`, `industry_group`, or equivalent industry/segment fields if present.
- Required discovery:
  - Discover actual industry/segment values before filtering.
  - Match only discovered values that clearly represent fitness, gym, wellness, sports, or closely related segments.
  - Explain included value mappings if the match is fuzzy.
- Default caveat:
  - "Fitness customer segment is not owner-verified; using discovered industry/segment values as candidate logic."
