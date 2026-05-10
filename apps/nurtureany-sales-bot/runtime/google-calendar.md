# Google Calendar Runtime

NurtureAny may use the StaffAny `team@staffany.com` Google Calendar account as read-only event context. HubSpot remains the queue and account source of truth.

## Contract

- Server name: `google_calendar_nurtureany`
- Account: `team@staffany.com`
- Auth env vars:
  - `GOOGLE_CALENDAR_TOKEN_FILE`
  - `GOOGLE_CALENDAR_CLIENT_SECRET_FILE`
  - `GOOGLE_CALENDAR_ACCOUNT_EMAIL`
- Access mode: read-only OAuth token file
- Required OAuth scope: `https://www.googleapis.com/auth/calendar.readonly`
- Allowed tools:
  - `list_google_calendar_events`

## Enrichment Signals

Use Google Calendar only after the scoped HubSpot account set is known.

Useful signals:

- Sales or event follow-up timing.
- Upcoming invite or meeting context.
- Recent event attendance context when the event is represented in Calendar.
- Account-name or domain matches in calendar event summaries.

For generic "do we have a follow-up" questions, Calendar invite lookup is required alongside HubSpot task lookup after the scoped HubSpot account is known. Return Calendar as `calendar_invite_signal`, not as the source of the contact person.

Google Calendar does not replace Luma event evidence when Luma has RSVP or attendance data. Treat Calendar as scheduling context unless the event source explicitly records attendance.

Google Calendar must not choose the follow-up person. Do not infer contacts from guests, organizers, descriptions, conference links, or private calendar metadata. If the user asks who to follow up with after a calendar hit, return to scoped HubSpot contacts and existing sales follow-up tasks first; use Luma matched attendees only when the request is event-related.

## Query Rules

- Run only bounded event list calls.
- Default to the `team@staffany.com` primary calendar unless a configured calendar ID is supplied.
- Cap reads at 5 calendars and 50 events per calendar.
- Do not create, update, delete, invite, RSVP, export attendees, or write calendar data.
- Do not return event descriptions, attendee emails, raw guest lists, conferencing links, or private calendar metadata by default.
- Return `Confidence: needs-check` when matching events to HubSpot accounts by name/domain only.
- Return `Confidence: blocked` when OAuth files, scopes, auth refresh, or calendar access fails.
