# PPh21 Knowledge Notes

## Scope

Use this file for PPh21 calculation and withholding questions: TER, PTKP, DTP, PPh21 methods, tax categories, and how StaffAny maps these concepts into payroll.

For reporting, SPT Masa PPh 21/26, e-Bupot 21/26, and bukti potong, read `reporting.md` instead.

## Regulatory Concepts To Verify

- PPh21 is employee income tax withholding for qualifying income paid by the employer or withholding party.
- PPh26 applies to certain income paid to non-resident taxpayers and should not be assumed to follow PPh21 behavior without regulator evidence.
- TER is the monthly average effective rate approach introduced for PPh21 withholding from 2024. Verify exact rates, categories, and period through official PP/PMK/PER text before quoting.
- PTKP affects the tax status/category used by PPh21 calculations. Verify current PTKP amounts against official regulation for the target tax year.
- DTP means tax borne by government. Treat DTP as regulation-specific and time-bounded; for 2026 DTP questions, use PMK 105/2025 as the main reference and verify eligibility criteria against the official JDIH/BPK text before quoting thresholds or requirements.

## StaffAny Behavior Map

Use `$pph21-settings-explainer` for detailed StaffAny setting impact. Key anchors from that skill:

- Employee tax detail model: `apps/kraken/src/database/models/PPh21/IndonesiaEmployeeTaxDetail.ts`.
- PPh21 identification model: `apps/kraken/src/database/models/PPh21/IndonesiaIdentificationInformation.ts`.
- PPh21 method selection and taxable buckets: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21.ts`.
- TER calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21TERCalculator.ts`.
- Annualized calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21AnnualizedCalculator.ts`.
- Freelance calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/pph21FreelanceCalculator.ts`.
- DTP calculator: `apps/kraken/src/server/lib/payroll/statutory/pph21/dtpCalculator.ts`.

## StaffAny Calculation Concepts

- `employmentStatus` helps select the calculation path: freelance, non-permanent TER, or permanent/contract TER/annualized behavior.
- `calculationMethod` controls who bears PPh21 and how it appears: Gross, Gross-up, Taxable Netto, or Netto.
- `ptkpStatus` maps to TER category and annual non-taxable income behavior.
- `beginningNetto` and `taxPaid` affect annualized calculations.
- Taxable pay item categories and Indonesia tax category determine whether items feed the PPh21 base.
- Payrun year, month, order, and business entity scope affect prior-payrun offsets.
- Organisation DTP settings and active DTP regulation affect StaffAny DTP eligibility and amount.

## Hipajak Consultant Guidance Imported 2026-05-18

Source: `hipajak_consultant_tax_knowledge_bank_2026_05`, StaffAny user-provided workbook `Tax Knowledge Bank.xlsx`, sheet `Ask Hipajak`. Treat this as secondary consultant/vendor guidance, not official DJP regulation.

### Employee Tax Setup And Identity

- PTKP should follow an effective-date approach, typically effective from 1 January of the relevant tax year. This is consultant guidance; StaffAny currently stores employee tax detail by `taxYear`, so distinguish regulatory/product ideal from current product behavior.
- `beginningNetto` and previous PPh21 paid should be cumulative and tracked per tax year.
- NPWP can be blank for calculation/reporting if a valid NIK is registered and validated in Coretax. The consultant also says the 120% no-NPWP multiplier is no longer applicable under Coretax/NIK usage. Verify against official DJP/Coretax sources before customer-facing claims.
- For foreign individuals, the consultant simplified the treatment as KITAS without NPWP -> PPh26, KITAS plus NPWP -> PPh21. This needs official validation because residency, NPWP/NIK, treaty, and income-recipient facts can be more nuanced than that shorthand.
- If PTKP or tax method changes mid-year, the consultant says the effective status depends on 1 January. Use this as support for cautioning against silent mid-year tax-year changes.

### PPh21 Calculation Notes

- Monthly PPh21 uses TER, while annual/final reconciliation uses annualized Pasal 17 calculation.
- Gross, Gross-up, Taxable Netto, and Netto handling can depend on client payroll policy and reporting expectations. Do not assume all customers use "netto" consistently with StaffAny terminology.
- For multiple payruns, the consultant did not answer whether later PPh21 should equal cumulative tax minus prior PPh21 and requested more context. Keep this as unresolved.
- PPh21 allowance/deduction values should be rounded, but the consultant answer did not specify the exact rounding stage or precision. Verify official examples and StaffAny reference tables before quoting a rule.
- Freelancer tax treatment depends on the freelancer agreement. Do not reduce all freelancer cases to a single 2.5% flat rule without checking the agreement and official rule.
- One employee should not appear in both TER and annualized/e-Bupot files in the same month, per consultant guidance. If StaffAny produces mixed-method participants because of multiple payruns or resignation timing, escalate as a reporting design question.
- Mixed tax-bearing methods for one employee can be valid in principle: the consultant answered that basic salary can be gross-up while commission/meal/transport are gross. StaffAny currently uses employee-level `calculationMethod`, so this remains a product gap if customers need per-pay-item tax method.
- Switching from Gross-up in January to Netto from February needs clarification on the customer's definitions of Gross-up and Netto; do not answer purely from labels.
- A customer should not set employees to No Tax first and later switch to Gross/PPh as a one-year catch-up strategy because taxes are reported monthly. If a customer starts late, use import/correction guidance instead.
- If StaffAny differs from Coretax or a tax calculator, consultant guidance says StaffAny should align to Coretax to avoid PPh21 errors. Operationally, reconcile inputs first: taxable gross, PTKP, beginning netto, previous tax paid, statutory items, DTP, THR, and reporting period.

### DTP Consultant Notes

- For DTP eligibility, the consultant answered "taxable gross" for monthly wage/income basis and warned that incorrect gross-income calculation can cancel DTP. Verify against PMK 105/2025 and any official examples before turning this into product copy.
- The consultant framed DTP configuration as looking at the business type. This is regulatory eligibility guidance, not necessarily a StaffAny configuration model; StaffAny has org-level DTP settings and selected pay items.
- Coretax requires explicit facility tagging for DTP in e-Bupot/Coretax payloads.
- DTP representation can depend on whether the company uses gross or nett salary. The consultant says for Gross, no transfer back to employee is needed; for Nett, DTP incentive needs to be transferred/paid to employee. This may conflict with prior PMK-based interpretation that DTP is paid in cash to eligible employees; verify before final customer advice.
- DTP can still apply for Netto or Gross-up employees if the employee meets DTP eligibility requirements, especially the income threshold.
- When a daily worker is promoted to permanent/contract, DTP eligibility should use the promotion/join month, per consultant guidance.
- Avoiding double-paid DTP when December DTP is paid manually in January depends on records. Keep period attribution explicit.
- If DTP is turned off and later turned back on, the consultant says no problem. StaffAny/product caveat: missed months may still need correction/import/backfill if DTP should have been reported for those months.
- For one customer with two cutoff dates, the consultant says to still view payroll records for the month. This does not resolve StaffAny's org-level cutoff limitation; verify with official/reporting requirements and product design.

## Answer Pattern For PPh21 Questions

Use this comparison shape:

| Topic | Regulatory rule | StaffAny behavior | Gap |
| --- | --- | --- | --- |
| TER category/rate | Cite official source and effective period | Cite StaffAny rate table/model/calculator | Not implemented / Implemented differently / Not proven in code |
| Tax base | Cite official source if asked legally | Cite pay item categories and calculator code | Same labels |
| DTP | Cite active regulation | Cite DTP org setting and calculator | Same labels |

Do not quote rates or thresholds from memory. If rates are needed, verify current official source and StaffAny seeded reference table for the target tax year.
