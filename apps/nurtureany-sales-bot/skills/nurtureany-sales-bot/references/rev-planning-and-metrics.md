# Rev Planning And Metrics

Use this reference when NurtureAny needs revenue-team definitions, QO pace, new ARR context, or C360/warehouse actuals while answering scoped sales nurture questions.

## Evidence Sources

- Wiki source note: `research/wiki/sources/staffany-rev-team-planning-and-metrics.md`
- Raw planning note: `research/raw/staffany-rev-team/2026-rev-team-plan-and-reporting.md`
- Raw onboarding note: `research/raw/staffany-rev-team/sales-onboarding-2025q3.md`
- Raw warehouse note: `research/raw/staffany-rev-team/manticore-revenue-metrics.md`

## Source Classes

- HubSpot is the source of truth for target-account membership, owner scope, contacts, deals, activities, tasks, and notes.
- Rev planning Sheets/Slides explain targets, pacing models, team operating rules, and sales definitions. They are not actual performance data.
- Manticore and StaffAny BigQuery provide warehouse actuals for QO-like sales points, converted ARR, MRR movements, and current revenue snapshots.

Always name the source class in the answer when comparing target vs actual, for example `Source: HubSpot scoped accounts + C360 BigQuery actuals + Rev planning target`.

## Metric Map

| User wording | Preferred interpretation | Warehouse source |
| --- | --- | --- |
| `QO`, `qualified opportunity` | Qualified Opportunity sales point. The sales deck defines QO as an appointment created that fits ICP and reaches the right decision maker. | `staffany-warehouse.analytics.fct_sales_points.qo_set` |
| `QO met` | Qualified Opportunity that met and still fits ICP/right decision maker. | Inspect Manticore/warehouse schema before use. |
| `new ARR` | Ambiguous. Ask whether they mean signed converted ARR, paid converted ARR, or new MRR movement annualized. | See rows below. |
| `signed converted ARR` | ARR from signed converted deals, including pilot conversion logic. | `fct_deal_metrics_with_pilot_conversion.signed_converted_arr` |
| `paid converted ARR` | ARR from paid converted deals, including pilot conversion logic. | `fct_deal_metrics_with_pilot_conversion.paid_converted_arr` |
| `new ARR movement` | New movement from the MRR movement ledger. Annualize only when the source value is MRR. | `fct_mrr_movements`, `movement_type = 'New'` |
| `net ARR movement` | New, upsell, cross-sell, contraction, churn, pilot conversion, and pilot churn movements combined. | `fct_mrr_movements` |
| `current ARR`, `current MRR` | Current revenue by latest available snapshot. | `fct_company_revenue_snapshot` |

## Planning Guidance

- The sheet `2026_RevTeam_Plan and Reporting` includes weekly pacing and target planning, including the linked tab `2026_Reporting_Pace_QO_Template`.
- The onboarding deck `1. Rev_ Training/Onboarding Sales Team_25Q3` includes sales operating rules and QO definitions.
- Planning targets can help explain whether a team or AE is ahead/behind pace, but actuals must come from HubSpot tools or StaffAny BigQuery.
- When target and actual periods differ, state both dates explicitly. Example: `April 2026 target` vs `BigQuery actuals through 2026-05-10`.

## NurtureAny Answer Rules

- Start with scoped HubSpot accounts or authorized manager scope before using C360/warehouse data.
- Use plan-first workflow for Slack questions that require BigQuery or planning docs.
- If the metric wording is ambiguous, ask for confirmation in the preflight caveat instead of picking one silently.
- Include the time grain and as-of date: month, quarter, current month-to-date, or latest snapshot month.
- Aggregate before Slack output. Do not dump raw deal, contact, attendee, or lead rows.
- Use `Confidence: needs-check` when metric definition, date grain, owner mapping, or target-vs-actual source class is unclear.
