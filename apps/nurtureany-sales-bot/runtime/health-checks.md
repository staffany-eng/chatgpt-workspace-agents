# Health Checks

NurtureAny needs deterministic runtime checks because prompt correctness does not guarantee connector scopes, HubSpot fields, or gateway restarts.

## Expected Checks

- Hermes gateway service for `nurtureanysalesbot` is active.
- Secret redaction remains enabled.
- Model route is pinned to native Anthropic Sonnet: `model.provider=anthropic`, `model.default=claude-sonnet-4-6`.
- Slack gateway can receive mentions and identify caller email.
- `NURTUREANY_ACCESS_POLICY_PATH` points to a runtime-only policy file when sales reps are enabled; the source template has fake example reps only.
- HubSpot owner lookup works for configured admins/managers and classified sales reps.
- HubSpot MCP lists `audit_hubspot_owner_roster`, and non-admin roster audit requests return `Confidence: blocked`.
- HubSpot company property metadata includes `hs_is_target_account`, `hubspot_owner_id`, and `company_country`.
- HubSpot company property metadata includes durable NurtureAny fields `contract_end_date` and `current_tools`; `current_tool_renewal_date` is present only as secondary context.
- HubSpot `company_country` options include `Singapore`, `Malaysia`, and `Indonesia`.
- HubSpot MCP lists inbound Conversations, Marketing Campaigns, campaign social effectiveness, marketing campaign attribution, `audit_priority_account_coverage`, `build_sales_metric_actuals_query`, `build_friday_sales_review`, `build_pre_demo_game_plans`, `list_sales_followup_tasks`, `check_account_followup_status`, `check_event_followup_status`, `generate_free_search_tasks`, and `review_public_enrichment_evidence` in addition to the existing queue, gap, draft, and preview tools.
- HubSpot campaign social-effectiveness smoke check uses `get_campaign_social_effectiveness`, reports aggregate `SOCIAL_BROADCAST` clicks separately from pipeline proof, redacts raw social channel IDs, and does not bulk-export all posts.
- HubSpot marketing attribution smoke check uses `get_marketing_campaign_attribution` to search bounded campaign/source fields, counts QO/QO Met/closed-won only with configured HubSpot stage IDs, and does not use generic QO totals as campaign attribution.
- HubSpot Friday review smoke check returns Hygiene Summary, Funnel Snapshot, optional warehouse metric follow-up SQL, Top Coaching Observations, Actions for Next Week, and Support Needed; blocks AE callers; enforces Kerren SG/MY and Sarah ID scope; and still returns hygiene/account coverage with `Confidence: needs-check` when QO/QO Met/deal stage config is missing.
- HubSpot Friday review activity check counts only completed calls of at least 120 seconds as connected calls, counts warm activity from completed meetings with configured labels, and does not expose call bodies, meeting bodies, recordings, phone numbers, task/note/communication bodies, or attachments.
- HubSpot clean-lead check treats associated contact and verified decision maker as separate required fields; `hs_num_contacts_with_buying_roles` alone is reported as hygiene, not decision-maker coverage.
- HubSpot pre-demo game plan smoke check accepts selected scoped company IDs, company links, or exact company names, caps at 5 accounts, returns candidate company IDs instead of guessing ambiguous names, returns approved case-study matches when available, returns `pricing needed` and `case-study match needed` when missing, and does not expose raw task bodies or mutation tools.
- HubSpot account-context smoke check returns `company.c360_url` for verified customer accounts and names Customer 360 link context in the source.
- C360 sales-packet smoke check calls `GET /api/companies/{customer360_route_key_or_hubspot_company_id}/sales-packet` with `NURTUREANY_C360_INTERNAL_API_TOKEN`, expects HTTP 200 plus `status=ok`, and fails with only subsystem/reason such as `c360-sales-packet:http-401`; it must not print token values or raw auth bodies.
- HubSpot task smoke check returns safe sales-owned follow-up task summaries only and does not expose task body or mutation tools.
- HubSpot T-90 smoke check returns a primary answer object with known T-90 `contract_end_date` accounts and a separate missing `contract_end_date` classification bucket.
- HubSpot follow-up-status smoke check returns safe WhatsApp communication, note, and task evidence only and does not expose raw communication bodies, note bodies, task bodies, phone numbers, unmatched attendees, or mutation tools.
- HubSpot event-follow-up smoke check resolves Luma checked-in attendance, verifies event-specific Eazybe WhatsApp communications in HubSpot, marks generic WhatsApp as `needs_check`, and never exposes raw WhatsApp bodies, guest emails, phone numbers, or raw attendee lists.
- Indonesia event-registration fallback smoke check confirms `read_indonesia_event_registration_attendance` is available, restricted to `ID REV - LL & HHH EVENTS`, uses `Attend The Event` as manual attendance only when Luma check-in is empty or not used, and never exposes phone numbers, full emails, or raw registration exports.
- HubSpot photo scan smoke check accepts Luma event candidates, correlates Drive photo timestamps to Luma event dates, auto-tags `nurture_event` only for one clear event-date match, and keeps HubSpot person/contact association blocked until uploader confirmation.
- A tiny target-account count query succeeds for each supported country.
- StaffAny BigQuery MCP lists only expected read-only tools.
- A tiny read-only C360 smoke query succeeds when C360 is enabled.
- A tiny revenue-metric schema smoke check can inspect `fct_sales_points`, `fct_deal_metrics_with_pilot_conversion`, `fct_mrr_movements`, and `fct_company_revenue_snapshot` without mutation or export.
- Revenue-metric prompt smoke checks use `build_sales_metric_actuals_query` and `fct_sales_points.qo_set` for direct qualified-opportunity pace, keep `new ARR` ambiguous until confirmed, and do not claim Rev planning targets are actuals.
- Direct QO prompt smoke checks, such as `what is Jeremy's QO in April`, plan owner/team scope resolution plus `build_sales_metric_actuals_query`; they do not plan `build_friday_sales_review` unless the prompt asks for Friday review or tactical pause context.
- Friday review smoke checks may include a second StaffAny BigQuery QO aggregate after `build_friday_sales_review`, but the answer must label HubSpot hygiene separately from C360 BigQuery actuals.
- Near-me MCP lists only `resolve_known_area_for_near_me`, `build_near_me_outlet_matches_query`, `refresh_google_places_for_known_area`, `build_near_me_c360_customer_query`, and `merge_near_me_sources` when known-area near-me is enabled.
- Near-me smoke check resolves `Raffles Place` to `sg_raffles_place`, builds C360 SQL using `kraken_rds.Locations`, `analytics.dim_sections`, `analytics.dim_org_section`, and `analytics.fct_deal_org_company`, and does not include person GPS, clock records, or raw employee location sources.
- Near-me merge smoke check returns `c360_url` for every current-customer item with a resolvable Customer 360 route key; missing route keys keep the row visible with `Confidence: needs-check` and a missing-link caveat.
- Near-me Google Places smoke check uses `GOOGLE_PLACES_API_KEY`, `POST /v1/places:searchNearby`, `includedTypes=["restaurant"]`, and the minimal field mask. Google-only results remain live candidates.
- Near-me outlet-match smoke check reads BigQuery `analytics.nurtureany_near_me_outlet_matches` by `area_id`, supports multiple outlet rows per Company, and does not mutate HubSpot or BigQuery.
- Google Calendar MCP lists only `list_google_calendar_events` and `audit_google_calendar_meeting_quality` when Google Calendar is enabled.
- Google Calendar smoke check uses the `team@staffany.com` read-only OAuth token and returns bounded event metadata without attendee exports or event mutation tools.
- Google Calendar meeting-quality smoke check uses HubSpot `calendar_audit_seed`, scans the resolved AE calendar through `team@staffany.com`, matches attendee email hashes internally, and returns no raw attendee emails, descriptions, guest lists, conference links, phone numbers, or raw HubSpot bodies.
- Luma MCP lists only `list_luma_events`, `get_luma_event_match_keys`, and `get_luma_event_context` when Luma is enabled.
- Luma event-link smoke check confirms found/selected event output includes `<event.url|event.name>` plus date and event ID when `event.url` is present.
- Event-first Luma smoke check confirms `get_luma_event_match_keys` and `find_target_accounts_by_luma_match_keys` are available, and broad event questions do not page every HubSpot target account.
- Luma read-only smoke check succeeds when Luma is enabled, uses `LUMA_API_KEY`, and returns bounded event metadata.
- Luma event-tag smoke check can filter by exact Luma event tags such as `Jakarta` plus `HR Happy Hour` or `Singapore` plus `Sports`, with country used for broader account scope.
- Luma guest-context smoke check requires scoped HubSpot company IDs, caps guest reads, returns `has_more`/`truncated`, treats attendance as `checked_in_at` present, and does not expose raw attendee exports, phone numbers, full emails, registration answers, or mutation tools.
- Exa MCP lists only `search_exa_people_candidates` when Exa is enabled.
- Exa smoke check returns `cost_report`, requires scoped HubSpot company IDs, uses `category: "people"`, and does not fetch profile contents or expose email/phone.
- Lusha MCP lists only `search_lusha_decision_maker_candidates`, `reveal_lusha_contact_details`, and `get_lusha_credit_usage` when Lusha is enabled.
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

Run the live profile drift audit after syncing repo packet files into the Hermes profile:

```bash
apps/nurtureany-sales-bot/runtime/audit-live-profile.sh
```

## Cron Pattern

Prefer Hermes `no_agent` cron for operational checks. Healthy runs should consume no model tokens and create no Slack noise.

Install profile-local scripts under `~/.hermes/profiles/nurtureanysalesbot/scripts`:

```bash
mkdir -p ~/.hermes/profiles/nurtureanysalesbot/scripts
mkdir -p ~/.hermes/profiles/nurtureanysalesbot/source
rsync -a --delete apps/nurtureany-sales-bot/ ~/.hermes/profiles/nurtureanysalesbot/source/nurtureany-sales-bot/
cp apps/nurtureany-sales-bot/runtime/check-health.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-health.sh
cp apps/nurtureany-sales-bot/runtime/audit-live-profile.sh ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-audit-live-profile.sh
hermes -p nurtureanysalesbot cron create "0 1 * * 1-5" \
  --name "nurtureanysalesbot health check" \
  --script nurtureanysalesbot-check-health.sh \
  --no-agent
hermes -p nurtureanysalesbot cron create "15 1 * * 1-5" \
  --name "nurtureanysalesbot live profile audit" \
  --script nurtureanysalesbot-audit-live-profile.sh \
  --no-agent
```

## Failure Behavior

On failure, print only the failing subsystem and next check. Do not print secrets, env values, raw logs, raw Slack messages, raw HubSpot rows, bulk PII, phone numbers, or contact exports.
