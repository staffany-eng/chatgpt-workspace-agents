---
name: pph21-settings-explainer
description: Explain which StaffAny user settings, organisation settings, payroll inputs, pay item tax parameters, and Indonesia PPh21 reference tables affect PPh21 calculation. Use when asked why PPh21 changed, what setup values drive Indonesian tax, which employee fields matter, or how PTKP, employment status, calculation method, tax paid, beginning netto, DTP, join/resign dates, and taxable pay items influence PPh21.
---

# PPh21 Settings Explainer

## Purpose

Explain the settings and tax parameters that feed Indonesia PPh21 calculation. This skill is for setup-level analysis, not a full payslip reconciliation. If the user also asks to reconcile take-home pay, use `$employee-payroll-breakdown` together with this skill.

## Guardrails

- Use read-only evidence. Prefer StaffAny Data Bot access for Metabase or warehouse-backed checks.
- Do not expose sensitive identifiers such as full NPWP, national ID, bank account, or unrelated employee data.
- Separate direct inputs from derived outputs. For example, `taxRate` and `pph21Deduction` in a payrun summary are outputs, while `ptkpStatus` and `calculationMethod` are inputs.
- If a setting is present in the UI/model but not proven to affect PPh21 code, say `Not proven to affect PPh21`.
- For current legal rates or regulation interpretation, verify against the code and seeded reference tables first; do not rely on memory.

## Primary Settings To Check

### Employee Tax Detail

Source model: `apps/kraken/src/database/models/PPh21/IndonesiaEmployeeTaxDetail.ts`.

- `taxYear`: selects the employee tax detail row for the payroll year.
- `ptkpStatus`: determines PTKP category and annual non-taxable income.
- `employmentStatus`: helps choose PPh21 method. Freelance uses freelance calculation; non-permanent uses TER; permanent/contract can become TER or annualized depending on month/resignation.
- `calculationMethod`: changes who bears PPh21 and how it appears: `Gross`, `Gross-up`, `Taxable Netto`, or `Netto`.
- `beginningNetto`: added to annual taxable income in annualized calculation.
- `taxPaid`: reduces current annualized PPh21 due.

API anchors:
- `apps/kraken/src/server/plugins/pph21/types.ts`
- `apps/kraken/src/server/plugins/pph21/IndonesiaEmployeeTaxDetail/upsert.ts`

### Employee Identity And Employment Dates

Source models:
- `apps/kraken/src/database/models/PPh21/IndonesiaIdentificationInformation.ts`
- `apps/kraken/src/database/models/OrgUserDetail.ts`

Explain carefully:
- `citizenship` and `npwpNumber` are stored as Indonesia identification information. Only claim they affect PPh21 when the calculation code proves it for the inspected scenario.
- `joinDate` affects annualized position allowance working-month proration and DTP eligibility timing.
- `resignDate` can make a payrun annualized when the payrun month matches the resignation period after payroll cutoff handling.

### Organisation Settings

Source anchors:
- `apps/kraken/src/database/models/OrganisationDetail.ts`
- `apps/kraken/src/database/repos/organisationDetailRepo.ts`
- `apps/kraken/src/database/models/Payroll/IndonesiaDTPOrganisationSetting.ts`
- `apps/kraken/src/database/models/Payroll/IndonesiaDTPRegulation.ts`

Settings:
- `payrollCutOffDate`: affects resignation-month method selection and join-month proration.
- Indonesia DTP organisation setting: controls whether the PPh21 DTP regulation is enabled for the org.
- DTP regulation max threshold and effective rule name influence DTP eligibility.

### Payrun And Pay Item Parameters

Source anchors:
- `apps/kraken/src/database/models/Payroll/enums.ts`
- `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21.ts`

Parameters:
- Payrun `year`, `month`, and `order`: determine tax detail year, TER vs annualized behavior, same-month prior payrun offsets, and year-to-date annualized offsets.
- `businessEntityId`: scopes prior-payrun PPh21 summaries.
- Pay item `category`: only taxable `Gross Addition`, `Gross Deduction`, `Employee Statutory`, and `Employer Statutory` categories feed PPh21 taxable buckets.
- Pay item Indonesia `taxCategory`: items marked `Not Taxable` are excluded from PPh21 taxable base.
- Payrun item `amount`: signed amount used in taxable gross/statutory totals.

### Government/Reference Tables

Source models:
- `apps/kraken/src/database/models/PPh21/PTKPStatusType.ts`
- `apps/kraken/src/database/models/PPh21/IndonesiaMonthlyTaxRate.ts`
- `apps/kraken/src/database/models/PPh21/IndonesiaNonTaxableIncome.ts`
- `apps/kraken/src/database/models/PPh21/IndonesiaProgressiveTaxRate.ts`

Parameters:
- PTKP status list: `TK/0`, `TK/1`, `TK/2`, `TK/3`, `K/0`, `K/1`, `K/2`, `K/3`.
- TER category mapping: TK0/TK1/K0 -> A; TK2/TK3/K1/K2 -> B; K3 -> C.
- Monthly TER rates: selected by category, taxable income bracket, and effective date.
- Non-taxable income: annual PTKP amount by PTKP status.
- Progressive tax rates: annualized and freelance calculations use progressive brackets.

## How Each Setting Changes PPh21

1. `calculationMethod`
- `Gross`: tax becomes employee deduction.
- `Gross-up`: tax is added as PPh21 allowance and deducted again; gross-up paths iterate until tax stabilizes.
- `Taxable Netto`: tax becomes `pph21Payment`, a company-paid benefit/payment, instead of employee deduction.
- `Netto`: standard PPh21 calculation returns zero deduction/allowance/payment.

2. `employmentStatus`
- `Freelance`: tax base is 50% of taxable income plus same-month previous taxable income, then progressive tax is applied.
- `Non-Permanent`: method is TER.
- `Permanent` or `Contract`: method is TER for normal months and annualized for December or resignation payrun month.

3. `ptkpStatus`
- Sets TER category for monthly TER.
- Sets annual PTKP non-taxable income for annualized calculation.

4. `beginningNetto` and `taxPaid`
- `beginningNetto` increases annual taxable income when annualized.
- `taxPaid` reduces current annualized tax due.

5. `joinDate`, `resignDate`, and `payrollCutOffDate`
- `joinDate` can reduce completed working months for annualized position allowance.
- `resignDate` can trigger annualized method.
- `payrollCutOffDate` decides whether join/resign dates after cutoff roll into the next payroll month.

6. Pay item category and tax category
- Taxable gross additions/deductions and taxable employer statutory feed `taxableIncome`.
- Taxable employee statutory is tracked separately and reduces annualized income subject to progressive tax.
- Non-taxable pay items do not feed the PPh21 tax base.

7. DTP settings
- Org-level DTP enablement and regulation threshold decide eligibility.
- If eligible, PPh21 DTP can offset or appear as relief based on the calculated PPh21 result and year-to-date DTP.

## Investigation Workflow

1. Identify the target scope.
- If the user names an employee/month/org, resolve the org, employee, payroll year/month, and payrun order.
- If the user asks generally, explain the setting map without querying employee data.

2. Pull current settings only when needed.
- Employee tax detail for the target tax year.
- Org user detail join/resign dates.
- Organisation payroll cutoff date and DTP settings.
- Pay item categories/tax categories for the relevant payrun items.
- Reference table rows for PTKP, monthly TER, and progressive brackets when a rate explanation is needed.

3. Classify each setting.
- `Direct employee setting`
- `Organisation setting`
- `Payrun/pay item input`
- `Government/reference parameter`
- `Derived payrun output`

4. Explain impact.
- Say whether changing the setting changes method selection, taxable base, tax rate/bracket, annual offset, payslip presentation, or DTP eligibility.
- Include whether the impact applies to TER, annualized, freelance, or all PPh21 paths.

## Useful Code Anchors

- Employee tax settings model: `apps/kraken/src/database/models/PPh21/IndonesiaEmployeeTaxDetail.ts`.
- Identification model: `apps/kraken/src/database/models/PPh21/IndonesiaIdentificationInformation.ts`.
- Payroll enums: `apps/kraken/src/database/models/Payroll/enums.ts`.
- PPh21 method selection and taxable buckets: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21.ts`.
- TER rate and gross-up behavior: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21TERCalculator.ts`.
- Annualized, PTKP, position allowance, and prior-payrun offsets: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21AnnualizedCalculator.ts`.
- Freelance calculation: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21FreelanceCalculator.ts`.
- DTP eligibility and DTP amount: `apps/kraken/src/server/lib/payroll/statutory/pph21/dtpCalculator.ts`.

## Output Format

Use this structure:

1. `Short answer`: concise explanation of the biggest settings affecting PPh21.
2. `Settings map`: table with setting, source, current value if inspected, calculation impact, and code evidence.
3. `Method impact`: explain why the employee uses TER, annualized, freelance, or netto.
4. `Tax base and rate impact`: explain taxable item inputs, PTKP/TER/progressive tables, and offsets.
5. `DTP impact`: include only if DTP may apply.
6. `Not affecting / not proven`: list fields the user asked about that are stored but not proven to affect the calculation.

## Starter Prompt

`Use $pph21-settings-explainer to explain which employee settings and tax parameters affect PPh21 for <employee/org/month>, and which ones do not.`
