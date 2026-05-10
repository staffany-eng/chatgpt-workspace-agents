# SOP Tool Coverage

Use this reference with `sales-best-practices.md` before answering from or changing NurtureAny tools. It maps the live Hermes profile tool surface to the sales SOP so source hierarchy, access, safety, cost, and mutation boundaries stay consistent.

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
| `list_inbound_threads` | Inbound | HubSpot Conversations summaries only; inbound/routing SOP, access scope, plan-first flow, PII/body safety, no mutation. |
| `get_inbound_thread_context` | Inbound | One explicitly selected thread; HubSpot override fields govern account truth; no bulk export; no mutation. |
| `list_marketing_campaigns` | Marketing | Campaign metadata is context only; source hierarchy, manager/admin access, PII safety, no revenue attribution without HubSpot proof. |
| `get_campaign_assets` | Marketing | Campaign assets and safe Forms submission summaries; raw submissions hidden; podcast assets are attribution context only; no mutation. |
| `get_marketing_touch_context` | Marketing | Maps safe marketing touches to scoped HubSpot context; inbound/routing and attribution stay `needs-check` without proof; no raw bodies. |
| `audit_hubspot_owner_roster` | HubSpot admin | Uses HubSpot owners API and access policy; admin-only scope; no mutation; no body/PII exports. |
| `list_my_target_accounts` | HubSpot queue | HubSpot target, owner, and country fields; AE-owned scope; completeness metadata; no mutation. |
| `list_team_target_accounts` | HubSpot queue | Manager/admin country scope; optional owner filter preserves caller identity; completeness metadata; no mutation. |
| `audit_priority_account_coverage` | Friday rhythm | Uses 120/150, double tap, clean lead, 40 connected calls, warm activity, and QO/QO Met quality; safe activity evidence only. |
| `build_friday_sales_review` | Friday rhythm | Uses sales best practices for hygiene, funnel, coaching, actions, and support; QO/QO Met/deals require configured stage IDs; no raw bodies. |
| `get_account_context` | Account context | HubSpot account truth plus C360 enrichment for verified customers; safe contacts/deals/activity only; no mutation. |
| `build_pre_demo_game_plans` | Pre-demo | Selected scoped accounts only; I-C-BANT and missing-evidence rules; no invented pricing/current tools/case studies; no mutation. |
| `list_sales_followup_tasks` | Follow-up | Existing incomplete sales-owned HubSpot tasks only; safe task fields; no duplicate task creation. |
| `check_account_followup_status` | Follow-up | HubSpot communications, notes, tasks, and meetings determine status; event attribution requires proof; raw bodies hidden. |
| `check_event_followup_status` | Event follow-up | Luma identifies checked-in matched accounts; HubSpot verifies event-specific WhatsApp/tasks; raw attendees and bodies hidden. |
| `find_target_accounts_by_luma_match_keys` | Event matching | Safe Luma match keys only become scoped HubSpot candidate accounts; event attribution remains `needs-check` until HubSpot evidence verifies; no raw match-key list or mutation. |
| `score_nurture_accounts` | Queue scoring | HubSpot override fields and clean-lead completeness; access scope and pagination caveats; no mutation. |
| `find_contact_gaps` | Enrichment gaps | HubSpot decision-maker and buying-role fields; clean-lead completeness; no paid enrichment or raw PII export. |
| `find_t90_renewal_gaps` | Renewal timing | HubSpot `contract_end_date` is durable timing truth; missing-date bucket is explicit; no raw contacts/task bodies. |
| `generate_free_search_tasks` | Public evidence | Review-only public/manual tasks after HubSpot scope; no paid calls, social scraping, or mutation. |
| `review_public_enrichment_evidence` | Public evidence | Public snippets support but do not override HubSpot; social/gated evidence remains manual-check; no mutation. |
| `scan_drive_event_photos` | Photo/event | Drive/Slack source pointers plus Luma date context; raw-image ban; person association requires human confirmation. |
| `propose_photo_people_matches` | Photo/event | Scoped HubSpot contact/company matching plus uploader clues; human confirmation required; no mutation. |
| `plan_event_photo_followup` | Preview | Confirmed photo match preview only; no WhatsApp auto-send; planned writes remain disabled. |
| `draft_nurture_message` | Drafting | Uses CCC, 3C, K/N/S, QO quality, and warm activity; manual review only; no send or mutation. |
| `plan_hubspot_writeback` | Preview | Preview-only mutation boundary; requires scoped HubSpot IDs and explicit future approval; managers remain read-only for team scope. |
| `list_google_calendar_events` | Calendar | Calendar is enrichment after HubSpot scope; read-only `team@staffany.com`; bounded metadata only; no event mutation/export. |
| `audit_google_calendar_meeting_quality` | Calendar | Uses HubSpot `calendar_audit_seed` and attendee hashes internally; safe names/roles only; follow-up via HubSpot. |
| `list_luma_events` | Luma | Exact tags first; Luma is event enrichment only; no raw guest lists or event mutation. |
| `get_luma_event_match_keys` | Luma | Event-first safe key extraction; no attendee names, emails, phone numbers, registration answers, or raw key list in Slack; use HubSpot candidate lookup next. |
| `get_luma_event_context` | Luma | Requires scoped HubSpot companies; attendance is `checked_in_at`; matched scoped attendee data only; no raw exports. |
| `search_exa_people_candidates` | Paid enrichment | Scoped HubSpot companies only; public candidates; `cost_report` required; no profile scraping, email/phone reveal, or mutation. |
| `search_lusha_decision_maker_candidates` | Paid enrichment | Scoped HubSpot companies only; `credit_report` required; availability flags only; no PII reveal or mutation. |
| `reveal_lusha_contact_details` | Approval-gated enrichment | Selected contacts plus approval marker; selected PII only in internal Slack; phone reveal requires explicit flag; no HubSpot mutation. |
| `get_lusha_credit_usage` | Paid enrichment | Credit reporting only; `credit_report` required; no prospect PII or mutation. |
| `list_drive_folder_images` | Drive photo | Drive metadata only from `team@staffany.com`; source pointers and uploader names only; no raw image copy or Drive mutation. |
| `extract_drive_image_clues` | Drive photo | Transient OCR/vision clues only; raw bytes discarded; event/person attribution remains `needs-check` until confirmed. |
| `read_indonesia_event_registration_attendance` | Drive/Sheets event fallback | Restricted Indonesia Rev LL/HHH registration Sheet fallback when Luma attendance is empty or not used; safe rows only; no phone numbers, full emails, raw exports, or Drive mutation. |
| `resolve_known_area_for_near_me` | Near-me | Curated known areas outside HubSpot; no person GPS or employee movement; no mutation. |
| `build_near_me_outlet_matches_query` | Near-me | Builds read-only SQL for curated outlet matches; BigQuery mutation is out of scope. |
| `refresh_google_places_for_known_area` | Near-me | Google Places is live candidate discovery only; Google-only rows are not CRM truth; no mutation. |
| `build_near_me_c360_customer_query` | Near-me | Builds read-only C360 current-customer SQL; no employee GPS/clock rows; HubSpot/C360 source hierarchy applies. |
| `prepare_near_me_seed_review_candidates` | Near-me review | Review-only candidate preparation; approval stays in Slack; writer job rejects unsafe/unlinked rows. |
| `merge_near_me_sources` | Near-me | Merges outlet matches, C360 customers, HubSpot prospects, and Google candidates with confidence caveats; no mutation. |

## Companion BigQuery Tools

`staffany_bigquery.list_dataset_ids`, `staffany_bigquery.list_table_ids`, `staffany_bigquery.get_table_info`, and `staffany_bigquery.execute_sql_readonly` are read-only companion tools. Use them only for bounded schema inspection and read-only SQL returned by approved NurtureAny planning tools. Never run DDL, DML, exports, grants, or raw PII dumps.
