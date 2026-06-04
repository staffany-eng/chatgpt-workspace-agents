---
name: staffany-indonesia-payroll-tax-grimoire
description: One-folder StaffAny Indonesia payroll tax bundle for PPh21, PPh26, TER, PTKP, DTP, SPT Masa PPh 21/26, e-Bupot/Coretax, bukti potong, 1721-A1/BPMP/BP21, StaffAny payroll tax settings, and knowledge-bank updates.
---

# StaffAny Indonesia Payroll Tax Grimoire

Use this as the single entry skill when StaffAny teammates install only one folder for Indonesia payroll tax work.

## Included Skills

Required:

- `skills/indonesia-payroll-tax-advisor`
- `skills/indonesia-tax-knowledge-updater`
- `skills/pph21-settings-explainer`

Optional, if present:

- `skills/employee-payroll-breakdown`

External plugins/tools that may still be needed and are not bundled here:

- Slack connector, for collecting or reading Slack threads.
- Spreadsheets plugin, for Excel outputs.
- Data Bot access, for Metabase or warehouse-backed analysis.
- Web browsing, for current official DJP/JDIH/BPK source verification.

## Standard Routing

1. For general Indonesia tax/reporting answers, start with `skills/indonesia-payroll-tax-advisor/SKILL.md`.
2. For StaffAny settings that affect PPh21, read `skills/pph21-settings-explainer/SKILL.md`.
3. For product capability or limitation claims, inspect the relevant Pantheon code directly and cite local files.
4. For one-employee pay/tax breakdowns, use `skills/employee-payroll-breakdown/SKILL.md` if bundled.
5. For Metabase or warehouse-backed checks, use StaffAny Data Bot access instead of a bundled Metabase workflow.
6. For Slack tax discussions, collect the relevant messages with the Slack connector, then cross-check against code/regulation.
7. For adding or refreshing reusable tax knowledge, use `skills/indonesia-tax-knowledge-updater/SKILL.md`.

## Tax Skill Audit Entry Point

Use this grimoire itself as the audit entry point for Indonesia payroll tax skill checks.

1. Read this `SKILL.md` first to set source priority, output format, and guardrails.
2. Load `skills/indonesia-payroll-tax-advisor/SKILL.md` for regulatory/reporting grounding.
3. Load `skills/pph21-settings-explainer/SKILL.md` for StaffAny PPh21 configuration and payroll-input behavior.
4. Load `skills/employee-payroll-breakdown/SKILL.md` only when the audit needs employee-level payroll reconstruction.
5. Use Data Bot for Metabase or warehouse-backed evidence; do not rely on a bundled Metabase workflow.
6. Finish with `Coverage`, `Validated`, `Not validated`, `Risk`, and `Recommended follow-up`.

## Answer Contract

For tax-related answers, separate:

- `Direct answer`
- `Regulatory basis`
- `StaffAny system behavior`
- `Gap / risk / not validated`
- `Sources checked`
- `Confidence`

Use official Indonesian terms first, then explain in English. Examples:

- `SPT Masa PPh 21/26`, not just "monthly tax report".
- `Bukti Potong / Bupot`, not "tax receipt".
- `Formulir 1721-A1 / BPA1`, not just "annual report".
- `BPMP / 1721-VIII`, `BP21`, `BP26`, `NITKU`, `PTKP`, `PKP`, `TER`, `PPh21 DTP`.

## Source Priority

1. Official regulation text from DJP, Kementerian Keuangan/JDIH, BPK, or other government repositories.
2. Official DJP guidance, help pages, templates, forms, or articles.
3. StaffAny repository evidence for actual product behavior.
4. Hipajak consultant guidance and other vendor/accounting sources as secondary guidance only.

Do not treat consultant/vendor answers as final authority for rates, forms, eligibility, filing obligations, or payment treatment unless official-source verification is unavailable and the answer labels that limitation.

## DTP Rule

For current/forward-looking 2026 DTP answers, use PMK 105/2025 as the main regulatory anchor, then compare with StaffAny DTP behavior and any Hipajak consultant notes.

## Knowledge Bank

The primary reusable references live inside:

- `skills/indonesia-payroll-tax-advisor/references/pph21.md`
- `skills/indonesia-payroll-tax-advisor/references/reporting.md`
- `skills/indonesia-payroll-tax-advisor/references/regulations.yml`
- `skills/indonesia-payroll-tax-advisor/references/source-quality.md`

When updating the knowledge bank, run:

```bash
ruby skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb
```

If working from the Pantheon repo instead of an extracted bundle, run:

```bash
ruby apps/grimoire/catalog/product/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb
```

## Guardrails

- This grimoire supports product/tax evidence synthesis, not professional filing advice.
- Browse official sources for current law, reporting forms, rates, filing processes, and Coretax/DJP template changes.
- Protect sensitive payroll data: do not expose full NPWP, NIK, bank account, or unrelated employee details.
- StaffAny capability claims must cite code, models, seeded references, or verified queries.
- Label mismatches clearly as `Regulatory rule`, `Consultant guidance`, `StaffAny behavior`, or `Not proven in code`.
