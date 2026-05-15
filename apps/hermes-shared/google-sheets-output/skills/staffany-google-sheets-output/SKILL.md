---
name: staffany-google-sheets-output
description: Use when a StaffAny Hermes bot needs to turn an already-approved bounded table result into a Google Sheets link using the team@staffany.com OAuth account.
version: 1.0.0
author: StaffAny
license: Internal
metadata:
  hermes:
    tags: [staffany, google-sheets, output, mcp]
    related_skills: [native-mcp]
---

# StaffAny Google Sheets Output

## When To Use

Use this skill only after the underlying data work is already approved or is clear same-thread continuation work. Examples:

- The user asks for a "spreadsheet", "Google Sheet", or "sheet summary" after a data answer.
- The user asks for a shareable table output from an already-confirmed query/result.

Do not use this skill to discover data, edit existing spreadsheets, read arbitrary Sheets, or replace the source system.

## Tool Contract

Use the `staffany_google_sheets` MCP server.

Allowed tools:

- `check_google_sheets_output_access`
- `create_spreadsheet_from_rows`

The MCP must use the `team@staffany.com` OAuth account through:

- `GOOGLE_SHEETS_TOKEN_FILE`
- `GOOGLE_SHEETS_CLIENT_SECRET_FILE`
- `GOOGLE_SHEETS_ACCOUNT_EMAIL`

Required OAuth scopes are:

- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/drive.file`

The tool must block if neither `GOOGLE_SHEETS_OUTPUT_FOLDER_ID` nor `GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS` is configured. A created Sheet that nobody can access is not a useful output.

## Safety Defaults

- Max 5 tabs.
- Max 5,000 rows per tab.
- Max 100,000 cells total.
- Max 2,000 characters per cell.
- Escape cells beginning with `=`, `+`, `-`, or `@`.
- Creation-only in v1. Do not edit existing spreadsheets.
- Never include raw Slack transcripts, raw query rows beyond the approved output table, employee-level payroll detail, phone numbers, NRIC/FIN, bank details, API keys, OAuth tokens, or connector secrets.

## Output Contract

Final bot answers should include:

```text
Answer: Google Sheet created: <url>
Source: <source tables/tools used for the underlying result> + staffany_google_sheets.create_spreadsheet_from_rows
Scope: <time range, filters, row count, tab count>
Confidence: <verified | needs-check | blocked>
Caveat: <only material limitation>
```

If `staffany_google_sheets` is unavailable or blocks, return `Confidence: blocked` with the exact connector issue. Do not suggest manual CSV import as the main path when the Sheets MCP is healthy.

