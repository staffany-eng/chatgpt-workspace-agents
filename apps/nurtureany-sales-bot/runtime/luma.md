# Luma Runtime

Luma is an optional read-only event-context source for NurtureAny. HubSpot remains the queue, ownership, contact, and account source of truth.

## Contract

- Base URL: `https://public-api.luma.com`
- Auth env var: `LUMA_API_KEY`
- Auth header: `x-luma-api-key`
- Access mode: read-only for V1
- 15s hard timeout
- Calendar event endpoint: `GET /v1/calendar/list-events`
- Guest list endpoint: `GET /v1/event/get-guests`
- Optional guest detail endpoint: `GET /v1/event/get-guest`
- Useful tools:
  - `list_luma_events`
  - `get_luma_event_context`

The local stdio MCP adapter lives at `runtime/mcp/luma_nurtureany_server.py`.

## Tool Behavior

`list_luma_events`:

- Input: Slack user email, optional query, optional start/end, optional max events.
- Output: safe event id, name, date/time, timezone, and URL only.
- Caps events at 50, defaults to 20, and returns `has_more` plus `truncated`.

`get_luma_event_context`:

- Input: Slack user email, HubSpot-scoped companies, optional event IDs or event search window, and optional guest cap.
- Requires scoped HubSpot company inputs with `company_id` plus `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`.
- Refuses arbitrary company-name-only lookup before calling Luma.
- Caps event context at 20 events and guest reads at 250 guests per event.
- Matches guests to scoped accounts by exact HubSpot contact email, exact company email domain, then company-name candidate match from Luma fields or registration answers.
- Returns attendee names only for matched scoped accounts, plus email domain/hash, RSVP status, checked-in timestamp, match reason, matched account IDs, RSVP counts, checked-in count, `has_more`, and `truncated`.

Attendance means `checked_in_at` is present. Approved, invited, pending, waitlist, declined, and other RSVP states are not attendance.

## Usage

Use Luma only when an account's nurture reason is event-related:

- Event invite chase.
- RSVP pending or approved.
- Attended event follow-up.
- No-show follow-up.
- Luma-only attendee matching back to HubSpot.
- Post-event follow-up queue for HubSpot-scoped target accounts.
- Manager rollups by event, AE scope, or country after HubSpot scope is known.

## Safety

- Do not expose raw attendee exports in Slack.
- Do not return unmatched guest names, emails, phone numbers, registration answers, or raw guest lists.
- Do not create, update, invite, RSVP, check in, or mutate Luma records from NurtureAny V1.
- Do not write Google Sheets from NurtureAny V1.
- Do not mutate HubSpot from Luma output in V1.
- Do not treat Luma attendance as HubSpot target-account membership.
- Use HubSpot account scope first, then add Luma event context.
- Return `Confidence: needs-check` when guest matching is candidate-only or truncated.
- Return `Confidence: blocked` when auth, schema, rate limit, or Luma API access fails.
