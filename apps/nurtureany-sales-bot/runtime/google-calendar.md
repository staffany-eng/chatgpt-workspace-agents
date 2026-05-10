# Google Calendar Runtime

NurtureAny may use the StaffAny `team@staffany.com` Google Calendar OAuth account as read-only event context. HubSpot remains the queue and account source of truth.

## Contract

- Server name: `google_calendar_nurtureany`
- Account: `team@staffany.com`
- Auth env vars:
  - `GOOGLE_CALENDAR_TOKEN_FILE`
  - `GOOGLE_CALENDAR_CLIENT_SECRET_FILE`
  - `GOOGLE_CALENDAR_ACCOUNT_EMAIL`
- Access mode: read-only OAuth token file. This is not a Google service account; `team@staffany.com` can read an AE calendar only when that calendar is shared to `team@staffany.com` or otherwise accessible to that OAuth user.
- Required OAuth scope: `https://www.googleapis.com/auth/calendar.readonly`
- Allowed tools:
  - `list_google_calendar_events`
  - `audit_google_calendar_meeting_quality`

## Enrichment Signals

Use Google Calendar only after the scoped HubSpot account set is known.

Useful signals:

- Sales or event follow-up timing.
- Upcoming invite or meeting context.
- Recent event attendance context when the event is represented in Calendar.
- Account-name or domain matches in calendar event summaries.
- AE-owned sales follow-up meetings from the HubSpot company owner's calendar when that calendar is shared to `team@staffany.com`.
- Account-level meeting-quality audit using HubSpot `calendar_audit_seed`, attendee email hashes/domains, and safe HubSpot contact match records.

Google Calendar does not replace Luma event evidence when Luma has RSVP or attendance data. Treat Calendar as scheduling context unless the event source explicitly records attendance.

## Query Rules

- Run only bounded event list calls.
- For account follow-up coverage, use the resolved HubSpot account owner first: resolve the scoped owner through HubSpot owners API and include that owner's email calendar ID, such as `jeremy.wong@staffany.com`, in `calendar_ids`. Use the `team@staffany.com` OAuth account to read that shared AE calendar.
- For meeting-quality audit, call `audit_google_calendar_meeting_quality` only after `get_account_context` returns `company.calendar_audit_seed`. The tool may read attendee emails internally, hashes them, matches them to HubSpot contact hashes, and returns safe summaries only.
- Default to the `team@staffany.com` primary calendar only when no account owner calendar is known.
- If the owner calendar is inaccessible, return `Confidence: blocked` for calendar coverage and state that the AE calendar is not accessible via `team@staffany.com`. Do not answer "no follow-up" from `team@staffany.com` primary alone.
- Cap reads at 5 calendars and 50 events per calendar.
- Do not create, update, delete, invite, RSVP, export attendees, or write calendar data.
- Do not return event descriptions, attendee emails, raw guest lists, conferencing links, or private calendar metadata by default.
- Do not expose raw attendee emails, descriptions, guest lists, conference links, phone numbers, or raw HubSpot bodies from meeting-quality audit output. Email hashes/domains are internal match evidence only.
- Treat title-only decision-maker inference as `needs-check`; verified decision-maker coverage must come from HubSpot `hs_buying_role=DECISION_MAKER` or HubSpot company decision-maker count.
- For past matched meetings, use the returned `hubspot_followup_check` hint to call HubSpot follow-up status from the event end time.
- Return `Confidence: needs-check` when matching events to HubSpot accounts by name/domain only.
- Return `Confidence: verified` only when the event has an account match plus a HubSpot-linked buying-relevant contact, ideally a verified decision maker.
- Return `Confidence: blocked` when OAuth files, scopes, auth refresh, or calendar access fails.
