# Exa Runtime

Exa is an optional people-discovery source for NurtureAny decision-maker lookup. It sits between manual/free public evidence and Lusha reveal: Exa can find likely public people-profile candidates, while Lusha remains the approval-gated source for selected email or phone reveal.

HubSpot remains the source of truth for accounts, ownership, existing contacts, and write-back approval.

## Credentials

Use `EXA_API_KEY` from the live profile `.env` or Secret Manager. Do not commit the key, paste it into Slack, or store it in packet files.

## Local MCP Adapter

The stdio MCP adapter lives at `runtime/mcp/exa_nurtureany_server.py`.

It exposes only:

- `search_exa_people_candidates`

It intentionally does not expose contents retrieval, LinkedIn scraping, broad crawling, contact reveal, company enrichment, bulk export, or write-back tools.

The adapter sends an explicit `StaffAny-NurtureAny/1.0` User-Agent header so Exa API traffic is identifiable.

## Endpoint Use

`search_exa_people_candidates`:

- Calls `POST /search`.
- Sends `category: "people"`, `type: "auto"`, `numResults <= 5`, and `userLocation` mapped from company country (`SG`, `MY`, or `ID`).
- Accepts up to 5 companies per call.
- Defaults to 5 candidates per company and caps at 5.
- Returns query, Exa request ID, candidate title, URL, source domain, source type, inferred name/title, decision-maker title match, and `cost_report`.
- Does not send `contents`, `includeDomains`, `excludeDomains`, crawl-date filters, or LinkedIn-specific fetch parameters.
- Does not reveal email addresses or phone numbers.

## Cost Reporting

Every Exa tool response must include:

```json
"cost_report": {
  "estimated_cost_usd": "...",
  "actual_cost_usd": "... | unavailable",
  "cost_dollars": "...",
  "caveat": "..."
}
```

Before running Exa from Slack, the bot must show the estimated scope and dollar-cost caveat: one Exa `/search` request per selected company, using current Exa dashboard pricing. After execution, the bot must include the actual `cost_report` from Exa `costDollars`.

Do not use the Exa Admin API or service keys in V1; per-response `costDollars` is the only billing evidence used by the bot.

## LinkedIn-Safe Handling

Exa People Search may return LinkedIn URLs as public result URLs. These URLs are allowed as manual-check source evidence, but the bot must not crawl, scrape, browser-automate, use cookies, or bypass LinkedIn or other gated/social access controls.

Source types:

- `linkedin_manual_check`: a LinkedIn result URL; manual-check evidence only.
- `social_or_gated_manual_check`: social or gated-looking result URL; manual-check evidence only.
- `company_public_profile`: a result from the supplied company domain.
- `public_people_result`: another public people-result URL.

All Exa candidates remain `Confidence: needs-check` until an AE verifies or selects the person for a Lusha reveal.

## HubSpot And Lusha Flow

Recommended flow:

1. Use HubSpot to identify accounts with missing decision-maker coverage.
2. Use Exa to discover likely public people candidates for selected accounts.
3. Ask the user to select one or more candidates.
4. Use Lusha targeted reveal only after explicit approval and cost estimate.
5. Use `plan_hubspot_writeback` only to prepare a preview.

No Exa output mutates HubSpot directly.

## Timeout And Failure Handling

Each Exa HTTP request has a 15s hard timeout.

Return `Confidence: blocked` for:

- missing `EXA_API_KEY`,
- authentication failure,
- quota or rate limit failure,
- legal restriction,
- unsupported endpoint or unsupported Exa parameter error,
- timeout or network failure.

The response should still include `cost_report` with the best available cost evidence and a caveat.
