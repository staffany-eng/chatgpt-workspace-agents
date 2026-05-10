# HubSpot Runtime

HubSpot is the source of truth for NurtureAny target-account queues.

## Required Capabilities

Read phase:

- Read owners and map explicitly classified sales reps from Slack email to HubSpot owner email to owner ID.
- Audit active HubSpot owners and target-account counts for admin-only classification.
- Search companies by target-account flag, owner, and country.
- Read company, contact, deal, association, activity, task, and note context.
- Read existing incomplete sales-owned follow-up tasks associated to scoped target accounts through company, contact, or deal links.
- Read property metadata for field validation and option values.

Write phase:

- Create HubSpot tasks only after preview approval.
- Append HubSpot notes only after preview approval.
- Update company/contact nurture fields only after preview approval.

Use a private app token from Secret Manager or the live profile `.env`. Do not store tokens in this repo.

Use `NURTUREANY_ACCESS_POLICY_PATH` for the runtime-only access policy. Copy `runtime/access-policy.template.json` outside the repo and classify real people there; do not commit the full sales roster.

## Local MCP Adapter

The V1 stdio MCP adapter lives at `runtime/mcp/hubspot_nurtureany_server.py`.

It exposes these tools:

- `list_my_target_accounts`
- `list_team_target_accounts`
- `audit_hubspot_owner_roster`
- `get_account_context`
- `list_sales_followup_tasks`
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
- Authorized manager/admin owner scope: add `hubspot_owner_id EQ <target owner id>` from `owner_email`, while preserving `slack_user_email` as caller identity.

Unclassified HubSpot owners are blocked. A HubSpot owner record alone does not grant AE access.

HubSpot search pages are capped at 100 records. The adapter must paginate internally up to the requested limit and return `total`, `requested_limit`, `returned_count`, `has_more`, and `truncated` for every account-list, scoring, gap, and free-task response. Do not let the agent claim a full count or "all returned" unless `truncated=false` and `has_more=false`.

Use pagination and respect HubSpot rate limits. On 429, back off and retry boundedly; if still rate-limited, return `Confidence: blocked` with the rate-limit caveat.

## Context Fetch

For account context, fetch:

- Company fields from `references/hubspot-fields.md`.
- Associated contacts with persona and buying-role fields.
- Associated deals with stage, amount, close date, contract end date, and owner.
- Existing incomplete sales-owned follow-up tasks as safe summaries only.
- Recent activities and notes as summarized evidence.
- Existing NurtureAny fields when present.

Avoid raw dumps. Return coverage, recency, and rationale.

Sales-owned follow-up tasks are read-only prioritization signals. A task is in scope when it is incomplete, associated to the scoped target account through the company, a company contact, or a company deal, and its `hubspot_owner_id` matches the scoped company owner. Return only `hs_timestamp`, `hs_task_subject`, `hubspot_owner_id`, `hs_task_status`, `hs_task_priority`, `hs_task_type`, `hs_lastmodifieddate`, and association path. Do not expose task body by default.

Generic follow-up coverage is broader than HubSpot task coverage. When the user asks whether a follow-up exists, use HubSpot tasks for `hubspot_task_signal`, then check `team@staffany.com` Calendar events for `calendar_invite_signal` after the scoped HubSpot company is known. Do not answer "no follow-up" from HubSpot tasks alone unless Calendar is also checked or explicitly out of scope.

For account-name-only follow-up checks, use bounded target-account lookup with `query` before task and Calendar checks. Do not use `score_nurture_accounts` as a direct company lookup or as a fallback after missing task/calendar results.

## Follow-Up Person Selection

When a user asks who to follow up with, choose the external person from scoped HubSpot contacts before any enrichment source. Prefer associated contacts with `hs_buying_role=DECISION_MAKER`, then decision-maker job titles, then other buying-role/persona contacts with usable channel fit. Use existing sales-owned follow-up task context to explain why now and identify the internal action owner. If no safe HubSpot contact exists, return no verified external person and recommend a contact-gap or scoped enrichment step.

Calendar hits are scheduling context only and must not determine the person. Luma matched attendees can support an event-related recommendation only after HubSpot account scope is known.

## Tool Behavior

`list_my_target_accounts`:

- Input: Slack user email, optional limit, optional bounded `query`.
- Output: owned target-account summaries only.

`list_team_target_accounts`:

- Input: Slack user email, optional countries, optional owner email filter, optional bounded `query`.
- Output: manager/admin scoped summaries only.
- Refuse if caller is not explicitly allowed.

`audit_hubspot_owner_roster`:

- Input: admin Slack user email, optional countries, optional owner limit.
- Output: active HubSpot owners, classification status, and target-account counts by country.
- Refuse all non-admin callers.

`get_account_context`:

- Input: company ID or exact company selector plus caller identity.
- Output: scoped account context with safe contact, deal, and existing sales follow-up task summary.

`list_sales_followup_tasks`:

- Input: Slack user email, optional company IDs, optional countries, optional owner email filter, optional due window.
- Output: existing incomplete sales-owned HubSpot follow-up tasks with safe task fields only.
- Must not create tasks, mutate HubSpot, trigger write-back preview, or recommend duplicate task creation when an open sales-owned task already exists.

`score_nurture_accounts`:

- Input: scoped account IDs or scope query.
- Output: ranked queue with score, segment, reason, missing data, sales follow-up task signals, pagination completeness metadata, and confidence.
- Do not use for direct account-name lookup or generic follow-up existence checks.

`find_contact_gaps`:

- Input: scoped account IDs or scope query.
- Output: missing contact/persona/channel/decision-maker coverage, gap count, scored account count, pagination completeness metadata, and confidence.

`generate_free_search_tasks`:

- Input: scoped account IDs or scope query, optional free source types.
- Output: manual/free public-search tasks for company website, careers, public job boards, general web, LinkedIn, Google Maps, Instagram/TikTok, Facebook, and review sites.
- Must not call paid APIs, Exa, Lusha, scrape social/gated sites, reveal PII, send external messages, or mutate HubSpot.

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
- Preserve public/Exa/Lusha source evidence, source type, source URL, and confidence in preview actions.
- Refuse manager callers because manager team scope is read-only.
- Refuse actions without scoped HubSpot `company_id` or outside the caller's target-account scope.

Mutation tools:

- Must reject calls without approved preview ID or explicit selected-action approval.
- Must write concise source summaries, not raw Slack transcripts.
- Must return created/updated object IDs without dumping sensitive fields.
