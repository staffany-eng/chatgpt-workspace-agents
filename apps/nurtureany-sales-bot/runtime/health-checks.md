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
- HubSpot `company_country` options include `Singapore`, `Malaysia`, and `Indonesia`.
- HubSpot MCP lists `list_sales_followup_tasks`, `generate_free_search_tasks`, and `review_public_enrichment_evidence` in addition to the existing queue, gap, draft, and preview tools.
- HubSpot task smoke check returns safe sales-owned follow-up task summaries only and does not expose task body or mutation tools.
- A tiny target-account count query succeeds for each supported country.
- StaffAny BigQuery MCP lists only expected read-only tools.
- A tiny read-only C360 smoke query succeeds when C360 is enabled.
- Google Calendar MCP lists only `list_google_calendar_events` when Google Calendar is enabled.
- Google Calendar smoke check uses the `team@staffany.com` read-only OAuth token and returns bounded event metadata without attendee exports or event mutation tools.
- Luma MCP lists only `list_luma_events` and `get_luma_event_context` when Luma is enabled.
- Luma read-only smoke check succeeds when Luma is enabled, uses `LUMA_API_KEY`, and returns bounded event metadata.
- Luma event-tag smoke check can filter by exact Luma event tags such as `Jakarta` plus `HR Happy Hour` or `Singapore` plus `Sports`, with country used for broader account scope.
- Luma event-link smoke check confirms found/selected event Slack answers include `<event.url|event.name>` when the Luma event URL is returned.
- Luma guest-context smoke check requires scoped HubSpot company IDs, caps guest reads, returns `has_more`/`truncated`, treats attendance as `checked_in_at` present, and does not expose raw attendee exports, phone numbers, full emails, registration answers, or mutation tools.
- Exa MCP lists only `search_exa_people_candidates` when Exa is enabled.
- Exa smoke check returns `cost_report`, requires scoped HubSpot company IDs, uses `category: "people"`, and does not fetch profile contents or expose email/phone.
- Lusha MCP lists only `search_lusha_decision_maker_candidates`, `reveal_lusha_contact_details`, and `get_lusha_credit_usage` when Lusha is enabled.
- Lusha search and reveal smoke checks require scoped HubSpot company IDs before any paid/API call.
- Lusha usage smoke check returns `credit_report` and does not block the gateway when `/account/usage` is rate-limited.
- Honcho is disabled.

Healthy checks print nothing and exit 0.

## Failure Behavior

On failure, print only the failing subsystem and next check. Do not print secrets, env values, raw logs, raw Slack messages, raw HubSpot rows, bulk PII, phone numbers, or contact exports.
