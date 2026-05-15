# Design: NurtureAny Singapore Lead Enrichment

## Approach

Add one read-only orchestrator tool to the NurtureAny HubSpot MCP:

`build_singapore_lead_enrichment_plan`

The tool reads scoped HubSpot companies and associated contacts, ranks stakeholder candidates, diagnoses HubSpot rollup mismatches, summarizes phone verification state, and returns provider-waterfall guidance plus writeback previews only. It does not mutate HubSpot, reveal paid contact details, run automated Truecaller lookup, run Prospeo/Lusha reveal, or send WhatsApp messages.

## Inputs

- `slack_user_email`
- optional `owner_email`
- optional `company_ids`
- optional `limit`
- optional `batch_size=30`
- optional `phone_stale_after_days=90`

## Scope

- Default pool: `company_country=Singapore` and `hs_is_target_account=true`.
- Explicit `company_ids`: allowed for scoped Singapore HubSpot companies, including non-target-account companies, because the workflow should work for any Singapore HubSpot company when selected.
- `owner_email` narrows the plan to a fixed AE account list and never changes ownership.

## Source Ladder

Use this order:

1. HubSpot
2. HubSpot notes, tasks, activity, existing WhatsApp/email history
3. Tavily public company/job-board research for company site, careers, MyCareersFuture, Indeed, and JobStreet signals
4. Exa people candidate discovery
5. Lusha search plus Prospeo search in a controlled parallel paid-provider pilot
6. approved Lusha or Prospeo reveal
7. manual Truecaller/call outcome
8. HubSpot writeback preview

Additional manual cross-checks from the fixed-AE pilot:

- Company website
- Google Maps
- Facebook / Instagram
- Past HubSpot notes
- Existing WhatsApp / email history
- ACRA only for director/entity verification, not phone numbers

Provider roles:

- Tavily: public company, company-site, careers, and SG job-board signal research.
- Exa: public people/profile candidate discovery; no contact reveal.
- Lusha: selected contact lookup/reveal with explicit approval and `credit_report`.
- Prospeo: V1.1 paid-provider pilot candidate beside Lusha for email/mobile yield comparison; no adapter is enabled in this change.
- Truecaller: manual callability lookup and call outcome evidence only.

Clay stays out of V1 automation, but the workflow copies Clay-style method: conditional runs, provider waterfall, stopping after coverage is sufficient, successful-provider tracking, and current-employment/company-match checks before treating results as usable.

Unbrowse stays out of this workflow because the current safety model avoids automated gated, social, or shadow-API access for prospect enrichment.

## Cost-Effective Waterfall Policy

Optimize for cost per usable AE handoff rather than lowest possible cash spend.

- Default cost mode: `capped_effective`.
- Pilot budget default: under $100/month unless changed.
- Run paid providers only when a real gap remains after HubSpot, public research, and people-candidate discovery.
- Stop paid work once minimum readiness is met or the AE marks the handoff not useful.
- Track successful provider, source, confidence, cost per account moved out of a gap bucket, cost per usable contact, cost per verified/callable phone, AE validation status, and Activities to QO follow-through.
- Provider candidates never count as verified decision makers or verified phones until HubSpot/call verification rules pass.

## Output Buckets

- `nurture_ready`
- `missing_associated_contact`
- `missing_decision_maker`
- `missing_verified_phone`
- `hubspot_rollup_mismatch`
- `needs_paid_reveal`
- `needs_manual_truecaller_check`
- `ready_for_whatsapp_batch`

Each account also returns `provider_waterfall_policy` with the next provider/source step, reason, paid-step eligibility, paid parallel-test status, stop condition, verification rule, and pilot metrics to track.

Each account also returns secondary pilot flags without adding new top-level buckets:

- `missing_champion_influencer_or_operating_contact`
- `below_three_usable_contacts_where_possible`

## Stakeholder Model

Minimum ready state:

- at least one associated contact
- at least one verified decision maker
- at least one verified/callable phone for WhatsApp/call readiness

Preferred SG pilot state:

- `decision_maker`: verified `hs_buying_role=DECISION_MAKER`, or high-confidence candidate needing call verification
- `champion_influencer` / `operating_contact`: HR Director/Manager first, Ops Director/Manager second, Area/Outlet Manager third, Finance/Payroll/Admin Manager fourth
- at least 3 usable contacts where possible
- persona type, source, confidence, and AE next action captured

Title inference alone never counts as verified decision maker.

## Phone Verification

Recognize these contact fields:

- `nurtureany_phone_verification_status`
- `nurtureany_phone_verified_at`
- `nurtureany_phone_verified_by`
- `nurtureany_phone_verification_source`
- `nurtureany_phone_verification_notes`

Allowed statuses:

`not_checked`, `candidate`, `called_connected`, `wrong_number`, `unreachable`, `no_answer`, `do_not_contact`, `stale`

Allowed sources:

`hubspot_existing`, `manual_call`, `lusha_reveal`, `truecaller_manual_lookup`, `apollo_manual`, `prospeo_manual`

Truecaller V1 policy:

- `truecaller_manual_lookup` is candidate/callability evidence only.
- It does not become verified unless paired with `nurtureany_phone_verification_status=called_connected`.
- No automated Truecaller reverse lookup, scraping, or bulk enrichment.

## HubSpot Diagnostics

Flag exact field-level reasons:

- `hs_num_decision_makers > 0` but no returned associated contact has `hs_buying_role=DECISION_MAKER`
- `hs_num_contacts_with_buying_roles > 0` but no associated contact has the actual decision-maker buying role
- associated contacts exist but no contact has fresh `called_connected` phone verification
- `truecaller_manual_lookup` appears without a connected-call outcome

## WhatsApp Readiness

`ready_for_whatsapp_batch` selects up to `batch_size` ready accounts and returns KNS-safe talking points only.

KNS stays as `Knowledge / Network / Support`. Suggested angles:

- salary benchmarking
- Network: event invites, peer/community matching, talent matching, future-speaker sourcing, and customer collaboration opportunities
- Support: speaker, venue, simple-meal, or outlet/product support asks when the opportunity is real
- approved customer proof only after `find_sales_case_studies` or the material registry confirms it

No auto-send.
