# Google Sheets Runtime

NurtureAny may use the StaffAny `team@staffany.com` Google Sheets OAuth account to write sanitized, table-shaped analysis output into one shared workbook. This is separate from the Google Drive read-only adapter.

## Contract

- Server name: `google_sheets_nurtureany`
- Account: `team@staffany.com`
- Auth env vars:
  - `GOOGLE_SHEETS_TOKEN_FILE`
  - `GOOGLE_SHEETS_CLIENT_SECRET_FILE`
  - `GOOGLE_SHEETS_ACCOUNT_EMAIL`
  - `NURTUREANY_ANALYSIS_OUTPUT_SPREADSHEET_ID`
- Required OAuth scope: `https://www.googleapis.com/auth/spreadsheets`
- Output model: one shared workbook, `Runs` index tab, and one run tab per analysis `idempotency_key`.
- Allowed tools:
  - `preview_analysis_sheet_export`
  - `apply_analysis_sheet_export`

## Query Rules

- Use Sheets export for table-shaped team analyses where Slack-only output is hard to consume.
- The Slack preflight must say sanitized rows will be previewed for the shared workbook. The same `run` approval covers row preparation and preview only; `apply_analysis_sheet_export` requires explicit Sheet approval in the same thread.
- Always call `preview_analysis_sheet_export` before `apply_analysis_sheet_export` when the output shape is not already deterministic.
- Use stable `idempotency_key` values from the Slack channel/thread/run or selected source so reruns update the same tab and `Runs` row.
- Write only Slack-safe / CRM-safe fields. Do not write raw Slack transcripts, phone numbers, full attendee emails, raw HubSpot bodies, raw guest exports, secrets, or raw Luma registration answers.
- For Luma/event analyses, use safe fields such as account name, HubSpot company link, HubSpot contact link for exact scoped matches, country, owner name, account status, RSVP status, match level, match confidence, root cause, next action, action owner, and source permalink.
- Event match action queues use one tab named `Event Match Action Queue`. The Slack summary should show RSVP truth, attendee-level match truth, action buckets, owner load, preview status, source, scope, confidence, and caveat. Include a Sheet link only after the approved apply step succeeds.
