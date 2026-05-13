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
| `kai.yi@staffany.com`, `leekai.yi@staffany.com` | Overall admin aliases for `kaiyi@staffany.com` | Singapore, Malaysia, Indonesia |
| `kerren.fong@staffany.com` | SG/MY manager | Singapore, Malaysia team view only |
| `sarah@staffany.com`, `sarah.ayutania@staffany.com` | Indonesia manager | Indonesia team view only |
| explicit `sales_reps` policy entry | AE | Own HubSpot target accounts only |
| unclassified HubSpot owner | blocked | No NurtureAny access |

Manager and AE access are explicit. Do not infer permissions from Slack profile title, channel membership, or a bare HubSpot owner record. The full rep roster lives in a runtime-only file pointed to by `NURTUREANY_ACCESS_POLICY_PATH`; `runtime/access-policy.template.json` contains fake example reps only. Sales rep entries should include an IANA `timezone` such as `Asia/Singapore`, `Asia/Jakarta`, or `Asia/Makassar` so coaching audits can evaluate user-requested WhatsApp windows in each rep's local time.

## Company Properties

| Label / meaning | Internal property | Usage |
| --- | --- | --- |
| Target Account | `hs_is_target_account` | Required base filter, `true`. |
| Company owner | `hubspot_owner_id` | AE ownership filter after Slack email maps to HubSpot owner. |
| Country | `company_country` | Region filter. |
| Number of employees | `numberofemployees` | ICP/headcount signal. |
| Industry | `industry` | ICP signal. |
| Lifecycle Stage | `lifecyclestage` | Customer/prospect classification. `customer` means customer; lead/MQL/SQL/opportunity means prospect unless stronger C360 customer evidence is supplied. |
| Company Type | `type` | Customer/prospect classification. `CUSTOMER` means customer; `PROSPECT` means prospect. |
| Contract end date | `contract_end_date` | Durable source of truth for renewal timing and T-90 nurture windows. |
| Current tools | `current_tools` | Durable source of truth for the sales current-tools answer. HubSpot label is `Past Tools`; metadata describes tools the prospect/customer was using for scheduling, time attendance, and payroll. |
| Current tool renewal date | `current_tool_renewal_date` | Secondary context only. Do not use as the T-90 renewal source of truth. |
| Notes last updated | `notes_last_updated` | Sales activity recency signal. |
| Decision-maker count | `hs_num_decision_makers` | HubSpot company count of associated contacts with buying role `DECISION_MAKER`. NurtureAny reads this from HubSpot; it does not read Eazybe directly for this count. |
| Buying-role contact count | `hs_num_contacts_with_buying_roles` | HubSpot company count of associated contacts with any buying role. This proves buying-role tagging exists, but it does not prove decision-maker coverage unless `hs_num_decision_makers` or a contact `hs_buying_role=DECISION_MAKER` is present. NurtureAny reads this from HubSpot; upstream syncs may affect HubSpot contact roles, but the bot's source is HubSpot. |
| Prospecting Account | `prospecting_account` | Focus/hunting signal, not the target-account source of truth. |
| Quarter Target Account | `quarter_target_account` | Secondary historical/focus signal, not the primary target-account flag. |
| Schedule | `schedule` | Granular current scheduling solution context. Not the durable `current tools` answer. |
| Time and Attendance | `time_and_attendance` | Granular current TMS context. Not the durable `current tools` answer. |
| Payroll Solution | `payroll_solution` | Granular current payroll context. Not the durable `current tools` answer. |
| Present Tools | `present_tools` | PS-managed installed-tools context. Do not use as the sales prospect current-tools source unless the user explicitly asks for PS-managed installed tools. |

## Durable Source-Of-Truth Map

When NurtureAny is asked what data sources it used, answer definitively from this map:

- Target-account membership: HubSpot company property `hs_is_target_account`.
- Owner scope: HubSpot owners API plus HubSpot company property `hubspot_owner_id`.
- Region scope: HubSpot company property `company_country`.
- Renewal timing / T-90 windows: HubSpot company property `contract_end_date`; explicit date-window requests must pass `start_date` and `end_date`.
- Current tools: HubSpot company property `current_tools`.
- Phone verification: HubSpot contact properties `nurtureany_phone_verification_status`, `nurtureany_phone_verified_at`, `nurtureany_phone_verified_by`, `nurtureany_phone_verification_source`, and `nurtureany_phone_verification_notes`.
- Customer/prospect status: HubSpot company property `type`, then `lifecyclestage`, then `prospecting_account`; C360 current-customer evidence may strengthen customer status when explicitly used.
- Sales follow-up status: HubSpot WhatsApp `communications`, notes, completed tasks, and existing incomplete tasks associated to the scoped company/contact/deal.
- Friday connected calls: HubSpot `calls` associated to scoped accounts through company/contact/deal where `hs_call_status=COMPLETED` and `hs_call_duration>=120000`.
- Friday warm activity proof: HubSpot `meetings` associated to scoped accounts through company/contact/deal where `hs_meeting_outcome=COMPLETED` and `hs_meeting_title` or `hs_activity_type` matches a configured warm activity label.
- Manager chase drafts: HubSpot priority-account coverage, safe sales-owned tasks, and safe activity summary fields are truth; selected Slack context is only a short summary/permalink for wording.

`current_tool_renewal_date`, C360, Google Calendar, Luma, Tavily public research, Exa, Lusha, Prospeo pilot evidence, Slack, and public evidence are enrichment or context sources only. They must not override HubSpot target-account membership, ownership, `contract_end_date`, `current_tools`, verified decision-maker fields, or phone-verification fields.

For Calendar follow-up coverage, first resolve the HubSpot company owner to owner name/email through HubSpot owners API. Then scan that AE's calendar ID, for example `jeremy.wong@staffany.com`, using the read-only `team@staffany.com` OAuth account. If the AE calendar is not accessible to `team@staffany.com`, return blocked/needs-check calendar coverage; do not say "no calendar follow-up" from the team primary calendar alone.

For Calendar meeting-quality audit, `get_account_context` returns `company.calendar_audit_seed`. It contains company ID/name/domain, owner email/calendar ID, missing clean-lead fields, decision-maker coverage, I-C-BANT readiness hints, and contact match records with display name, persona/title, buying role, decision-maker flags, email domain, and normalized email hash. It must not return raw contact emails in Slack-facing output. The Calendar audit tool may compare attendee email hashes internally, but output remains safe names/roles and sales-standard findings only.

Do not call a contract-timing prompt a StaffAny renewal call unless customer status is verified. For prospects, use incumbent-tool contract timing, migration/procurement timing, or current-tool confirmation language.

For near-me answers, BigQuery `analytics.nurtureany_near_me_outlet_matches` is the curated outlet/account memory layer, not the customer source of truth. It links known places to HubSpot Company IDs and StaffAny organisations. C360 `analytics.fct_deal_org_company` is still required for current-customer coverage, including customers without stored outlet matches yet. Google Places is live discovery/enrichment only and should not be treated as HubSpot truth.

## BigQuery Outlet Match Table

Use BigQuery table `analytics.nurtureany_near_me_outlet_matches` for curated near-me matches. Do not overload HubSpot Company fields or the existing HubSpot `StaffAny Organisation` object.

Expected properties:

| Label / meaning | Internal property | Usage |
| --- | --- | --- |
| Known area ID | `area_id` | Stable join to curated `known_areas`, e.g. `sg_raffles_place`. |
| Known area name | `area_name` | Display context only. |
| Outlet name | `outlet_name` | Human-readable outlet/branch name. |
| Google Place ID | `google_place_id` | Primary map identity and dedupe key. |
| HubSpot company ID | `hubspot_company_id` | Company pointer when matched; HubSpot Company remains CRM truth. |
| HubSpot owner ID | `hubspot_owner_id` | Snapshot for Slack output; refresh from HubSpot/C360 as needed. |
| StaffAny organisation ID | `organisation_id` | Optional C360 join key. |
| Match status | `match_status` | `confirmed`, `candidate`, or `rejected`. |
| Account status | `account_status` | `customer`, `prospect`, or `unknown`; enrich from Company/C360 when available. |
| Confidence | `confidence` | Match confidence for review. |
| Source | `source` | `manual`, `google_places`, `import`, or workflow source. |
| Last checked at | `last_checked_at` | Last review/refresh timestamp. |

Multiple outlet-match rows may point to one HubSpot Company, for example multiple outlets under one restaurant group at VivoCity.

Google Places live refresh should not permanently store every restaurant. Save, update, reject, or confirm outlet-match records only after review/admin workflow approval.

For T-90 renewal output, split accounts into two explicit buckets: known T-90 accounts with `contract_end_date` inside the requested window, and target accounts missing `contract_end_date` that need classification. If no window is requested, use today through today plus 90 days. The missing-date bucket is required output, not an optional caveat, but broad manager scopes should use the bounded default sample plus total/truncation metadata unless the user explicitly asks for a full missing-date classification list.

## Follow-Up Activity Properties

Use these safe HubSpot timeline fields for post-event follow-up status:

| Object | Safe properties | Usage |
| --- | --- | --- |
| Communications | `hs_timestamp`, `hubspot_owner_id`, `hs_communication_channel_type`, `hs_communication_logged_from` | Count only WhatsApp records where `hs_communication_channel_type=WHATS_APP`. |
| Notes | `hs_timestamp`, `hubspot_owner_id`, `hs_lastmodifieddate` | Count associated notes after `since_at`; do not return note body. |
| Tasks | `hs_timestamp`, `hubspot_owner_id`, `hs_task_status`, `hs_task_priority`, `hs_task_type`, `hs_lastmodifieddate` | Completed tasks count as followed up; incomplete tasks count as scheduled follow-up. |
| Meetings | `hs_timestamp`, `hubspot_owner_id`, `hs_meeting_title`, `hs_meeting_outcome`, `hs_activity_type`, `hs_lastmodifieddate` | Completed meeting logs are safe CRM hygiene evidence; do not return meeting body or guest exports. |

Return safe evidence only: object type, object ID, timestamp, owner ID, channel/status when safe, event-match label when applicable, and association path. `check_event_followup_status` may inspect `hs_communication_body` internally to confirm event-specific Eazybe WhatsApp follow-up, but must never return, log, store, or expose the body. Do not expose `hs_communication_body`, `hs_note_body`, task body, phone numbers, unmatched event attendees, or raw attendee lists.

## Friday Sales Review Activity Properties

Use these safe HubSpot timeline fields for tactical pause Friday reporting:

| Object | Safe properties | Usage |
| --- | --- | --- |
| Calls | `hs_timestamp`, `hubspot_owner_id`, `hs_call_title`, `hs_call_status`, `hs_call_duration`, `hs_lastmodifieddate` | Count connected calls only when status is completed and duration is at least 120 seconds. |
| Meetings | `hs_timestamp`, `hubspot_owner_id`, `hs_meeting_title`, `hs_meeting_outcome`, `hs_activity_type`, `hs_lastmodifieddate` | Count warm activity only when outcome is completed and title/type matches HHH, LL, coffee, lunch, dinner, cosy, ABM, event, appreciation afternoon, or sports. |
| Deals | `pipeline`, `dealstage`, `createdate`, `closedate`, `hs_lastmodifieddate`, `hubspot_owner_id` | QO, QO Met, and closed-won counts require configured pipeline/stage IDs. |

Friday report output mirrors the tactical pause docs: 120/150 account coverage, double tap, 30 WhatsApp daily rhythm, 40 connected calls, QO/QO Met guardrail, warm activity proof, Friday correction, coaching observations, and next-week actions. If `NURTUREANY_QO_PIPELINE_IDS`, `NURTUREANY_QO_STAGE_IDS`, `NURTUREANY_QO_MET_STAGE_IDS`, or `NURTUREANY_CLOSED_WON_STAGE_IDS` is missing, the report still returns hygiene/account coverage with `Confidence: needs-check`.

Do not expose `hs_call_body`, call recordings, meeting bodies, meeting descriptions, attachments, phone numbers, raw communication bodies, note bodies, task bodies, or bulk exports.

## Contact Properties

| Label / meaning | Internal property | Usage |
| --- | --- | --- |
| Email | `email` | Matching and dedupe; avoid exposing by default. |
| First name | `firstname` | Draft personalization when safe. |
| Last name | `lastname` | Draft personalization when safe. |
| Job title | `jobtitle` | Persona signal and role-only decision-maker candidate signal. It does not satisfy audited clean-account coverage by itself. |
| Job role | `job_role` | Persona signal and role-only decision-maker candidate signal. It does not satisfy audited clean-account coverage by itself. |
| Phone | `phone` | Existing phone candidate field. Do not expose raw values in Slack-facing output. |
| Mobile phone | `mobilephone` | Existing mobile candidate field. Do not expose raw values in Slack-facing output. |
| Buying role | `hs_buying_role` | Auditable decision-maker field. Value `DECISION_MAKER` counts as verified direct coverage. |
| Email opt-out | `hs_email_optout` | Do-not-contact guardrail. |
| Contact owner | `hubspot_owner_id` | Secondary ownership/context only. |
| Last modified | `lastmodifieddate` | Contact freshness signal. |
| NurtureAny persona | `nurtureany_persona` | Optional persona/handoff classification. |
| NurtureAny channel fit | `nurtureany_channel_fit` | Optional channel-fit classification. |
| NurtureAny contact confidence | `nurtureany_contact_confidence` | High/Medium/Low/needs-check research confidence. |
| NurtureAny last verified at | `nurtureany_last_verified_at` | General contact verification freshness signal. |
| Phone verification status | `nurtureany_phone_verification_status` | One of `not_checked`, `candidate`, `called_connected`, `wrong_number`, `unreachable`, `no_answer`, `do_not_contact`, or `stale`. Only `called_connected` counts as verified callable coverage. |
| Phone verified at | `nurtureany_phone_verified_at` | Verification date used for staleness checks, default stale after 90 days. |
| Phone verified by | `nurtureany_phone_verified_by` | AE/operator who verified the number. |
| Phone verification source | `nurtureany_phone_verification_source` | One of `hubspot_existing`, `manual_call`, `lusha_reveal`, `truecaller_manual_lookup`, `apollo_manual`, or `prospeo_manual`. |
| Phone verification notes | `nurtureany_phone_verification_notes` | Short safe note. Do not store raw phone numbers in Slack-facing summaries. |

Slack evidence treats Boss, Founder, Owner, HR Director, and Ops Director as decision-maker examples for candidate review. HR Executive alone should not count as decision-maker coverage. Title-only matches are `needs-check` candidates until HubSpot buying role is set.

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
- `nurtureany_phone_verification_status`
- `nurtureany_phone_verified_at`
- `nurtureany_phone_verified_by`
- `nurtureany_phone_verification_source`
- `nurtureany_phone_verification_notes`

All write-back must be previewed first and explicitly approved.
