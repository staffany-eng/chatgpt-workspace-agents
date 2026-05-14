# Public Research Runtime

Public research is the reusable NurtureAny company-signal layer for game plans, enrichment review, SG lead-enrichment company/job-board discovery, and future nurture drafting.

HubSpot remains the source of truth for account scope, owner, status, current tools, contract dates, contacts, tasks, notes, and follow-up. Tavily output is review-only public evidence.

The `target-account-news-scout` skill uses this same public-research layer for recent news and brand signals. It must receive NurtureAny-scoped HubSpot company identity first, use safe company fields only, report cost, and return manual-review outreach drafts only.

## Credentials

Use `TAVILY_API_KEY` from the live profile `.env` or Secret Manager. Do not commit the key, paste it into Slack, or store it in packet files.

## Local MCP Adapter

The stdio MCP adapter lives at `runtime/mcp/public_research_nurtureany_server.py`.

It exposes only:

- `research_public_company_signals`
- `find_brand_parent_candidates`

The shared engine lives at `runtime/mcp/nurtureany_common/public_research.py` so HubSpot evidence review and pre-demo game plans can reuse the same URL policy, source classification, signal extraction, snippet caps, and cost reporting.

## Endpoint Use

`research_public_company_signals`:

- Calls Tavily `POST /search` and `POST /extract`.
- Does not call Tavily `POST /research` in V1.
- Requires NurtureAny scoped HubSpot company inputs with `company_id`, `name`, `domain`, `country`, and `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`.
- Blocks arbitrary company-name-only inputs before reading `TAVILY_API_KEY` or making a Tavily call.
- Sends only safe company identity fields to Tavily: `company_id`, `name`, `domain`, and `country`.
- Accepts up to 5 companies per call.
- Returns `company_signals`, `source_evidence`, `game_plan_inputs`, `manual_check_items`, `missing_evidence`, `cost_report`, `confidence`, `caveat`, and `will_mutate_hubspot=false`.
- May return `recommended_next_tool=search_exa_people_candidates` when public evidence lacks decision-maker hints.

`find_brand_parent_candidates`:

- Calls Tavily `POST /search` only.
- Is allowed only as an identity-resolution fallback after a brand/outlet name failed direct scoped HubSpot target-account lookup.
- Accepts `brand_name`, `country`, and caller email; it does not accept private HubSpot rows, contacts, notes, tasks, Slack transcripts, or PII.
- Returns possible parent/group names, source evidence, `suggested_hubspot_queries`, `cost_report`, and `will_mutate_hubspot=false`.
- Does not grant scope and does not produce outreach research. The agent must re-query scoped HubSpot target accounts with returned parent/group candidates before calling `research_public_company_signals` or `search_exa_people_candidates`.
- If no returned parent/group candidate resolves to a scoped HubSpot target account, the target-account news flow must stop with `Confidence: blocked`.
- Must run before Exa People Search when an F&B/Retail request names an outlet/brand that may differ from the legal entity Exa should search. The parent/group candidate is identity evidence only; it is not account truth until it resolves back to a scoped HubSpot company.
- Regression example: `Eat 3 Bowls` can resolve through parent/group evidence to `The Better Kompany Pte Ltd`, then to Jeff's scoped HubSpot target account `The Better Kompany Pte Ltd (Super Sushi)`.

Never send private HubSpot notes, task bodies, contact emails, phone numbers, Slack transcripts, raw CRM rows, or unscoped enrichment dumps to Tavily.

## Modes And Cost Reporting

Supported modes:

- `light`: about 3 Tavily credits per company.
- `standard`: about 5 Tavily credits per company.
- `deep`: about 6-8 Tavily credits per company.

Every response must include `cost_report`, including blocked responses.

Cost estimates use Tavily public credit rules for Search and Extract. Actual account billing totals are not fetched in V1; the adapter reports actual cost as unavailable after successful runs and zero when no Tavily call completed.

## Source Handling

Automatically fetchable public URLs:

- company websites,
- company careers pages,
- public job boards,
- news/general public web,
- review sites.

Manual-check only:

These are manual-check only sources:

- LinkedIn,
- Instagram,
- TikTok,
- Facebook,
- Google Maps and regular Google pages,
- other gated/social pages.

Manual-check sources must not be scraped, browser-automated, accessed with cookies, or bypassed. They can be returned as review tasks and source pointers only.

## Reuse Points

- `build_pre_demo_game_plans` keeps public research off by default. When `include_public_research=true`, it enriches only the Research / stalking signal section and adds the returned cost report.
- `review_public_enrichment_evidence` uses the shared public-research normalization and signal extraction helpers for user-provided snippets and safe public URLs.
- Exa remains the people-candidate discovery path. Public research can recommend Exa, but it does not reveal contact PII or replace HubSpot decision-maker coverage.
- For SG lead enrichment, Tavily public research should be the company/job-board step before Exa people candidates and before any Lusha/Prospeo paid-provider pilot.

## Failure Handling

Return `Confidence: blocked` for:

- missing `TAVILY_API_KEY`,
- unscoped company input,
- authentication failure,
- quota or rate limit failure,
- unsupported endpoint or parameter error,
- timeout or network failure.

The response should still include `cost_report`, `will_mutate_hubspot=false`, and a caveat that public evidence never overrides HubSpot.
