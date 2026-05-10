# Slack Runtime

NurtureAny's first runtime surface is Slack mention usage in sales pilot channels.

## Required Behavior

- Mention-only in configured channels for V1.
- First tool-backed requests are plan-first.
- The bot asks for `run` before the first confirmed execution.
- Clear same-thread corrections, fixes, and reruns after a delivered result are continuation work when scope is bounded.
- Materially expanded scope, source-class changes, write intent, or expensive/ambiguous follow-ups require a revised plan and `run`.
- T-90 renewal answers must display both the known T-90 `contract_end_date` bucket and the missing `contract_end_date` classification bucket. Do not bury missing-date accounts in the caveat.
- Repeated account-name follow-up requests should reuse bounded sources or run bounded target-account `query` lookup. Do not switch to broad queue scoring as a direct lookup.
- Follow-up coverage answers must name the calendars checked. For a scoped HubSpot account, include the account owner's email calendar ID when calling Google Calendar; if it is inaccessible to `team@staffany.com`, say that instead of saying no follow-up.
- Calendar meeting-quality audit requests must first resolve the scoped HubSpot account, then fetch `get_account_context`, pass `company.calendar_audit_seed` to `audit_google_calendar_meeting_quality`, and only then summarize whether the right people are on the meeting.
- For past matched Calendar meetings, if the audit tool returns `hubspot_followup_check.required=true`, call `check_account_followup_status` from the event end time before answering follow-up hygiene.
- Calendar audit answers are safe summaries only: account, owner/calendar checked, matching events, right-people status, HubSpot-linked names/roles, missing sales-standard evidence, follow-up hygiene, source, scope, confidence, and caveat. Never expose raw attendee emails, guest lists, descriptions, conference links, phone numbers, or raw HubSpot bodies.
- Exa People Search requests must show the estimated dollar-cost scope before execution and include `cost_report` after execution.
- Luma guest or attendance requests must check HubSpot scope first, then return bounded RSVP/attendance context without raw attendee exports.
- Post-event follow-up requests must use `check_event_followup_status` when the event is named or needs Luma resolution, then use HubSpot/Eazybe event-specific WhatsApp communications, notes, and tasks for status. Generic post-event WhatsApp is `needs_check`, not clean follow-up.
- Luma event requests should pass exact Luma event tags when the prompt implies them, for example `event_tags=["Jakarta", "Appreciation Afternoon"]` for `StaffAny Appreciation Afternoon (JKT)` or `event_tags=["Singapore", "Sports"]` for the screenshot-style Sports event. Use country as broad account scope, not as the event filter when exact tags are known.
- Near-me prompts should plan for known-area snapping, BigQuery outlet-match lookup, Google Places live restaurant refresh, C360 BigQuery current-customer query, and merge/ranking. Ask for `run` before tool execution.
- Near-me answers must show C360 current customers even when no BigQuery outlet match exists, link every current customer name to returned `c360_url` when available, and mark Google-only restaurants as live candidates.
- Pre-demo game plan requests are selected-account only. If the prompt or same thread has scoped HubSpot company IDs, company links, or exact company names, plan for those selected accounts only. If a company name is ambiguous, return scoped candidate company IDs and ask the user to pick before execution.
- Ad hoc photo match requests are allowed in configured pilot channels when a user uploads an image and tags `@NurtureAny`.
- For photo match requests, read the current Slack message/thread, attachment metadata, uploader, channel, timestamp, permalink, and short text hints. Download the Slack image only transiently using `files:read`, run LLM vision/OCR for clues, then discard the raw image.
- Use `propose_photo_people_matches` for the people layer and require uploader/human confirmation before HubSpot association or follow-up preview.
- After confirmation, use `plan_event_photo_followup` to preview the HubSpot note and WhatsApp follow-up task. No WhatsApp auto-send in V1.
- For `@NurtureAny scan recent photos`, call `list_drive_folder_images` for the Google Drive `all-random` folder `1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-`, display Slack-export uploaders by Slack display name when available, call `list_luma_events` for the Drive photo date window, then `scan_drive_event_photos` with the Luma events, then `extract_drive_image_clues` in bounded batches before `propose_photo_people_matches`; Luma date matching may auto-tag the event context only, never the HubSpot person/contact; ask the original uploader to identify or confirm every person, grouping prompts by uploader when possible; do not scan local machine photo folders. If Drive auth/tooling or vision extraction is missing, return `Confidence: blocked` for that missing prerequisite. If Luma is unavailable, continue with Drive/OCR and mark event correlation as `needs-check`.

## Commands

AE commands:

- `@NurtureAny my 150`
- `@NurtureAny my target accounts`
- `@NurtureAny my nurture queue`
- `@NurtureAny accounts missing direct contact`
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
- `@NurtureAny which target accounts attended yesterday's Luma event`
- `@NurtureAny which target accounts attended our last Jakarta HHH and did we follow up`
- `@NurtureAny which target accounts attended StaffAny Appreciation Afternoon (JKT)?`
- `@NurtureAny build pre-demo game plans for these 3 HubSpot company links`
- `@NurtureAny build pre-demo game plans for Noci Bakehouse, Bali Beans, and Kopi House`

## Scope Routing

Use Slack user email as the caller identity.

- AE calls require an explicit `sales_reps` policy entry that maps Slack email to HubSpot owner email, then restrict to owned HubSpot target accounts.
- Manager calls require explicit email allowlist and are team read-only.
- Unclassified HubSpot owners are blocked even if Slack email matches a HubSpot owner record.
- Country filters come from the manager scope, not from channel name.

If Slack cannot provide the user email, return `Confidence: blocked` and ask for the missing identity mapping. If the Slack email is not classified, ask for runtime access policy classification.

## Output Contract

Preflight plain Slack text:

Interpreted question: <question>
Plan: I will check <sources>, using <owner/team/country filters>.
Estimate: <1-2 min | 3-5 min | may exceed 5 min>
Caveat: <material limitation>
Reply "run" to start, or tell me what to change.

Final plain Slack text:

Answer: <result or blocked reason>
Source: <HubSpot/C360/Google Calendar/Luma/tool used>
Scope: <owner/team/country/time filters>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

## Slack Scopes

The Slack app needs enough access to receive mentions, identify users, and reply in configured channels. Do not request broad private-channel enumeration for V1 unless a concrete pilot channel requires it and the security owner approves.

Photo matching additionally needs `files:read` for attached images in configured pilot channels only. Store Slack photo source pointers (`channel_id`, `message_ts`, `file_id`, permalink), not raw image copies. If the same photo later appears in Drive, reconcile by source pointer, filename/hash, and source timestamp before creating a duplicate HubSpot photo record.
