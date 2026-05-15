# Google Sheets Output Runtime

This runtime packet provides creation-only Google Sheets output for StaffAny Hermes bots.

## Contract

- Server name: `staffany_google_sheets`
- Account: `team@staffany.com`
- Access mode: OAuth token file. This is not a Google service account.
- Auth env vars:
  - `GOOGLE_SHEETS_TOKEN_FILE`
  - `GOOGLE_SHEETS_CLIENT_SECRET_FILE`
  - `GOOGLE_SHEETS_ACCOUNT_EMAIL`
  - `GOOGLE_SHEETS_OUTPUT_FOLDER_ID` or `GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS`
  - optional `GOOGLE_SHEETS_OUTPUT_SHARE_ROLE`
- Required OAuth scopes:
  - `https://www.googleapis.com/auth/spreadsheets`
  - `https://www.googleapis.com/auth/drive.file`

## Allowed Tools

- `check_google_sheets_output_access`
- `create_spreadsheet_from_rows`

## Runtime Rules

- Create new spreadsheets only. Do not expose generic edit-existing-Sheet tools in v1.
- Require either a configured output folder or configured share target before creating a spreadsheet.
- Escape formula-like cells before writing.
- Keep output bounded: 5 tabs, 5,000 rows per tab, 100,000 total cells, 2,000 characters per cell.
- Return the created spreadsheet URL, tab count, row count, and sharing/folder actions.
- Return `Confidence: blocked` when OAuth files, scopes, folder/share policy, or Google API access fails.
- Do not return token values, raw credential file content, or private error details.

