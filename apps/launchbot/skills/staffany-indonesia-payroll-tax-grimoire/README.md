# StaffAny Indonesia Payroll Tax Grimoire

Reusable StaffAny Codex bundle for Indonesia payroll tax and reporting work.

## Included Skills

- `indonesia-payroll-tax-advisor`
- `indonesia-tax-knowledge-updater`
- `pph21-settings-explainer`
- `employee-payroll-breakdown` if available

## Package

From the Pantheon repo root:

```bash
bash apps/grimoire/catalog/product/staffany-indonesia-payroll-tax-grimoire/package-skill.sh
```

Outputs are written to `dist/` by default.

## Validate Extracted Bundle

```bash
python3 scripts/quick_validate.py /path/to/extracted/staffany-indonesia-payroll-tax-grimoire
```

## Notes

- Official tax facts must still be verified against DJP/JDIH/BPK for current filing use.
- Hipajak consultant answers are bundled in the knowledge bank as secondary guidance, not official regulation.
- Slack, Spreadsheets, web browsing, and Data Bot access are external tools/plugins and are not packaged inside this folder.
- Use Data Bot access for Metabase or warehouse-backed analysis; this catalogue entry intentionally does not bundle Metabase workflow skills.
- The package script strips `*.env`, `*.pem`, and `*.key` files from bundled skills. Do not distribute database credentials or service-account files through this grimoire.
