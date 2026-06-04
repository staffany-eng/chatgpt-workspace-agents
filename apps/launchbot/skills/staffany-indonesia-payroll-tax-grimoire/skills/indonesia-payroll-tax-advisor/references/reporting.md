# Indonesia Payroll Tax Reporting Notes

## Scope

Use this file for SPT Masa PPh 21/26, e-Bupot 21/26, bukti potong, employer reporting workflows, and questions about whether StaffAny supports Indonesia payroll-tax reporting.

For PPh21 calculation behavior, read `pph21.md`.

## Regulatory Concepts To Verify

- SPT Masa PPh 21/26 is the periodic reporting mechanism for PPh21/PPh26 withholding. Verify current channels, form changes, and filing periods through DJP guidance.
- e-Bupot 21/26 is the DJP electronic withholding slip and reporting channel for PPh21/PPh26. Verify applicability, mandatory scope, and submission flow through DJP or regulation text.
- Bukti potong is the withholding proof issued to the income recipient. Verify which proof type applies to the target taxpayer/income scenario.
- Reporting obligations may differ by taxpayer type, withholding party, tax period, transition period, and DJP platform availability.

## Seeded Official References

Check `regulations.yml` for source metadata. Seed entries include:

- `djp_spt_masa_pph21_26_guide_2024`: DJP guide for SPT Masa PPh Pasal 21/26 reporting.
- `djp_ebupot_21_26_ter_article_2024`: DJP official article explaining e-Bupot 21/26 and TER context.
- `per_2_pj_2024`: placeholder for the exact DJP regulation source for e-Bupot/SPT Masa PPh 21/26 details.

## StaffAny Behavior Map

Inspect Pantheon code directly when the user asks whether StaffAny supports a reporting capability. Search the repo before claiming support, especially for:

- Indonesia payroll tax reports.
- e-Bupot 21/26 exports or submissions.
- SPT Masa PPh 21/26 forms or files.
- Bukti potong generation.
- PPh21/PPh26 employee or employer identifiers needed for reporting.

If search only finds PPh21 calculation, payslip, or employee tax setup code, say reporting support is `Not proven in code` until product/reporting evidence is found.

## Hipajak Consultant Guidance Imported 2026-05-18

Source: `hipajak_consultant_tax_knowledge_bank_2026_05`, StaffAny user-provided workbook `Tax Knowledge Bank.xlsx`, sheet `Ask Hipajak`. Treat this as secondary consultant/vendor guidance, not official DJP regulation.

### e-Bupot / Coretax

- Customers may have monthly e-Bupot and annual/final e-Bupot flows, but one employee should only have one e-Bupot per month. The consultant phrased this as "Yearly (resign) or Monthly"; clarify exact BPMP/BP21/BPA1 scenario before implementation.
- Consultant guidance says Coretax import should use XML only. Keep XLSX/DJP converter support as a product/workflow question and verify against current DJP Coretax template guidance.
- If e-Bupot import values override gross/PPh while payslip values differ, the consultant asked whether this means revision e-Bupot. Treat mismatched payroll/reporting values as a correction/revision workflow, not a normal state.
- IDTKU/NITKU is business-location identification under Coretax.
- The `NPWP Pemotong` in BPMP comes from the customer's employer tax ID.
- Tax Withholding Date should be treated as the e-Bupot issuance date or transaction date, per consultant guidance. Confirm the exact rule for off-cycle, THR, correction, and backdated payroll before product copy.
- Coretax can generate/download 1721-A1 in its ecosystem, but many customers still expect the payroll system to generate A1.

### A1 / Employee Delivery

- A1 can be emailed to staff through Hipajak if employee emails are available, per consultant guidance.
- Many customers still expect payroll-system-generated A1 even when Coretax can produce it. Keep StaffAny BPA1/1721-A1 export scope separate from full SPT Masa filing scope.

### Reports And Reconciliation

- The consultant answered "No" to needing a PPh21 Karyawan Tetap report and BPJS-style report for customers to tally with consultants/government formats. Treat this as "not legally required as a DJP report" unless clarified; product/customer reconciliation may still need such reports.
- If a company asks for consultant-ready reports, separate official forms from operational reconciliation reports:
  - Official/core tax artifacts: SPT Masa PPh 21/26, BPMP, BP21, BP26, BPA1/BPA2, payment evidence, correction files.
  - Operational reconciliation: payroll report, taxable gross breakdown, BPJS/statutory breakdown, PTKP, TER/annualized method, previous PPh paid, and DTP.

## Suggested Code Search Terms

Use targeted searches such as:

```bash
rg -n "e-?Bupot|Bupot|SPT Masa|PPh 21/26|PPh21/26|PPh26|bukti potong|withholding slip" apps/kraken apps/gryphon apps/pixie
rg -n "pph21|PPh21|Indonesia.*tax|TER|PTKP|DTP" apps/kraken/src
```

## Answer Pattern For Reporting Questions

Use this structure:

1. `Direct answer`: whether the reporting workflow is required/supported/proven.
2. `Regulatory rule`: official reporting requirement or guidance, with source and effective period.
3. `StaffAny behavior`: proven feature, limitation, or `Not proven in code`.
4. `Operational implication`: what payroll/product/support teams should do next.
5. `Sources checked`: regulator URLs and local files/searches.

Avoid saying StaffAny "supports e-Bupot" unless there is direct product/code evidence for e-Bupot files, API submission, or an explicit reporting workflow.
