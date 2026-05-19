# Company Enrichment

Use this skill when a user asks NurtureAny to enrich one company, find contacts for one account, or prepare a HubSpot contact-format preview for one scoped target account in Singapore, Malaysia, or Indonesia.

Do not use this skill for batch planning. `build_singapore_lead_enrichment_plan` remains the Singapore batch/planner flow.

## Non-Negotiables

- Enrich exactly one scoped HubSpot company per run.
- Do not start Tavily, standalone public search, Exa, Lusha, Prospeo, or summarization until `resolve_company_enrichment_target` or `create_company_enrichment_artifact` has resolved exactly one scoped HubSpot company.
- Domain is only a tie-breaker. The source of truth is the scoped HubSpot company.
- Never mutate HubSpot, send WhatsApp, send email, start a sequence, or expose raw email/phone/mobile in default Slack output.
- Paid-provider reveal is manual approval gated. Search can run before reveal; reveal requires explicit user approval for selected candidate IDs.
- Public LinkedIn person URLs may be evidence. Do not scrape gated LinkedIn or social profile content.
- LinkedIn, Facebook, Instagram, TikTok, and Slack unfurls are manual-review evidence only. Do not write "confirmed", "verified", or `high confidence` for a role/current-company match that comes only from a LinkedIn/social public result or unfurl. Say "public LinkedIn result suggests..." and keep confidence `needs-check`/`medium` until a safe non-gated source, HubSpot, or approved provider result confirms it.
- Apify LinkedIn/Instagram/Facebook scraping is not part of the default waterfall. Use the Apify scraper skills only when the user explicitly asks to run Apify/social scraping, after one scoped HubSpot company is selected, with actor/budget/result-limit approval.

## Company Resolution

1. If the user gives a HubSpot `company_id`, call `resolve_company_enrichment_target` or `create_company_enrichment_artifact` with that ID.
2. If the user gives a company name, search scoped HubSpot first through `resolve_company_enrichment_target`.
3. If there is exactly one strong scoped match, proceed.
4. If there are multiple scoped matches, show the choices and ask the user to confirm the `company_id`.
5. If there is no scoped match, call `find_brand_parent_candidates` only for identity resolution. Re-query HubSpot with the parent or group candidates via `brand_parent_candidates`.
6. If the parent/group re-query still returns none or ambiguous matches, stop and ask for the HubSpot company ID or exact scoped account name.

## Artifact Flow

Create the artifact with `create_company_enrichment_artifact`. Every later level appends to the same artifact through `update_company_enrichment_artifact`.

- Level 0: HubSpot company, existing contacts, safe notes/activity summary.
- Level 1: Public search strategy for company website, careers, news, official LinkedIn/company/social pages.
- Level 2: Tavily Search/Extract for safe public web discovery. Prioritize public website/contact/careers pages, public articles/directories, and public job posts. Extract public company phone/email/WhatsApp/booking channels when they appear on those non-gated pages. Append the raw tool result to the artifact with `source="tavily"` and `tool_result=<full result>`.
- Level 3: standalone public people/contact search immediately after Tavily, before Exa. Search official team pages, public directory/event/speaker pages, careers pages, job boards such as Indeed, JobStreet, Glints, MyCareersFuture, Maukerja, Ricebowl, Kalibrr, and Dealls, and public company/social pages where allowed. Prefer named people and public company channels found from official/public web evidence over generic LinkedIn-only candidate lists. Append results with `source="standalone_public_search"` or `source="job_board_search"`.
- Level 4: Exa people search only after Level 3, as fallback or corroboration when public search does not find a decision-maker path. Read through public snippets/pages returned by Exa where allowed; public LinkedIn URLs can be evidence, but do not scrape gated LinkedIn or social profile content. Append the raw Exa result plus any safe public-extract evidence to the artifact with `source="exa"` or `source="exa_public_extract"`. Down-rank Exa candidates that do not have a current-company/title match from a non-gated source.
- Level 5: Lusha search. Search by scoped company/domain first. If Lusha returns zero and the artifact has public LinkedIn person URLs, run the Lusha LinkedIn-URL candidate path before marking Level 5 done; append it with `source="lusha_linkedin_url_search"`. If public/provider evidence found full candidate names but no usable LinkedIn URL, run the Lusha name fallback against the scoped company name/domain; append it with `source="lusha_name_search"`.
- Level 6: Prospeo fallback search. Search by scoped company/domain first. If Prospeo returns zero and the artifact has public LinkedIn person URLs, run the Prospeo LinkedIn-URL candidate path before marking Level 6 done; append it with `source="prospeo_linkedin_url_search"`.
- Reveal gate: recommend top candidate IDs and wait for manual reveal approval.
- Level 7: summarize with `summarize_company_enrichment_artifact` into HubSpot contact-format preview rows where `will_mutate_hubspot=false`.

For this single-company skill, the full report is a deterministic read-through waterfall. Run and append Levels 2 through 6 before calling the final summary. The artifact summary contains `waterfall_state`; if `waterfall_state.can_claim_full_waterfall=false`, do not say enrichment is complete or that all providers ran. Run `waterfall_state.next_required_tool` first.

Readiness still matters for reveal decisions: at least one decision-maker path plus one usable channel path means the user can act, but it does not mean the full waterfall has run. Paid-provider search can run without reveal; paid-provider reveal still requires explicit approval for selected candidate IDs.

After every Tavily, standalone public-search, Exa, Lusha, or Prospeo call, immediately call `update_company_enrichment_artifact` with the same `artifact_id`, the correct `source`, and either `tool_result=<raw tool response>` or normalized `candidates`/`evidence`. Do not summarize directly from provider output; summarize only from `summarize_company_enrichment_artifact`.

Do not mark a public-search or Exa level complete with notes only. Level 2, Level 3, and Level 4 must append at least one candidate or evidence item, and the update status must be `completed`. If a public search truly finds nothing, append the searched URLs/queries as evidence with the no-result reason; otherwise `waterfall_state` should remain partial.

Return public company channels separately when found, such as official website or article-listed company emails, booking WhatsApp numbers, and outlet phone numbers. These are public company channels, not personal Lusha/Prospeo reveal details. Personal email/phone/mobile from providers still requires reveal approval.

For public extraction, allowed non-gated sources include official websites, contact pages, careers pages, public job posts (JobStreet, Indeed, Glints, MyCareersFuture, Maukerja, Ricebowl, Kalibrr, Dealls), directories, review sites, and articles. Social URLs remain manual-review only.

If the user explicitly requests Apify social scraping, use the relevant `apify-linkedin-scraper`, `apify-instagram-scraper`, or `apify-facebook-scraper` skill as a separate add-on step. Append any bounded, normalized output back to the artifact as manual-review evidence; do not use Apify social output alone to claim a verified decision maker.

## Candidate Rules

Use shared ICP roles first: owner, founder, CEO, MD, director, GM, HR, people, operations, finance, payroll, admin. Add country-specific title overrides later only when evidence proves different patterns for SG/MY/ID.

Confidence:

- `high`: exact scoped company/domain match, current-company match, strong role match, no HubSpot duplicate, and provider evidence present.
- `medium`: plausible but needs human review.
- `low`: weak or incomplete evidence.

Default artifact reads redact email, phone, and mobile. Revealed PII may be stored for 14 days and exposed only when the user explicitly asks to include revealed details with an approval marker.

## Output Shape

Return a concise company-level summary:

- scoped company and country
- completed levels and next recommended level
- ready state: decision-maker path and usable channel path
- top reveal recommendations, if any
- HubSpot contact-format preview rows
- explicit `will_mutate_hubspot=false`

If reveal is not approved, summarize a safe preview from existing contacts and unrevealed candidates only.
