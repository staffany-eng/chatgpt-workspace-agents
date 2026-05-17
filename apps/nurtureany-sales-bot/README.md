# NurtureAny Sales Bot

Canonical Hermes app packet for StaffAny's sales nurture bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `nurtureanysalesbot`
- Surface: Slack mentions in sales pilot channels
- Model: Anthropic Claude Sonnet provider configured in the live profile
- Primary data source: HubSpot CRM
- Enrichment sources: HubSpot follow-up activity from WhatsApp communications, notes, tasks, and completed meeting logs, selected Aircall call metadata and recording transcription through OpenAI when configured, the read-only NurtureAny material registry Google Sheet for podcast, case study, event, speaker, venue, peer intro, salary benchmark, and fireside material, Drive/Slack event-photo source pointers with transient vision/OCR, Indonesia LL/HHH registration Sheet attendance fallback when Luma check-in is empty or not used, free public evidence tasks/review, Tavily public company/job-board research when explicitly requested, Rev planning definitions/targets, StaffAny C360 through read-only BigQuery with Customer 360 links, compact sales packets for current-client product/Payroll truth, and revenue-metric actuals, known-area near-me matching with BigQuery outlet matches plus Google Places live candidates when configured, read-only Google Calendar context and meeting-quality audit from `team@staffany.com` when configured, Luma event context when configured, Exa People Search public candidate discovery when configured, approval-gated Lusha decision-maker lookup when configured, approval-gated Prospeo paid-provider pilot lookup when configured, and approval-gated Eazybe template sending when configured
- V1 regions: Singapore, Malaysia, Indonesia
- V1 safety mode: review-first, no external message auto-send; scoped HubSpot Tasks use preview-first exact approval; V2 Eazybe sends require approved template payloads and `approval_marker`
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/nurtureanysalesbot/` on `nurtureany-sales-bot-prod`

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
- Phone verification: contact `nurtureany_phone_verification_status`, `nurtureany_phone_verified_at`, `nurtureany_phone_verified_by`, `nurtureany_phone_verification_source`, and `nurtureany_phone_verification_notes`; raw HubSpot phone fields are not exposed in default Slack output. Exception: selected Lusha or Prospeo reveal may show selected email/phone PII in internal Slack only after explicit reveal approval, `approval_marker`, and `reveal_phones=true` for phone reveal.
- Follow-up signal and task queue: HubSpot WhatsApp `communications`, notes, completed tasks, and existing incomplete HubSpot tasks associated to scoped companies, contacts, or deals. HubSpot Task `hs_timestamp` is the NurtureAny due/reminder source, and `hs_task_status=COMPLETED` is completion truth. Event follow-up uses Luma attendance to find matched scoped accounts, with the Indonesia Rev LL/HHH Google Sheet `Attend The Event` column as a manual attendance fallback when Luma check-in is empty or not used, then verifies event-specific Eazybe WhatsApp logs in HubSpot.

`current_tool_renewal_date`, Aircall recordings/transcripts, C360, Google Places, Google Calendar, Luma, the Indonesia event registration Sheet fallback, Tavily public research, Exa, Lusha, Prospeo, Slack, and public evidence are context/enrichment only unless a specific workflow says otherwise. Prospeo is an active paid-provider pilot adapter under Lusha-style approval/cost guardrails: scoped HubSpot company IDs, selected contacts only, explicit approval before reveal, credit reporting, no bulk export, and no HubSpot mutation. For near-me answers, C360 is the current-customer coverage layer, BigQuery `nurtureany_near_me_outlet_matches` is the curated outlet/account memory layer, and Google Places is live discovery only. For call review, HubSpot remains account and activity truth; Aircall is used only for selected call artifacts and bounded redacted transcription/coaching. Gong public coaching docs are design inspiration for the coaching rubric and output shape only; there is no Gong integration, credential, MCP, webhook, or source-of-truth role. ElevenLabs public voice docs are future/alternative technical evidence only; there is no ElevenLabs integration, credential, webhook, SIP/Twilio routing, or source-of-truth role in this packet.

T-90 renewal answers must show both buckets: known T-90 accounts where `contract_end_date` is inside the requested window, and scoped target accounts missing `contract_end_date` for classification. If no window is requested, use today through today plus 90 days.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled copy of the profile soul prompt. |
| `profile/config.template.yaml` | Non-secret profile config template and access policy. |
| `skills/nurtureany-sales-bot/` | Hermes skill and progressive-disclosure references. |
| `skills/nurtureany-sales-bot/references/reviewed-lessons.md` | Reviewed lesson-candidate and promotion contract for runtime learning. |
| `skills/target-account-news-scout/` | Add-on skill for scoped target-account news signals and manual-review outreach drafts. |
| `runtime/slack.md` | Slack gateway behavior, commands, and run gate. |
| `runtime/hubspot.md` | HubSpot API contract, fields, and write approval rules. |
| `runtime/aircall.md` | Read-only Aircall selected-call metadata, OpenAI transcription, and post-call coaching contract. |
| `runtime/mcp/aircall_nurtureany_server.py` | Aircall MCP adapter for safe call lookup, selected recording transcription, and selected call coaching. |
| `runtime/data/case-studies.json` | Approved public StaffAny case-study catalog for pre-demo name-drop matching. |
| `runtime/bigquery.md` | C360 read-only enrichment and revenue-metric actuals contract. |
| `runtime/google-calendar.md` | Read-only `team@staffany.com` Google Calendar event-context and meeting-quality audit contract. |
| `runtime/google-drive.md` | Read-only `team@staffany.com` Drive/Sheets contract for event photos and Indonesia registration attendance fallback. |
| `runtime/eazybe.md` | Approval-gated Eazybe Broadcast API contract for WhatsApp template previews, sends, and status checks. |
| `runtime/luma.md` | Luma read-only event, RSVP, and attendance-context contract. |
| `runtime/mcp/luma_nurtureany_server.py` | Luma read-only MCP adapter for scoped event-context lookup. |
| `runtime/near-me.md` | Known-area near-me flow with BigQuery outlet matches, C360 customers, and Google Places live refresh. |
| `runtime/mcp/near_me_nurtureany_server.py` | Read-only known-area near-me MCP adapter and merge logic. |
| `runtime/sql/near-me-outlet-matches.sql` | BigQuery provisioning SQL for the near-me outlet match memory table. |
| `runtime/public-research.md` | Tavily public company research, shared signal extraction, manual-check source rules, and cost-reporting contract. |
| `runtime/mcp/public_research_nurtureany_server.py` | Read-only Tavily public company research MCP adapter for scoped HubSpot companies. |
| `runtime/exa.md` | Exa People Search public candidate-discovery and cost-reporting contract. |
| `runtime/lusha.md` | Cost-controlled Lusha lookup, selected-PII, and credit-reporting contract. |
| `runtime/prospeo.md` | Cost-controlled Prospeo paid-provider pilot lookup, selected-PII, and credit-reporting contract. |
| `runtime/health-checks.md` | Operational checks and expected silence. |
| `runtime/check-health.sh` | Silent no-agent health check for live runtime wiring. |
| `runtime/check-cloud-heartbeat.sh` | Silent no-agent local VM heartbeat for gateway, cron, and cloud-doctor health. |
| `runtime/check-slack-socket-health.sh` | Silent no-agent Slack Socket Mode watchdog for managed gateway restart. |
| `runtime/scripts/nurtureany_sales_task_reminders.py` | No-agent HubSpot Task reminder digest for overdue, due today, and due tomorrow tasks. |
| `runtime/scripts/nurtureany_sales_task_reminders_eod.py` | No-agent EOD HubSpot Task reminder digest for overdue and due today tasks. |
| `runtime/audit-live-profile.sh` | Live profile drift audit against the source packet. |
| `runtime/nurtureany-cloud-doctor.sh` | Redacted cloud doctor for service state, cron state, MCP counts, drift, ledger, and daily-run persistence. |
| `tests/regression-cases.md` | Manual/eval regression cases for app behavior. |
| `tests/prompt-evals.json` | Machine-readable static, tool-trace, answer-contract, and live-smoke prompt eval specs. |

## Product Scope

NurtureAny helps AEs and sales managers work the HubSpot target-account list:

- AEs ask for their own target accounts and nurture queue.
- Managers ask for team queues, missing direct contacts, renewal risk, post-demo nurture, overdue nurture work, existing sales follow-up tasks, and event follow-up status.
- Direct QO count or pace prompts use `build_sales_metric_actuals_query` and StaffAny BigQuery actuals from `fct_sales_points.qo_set`; Friday review stays HubSpot hygiene first and may add warehouse QO actuals as a second source.
- Selected call review can use `find_aircall_calls` to locate recent Aircall call artifacts, `resolve_aircall_call_for_coaching` to resolve safe call hints to one numeric Aircall ID, `transcribe_aircall_recording` as the lower-level selected recording transcription primitive, and `analyze_aircall_call_coaching` for the composed manager-quality post-call coach summary. The adapter deletes downloaded audio before returning, caps audio at 25 MB / 60 minutes, computes transcript/timing interaction metrics locally, and returns safe coaching JSON without raw transcript/audio/recording URLs/phone numbers.
- The bot ranks accounts, identifies enrichment gaps, builds the SG lead-enrichment pre-work plan before WhatsApp nurturing, answers known-area near-me customer/prospect walk-in prompts, adds C360 revenue/calendar/event context when relevant, scans Drive/Slack event photos into a source-pointer people layer, generates free public search tasks, reviews public evidence, runs Tavily public company/job-board research only when explicitly requested, searches Exa for public people candidates when approved, searches Lusha or Prospeo for selected decision-maker candidates when approved, drafts nurture messages, and previews HubSpot write-backs.
- The bot can run a bounded stand-up/down accountability inspector for explicitly configured public Slack channels such as `#team-rev-ps-syncup` (`C013N5XL7EV`). This is Slack-only, plan-first, and returns safe per-person status/permalinks without raw note bodies, Slack posting, HubSpot mutation, user-token fallback, or Slack-connector fallback.
- The Target Account News Scout skill can turn scoped HubSpot target accounts into recent public-news angles and send-ready manual-review drafts. It must resolve the account inside NurtureAny scope before public research and never auto-sends outreach.
- The SG lead-enrichment workflow uses `build_singapore_lead_enrichment_plan` for fixed AE account lists or selected SG HubSpot companies. It closes associated-contact, verified decision-maker, champion/influencer, usable-contact, and verified-phone gaps; returns provider-waterfall policy and writeback previews only; optimizes for capped-effective cost per usable AE handoff; treats Truecaller as manual lookup/callability evidence; and does not auto-send WhatsApp. If a user explicitly asks to reveal a personal/mobile number, route that as a separate approval-gated Lusha or Prospeo reveal flow, not as SG lead-enrichment output.
- The Jeremy daily nurture workflow is not an approved runtime workflow yet. Do not install Jeremy daily nurture or reminder cron, and do not advertise it as a ready Slack command until the workflow is refined and confirmed. Eugene-owned WhatsApp Morning Blitz report crons are separate intended production crons for SG/MY and Indonesia manager reporting.
- Existing HubSpot WhatsApp communications, notes, and sales follow-up tasks remain follow-up signals. For event questions, NurtureAny recomputes status from Luma checked-in attendance, or the Indonesia Rev LL/HHH registration Sheet `Attend The Event` fallback when Luma check-in is empty or not used, plus event-specific Eazybe WhatsApp communications in HubSpot; generic post-event WhatsApp is `needs_check`. New HubSpot Tasks use the narrow task primitives only: preview first, duplicate check, then exact approval (`create task` / `confirm task`, `update task` / `confirm reminder`, or `mark done` / `complete task`). Generic HubSpot notes and nurture-field write tools remain disabled.

NurtureAny never auto-sends WhatsApp, email, LinkedIn, or sequence messages. Eazybe sends are V2 approval-gated only: preview first, then send selected message IDs with `approval_marker`.

## Access Model

Slack user email is identity only. Access is granted by explicit NurtureAny policy, with HubSpot owners as the canonical roster source. Classified sales reps map `slack_email` to `hubspot_owner_email`, then to `hubspot_owner_id`; unclassified HubSpot owners are blocked even if HubSpot has an owner record.

| Role | Slack email | Scope |
| --- | --- | --- |
| Overall admin | `eugene@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin | `kaiyi@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin alias | `kai.yi@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin alias | `leekai.yi@staffany.com` | Singapore, Malaysia, Indonesia |
| SG/MY manager | `kerren.fong@staffany.com` | Singapore, Malaysia team view plus preview-first exact-approval HubSpot Task primitives |
| Indonesia manager | `sarah@staffany.com`, `sarah.ayutania@staffany.com` | Indonesia team view plus preview-first exact-approval HubSpot Task primitives |
| Partnerships viewer | Explicit `partnerships_viewers` policy entry | Country-scoped read-only team target-account and selected account context; no HubSpot Task writes, manager coaching audits, Friday review, or revenue metrics |
| Regional event operator | Explicit `event_operators` policy entry | Read-only in-country event sourcing through `find_event_sourcing_target_accounts` and Luma RSVP match-key account resolution through `get_luma_event_match_keys(include_contact_pii=true)` plus `find_target_accounts_by_luma_match_keys`; matched scoped HubSpot contacts may include email/phone/mobile in internal event output only; no manager/admin tools, HubSpot writes, coaching, revenue metrics, generic account context, unmatched attendee export, raw registration answers, or message bodies |
| AE | Explicit `sales_reps` policy entry | Own HubSpot target accounts only |

The full rep roster is runtime-only through `NURTUREANY_ACCESS_POLICY_PATH`; `runtime/access-policy.template.json` contains fake example reps only. Known Slack or Google email variants must be declared with `alias_for` or top-level `aliases`, then canonicalized before role lookup. Permissions are not inferred from Slack titles, channel membership, display names, or a bare HubSpot owner lookup.

## Runtime Secrets

Production dotenv hydration uses one Secret Manager secret:

```text
projects/1093387803298/secrets/nurtureany-sales-bot-prod-env
```

The secret is in project `staffany-warehouse`, uses dotenv format, and is labeled `app=nurtureany-sales-bot`, `env=prod`, `format=dotenv`. It contains NurtureAny runtime keys only; do not copy secret values into this repo.

To grant a teammate access, bind the one secret:

```bash
gcloud secrets add-iam-policy-binding nurtureany-sales-bot-prod-env \
  --project=staffany-warehouse \
  --member='user:TEAMMATE_EMAIL' \
  --role='roles/secretmanager.secretAccessor'
```

To hydrate the prod VM Hermes profile from prod secrets, run on `nurtureany-sales-bot-prod`:

```bash
mkdir -p ~/.hermes/profiles/nurtureanysalesbot
gcloud secrets versions access latest \
  --project=staffany-warehouse \
  --secret=nurtureany-sales-bot-prod-env \
  > ~/.hermes/profiles/nurtureanysalesbot/.env
chmod 600 ~/.hermes/profiles/nurtureanysalesbot/.env
```

Do not run a Mac-local NurtureAny Slack gateway with the production Slack app. Local NurtureAny tests should use source-packet verification, dry-run tools, or a separate isolated Slack app/profile.

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `nurtureanysalesbot` profile.
3. Copy `profile/SOUL.md` into the profile's `SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Copy `runtime/access-policy.template.json` outside the repo, classify real HubSpot owners there, and set `NURTUREANY_ACCESS_POLICY_PATH`.
6. Copy NurtureAny skill directories under `skills/` into the profile skills directory.
7. Set profile `.env` from Secret Manager only, normally `staffany-warehouse/nurtureany-sales-bot-prod-env`; do not commit or inline model-provider, Slack, HubSpot, Aircall, OpenAI, Luma, Lusha, Prospeo, Exa, Tavily, BigQuery, Google Places, or C360 credentials.
8. Configure Slack gateway, Slack inbound alert channel IDs with `NURTUREANY_INBOUND_ALERT_CHANNEL_IDS` (production starts with `CM1A8UE6Q` for `#team-rev-bd-inbound-leads`), HubSpot MCP/API adapter, optional Aircall MCP with `AIRCALL_API_ID`, `AIRCALL_API_TOKEN`, `OPENAI_API_KEY`, optional call-coach defaults `NURTUREANY_CALL_COACH_PROVIDER=openai`, `NURTUREANY_CALL_COACH_TRANSCRIBE_MODEL=gpt-4o-transcribe-diarize`, `NURTUREANY_CALL_COACH_REASONING_MODEL=gpt-5.5`, `NURTUREANY_CALL_COACH_ELEVENLABS_ENABLED=false`, StaffAny BigQuery MCP, optional near-me adapter with `GOOGLE_PLACES_API_KEY`, `NURTUREANY_KNOWN_AREAS_FILE`, `NURTUREANY_OUTLET_MATCHES_TABLE`, and optional Customer 360 URL template overrides, optional Google Calendar adapter with read-only `team@staffany.com` OAuth files, Google Drive material registry with `NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID`, optional Luma adapter, optional Tavily public research MCP with `TAVILY_API_KEY`, optional Exa MCP with `EXA_API_KEY`, optional Lusha MCP with `LUSHA_API_KEY`, optional Prospeo MCP with `PROSPEO_API_KEY`, optional Eazybe MCP with `EAZYBE_API_KEY` plus `EAZYBE_BROADCAST_API_URL`, `NURTUREANY_DAILY_RUNS_DIR`, `NURTUREANY_OPERATION_LEDGER_DIR`, optional `NURTUREANY_LESSON_CANDIDATES_DIR`, optional `NURTUREANY_REPORT_SCHEDULE_DIR`, and report delivery allowlist `NURTUREANY_REPORT_DELIVERY_CHANNEL_IDS`.
9. Run health checks and regression cases before adding sales channels.

When syncing the prod profile runtime from this repo, preserve the runtime-only `runtime/access-policy.json` file or restore it from a profile backup after replacing `runtime/`. The repo contains only `runtime/access-policy.template.json`; deleting the live policy breaks Slack allowlist health.

To repair Slack access drift after an approved runtime policy change, run the no-agent repair script from the live profile. It resolves approved policy emails with the bot token, updates only `SLACK_ALLOWED_USERS`, restarts the gateway, and can run the health check:

```bash
~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureany_slack_access_repair.py \
  --profile-env ~/.hermes/profiles/nurtureanysalesbot/.env \
  --expect-email jan-e@staffany.com
```

Add `--apply --health-check ~/.hermes/profiles/nurtureanysalesbot/scripts/nurtureanysalesbot-check-health.sh` only after the runtime policy already contains the approved `event_operators` entry. The repair script must not be used to infer or grant new access from Slack profile data.

## Canonical Source Rule

The live Hermes profile may accumulate local state and runtime learning. Treat that as unreviewed drift until the specific useful change is copied back here and committed.

Reviewed learning uses `record_nurtureany_lesson_candidate`, `list_nurtureany_lesson_candidates`, and `read_nurtureany_lesson_candidate`. These tools store runtime-only candidates; they do not change behavior until a human promotes the lesson into the repo packet, tests it, merges it, deploys it, and verifies prod. Honcho stays disabled.
