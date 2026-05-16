# Prospeo Runtime

Prospeo is an optional, cost-controlled paid-provider pilot beside Lusha for NurtureAny decision-maker discovery and selected email/mobile reveal. HubSpot remains the source of truth for accounts, ownership, existing contacts, and write-back approval.

## Credentials

Use `PROSPEO_API_KEY` from the live profile `.env` hydrated from Secret Manager. The adapter falls back to reading `HERMES_HOME/.env` because stdio MCP child processes may not inherit every profile secret as `os.environ`. Do not commit the key, paste it into Slack, or store it in packet files.

Recommend setting a low dashboard/API usage limit before enabling the connector in production.

## Local MCP Adapter

The stdio MCP adapter lives at `runtime/mcp/prospeo_nurtureany_server.py`.

It exposes only:

- `search_prospeo_decision_maker_candidates`
- `search_prospeo_candidates_by_linkedin_urls`
- `reveal_prospeo_contact_details`
- `get_prospeo_credit_usage`

It intentionally does not expose broad bulk list exports, company enrichment, dashboard-list sync, CRM push, or write-back tools.

The adapter sends an explicit `StaffAny-NurtureAny/1.0` User-Agent header so Prospeo API traffic is identifiable.

## Endpoint Use

`search_prospeo_decision_maker_candidates`:

- Calls `POST /search-person`.
- Requires NurtureAny scoped HubSpot company inputs with `company_id` and `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`; arbitrary company-name-only inputs are blocked before any Prospeo API call.
- Accepts up to 5 companies per call.
- Defaults to 5 candidates per company and caps at 5.
- Uses company domain when available, because Prospeo advises against company-name-only matching for enrichment accuracy.
- Searches default title targets matching Lusha: owner/founder/CEO/MD/director/GM coverage plus SG operating roles: HR manager, people manager, operations manager, finance manager, and payroll manager.
- Filters for verified email or mobile availability, but does not return email addresses or mobile numbers.
- Returns Prospeo `person_id`, public profile/title/company context, pagination, and `credit_report`.

`search_prospeo_candidates_by_linkedin_urls`:

- Uses `POST /bulk-enrich-person` with `linkedin_url` because Prospeo's `/search-person` filters do not expose a LinkedIn URL filter.
- Requires `scoped_company_ids` from prior NurtureAny HubSpot-scoped output, validates those IDs against HubSpot, and blocks before any Prospeo call if validation fails.
- Accepts up to 10 LinkedIn profile URLs per call and returns at most 1 candidate per URL.
- Accepts profile URLs under `/in/` only. It does not scrape or browser-automate LinkedIn.
- Sends `only_verified_email=false` and `enrich_mobile=false`, strips any email/mobile fields from the returned candidate shape, and returns inferred name, title, Prospeo person ID, LinkedIn URL, confidence band, decision-maker match, quality warnings, company context, and `credit_report`.
- Does not reveal email addresses or mobile numbers. Use `reveal_prospeo_contact_details` only after selected approval.

`reveal_prospeo_contact_details`:

- Calls `POST /bulk-enrich-person` with selected `person_id` values from prior search.
- Requires scoped HubSpot `company_ids` from the prior NurtureAny HubSpot-scoped search before any reveal call.
- Requires `approval_marker` from the Slack thread.
- Accepts up to 3 selected persons per call.
- Defaults to verified email reveal only.
- Reveals mobile only when `reveal_phones=true`.
- Returns selected contact details and a HubSpot preview seed. It does not mutate HubSpot.

`get_prospeo_credit_usage`:

- Calls `GET /account-information` when the usage cache allows it.
- Returns current plan, used credits, remaining credits, and quota renewal timing.

## Credit Reporting

Every Prospeo tool response must include:

```json
"credit_report": {
  "estimated_credits": "...",
  "actual_delta_credits": "... | unavailable",
  "reported_total_cost": "... | unavailable",
  "usage_before": "... | unavailable",
  "usage_after": "... | unavailable",
  "rate_limit_remaining": "... | unavailable",
  "caveat": "..."
}
```

Credit estimates:

- Search: 1 credit per `POST /search-person` request that returns at least one person, unless Prospeo returns `free=true` for deduplication.
- LinkedIn URL lookup: use Prospeo `total_cost` from `POST /bulk-enrich-person` when returned; otherwise report `unavailable`.
- Email reveal: about 1 credit per selected matched person.
- Mobile reveal: about 10 credits per selected matched person; email is included by Prospeo when mobile is requested, but NurtureAny still only returns email when `reveal_emails=true`.

Use `/account-information` before and after Prospeo calls when available. Cached usage is acceptable and `actual_delta_credits` should be `unavailable` when the delta cannot be proven. Never block the main search or reveal result just to fetch usage.

## Selected PII Policy

Selected contact PII is allowed in internal Slack threads after explicit reveal approval. This allowance is narrow:

- Search responses show candidate profile context only; they do not show email or mobile values.
- Reveals show email and/or mobile only for selected contacts.
- Mobile reveal requires `reveal_phones=true`.
- When `reveal_phones=true`, the final internal Slack answer may show the selected raw mobile number returned by Prospeo. Do not downgrade approved selected reveal output to a generic phone availability flag.
- Bulk email, phone, or contact exports remain out of scope.
- Never paste Prospeo API keys, raw connector credentials, or unselected contact data into Slack.

## HubSpot Preview

After selected reveal, pass `hubspot_preview_actions` into `plan_hubspot_writeback` for review. The preview should:

- create or update a contact candidate only after explicit HubSpot approval in a future write phase,
- set available persona/channel-confidence fields such as `nurtureany_persona`, `nurtureany_channel_fit`, `nurtureany_contact_confidence`, and `nurtureany_last_verified_at`,
- include the source note: `Prospeo candidate, revealed by approval on <date>.`,
- list exact proposed fields and selected contacts,
- keep `will_mutate_hubspot=false` in V1.

No actual HubSpot mutation is allowed in V1.

## Timeout And Failure Handling

Each Prospeo HTTP request has a 15s hard timeout.

Return `Confidence: blocked` for:

- missing `PROSPEO_API_KEY`,
- authentication failure,
- quota or rate limit failure,
- legal restriction,
- unsupported endpoint,
- timeout or network failure.

The response should still include `credit_report` with the best estimate and a caveat.
