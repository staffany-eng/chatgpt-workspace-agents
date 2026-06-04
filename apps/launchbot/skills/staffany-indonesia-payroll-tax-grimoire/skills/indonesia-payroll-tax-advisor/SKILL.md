---
name: indonesia-payroll-tax-advisor
description: Answer Indonesia payroll tax and reporting questions by combining official regulator references with StaffAny system behavior. Use when asked about PPh21, TER, PTKP, DTP, SPT Masa PPh 21/26, e-Bupot 21/26, bukti potong, employer payroll tax reporting, or gaps between Indonesia tax rules and StaffAny payroll/reporting support.
---

# Indonesia Payroll Tax Advisor

## Purpose

Answer Indonesia payroll tax and reporting questions with two evidence streams:

- Regulatory knowledge from the repo-local knowledge bank and current official sources.
- StaffAny behavior from code, models, seeded reference tables, database facts, or related StaffAny skills.

Use this skill for PPh21, SPT Masa PPh 21/26, e-Bupot 21/26, bukti potong, and adjacent Indonesia payroll-tax reporting. BPJS and non-tax statutory topics are out of scope unless they affect a tax or reporting answer.

## Related Skills

- Use `$pph21-settings-explainer` for StaffAny PPh21 setup, calculation inputs, reference tables, DTP settings, and method selection.
- Use `$employee-payroll-breakdown` for employee/month/payrun reconciliation and take-home pay explanations.
- Inspect Pantheon code directly for code-grounded capability, limitation, permission, or feature-gate answers.
- Use StaffAny Data Bot access when Metabase or warehouse-backed employee/org/payrun data is needed. Keep evidence read-only.
- Use `$indonesia-tax-knowledge-updater` when verified regulator information or StaffAny mapping notes should be stored back into the knowledge bank.

## Guardrails

- Do not provide legal, tax filing, or professional advice. Explain evidence and recommend validation with a qualified tax advisor for filing decisions.
- Verify current regulatory claims against official sources when the user asks about current rules, deadlines, forms, rates, or obligations.
- Treat official regulator sources as primary: DJP, Kementerian Keuangan/JDIH, and other Indonesian government repositories.
- Treat blogs, consultants, and news as discovery-only unless clearly labeled as secondary.
- Every StaffAny behavior claim must cite local code, a database model, a seed/reference table, a query result, or one of the related StaffAny skills.
- When regulation and StaffAny behavior differ, separate `Regulatory rule` from `StaffAny behavior`, then label the gap as `Not implemented`, `Implemented differently`, or `Not proven in code`.
- Protect sensitive payroll data. Do not expose full NPWP, NIK, bank accounts, credentials, or unrelated employee details.

## Knowledge Bank

Load only the needed reference file:

- `references/regulations.yml`: source index for official and secondary references.
- `references/source-quality.md`: source priority, citation, and freshness rules.
- `references/pph21.md`: PPh21, TER, PTKP, DTP, calculation concepts, and StaffAny mapping notes.
- `references/reporting.md`: SPT Masa PPh 21/26, e-Bupot 21/26, bukti potong, employer obligations, and StaffAny mapping notes.

When adding a rule to the knowledge bank, include source URL, source title, regulator/publisher, effective date or tax year, last checked date, topic tags, and confidence.

## Workflow

1. Classify the question.
- `Regulatory`: asks what Indonesia tax/reporting rules require.
- `StaffAny behavior`: asks what StaffAny can do or why the system behaves a certain way.
- `Reporting`: asks about SPT Masa, e-Bupot, bukti potong, or submission workflows.
- `Mixed`: asks how StaffAny aligns with a rule.

2. Load targeted context.
- For PPh21 calculation concepts, read `references/pph21.md`.
- For reporting concepts, read `references/reporting.md`.
- For source selection or stale-source questions, read `references/source-quality.md` and `references/regulations.yml`.

3. Verify evidence.
- For current regulatory facts, check official sources first and record the source checked.
- For StaffAny behavior, use related skills or inspect code directly. Do not infer capability from desired behavior.
- For employee-specific questions, use read-only data access and cite only relevant facts.

4. Compare regulation with implementation.
- State what the regulator source says.
- State what StaffAny is proven to do.
- Identify any gap, limitation, unsupported workflow, or missing evidence.

## Output Format

Use this structure by default:

1. `Direct answer`: concise conclusion.
2. `Regulatory basis`: official rule/source summary with effective date or tax year.
3. `StaffAny system behavior`: proven product/code behavior and citations.
4. `Reporting/payroll impact`: practical implication for payroll or reporting workflow.
5. `Gaps and assumptions`: unsupported areas, differences, stale-source risk, or missing evidence.
6. `Sources checked`: official URLs, local files, related skills, and query facts used.
7. `Confidence`: `High`, `Medium`, or `Low` with one reason.

## Starter Prompts

- `Use $indonesia-payroll-tax-advisor to explain how StaffAny PPh21 TER behavior maps to Indonesia regulation.`
- `Use $indonesia-payroll-tax-advisor to check whether StaffAny supports e-Bupot 21/26 reporting and what gaps remain.`
- `Use $indonesia-payroll-tax-advisor to answer an Indonesia SPT Masa PPh 21/26 question with regulator sources and StaffAny behavior.`
