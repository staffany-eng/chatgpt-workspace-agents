---
name: employee-payroll-breakdown
description: Deconstruct how an employee's take-home pay was calculated in StaffAny payroll. Use when given an organisation name, employee name, target month/year, and take-home pay, especially to reconcile payrun components, payslip figures, payroll snapshots, statutory deductions, and Indonesia PPh21 calculations with TER rate, PTKP status, taxable gross basis, and annualized variables.
---

# Employee Payroll Breakdown

## Purpose

Explain how a specific employee's take-home pay was produced for one payroll month. Default input is:
- Organisation name.
- Employee name.
- Payroll month/year.
- Expected take-home pay.

The output should reconcile the expected amount against the stored payrun participant summary and explain each payroll component in plain business language.

## Required Guardrails

- Use read-only data access only. Prefer StaffAny Data Bot access for Metabase or warehouse-backed payroll checks.
- Do not expose unrelated employees, full bank account numbers, national ID numbers, or credentials.
- Treat payroll data as sensitive. Return only the employee, org, payrun, and component details needed to answer the request.
- Never invent missing payroll components. If the database or code does not prove a figure, mark it as `Not proven yet`.
- For production data, ask for or use the appropriate approved readonly profile; do not run mutating admin endpoints.

## Investigation Workflow

1. Resolve the organisation, employee, and month.
- Search by organisation name and employee display/name fields.
- If the employee name is ambiguous, list the possible matches with non-sensitive identifiers and ask for confirmation.
- Convert the month into Kraken payrun fields: `month` is 1-12 and `year` is four digits.

2. Find the relevant payrun participant.
- Locate payruns for the organisation and month/year.
- Include payrun `order` because multiple payruns can exist in the same month.
- Find the participant for the employee across those payruns.
- Compare `summary.totalTakeHomePay` to the user-provided amount. If several participants/payruns contribute to a bank payment, sum only the matching employee's participant rows and call this out.

3. Pull the calculation facts.
- Payrun participant summary JSON, especially `grossSalary`, `netTotal`, `allStatutory`, `totalTakeHomePay`, `employeeStatutory`, `employerStatutory`, and country-specific statutory fields.
- Payrun items joined with pay items: name, category, tax category, amount, compensation id, and whether the item is gross addition, gross deduction, net addition, net deduction, employee statutory, or employer statutory.
- Compensation snapshot rows used by the participant when the question involves salary proration, join/resign dates, unpaid leave, hourly/event pay, or working days.
- Payslip data path if display differs from raw items: `apps/kraken/src/server/lib/payroll/payslip/formatPayslipData.ts`.

4. Reconcile take-home pay.
- Start with gross additions and gross deductions.
- Add net additions.
- Subtract net deductions and employee statutory deductions.
- Include country-specific statutory treatment from the participant summary.
- Confirm the final number equals `summary.totalTakeHomePay`; if it differs from the user's expected value, show the variance.

5. Explain component calculations.
- For each material component, show `component name`, `category`, `amount`, and `why it affects take-home pay`.
- For prorated base pay, cite the compensation snapshot and period facts used; do not guess the proration formula until verified in code or stored rows.
- Distinguish pay items that affect taxable income from pay items that only affect net pay.

## Indonesia PPh21 Workflow

Use this section when the organisation/payrun is Indonesia payroll or the participant summary contains PPh21 fields.

1. Read the stored PPh21 summary.
- `summary.taxableIncome`
- `summary.taxableEmployeeStatutory`
- `summary.taxableEmployerStatutory`
- `summary.annualTaxableIncome` when present
- `summary.taxRate`
- `summary.positionAllowance`
- `summary.pph21Method`
- `summary.statutory.pph21Allowance`
- `summary.statutory.pph21Deduction`
- `summary.statutory.pph21Payment`
- `summary.statutory.pph21Dtp`
- `summary.isDTPEligible`
- Employee tax settings for the payrun year: `ptkpStatus`, `employmentStatus`, `calculationMethod`, `beginningNetto`, and `taxPaid`.
- Payrun context: `year`, `month`, `order`, `businessEntityId`, join date, resign date, and organisation payroll cutoff date.

2. Verify the taxable base.
- Code anchor: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21.ts`.
- `calculateTaxable` includes taxable gross additions/deductions and taxable employer statutory in `taxableIncome`.
- Employee statutory is tracked separately as `taxableEmployeeStatutory` and is included in annualized tax basis.
- Items with Indonesia tax category `Not Taxable` are excluded from the PPh21 taxable base.
- Always show the gross income/taxable income basis used for PPh21:
  - `taxableGross`: taxable gross additions plus taxable gross deductions.
  - `taxableEmployerStatutory`: taxable employer statutory included in TER taxable income.
  - `taxableForTER = taxableGross + taxableEmployerStatutory`.
  - `taxableForAnnual = taxableForTER + abs(taxableEmployeeStatutory)`.
- If the warehouse/report does not expose `taxableGross` directly, reconstruct it from payrun items by summing taxable `Gross Addition` and taxable `Gross Deduction` items, then reconcile to stored `summary.taxableIncome`.

3. Explain method selection.
- `NETTO` when calculation method is `Netto`.
- `FREELANCE` when employment status is `Freelance`.
- `TER` for non-permanent employees and regular non-final months.
- `ANNUALIZED` for December or the payrun month matching the employee's resignation period after payroll cutoff handling.

4. Explain TER calculation.
- Code anchor: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21TERCalculator.ts`.
- Always show `ptkpStatus`, derived TER category, TER `%` used, and the taxable income bracket/rate source.
- Determine PTKP category from PTKP status: TK0/TK1/K0 -> A; TK2/TK3/K1/K2 -> B; K3 -> C.
- Add taxable income from earlier payruns in the same month and lower payrun order.
- Show `incomeToTax = taxableForTER + same-month previous taxable income`.
- Gross/Netto TER tax is `incomeToTax * TER%`.
- Gross-up iterates by adding the computed PPh21 to income until the rounded tax stabilizes.
- Subtract prior PPh21 deductions/payments from earlier same-month payruns to get the current payrun's PPh21 amount.
- Always show TER as a step-by-step calculation, not only a final value. Use this calculation trail:
  1. List taxable gross pay items and formula: `taxableGross = taxable gross additions + taxable gross deductions`.
  2. List taxable employer statutory: `taxableEmployerStatutory`.
  3. List taxable employee statutory separately: `taxableEmployeeStatutory`; explain whether it is excluded from TER income but used elsewhere.
  4. Compute `taxableForTER = taxableGross + taxableEmployerStatutory`.
  5. Add same-month lower-order payrun taxable income: `incomeToTax = taxableForTER + priorSameMonthTaxableIncome`.
  6. Resolve PTKP category and TER bracket: `ptkpStatus -> TER category -> bracket min/max -> TER%`.
  7. For Gross/Netto: `grossTERTax = round-or-stored(incomeToTax * TER%)`, then subtract prior same-month PPh21 deductions/payments to get current PPh21.
  8. For Gross-up: show each iteration when relevant: `grossedIncome = incomeToTax + pph21Allowance`, apply TER%, repeat until rounded allowance stabilizes, then subtract prior same-month offsets.
  9. Show final `pph21Allowance`, `pph21Deduction`, `pph21Payment`, `pph21Dtp`, and how they affect take-home pay.
- TER output must include:
  - PTKP status and TER category.
  - Taxable gross/addition-deduction basis.
  - Taxable employer statutory included in TER income.
  - Same-month previous taxable income offset, if any.
  - TER taxable income actually multiplied by the TER rate.
  - TER rate `%`, bracket min/max when available, and effective date/rate table source when available.
  - Prior same-month PPh21 deduction/payment offsets.
  - Final `pph21Allowance`, `pph21Deduction`, and `pph21Payment`.

5. Explain annualized calculation.
- Code anchor: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21AnnualizedCalculator.ts`.
- Annual taxable income equals current taxable income plus previous taxable income in the year plus beginning netto when present.
- Annual taxable employee statutory equals current plus previous taxable employee statutory.
- Income subject to progressive tax equals annual taxable income minus annual taxable employee statutory minus PTKP non-taxable income minus position allowance.
- Progressive annual PPh21 is reduced by prior PPh21 and tax paid to get the current payrun's deduction, allowance, or payment depending on calculation method.
- Always show annualized PPh21 as a step-by-step calculation, not only a final value. Use this calculation trail:
  1. Explain why the payrun is annualized: December or resignation-month logic, plus the payrun month, resign date, payroll cutoff date, employment status, and calculation method.
  2. List taxable gross pay items and formula: `taxableGross = taxable gross additions + taxable gross deductions`.
  3. List `taxableEmployerStatutory` and `taxableEmployeeStatutory`, including which pay items were excluded because tax category is `Not Taxable`.
  4. Compute current basis: `taxableForTER = taxableGross + taxableEmployerStatutory`; `currentTaxableEmployeeStatutory = abs(taxableEmployeeStatutory)`.
  5. Compute yearly offsets before this payrun: `priorTaxableIncome`, `priorTaxableEmployeeStatutory`, `priorPPh21Deduction`, `priorPPh21Allowance`, `priorPPh21Payment`.
  6. Compute `annualTaxableIncome = taxableForTER + priorTaxableIncome + beginningNetto`.
  7. Compute `annualTaxableEmployeeStatutory = currentTaxableEmployeeStatutory + priorTaxableEmployeeStatutory`.
  8. Compute position allowance: completed months from join date/cutoff, `5% x annualTaxableIncome`, monthly cap `500,000 x completedMonths`, then final lower applicable allowance.
  9. Compute progressive taxable income: `PKP = annualTaxableIncome - annualTaxableEmployeeStatutory - PTKP - positionAllowance`; show the floored-to-thousand PKP used by the progressive bracket calculator when PKP is positive.
  10. Apply annual progressive brackets line by line: amount in each bracket, rate, tax per bracket, and total `annualPPh21`.
  11. Convert annual tax to current payrun result by calculation method:
      - Gross: `pph21Deduction = annualPPh21 - priorPPh21Deduction - taxPaid`.
      - Gross-up: also show `pph21Allowance = annualPPh21 - priorPPh21Allowance - taxPaid`.
      - Taxable Netto: `pph21Payment = annualPPh21 - priorPPh21Payment - priorPPh21Deduction - taxPaid`.
  12. Show final `pph21Allowance`, `pph21Deduction`, `pph21Payment`, `pph21Dtp`, and the take-home-pay impact. If the final deduction is negative, explicitly call it a refund/reversal of prior PPh21.
- Annualized output must show all variables that affect the calculation:
  - Method trigger: December or resignation payrun month, including resign date and payroll cutoff date when relevant.
  - Employee tax settings: PTKP status, employment status, calculation method, beginning netto, tax paid.
  - Current taxable basis: taxable gross, taxable employer statutory, taxable employee statutory, taxableForTER, and taxableForAnnual.
  - Prior-year-to-date offsets: previous taxable income, previous taxable employee statutory, previous PPh21 deduction, previous PPh21 allowance, and previous PPh21 payment.
  - Annual taxable income formula: current taxableForTER + prior taxable income + beginning netto.
  - Annual taxable employee statutory formula: current taxable employee statutory + prior taxable employee statutory.
  - PTKP non-taxable income amount used.
  - Position allowance inputs: join date, completed working months, 5% allowance, monthly cap, final position allowance.
  - Income subject to progressive tax.
  - Progressive tax brackets/rates applied and resulting annual PPh21.
  - Final current-payrun PPh21 after subtracting prior PPh21 and `taxPaid`.
  - Final `pph21Allowance`, `pph21Deduction`, `pph21Payment`, and `pph21Dtp`.

6. Explain calculation method effect on payslip/take-home pay.
- `Gross`: PPh21 appears as a deduction and reduces take-home pay.
- `Gross-up`: PPh21 allowance is added, and PPh21 deduction is subtracted; explain both sides because the net effect may be offset.
- `Taxable Netto`: PPh21 payment appears as a company-paid benefit, not a normal employee deduction.
- `Netto`: PPh21 deduction/allowance/payment are zero in the standard calculation path.
- `PPh21 DTP`: when eligible, DTP is shown as a net addition/payment relief; include `pph21Dtp` in the reconciliation.

## Useful Code Anchors

- Payrun participant summary shape: `apps/kraken/src/database/models/Payroll/PayrunParticipant.ts`.
- Payroll enums and pay item categories: `apps/kraken/src/database/models/Payroll/enums.ts`.
- PPh21 dispatcher and taxable-base logic: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21.ts`.
- TER calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21TERCalculator.ts`.
- Annualized calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21AnnualizedCalculator.ts`.
- Freelance calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21FreelanceCalculator.ts`.
- DTP calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/dtpCalculator.ts`.
- Payslip formatting: `apps/kraken/src/server/lib/payroll/payslip/formatPayslipData.ts`.
- Indonesia PPh21 payslip contributions: `apps/kraken/src/server/lib/payroll/payslip/idPphContributions.ts`.

## Output Format

Use this structure:

1. `Answer`: one paragraph saying whether the take-home pay reconciles.
2. `Inputs checked`: org, employee, month/year, payrun id/order, participant id, payroll scope/country.
3. `Take-home reconciliation`: table with component groups and signed amounts.
4. `Component explanation`: concise bullets for each material component.
5. `Indonesia PPh21 calculation`: include only for Indonesia payroll; show method, PTKP status, TER category/rate if TER, taxable gross basis, taxable employer/employee statutory, rate/source table, allowance/deduction/payment/DTP, and prior-payrun offsets. If annualized, include every variable listed in the annualized workflow.
6. `Variance or gaps`: expected vs actual difference, ambiguous matches, missing data, or unverified assumptions.
7. `Evidence`: local code/file references and query facts used.

## Starter Prompt

Use this when the user gives only default inputs:

`Use $employee-payroll-breakdown to explain <employee name>'s <month year> take-home pay of <amount> for <organisation name>, including payroll components and Indonesia PPh21 if applicable.`
