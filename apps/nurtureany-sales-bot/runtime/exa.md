# Exa Runtime

Exa is an optional people-discovery source for NurtureAny decision-maker lookup. It sits after Tavily/manual public company and job-board evidence, and before selected contact-data providers: Exa can find likely public people-profile candidates, while Lusha remains the approval-gated source for selected email or phone reveal and Prospeo remains a V1.1 pilot candidate only.

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
- Requires NurtureAny scoped HubSpot company inputs with `company_id` and `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`; arbitrary company-name-only inputs are blocked before any Exa API call.
- Sends `category: "people"`, `type: "auto"`, `numResults <= 5`, and `userLocation` mapped from company country (`SG`, `MY`, or `ID`).
- Accepts up to 5 companies per call.
- Defaults to 5 candidates per company and caps at 5.
- Default title targets are StaffAny ICP personas only: Owner, Founder, CEO, Chief Executive Officer, HR Manager, HR Director, Head of HR, People & Culture, People Operations, Chief People Officer, Operations Manager, Head of Operations, Director of Operations, Operations Director, COO, and Chief Operating Officer. Avoid generic `manager`, `director`, store/outlet manager, junior ops, finance-only, or payroll-only titles unless the user explicitly asks.
- Returns query, Exa request ID, candidate title, URL, source domain, source type, inferred name/title, decision-maker title match, `signal_count`, `confidence_band`, quality signals/warnings, and `cost_report`.
- The company domain is added as text in the query, not as a hard `includeDomains` filter. LinkedIn result URLs therefore still need public-search corroboration or a scoped-company mention before they can be shown as AE-ready contact rows.
- Does not send `contents`, `includeDomains`, `excludeDomains`, crawl-date filters, or LinkedIn-specific fetch parameters.
- Does not reveal email addresses or phone numbers.

Prefer scoped HubSpot company records that include both `name` and resolved `domain`. The resolved domain must come from HubSpot company `domain` first, falling back to `website` only when `domain` is empty, normalized by removing scheme, path, and `www.` prefix. Domain-pinned queries reduce same-name ambiguity. Scoped HubSpot records without a resolved domain are still allowed only when the tool result carries a missing-domain warning; candidates from those searches should be treated as weaker until public evidence or HubSpot confirms the entity.

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

All Exa candidates remain `Confidence: needs-check` until an AE verifies or selects the person for a Lusha or Prospeo reveal.

Candidate quality gate:

- `high`: at least two core signals align, from target-title match, company-domain result URL, or LinkedIn result URL, with no weak-store/junior-manager or former-employee warning.
- `medium`: at least two core signals align, but a material non-fatal warning remains, such as missing domain anchor.
- `low`: single-signal, missing-title, no LinkedIn/company-domain URL, missing-domain-anchor, store/outlet/junior manager, or possible former-employee candidates.

Do not hide low-confidence candidates, but label them clearly and do not present them as AE-ready handoff candidates.

## HubSpot, Lusha, And Prospeo Flow

Recommended flow:

1. Use HubSpot to identify accounts with missing decision-maker coverage.
2. For F&B/Retail outlet or brand names that do not clearly match the legal/group entity in scoped HubSpot, run `find_brand_parent_candidates`, then re-resolve the returned parent/group candidates back to scoped HubSpot before Exa. Do not run Exa on an unresolved outlet brand.
3. Pass only the scoped HubSpot company records returned by NurtureAny into Exa, preferably with `domain`.
4. Pass Exa candidate rows into `review_public_enrichment_evidence` for HubSpot contact dedupe before showing anything as a usable AE handoff candidate.
5. Ask the user to select one or more reviewed candidates.
6. Use Lusha or Prospeo targeted reveal only after explicit approval, scoped HubSpot company IDs, and cost estimate.
7. Use `plan_hubspot_writeback` only to prepare a preview.

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
