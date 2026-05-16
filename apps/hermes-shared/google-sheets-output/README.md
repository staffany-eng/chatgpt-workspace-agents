# StaffAny Google Sheets Output

Shared Hermes packet for creating bounded Google Sheets output from bot-owned tabular results.

## Runtime Shape

- MCP server: `staffany_google_sheets`
- Skill: `staffany-google-sheets-output`
- Account: `team@staffany.com`
- Auth mode: OAuth token file, not a service account
- Tools:
  - `check_google_sheets_output_access`
  - `create_spreadsheet_from_rows`

This packet is shared runtime plumbing. Bot-specific source truth and answer contracts stay in each app packet.

