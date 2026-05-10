# NurtureAny Regression Cases

Use these cases to validate the skill and runtime behavior before enabling a sales channel.

## AE Queue

Prompt:

```text
@NurtureAny my 150
```

Expected behavior:

- First response is plan-only.
- Uses HubSpot target accounts after `run`.
- Requires an explicit `sales_reps` runtime access policy entry.
- Filters to `hs_is_target_account=true`, supported countries, and the requesting AE's `hubspot_owner_id`.
- Returns ranked accounts only from the AE's own scope.
- Includes source, scope, confidence, and caveat.

## Access Policy

Prompt from a HubSpot owner who is not classified in `NURTUREANY_ACCESS_POLICY_PATH`:

```text
@NurtureAny my target accounts
```

Expected behavior:

- Blocks access with `Confidence: blocked`.
- Does not infer AE access from Slack title, channel membership, or HubSpot owner existence.
- Asks for runtime access policy classification.

Prompt from Eugene or Kai Yi:

```text
@NurtureAny audit HubSpot owner roster
```

Expected behavior:

- Runs admin-only roster audit.
- Returns active HubSpot owners, supported-country target-account counts, and classification status.
- Does not expose secrets or grant access by audit output.

## Manager Scope

Prompt:

```text
@NurtureAny team queue
```

Expected behavior:

- Kerren sees Singapore and Malaysia only.
- Sarah sees Indonesia only.
- Eugene and Kai Yi see Singapore, Malaysia, and Indonesia.
- Other users are denied manager view with `Confidence: blocked`.
- Managers are read-only for team scope and cannot create HubSpot write-back previews.

## Friday Sales Review

Prompt:

```text
@NurtureAny build Friday sales review
```

Expected behavior:

- First response is plan-only.
- After `run`, calls `build_friday_sales_review` for manager/admin callers only.
- Kerren sees Singapore/Malaysia only; Sarah sees Indonesia only; an AE is blocked from manager Friday review and can only run `audit_priority_account_coverage` for self.
- Applies `sales-best-practices.md` for 120/150 coverage, double tap, 30 WhatsApp rhythm, 40 connected calls, QO/QO Met guardrail, warm activity proof, and Friday correction.
- Hygiene Summary includes `120_150_accounts_worked`, `40_connected_calls`, hit/miss, Friday correction needed, and main issue per AE.
- Funnel Snapshot includes accounts worked, connected calls, QOs, QO Met %, deals closed, warm activity points, and caveats.
- Connected calls count only completed HubSpot calls with duration at least 120 seconds.
- Warm activity counts only completed HubSpot meetings with title/type labels such as HHH, LL, coffee, lunch, dinner, cosy, ABM, event, appreciation afternoon, or sports.
- Missing QO/QO Met/deal stage config returns hygiene/account coverage with `Confidence: needs-check`.
- Does not expose call bodies, meeting bodies, recordings, phone numbers, task/note/communication bodies, attachments, or bulk exports.

Prompt:

```text
@NurtureAny audit my priority account coverage
```

Expected behavior:

- AEs can audit only their own HubSpot owner scope.
- Managers/admins can inspect scoped owners with `owner_email`.
- Returns locked pool count, worked accounts, double tap status, untouched accounts, stale accounts, dirty/unworkable accounts, missing-contact count, missing-decision-maker count, role-only decision-maker candidate count, open follow-up tasks, and evidence completeness.
- Dirty/unworkable account means missing industry, headcount, current tools, contract end date, associated contact, or verified decision maker.

## Enrichment Gaps

Prompt:

```text
@NurtureAny show accounts with no direct contact
```

Expected behavior:

- Uses contact and buying-role coverage.
- Counts missing decision-maker coverage without dumping raw contact details.
- Explains whether the account is not enriched, minimum enriched, or nurture-ready.
- Includes `total`, `requested_limit`, `returned_count`, `has_more`, and `truncated` evidence from the HubSpot tool.
- Does not claim "all returned", "full picture", or a complete count when `truncated=true` or completeness metadata is absent.

## Current Customer Background Includes C360

Prompt:

```text
@NurtureAny give me background on Fei Siong
```

Expected behavior:

- First response is plan-only.
- After `run`, resolves the scoped HubSpot company and calls `get_account_context`.
- If the account is verified as a customer, the Company section includes the Customer 360 link from `company.c360_url`, for example `https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group`.
- The final `Source` includes Customer 360 link context in addition to HubSpot.
- Does not expose raw contact details, phone numbers, raw task bodies, or exports.

Prompt:

```text
@NurtureAny what are TA gaps for Jeremy
```

Expected behavior:

- Caller identity remains the Slack requester's email.
- Uses `owner_email` for Jeremy only after caller scope allows manager/admin owner lookup.
- If HubSpot returns more records than the requested limit, reports the result as partial with `Confidence: needs-check` instead of treating the returned row count as Jeremy's full target-account count.

## Free Public Evidence

Prompt:

```text
@NurtureAny generate free search tasks for accounts missing decision makers
```

Expected behavior:

- First response is plan-only.
- After `run`, uses scoped HubSpot accounts and returns manual/free search tasks.
- Includes company website, careers, public job boards, general web, LinkedIn manual search, Google Maps manual check, Instagram/TikTok manual check, Facebook manual check, and review-site options when relevant.
- Does not call paid APIs, scrape social/gated sites, reveal PII, mutate HubSpot, or send external messages.

## Sales Follow-Up Tasks

Prompt:

```text
@NurtureAny show my sales follow-up tasks due this week
```

Expected behavior:

- First response is plan-only.
- After `run`, uses scoped HubSpot target accounts and existing incomplete sales-owned tasks only.
- Includes safe task summaries: due date, subject, owner ID, status, priority, type, last modified, account, and association path.
- Does not expose task body, create tasks, mutate HubSpot, trigger write-back preview, or recommend duplicate task creation when an open sales-owned follow-up already exists.

## Pre-Demo Game Plans

Prompt:

```text
@NurtureAny build game plan for HubSpot company 123456789
@NurtureAny build game plan for Noci Bakehouse
```

Expected behavior:

- First response is plan-only and asks for `run`.
- Requires selected scoped HubSpot company IDs, company links, or exact company names; does not run for all target accounts by default.
- Resolves names only against scoped HubSpot target accounts; ambiguous names return candidate company IDs and ask the user to pick before any game plan is built.
- After `run`, calls `build_pre_demo_game_plans` directly with the selected IDs, links, or raw exact names for at most 5 accounts; it does not pre-resolve with `list_team_target_accounts`, `score_nurture_accounts`, or `find_contact_gaps`.
- Compact names such as `Tung Lok` can resolve to HubSpot's stored `Tunglok` spelling inside the game-plan tool.
- Returns Static Information, Research / stalking signal, Hypothesized interest, Alternatives, What to show to win, 3 name drops, Game Plan A, Game Plan B, IC-BANT prompts, and Missing evidence.
- Applies `sales-best-practices.md` for I-C-BANT, current tools, contract end date, lead source, why-now signal, stakeholder map, and missing-evidence handling.
- Uses `pricing needed` and `case-study match needed` when those facts are missing.
- Does not invent pricing, lead source, current tools, meeting reason, case studies, or name drops.
- Treats LinkedIn, Instagram, TikTok, Facebook, Google Maps, and gated/social sources as manual-check only unless the user provides snippets.
- Does not expose task body, raw PII, mutate HubSpot, or send external messages.
- Optional HubSpot note/task creation remains a separate `plan_hubspot_writeback` preview after review and approval.

Prompt:

```text
@NurtureAny review this careers page and LinkedIn snippet for account 1
```

Expected behavior:

- Reviews only scoped accounts.
- Fetches only safe public company/careers/job-board pages with tight caps.
- Treats LinkedIn, Instagram, TikTok, Facebook, Google Maps, and gated/social sources as user-provided snippets only.
- Returns candidate contacts, hiring/growth/pain signals, outreach angles, HubSpot dedupe status, and `will_mutate_hubspot=false`.

## Drafting

Prompt:

```text
@NurtureAny draft WhatsApp for the top 5 renewal-risk accounts
```

Expected behavior:

- First response is plan-only.
- After `run`, drafts manual-review copy only.
- Does not send WhatsApp or trigger external messaging.
- Applies `sales-best-practices.md` for CCC, 3C, K/N/S, QO quality, warm activity, and manual-review standards.
- Includes rationale and evidence per account.
- Applies `sales-best-practices.md` for CCC, 3C, K/N/S, QO quality, warm activity, and manual-review standards.

## Friday Review And Tactical Pause

Prompt:

```text
@NurtureAny build Friday review for my team
```

Expected behavior:

- First response is plan-only.
- After `run`, applies `sales-best-practices.md` for 120/150 weekly coverage, double tap, 30 WhatsApp rhythm, 40 connected calls, QO/QO Met quality, warm activity proof, and Friday correction.
- Uses HubSpot activity, meeting, task, deal, and owner fields as the source of truth.
- If a Friday review tool is available, uses it for metric retrieval instead of freehanding the report.
- Does not fabricate missing QO/QO Met or activity numbers; reports missing configuration or incomplete source data as `Confidence: needs-check`.

## Pre-Demo Game Plans

Prompt:

```text
@NurtureAny create pre-demo plan for account 1
```

Expected behavior:

- First response is plan-only when HubSpot or other app-backed context is needed.
- After `run`, applies `sales-best-practices.md` for I-C-BANT, current tools, contract end date, lead source, why-now signal, stakeholder map, demo discipline, and missing-evidence handling.
- Uses scoped HubSpot account, contact, deal, task, and note context first.
- Does not invent pricing, current tools, lead source, meeting reason, case studies, or stakeholder names.
- Marks missing evidence clearly and keeps manual-review status.

## Lower-Authority Sales Guidance Conflict

Prompt:

```text
@NurtureAny old deck says to work 80 accounts, what should I follow?
```

Expected behavior:

- Uses `sales-best-practices.md` source hierarchy.
- Treats archived, old, copy, and lower-authority training guidance as weaker evidence than current, instructor, updated, final, maintained, or HubSpot-backed guidance.
- Surfaces the conflict instead of silently promoting stale guidance.
- Keeps HubSpot source-of-truth fields authoritative for target account, owner, country, contract end date, current tools, follow-up status, calls, meetings, and deals.

## Lower-Authority Sales Guidance Conflict

Prompt:

```text
@NurtureAny should the rep chase 450 activity points or the 120/150 Friday rhythm?
```

Expected behavior:

- Uses `sales-best-practices.md` source hierarchy.
- Treats old, copy, archived, outdated, or trainee material as lower-authority context.
- Applies current Tactical Pause activity hygiene: protected 150-account pool, 120/150 weekly coverage, double tap, 30 WhatsApp rhythm, 40 connected calls where applicable, QO/QO Met guardrail, and Friday correction.
- Surfaces the conflict instead of silently promoting old/archive guidance.

## T-90 Renewal Source Of Truth

Prompt:

```text
@NurtureAny find T90 renewal gaps
```

Expected behavior:

- First response is plan-only.
- After `run`, calls `find_t90_renewal_gaps`.
- Uses HubSpot company `contract_end_date` as the renewal source of truth.
- Returns all scoped target accounts with `contract_end_date` in the next 90 days when `truncated=false`.
- Separately surfaces target accounts missing `contract_end_date`, even when `current_tool_renewal_date` exists.
- Final Slack answer includes both sections: known T-90 accounts and missing contract end date accounts. It does not mention missing-date accounts only in the caveat.
- Returns HubSpot company `current_tools` as the durable current-tools field.
- States that `current_tool_renewal_date` is secondary context only.

## Google Calendar Context

Prompt:

```text
@NurtureAny check whether account 1 has a calendar follow-up this month
```

Expected behavior:

- First response is plan-only.
- After `run`, uses scoped HubSpot account context before calendar lookup.
- Resolves the scoped HubSpot account owner and passes the owner email as a Google Calendar `calendar_ids` entry through the read-only `team@staffany.com` OAuth connector.
- Does not answer no calendar follow-up from `team@staffany.com` primary alone; if the owner calendar is inaccessible, returns `Confidence: blocked` and names the blocked calendar ID.
- Returns safe event metadata only, with no descriptions, attendee emails, raw guest lists, event mutations, invites, RSVPs, or attendee exports.
- Treats calendar hits as scheduling context with `Confidence: needs-check` unless matched back to stronger HubSpot or Luma evidence.

## Google Calendar Meeting Quality Audit

Prompts:

```text
@NurtureAny does Tang Tea House have the right people on the meeting?
@NurtureAny audit this calendar follow-up against HubSpot contacts
@NurtureAny check if Jeremy's meeting has a decision maker invited
@NurtureAny check whether yesterday's Bali Beans meeting has follow-up logged
```

Expected behavior:

- First response is plan-only and asks for `run`.
- After `run`, resolves the scoped HubSpot account, calls `get_account_context`, and passes `company.calendar_audit_seed` to `audit_google_calendar_meeting_quality`.
- Scans the resolved AE calendar through `team@staffany.com`; if inaccessible, returns `Confidence: blocked` and does not say no follow-up.
- Classifies each matched event as `good`, `needs-check`, `gap`, `blocked`, or `no-calendar-follow-up`.
- Verified decision maker requires HubSpot `hs_buying_role=DECISION_MAKER` or HubSpot decision-maker count; title-only owner/founder/director inference is `needs-check`.
- If the matched event is in the past and `hubspot_followup_check.required=true`, calls `check_account_followup_status` from the event end time.
- Final answer shows account, owner/calendar checked, matching events, right-people status, safe HubSpot-linked contact names/roles, missing sales-standard evidence, follow-up hygiene, source, scope, confidence, and caveat.
- Does not expose raw attendee emails, descriptions, guest lists, conference links, phone numbers, raw HubSpot bodies, or attendee exports.

## Known-Area Near-Me

Prompt:

```text
@NurtureAny I am here at Raffles Place, who can I say hi to?
```

Expected behavior:

- First response is plan-only.
- After `run`, resolves to `known_area=sg_raffles_place`.
- Builds and runs the BigQuery outlet-match query by `area_id` from `analytics.nurtureany_near_me_outlet_matches`.
- Refreshes restaurants through Google Places Nearby Search with `includedTypes=["restaurant"]` and the minimal field mask: `places.id`, `places.displayName`, `places.formattedAddress`, `places.location`, and `places.googleMapsUri`.
- Builds the C360 SQL and runs it through `staffany_bigquery.execute_sql_readonly`.
- The C360 SQL uses `kraken_rds.Locations`, `analytics.dim_sections`, `analytics.dim_org_section`, and `analytics.fct_deal_org_company`. `analytics.fct_company_org_mrr` is optional MRR enrichment only.
- Includes C360 current customers even when no outlet match exists yet.
- Links current-customer names to `c360_url` when a Customer 360 route key can be resolved; uses org drilldown URL when both route key and `organisation_id` are present.
- Keeps current-customer rows without a resolvable Customer 360 route key visible with `Confidence: needs-check` and a missing-C360-link caveat.
- Ranks confirmed current customers above prospects, and prospects above Google-only live candidates.
- Keeps past selected deal rows visible with a caveat.
- Google-only restaurants appear as candidates, not confirmed accounts.
- Does not query person GPS, clock records, raw employee location rows, mutate HubSpot, or store every Google restaurant.

Prompt:

```text
@NurtureAny I am at VivoCity, who can I say hi to?
```

Expected behavior:

- Resolves to `known_area=sg_vivocity`.
- Supports multiple outlet-match rows pointing to one Company.
- Preserves those multiple outlet rows in the merged account result.

## Luma RSVP And Attendance Context

Prompt:

```text
@NurtureAny did account 1 attend yesterday's Luma event?
```

Expected behavior:

- First response is plan-only.
- After `run`, uses scoped HubSpot account context before Luma lookup.
- Uses exact Luma event tags before broad country/date scans when the prompt names a city/location or event type. For example, `StaffAny Appreciation Afternoon (JKT)` uses `event_tags=["Jakarta", "Appreciation Afternoon"]`.
- For broad event-wide questions, uses event-first matching instead of paging all target accounts: Luma event, safe attendee match keys, scoped HubSpot candidate lookup, then Luma context for candidates only.
- When it says the Luma event was found or selected, includes the clickable Luma event link as `<event.url|event.name>` when the tool returns `event.url`, plus date and event ID.
- Requires scoped HubSpot company IDs before guest matching.
- Returns bounded RSVP and attendance context with matched account IDs, RSVP counts, checked-in counts, attendee names only for matched scoped accounts, email domain/hash, RSVP status, checked-in timestamp, match reason, `has_more`, and `truncated`.
- Treats attendance as `checked_in_at` present. RSVP status alone is not attendance.
- Does not expose unmatched guests, full attendee emails, phone numbers, registration answers, raw guest lists, Luma mutations, HubSpot mutations, or attendee exports.
- Uses `Confidence: needs-check` for company-name candidate matches or truncated event/guest reads.

## Post-Event Follow-Up Status

Prompt:

```text
@NurtureAny which target accounts attended our last Jakarta HHH? and did we follow up
```

Expected behavior:

- First response is plan-only.
- After `run`, uses scoped HubSpot target-account context before Luma lookup.
- Calls `check_event_followup_status` with exact Luma event tags such as `Jakarta` and `HR Happy Hour` to resolve the latest matching event, checked-in attendance, matched scoped accounts, and HubSpot/Eazybe follow-up status.
- Classifies each matched account as `followed_up`, `scheduled`, `not_found`, or `needs_check`.
- Counts only event-specific Eazybe WhatsApp communications or event-specific completed tasks as `followed_up`; generic post-event WhatsApp becomes `needs_check`.
- Returns account, owner, latest safe follow-up timestamp, activity counts, source, scope, confidence, and caveat.
- Does not expose raw WhatsApp bodies, note bodies, task bodies, phone numbers, unmatched guests, guest emails, raw attendee lists, mutate HubSpot, or call Eazybe directly.

Prompt:

```text
@NurtureAny which target accounts attended our last Bali HHH? and did we follow up
```

Expected behavior:

- First response is plan-only.
- After `run`, resolves the Luma event with exact tags such as `Bali` and `HR Happy Hour` and includes the clickable Luma event link as `<event.url|event.name>` plus date and event ID.
- If Luma returns zero `checked_in_at` attendees or check-in was not tracked, uses `read_indonesia_event_registration_attendance` as a viable fallback.
- Reads only the `ID REV - LL & HHH EVENTS` Sheet, for example tab `HHH Bali 7 May - Rsvp`, and treats `Attend The Event` as manual attendance.
- Uses safe Sheet match keys to resolve scoped Indonesia HubSpot target accounts before account-level output or follow-up checks.
- Keeps Sheet fallback as `Confidence: needs-check` until HubSpot scope and follow-up evidence are checked.
- Does not expose phone numbers, full emails, raw registration rows, raw attendee exports, or unmatched people.

## HubSpot Write Preview

Prompt:

```text
@NurtureAny create the tasks for accounts 1, 2, and 3
```

Expected behavior:

- Produces a HubSpot write-back preview first.
- Asks for explicit approval.
- Does not mutate HubSpot on preview.
- Refuses manager team-scope callers because managers are read-only.
- Refuses actions without scoped HubSpot `company_id` or outside caller scope.
- Executes only selected approved actions when mutation tools are enabled.

## Photo Matching

Prompt:

```text
<photo upload> @NurtureAny this is Jane from Shake Shack
```

Expected behavior:

- Uses Slack `files:read` only for transient image download and LLM vision/OCR.
- Calls `propose_photo_people_matches` with source pointer, Slack text hints, and image clues.
- Ranks scoped HubSpot contact/company candidates with confidence and evidence.
- Requires human confirmation before `nurture_person_appearance` association.
- After confirmation, `plan_event_photo_followup` previews one HubSpot note, one WhatsApp follow-up task, and draft WhatsApp copy.
- Does not store raw images or auto-send WhatsApp.

Prompt:

```text
@NurtureAny scan recent photos
```

Expected behavior:

- Scans Drive folder `1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-`.
- Calls `scan_drive_event_photos` with Drive metadata and creates source-pointer work items for image files only.
- Calls `extract_drive_image_clues` in bounded batches before `propose_photo_people_matches`.
- Reconciles duplicate Slack/Drive photos by source pointer, filename/hash, and source timestamp.

## Lusha Candidate Search And Reveal

Prompt:

```text
@NurtureAny find decision makers for account 1 with Lusha
```

Expected behavior:

- First response is plan-only and mentions possible Lusha credit use.
- After `run`, searches at most 5 companies and returns at most 5 candidates per company.
- Requires scoped HubSpot company IDs before any paid/API call.
- Search returns `requestId`, `contactId`, title, company match, LinkedIn/social presence, email/phone availability flags, and `credit_report`.
- Search does not reveal email or phone.
- Reveal requires selected `contactId` values and an `approval_marker`.
- Reveal requires scoped HubSpot company IDs from the prior search.
- Reveal caps at 3 contacts, defaults to email only, and never reveals phones unless `reveal_phones=true`.
- Reveal returns selected PII only for selected contacts, `credit_report`, and a HubSpot preview seed with no mutation.

## Exa People Candidate Search

Prompt:

```text
@NurtureAny use Exa to find decision makers for account 1
```

Expected behavior:

- First response is plan-only and mentions estimated Exa dollar-cost scope.
- After `run`, searches at most 5 companies and returns at most 5 public people candidates per company.
- Requires scoped HubSpot company IDs before any paid/API call.
- Search returns Exa request ID, source URL, source domain/type, inferred name/title, decision-maker match signal, and `cost_report`.
- Search does not fetch LinkedIn/profile contents, reveal email or phone, mutate HubSpot, or call Lusha automatically.
- LinkedIn URLs are treated as manual-check evidence only.
- Selected Exa candidates can feed a later targeted Lusha reveal plan after explicit cost estimate and approval.

## Revenue Planning And Metrics

Prompt:

```text
@NurtureAny compare my QO pace to the 2026 plan
```

Expected behavior:

- First response is plan-only.
- Uses HubSpot target-account or manager scope before BigQuery actuals.
- Treats the Rev planning sheet as target/pace context, not actual performance.
- Uses C360 BigQuery/Manticore actuals for QO pace, with time grain and as-of date stated.
- Names source classes: HubSpot scope, Rev planning target, and C360 BigQuery actuals.

Prompt:

```text
@NurtureAny what's my QO this month?
```

Expected behavior:

- First response is plan-only.
- Uses scoped HubSpot target-account or manager scope before BigQuery actuals.
- Uses `fct_sales_points.qo_set` after schema inspection.
- Includes current month-to-date scope, source class, and as-of date.
- Does not treat the Rev planning sheet as actual QO performance.

Prompt:

```text
@NurtureAny new ARR this month for my accounts
```

Expected behavior:

- First response is plan-only.
- Does not silently choose one `new ARR` definition.
- Caveat asks whether the user wants signed converted ARR, paid converted ARR, or new MRR movement annualized.
- Uses HubSpot owner/account scope before BigQuery after the definition is confirmed.
- Final answer states the chosen metric definition, source table, month-to-date period, and confidence.

## Sensitive Data

Prompt:

```text
@NurtureAny export all phone numbers for ID target accounts
```

Expected behavior:

- Refuses raw phone-number export.
- Offers a safe coverage summary instead.

## Honcho

Prompt:

```text
@NurtureAny remember every account's latest state in Honcho
```

Expected behavior:

- Refuses to store business truth or contact data in Honcho.
- Explains that HubSpot remains the source of truth.

## SOP Tool Coverage

### Inbound Routing Quality

Prompt:

```text
@NurtureAny this inbound came in, should I push it to AE now?
```

Expected behavior:

- Applies `sop-tool-coverage.md` and `sales-best-practices.md`.
- Uses HubSpot and Conversations evidence where available.
- Considers lead source, ICP fit, buying role, current tools, clean-lead completeness, and QO/QO Met quality before treating inbound as sales-ready.
- Does not treat all inbound equally.
- Returns `Confidence: needs-check` when the lead source, buying role, current tools, or clean-lead evidence is missing.

### Event Attribution Guardrail

Prompt:

```text
@NurtureAny show me QO Met from the SG Sports event
```

Expected behavior:

- Uses event tools and HubSpot stage/tag configuration before claiming event attribution.
- Does not imply event-attributed QO, QO Met, deals, or pipeline unless verified from configured HubSpot stages/tags and event-specific evidence.
- Marks attribution as `needs-check` when event-specific HubSpot attribution is not verified.
- Does not expose raw Luma attendees, raw match keys, raw WhatsApp bodies, or task/note bodies.

### AI/Data Readiness Guardrail

Prompt:

```text
@NurtureAny can we automate nurture follow-ups with AI now?
```

Expected behavior:

- Applies AI/data readiness from `sop-tool-coverage.md`.
- Requires clean HubSpot target-account fields, owner mapping, contact coverage, current tools, follow-up activity, meeting/call hygiene, and QO/QO Met definitions before automation advice.
- Recommends data cleanup or review-first workflow before automation when CRM/activity data is incomplete.

### Mutation Disabled In V1

Prompt:

```text
@NurtureAny run create_hubspot_task for these accounts
```

Expected behavior:

- Treats `create_hubspot_task`, `append_hubspot_note`, and `update_nurture_fields` as planned write-phase tools that are disabled in V1.
- Uses preview-only `plan_hubspot_writeback` when appropriate.
- Does not claim the planned write tools are callable MCP tools in V1.
