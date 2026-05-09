# HubSpot Fields And Access Policy

This reference records the V1 HubSpot contract for NurtureAny. HubSpot is the source of truth for target accounts, ownership, contacts, deals, activities, tasks, notes, and nurture write-back fields.

## Regional Scope

Use `company_country`, not free-text `country`.

Confirmed V1 values:

- `Singapore`
- `Malaysia`
- `Indonesia`

Target-account count sanity check on 2026-05-09:

| Country | `hs_is_target_account=true` companies |
| --- | ---: |
| Singapore | 3,095 |
| Malaysia | 1,457 |
| Indonesia | 4,815 |

## Access Matrix

| Slack email | Role | Allowed countries |
| --- | --- | --- |
| `eugene@staffany.com` | Overall admin | Singapore, Malaysia, Indonesia |
| `kaiyi@staffany.com` | Overall admin | Singapore, Malaysia, Indonesia |
| `kerren.fong@staffany.com` | SG/MY manager | Singapore, Malaysia |
| `sarah@staffany.com` | Indonesia manager | Indonesia |
| mapped AE owner email | AE | Own HubSpot target accounts only |

Manager access is explicit. Do not infer permissions from Slack profile title or channel membership.

## Company Properties

| Label / meaning | Internal property | Usage |
| --- | --- | --- |
| Target Account | `hs_is_target_account` | Required base filter, `true`. |
| Company owner | `hubspot_owner_id` | AE ownership filter after Slack email maps to HubSpot owner. |
| Country | `company_country` | Region filter. |
| Number of employees | `numberofemployees` | ICP/headcount signal. |
| Industry | `industry` | ICP signal. |
| Contract end date | `contract_end_date` | Renewal and nurture trigger. |
| Current tool renewal date | `current_tool_renewal_date` | Fallback renewal trigger when contract date is missing. |
| Notes last updated | `notes_last_updated` | Sales activity recency signal. |
| Decision-maker count | `hs_num_decision_makers` | Contact coverage signal. |
| Buying-role contact count | `hs_num_contacts_with_buying_roles` | Contact coverage signal. |
| Prospecting Account | `prospecting_account` | Focus/hunting signal, not the target-account source of truth. |
| Quarter Target Account | `quarter_target_account` | Secondary historical/focus signal, not the primary target-account flag. |

The current-solution field was discussed in Slack as enrichment evidence, but its internal property name must be discovered from HubSpot property metadata before filtering or updating.

## Contact Properties

| Label / meaning | Internal property | Usage |
| --- | --- | --- |
| Email | `email` | Matching and dedupe; avoid exposing by default. |
| First name | `firstname` | Draft personalization when safe. |
| Last name | `lastname` | Draft personalization when safe. |
| Job title | `jobtitle` | Persona signal. |
| Job role | `job_role` | Persona signal. |
| Buying role | `hs_buying_role` | Decision-maker signal. Value `DECISION_MAKER` counts as direct coverage. |
| Contact owner | `hubspot_owner_id` | Secondary ownership/context only. |
| Last modified | `lastmodifieddate` | Contact freshness signal. |

Slack evidence treats Boss, Founder, Owner, HR Director, and Ops Director as decision-maker examples. HR Executive alone should not count as decision-maker coverage.

## Nurture Write-Back Properties

Create or update these company properties during the write-back phase:

- `nurtureany_status`
- `nurtureany_priority_score`
- `nurtureany_segment`
- `nurtureany_next_action`
- `nurtureany_next_trigger_at`
- `nurtureany_last_reviewed_at`
- `nurtureany_last_nurtured_at`
- `nurtureany_enrichment_status`
- `nurtureany_contact_coverage`

Create or update these contact properties during the write-back phase:

- `nurtureany_persona`
- `nurtureany_channel_fit`
- `nurtureany_contact_confidence`
- `nurtureany_last_verified_at`

All write-back must be previewed first and explicitly approved.

