# HubSpot Runtime

HubSpot is the source of truth for NurtureAny target-account queues.

## Required Capabilities

Read phase:

- Read owners and map owner email to owner ID.
- Search companies by target-account flag, owner, and country.
- Read company, contact, deal, association, activity, task, and note context.
- Read property metadata for field validation and option values.

Write phase:

- Create HubSpot tasks only after preview approval.
- Append HubSpot notes only after preview approval.
- Update company/contact nurture fields only after preview approval.

Use a private app token from Secret Manager or the live profile `.env`. Do not store tokens in this repo.

## Local MCP Adapter

The V1 stdio MCP adapter lives at `runtime/mcp/hubspot_nurtureany_server.py`.

It exposes these tools:

- `list_my_target_accounts`
- `list_team_target_accounts`
- `get_account_context`
- `score_nurture_accounts`
- `find_contact_gaps`
- `generate_free_search_tasks`
- `review_public_enrichment_evidence`
- `draft_nurture_message`
- `plan_hubspot_writeback`

It intentionally does not expose mutation tools in V1.

## Base Company Search

Use HubSpot CRM search with:

- `hs_is_target_account EQ true`
- `company_country IN ["Singapore", "Malaysia", "Indonesia"]`
- AE scope: `hubspot_owner_id EQ <owner id>`
- Manager scope: `company_country IN <allowed countries>`

Use pagination and respect HubSpot rate limits. On 429, back off and retry boundedly; if still rate-limited, return `Confidence: blocked` with the rate-limit caveat.

## Context Fetch

For account context, fetch:

- Company fields from `references/hubspot-fields.md`.
- Associated contacts with persona and buying-role fields.
- Associated deals with stage, amount, close date, contract end date, and owner.
- Recent activities, tasks, and notes as summarized evidence.
- Existing NurtureAny fields when present.

Avoid raw dumps. Return coverage, recency, and rationale.

## Tool Behavior

`list_my_target_accounts`:

- Input: Slack user email, optional limit, optional segment.
- Output: owned target-account summaries only.

`list_team_target_accounts`:

- Input: Slack user email, optional countries, optional owner filter.
- Output: manager/admin scoped summaries only.
- Refuse if caller is not explicitly allowed.

`get_account_context`:

- Input: company ID or exact company selector plus caller identity.
- Output: scoped account context with safe contact summary.

`score_nurture_accounts`:

- Input: scoped account IDs or scope query.
- Output: ranked queue with score, segment, reason, missing data, and confidence.

`find_contact_gaps`:

- Input: scoped account IDs or scope query.
- Output: missing contact/persona/channel/decision-maker coverage.

`generate_free_search_tasks`:

- Input: scoped account IDs or scope query, optional free source types.
- Output: manual/free public-search tasks for company website, careers, public job boards, general web, LinkedIn, Google Maps, Instagram/TikTok, Facebook, and review sites.
- Must not call paid APIs, scrape social/gated sites, reveal PII, send external messages, or mutate HubSpot.

`review_public_enrichment_evidence`:

- Input: one scoped company and public evidence items with source type, URL, title, snippet, observed date, and optional contact candidate fields.
- Output: reviewed evidence, candidate contacts, company signals, outreach angles, and HubSpot dedupe status.
- Fetch only safe public company, careers, or job-board pages with tight caps. Treat LinkedIn, Instagram, TikTok, Facebook, Google Maps, and gated/social sources as manual snippets only.

`draft_nurture_message`:

- Input: account context, segment, manual channel.
- Output: draft only; no send action.

`plan_hubspot_writeback`:

- Input: selected accounts and proposed actions.
- Output: dry-run task/note/field update preview.
- Preserve public/Lusha source evidence, source type, source URL, and confidence in preview actions.

Mutation tools:

- Must reject calls without approved preview ID or explicit selected-action approval.
- Must write concise source summaries, not raw Slack transcripts.
- Must return created/updated object IDs without dumping sensitive fields.
