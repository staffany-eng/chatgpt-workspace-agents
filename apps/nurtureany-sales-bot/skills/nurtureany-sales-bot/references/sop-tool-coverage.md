# SOP Tool Coverage

Use this reference with `sales-best-practices.md` before changing or answering from NurtureAny tools. It maps the live V1 MCP surface to the sales SOP so every tool keeps the same source hierarchy, access, safety, cost, and mutation boundary.

## Global SOP Rules

- Source hierarchy: HubSpot and live tool output override training docs for target-account membership, owner, country, contract end date, current tools, follow-up status, calls, meetings, tasks, notes, conversations, campaigns, and deals.
- HubSpot override fields: `hs_is_target_account`, `hubspot_owner_id`, `company_country`, `contract_end_date`, `current_tools`, HubSpot communications/notes/tasks/meetings/calls, Conversations threads, Marketing Campaigns, and configured QO/QO Met/closed-won deal stages.
- Plan-first Slack flow: first tool-backed Slack request plans only and waits for `run`; material scope changes need a revised plan.
- Access scope: Slack email is caller identity only; access comes from `NURTUREANY_ACCESS_POLICY_PATH`, HubSpot owners API, and country/owner scope.
- PII/body safety: never return raw Slack transcripts, raw HubSpot rows, communication bodies, note bodies, task bodies, call/meeting bodies, attendee exports, phone exports, raw images, raw registration answers, raw match-key lists, or secrets by default. The only communication-body exception is `check_account_followup_status(include_body=true)` for admin callers and selected company IDs; note/task bodies, event guest data, phone exports, and bulk exports remain blocked.
- Cost/credit reporting: Tavily public research and Exa must return `cost_report`; Lusha must return `credit_report`; any future Prospeo pilot must add equivalent cost/credit reporting before use. No hidden paid enrichment.
- Mutation policy: V1 exposes read, preview, and selected approval-gated enrichment tools only. `create_hubspot_task`, `append_hubspot_note`, and `update_nurture_fields` are planned write-phase tools and are disabled in V1.
- PII/body safety: never return raw Slack transcripts, raw HubSpot rows, communication bodies, note bodies, task bodies, call/meeting bodies, attendee exports, phone exports, raw images, raw registration answers, raw match-key lists, or secrets.
- Cost/credit reporting: Exa must return `cost_report`; Lusha must return `credit_report`; Prospeo has no active adapter and remains pilot-contract only until cost reporting exists. No hidden paid enrichment.
- Mutation policy: V1 exposes read, preview, selected approval-gated enrichment, and selected approval-gated Eazybe template-send tools only. `create_hubspot_task`, `append_hubspot_note`, and `update_nurture_fields` are planned write-phase tools and are disabled in V1.
- Sales-best-practices usage: apply `sales-best-practices.md` for Friday review, operating rhythm, QO/QO Met quality, inbound/routing, warm activity, events, pre-demo/demo/post-demo, coaching, AI/data readiness, and nurture drafting.
- Inbound/routing: consider lead source, ICP fit, buying role, current tools, clean-lead completeness, and QO/QO Met quality before treating inbound as sales-ready.
- Event attribution: do not attribute QO, QO Met, deals, or follow-up to an event unless HubSpot stages/tags and event-specific evidence verify it; otherwise mark `needs-check`.
- AI/data readiness: clean CRM/activity data comes before automation advice.

## Tool Coverage Matrix

| Tool | Group | SOP coverage |
| --- | --- | --- |
| `list_inbound_threads` | Inbound | HubSpot Conversations summaries only; apply inbound/routing SOP, access scope, plan-first flow, PII/body safety, no mutation. |
| `get_inbound_thread_context` | Inbound | One selected thread only; HubSpot override fields govern account truth; no bulk export, no raw-body dump, no mutation. |
| `audit_inbound_sla` | Inbound | Admin/manager inbound SLA audit only; safe aggregate routing/ack/first-touch evidence plus safe per-row lead context when available; no phone numbers, bulk raw thread export, or mutation. |
| `list_marketing_campaigns` | Marketing | Campaign metadata is context only; manager/admin access, PII/body safety, no mutation, no revenue attribution without HubSpot proof. |
| `get_campaign_assets` | Marketing | Reads bounded HubSpot campaign assets and safe Forms summaries; raw submissions hidden; campaign assets do not override CRM fields. |
| `get_campaign_social_effectiveness` | Marketing | Reads HubSpot social connected-account status and aggregate `SOCIAL_BROADCAST` clicks for one campaign; social clicks are engagement evidence only, raw channel IDs and bulk post exports stay hidden, and no native social scraping or mutation is allowed. |
| `get_marketing_touch_context` | Marketing | Maps safe marketing touches to scoped HubSpot context; inbound/routing and attribution stay `needs-check` without proof. |
| `get_marketing_campaign_attribution` | Marketing | Searches bounded HubSpot contact source fields and maps only scoped contacts/companies before checking configured QO/QO Met/closed-won deal stages; read `answer.outcome_summary` first so truncation cannot hide visible QO/QO Met/closed-won counts; no raw PII, raw form rows, generic QO-total substitution, or mutation. |
| `audit_hubspot_owner_roster` | HubSpot admin | Uses HubSpot owners API and access policy; admin-only scope; no body/PII exports, no mutation. |
| `list_my_target_accounts` | HubSpot queue | HubSpot target, owner, and country fields; AE-owned scope; completeness metadata; no mutation. |
| `list_team_target_accounts` | HubSpot queue | Manager/admin country scope; optional owner filter preserves caller identity; completeness metadata; no mutation. |
| `find_target_accounts_by_luma_match_keys` | Event matching | Safe Luma/Sheet match keys become scoped HubSpot candidate accounts with HubSpot owner and customer/prospect/unknown status; event attribution remains `needs-check` until HubSpot evidence verifies. |
| `audit_priority_account_coverage` | Friday rhythm | Uses 120/150, double tap, clean lead, 40 connected calls, warm activity, and QO/QO Met quality; safe activity evidence only. |
| `build_sales_metric_actuals_query` | Revenue actuals | Builds scoped aggregate SQL for QO and revenue actuals; Rev Sheets/Slides are targets/definitions only; execute through `staffany_bigquery.execute_sql_readonly`. |
| `build_hubspot_revenue_funnel_metrics` | Revenue funnel | Read-only HubSpot created-date deal cohort with Sales Outbound/all-outbound, new-business, renewal exclusion, headcount, industry, signed-stage, and manual-correction audit rows; no HubSpot mutation. |
| `build_ae_coaching_audit` | AE coaching | Metadata-only weekly AE audit for 3 QOs set, morning-message coverage, 40 connected calls, and >=60s calls without appointment evidence; returns 1:1 preview rows only, no Sheet mutation or call bodies. |
| `count_owner_whatsapp_sent_today` | Activity count | Direct owner/date count of HubSpot WhatsApp communication metadata for scoped target accounts; use instead of broad Friday/coaching audits for "sent today" counts; no raw bodies, phone numbers, notes, tasks, meetings, or mutation. |
| `prepare_sales_navigator_decision_maker_queue` | Decision-maker handoff | Manual Sales Navigator queue from scoped HubSpot company/contact context; `pre_demo_150` and `post_event_top10` only, no LinkedIn scraping, browser automation, PII reveal, or HubSpot mutation. |
| `build_friday_sales_review` | Friday rhythm | Uses sales best practices for hygiene, funnel, coaching, actions, support, and optional warehouse follow-ups; stage config gates QO/QO Met; no raw bodies. |
| `build_manager_chase_plan` | Manager chase | Manager/admin-only copy-ready chase drafts from HubSpot coverage, task/activity evidence, and optional selected Slack blocker summaries; Manager draft only, no rep tags, raw transcripts, sends, or mutation. |
| `get_account_context` | Account context | HubSpot account truth plus C360 enrichment for verified customers; safe packet by default; access scope, PII/body safety, no mutation. |
| `build_pre_demo_game_plans` | Pre-demo | Selected scoped accounts only; I-C-BANT and missing-evidence rules; optional Slack source-thread permalink as provenance only; no raw Slack transcript, invented pricing/current tools/case studies, or mutation. |
| `find_sales_case_studies` | Case studies | Read-only approved public customer-story and full-video-reviewed BMC podcast-card lookup for scoped HubSpot accounts or supplied brainstorm queries; no weak analogy promotion, HubSpot mutation, or unapproved name drops. |
| `build_singapore_lead_enrichment_plan` | Lead enrichment | Review-first Singapore lead-enrichment plan over scoped HubSpot target accounts or selected SG HubSpot companies; covers decision maker, champion/influencer, usable-contact, phone verification, field-level mismatch, capped-effective provider-waterfall policy, handoff note, and draft-only WhatsApp readiness; source ladder is HubSpot -> HubSpot notes/tasks/history -> Tavily public company/job-board research -> Exa people candidates -> controlled Lusha + Prospeo paid-provider pilot -> approved reveal -> manual Truecaller/call outcome -> HubSpot preview; no paid reveal, Truecaller automation, raw phone export, WhatsApp send, owner reassignment, or HubSpot mutation. |
| `list_active_deals_missing_next_meeting` | Deal hygiene | Direct path for active deals with no next meeting; uses scoped target accounts, associated deals, and future HubSpot meeting associations; no Friday-review/account-coverage detour. |
| `list_sales_followup_tasks` | Follow-up | Existing incomplete sales-owned HubSpot tasks only; safe task fields; no duplicate task creation. |
| `check_account_followup_status` | Follow-up | HubSpot communications, notes, tasks, and meetings determine status; event attribution requires proof; raw bodies hidden. |
| `check_event_followup_status` | Event follow-up | Luma/Sheet attendance identifies matched accounts; HubSpot owner and customer/prospect/unknown status travel with each account; HubSpot verifies event-specific WhatsApp/tasks; raw attendees and bodies hidden. |
| `build_daily_nurture_plan` | Daily nurture | Jeremy-style 09:00 Asia/Singapore pack; HubSpot target accounts/contacts/roles are source of truth, Sheet material rows are read-only context, 30/150 rotation has no silent replacement, all decision makers/influencers/champions get draft rows. |
| `record_nurtureany_operation_checkpoint` | Runtime continuity | Profile-runtime ledger checkpoint only; records resumable phase, approval marker presence, idempotency key, and side-effect class without performing any external send or HubSpot mutation. |
| `read_nurtureany_operation_ledger` | Runtime continuity | Reads compact checkpoint state for restart-safe continuation; read-only resume is allowed, but repeated sends/writes stay blocked unless approval marker and idempotency key are both present. |
| `score_nurture_accounts` | Queue scoring | HubSpot override fields and clean-lead completeness; access scope and pagination caveats; no mutation. |
| `find_contact_gaps` | Enrichment gaps | HubSpot decision-maker and buying-role fields; clean-lead completeness; no paid enrichment or raw PII export. |
| `find_t90_renewal_gaps` | Renewal timing | HubSpot `contract_end_date` is durable timing truth; missing-date bucket is explicit; no raw contacts/task bodies. |
| `generate_free_search_tasks` | Public evidence | Review-only public/manual tasks after HubSpot scope; no paid calls, social scraping, or mutation. |
| `research_public_company_signals` | Public evidence | Tavily Search/Extract public company research only after scoped HubSpot company inputs; return `cost_report`, `manual_check_items`, `missing_evidence`, and `will_mutate_hubspot=false`; no gated/social scraping, private HubSpot notes/tasks/contact PII export, or mutation. |
| `review_public_enrichment_evidence` | Public evidence | Public snippets support but do not override HubSpot; social/gated evidence remains manual-check; no mutation. |
| `scan_drive_event_photos` | Photo/event | Drive/Slack source pointers plus Luma date context; raw-image ban; person association requires human confirmation. |
| `propose_photo_people_matches` | Photo/event | Scoped HubSpot contact/company matching plus uploader clues; human confirmation required; no mutation. |
| `plan_event_photo_followup` | Preview | Confirmed photo match preview only; no WhatsApp auto-send; planned writes remain disabled. |
| `draft_nurture_message` | Drafting | Uses CCC, 3C, K/N/S, QO quality, warm activity, and inbound/routing; manual review only; no send or mutation. |
| `plan_hubspot_writeback` | Preview | Preview-only mutation boundary; requires scoped HubSpot IDs and explicit future approval; managers remain read-only for team scope. |
| `list_google_calendar_events` | Calendar | Calendar is enrichment after HubSpot scope; read-only `team@staffany.com`; bounded metadata only; no event mutation/export. |
| `audit_google_calendar_meeting_quality` | Calendar | Uses HubSpot `calendar_audit_seed` and attendee hashes internally; safe names/roles only; follow-up via HubSpot. |
| `list_luma_events` | Luma | Exact tags first; Luma is event enrichment only; no raw guest lists or event mutation. |
| `get_luma_event_match_keys` | Luma | Event-first safe key extraction; no attendee names, emails, phone numbers, registration answers, or raw key list in Slack. |
| `get_luma_event_context` | Luma | Requires scoped HubSpot companies; attendance is `checked_in_at`; matched scoped attendee data only; no raw exports. |
| `search_exa_people_candidates` | Paid enrichment | Scoped HubSpot companies only; public candidates; `cost_report` required; no profile scraping, email/phone reveal, or mutation. |
| `search_lusha_decision_maker_candidates` | Paid enrichment | Scoped HubSpot companies only; `credit_report` required; availability flags only; no PII reveal or mutation. |
| `reveal_lusha_contact_details` | Approval-gated enrichment | Selected contacts plus approval marker; selected PII only in internal Slack; phone reveal requires explicit flag; no HubSpot mutation. |
| `get_lusha_credit_usage` | Paid enrichment | Credit reporting only; `credit_report` required; no prospect PII or mutation. |
| `read_google_slides_deck` | Drive material | Read-only Google Slides extraction for approved sales material; no Drive mutation and no raw export beyond bounded text. |
| `list_drive_folder_images` | Drive photo | Drive metadata only from `team@staffany.com`; source pointers and uploader names only; no raw image copy or Drive mutation. |
| `read_google_slides_deck` | Drive deck | Selected Google Slides or Drive-hosted `.pptx` text only through `team@staffany.com`; no public link sharing, edits, comments, raw byte retention, or CRM truth override. |
| `extract_drive_image_clues` | Drive photo | Transient OCR/vision clues only; raw bytes discarded; event/person attribution remains `needs-check` until confirmed. |
| `read_nurture_material_registry` | Material registry | One read-only Google Sheet for Materials, Playbooks, Peer Intros, Speaker/Venue Opportunities, Events, and Review Log; active/approved/live rows only; no Drive mutation. |
| `read_indonesia_event_registration_attendance` | Event fallback | Indonesia LL/HHH Sheet fallback only when Luma check-in is empty or not used; `Attend The Event` is manual attendance evidence; safe rows and match keys only. |
| `preview_eazybe_template_messages` | Eazybe preview | Selected message IDs only; validates approved template payload and ordered params; phone numbers redacted; no send. |
| `send_approved_eazybe_messages` | Approval-gated send | Requires `approval_marker`; sends only approved Eazybe `templateName` plus ordered `templateParams`; partial failures surfaced; no free-form drafts. |
| `check_eazybe_send_status` | Eazybe status | Summarizes accepted/queued/sent/delivered/failed/pending states for the run; HubSpot WhatsApp evidence can also satisfy sent definition. |
| `build_daily_nurture_reminder` | Slack reminder | 12:00 Asia/Singapore reminder; fires for unsent/unskipped stakeholder messages and tags the configured AE and manager. |
| `resolve_known_area_for_near_me` | Near-me | Curated known areas outside HubSpot; no person GPS or employee movement; no mutation. |
| `build_near_me_outlet_matches_query` | Near-me | Builds read-only SQL for curated outlet matches; BigQuery mutation is out of scope. |
| `refresh_google_places_for_known_area` | Near-me | Google Places is live candidate discovery only; Google-only rows are not CRM truth; no mutation. |
| `build_near_me_c360_customer_query` | Near-me | Builds read-only C360 current-customer SQL; no employee GPS/clock rows; HubSpot/C360 source hierarchy applies. |
| `prepare_near_me_seed_review_candidates` | Near-me review | Review-only candidate preparation; approval stays in Slack; writer job rejects unsafe/unlinked rows. |
| `merge_near_me_sources` | Near-me | Merges outlet matches, C360 customers, HubSpot prospects, and Google candidates with confidence caveats; no mutation. |

## Companion BigQuery Tools

`staffany_bigquery.list_dataset_ids`, `staffany_bigquery.list_table_ids`, `staffany_bigquery.get_table_info`, and `staffany_bigquery.execute_sql_readonly` are read-only companion tools. Use them only for bounded schema inspection and read-only SQL returned by approved NurtureAny planning tools. Never run DDL, DML, exports, grants, or raw PII dumps.

## Runtime Boundaries

If a broad HubSpot tool returns `partial_due_to_soft_timeout=true`, answer from the partial scope and stop. Do not chain another broad audit to compensate; narrow the next run by owner, country, date, or direct-purpose tool.
