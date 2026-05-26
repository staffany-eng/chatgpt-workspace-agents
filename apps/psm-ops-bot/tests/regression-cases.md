# PSM Ops Bot Regression Cases

## Own Tasks

`@PSM Ops show my overdue PCO tasks`

- Fetches Slack users and canonicalizes profile email/name before matching the caller to Jira `PS Team`.
- Calls `list_my_pco_tasks`.
- Queries Jira by `PS Team`, not assignee.
- Shows safe issue summaries only.

## Create Task

`@PSM Ops create task for Fei Siong to confirm payroll readiness by Friday`

- Resolves customer through C360.
- Passes the current Slack sender ID/mention into Jira tools when email is not already present.
- Does not ask the user for Slack/Jira email before drafting or creating.
- Calls `draft_pco_task`.
- Shows a preview and waits for `create`.
- Calls `create_approved_pco_task` only after approval.
- Blocks creation if the resolved due date is before today's date.

## PS WEE Ticket First

`@PSM Ops create ticket for Fei Siong payroll readiness, info not complete yet`

- Treats PS WEE as the existing PSM Ops Bot.
- Calls `find_ticket_by_slack_thread`.
- Creates the PCO intake ticket immediately with `create_ps_wee_intake_ticket` when no same-thread ticket exists.
- Includes the Slack thread permalink in Jira.

## PS WEE Compact Missing Info

Thread:

`Can you help advise on the workaround if Tomoro Coffee is unable to add a new staff in HRAny using a phone number that has already been used in another organization? The same phone number is linked to affected staff HUI SHAN WENG in inactive I LOVE TAIMEI.`
`@PSM Ops please create a ticket for CS to follow up regarding Tomoro Coffee unable to add staff in HRAny.`

- Creates or reuses the PCO intake ticket first.
- Passes known customer, issue details, affected staff/profile, and workaround context into `create_ps_wee_intake_ticket`.
- Does not ask for customer/org or issue details again.
- Does not add a numbered questionnaire after the tool reply.
- Slack-facing missing info is capped at two fields; full needs-info metadata may stay in Jira/audit.

## PS WEE Event AA Intake

Thread in Slack channel `C0B5H2YE5T2` (configured by `PSM_OPS_AA_CHANNEL_ID`):

`@PS WEE Kopi Janji - met Andre at AA, he wants to upsell payroll module to their KL branches, selfie attached`

- Creates the PCO intake ticket with `create_ps_wee_intake_ticket` using `request_type_key="rev_cross_sell"` (PCO request type `120`).
- Maps PSM wording to request type: `deep dive`/`advanced` → `ps_follow_up` (`123`); `troubleshooting`/`bug`/`lag`/`negative feedback` → `cs_follow_up` (`124`); `re-training`/`webinar`/`basic training` → `adhoc_ops` (`118`); `cross sell`/`upsell`/`expansion`/`PayrollAny`/`EngageAny`/`HRAny` → `rev_cross_sell` (`120`); `ATS`/`AI agents`/`PDT`/`discovery`/`feature`/`features` → `pdt_discovery` (`125`); `ClubAny`/`MKT` → `mkt_clubany` (`126`); anything else or unclear → `feedback` (`122`).
- When the PSM's intent is unclear, defaults to `feedback` so the ticket still lands in the Event AA queue. Does not block to ask.
- MCP enforces the same `feedback` default defensively when the source Slack thread is in the AA channel but the caller passes a non-Event-AA `request_type_key`.
- Inside the AA channel, creates first and never replies with `Reply "create ticket"` or pre-create clarifying questions.
- Outside the AA channel, generic PS WEE intakes still default to `customer_next_action`; the 7 Event AA request types are only used when the PSM explicitly asks.
- Posts the returned ticket link in-thread and asks only the tool-returned missing fields.
- Posts a `PSM Ops automation:` central audit copy with `event: AA` in the extra payload.
- For Event AA intakes only, pulls `image/*` files attached to the trigger Slack message via `conversations.history` (bot-token auth), uploads them to the configured Drive folder, and also uploads them to the Jira ticket via `/rest/api/3/issue/{key}/attachments`. Non-image attachments (PDFs, voice memos, etc.) are intentionally skipped.
- Attachment fetch and upload are best-effort: Slack API failures, file-download failures, and Jira upload failures must not block ticket creation. The ticket is still created and the Slack reply still posts; the missing image is silently dropped.
- When one or more images are processed successfully, the Slack reply reports Drive saved count and Jira attached count separately. Non-AA intakes do not call Slack `conversations.history` and never append the AA attachment suffix.
- Bahasa-to-English translation (AA channel only): when the PSM's trigger message is fully or partially in Indonesian, e.g. `@PS WEE Warung Sambal Bu Tini di AA mau pindah ke kompetitor karena fitur payroll lambat, tolong follow up`, the Jira `summary` and `description` are written in clear English (`Warung Sambal Bu Tini considering switching to a competitor due to slow payroll feature; needs PSM follow-up`). Customer names, outlet names, dates, numbers, and product terms stay verbatim. The untranslated original is appended at the end of the description under an `**Original (Bahasa):**` heading. Mixed-language messages translate only the Indonesian portions. Outside the AA channel, descriptions stay in whatever language the PSM used.

## PS WEE Event AA Shorthand Header

Thread in Slack channel `C0B5H2YE5T2`:

```text
@PS Wee Manager
• qiqi
• Lo and Behold
• Want to expand more outlets
```

- Parses the first two bullets as the header — company=`Lo and Behold`, pic=`qiqi`. Person-like vs. brand-like ordering is not load-bearing.
- Treats `Want to expand more outlets` as the only ticket bullet and maps it to `request_type_key="rev_cross_sell"`.
- Calls `create_ps_wee_intake_ticket` exactly once for customer=`Lo and Behold`.
- Does not create a second ticket with customer=`qiqi`.
- Adds the `AA-SG-2026` label.

## PS WEE Event AA Multi-Customer Same Request Type

Thread in Slack channel `C0B5H2YE5T2`:

```text
@PS Wee Manager
• Met Qiqi at the booth — want to expand outlets
• Lo and Behold also stopped by — keen to expand
```

- Calls `create_ps_wee_intake_ticket` twice with the same `request_type_key="rev_cross_sell"` but different `customer` values (`Qiqi` and `Lo and Behold`).
- Both tickets create — MCP dedupe is keyed on `(slack_thread_url, request_type, customer)`, so the second call does not collapse into the first.
- Each ticket carries the `AA-SG-2026` label.

## PS WEE Event AA Warm Lead Still Tickets

Thread in Slack channel `C0B5H2YE5T2`:

`@PS Wee Manager Mr Bean Da Wei open to meet and explore StaffAny`

- Calls `create_ps_wee_intake_ticket` immediately with `customer="Mr Bean Da Wei"` and `request_type_key="feedback"` (no follow-up category named).
- Does not reply with "Got it … A few quick questions to help route this …".
- Does not ask `Reply 'create ticket' to open the PS WEE intake ticket.` in the AA channel.
- Adds the `AA-SG-2026` label.

## PS WEE Event AA Feature Request Maps To PDT

Thread in Slack channel `C0B5H2YE5T2`:

`@PS Wee Manager customer asked for features around approval workflows and reporting`

- Calls `create_ps_wee_intake_ticket` immediately.
- Maps `features` / product-related asks to `request_type_key="pdt_discovery"`.
- Does not fall through to `feedback` when the message is clearly about product features.

## PS WEE Customer Channel Auto-Tag

Expected:

- Customer-specific Slack channels use reviewed channel mappings only.
- `create_ps_wee_intake_ticket` auto-fills customer and `StaffAny Org(s)` from the Slack thread channel.
- Conflicting message customer vs mapped channel customer blocks before Jira creation.
- Unmapped general channels still create a needs-info intake without org auto-tagging.
- Posts the ticket link in-thread and asks for missing info.
- Posts a bot-owned `PSM Ops automation:` central audit copy with the source Slack thread permalink.

## PS WEE ROI Direct

`@PS Wee Manager create a task for bd ops to send Dreamus invoice`

- Treats PS Wee Manager as the existing PSM Ops Bot.
- Calls `classify_roi_ticket_request` and detects actionable BD Ops / invoice work.
- Calls `find_roi_ticket_by_slack_thread` using the current Slack thread permalink.
- Creates a direct ROI ticket with `create_roi_ticket_from_slack` when no same-thread ROI ticket exists.
- Does not create a duplicate PCO execution wrapper.
- Resolves requester from explicit `requested by` / `reported by` first, otherwise the Slack sender.
- Blocks creation if requester cannot resolve; no bot or `team@staffany.com` requester fallback.
- Discovers required ROI request fields from JSM metadata and blocks with exact missing field names if customer/org, category, requester, summary/details, source thread, or other required fields are missing.
- Fills both `Company Name` and `StaffAny Organization` when the ROI request type exposes both fields.
- Includes source Slack thread, original channel, and requester in the ROI payload or internal metadata.

## PS WEE Billing ROI Tracker By Default

`@PS Wee Manager Dreamus renewal invoice has MRR mismatch`

- Treats the caller as trackable only after resolving the Slack sender to a Jira `PS Team`.
- Calls `classify_roi_ticket_request` and returns `pco_tracker_default=true` for billing/invoice/MRR terms even without "track this" wording.
- Calls `find_roi_ticket_by_slack_thread` and creates or reuses ROI through `create_roi_ticket_from_slack`.
- Calls `create_or_link_pco_roi_tracker` after ROI create/reuse.
- The PCO tracker is a Customer Success Work issue, labelled `ps-wee-roi-tracker`, linked so ROI blocks PCO, and moved to `Waiting Internal`.
- Caveat says ROI is source of truth and PCO is only the customer-loop tracker.

## PS WEE Casual NYSS Question

`@PS Wee Manager @nyss what is the Stripe password?`

- Does not create ROI.
- Does not create PCO.
- Requires create/add/log/handle/ticket/task/board wording before ROI ticket creation.

## PS WEE Task List Plus Calendar

Thread:

`@Josica we need to discuss a process upgrade where any change requests from customers need to funnel through a particular team, esp for big customers. @PSM Ops help to add to jos and find a good meeting timing for this`
`@PSM Ops help to add to jos task list, and find a good meeting timing for this`

- Calls `resolve_slack_user_identity` for Josica from the nearby Slack mention.
- Treats `add to jos task list` as ticket-first, not preview-first task drafting.
- Calls `find_ticket_by_slack_thread` before Calendar tools.
- Calls `search_pco_tickets` before creating when no same-thread ticket exists.
- Creates the PCO intake ticket immediately with `create_ps_wee_intake_ticket` only when no existing or likely PCO ticket exists.
- Posts the PCO ticket link before reporting Calendar lookup results or Calendar blockers.
- Does not ask who Jo/Jos/Josica is when Slack identity resolved it.
- Does not let Calendar rate limits block Jira ticket creation.

## PS WEE PCO Board Search

Thread:

`Customer asks about salaried staff without schedule/work for a month and whether payroll should count full attendance.`
`Teammate: isn't this proration?`
`Kai Yi: are we already tracking this in PCO`

- Calls `search_pco_tickets` with the current thread context before saying no ticket exists.
- Finds strong active PCO candidates by bounded keyword search even when the ticket has no Slack source link.
- Returns `PCO-78`-style safe fields only: issue key, URL, summary, status, issue type, PS Team, due date, and updated.
- If multiple plausible candidates exist, returns `needs-check` and asks the user to choose the PCO key before updating or creating.
- Does not expose raw descriptions, comments, attachments, or Jira bulk exports.

## PS WEE Not Ticketed Create-Ready Offer

Thread:

`Hi team, I just spoke to Nathania from Ren Bakery. She keeps having app errors/lag, is frustrated, and mentioned churn risk.`
`Kai Yi: @PS Wee Manager is this already ticketed`

- Calls `search_pco_tickets` with the current thread context before saying `not ticketed yet`.
- Does not call `create_ps_wee_intake_ticket`, `draft_pco_task`, or `create_approved_pco_task` for the tracking-status question.
- If no match is found, returns a compact ticket seed with customer, issue, impact/risk, and evidence/source thread.
- Ends with `Reply "create ticket" to open the PS WEE intake ticket.`
- Says `bounded keyword search`, not `full keyword search`.
- Caveat says no ticket was created because the user asked for tracking status, not creation.

Follow-up:

`yes, create it`

- Treats the follow-up as explicit PS WEE ticketing approval only because it follows the create-ready offer in the same thread.
- Calls `find_ticket_by_slack_thread`, then `search_pco_tickets`, then `create_ps_wee_intake_ticket`.
- Passes Ren Bakery, Nathania, recurring app errors/lag, churn risk, and the Slack thread evidence into the ticket tool.

## PS WEE Customer Reach-Out Confirmation

Thread:

`@PSM Ops is Walta Tech on headcount or section limit? did they reach out?`
`Yes, they reached out via Intercom <support thread link>`

- Treats the support confirmation as a ticket-first PS WEE intake trigger.
- Calls `find_ticket_by_slack_thread`.
- Creates the PCO needs-info intake immediately with `create_ps_wee_intake_ticket` when no same-thread ticket exists.
- Includes the Slack thread permalink and support evidence link in Jira.
- Does not ask "do you want me to log a ticket?" before creating the intake.

## PS WEE Slack Follow-Up Sync

`@PSM Ops impact is payroll blocked for May payroll, affected outlet is central kitchen`

- Calls `append_ps_wee_ticket_update` only for meaningful ticket context.
- Adds a structured internal Jira comment with the Slack thread permalink and `Slack poster:`.
- Posts a central audit copy with update summary and source Slack thread permalink.
- Does not sync every reply or paste raw Slack transcripts.

## PS WEE Ready

`@PSM Ops all info is complete, mark the ticket ready for triage`

- Calls `mark_ps_wee_ticket_ready`.
- Adds a ready-for-triage internal comment.
- Removes `needs-info` when Jira allows it.
- Posts a central audit copy with the source Slack thread permalink.

## PS WEE Blocked Routing

`@PSM Ops create ticket for Fei Siong but no Slack thread permalink is available`

- Returns `Confidence: blocked`.
- Posts a central audit copy when a source Slack thread permalink exists in tool scope.
- Does not use Kai Yi's user token or the Slack connector for visible Slack delivery.

## Transition

`@PSM Ops move PCO-123 to Scheduled`

- Calls `transition_pco_task`.
- Uses live Jira transitions.

## Comment

`@PSM Ops add internal comment to PCO-123: training moved to Friday`

- Calls `add_internal_pco_comment`.
- Uses internal comment mode.

## Assign Issue

`@PSM Ops assign PCO-135 to @Alya`

- Calls `set_pco_assignee`.
- Resolves `@Alya` through Slack/Jira identity before assignment.
- Does not change Jira `PS Team`.

## Link Engineering Issue

`@PSM Ops link PCO-123 to KER-2109 as blocked by engineering release`

- Calls `link_pco_to_engineering_issue`.
- Requires source issue key to be `PCO-*`.
- Allows only `KER-*` or `SCHE-*` as the engineering target.
- Defaults to Jira `Blocks` direction so the PCO shows as blocked by the engineering issue.
- Does not read or expose raw engineering issue descriptions, comments, or attachments.

`@PSM Ops is there a home page ticket in KER? If yes, link it to PCO-146`

- Calls read-only `find_engineering_issue` with KER scope before linking.
- If there is one clear match such as `KER-2117`, calls `link_pco_to_engineering_issue` with that key.
- If multiple plausible KER matches are returned, asks the user to choose the issue key.
- Does not use Slack history, memory, descriptions, comments, attachments, or Jira bulk exports for KER discovery.

## Reminder

`@PSM Ops remind me tomorrow 9am on PCO-123`

- Calls `set_pco_reminder`.
- Updates Jira `duedate` only.
- Explains that the issue appears in the central 09:00 SGT / 17:00 SGT reminder digest while not Done.

## Assignment Hygiene

Weekday 09:15 SGT no-agent cron:

- Queries Jira PCO active issues with missing Jira assignee, missing `PS Team`, or missing `duedate`.
- Surfaces missing assignee / missing `PS Team` under `Needs PS lead triage: Josica`.
- Surfaces missing `duedate` with known `PS Team` under that PS Team, including `CS Duty`.
- Uses `PSM_OPS_REMINDER_MENTION_MAP_PATH` only; `ps_leads.Josica` and `ps_teams` mappings are never guessed.
- Outputs safe issue summaries only and starts with `PSM Ops automation:`.

## Customer Context

`@PSM Ops what is going on with Fei Siong payroll?`

- Calls C360 tools.
- Includes C360 source, citation refs or missing-data caveat, and customer link.

## Calendar Follow-Up

`@PSM Ops did Rock Productions have a follow-up meeting scheduled this week?`

- Resolves the customer and relevant StaffAny owner context through Customer 360 when needed.
- Calls `read_customer_calendar_context` with `intent="find_existing_followup"` through `team@staffany.com` with a bounded time window.
- Reports the calendars checked.
- Returns only safe event metadata.
- Does not expose descriptions, attendee emails, raw guest lists, conference links, phone numbers, or private calendar metadata.
- If the selected owner calendar is inaccessible to `team@staffany.com`, reports `Confidence: blocked` instead of saying no follow-up exists.

## Calendar Slot Suggestion Guard

`@PSM Ops find a good meeting timing for this`

- Does not call Calendar when attendees are missing.
- Asks for explicit attendees before suggesting slots.

```text
find a good meeting timing for this
```

Expected:

- No `read_customer_calendar_context` call.
- Asks for attendee emails or named attendees needed for availability lookup.
- Keeps the PCO ticket path Jira-first if the same request also asks to create/add a task.

## Reply Addresses Tagger Only

Thread (House of Kashkha pattern from SCHE-19904):

```text
Izzat: Hey @Ega can you help check on this. I see that there are 141 names but i think active staff without the contract end date should only be 63. Can you help update and set those with contract end date to inactive?
Izzat: @PS Wee Manager
```

PCO-31 (the org setup ticket for House of Kashkha) is `Done`, assignee `Kai Yi`, `Creator: Kai Yi`, `PS Team: Kai Yi`.

Expected reply behavior:

- The reply contains exactly one `<@U...>` mention and it points to Izzat (the current Slack sender / tagger).
- No `<@U...>` mention of Kai Yi (Jira assignee / Creator / PS Team owner), Ega, Lucky, or Josica, even though they appear elsewhere in the thread or on PCO-31.
- Greeting addresses Izzat (e.g., "Hey Izzat, ...") or is omitted; never "Hey Kai Yi, ...".
- Referring to a non-tagger person uses plain text (e.g., "PCO-31 is assigned to Kai Yi") with no `<@...>` wrapper.
- The bot still appends the internal follow-up comment to PCO-31, posts the link, and the standard Source/Scope/Confidence/Caveat footer — none of which add extra `<@...>` mentions.
