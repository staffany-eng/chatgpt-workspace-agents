# Google Calendar Runtime

PSM Ops Bot uses Google Calendar only as read-only scheduling context.

## Contract

- Account: `team@staffany.com`
- OAuth token env var: `GOOGLE_CALENDAR_TOKEN_FILE`
- OAuth client secret env var: `GOOGLE_CALENDAR_CLIENT_SECRET_FILE`
- Required scope: `https://www.googleapis.com/auth/calendar.readonly`
- Access mode: team OAuth against shared calendars
- Max calendars per request: 5
- Max events per calendar: 50

## Tool Rules

- `read_customer_calendar_context`: gated safe read for customer follow-up checks and meeting-slot suggestions.
- `intent="find_existing_followup"` requires a specific customer query plus bounded `start`/`end`.
- `intent="suggest_meeting_slots"` requires a specific customer query, bounded `start`/`end`, explicit attendee emails, and duration.
- The tool rejects blank or weak customer queries such as `Jo` before calling Google.
- Do not create, update, delete, RSVP, invite, export attendees, or return raw guest lists.
- Do not return descriptions, attendee emails, conference links, phone numbers, or raw private calendar metadata.
- If a selected calendar is inaccessible to `team@staffany.com`, return `Confidence: blocked` and do not conclude that no meeting, follow-up, or available slot exists.

## Usage Pattern

For customer project threads, create/find the Jira PCO intake ticket first when the request includes task or ticket work. Then call `read_customer_calendar_context` only when the user explicitly asks for scheduling, follow-up meeting checks, invites, or meeting-slot suggestions.

Calendar is scheduling context only. Jira PCO remains source of truth for tasks and Customer 360 remains source of truth for customer context.
