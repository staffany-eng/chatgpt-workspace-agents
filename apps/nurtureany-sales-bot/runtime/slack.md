# Slack Runtime

NurtureAny's first runtime surface is Slack mention usage in sales pilot channels.

## Required Behavior

- Mention-only in configured channels for V1.
- First tool-backed requests are plan-first unless the quick-autorun gate is fully satisfied.
- The bot asks for `run` before the first confirmed execution unless recent configured-channel context makes the intent obvious and the work is exact, read-only or preview/draft-only, expected under 60 seconds, and bounded to a small number of tool calls.
- Same-thread `run` replies after a bot plan must route without re-mentioning the bot. The gateway should treat a thread whose parent message mentioned `@NurtureAny` as a mentioned thread even after restart or cache loss.
- For top-level mentions, the gateway must register the effective thread root (`event.thread_ts` when present, otherwise the parent message `ts`) as the mentioned thread. Do not rely only on Slack's `event.thread_ts`, because top-level app mentions may omit it and then plain `run` replies can be dropped.
- Slack status reactions are enabled for NurtureAny so users can see processing start while long tool-backed work is running.
- Local source-packet hydration is allowed and required before the first preflight when the prompt involves NurtureAny sales workflow terms, drafting, pre-demo, demo, post-demo, event follow-up, Friday review, coaching, inbound/routing, AI/data readiness, or operating rhythm. The intent gate blocks HubSpot, C360, BigQuery, Google Calendar, Google Drive, Luma, Exa, Lusha, Prospeo, public research, broad Slack lookup, and other app-backed or external sources before `run` unless quick-autorun applies; it must not block local skill/reference loading.
- `read_recent_slack_intent_context` is the recent-channel Slack lookup allowed before preflight for quick-autorun routing. It must use `SLACK_BOT_TOKEN`, configured channels only, at most 10 recent messages or 30 minutes, and safe summaries/permalinks only. Do not persist raw transcripts. If the bot lacks scope or channel membership, do not use Kai Yi's user token or the Slack connector; fall back to the normal preflight with a clear caveat.
- `get_current_slack_thread_context` and `get_selected_slack_thread_context` may also run before `run` when the user's first request explicitly points to the current thread or a selected Slack permalink and thread context is needed to interpret the request or write the preflight. This pre-run thread read must stay read-only, use `SLACK_BOT_TOKEN`, read one selected public or configured thread-context channel only, cap at 50 messages, and return safe summaries/permalinks only. It may not execute HubSpot, C360, BigQuery, Calendar, Drive, Luma, Exa, Lusha, Prospeo, public research, paid, write, or send tools before `run` unless the full quick-autorun gate is satisfied.
- After `run`, or for a clear bounded same-thread continuation after a delivered result, `get_current_slack_thread_context` and `get_selected_slack_thread_context` may read one selected public or configured thread-context Slack thread, capped at 50 messages, and return safe summaries/permalinks only. These tools use the bot token and do not depend on Kai Yi being a channel member. If a public source channel returns `not_in_channel`, the adapter may call `conversations.join` with the bot token and retry. Set `NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS=all` for public source-channel permalinks outside the configured channel IDs. These tools must not be used for broad channel history, private-channel bypass, workspace search, user listing, reactions, pins, arbitrary posting, raw transcript export, Slack connector fallback, or any user-token fallback.
- `audit_standup_down_accountability` is a separate plan-first Slack-only inspector for configured public channels such as `#team-rev-ps-syncup` (`C013N5XL7EV`). It requires `run`, reads one local date from channels in `NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS`, builds the expected roster as active Slack channel members intersected with prior stand-up/down participants, and returns safe per-person status/permalinks only. For relative "today" prompts, pass literal `date="today"` and let the tool resolve it in `Asia/Singapore`. It must not be used through quick-autorun, arbitrary channel search, private channels, raw note-body export, Slack posting, HubSpot mutation, user-token fallback, or Slack connector fallback.
- Slack capability answers must be precise: NurtureAny can read Hermes-injected current thread context and can call bounded bot-token Slack read tools for selected public or configured thread-context channels; it cannot browse arbitrary Slack history, search all channels, list users broadly, pin/react, or post arbitrary Slack messages through exposed tools.
- If local NurtureAny references define a term, the preflight must use that definition instead of asking the user. `KNS`, `K/N/S`, and `K N S` mean `Knowledge, Network, Support`; only caveat that an external slide/doc may refine the wording after `run`.
- If a request includes a Google Slides URL or asks to use a deck, first response is still plan-only and must name `read_google_slides_deck` as the first source check after `run`. Do not plan from the URL alone. If deck access is blocked, ask for viewer access to `team@staffany.com` or an approved StaffAny group; do not ask for "Anyone with the link" public sharing.
- Smoke/test/eval prompts follow the same quick-autorun gate. Words like `smoke`, `test`, `compact`, `keep output compact`, `quick`, or `just check` do not bypass approval by themselves.
- CRO readiness prompts that only ask what NurtureAny can help leaders do may answer from the source packet without tools, but must stay role-correct and end with Source, Scope, Confidence, and Caveat.
- CRO readiness prompts for Kerren, Eugene, and Sarah must treat them as revenue leaders, not AEs. Never write `For each AE (Kerren, Eugene, Sarah)`. Capability-only readiness must use `Confidence: needs-check`, not `verified`, and must not use Markdown tables.
- CRO prompts that ask for a live sample, current account recommendations, this-week account findings, or owner-specific queue rows are tool-backed and must use the intent gate before HubSpot/C360/Luma/Calendar/Drive/public tools. Exact bounded live samples may auto-run only when the quick-autorun criteria are fully satisfied.
- Bounded live samples and smoke tests should plan `list_team_target_accounts` or `list_my_target_accounts` with exact owner/country/query/limit filters, then `get_account_context` and optional `draft_nurture_message` for selected scoped company IDs. Do not plan `score_nurture_accounts` unless the user explicitly asks for a ranked queue.
- Account-background and `get account context for <account>` are tool-backed requests; first mention must plan only and must not resolve the company until `run` unless the account identity is exact and quick-autorun is fully satisfied.
- Clear same-thread corrections, fixes, and reruns after a delivered result are continuation work when scope is bounded.
- After a final answer, bare same-thread acknowledgements like `ok`, `done`, `yes`, and `thanks` close the thread silently unless they include a new request.
- Do not run a post-answer acceptance workflow: do not mark answered data-question threads as action needed, ask users to confirm yes/ok/done, or send reminders waiting for explicit acceptance. The mark-as-done / action-needed pattern is only for explicit task workflows with a real assignee and completion state.
- A `run` after a gateway interruption, shutdown warning, or missing post-`run` tool result must execute the confirmed plan again; do not answer from a stale "already ran" assumption. For long reads or side-effect preview/send steps, use `record_nurtureany_operation_checkpoint` before the step and `read_nurtureany_operation_ledger` after restart when an operation id is available.
- Common same-thread approval nudges after a preflight count as `run` when there is no scope change: bot mention only, `^`, `+1`, `yes`, `ok`, `go`, or `please proceed`.
- HubSpot Task writes have stricter approval than `run`: create requires exact `create task` or `confirm task`; reschedule requires exact `update task` or `confirm reminder`; completion requires exact `mark done` or `complete task`. `run`, `ok`, `yes`, `+1`, and `^` do not approve HubSpot Task writes.
- Materially expanded scope, source-class changes, write intent, or expensive/ambiguous follow-ups require a revised plan and `run`. A later same-thread request for personal/mobile numbers is a new source-class plan; its following `run` must execute that revised plan, not recap the earlier HubSpot-only answer.
- T-90 renewal answers must display both the known T-90 `contract_end_date` bucket and the missing `contract_end_date` classification bucket. Do not bury missing-date accounts in the caveat.
- Repeated account-name follow-up requests should reuse bounded sources or run bounded target-account `query` lookup. Do not switch to broad queue scoring as a direct lookup.
- Account-background and `get account context` answers should render the slim packet returned by `get_account_context` and should not add `Additional context`, contacts, last activity, open tasks, deals, or IC-BANT unless explicitly requested.
- Follow-up coverage answers must name the calendars checked. For a scoped HubSpot account, include the account owner's email calendar ID when calling Google Calendar; if it is inaccessible to `team@staffany.com`, say that instead of saying no follow-up.
- Calendar meeting-quality audit requests must first resolve the scoped HubSpot account, then fetch `get_account_context`, pass `company.calendar_audit_seed` to `audit_google_calendar_meeting_quality`, and only then summarize whether the right people are on the meeting.
- For past matched Calendar meetings, if the audit tool returns `hubspot_followup_check.required=true`, call `check_account_followup_status` from the event end time before answering follow-up hygiene.
- Calendar audit answers are safe summaries only: account, owner/calendar checked, matching events, right-people status, HubSpot-linked names/roles, missing sales-standard evidence, follow-up hygiene, source, scope, confidence, and caveat. Never expose raw attendee emails, guest lists, descriptions, conference links, phone numbers, or raw HubSpot bodies.
- Exa People Search requests must show the estimated dollar-cost scope before execution and include `cost_report` after execution.
- Tavily public research requests must be explicitly scoped to HubSpot companies, show the selected `research_mode`, and include `cost_report` plus `will_mutate_hubspot=false` after execution.
- Target-account news-scout requests must resolve the account through the caller's NurtureAny HubSpot scope before public research. After `run`, or after a quick-autorun decision for an exact scoped light check, try direct scoped HubSpot target-account lookup first; when a brand/outlet is not found, run `find_brand_parent_candidates` for parent/group identity evidence only, then re-query scoped HubSpot target accounts with the returned candidate names before blocking. Use `target-account-news-scout` for recent public signals only after a scoped account resolves, and return a manual-review draft only; do not auto-send outreach.
- Target-account news-scout first responses must use the standard five-line preflight only unless quick-autorun is fully satisfied. Do not add checklists, prerequisites, or extra headings before `run`.
- Campaign-effectiveness questions such as `did the Salary Benchmark campaign lead to QO or closed-won` must plan for HubSpot campaign lookup, campaign assets, `get_marketing_campaign_attribution`, and configured HubSpot deal-stage checks. Do not answer from campaign metadata alone, and do not use generic QO totals as campaign attribution.
- Direct QO count or pace requests such as `what's my QO this month` should plan HubSpot owner/team scope plus C360 BigQuery actuals via `build_sales_metric_actuals_query`; they are not Friday review prompts unless the user asks for Friday, tactical-pause, hygiene, or coaching context.
- HubSpot revenue-funnel prompts should plan `build_hubspot_revenue_funnel_metrics` with created-date cohort, owner/country/team filters, Sales Outbound/all-outbound choice, New/Existing Business, headcount, industry, signed-deal rules, and manual-correction caveats.
- AE coaching audit prompts should plan `build_ae_coaching_audit`; the final must return 1:1-sheet preview rows only and say no Sheet mutation or call-content read occurred.
- Direct call-stat prompts like `connected calls over 1 min between 2pm and 5pm` should plan `resolve_nurture_scope` when needed, `resolve_sales_owners` for scoped owner IDs, then `summarize_sales_call_stats`. Do not plan AE coaching, Friday review, priority-account coverage, or capped `long_call_without_appointment_candidates` for this narrow metric class. Final answers must show `association_mode`, Source, Scope, Confidence, and Caveat.
- Direct owner-level prompts like `how many WhatsApp messages did Jeremy send today` should plan `count_owner_whatsapp_sent_today` with owner email, scoped countries, and date. Do not plan Friday review, priority-account coverage, or AE coaching audit for this narrow count.
- Stand-up/down accountability prompts like `inspect sales rep, BD Ops and marketing stand up/down accountability in #team-rev-ps-syncup today` should plan `audit_standup_down_accountability` with channel `C013N5XL7EV`, `date="today"` for relative today or the explicit `YYYY-MM-DD` if supplied, `timezone="Asia/Singapore"`, and default `roster_lookback_days=30`. First response is plan-only and requires `run`; after execution, report complete/missing stand-up/missing stand-down/missing-both counts plus safe per-person rows. Do not paste raw Slack note bodies, infer HR employment truth, or use the Slack connector/user token.
- Exact-owner WhatsApp KNS timing prompts like `how many WhatsApp messages did Jeremy send 9:30-10:30 and flag no KNS` should plan `audit_owner_whatsapp_kns_window`. This tool may read HubSpot WhatsApp bodies internally for KNS flags but must never return raw bodies. Timezone comes from the runtime access policy or explicit override; Slack and HubSpot owner records only identify the rep. If timezone is missing, report `needs-check` and do not claim zero messages.
- AE coaching WhatsApp timing prompts must interpret requested windows in each rep's local timezone. Pass user-specified windows such as `9:30-10:30am` as `whatsapp_window_start_local="09:30"` and `whatsapp_window_end_local="10:30"`, rely on the access-policy `timezone` for each rep, and report exact `first_message_local`, `in_window_message_count`, and `late_by_minutes`. If a user corrects a rep's location/timezone, rerun or remap through `timezone_override_by_owner_email`; do not answer with "no new tool calls needed" unless the tool output already contains the corrected timezone fields.
- Do not emit `Marked :question: action needed` or acceptance reminders for AE coaching audits unless the user explicitly asks for completion tracking.
- Sales Navigator prompts should plan `prepare_sales_navigator_decision_maker_queue`; the final must state it is a manual handoff queue with no LinkedIn scraping or automated Sales Navigator browser action.
- Personal/mobile-number requests are approval-gated Lusha or Prospeo reveal requests, not a blanket "raw phone numbers are impossible" block. First plan: resolve the scoped HubSpot company/contact, check existing safe phone-verification status, then search Lusha or Prospeo candidates. Search results show availability/candidate context only. If the user selects contact IDs/candidates and explicitly approves reveal, call `reveal_lusha_contact_details` or `reveal_prospeo_contact_details` with `approval_marker` and `reveal_phones=true`; the final internal Slack answer may show the selected raw phone number(s) returned by the approved provider plus `credit_report`. Do not show raw HubSpot phone fields by default, bulk-export numbers, reveal unselected contacts, or send WhatsApp.
- SG lead-enrichment prompts should plan `build_singapore_lead_enrichment_plan`. Use it for fixed AE account lists, any selected Singapore HubSpot company, weak contact coverage, missing decision maker, missing champion/influencer, missing verified phone, Truecaller/manual callability checks, or pre-WhatsApp readiness. First response remains plan-only unless quick-autorun is fully satisfied for one exact bounded read-only sample. After `run`, report bucket counts, priority accounts, next source, provider-waterfall policy, field-level HubSpot mismatch notes, handoff notes, and draft-only KNS WhatsApp readiness. The source ladder is HubSpot -> HubSpot notes/tasks/history -> Tavily public company/job-board research -> Exa people candidates -> controlled Lusha + Prospeo paid-provider pilot -> approved reveal -> manual Truecaller/call outcome -> HubSpot preview. Do not expose raw HubSpot phone fields, call Lusha/Prospeo reveal from the SG plan, run automated Truecaller lookup, mutate HubSpot, or send WhatsApp.
- Campaign-effectiveness questions that ask whether a campaign led to QO, QO Met, closed-won, pipeline, or revenue must plan by name for `list_marketing_campaigns`, `get_campaign_assets`, and `get_marketing_campaign_attribution`. On the first Slack mention, this is plan-only: do not call HubSpot, C360, BigQuery, or any other data-source tool before `run`. Do not answer from campaign metadata, social metrics, or generic QO totals.
- After `get_marketing_campaign_attribution`, read `answer.outcome_summary` first. Report QO, QO Met, and closed-won counts from that summary before any detailed contact/company samples; if the result is `needs-check`, still show the visible counts as partial instead of saying deal outcomes were not read.
- Campaign/social answers must use checked/not-checked wording. A social-only run must include the exact sentence "QO / closed-won attribution was not checked in this run", not say that no QO/conversion evidence exists.
- Inbound SLA audit prompts should plan for `audit_inbound_sla`. After `run`, an approved rerun, or a same-thread correction with clear scope, call `audit_inbound_sla`; do not answer from a manually computed final table. If the current Slack thread/channel is part of the audit, collect only safe alert metadata: alert timestamp, source, owner tagged/ack time, first customer touch time, outcome time, assigned owner, backup owner, status, outcome, any HubSpot thread/contact/company IDs, and safe lead context such as contact name, company name, role, email domain, or a short context summary. Treat elapsed minutes `<=` the SLA target as pass. If no safe HubSpot IDs are available, timestamp collisions are duplicate candidates only; keep duplicate groups `needs-check`. Final per-alert rows must include `Context:` from `lead_context`; if unavailable, say context is missing and HubSpot match is needed. Do not paste raw Slack transcripts, phone numbers, or raw HubSpot bodies into HubSpot or the final answer.
- Inbound thread replies should use this operating format when recommending or auditing owner updates: `Owner: <name> | Status: acknowledged / called / reassigned / set / blocked | Next step: <action> | ETA: <time>`.
- Friday review requests should plan HubSpot hygiene first with `build_friday_sales_review`, then run returned `warehouse_metric_followups` through `staffany_bigquery.execute_sql_readonly` when QO actuals are needed.
- Manager chase requests should plan HubSpot priority-account coverage and selected-thread Slack context summary only. After `run`, call `build_manager_chase_plan` with the manager/admin caller email, owner/account filters, a short selected Slack blocker summary, and the thread permalink. Output manager drafts only; do not tag reps, send external messages, or mutate HubSpot.
- Luma guest or attendance requests must check HubSpot scope first, then return bounded RSVP/attendance context without raw attendee exports.
- Post-event follow-up requests must use `check_event_followup_status` when the event is named or needs Luma resolution, then use HubSpot/Eazybe event-specific WhatsApp communications, notes, and tasks for status. Generic post-event WhatsApp is `needs_check`, not clean follow-up.
- Daily nurture automation is disabled pending refinement for the Jeremy daily-pack workflow. Do not install a scheduled 09:00 Jeremy daily nurture cron, scheduled noon Jeremy daily nurture reminder cron, or advertise a ready Jeremy daily-pack workflow. Eugene-owned WhatsApp Morning Blitz report crons are separate intended production crons. HubSpot Task reminder digests are separate no-agent automation that read incomplete HubSpot Tasks by `hs_timestamp` until `hs_task_status=COMPLETED`.
- WhatsApp send flow is approval-gated only: call `preview_eazybe_template_messages` for selected message IDs, then `send_approved_eazybe_messages` only after Jeremy provides `approval_marker`. No free-form WhatsApp sends and no auto-blast.
- Luma event requests should pass exact Luma event tags when the prompt implies them, for example `event_tags=["Jakarta", "Appreciation Afternoon"]` for `StaffAny Appreciation Afternoon (JKT)` or `event_tags=["Singapore", "Sports"]` for the screenshot-style Sports event. Use country as broad account scope, not as the event filter when exact tags are known.
- Broad event-wide Luma questions must use event-first matching instead of paging every HubSpot target account: find event, extract safe match keys, search HubSpot scoped candidates, then fetch Luma context for those candidates only.
- For Indonesia LL/HHH event follow-up where Luma returns zero checked-in attendees or check-in was not tracked, use the `ID REV - LL & HHH EVENTS` Google Sheet fallback through `read_indonesia_event_registration_attendance`. Do not match Luma RSVP/no-show keys as attended when `checked_in_count=0` for a past event. Treat `Attend The Event` as manual attendance, match attended company/domain keys back to scoped HubSpot target accounts through `find_target_accounts_by_luma_match_keys`, then check HubSpot follow-up. Do not call `list_team_target_accounts` or delegate the matching flow. Do not expose phone numbers, full emails, raw registration rows, or raw attendee exports.
- When Slack output says a Luma event was found or selected, include the clickable event link as `<event.url|event.name>` whenever `event.url` is present, followed by date and event ID.
- Near-me prompts should plan for known-area snapping, BigQuery outlet-match lookup, Google Places live restaurant refresh, C360 BigQuery current-customer query, and merge/ranking. Ask for `run` before tool execution because this is multi-source work.
- Near-me answers must show C360 current customers even when no BigQuery outlet match exists, link every current customer name to returned `c360_url` when available, and mark Google-only restaurants as live candidates.
- Direct QO count or pace prompts with owner/team/date scope should plan for revenue metrics, not Friday review. Examples such as `what is Jeremy's QO in April` or `what's my QO this month` should resolve the owner/team scope, inspect `fct_sales_points`, and query `qo_set` through StaffAny BigQuery after `run`.
- Friday review prompts can include QO actuals only as a second step after `build_friday_sales_review`; keep HubSpot hygiene and C360 BigQuery actuals as separate source classes in the answer.
- Pre-demo game plan requests are selected-account only. If the prompt or same thread has scoped HubSpot company IDs, company links, or exact company names, plan for those selected accounts only. If the request includes or points to a Slack pre-meeting source thread, pass that permalink to `build_pre_demo_game_plans` as `source_slack_thread_url` and show it as `Source thread`. The preflight must not promise public/news/LinkedIn/social research unless the user explicitly supplied snippets or separately approved a public-evidence workflow. If a company name is ambiguous, return scoped candidate company IDs and ask the user to pick before execution.
- Ad hoc photo match requests are allowed in configured pilot channels when a user uploads an image and tags `@NurtureAny`.
- For photo match requests, read the current Slack message/thread, attachment metadata, uploader, channel, timestamp, permalink, and short text hints. Download the Slack image only transiently using `files:read`, run LLM vision/OCR for clues, then discard the raw image.
- Use `propose_photo_people_matches` for the people layer and require uploader/human confirmation before HubSpot association or follow-up preview.
- After confirmation, use `plan_event_photo_followup` to preview the HubSpot note and WhatsApp follow-up task. No WhatsApp auto-send in V1.
- For `@NurtureAny scan recent photos`, call `list_drive_folder_images` for the Google Drive `all-random` folder `1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-`, display Slack-export uploaders by Slack display name when available, call `list_luma_events` for the Drive photo date window, then `scan_drive_event_photos` with the Luma events, then `extract_drive_image_clues` in bounded batches before `propose_photo_people_matches`; set `luma_event_auto_tag=true` only when the user explicitly scoped the scan to a selected event or exact event tags such as tomorrow's HHH. Generic scans and account-visit photos must keep same-date Luma matches as `needs-check` candidates so Loco-style visits are not mis-tagged; Luma date matching may auto-tag the event context only, never the HubSpot person/contact; ask the original uploader to identify or confirm every person, grouping prompts by uploader when possible; do not scan local machine photo folders. If Drive auth/tooling or vision extraction is missing, return `Confidence: blocked` for that missing prerequisite. If Luma is unavailable, continue with Drive/OCR and mark event correlation as `needs-check`.

## Commands

AE commands:

- `@NurtureAny my 150`
- `@NurtureAny my target accounts`
- `@NurtureAny my nurture queue`
- `@NurtureAny preview Eazybe messages msg-1 msg-2`
- `@NurtureAny accounts missing direct contact`
- `@NurtureAny build SG lead enrichment for my accounts`
- `@NurtureAny which SG accounts still need decision maker, champion, and verified phone before WhatsApp`
- `@NurtureAny build game plan for company 123456789`
- `@NurtureAny build game plan for Noci Bakehouse`
- `@NurtureAny does Tang Tea House have the right people on the meeting?`
- `@NurtureAny audit this calendar follow-up against HubSpot contacts`
- `@NurtureAny check if Jeremy's meeting has a decision maker invited`
- `@NurtureAny scan recent photos`
- Upload an event photo and tag `@NurtureAny this is Jane from Shake Shack`
- `@NurtureAny I am here at Raffles Place, who can I say hi to?`
- `@NurtureAny customers or prospects around me at VivoCity`

Manager commands:

- `@NurtureAny team queue`
- `@NurtureAny show ID team accounts with no direct contact`
- `@NurtureAny post-demo nurture queue`
- `@NurtureAny renewal risk queue this month`
- `@NurtureAny audit inbound SLA from this Slack thread`
- `@NurtureAny Friday review for SG this week`
- `@NurtureAny which target accounts attended yesterday's Luma event`
- `@NurtureAny which target accounts attended our last Jakarta HHH and did we follow up`
- `@NurtureAny which target accounts attended our last Bali HHH and did we follow up`
- `@NurtureAny which target accounts attended StaffAny Appreciation Afternoon (JKT)?`
- `@NurtureAny build pre-demo game plans for these 3 HubSpot company links`
- `@NurtureAny build pre-demo game plans for Noci Bakehouse, Bali Beans, and Kopi House`
- `@NurtureAny build manager chase drafts for Jeremy from this thread`
- `@NurtureAny build Singapore lead enrichment plan for Jeremy's fixed account list`

## Scope Routing

Use Slack user email as the caller identity.

- AE calls require an explicit `sales_reps` policy entry that maps Slack email to HubSpot owner email, then restrict to owned HubSpot target accounts.
- Manager calls require explicit email allowlist and are team read-only.
- Unclassified HubSpot owners are blocked even if Slack email matches a HubSpot owner record.
- Country filters come from the manager scope, not from channel name.
- Known Slack or Google email variants must be configured as access-policy aliases. Never infer `slack_user_email` from a display name.

If Slack cannot provide the user email, return `Confidence: blocked` and ask for the missing identity mapping. If the Slack email is not classified, ask for runtime access policy classification.

## Output Contract

Preflight plain Slack text:

Interpreted question: <question>
Plan: I will check <sources>, using <owner/team/country filters>.
Estimate: <1-2 min | 3-5 min | may exceed 5 min>
Caveat: <material limitation>
Reply "run" to start, or tell me what to change.

Campaign-effectiveness preflight plain Slack text for QO / closed-won questions:

Interpreted question: <campaign effectiveness question>
Plan: I will check list_marketing_campaigns to find the HubSpot campaign, get_campaign_assets to inspect campaign assets, and get_marketing_campaign_attribution to search source-field touched contacts/companies plus configured QO/QO Met/closed-won deal-stage outcomes, using <owner/team/country filters>.
Estimate: 2-3 min
Caveat: Campaign metadata and assets do not prove QO or closed-won attribution; deal outcomes are verified only when HubSpot stage IDs are configured.
Reply "run" to start, or tell me what to change.

Final plain Slack text:

Answer: <result or blocked reason>
Checked: <specific source/tool class actually checked, when marketing/social attribution can be confused>
Not checked: <expected outcome classes not verified in this run, when relevant>
Next check: <separate attribution/QO check, when relevant>
Source: <HubSpot/C360/Google Calendar/Luma/tool used>
Source thread: <Slack permalink when supplied>
Scope: <owner/team/country/time filters>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

For readiness briefs with no live data, use plain labeled lines rather than tables and set:

Source: NurtureAny source packet / local references
Scope: capability brief only; no live HubSpot data queried
Confidence: needs-check
Caveat: Run a scoped HubSpot/C360/Luma/Calendar check before using it as a live account plan.

For manager chase final answers, put copy-ready manager draft lines first, then evidence, deadline, fallback action, source, scope, confidence, and caveat. Say Manager draft only. Do not tag reps, expose raw Slack transcripts, expose HubSpot task/communication bodies, send external messages, or mutate HubSpot.

## Slack Scopes

The Slack app needs enough access to receive mentions, identify users, and reply in configured channels. Do not request broad private-channel enumeration for V1 unless a concrete pilot channel requires it and the security owner approves.

Quick-intent context reads additionally require bot-token access to `conversations.history`, `conversations.replies`, and `chat.getPermalink` for configured channels only. The runtime should validate this read path through `read_recent_slack_intent_context` and report missing scope or channel membership as a blocker instead of falling back to user tokens or the Slack connector.

Explicit selected-thread reads before or after `run` also use bot-token `conversations.info`, `conversations.replies`, `conversations.join`, and `chat.getPermalink` through `get_current_slack_thread_context` or `get_selected_slack_thread_context`, capped at 50 messages with safe summaries/permalinks only. Set `NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS=all` when selected source threads may come from any public channel; this covers public channels only. Without that flag, set `NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS` for allowed source channels beyond the live mention channels; otherwise the adapter falls back to `NURTUREANY_SLACK_INTENT_CHANNEL_IDS` / `SLACK_HOME_CHANNEL`. If the bot is not already in a public source channel, it may join that public channel and retry the read. This is still an explicit public-channel guard, not workspace search or private-channel enumeration.

Stand-up/down accountability additionally requires bot-token access to `conversations.info`, `conversations.history`, `conversations.members`, `conversations.join`, `users.info`, and `chat.getPermalink` for configured public channels in `NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS`. Default production channel: `C013N5XL7EV` (`#team-rev-ps-syncup`). The tool may join a configured public channel before reading; it still does not browse arbitrary Slack history, read private channels, return raw note bodies, or post messages.

Photo matching additionally needs `files:read` for attached images in configured pilot channels only. Store Slack photo source pointers (`channel_id`, `message_ts`, `file_id`, permalink), not raw image copies. If the same photo later appears in Drive, reconcile by source pointer, filename/hash, and source timestamp before creating a duplicate HubSpot photo record.
