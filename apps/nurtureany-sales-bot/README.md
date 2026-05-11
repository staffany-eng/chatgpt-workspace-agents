# NurtureAny Sales Bot

Canonical Hermes app packet for StaffAny's sales nurture bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `nurtureanysalesbot`
- Surface: Slack mentions in sales pilot channels
- Model: Anthropic Claude Sonnet provider configured in the live profile
- Primary data source: HubSpot CRM
- Enrichment sources: HubSpot follow-up activity from WhatsApp communications, notes, tasks, and completed meeting logs, Drive/Slack event-photo source pointers with transient vision/OCR, Indonesia LL/HHH registration Sheet attendance fallback when Luma check-in is empty or not used, free public evidence tasks/review, Tavily public company research when explicitly requested, Rev planning definitions/targets, StaffAny C360 through read-only BigQuery with Customer 360 links, compact sales packets for current-client product/Payroll truth, and revenue-metric actuals, known-area near-me matching with BigQuery outlet matches plus Google Places live candidates when configured, read-only Google Calendar context and meeting-quality audit from `team@staffany.com` when configured, Luma event context when configured, Exa People Search public candidate discovery when configured, and approval-gated Lusha decision-maker lookup when configured
- V1 regions: Singapore, Malaysia, Indonesia
- V1 safety mode: review-first, no external message auto-send
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/nurtureanysalesbot/`

## Relationship To Da Ta Hermz

NurtureAny is a separate Hermes profile from Da Ta Hermz.

| Bot | Hermes profile | Responsibility |
| --- | --- | --- |
| Da Ta Hermz | `staffanydatabot` | General StaffAny data bot and BigQuery/C360 analysis workflows. |
| NurtureAny | `nurtureanysalesbot` | Sales nurture workflow for HubSpot target accounts, AE queues, manager queues, and approved HubSpot write-back previews. |

The two profiles may share model authentication credentials during the pilot. They must not share Slack app tokens, HubSpot tool policy, SOUL prompts, skills, runtime safety rules, or business state.

For production, prefer a dedicated service credential for NurtureAny model auth instead of copied pilot auth from Da Ta Hermz.

## Durable Data Sources

When NurtureAny is asked what sources it is using, it must answer with this field map:

- Target accounts: HubSpot company `hs_is_target_account`.
- Owner scope: HubSpot owners API plus HubSpot company `hubspot_owner_id`.
- Region scope: HubSpot company `company_country`.
- Renewal timing and T-90 windows: HubSpot company `contract_end_date`; explicit date-window requests must pass `start_date` and `end_date`.
- Current tools: HubSpot company `current_tools`.
- Verified decision-maker coverage: HubSpot company `hs_num_decision_makers` or contact `hs_buying_role=DECISION_MAKER`; buying-role contact count is hygiene context only.
- Follow-up signal: HubSpot WhatsApp `communications`, notes, completed tasks, and existing incomplete HubSpot tasks associated to scoped companies, contacts, or deals. Event follow-up uses Luma attendance to find matched scoped accounts, with the Indonesia Rev LL/HHH Google Sheet `Attend The Event` column as a manual attendance fallback when Luma check-in is empty or not used, then verifies event-specific Eazybe WhatsApp logs in HubSpot.

`current_tool_renewal_date`, C360, Google Places, Google Calendar, Luma, the Indonesia event registration Sheet fallback, Tavily public research, Exa, Lusha, Slack, and public evidence are context/enrichment only unless a specific workflow says otherwise. For near-me answers, C360 is the current-customer coverage layer, BigQuery `nurtureany_near_me_outlet_matches` is the curated outlet/account memory layer, and Google Places is live discovery only.

T-90 renewal answers must show both buckets: known T-90 accounts where `contract_end_date` is inside the requested window, and scoped target accounts missing `contract_end_date` for classification. If no window is requested, use today through today plus 90 days.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled copy of the profile soul prompt. |
| `profile/config.template.yaml` | Non-secret profile config template and access policy. |
| `skills/nurtureany-sales-bot/` | Hermes skill and progressive-disclosure references. |
| `runtime/slack.md` | Slack gateway behavior, commands, and run gate. |
| `runtime/hubspot.md` | HubSpot API contract, fields, and write approval rules. |
| `runtime/data/case-studies.json` | Approved public StaffAny case-study catalog for pre-demo name-drop matching. |
| `runtime/bigquery.md` | C360 read-only enrichment and revenue-metric actuals contract. |
| `runtime/google-calendar.md` | Read-only `team@staffany.com` Google Calendar event-context and meeting-quality audit contract. |
| `runtime/google-drive.md` | Read-only `team@staffany.com` Drive/Sheets contract for event photos and Indonesia registration attendance fallback. |
| `runtime/luma.md` | Luma read-only event, RSVP, and attendance-context contract. |
| `runtime/mcp/luma_nurtureany_server.py` | Luma read-only MCP adapter for scoped event-context lookup. |
| `runtime/near-me.md` | Known-area near-me flow with BigQuery outlet matches, C360 customers, and Google Places live refresh. |
| `runtime/mcp/near_me_nurtureany_server.py` | Read-only known-area near-me MCP adapter and merge logic. |
| `runtime/sql/near-me-outlet-matches.sql` | BigQuery provisioning SQL for the near-me outlet match memory table. |
| `runtime/public-research.md` | Tavily public company research, shared signal extraction, manual-check source rules, and cost-reporting contract. |
| `runtime/mcp/public_research_nurtureany_server.py` | Read-only Tavily public company research MCP adapter for scoped HubSpot companies. |
| `runtime/exa.md` | Exa People Search public candidate-discovery and cost-reporting contract. |
| `runtime/lusha.md` | Cost-controlled Lusha lookup, selected-PII, and credit-reporting contract. |
| `runtime/health-checks.md` | Operational checks and expected silence. |
| `runtime/check-health.sh` | Silent no-agent health check for live runtime wiring. |
| `runtime/audit-live-profile.sh` | Live profile drift audit against the source packet. |
| `tests/regression-cases.md` | Manual/eval regression cases for app behavior. |

## Product Scope

NurtureAny helps AEs and sales managers work the HubSpot target-account list:

- AEs ask for their own target accounts and nurture queue.
- Managers ask for team queues, missing direct contacts, renewal risk, post-demo nurture, overdue nurture work, existing sales follow-up tasks, and event follow-up status.
- Direct QO count or pace prompts use `build_sales_metric_actuals_query` and StaffAny BigQuery actuals from `fct_sales_points.qo_set`; Friday review stays HubSpot hygiene first and may add warehouse QO actuals as a second source.
- The bot ranks accounts, identifies enrichment gaps, answers known-area near-me customer/prospect walk-in prompts, adds C360 revenue/calendar/event context when relevant, scans Drive/Slack event photos into a source-pointer people layer, generates free public search tasks, reviews public evidence, runs Tavily public company research only when explicitly requested, searches Exa for public people candidates when approved, searches Lusha for selected decision-maker candidates when approved, drafts nurture messages, and previews HubSpot write-backs.
- Existing HubSpot WhatsApp communications, notes, and sales follow-up tasks are read-only follow-up signals. For event questions, NurtureAny recomputes status from Luma checked-in attendance, or the Indonesia Rev LL/HHH registration Sheet `Attend The Event` fallback when Luma check-in is empty or not used, plus event-specific Eazybe WhatsApp communications in HubSpot; generic post-event WhatsApp is `needs_check`. New HubSpot tasks, notes, and field updates happen only after explicit approval.

V1 does not send WhatsApp, email, LinkedIn, or sequence messages.

## Access Model

Slack user email is identity only. Access is granted by explicit NurtureAny policy, with HubSpot owners as the canonical roster source. Classified sales reps map `slack_email` to `hubspot_owner_email`, then to `hubspot_owner_id`; unclassified HubSpot owners are blocked even if HubSpot has an owner record.

| Role | Slack email | Scope |
| --- | --- | --- |
| Overall admin | `eugene@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin | `kaiyi@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin alias | `kai.yi@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin alias | `leekai.yi@staffany.com` | Singapore, Malaysia, Indonesia |
| SG/MY manager | `kerren.fong@staffany.com` | Singapore, Malaysia team view only |
| Indonesia manager | `sarah@staffany.com`, `sarah.ayutania@staffany.com` | Indonesia team view only |
| AE | Explicit `sales_reps` policy entry | Own HubSpot target accounts only |

The full rep roster is runtime-only through `NURTUREANY_ACCESS_POLICY_PATH`; `runtime/access-policy.template.json` contains fake example reps only. Known Slack or Google email variants must be declared with `alias_for` or top-level `aliases`, then canonicalized before role lookup. Permissions are not inferred from Slack titles, channel membership, display names, or a bare HubSpot owner lookup.

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `nurtureanysalesbot` profile.
3. Copy `profile/SOUL.md` into the profile's `SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Copy `runtime/access-policy.template.json` outside the repo, classify real HubSpot owners there, and set `NURTUREANY_ACCESS_POLICY_PATH`.
6. Copy `skills/nurtureany-sales-bot/` into the profile skills directory.
7. Set profile `.env` from Secret Manager values only; do not commit or inline model-provider or Lusha credentials.
8. Configure Slack gateway, HubSpot MCP/API adapter, StaffAny BigQuery MCP, optional near-me adapter with `GOOGLE_PLACES_API_KEY`, `NURTUREANY_KNOWN_AREAS_FILE`, `NURTUREANY_OUTLET_MATCHES_TABLE`, and optional Customer 360 URL template overrides, optional Google Calendar adapter with read-only `team@staffany.com` OAuth files, optional Luma adapter, optional Tavily public research MCP with `TAVILY_API_KEY`, optional Exa MCP with `EXA_API_KEY`, and optional Lusha MCP with `LUSHA_API_KEY`.
9. Run health checks and regression cases before adding sales channels.

## Canonical Source Rule

The live Hermes profile may accumulate local state and runtime learning. Treat that as unreviewed drift until the specific useful change is copied back here and committed.
