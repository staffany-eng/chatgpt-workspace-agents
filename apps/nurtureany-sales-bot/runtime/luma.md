# Luma Runtime

Luma is an optional read-only event-context source for NurtureAny. HubSpot remains the queue, ownership, contact, and account source of truth.

## Contract

- Base URL: `https://public-api.luma.com`
- Auth env var: `LUMA_API_KEY`
- Auth header: `x-luma-api-key`
- Access mode: read-only for V1
- 15s hard timeout
- Calendar event endpoint: `GET /v1/calendar/list-events`
- Calendar event tags endpoint: `GET /v1/calendar/event-tags/list`
- Event detail endpoint: `GET /v1/event/get`
- Guest list endpoint: `GET /v1/event/get-guests`
- Optional guest detail endpoint: `GET /v1/event/get-guest`
- Useful tools:
  - `list_luma_events`
  - `get_luma_event_match_keys`
  - `get_luma_event_context`

The local stdio MCP adapter lives at `runtime/mcp/luma_nurtureany_server.py`.

## Tool Behavior

`list_luma_events`:

- Input: Slack user email, optional query, optional start/end, optional max events, optional `event_tags`, optional location, optional country, and optional event type.
- Output: safe event id, name, date/time, timezone, URL, Luma tags, normalized location tags, normalized country tags, normalized event type tags, and tag match source only.
- Caps events at 50, defaults to 20, and returns `has_more` plus `truncated`.
- Uses exact Luma event tags first when `event_tags` is supplied. If Luma omits tags from `list-events`, the adapter fetches event detail; if tags are still unavailable, it falls back to event name/timezone metadata with `Confidence: needs-check`.

`get_luma_event_context`:

- Input: Slack user email, HubSpot-scoped companies, optional event IDs or event search window, optional `event_tags`, optional location, optional country, optional event type, and optional guest cap.
- Requires scoped HubSpot company inputs with `company_id` plus `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`.
- Refuses arbitrary company-name-only lookup before calling Luma.
- Caps event context at 20 events and guest reads at 250 guests per event.
- Filters event search by Luma country/type tags before guest lookup when those filters are supplied.
- Matches guests to scoped accounts by exact HubSpot contact email, exact company email domain, then company-name candidate match from Luma fields or registration answers.
- Returns attendee names only for matched scoped accounts, plus email domain/hash, RSVP status, checked-in timestamp, match reason, matched account IDs, RSVP counts, checked-in count, `has_more`, and `truncated`.

`get_luma_event_match_keys`:

- Input: Slack user email and either selected event IDs or bounded event search filters.
- Output: safe company email domains and company-name candidates for HubSpot target-account lookup.
- Does not return raw attendee names, full emails, phone numbers, registration answers, or raw guest lists.
- Use it for broad event-first matching before calling `get_luma_event_context` with scoped HubSpot candidate companies.

Attendance means `checked_in_at` is present. Approved, invited, pending, waitlist, declined, and other RSVP states are not attendance.

## Event Tags

Use Luma event tags to narrow event lookup before scanning guests:

- Luma event tags are flat labels such as `Singapore`, `Jakarta`, `Bali`, `HR Happy Hour`, and `Sports`.
- Prefer passing the exact tags through `event_tags`, for example `event_tags=["Singapore", "Sports"]` or `event_tags=["Jakarta", "HR Happy Hour"]`.
- Supported event type labels are `Sports`, `Appreciation Afternoon`, `HR Happy Hour`, and `Leaders Lounge`.
- City/country labels include `Singapore`, `Jakarta`, `Bali`, and `Kuala Lumpur`; `Jakarta` and `Bali` map to `Indonesia`, and `Kuala Lumpur` maps to `Malaysia` for HubSpot account scope.
- For `last Jakarta HHH`, pass `event_tags=["Jakarta", "HR Happy Hour"]`; use `country="Indonesia"` for HubSpot account scope and only as a broad Luma fallback.
- If a caller mistakenly sends a location tag through `event_type` or `country`, the adapter normalizes it back to `location` so `Jakarta` does not broaden to all Indonesia events.
- For prompts like `StaffAny Appreciation Afternoon (JKT)`, pass `event_tags=["Jakarta", "Appreciation Afternoon"]` instead of broad date-only scans.

## Usage

Use Luma only when an account's nurture reason is event-related:

- Event invite chase.
- RSVP pending or approved.
- Attended event follow-up.
- No-show follow-up.
- Drive/Slack photo event-context tagging by date match.
- Luma-only attendee matching back to HubSpot.
- Post-event follow-up queue for HubSpot-scoped target accounts.
- Event-account matching before HubSpot follow-up-status checks.
- Manager rollups by event, AE scope, or country after HubSpot scope is known.
- `check_event_followup_status` is the preferred NurtureAny workflow for event follow-up because it resolves Luma checked-in attendance and verifies event-specific Eazybe WhatsApp logs in HubSpot without using Sheets as tracking state.

## Safety

- Do not expose raw attendee exports in Slack.
- Do not return unmatched guest names, emails, phone numbers, registration answers, or raw guest lists.
- Do not create, update, invite, RSVP, check in, or mutate Luma records from NurtureAny V1.
- Do not write Google Sheets from NurtureAny V1.
- Do not mutate HubSpot from Luma output in V1.
- Luma photo date matching may auto-tag event context only. It must not auto-link a person appearance to a HubSpot contact without uploader/human confirmation.
- Do not treat Luma attendance as HubSpot target-account membership.
- Do not treat Luma attendance as follow-up evidence; use HubSpot WhatsApp communications, notes, and tasks for follow-up status.
- Use HubSpot account scope first, then add Luma event context.
- Return `Confidence: needs-check` when guest matching is candidate-only or truncated.
- Return `Confidence: blocked` when auth, schema, rate limit, or Luma API access fails.
