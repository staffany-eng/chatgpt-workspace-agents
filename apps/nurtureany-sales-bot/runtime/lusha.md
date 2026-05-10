# Lusha Runtime

Lusha is an optional, cost-controlled enrichment source for NurtureAny decision-maker discovery. HubSpot remains the source of truth for accounts, ownership, existing contacts, and write-back approval.

## Credentials

Use `LUSHA_API_KEY` from the live profile `.env` or Secret Manager. Do not commit the key, paste it into Slack, or store it in packet files.

Recommend setting a low monthly API key limit in the Lusha dashboard before enabling the connector.

## Local MCP Adapter

The stdio MCP adapter lives at `runtime/mcp/lusha_nurtureany_server.py`.

It exposes only:

- `search_lusha_decision_maker_candidates`
- `reveal_lusha_contact_details`
- `get_lusha_credit_usage`

It intentionally does not expose bulk export, broad enrichment, company enrichment, or write-back tools.

The adapter sends an explicit `StaffAny-NurtureAny/1.0` User-Agent header so Lusha API traffic is not blocked as a generic Python client.

## Endpoint Use

`search_lusha_decision_maker_candidates`:

- Calls `POST /prospecting/contact/search`.
- Requires NurtureAny scoped HubSpot company inputs with `company_id` and `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`; arbitrary company-name-only inputs are blocked before any Lusha API call.
- Accepts up to 5 companies per call.
- Defaults to 5 candidates per company and caps at 5.
- Returns name, title, company match, `requestId`, `contactId`, LinkedIn/social presence, and email/phone availability flags.
- Does not reveal email addresses or phone numbers.

`reveal_lusha_contact_details`:

- Calls `POST /prospecting/contact/enrich`.
- Requires scoped HubSpot `company_ids` from the prior NurtureAny HubSpot-scoped search before any reveal call.
- Requires `approval_marker` from the Slack thread.
- Accepts up to 3 selected contacts per call.
- Always sends explicit `revealEmails` and `revealPhones` flags.
- Defaults to email reveal only.
- Reveals phones only when `reveal_phones=true`.
- Returns selected contact details and a HubSpot preview seed. It does not mutate HubSpot.

`get_lusha_credit_usage`:

- Calls `GET /account/usage` when the usage cache and 5/minute limit allow it.
- Returns summarized used, remaining, and total credits across returned categories.

## Credit Reporting

Every Lusha tool response must include:

```json
"credit_report": {
  "estimated_credits": "...",
  "actual_delta_credits": "... | unavailable",
  "usage_before": "... | unavailable",
  "usage_after": "... | unavailable",
  "rate_limit_remaining": "... | unavailable",
  "caveat": "..."
}
```

Credit estimates:

- Search: `ceil(returned_results / 25)`, minimum 1 credit per API search.
- Email reveal: `+1 credit/contact`.
- Phone reveal: `+5 credits/contact`.
- Company full-data enrichment, if added later: `+1 credit/company`.

Use `/account/usage` before and after Lusha calls when available. The usage endpoint is limited to 5 requests/minute, so cached usage is acceptable and `actual_delta_credits` should be `unavailable` when the delta cannot be proven. Never block the main search or reveal result just to fetch usage.

Capture rate-limit headers such as daily, hourly, or minute remaining quota when present. If headers are absent, return `rate_limit_remaining: {"status": "unavailable"}`.

## Selected PII Policy

Selected contact PII is allowed in internal Slack threads after explicit reveal approval. This allowance is narrow:

- Search responses show availability flags only.
- Reveals show email and/or phone only for selected contacts.
- Phone reveal requires `reveal_phones=true`.
- Bulk email, phone, or contact exports remain out of scope.
- Never paste Lusha API keys, raw connector credentials, or unselected contact data into Slack.

## HubSpot Preview

After selected reveal, pass `hubspot_preview_actions` into `plan_hubspot_writeback` for review. The preview should:

- create or update a contact candidate only after explicit HubSpot approval in a future write phase,
- set available persona/channel-confidence fields such as `nurtureany_persona`, `nurtureany_channel_fit`, `nurtureany_contact_confidence`, and `nurtureany_last_verified_at`,
- include the source note: `Lusha candidate, revealed by approval on <date>.`,
- list exact proposed fields and selected contacts,
- keep `will_mutate_hubspot=false` in V1.

No actual HubSpot mutation is allowed in V1.

## Timeout And Failure Handling

Each Lusha HTTP request has a 15s hard timeout.

Return `Confidence: blocked` for:

- missing `LUSHA_API_KEY`,
- authentication failure,
- quota or rate limit failure,
- legal restriction,
- unsupported endpoint,
- timeout or network failure.

The response should still include `credit_report` with the best estimate and a caveat.
