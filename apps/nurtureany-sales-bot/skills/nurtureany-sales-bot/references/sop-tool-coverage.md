# SOP Tool Coverage

Use this reference with `sales-best-practices.md` before changing or answering from NurtureAny tools. It maps the live V1 MCP surface to the sales SOP so every tool keeps the same source hierarchy, access, safety, cost, and mutation boundary.

## Global SOP Rules

- Source hierarchy: HubSpot and live tool output override training docs for target-account membership, owner, country, contract end date, current tools, follow-up status, calls, meetings, tasks, notes, conversations, campaigns, and deals.
- HubSpot override fields: `hs_is_target_account`, `hubspot_owner_id`, `company_country`, `contract_end_date`, `current_tools`, HubSpot communications/notes/tasks/meetings/calls, Conversations threads, Marketing Campaigns, and configured QO/QO Met/closed-won deal stages.
- Plan-first Slack flow: first tool-backed Slack request plans only and waits for `run`; material scope changes need a revised plan.
- Access scope: Slack email is caller identity only; access comes from `NURTUREANY_ACCESS_POLICY_PATH`, HubSpot owners API, and country/owner scope.
- PII/body safety: never return raw Slack transcripts, raw HubSpot rows, communication bodies, note bodies, task bodies, call/meeting bodies, attendee exports, phone exports, raw images, raw registration answers, raw match-key lists, or secrets.
- Cost/credit reporting: Exa must return `cost_report`; Lusha must return `credit_report`; no hidden paid enrichment.
- Mutation policy: V1 exposes read, preview, and selected approval-gated enrichment tools only. `create_hubspot_task`, `append_hubspot_note`, and `update_nurture_fields` are planned write-phase tools and are disabled in V1.
- Sales-best-practices usage: apply `sales-best-practices.md` for Friday review, operating rhythm, QO/QO Met quality, inbound/routing, warm activity, events, pre-demo/demo/post-demo, coaching, AI/data readiness, and nurture drafting.
- Inbound/routing: consider lead source, ICP fit, buying role, current tools, clean-lead completeness, and QO/QO Met quality before treating inbound as sales-ready.
- Event attribution: do not attribute QO, QO Met, deals, or follow-up to an event unless HubSpot stages/tags and event-specific evidence verify it; otherwise mark `needs-check`.
- AI/data readiness: clean CRM/activity data comes before automation advice.

## Tool Coverage Matrix

| Tool | Group | SOP coverage |
| --- | --- | --- |
| `list_inbound_threads` | Inbound | HubSpot Conversations is live evidence; route by lead source, ICP fit, buying role, current tools, clean-lead completeness, and QO/QO Met quality; access scope, plan-first flow, PII/body safety, no mutation. |
| `get_inbound_thread_context` | Inbound | Summarizes one scoped thread without raw bodies; HubSpot override fields still govern account truth; inbound/routing SOP and sales-best-practices apply; no mutation or paid cost. |
| `list_marketing_campaigns` | Marketing | HubSpot Marketing Campaigns are campaign evidence only; source hierarchy, access scope, PII/body safety, and no mutation apply; do not infer revenue attribution without configured HubSpot proof. |
| `get_campaign_assets` | Marketing | Reads bounded HubSpot campaign assets; source hierarchy, PII/body safety, plan-first flow, and no mutation apply; campaign assets do not override HubSpot CRM fields. |
| `get_marketing_touch_context` | Marketing | Maps safe marketing touches back to scoped HubSpot contacts/companies; inbound/routing and attribution stay `needs-check` without stage/tag proof; no raw bodies or mutation. |
| `audit_hubspot_owner_roster` | HubSpot admin | Uses HubSpot owners API and access policy; admin-only scope; PII/body safety; no mutation; cost/credit not applicable. |
| `list_my_target_accounts` | HubSpot queue | HubSpot override fields for target account, owner, and country; AE-only access scope; plan-first flow; PII/body safety; no mutation. |
| `list_team_target_accounts` | HubSpot queue | HubSpot override fields for target account, owner, and country; manager/admin country scope; plan-first flow; PII/body safety; no mutation. |
| `find_target_accounts_by_luma_match_keys` | Event matching | Safe Luma match keys only become scoped HubSpot candidate accounts; event attribution remains `needs-check` until HubSpot evidence verifies; PII/body safety; no mutation. |
| `audit_priority_account_coverage` | Friday rhythm | Uses sales-best-practices for 120/150, double tap, clean lead, 40 connected calls, and QO/QO Met quality; HubSpot override fields, access scope, PII/body safety, no mutation. |
| `build_friday_sales_review` | Friday rhythm | Uses sales-best-practices for operating rhythm, warm activity, Friday correction, inbound/routing, and AI/data readiness; HubSpot stage config gates QO/QO Met; PII/body safety; no mutation. |
| `get_account_context` | Account context | HubSpot override fields plus C360 enrichment for verified customers; access scope; PII/body safety; no mutation; sales-best-practices governs customer/prospect wording. |
| `build_pre_demo_game_plans` | Pre-demo | Uses sales-best-practices and pre-demo reference for I-C-BANT, lead source, current tools, clean-lead completeness, and missing evidence; selected scoped accounts only; no invented pricing/case studies; no mutation. |
| `list_sales_followup_tasks` | Follow-up | HubSpot tasks are source of truth for existing sales-owned follow-up; access scope; task-body safety; no duplicate-task creation or mutation. |
| `check_account_followup_status` | Follow-up | HubSpot communications, notes, tasks, and meetings are source of truth; event attribution stays `needs-check` without event-specific proof; PII/body safety; no mutation. |
| `check_event_followup_status` | Event follow-up | Luma identifies checked-in matched accounts; HubSpot verifies event-specific WhatsApp/tasks; event attribution requires HubSpot verification; raw attendees/bodies hidden; no mutation. |
| `score_nurture_accounts` | Queue scoring | HubSpot override fields and sales-best-practices clean-lead completeness; access scope; PII/body safety; no mutation. |
| `find_contact_gaps` | Enrichment gaps | HubSpot decision-maker and buying-role fields; clean-lead completeness; access scope; PII/body safety; no mutation or paid enrichment. |
| `find_t90_renewal_gaps` | Renewal timing | HubSpot `contract_end_date` overrides secondary dates; current tools from HubSpot; access scope; PII/body safety; no mutation; sales-best-practices follow-up quality. |
| `generate_free_search_tasks` | Public evidence | Review-only public/manual tasks after HubSpot scope; plan-first flow; PII/body safety; no mutation; no Exa/Lusha cost because paid calls are not used. |
| `review_public_enrichment_evidence` | Public evidence | Public snippets support but do not override HubSpot; access scope; PII/body safety; social/gated evidence remains manual-check; no mutation. |
| `scan_drive_event_photos` | Photo/event | Drive/Slack source pointers plus Luma event-date context; raw-image ban; event attribution only when date/tag evidence is clear; PII/body safety; no mutation. |
| `propose_photo_people_matches` | Photo/event | HubSpot scoped contact/company search plus uploader clues; human confirmation required before association; PII/body safety; no mutation. |
| `plan_event_photo_followup` | Preview | Uses confirmed photo match and sales-best-practices warm activity; preview-only mutation policy; no WhatsApp auto-send; planned writes remain disabled. |
| `draft_nurture_message` | Drafting | Uses sales-best-practices for CCC, 3C, K/N/S, QO quality, warm activity, inbound/routing, and manual review; source hierarchy; PII/body safety; no send or mutation. |
| `plan_hubspot_writeback` | Preview | Preview-only mutation policy; requires scoped HubSpot IDs and explicit approval marker before future write phase; PII/body safety; managers remain read-only for team scope. |
| `list_google_calendar_events` | Calendar | Calendar is enrichment only after HubSpot scope; plan-first flow; attendee PII safety; no event mutation; no attendee export. |
| `audit_google_calendar_meeting_quality` | Calendar | Uses HubSpot `calendar_audit_seed` and safe attendee hashes; sales-best-practices meeting/QO quality; PII/body safety; follow-up check via HubSpot; no mutation. |
| `list_luma_events` | Luma | Exact event tags first; Luma is event enrichment only; no raw guest lists; event attribution requires HubSpot verification; no mutation. |
| `get_luma_event_match_keys` | Luma | Event-first safe key extraction; no attendee names, emails, phone numbers, registration answers, or raw key list in Slack; use HubSpot candidate lookup next; no mutation. |
| `get_luma_event_context` | Luma | Requires scoped HubSpot companies; attendance means `checked_in_at`; matched scoped attendee data only; event attribution/follow-up require HubSpot verification; no mutation. |
| `search_exa_people_candidates` | Paid enrichment | Requires scoped HubSpot companies; public candidate discovery only; plan-first flow with cost estimate; `cost_report` required; no PII reveal and no mutation. |
| `search_lusha_decision_maker_candidates` | Paid enrichment | Requires scoped HubSpot companies; plan-first flow with credit caveat; `credit_report` required; availability flags only; no PII reveal and no mutation. |
| `reveal_lusha_contact_details` | Approval-gated enrichment | Requires selected contacts, scoped company IDs, approval marker, and `credit_report`; selected PII only in internal Slack; phone reveal requires explicit flag; no HubSpot mutation. |
| `get_lusha_credit_usage` | Paid enrichment | Credit reporting tool; `credit_report` required; no prospect PII; no HubSpot mutation; blocked/needs-check if usage API is unavailable. |
| `list_drive_folder_images` | Drive photo | Drive metadata only from `team@staffany.com`; source pointers and uploader names only; no raw image copy; no Drive mutation. |
| `extract_drive_image_clues` | Drive photo | Transient image download for OCR/vision clues only; raw bytes discarded; event attribution remains `needs-check` until confirmed; no mutation. |
| `read_indonesia_event_registration_attendance` | Event fallback | Indonesia LL/HHH Sheet fallback only when Luma check-in is empty or not used; `Attend The Event` is manual attendance evidence; safe rows and match keys only; no phone numbers, full emails, raw registration exports, or mutation. |
| `resolve_known_area_for_near_me` | Near-me | Curated known areas outside HubSpot; plan-first flow; no person GPS or employee movement; PII/body safety; no mutation. |
| `build_near_me_c360_customer_query` | Near-me | C360 current-customer layer enriches near-me; HubSpot override fields still govern CRM truth; read-only SQL; PII/body safety; no mutation. |
| `refresh_google_places_for_known_area` | Near-me | Google Places is live candidate discovery only; Google-only rows are not CRM truth; PII/body safety; no mutation. |
| `build_near_me_outlet_matches_query` | Near-me | BigQuery outlet matches are curated memory; read-only SQL; HubSpot/C360 remain context; PII/body safety; no mutation. |
| `merge_near_me_sources` | Near-me | Merge preserves source hierarchy: outlet matches, C360 customers, HubSpot prospects, Google-only candidates; confidence caveats for missing C360 links; no mutation. |
