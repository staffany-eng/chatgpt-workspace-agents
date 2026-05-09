# Luma Runtime

Luma is an optional read-only event-context source for NurtureAny.

## Contract

- Auth env var: `LUMA_API_KEY`
- Access mode: read-only for V1
- Useful tools:
  - `list_luma_events`
  - `get_luma_event_context`

## Usage

Use Luma only when an account's nurture reason is event-related:

- Event invite chase.
- RSVP pending or approved.
- Attended event follow-up.
- No-show follow-up.
- Luma-only attendee matching back to HubSpot.

The existing Luma events platform can list managed events, read guests, match attendees to HubSpot, and produce dry-run previews before writes. NurtureAny should reuse that review-first pattern.

## Safety

- Do not expose raw attendee exports in Slack.
- Do not write Google Sheets from NurtureAny V1.
- Do not treat Luma attendance as HubSpot target-account membership.
- Use HubSpot account scope first, then add event context.

