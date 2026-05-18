# Health Checks

NurtureAny needs deterministic runtime checks because prompt correctness does not guarantee connector scopes, HubSpot fields, or gateway restarts.

## Expected Checks

- Hermes gateway service for `nurtureanysalesbot` is active.
- On Linux cloud hosts, gateway health checks `hermes-gateway-nurtureanysalesbot.service` through `systemd --user` instead of grepping old journal/status text.
- On macOS development hosts, gateway health checks the launchctl label before falling back to `hermes gateway status`.
- Slack Socket Mode watchdog is installed as no-agent cron and restarts the managed `nurtureanysalesbot` gateway service when the latest stale Socket Mode line is not followed by a fresh session for at least 300 seconds.
- Slack ingress watchdog uses `SLACK_BOT_TOKEN` to read recent configured-channel history, finds recent human messages that mention the bot, checks for a bot reply or a gateway `inbound message: platform=slack` log after the mention, and restarts the gateway when the mention is older than the grace window but never reached the gateway. This catches the stale-listener failure mode where Socket Mode still says connected.
- Local cloud heartbeat is installed as no-agent cron on `nurtureany-sales-bot-prod`. It checks only the local VM: user-systemd gateway state, expected Hermes cron records, paused legacy event-ROI jobs, unsafe-send absence, and redacted cloud-doctor MCP counts. Healthy runs print nothing.
- Cron concurrency is capped with `cron.max_parallel_jobs: 1`.
- Secret redaction remains enabled.
- Production dotenv hydration can use Secret Manager secret `projects/1093387803298/secrets/nurtureany-sales-bot-prod-env` in project `staffany-warehouse`; health, doctor, and audit output must verify key presence by name only and must not print values.
- Model route is pinned to native Anthropic Sonnet: `model.provider=anthropic`, `model.default=claude-sonnet-4-6`.
- Slack gateway can receive mentions and identify caller email.
- Slack processing status reactions are enabled with `slack.reactions=true`.
- Same-thread `run` replies after a bot plan route without re-mentioning the bot when the thread parent mentioned `@NurtureAny`.
- Quick-autorun policy is enabled only for obvious, exact, read-only or preview/draft-only work expected under 60 seconds, using at most 10 configured-channel Slack context messages from the last 30 minutes.
- Slack intent-context smoke check confirms `read_recent_slack_intent_context` is available, uses `SLACK_BOT_TOKEN`, reads configured channels only, returns safe summaries/permalinks only, persists no raw transcript, and reports missing `conversations.history`, `conversations.replies`, `chat.getPermalink`, or channel membership as a blocker.
- Slack selected-thread smoke check confirms `get_current_slack_thread_context` and `get_selected_slack_thread_context` are available only for selected public or configured thread-context channel reads before `run`, after `run`, or during bounded continuation, cap output at 50 messages, return safe summaries/permalinks only, persist no raw transcript, can use `NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS=all` for public channels, can auto-join public source channels with `conversations.join`, do not depend on Kai Yi channel membership, and do not expose posting, reactions, pins, private-channel bypass, broad search, broad user listing, user-token fallback, or Slack connector fallback.
- Slack inbound-alert smoke check confirms `extract_inbound_lead_alerts` is available, uses `SLACK_BOT_TOKEN`, reads only configured public channels from `NURTUREANY_INBOUND_ALERT_CHANNEL_IDS`, can auto-join configured public inbound channels, caps output at 50 alert messages, returns safe alert rows/permalinks only, persists no raw transcript, and exposes no raw phone numbers.
- Slack stand-up/down accountability smoke check confirms `audit_standup_down_accountability` is available, uses `NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS`, can read configured public channel `C013N5XL7EV` (`#team-rev-ps-syncup`) with `conversations.info`, `conversations.history`, `conversations.members`, `users.info`, `chat.getPermalink`, and configured-public-channel `conversations.join`, returns safe per-person status/permalinks only, persists no raw transcript, returns no raw note bodies, and does not expose posting, private-channel reads, broad search, broad user listing, user-token fallback, or Slack connector fallback.
- Slack gateway `SLACK_ALLOWED_USERS` matches the active, resolved Slack users from `NURTUREANY_ACCESS_POLICY_PATH`, including admins, managers, partnerships viewers, event-operator aliases, and sales reps; policy aliases that do not resolve in Slack are ignored, but missing or extra resolved user IDs fail health.
- Slack allowlist checks include built-in admins/managers, active `sales_reps`, and explicit `event_operators`. The no-agent repair script may update only `SLACK_ALLOWED_USERS` to match an already-approved runtime policy; it must not grant new policy roles from Slack profile data.
- `NURTUREANY_ACCESS_POLICY_PATH` points to a runtime-only policy file when sales reps are enabled; the source template has fake example reps only.
- HubSpot owner lookup works for configured admins/managers and classified sales reps.
- HubSpot MCP lists `audit_hubspot_owner_roster`, and non-admin roster audit requests return `Confidence: blocked`.
- HubSpot company property metadata includes `hs_is_target_account`, `hubspot_owner_id`, and `company_country`.
- HubSpot company property metadata includes durable NurtureAny fields `contract_end_date` and `current_tools`; `current_tool_renewal_date` is present only as secondary context.
- HubSpot `company_country` options include `Singapore`, `Malaysia`, and `Indonesia`.
- Slack MCP lists `read_recent_slack_intent_context`, `get_current_slack_thread_context`, `get_selected_slack_thread_context`, and `audit_standup_down_accountability`.
- HubSpot MCP lists inbound Conversations, Marketing Campaigns, campaign social effectiveness, marketing campaign attribution, `resolve_inbound_slack_alerts_to_hubspot`, `resolve_nurture_scope`, `resolve_sales_owners`, `list_sales_call_events`, `summarize_sales_call_stats`, `audit_priority_account_coverage`, `build_sales_metric_actuals_query`, `build_hubspot_revenue_funnel_metrics`, `build_ae_coaching_audit`, `prepare_sales_navigator_decision_maker_queue`, `build_friday_sales_review`, `build_manager_chase_plan`, `find_event_sourcing_target_accounts`, `build_pre_demo_game_plans`, `build_singapore_lead_enrichment_plan`, `list_sales_followup_tasks`, `preview_hubspot_sales_task`, `create_approved_hubspot_sales_task`, `preview_hubspot_task_update`, `apply_approved_hubspot_task_update`, `list_due_hubspot_sales_task_reminders`, `check_account_followup_status`, `check_event_followup_status`, `generate_free_search_tasks`, and `review_public_enrichment_evidence` in addition to the existing queue, gap, draft, and preview tools.
- HubSpot campaign social-effectiveness smoke check uses `get_campaign_social_effectiveness`, reports aggregate `SOCIAL_BROADCAST` clicks separately from pipeline proof, redacts raw social channel IDs, and does not bulk-export all posts.
- HubSpot marketing attribution smoke check uses `get_marketing_campaign_attribution` to search bounded campaign/source fields, counts QO/QO Met/closed-won only with configured HubSpot stage IDs, and does not use generic QO totals as campaign attribution.
- HubSpot Friday review smoke check returns Hygiene Summary, Funnel Snapshot, optional warehouse metric follow-up SQL, Top Coaching Observations, Actions for Next Week, and Support Needed; blocks AE callers; enforces Kerren SG/MY and Sarah ID scope; and still returns hygiene/account coverage with `Confidence: needs-check` when QO/QO Met/deal stage config is missing.
- HubSpot manager-chase smoke check returns Manager draft only rows from `build_manager_chase_plan`, blocks AE callers, accepts selected Slack context only as summary/permalink, and does not tag reps, expose raw Slack transcripts, expose task/communication bodies, send external messages, or mutate HubSpot.
- HubSpot Friday review activity check counts only completed calls of at least 120 seconds as connected calls, counts warm activity from completed meetings with configured labels, and does not expose call bodies, meeting bodies, recordings, phone numbers, task/note/communication bodies, or attachments.
- Aircall MCP lists only `find_aircall_calls`, `resolve_aircall_call_for_coaching`, `transcribe_aircall_recording`, and `analyze_aircall_call_coaching` when Aircall is enabled.
- Aircall metadata smoke check uses `AIRCALL_API_ID` and `AIRCALL_API_TOKEN`, verifies `/v1/calls` is reachable, caps recent calls at 5, reports recording availability, and does not print phone numbers or raw recording URLs.
- Aircall transcription smoke check uses one selected numeric call ID with recording, requires `OPENAI_API_KEY`, defaults to `gpt-4o-transcribe-diarize`, caps audio at 25 MB / 60 minutes, deletes temporary audio, returns redacted bounded transcript fields only, and never mutates Aircall or HubSpot.
- Aircall coaching smoke check uses `analyze_aircall_call_coaching` for one selected numeric call ID, defaults to OpenAI `gpt-4o-transcribe-diarize` plus `gpt-5.5`, computes transcript/timing interaction metrics locally, returns Gong-inspired safe coaching JSON only, says audio-native tone was not checked, and never returns raw transcript/audio/recording URLs/phone numbers or claims Gong/ElevenLabs integration.
- HubSpot clean-lead check treats associated contact and verified decision maker as separate required fields; `hs_num_contacts_with_buying_roles` alone is reported as hygiene, not decision-maker coverage.
- HubSpot SG lead-enrichment smoke check confirms `build_singapore_lead_enrichment_plan` returns the requested gap buckets, reads phone-verification fields, treats manual Truecaller lookup as candidate evidence only, emits field-level rollup mismatch notes, and returns WhatsApp talking points without sending.
- HubSpot pre-demo game plan smoke check accepts selected scoped company IDs, company links, or exact company names, caps at 5 accounts, returns candidate company IDs instead of guessing ambiguous names, returns approved case-study matches when available, returns `pricing needed` and `case-study match needed` when missing, and does not expose raw task bodies or mutation tools.
- HubSpot account-context smoke check returns `company.c360_url` for verified customer accounts and names Customer 360 link context in the source.
- C360 sales-packet smoke check calls `GET /api/companies/{customer360_route_key_or_hubspot_company_id}/sales-packet` with `NURTUREANY_C360_INTERNAL_API_TOKEN`, expects HTTP 200 plus `status=ok`, and fails with only subsystem/reason such as `c360-sales-packet:http-401`; it must not print token values or raw auth bodies.
- HubSpot task smoke check returns safe sales-owned follow-up task summaries only, exposes the narrow preview-first task primitives, keeps generic `create_hubspot_task` / `append_hubspot_note` / `update_nurture_fields` disabled, and does not expose raw task body.
- HubSpot task-write smoke check confirms task creation needs `preview_hubspot_sales_task` plus exact `create task` or `confirm task`, reschedule needs `update task` or `confirm reminder`, completion needs `mark done` or `complete task`, and `run`, `ok`, `yes`, `+1`, and `^` are not HubSpot Task write approvals.
- HubSpot T-90 smoke check returns a primary answer object with known T-90 `contract_end_date` accounts and a separate missing `contract_end_date` classification bucket.
- HubSpot follow-up-status smoke check returns safe WhatsApp communication, note, and task evidence only and does not expose raw communication bodies, note bodies, task bodies, phone numbers, unmatched attendees, or mutation tools.
- HubSpot event-follow-up smoke check resolves Luma checked-in attendance, verifies event-specific Eazybe WhatsApp communications in HubSpot, marks generic WhatsApp as `needs_check`, and never exposes raw WhatsApp bodies, guest emails, phone numbers, or raw attendee lists.
- Indonesia event-registration fallback smoke check confirms `read_indonesia_event_registration_attendance` is available, restricted to `ID REV - LL & HHH EVENTS`, uses `Attend The Event` as manual attendance only when Luma check-in is empty or not used, and never exposes phone numbers, full emails, or raw registration exports.
- Google Slides deck-access smoke check confirms `read_google_slides_deck` is available, uses the `team@staffany.com` read-only Drive OAuth token, supports native Slides and Drive-hosted `.pptx` text extraction, never retains raw deck bytes, and never asks for "Anyone with the link" public sharing.
- Daily nurture automation is disabled pending refinement for the Jeremy daily-pack workflow. Health checks must not require a Jeremy daily pack, 09:00 daily nurture cron, noon daily nurture reminder, or `NURTUREANY_DAILY_RUNS_DIR`; `read_nurture_material_registry` remains read-only material context only.
- Eugene-owned WhatsApp Morning Blitz report crons are intended production crons. They are separate from the paused Jeremy daily nurture workflow and must stay active for SG/MY and Indonesia manager reporting.
- HubSpot Task reminder automation is separate from daily nurture: morning no-agent digest reads overdue/due-today/due-tomorrow incomplete HubSpot Tasks, EOD no-agent digest reads overdue/due-today incomplete HubSpot Tasks, both start with `NurtureAny automation:`, and HubSpot Task `hs_timestamp` remains the source of truth until `hs_task_status=COMPLETED`.
- HubSpot inbound monitor automation is optional and disabled unless `NURTUREANY_INBOUND_MONITOR_ENABLED` is truthy. It reads HubSpot Conversations through `audit_inbound_sla`, emits only exception rows starting with `NurtureAny automation:`, stores runtime-only cursor/dedupe state, and never mutates HubSpot or sends external messages.
- Operation ledger tools `record_nurtureany_operation_checkpoint` and `read_nurtureany_operation_ledger` are available for restart-safe Slack workflow continuation.
- Sales WhatsApp report primitives `build_sales_whatsapp_window_report`, `save_sales_whatsapp_window_report_schedule`, `run_sales_whatsapp_window_report_schedule`, and `post_generated_sales_report` are available for Singapore, Malaysia, and Indonesia. Delivery requires `NURTUREANY_REPORT_DELIVERY_CHANNEL_IDS`, generated report markdown, approval marker, idempotency key, and operation-ledger checkpoints; ad hoc reruns must not update the saved weekday schedule. The ID manager cron must run `nurtureany_sales_whatsapp_report_runner.py` as a no-agent local-delivery job; the runner posts through `post_generated_sales_report` with the `NurtureAny automation:` report prefix instead of relying on a free-form agent prompt.
- Reviewed lesson tools `record_nurtureany_lesson_candidate`, `list_nurtureany_lesson_candidates`, and `read_nurtureany_lesson_candidate` are available. They write/read runtime-only candidates, keep Honcho disabled, and do not change behavior before repo promotion.
- Eazybe approval-gated smoke check confirms `preview_eazybe_template_messages`, `send_approved_eazybe_messages`, and `check_eazybe_send_status` are available; sends require `approval_marker`, `templateName`, ordered `templateParams`, and phone-number redaction.
- HubSpot photo scan smoke check accepts Luma event candidates, correlates Drive photo timestamps to Luma event dates, auto-tags `nurture_event` only for one clear event-date match, and keeps HubSpot person/contact association blocked until uploader confirmation.
- A tiny target-account count query succeeds for each supported country.
- StaffAny BigQuery MCP lists only expected read-only tools.
- A tiny read-only C360 smoke query succeeds when C360 is enabled.
- A tiny revenue-metric schema smoke check can inspect `fct_sales_points`, `fct_deal_metrics_with_pilot_conversion`, `fct_mrr_movements`, and `fct_company_revenue_snapshot` without mutation or export.
- Revenue-metric prompt smoke checks use `build_sales_metric_actuals_query` and `fct_sales_points.qo_set` for direct qualified-opportunity pace, keep `new ARR` ambiguous until confirmed, and do not claim Rev planning targets are actuals.
- Direct QO prompt smoke checks, such as `what is Jeremy's QO in April`, plan owner/team scope resolution plus `build_sales_metric_actuals_query`; they do not plan `build_friday_sales_review` unless the prompt asks for Friday review or tactical pause context.
- Revenue funnel smoke checks use `build_hubspot_revenue_funnel_metrics`, created-date cohort, Sales Outbound/default outbound rules, new-business/renewal/signed-stage caveats, summary metrics, and deal audit rows.
- AE coaching smoke checks use `build_ae_coaching_audit`, return 1:1-sheet preview rows, keep call content metadata-only, interpret WhatsApp windows in each rep's local timezone from access policy or override, return local/UTC window fields, and do not mutate Sheets.
- Direct call-stat smoke checks use `summarize_sales_call_stats`, not AE coaching, return explicit `association_mode`, treat `>60s` as strict, use completed plus `>=120s` for the default connected-call guardrail, and do not count from capped `long_call_without_appointment_candidates`.
- Sales Navigator smoke checks use `prepare_sales_navigator_decision_maker_queue`, return manual handoff rows, include Exa/Lusha/Prospeo cost/credit status, and do not scrape LinkedIn or automate Sales Navigator.
- Friday review smoke checks may include a second StaffAny BigQuery QO aggregate after `build_friday_sales_review`, but the answer must label HubSpot hygiene separately from C360 BigQuery actuals.
- Near-me MCP lists only `resolve_known_area_for_near_me`, `build_near_me_outlet_matches_query`, `refresh_google_places_for_known_area`, `build_near_me_c360_customer_query`, and `merge_near_me_sources` when known-area near-me is enabled.
- Near-me smoke check resolves `Raffles Place` to `sg_raffles_place`, builds C360 SQL using `kraken_rds.Locations`, `analytics.dim_sections`, `analytics.dim_org_section`, and `analytics.fct_deal_org_company`, and does not include person GPS, clock records, or raw employee location sources.
- Near-me merge smoke check returns `c360_url` for every current-customer item with a resolvable Customer 360 route key; missing route keys keep the row visible with `Confidence: needs-check` and a missing-link caveat.
- Near-me Google Places smoke check uses `GOOGLE_PLACES_API_KEY`, `POST /v1/places:searchNearby`, `includedTypes=["restaurant"]`, and the minimal field mask. Google-only results remain live candidates.
- Near-me outlet-match smoke check reads BigQuery `analytics.nurtureany_near_me_outlet_matches` by `area_id`, supports multiple outlet rows per Company, and does not mutate HubSpot or BigQuery.
- Google Calendar MCP lists only `list_google_calendar_events` and `audit_google_calendar_meeting_quality` when Google Calendar is enabled.
- Google Calendar smoke check uses the `team@staffany.com` read-only OAuth token and returns bounded event metadata without attendee exports or event mutation tools.
- Google Calendar meeting-quality smoke check uses HubSpot `calendar_audit_seed`, scans the resolved AE calendar through `team@staffany.com`, matches attendee email hashes internally, and returns no raw attendee emails, descriptions, guest lists, conference links, phone numbers, or raw HubSpot bodies.
- Google Sheets MCP lists `preview_analysis_sheet_export` and `apply_analysis_sheet_export`. Preview does not call the Google Sheets API. Apply writes only sanitized rows to the configured shared workbook, upserts `Runs`, and rejects raw transcripts, phones, full emails, raw HubSpot bodies, or raw guest exports.
- Luma MCP lists only `list_luma_events`, `get_luma_event_match_keys`, and `get_luma_event_context` when Luma is enabled.
- Luma event-link smoke check confirms found/selected event output includes `<event.url|event.name>` plus date and event ID when `event.url` is present.
- Event-first Luma smoke check confirms `get_luma_event_match_keys(include_contact_pii=true)` and `find_target_accounts_by_luma_match_keys(include_contact_pii=true)` are available for Jan-E/event-operator account breakdowns, broad event questions do not page every HubSpot target account, matched contact PII appears only for scoped exact HubSpot contact-email matches, and attendee-record action packs report RSVP truth/action buckets without subtracting matched account count from RSVP count.
- Luma read-only smoke check succeeds when Luma is enabled, uses `LUMA_API_KEY`, and returns bounded event metadata.
- Luma event-tag smoke check can filter by exact Luma event tags such as `Jakarta` plus `HR Happy Hour` or `Singapore` plus `Sports`, with country used for broader account scope.
- Luma guest-context smoke check requires scoped HubSpot company IDs, caps guest reads, returns `has_more`/`truncated`, treats attendance as `checked_in_at` present, and does not expose unmatched attendee exports, raw registration answers, raw match-key lists, message bodies, or mutation tools.
- Exa MCP lists only `search_exa_people_candidates` when Exa is enabled.
- Exa smoke check returns `cost_report`, requires scoped HubSpot company IDs, uses `category: "people"`, and does not fetch profile contents or expose email/phone.
- Public research MCP lists only `research_public_company_signals` and `find_brand_parent_candidates` when Tavily is enabled.
- Target-account news brand fallback smoke check confirms unresolved brand/outlet names can call `find_brand_parent_candidates`, then must re-query scoped HubSpot target accounts before `research_public_company_signals`; `Eat 3 Bowls` should resolve via `The Better Kompany Pte Ltd` when that parent is in caller scope.
- Target Account News Scout skill is installed in the live profile and uses scoped HubSpot company identity before public research.
- Public research smoke blocks missing `TAVILY_API_KEY` before HTTP, requires scoped HubSpot company IDs, returns `cost_report`, and never mutates HubSpot.
- Lusha MCP lists only `search_lusha_decision_maker_candidates`, `search_lusha_candidates_by_linkedin_urls`, `reveal_lusha_contact_details`, and `get_lusha_credit_usage` when Lusha is enabled.
- Prospeo MCP lists only `search_prospeo_decision_maker_candidates`, `search_prospeo_candidates_by_linkedin_urls`, `reveal_prospeo_contact_details`, and `get_prospeo_credit_usage` when Prospeo is enabled.
- Lusha search and reveal smoke checks require scoped HubSpot company IDs before any paid/API call.
- Lusha usage smoke check returns `credit_report` and does not block the gateway when `/account/usage` is rate-limited.
- Honcho is disabled.

Healthy checks print nothing and exit 0.

## Commands

Run the source-packet verifier from the repo root:

```bash
/Applications/Codex.app/Contents/Resources/node scripts/verify-nurtureany-sales-bot.mjs
```

Run the live health check after config, MCP, token, or gateway changes:

```bash
apps/nurtureany-sales-bot/runtime/check-health.sh
```

For a different current-customer packet smoke account, override:

```bash
C360_SALES_PACKET_SMOKE_COMPANY_ID=<hubspot_company_id> apps/nurtureany-sales-bot/runtime/check-health.sh
```

Run the live profile drift audit after syncing repo packet files into the Hermes profile:

```bash
apps/nurtureany-sales-bot/runtime/audit-live-profile.sh
```

Run the redacted cloud doctor when the cloud service restarts, cron drifts, or live runtime looks suspicious:

```bash
apps/nurtureany-sales-bot/runtime/nurtureany-cloud-doctor.sh
```

Dry-run Slack access repair after an approved runtime access-policy change:

```bash
apps/nurtureany-sales-bot/runtime/scripts/nurtureany_slack_access_repair.py \
  --profile-env ~/.hermes/profiles/nurtureanysalesbot/.env \
  --expect-email jan-e@staffany.com
```

Only after the runtime policy already grants the role, apply the repair and run health:

```bash
apps/nurtureany-sales-bot/runtime/scripts/nurtureany_slack_access_repair.py \
  --profile-env ~/.hermes/profiles/nurtureanysalesbot/.env \
  --apply \
  --health-check ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-health.sh
```

Run the silent local cloud heartbeat after cron or cloud-doctor changes:

```bash
apps/nurtureany-sales-bot/runtime/check-cloud-heartbeat.sh
```

## Cron Pattern

Prefer Hermes `no_agent` cron for operational checks. Healthy runs should consume no model tokens and create no Slack noise.

Install profile-local scripts under `~/.hermes/profiles/nurtureanysalesbot/scripts`:

```bash
mkdir -p ~/.hermes/profiles/nurtureanysalesbot/scripts
mkdir -p ~/.hermes/profiles/nurtureanysalesbot/source
rsync -a --delete apps/nurtureany-sales-bot/ ~/.hermes/profiles/nurtureanysalesbot/source/nurtureany-sales-bot/
cp apps/nurtureany-sales-bot/runtime/check-health.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-health.sh
cp apps/nurtureany-sales-bot/runtime/check-cloud-heartbeat.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-cloud-heartbeat.sh
cp apps/nurtureany-sales-bot/runtime/audit-live-profile.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-audit-live-profile.sh
cp apps/nurtureany-sales-bot/runtime/check-slack-socket-health.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-slack-socket-health.sh
cp apps/nurtureany-sales-bot/runtime/nurtureany-cloud-doctor.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-cloud-doctor.sh
cp apps/nurtureany-sales-bot/runtime/scripts/nurtureany_slack_access_repair.py ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_slack_access_repair.py
cp apps/nurtureany-sales-bot/runtime/scripts/nurtureany_sales_task_reminders.py ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_sales_task_reminders.py
cp apps/nurtureany-sales-bot/runtime/scripts/nurtureany_sales_task_reminders_eod.py ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_sales_task_reminders_eod.py
cp apps/nurtureany-sales-bot/runtime/scripts/nurtureany_inbound_monitor.py ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_inbound_monitor.py
cp apps/nurtureany-sales-bot/runtime/scripts/nurtureany_sales_whatsapp_report_runner.py ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_sales_whatsapp_report_runner.py
chmod +x ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_slack_access_repair.py
chmod +x ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_inbound_monitor.py
chmod +x ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_sales_whatsapp_report_runner.py
hermes -p nurtureanysalesbot cron create "0 1 * * 1-5" \
  --name "nurtureanysalesbot health check" \
  --script nurtureanysalesbot-check-health.sh \
  --no-agent
hermes -p nurtureanysalesbot cron create "15 1 * * 1-5" \
  --name "nurtureanysalesbot live profile audit" \
  --script nurtureanysalesbot-audit-live-profile.sh \
  --no-agent
hermes -p nurtureanysalesbot cron create "*/15 * * * *" \
  --name "nurtureanysalesbot local cloud heartbeat" \
  --script nurtureanysalesbot-check-cloud-heartbeat.sh \
  --no-agent
hermes -p nurtureanysalesbot cron create "*/5 * * * *" \
  --name "nurtureanysalesbot Slack socket watchdog" \
  --script nurtureanysalesbot-check-slack-socket-health.sh \
  --no-agent
hermes -p nurtureanysalesbot cron create "0 1 * * 1-5" \
  --name "nurtureanysalesbot HubSpot task reminders" \
  --script nurtureany_sales_task_reminders.py \
  --deliver slack:#nurtureany-testing \
  --no-agent
hermes -p nurtureanysalesbot cron create "0 9 * * 1-5" \
  --name "nurtureanysalesbot HubSpot task EOD catch-up" \
  --script nurtureany_sales_task_reminders_eod.py \
  --deliver slack:#nurtureany-testing \
  --no-agent
hermes -p nurtureanysalesbot cron create "*/2 * * * *" \
  --name "nurtureanysalesbot HubSpot inbound monitor" \
  --script nurtureany_inbound_monitor.py \
  --deliver slack:#nurtureany-testing \
  --no-agent
```

Daily nurture is available as an on-demand workflow, not a required production cron. Eugene-owned WhatsApp Blitz is separate and intended. The runtime audit expects ten enabled recurring operational crons: health check, live profile audit, local cloud heartbeat, Slack socket watchdog, HubSpot task reminders, HubSpot task EOD catch-up, HubSpot inbound monitor, SG MY WhatsApp Morning Blitz Report, ID Morning WhatsApp Blitz Report, and ID WhatsApp Morning Blitz Report. The ID WhatsApp Morning Blitz Report cron is a no-agent local-delivery script job using `nurtureany_sales_whatsapp_report_runner.py`; the report delivery itself is bot-owned Slack posting through the saved schedule and operation ledger. Safe enabled one-shot report jobs are allowed and must not change the recurring cron count. The HubSpot inbound monitor is a read-only internal exception report to `#nurtureany-testing`; it must use `audit_inbound_sla`, never mutate HubSpot, and never send external messages. The saved WhatsApp report schedule lives in profile-runtime JSON and is called by deterministic primitives; it supports SG/MY defaults and explicit Indonesia report args, and does not remove or rename the existing WhatsApp Blitz cron records.

To enable the optional HubSpot-source inbound monitor after a prod dry run,
set `NURTUREANY_INBOUND_MONITOR_ENABLED=true`,
`NURTUREANY_INBOUND_MONITOR_INBOX_ID=<hubspot inbox id>`, and create a no-agent
cron whose Slack delivery matches `NURTUREANY_INBOUND_MONITOR_DELIVER_CHANNEL`:

```bash
hermes -p nurtureanysalesbot cron create "*/2 * * * *" \
  --name "nurtureanysalesbot HubSpot inbound monitor" \
  --script nurtureany_inbound_monitor.py \
  --deliver slack:#nurtureany-testing \
  --no-agent
```

The current Hermes CLI uses the deployment host timezone for cron scheduling and does not expose a `--timezone` flag.

Pause legacy event ROI jobs until they are rewritten for bot-safe delivery:

```bash
hermes -p nurtureanysalesbot cron pause event-roi-job1-daily-signup-update
hermes -p nurtureanysalesbot cron pause event-roi-job2-t3-wa-reminder-drafts
hermes -p nurtureanysalesbot cron pause event-roi-job3-fireside-ping-7pm
hermes -p nurtureanysalesbot cron pause event-roi-job4-fireside-summary-730pm
hermes -p nurtureanysalesbot cron pause event-roi-job5-attendance-excel-drafts
hermes -p nurtureanysalesbot cron pause event-roi-job6-hubspot-task-preview
hermes -p nurtureanysalesbot cron pause event-roi-job7-roi-report-day3
```

## Failure Behavior

On failure, print only the failing subsystem and next check. Do not print secrets, env values, raw logs, raw Slack messages, raw HubSpot rows, bulk PII, phone numbers, or contact exports.
