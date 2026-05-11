# HubSpot Runtime

HubSpot is the source of truth for NurtureAny target-account queues.

Field-level durable sources:

- Target accounts: company `hs_is_target_account`.
- Owner scope: HubSpot owners API plus company `hubspot_owner_id`.
- Region scope: company `company_country`.
- Renewal timing and T-90 windows: company `contract_end_date`.
- Current tools: company `current_tools`.
- Customer/prospect status: company `type`, then `lifecyclestage`, then `prospecting_account`; C360 current-customer evidence may strengthen customer status when explicitly used.
- Current-customer account-background packets: C360 sales packet is StaffAny product/Payroll truth. If C360 is unavailable, return `Confidence: needs-check` and do not infer Payroll status from stale HubSpot `current_tools` / `contract_end_date`.
- Decision-maker coverage: company `hs_num_decision_makers` plus contact `hs_buying_role=DECISION_MAKER` are verified HubSpot decision-maker sources. `hs_num_contacts_with_buying_roles` is reported separately as buying-role hygiene, but it does not satisfy decision-maker coverage by itself. NurtureAny does not read Eazybe directly for these counts.

`current_tool_renewal_date` is secondary context only. C360, Google Calendar, Luma, the Indonesia event registration Sheet fallback, Tavily public research, Exa, Lusha, Slack, and public evidence enrich the answer but do not override the durable HubSpot fields above.

Do not call contract timing a StaffAny renewal unless customer status is verified. For prospects or unknowns, use incumbent-tool contract timing or migration/procurement timing.

For near-me workflows, HubSpot Company remains CRM context only. The outlet/account memory layer is BigQuery `analytics.nurtureany_near_me_outlet_matches`; no HubSpot custom object is required.

## Required Capabilities

Read phase:

- Read owners and map explicitly classified sales reps from Slack email to HubSpot owner email to owner ID.
- Audit active HubSpot owners and target-account counts for admin-only classification.
- Search companies by target-account flag, owner, and country.
- Read company, contact, deal, association, activity, task, and note context.
- Read HubSpot follow-up activity associated to scoped target accounts through company, contact, or deal links: WhatsApp communications, notes, completed tasks, existing incomplete sales-owned tasks, and completed meeting logs where available.
- Read HubSpot calls and meetings for the Friday sales review with safe properties only: completed calls, call duration, completed meeting outcome/title/type, and association paths. Do not read call bodies, meeting bodies, recordings, phone numbers, or attachments.
- Read property metadata for field validation and option values.

Write phase:

- Create HubSpot tasks only after preview approval.
- Append HubSpot notes only after preview approval.
- Update company/contact nurture fields only after preview approval.

Use a private app token from Secret Manager or the live profile `.env`. Do not store tokens in this repo.

Use `NURTUREANY_ACCESS_POLICY_PATH` for the runtime-only access policy. Copy `runtime/access-policy.template.json` outside the repo and classify real people there; do not commit the full sales roster. Configure known Slack or Google email variants with `alias_for` or top-level `aliases`; the MCP adapter canonicalizes aliases before role lookup.

`check_event_followup_status` also requires `LUMA_API_KEY` in the same runtime environment so the HubSpot adapter can resolve read-only Luma attendance before checking HubSpot/Eazybe follow-up evidence.
`build_daily_nurture_plan` may use `NURTUREANY_DAILY_RUNS_DIR` to persist the 9am run payload for 12pm Eazybe status/reminder checks. If the env var is absent, return `Confidence: needs-check` instead of silently losing reminder continuity.

## Local MCP Adapter

The V1 stdio MCP adapter lives at `runtime/mcp/hubspot_nurtureany_server.py`.

It exposes these tools:

- `list_inbound_threads`
- `get_inbound_thread_context`
- `audit_inbound_sla`
- `list_marketing_campaigns`
- `get_campaign_assets`
- `get_campaign_social_effectiveness`
- `get_marketing_touch_context`
- `get_marketing_campaign_attribution`
- `list_my_target_accounts`
- `list_team_target_accounts`
- `audit_hubspot_owner_roster`
- `audit_priority_account_coverage`
- `build_sales_metric_actuals_query`
- `build_friday_sales_review`
- `get_account_context`
- `build_pre_demo_game_plans`
- `build_daily_nurture_plan`
- `list_sales_followup_tasks`
- `check_account_followup_status`
- `check_event_followup_status`
- `score_nurture_accounts`
- `find_contact_gaps`
- `find_t90_renewal_gaps`
- `generate_free_search_tasks`
- `review_public_enrichment_evidence`
- `find_target_accounts_by_luma_match_keys`
- `scan_drive_event_photos`
- `propose_photo_people_matches`
- `draft_nurture_message`
- `plan_event_photo_followup`
- `plan_hubspot_writeback`

It intentionally does not expose mutation tools in V1.

The near-me stdio MCP adapter lives separately at `runtime/mcp/near_me_nurtureany_server.py`. It builds BigQuery outlet-match and C360 SQL, refreshes Google Places, and never mutates HubSpot.

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

Generic account-name follow-up checks should resolve scoped HubSpot candidates with bounded target-account `query` lookup before task/calendar checks. Use the resolved HubSpot `owner_email` as the AE calendar ID for Google Calendar coverage through the `team@staffany.com` OAuth token. Do not use `score_nurture_accounts` as a direct company lookup or as a fallback after missing task/calendar results.

Post-event follow-up status uses safe HubSpot timeline evidence only. Count associated WhatsApp `communications` with `hs_communication_channel_type=WHATS_APP`, associated notes, completed tasks, open/incomplete tasks, and completed HubSpot meeting logs after the supplied `since_at`. Event-level follow-up uses Luma first to resolve checked-in matched accounts; for Indonesia LL/HHH events where Luma check-in is empty or not used, `read_indonesia_event_registration_attendance` may provide manual `Attend The Event` attendance keys from the ID Rev registration Sheet. Resolve those attended keys with `find_target_accounts_by_luma_match_keys`; do not call `list_team_target_accounts` or delegate this matching flow. The matched scoped accounts then require event-specific Eazybe WhatsApp evidence in HubSpot or an event-specific completed task for `followed_up`; generic post-event WhatsApp and meeting logs alone become `needs_check`/hygiene evidence. Return object type, object ID, timestamp, owner ID, channel/status/outcome when safe, event-match label when applicable, and association path only. Do not expose communication body, note body, task body, meeting body, phone numbers, unmatched attendees, raw registration rows, or raw event guest exports.

Friday sales review uses the same scoped association discipline, plus HubSpot calls and meetings. Connected calls are completed calls with `hs_call_duration >= 120000` milliseconds. Warm activity points are completed meetings whose title or activity type matches configured labels: HHH, LL, coffee, lunch, dinner, cosy, ABM, event, appreciation afternoon, or sports. QO, QO Met, and closed-won counts require runtime stage config through `NURTUREANY_QO_PIPELINE_IDS`, `NURTUREANY_QO_STAGE_IDS`, `NURTUREANY_QO_MET_STAGE_IDS`, and `NURTUREANY_CLOSED_WON_STAGE_IDS`; when missing, return hygiene and account coverage with `Confidence: needs-check`.

## Tool Behavior

`list_marketing_campaigns` / `get_campaign_assets`:

- Input: manager/admin Slack user email plus campaign name/ID and optional date filters.
- Output: read-only HubSpot campaign metadata and bounded asset summaries.
- Must not imply form submissions, QO, QO Met, closed-won, pipeline, or revenue attribution from campaign asset association alone.

`get_campaign_social_effectiveness`:

- Input: manager/admin Slack user email plus campaign ID, campaign name, or campaign date filters.
- Output: aggregate HubSpot social connected-account counts, `SOCIAL_BROADCAST` click metrics, top clicked post summaries capped at 10, podcast asset count, and metric window.
- Social clicks are engagement evidence only. Do not expose raw social channel IDs, dump all campaign posts, scrape native social platforms, mutate HubSpot, or claim QO/closed-won proof.

`get_marketing_campaign_attribution`:

- Input: manager/admin Slack user email plus campaign ID, campaign name, or campaign UTM.
- Output: bounded search of HubSpot contact marketing source fields, scoped contact/company summaries, and associated deal-stage counts.
- Search source fields such as `utm_campaign`, conversion-event names, and analytics source data; never expose raw PII, raw form submissions, raw contact rows, or mutation tools.
- QO, QO Met, and closed-won counts are valid only when `NURTUREANY_QO_PIPELINE_IDS`, `NURTUREANY_QO_STAGE_IDS`, `NURTUREANY_QO_MET_STAGE_IDS`, and `NURTUREANY_CLOSED_WON_STAGE_IDS` are configured. Without that config, return `Confidence: needs-check`.
- Do not use generic `build_sales_metric_actuals_query` QO totals as campaign attribution. Use BigQuery only after a purpose-built, schema-inspected campaign/UTM query is available.

`audit_inbound_sla`:

- Input: Slack user email, optional safe Slack alert metadata, optional HubSpot inbox/thread filters, SLA minutes, and limit.
- Output: SLA policy, one audit row per Slack alert or HubSpot inbound thread, duplicate summary, rollup, source, scope, confidence, and caveat.
- Default SLA is 5-minute owner acknowledgement and 15-minute first customer touch. Reassignment remains a manual Eugene/manager action; the tool must not auto-assign or mutate HubSpot.
- Treat elapsed minutes `<=` the configured SLA target as pass; do not create a separate boundary status.
- Dedupe only through the same HubSpot conversation thread, contact, ticket, or company. Slack-only duplicate hints stay `needs-check`.
- If supplied Slack alerts have no safe HubSpot IDs, keep `hubspot_match_mode=skipped_no_safe_ids`, say HubSpot match was skipped/no safe IDs, and report timestamp overlaps only as duplicate candidates.
- Final inbound SLA audit answers must use the tool output as the answer source; do not manually recompute a replacement audit table.
- Must not expose raw Slack transcripts, raw HubSpot message bodies, phone numbers, bulk PII, or send external messages.

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

`audit_priority_account_coverage`:

- Input: Slack user email, optional countries, optional owner email filter, optional week start/end, optional limit.
- Output: per-AE locked-pool coverage for the tactical pause rhythm: locked pool count, worked accounts, 120/150 status, double-tapped accounts, untouched accounts, stale accounts, dirty/unworkable accounts, open follow-up tasks, connected calls, warm activity points, evidence completeness, source, scope, confidence, and caveat.
- Locked pool source is `hs_is_target_account=true` plus `hubspot_owner_id` and `company_country`. AEs can audit self only; managers/admins can inspect scoped owners and countries.
- Dirty/unworkable means missing one or more clean-lead fields: industry, headcount, current tools, contract end date, at least one associated contact, and at least one verified decision maker. Role/title-only matches are returned as `needs-check` candidates, not audited clean coverage.
- Must not expose call bodies, meeting bodies, recordings, phone numbers, raw note/task/communication bodies, attachments, or bulk exports.

`build_sales_metric_actuals_query`:

- Input: Slack user email, metric, date range or snapshot month, optional owner email/name, optional countries, and grain.
- Output: metric definition, source table, source class, scoped SQL, `execute_with=staffany_bigquery.execute_sql_readonly`, confidence, and caveat.
- Direct QO prompts use `fct_sales_points.qo_set`. Do not route direct QO questions to Friday review.
- `new ARR` is ambiguous and must ask the user to choose signed converted ARR, paid converted ARR, or New MRR movement ARR before returning SQL.
- Keep BigQuery auth and read-only enforcement in the StaffAny BigQuery MCP proxy. NurtureAny builds SQL only.

`build_friday_sales_review`:

- Input: manager/admin Slack user email, optional countries, optional owner email filter, optional week start/end, optional limit.
- Output: `answer.hygiene_summary`, `answer.funnel_snapshot`, optional `answer.warehouse_metric_followups`, `answer.coaching_observations`, `answer.next_week_actions`, and `answer.support_needed`, plus source, scope, total, returned count, truncation, confidence, and caveat.
- Hygiene summary mirrors the tactical pause docs: `120_150_accounts_worked`, `40_connected_calls`, hit/miss, Friday correction needed, and main issue.
- Funnel snapshot returns accounts worked, connected calls, QOs, QO Met %, deals closed, warm activity points, and caveats. If funnel stage config is missing, QO/QO Met/deal counts are `needs-check` but hygiene still returns.
- Friday review is HubSpot hygiene first. Warehouse QO actuals are a second source and require executing returned SQL through `staffany_bigquery.execute_sql_readonly`.
- Next-week actions must be concrete corrections tied to 120/150 account coverage, double tap, 30 WhatsApp daily rhythm, 40 connected calls, clean-lead fields, and warm activity proof.
- Direct QO count/pace questions should not call this tool. They should resolve owner/team scope and use StaffAny BigQuery `fct_sales_points.qo_set`. A Friday review may add that revenue-metric result as a second source after this HubSpot review output.

`get_account_context`:

- Input: company ID or exact company selector plus caller identity.
- Output: scoped account context with safe contact, deal, and existing sales follow-up task summary, plus HubSpot owner name/email, customer/prospect status/source, route-keyed `c360_url` and `c360_sales_packet` for verified current customers, `account_packet` for default account-background answers, contact coverage source fields, and the recommended AE calendar ID for follow-up scans.
- Output includes `company.calendar_audit_seed` for Google Calendar meeting-quality audits: company ID/name/domain, owner email/calendar ID, missing clean-lead fields, decision-maker coverage, I-C-BANT readiness hints, and safe contact match records with email domains/hashes only. It must not expose raw contact emails in Slack-facing output.
- For account-background answers, use top-level `slack_markdown` or `answer.account_packet.slack_markdown` as the default Slack answer, include the Customer 360 link when returned, and name Customer 360 in `Source` whenever the scoped company is a verified customer. C360 sales packet verifies StaffAny Payroll/product truth; HubSpot `current_tools`, `contract_end_date`, deals, last activity, open tasks, and full IC-BANT stay suppressed by default for StaffAny Payroll customers.

`build_pre_demo_game_plans`:

- Input: Slack user email and selected HubSpot company IDs, company links, or exact company names, capped at 5 accounts per run.
- Output: Slack-first pre-demo game plans with Static Information, Research / stalking signal, Hypothesized interest, Alternatives, What to show to win, 3 name drops, Game Plan A, Game Plan B, IC-BANT prompts, Missing evidence, source, scope, confidence, and caveat.
- Case-study source: `runtime/data/case-studies.json`, generated from the approved public StaffAny customer-story catalog. Matching uses country, industry, size, current-tool pain, and workflow tags.
- Must resolve company names only inside the caller's scoped HubSpot target accounts. Exact one-match results can run; ambiguous names must return scoped candidate company IDs and ask the user to pick; no broad account default.
- On post-approval `run`, pass the selected IDs, links, or raw exact names directly into this tool. Do not call `list_team_target_accounts`, `score_nurture_accounts`, or `find_contact_gaps` as a pre-resolver for game-plan requests; this tool owns scoped name resolution, including compact-name matching such as `Tung Lok` to `Tunglok`.
- Must output `pricing needed` and `case-study match needed` when pricing or approved case studies are missing.
- Must not use Slack-only/WIP case-study mentions as approved name drops.
- Must not fetch social/gated sources, expose raw task bodies, reveal unnecessary PII, mutate HubSpot, or send external messages.

`list_sales_followup_tasks`:

- Input: Slack user email, optional company IDs, optional countries, optional owner email filter, optional due window.
- Output: existing incomplete sales-owned HubSpot follow-up tasks with safe task fields only.
- Must not create tasks, mutate HubSpot, trigger write-back preview, or recommend duplicate task creation when an open sales-owned task already exists.

`check_account_followup_status`:

- Input: Slack user email, selected HubSpot company IDs or links, `since_at`, optional `until_at`, optional limit.
- Output: one row per scoped target account with follow-up status, latest safe follow-up timestamp, activity counts, and safe evidence.
- Optional `include_body=true` is admin-only. When supplied by an admin caller, WhatsApp communication evidence may include a bounded `body` field from HubSpot `hs_communication_body`; non-admin callers are blocked and the default remains body-free.
- Status is `followed_up` when a WhatsApp communication, note, or completed task exists after `since_at`; `scheduled` when only open tasks exist; `not_found` when no associated activity exists; `needs_check` when associations are truncated, ownership does not match cleanly, or evidence is weak.
- Must not expose communication bodies unless `include_body=true` and caller scope is admin. Must not expose note bodies, task bodies, phone numbers, unmatched Luma guests, raw attendee lists, mutate HubSpot, or call Eazybe directly.

`check_event_followup_status`:

- Input: Slack user email, Luma `event_tags`, optional event ID, location, country, event type, search window, owner email, `since_at`, `until_at`, and limit.
- Output: selected event summary, matched target-account count, status counts, per-account status, latest safe evidence timestamp, owner, activity counts, confidence, and caveat.
- Resolves Luma checked-in guests, matches them to scoped HubSpot target accounts, and classifies follow-up from associated event-specific Eazybe WhatsApp communications or event-specific tasks.
- If Luma checked-in attendance is empty for an Indonesia LL/HHH event, Slack workflow may use `read_indonesia_event_registration_attendance` first, then pass attended keys into `find_target_accounts_by_luma_match_keys`, then pass the resolved scoped HubSpot companies into `check_account_followup_status` from the event end time.
- Generic post-event WhatsApp, candidate attendee matching, truncated reads, owner mismatch, or incomplete Eazybe association returns `needs_check`.
- It may inspect `hs_communication_body` internally for event-keyword matching, but the body is never returned, logged, or stored by `check_event_followup_status`.

`score_nurture_accounts`:

- Input: scoped account IDs or scope query.
- Output: ranked queue with score, segment, reason, missing data, sales follow-up task signals, pagination completeness metadata, and confidence.
- Do not use for direct account-name lookup or generic follow-up existence checks.

`find_contact_gaps`:

- Input: scoped account IDs or scope query.
- Output: missing contact/persona/channel/decision-maker coverage, gap count, scored account count, pagination completeness metadata, and confidence.

`find_t90_renewal_gaps`:

- Input: Slack user email, optional countries, optional owner email filter, optional `start_date`/`end_date` renewal window, optional known-T90 limit, optional missing-contract-end-date limit, optional follow-up task lookup flag.
- Output: a primary `answer` object with `known_t90_contract_end_date_accounts`, `gap_accounts`, `missing_contract_end_date_accounts`, counts, and required output sections; plus backward-compatible top-level lists for each bucket.
- Must make missing-contract-date classification a first-class output bucket, not a caveat. The Slack answer must display it even when the user asks for "known T90" or "T90 gaps".
- Returns all scoped target accounts whose HubSpot `contract_end_date` is in the requested window when not truncated, the subset with weak nurture coverage or no verified open sales-owned follow-up, and target accounts with no `contract_end_date` for classification. If no window is requested, use today through today plus 90 days.
- Must filter `contract_end_date` first before any enrichment or task checks.
- Must return `current_tool_renewal_date` as secondary context only; it must not cause T-90 inclusion when `contract_end_date` is missing or outside the window.
- Must return `current_tools` from HubSpot company `current_tools` as the durable current-tools field.
- Must surface completeness metadata separately for the renewal-window bucket and missing-contract-end-date bucket. Do not claim "all" unless `truncated=false` and `has_more=false`.
- Must not let a small known-T90 display `limit` cap the missing-contract-end-date classification bucket; use the bounded default `missing_contract_end_date_limit` with total/truncation metadata unless the user explicitly asks for a full classification list.
- Must not compose broad `score_nurture_accounts` + `find_contact_gaps` calls for this workflow.
- Must not fetch raw contacts, task bodies, paid enrichment, social/gated pages, or mutate HubSpot.

`generate_free_search_tasks`:

- Input: scoped account IDs or scope query, optional free source types.
- Output: manual/free public-search tasks for company website, careers, public job boards, general web, LinkedIn, Google Maps, Instagram/TikTok, Facebook, and review sites.
- Must not call paid APIs, Exa, Lusha, scrape social/gated sites, reveal PII, send external messages, or mutate HubSpot.

`review_public_enrichment_evidence`:

- Input: one scoped company and public evidence items with source type, URL, title, snippet, observed date, and optional contact candidate fields.
- Output: reviewed evidence, candidate contacts, company signals, outreach angles, and HubSpot dedupe status.
- Fetch only safe public company, careers, or job-board pages with tight caps. Treat LinkedIn, Instagram, TikTok, Facebook, Google Maps, and gated/social sources as manual snippets only.

`scan_drive_event_photos`:

- Input: caller Slack email plus Drive file metadata from folder `1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-` (`all-random`), optional Luma event list from the Drive photo date window, optional event/context text.
- Output: photo work items with deterministic `photo_key`, Drive source pointer, parsed Slack-export timestamp/uploader hints, Luma event-date correlation, per-photo uploader confirmation requests, grouped uploader confirmation batches, and a preview of `nurture_event` / `nurture_event_photo` / `nurture_person_appearance` records.
- Luma date matching may auto-tag `nurture_event` only when one clear event-date candidate exists; it must not auto-link a HubSpot contact/person.
- Must not download or store raw images in HubSpot. The Drive runtime may download images transiently for LLM vision/OCR, then pass extracted clues to `propose_photo_people_matches`.

`extract_drive_image_clues`:

- Input: bounded Drive image metadata records from `list_drive_folder_images`, optional context text.
- Output: one clue payload per image with visible badge/signage/company/contact/event text extracted by LLM vision/OCR.
- Must discard raw image bytes before returning, return source/clue JSON only, and never mutate Drive or HubSpot.

`propose_photo_people_matches`:

- Input: Slack or Drive photo source pointer, user/context text, optional LLM vision/OCR clues, and optional explicit contact/company/event/country hints.
- Output: ranked HubSpot contact/company candidates scoped to the caller, confidence score, evidence, missing-clue prompt, optional Luma event-date context, and source-pointer-only custom object plan.
- Use explicit user hints first; otherwise use Luma event-date context, OCR, badge/signage, caption, uploader/thread context, timestamp/event cluster, and scoped HubSpot search.
- High-confidence photo match still requires confirmation from the original uploader or an explicitly responsible human before creating `nurture_person_appearance`, linking a HubSpot contact, or preparing follow-up writes.
- Low-confidence or ambiguous matches should ask one short missing clue, for example `company name?` or `Which contact should I use?`.

`find_target_accounts_by_luma_match_keys`:

- Input: Slack user email, safe Luma email domains, safe Luma company-name candidates, optional countries, optional owner email filter, and limit.
- Output: HubSpot-scoped target-account candidates only, with `hubspot_scoped=true`, `scope_source=hubspot_nurtureany`, and Luma match reason metadata.
- Use after `get_luma_event_match_keys` for broad event-wide questions so the bot searches from Luma attendee keys into HubSpot instead of paging every target account.
- Domain matches are stronger; company-name candidate matches return `Confidence: needs-check`.
- Must not accept raw attendee exports, full Luma emails, phone numbers, or registration answers.

`draft_nurture_message`:

- Input: account context, segment, manual channel.
- Output: draft only; no send action.

`plan_event_photo_followup`:

- Input: a human-confirmed photo match with `contact_id`, scoped `company_id`, photo source pointer, event name, optional due date, and optional `approval_marker`.
- Output: preview-only HubSpot note summary, WhatsApp follow-up task, default due date of next business day 10:00 Asia/Singapore, draft WhatsApp copy, and custom object preview.
- Must never auto-send WhatsApp. HubSpot note/task creation remains approval-gated through the normal write-back phase.

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
