# StaffAny Rev Team Planning And Metrics

## Source Metadata

- Type: private revenue planning, sales onboarding, and warehouse metric evidence
- Source class: StaffAny Rev Team operating model and Manticore metric lineage
- Source URLs or paths:
  - `https://docs.google.com/spreadsheets/d/1iinxJg3HmHhurDSUJlZew9Nv8of_wMWwieptmcLRIk8/edit?gid=1934739289#gid=1934739289`
  - `https://docs.google.com/presentation/d/1LpkkwtkrmkEWFJt4cT4mnVSGIRRG448LG1Lqu4NBA_8/edit?slide=id.g26982aca271_0_1244#slide=id.g26982aca271_0_1244`
  - `/Users/leekaiyi/workspace/manticore`
- Date ingested: 2026-05-10
- Context: StaffAny Rev Team 2026 planning, sales operating standards, and actual metrics available to NurtureAny/Hermes data workflows
- Default weight: 4 for current StaffAny revenue-metric routing and operating context; 3 when generalized outside StaffAny Rev workflows
- Privacy: private

## Context Caveat

This source combines planning targets, training rules, dbt metric definitions, and live aggregate BigQuery outputs.
Planning sheets and training decks describe intent and operating context; Manticore/BigQuery describes actual metric lineage.
Do not treat sheet targets as actual revenue performance, and do not generalize StaffAny-specific sales policy into a universal agent rule.

## Evidence Used

- Raw record: [2026 Rev Team Plan And Reporting](../../raw/staffany-rev-team/2026-rev-team-plan-and-reporting.md)
- Raw record: [Rev Training And Onboarding Sales Team 25Q3](../../raw/staffany-rev-team/sales-onboarding-2025q3.md)
- Raw record: [Manticore Revenue Metrics And BigQuery Aggregates](../../raw/staffany-rev-team/manticore-revenue-metrics.md)

## What They Said

- The 2026 revenue plan turns yearly ARR goals into monthly bottom-up estimates and then weekly committed pace, with weekly quarter reporting and monthly year-to-date reporting.
- The linked QO pace tab tracks weekly QO goals, gains, cumulative results, and pace by segment or market.
- The workbook separates initiative planning from pace tracking: initiatives have QO-setting, closing, market, DRI, execution lead, assist, month, and execute-status fields.
- Bottom-up planning converts funnel assumptions into ARR using leads, activities, QO rates, closing rates, deal counts, headcount, price per head, ACV, and ARR output.
- The sales onboarding deck defines 450 capacity points per week and maps operational activity types into points.
- The onboarding deck distinguishes QO, QO met, Deal Signed ARR, and Deal Paid ARR as separate reporting concepts.
- The deck sets sales hygiene expectations around HubSpot logging, daily standup or standdown, follow-up within 24 hours, and revenue Slack updates after meetings.
- The requested activity metric is QO. Manticore's current QO source is `fct_sales_points.qo_set`.
- `fct_sales_points` computes `qo_set` from HubSpot deals that meet appointment-owner, employee-size, appointment-date, and new-business filters.
- `fct_deal_metrics_with_pilot_conversion` exposes deal ARR, signed converted ARR, paid converted ARR, eligible revenue, pilot status, conversion status, and outbound status.
- `fct_mrr_movements` is the MRR movement ledger for New, Upsell, Cross-sell, Contraction, Churn, Pilot Conversion, and Pilot Churn.
- Aggregate BigQuery output on 2026-05-10 showed January to May 2026 QO set of 122, 116, 78, 83, and 16, with May being month-to-date.
- The latest company revenue snapshot query returned April 2026 as the latest snapshot month, with total ARR about 2.30M and total MRR about 191.54k.

## Evidence Trace

- Claim: The 2026 revenue plan turns yearly ARR goals into monthly and weekly pace. Evidence: the raw sheet extract states the planning and reporting flow. Source: `research/raw/staffany-rev-team/2026-rev-team-plan-and-reporting.md:29`.
- Claim: The linked QO pace tab tracks weekly QO goals, gains, cumulative result, and pace by segment or market. Evidence: the raw sheet extract lists the QO pace dimensions. Source: `research/raw/staffany-rev-team/2026-rev-team-plan-and-reporting.md:32`.
- Claim: The workbook separates initiative planning from pace tracking. Evidence: the guide and initiatives table define QO Setting, Closing, DRI, Execution Lead, Assist, Month, and Execute. Source: `research/raw/staffany-rev-team/2026-rev-team-plan-and-reporting.md:38`.
- Claim: Bottom-up planning converts funnel assumptions into ARR. Evidence: the SG bottom-up extract lists leads, QO rates, closing rate, deal count, headcount, price, ACV, and ARR. Source: `research/raw/staffany-rev-team/2026-rev-team-plan-and-reporting.md:40`.
- Claim: The onboarding deck defines 450 capacity points per week and activity point mappings. Evidence: the linked-slide extract lists capacity and activity point values. Source: `research/raw/staffany-rev-team/sales-onboarding-2025q3.md:32`.
- Claim: The onboarding deck distinguishes QO, QO met, Deal Signed ARR, and Deal Paid ARR. Evidence: key definitions list those reporting concepts separately. Source: `research/raw/staffany-rev-team/sales-onboarding-2025q3.md:46`.
- Claim: The deck sets hygiene expectations around logging, standup, follow-up, and Slack updates. Evidence: sales basics and SLA extracts describe those operating standards. Source: `research/raw/staffany-rev-team/sales-onboarding-2025q3.md:38`.
- Claim: Manticore's current QO source is `fct_sales_points.qo_set`. Evidence: the information-schema extract records `qo_set`, and the user clarified the intended metric is QO. Source: `research/raw/staffany-rev-team/manticore-revenue-metrics.md:24`.
- Claim: `fct_sales_points` computes `qo_set` from appointment-owner, employee-size, appointment-date, and new-business filters. Evidence: the raw metric extract records the calculation. Source: `research/raw/staffany-rev-team/manticore-revenue-metrics.md:28`.
- Claim: `fct_deal_metrics_with_pilot_conversion` exposes ARR conversion and eligibility fields. Evidence: raw extracts record the signed, paid, and eligible revenue calculations. Source: `research/raw/staffany-rev-team/manticore-revenue-metrics.md:31`.
- Claim: `fct_mrr_movements` is the MRR movement ledger. Evidence: raw extracts record the movement categories and ARR-to-MRR derivation. Source: `research/raw/staffany-rev-team/manticore-revenue-metrics.md:34`.
- Claim: Aggregate BigQuery output returned January to May 2026 QO set values. Evidence: raw aggregate output records the five monthly values as of 2026-05-10. Source: `research/raw/staffany-rev-team/manticore-revenue-metrics.md:39`.
- Claim: The latest revenue snapshot was April 2026 with about 2.30M ARR and 191.54k MRR. Evidence: raw aggregate output records the latest snapshot query result. Source: `research/raw/staffany-rev-team/manticore-revenue-metrics.md:44`.

## Learning Summary

- NurtureAny and Hermes Data Bot should separate plan targets from actuals: Sheets and Slides provide Rev Team intent, while Manticore/BigQuery provides actual metric lineage.
- For QO requests, prefer `fct_sales_points.qo_set`.
- For new ARR, be explicit about which definition is needed: signed converted ARR, paid converted ARR, or New ARR from the MRR movement ledger.
- For revenue movement questions, `fct_mrr_movements` is the right source for New, Upsell, Cross-sell, Contraction, Churn, Pilot Conversion, and Pilot Churn.
- For current ARR/MRR by company or product split, use `fct_company_revenue_snapshot` and state the latest available snapshot month.
- Agent answers about Rev Team performance should quote the source date and whether the current month is partial.
- Sales activity metrics should respect the deck's operating vocabulary: QO, QO met, appointment set, ABM, connected calls, and non-email outreach.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, `research/wiki/sources/bigquery-mcp-proxy.md`, `research/wiki/sources/staffany-hermes-data-bot-poc.md`
- Evidence weight check: weight 4 for current StaffAny revenue data-bot routing; weight 3 outside StaffAny Rev-specific workflows.
- Decision: use this as StaffAny-specific metric-routing and operating-context evidence for NurtureAny and Hermes Data Bot, not as general workspace-agent product truth.

## Possible Agent Builder Relevance

- Agent-synthesized: Add NurtureAny metric guidance that separates planning artifacts from actual warehouse metrics.
- Agent-synthesized: Teach the bot to ask which ARR definition is wanted when a user says "new ARR" without specifying signed, paid, or movement-ledger ARR.
- Agent-synthesized: Store the Manticore table map as a durable reference for Rev Team metric answers.
- Do-not-promote: Do not copy raw Sheet rows, deck role-play personal examples, or warehouse row-level data into app files or memory.

## Follow-Up Questions

- Should Hermes Data Bot add a small Rev metrics glossary for QO, QO met, signed ARR, paid ARR, eligible revenue, and ARR movement?
- Should the bot default "new ARR" to `fct_mrr_movements` New movement ARR, or ask every time unless the user says signed or paid?
- Should weekly QO pace targets from the planning Sheet be ingested into a structured local reference, or kept as source evidence only?
