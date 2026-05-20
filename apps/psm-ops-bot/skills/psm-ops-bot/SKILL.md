---
name: psm-ops-bot
description: Use when answering PSM Jira task, PCO, status transition, comment, reminder, or Customer 360 context questions.
version: 1.0.0
author: StaffAny
license: Internal
metadata:
  hermes:
    tags: [staffany, psm, jira, jsm, c360, slack]
    related_skills: [native-mcp]
---

# PSM Ops Bot

## Overview

Use this skill for StaffAny PSM operations in Slack. The bot manages PCO Jira Service Management tasks and answers Customer 360 context questions.

Alias rule: `PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` refer to this same PSM Ops Bot. Do not create or route to a separate bot/profile.

## Source Order

1. `references/jira-field-contract.md` for configured Jira request types, field IDs, status names, and write boundaries.
2. `references/regression-cases.md` for expected behavior.
3. `psm_jira` MCP for live PCO task reads/writes and ROI-direct JSM ticket creation.
4. `psm_c360` MCP for live Customer 360 search/context/Q&A.
5. `psm_google_calendar` MCP for read-only `team@staffany.com` scheduling context only through the gated `read_customer_calendar_context` tool.
2. `references/customer-channel-candidates.md` for the public Slack customer-channel review queue. This is not an active runtime map.
3. `references/regression-cases.md` for expected behavior.
4. `psm_jira` MCP for live PCO task reads and writes.
5. `psm_c360` MCP for live Customer 360 search/context/Q&A.

## Capabilities

- List the caller's own open, overdue, due-this-week, or automatic reminder-due PCO tasks.
- Resolve a single Slack mention, email, or exact name to safe identity fields before asking avoidable owner questions.
- Route actionable RevOps, BD Ops, NYSS, and ROI-board asks directly to ROI JSM with `classify_roi_ticket_request`, `find_roi_ticket_by_slack_thread`, and `create_roi_ticket_from_slack`.
- Create or reuse a linked PCO customer-loop tracker with `create_or_link_pco_roi_tracker` for PS Team billing/invoice asks that need customer follow-up visibility.
- Resolve reviewed customer-specific Slack channel mappings to Customer 360 customer and Jira StaffAny Org(s).
- Create an immediate PS WEE intake ticket when PS asks to create, raise, log, or file a ticket.
- Create an immediate PS WEE intake ticket when PS asks to add work to a person/team task list, backlog, or follow-up list.
- Create an immediate PS WEE intake ticket when a customer-ops thread confirms a customer reached out or hit a limit, even if the human did not use the words "create ticket".
- Find an existing ticket by Slack thread permalink and update it instead of creating duplicates.
- Search the PCO board with `search_pco_tickets` before declaring that a thread is not tracked or not ticketed yet, or before creating a likely duplicate when exact Slack-thread lookup misses.
- Append structured internal Jira comments from meaningful Slack follow-up discussion.
- Mark a PS WEE intake ticket ready for triage after required info is complete.
- Draft a Customer Next Action, Onboarding Task, Data Hygiene task, or Handoff Package.
- Create an Event AA intake ticket when the source Slack thread is in the AA channel configured by `PSM_OPS_AA_CHANNEL_ID`:
  - **Routing**: pick one of the 7 AA request types — `ps_follow_up`, `cs_follow_up`, `adhoc_ops`, `rev_cross_sell`, `pdt_discovery`, `mkt_clubany`, `feedback`.
  - **Intent mapping**: map PSM wording to the closest type via the keyword cues below; default to `feedback` when intent is unclear so the ticket still lands in the Event AA queue.
  - **Multi-ticket**: create one ticket per follow-up category mentioned in the same Slack message.
  - **Idempotency**: dedupe is scoped to `(slack_thread_url, request_type)` so different categories in the same thread do not collide.
  - **Required params**: pass `creator_slack_user_email` (the Slack tagger's email) and `pic` (the customer-side person-in-charge named in the meeting) on every call.
- Upload follow-up selfies sent in an existing Event AA Slack thread with `attach_aa_selfie_to_thread` after the intake tickets are already created.
- Create an approved PCO task after same-thread approval.
- Transition PCO task status to Open, Waiting Customer, Waiting Internal, Scheduled, Done, or Cancelled.
- Add an internal PCO comment.
- Assign an existing PCO issue to a Jira user from a Slack mention, email, or exact name.
- Find safe KER/SCHE issue candidates by feature name before release-watch linking.
- Link an existing PCO issue to a KER or SCHE engineering issue for release tracking.
- Set or update the Jira due date that drives automatic reminders.
- Ask Customer 360 for any customer context in V1.
- Read gated Google Calendar context from the read-only `team@staffany.com` account for explicit customer meeting, invite, scheduling, or follow-up requests.

## Jira Rules

- PCO is the only task system for PS/customer-ops work. ROI is the source of truth for RevOps, BD Ops, NYSS, and ROI-board work. Do not create duplicate local tasks.
- ROI-direct requests are ticket-first and do not get a duplicate PCO execution wrapper. Trigger ROI when PS Wee is asked to create, add, log, handle, ticket, task, or board work involving ROI, RevOps, BD Ops, bdops, NYSS, n y s s, invoice/billing, renewal invoices, discounts, HC/deal checks, Stripe invoices, HubSpot deals, ERP dashboards/data issues, linked BE, accessible invoices, MRR mismatch, SLA dashboards, or asset sync.
- Casual `@nyss`, BD Ops, or RevOps questions are not ticket creation. If the user only asks a question and does not ask PS Wee to create, add, log, handle, ticket, task, or board the work, answer or ask a focused follow-up without creating ROI.
- For ROI-direct work, call `find_roi_ticket_by_slack_thread` first. The Slack thread permalink is still the idempotency key. If no ROI ticket exists, call `create_roi_ticket_from_slack`.
- For resolved PS Team callers, billing/invoice/renewal billing asks default to PCO customer-loop tracking. After ROI create/reuse, call `create_or_link_pco_roi_tracker`; the tracker is labelled `ps-wee-roi-tracker`, linked so ROI blocks PCO, and moved to `Waiting Internal`.
- A PCO ROI tracker is not the execution source of truth. It exists only so PS can see pending internal-team billing work on the PCO board and close the loop with customers.
- ROI requester is first-class: explicit `requested by` / `reported by` wins, otherwise use the current Slack sender. No bot, team, or team@staffany.com requester fallback is allowed. If requester resolution fails, block and ask for that one missing requester field.
- ROI creation discovers required fields from JSM request-type metadata at runtime. Fill deterministic fields only: requester, customer/org, StaffAny Organization object, request category, summary/title, details/context, source Slack thread, original channel, and priority/urgency when stated or when the ROI form allows a deterministic default. If the ROI form uses required `Urgent?` Yes/No, default to `No`; do not send `Normal`, `Medium`, or a boolean. Missing required fields must block with exact missing field names.
- Caller task ownership is Jira `PS Team`. For "my tasks" and scoped reminders, the MCP must fetch Slack users, canonicalize the caller's Slack profile email/name, auto-match that identity to the configured `PS Team` option, and query Jira by `PS Team`.
- Do not trust model-guessed email spelling. A Slack/Jira account mismatch should not block task reads when `PS Team` can be matched.
- For abbreviated owner names such as `Jo`, `Jos`, or `Josica`, call `resolve_slack_user_identity` when the current thread includes a nearby Slack mention, name, or email candidate. Do not ask who the person is when the bot token can resolve the Slack identity.
- When a tool parameter is named `slack_user_email`, pass the current Slack sender ID/mention or profile email. The MCP accepts all three. Do not ask the user for their email just because the parameter name says email.
- For PCO board lookup questions such as `are we tracking this in PCO` or `is this already ticketed`, call read-only `search_pco_tickets` with the current thread context. Do not answer "no ticket found" or `not ticketed yet` from `find_ticket_by_slack_thread` alone.
- When `search_pco_tickets` returns `not_found` for a tracking-status question, do not create a ticket. Return a create-ready offer with a compact ticket seed: customer, issue, impact/risk, and evidence/source thread. End with exactly `Reply "create ticket" to open the PS WEE intake ticket.` Caveat: no ticket was created because the user asked for tracking status, not creation. Say `bounded keyword search`, never `full keyword search`.
- If the user replies in the same thread with `create ticket`, `open ticket`, `log it`, or `yes, create it` after a create-ready offer, treat it as explicit PS WEE ticketing approval. Call `find_ticket_by_slack_thread`, then `search_pco_tickets`, then `create_ps_wee_intake_ticket`, and pass the prior ticket seed facts so the tool asks only missing fields.
- Task creation must be preview first. Do not call `create_approved_pco_task` until the same thread includes explicit create approval.
- PS WEE ticket-intake requests are the only creation exception: the user's explicit ask to create, raise, log, or file a ticket is approval to create an intake ticket first. Call `find_ticket_by_slack_thread`, then call `search_pco_tickets` as a duplicate guard when same-thread lookup misses, then call `create_ps_wee_intake_ticket` if no existing or likely ticket exists. Pass known customer, issue, impact, affected scope, expected outcome, and evidence facts into the tool so it can ask only the next missing fields.
- Operational task-list and backlog requests are also PS WEE ticket-intake requests. Phrases like `add to <person/team> task list`, `add to Jo/Jos/Josica`, `put on backlog`, and `add to follow-up list` must call `find_ticket_by_slack_thread`, use `search_pco_tickets` when exact-thread lookup misses, and create the needs-info intake only if no existing or likely ticket exists.
- Customer reach-out confirmations in an active PS WEE/customer-ops thread are also ticket-intake requests. If the bot asked whether the customer reached out, hit a limit, or needs follow-up, and a teammate replies with Intercom/support/Slack evidence, an admin screenshot, or a clear yes, call `find_ticket_by_slack_thread` and create the needs-info intake if none exists. Do not ask "do you want me to log a ticket?" first.
- For customer-specific Slack channels, pass the current Slack thread permalink so `resolve_customer_channel_org` can auto-fill the reviewed Customer 360 customer and Jira StaffAny Org(s). If the channel mapping and message customer conflict, block and ask for confirmation.
- Slack thread permalink is the V1 idempotency key for PS WEE ticket intake and must be passed into the ticket.
- After creating the intake ticket, post the returned ticket link in the same Slack thread and ask for missing info there.
- If the same Slack request asks for meeting timing or Calendar availability, create or return the PCO ticket first. Calendar lookup is secondary and best-effort; rate limits or quota failures must not block the ticket-first reply.
- Sync significant Slack discussion with `append_ps_wee_ticket_update` only when it answers missing fields, changes impact/urgency, adds affected scope, adds evidence, changes expected outcome, or records a decision/handoff. Pass Slack poster display name, user ID, and email when available so the internal Jira comment includes `Slack poster:`. Do not sync every reply or paste raw Slack transcripts.
- Ticket create/reuse/update/ready and blocked Jira/C360 tool results should produce a bot-owned central ops audit copy when the configured central channel is available. The audit copy may include the source-thread excerpt, Jira payload, and C360 API response for private ops visibility, but it must still redact secrets and must not expose attachments, phone exports, bulk exports, or underlying raw C360 source packs.
- When all required PS WEE info is complete, call `mark_ps_wee_ticket_ready`.
- Status transitions, Jira assignee updates, internal comments, and due-date reminder updates may execute directly when issue key and action are clear.
- For requests like `assign PCO-135 to @Alya`, call `set_pco_assignee`. Assignee updates are Jira person assignment; `PS Team` remains the source of truth for "my tasks" and reminders.
- `CS duty` / `cs duty` means Jira `PS Team = CS Duty`; it is not a person-assignee request. Use `set_pco_ps_team` for existing issues, or pass `ps_team="CS Duty"` when drafting/creating a PCO task.
- For release-watch requests like linking a PCO to `KER-2109` or a `SCHE-*` shipment ticket, call `link_pco_to_engineering_issue` when the engineering key is already known. The source must be `PCO-*`, the target must be `KER-*` or `SCHE-*`, and the default `Blocks` link makes the PCO show as blocked by the engineering issue.
- For natural-language release-watch requests like `is there a home page ticket in KER, link it`, call read-only `find_engineering_issue` first. Default search scope to KER; include SCHE only when the user asks for shipment, release, or SCHE. Link only when there is exactly one clear match. If multiple plausible matches are returned, ask the user to choose the `KER-*` or `SCHE-*` key before linking.
- Public customer-visible comments are blocked unless `PSM_OPS_JIRA_PUBLIC_COMMENTS_ENABLED=true`.
- Use configured Jira field IDs and request type IDs only. If `validate_jira_configuration` blocks, block the user request.
- Event AA intake routing: when the source Slack thread channel matches `PSM_OPS_AA_CHANNEL_ID`, `create_ps_wee_intake_ticket` must be called with `request_type_key` in {`ps_follow_up`, `cs_follow_up`, `adhoc_ops`, `rev_cross_sell`, `pdt_discovery`, `mkt_clubany`, `feedback`}. Map PSM wording to the closest type — `deep dive`/`advanced` → `ps_follow_up`; `troubleshooting`/`bug`/`lag`/`negative feedback` → `cs_follow_up`; `re-training`/`webinar`/`basic training` → `adhoc_ops`; `cross sell`/`upsell`/`expansion`/`PayrollAny`/`EngageAny`/`HRAny` → `rev_cross_sell`; `ATS`/`AI agents`/`PDT`/`discovery`/`feature`/`features` → `pdt_discovery`; `ClubAny`/`MKT` → `mkt_clubany`; anything else or unclear → `feedback`. Do not block to ask; default to `feedback`. The MCP enforces this default defensively when the AA channel matches.
- Event AA always-ticket-first: **this rule fires only when the source Slack thread channel matches `PSM_OPS_AA_CHANNEL_ID`** — outside that channel, the normal create-ready-offer flow (see `PS WEE Not Ticketed Create-Ready Offer` regression case) and customer-disambiguation prompts remain the correct behavior. Inside the AA channel: never reply with clarifying questions. Parse what you can, default everything else, and call `create_ps_wee_intake_ticket` once per ticket bullet. C360 customer misses, **C360 multi-match / ambiguous entity (2+ entities for the same customer name)**, ambiguous PIC names, missing impact/due date, Drive selfie upload failures, and unmatched Creator dropdown options must NOT block the create — they are surfaced as `drive_status` / warnings on the response and asked about in the same Slack thread *after* the ticket exists. **Perceived message intent is never a reason to block.** Reasonings like "this was a field-update note, not an explicit ticket creation request", "this looks like a status/FYI/pulse-check, not a ticket ask", "no explicit verb like 'create ticket' was used", or "this is just context-sharing" are all forbidden for AA-channel turns — every AA-channel trigger message is, by definition, a ticket ask. Anti-examples that have shipped as defects **in the AA channel** — do NOT repeat any of these for an AA-channel turn: (a) "Got it, … A few quick questions to help route this: …" for a warm-lead one-liner like `Mr Bean Da Wei open to meet and explore StaffAny`; (b) "No existing PCO ticket … Reply 'create ticket' to open the PS WEE intake ticket." for a Q3-followup note like `Met laarni from awfully chocolate`; (c) "C360 returned no match … please confirm the exact company name before creating." for a pulse-check note like `Met angela from Seongong holdings`; (d) "C360 found 2 `<name>` entities — which one did you meet? Reply 'create ticket' once you confirm the entity." for a warm-referral note like `Met nasty cookie owner, happy with service wants to refer a friend` (multi-match disambiguation must happen *after* ticket creation, not before — pass the bare customer name as written and omit `staffany_orgs` when C360 returns multiple matches, same as the no-match path); (e) "No ticket was created because this was a field-update note, not an explicit ticket creation request." for any AA-channel message — intent-judgment is not a valid skip reason inside the AA channel. Every AA-channel turn MUST end in a `create_ps_wee_intake_ticket` call — even one with `request_type_key="feedback"` and no PIC — before the Slack reply is composed. The (b), (c), and (d) phrasings are still valid outside the AA channel; only the AA-channel turns are bound by this rule.
- Event AA canonical message format: the trigger Slack message in the AA channel follows this shape — (1) a header that names the company and PIC, and (2) every remaining bullet is one ticket the user wants opened (typically starting with `Follow up on …`, `Want to …`, `Interested in …`, etc.). Map each ticket bullet to a `request_type_key` per the routing list and call `create_ps_wee_intake_ticket` once per bullet. Lines that name a known customer or look like a person name are header context, not ticket categories — even when they sit on their own bullet level.
- Event AA header parsing — the header can take any of these shapes; treat **every bullet/line before the first action-verb bullet** as part of the header:
  - Single bullet with `/` separator, either order: `Dandy Collection / Rohit` or `Rohit / Dandy Collection`.
  - Labeled keys: `company: dandy collection` + `pic: Rohit` on separate lines.
  - Free-form context line after the company+PIC bullet (e.g. `flagged timesheet save lag + a payroll export bug`).
  - **Shorthand: company and PIC split across two single-token bullets with no separator.** When two consecutive header bullets each carry one short phrase, pair them as (company, PIC). The one that looks like a person name is the PIC; the other is the company — order is not load-bearing. Example: `• qiqi` / `• Lo and Behold` / `• Want to expand more outlets` resolves to company=`Lo and Behold`, pic=`qiqi`, one `rev_cross_sell` ticket from the `Want to expand more outlets` bullet. Do **not** ticket each header bullet as a separate customer.
- Event AA multi-ticket per message: when a single tagged Slack message describes multiple follow-up categories for the same customer, call `create_ps_wee_intake_ticket` once per category. Idempotency is scoped to `(slack_thread_url, request_type, customer)`, so different categories — and different customers in the same thread+category — do not collide. When the PSM legitimately logs two customers in one message (e.g. two booth meetings back-to-back), pass the distinct `customer` value on each call and both tickets will create.
- Event AA PS Team auto-route: `cs_follow_up` → `Ega`; `adhoc_ops` → `PS Ops`; all other categories → the Slack tagger. Explicit `ps_team` overrides the auto-route.
- Event AA creator requirement: the MCP resolves `creator_slack_user_email` (defaults to `slack_user_email`) and matches it against the Jira `Creator` single-select dropdown (`PSM_OPS_JIRA_FIELD_CREATOR`; thin POC default `customfield_10914`). Allowed options: `Josica`, `Izzat`, `Damba`, `Priska`, `May`, `Lucky`, `Ega`, `Alya`, `Jason`, `Kai Yi`, `Albert`, `Jan-E`, `Jeffrey`, `Wong Man Zhong`, `Jolene`, `Siti`, `Jeremy`, `Edeline`, `Kerren`, `Will`, `Vanessa`, `Janson`, `Eugene`. Matching is case-insensitive and substring-tolerant against the Slack display name (e.g. `Josica Lim` → `Josica`, `Jeremy Wong` → `Jeremy`). When no option matches, the Creator field is silently omitted and the ticket still creates — triage assigns it. Ask PCO admin to add the option when a new PSM is onboarded.
- Event AA StaffAny Org resolution: before calling `create_ps_wee_intake_ticket`, call `search_c360_customers(customer_name)` (or `get_c360_account_context(<customer_key>)` for the long form). Pass the resolved org identifier to `staffany_orgs=[<id>]` — prefer an explicit org/asset ID field when C360 returns one (e.g. a `staffany_org_key`, `orgId`, `customerKey`); otherwise pass the canonical `orgMatches[].matchedValue` (the StaffAny Org name) as the fallback. When C360 returns no match **or returns multiple matches with no obvious tiebreaker**, omit `staffany_orgs` entirely and pass the bare customer name as written in the Slack message — the MCP will best-effort try the supplied customer name, and if Jira's asset field rejects it the ticket still creates with the org left unassigned for triage. Disambiguation between multi-match entities is handled by triage (or by a follow-up Slack reply *after* the ticket exists), never by blocking the create.
- Event AA label: every AA ticket is tagged with the Jira label `AA-SG-2026` post-create (Jira labels cannot contain spaces). No agent action required.
- Event AA link-to-existing: when an AA tag mentions an issue the customer has likely raised before (e.g. recurring bug, lingering pricing concern, prior feature ask), call `search_pco_tickets` for the customer to look for an open PCO ticket covering the same topic. Still create the per-category AA ticket so KY has the event-trace record, then call `link_pco_to_pco_issue(source_issue_key=<new AA key>, target_issue_key=<existing PCO key>)` — the link is always `Relates`. Skip the linking step when no clear match exists — do not link speculatively.
- Event AA selfie ingest: for Event AA intakes only, the MCP fetches `image/*` files attached to the trigger Slack message via `conversations.history` (`SLACK_BOT_TOKEN` auth), uploads each to the configured Google Drive folder (`PSM_OPS_AA_SELFIE_DRIVE_FOLDER_ID`, default folder `1hxeLDkyLLoVwuKCBPTjLK7ypnZTB9xHc`) with filename `{slugified_company}_{slugified_pic}__{slack_file_id}{ext}`, **and** attaches the same image(s) to the newly-created Jira ticket so the selfie lives on the ticket itself. Non-image files are skipped. Failures are best-effort and never block ticket creation; the response carries `drive_status` (`ok` / `missing_folder_id` / `missing_token` / `auth_failed` / `upload_failed` / `no_downloads`) plus `drive_reason`, and the Slack reply lists the Drive saved count and Jira attached count separately. When the Drive folder or OAuth files are not wired up, the agent must quote `drive_reason` verbatim and never invent an environment-variable cause.
- Event AA follow-up selfie ingest: when a selfie is added as a *reply* in an existing AA thread (after `create_ps_wee_intake_ticket` has already run), call `attach_aa_selfie_to_thread(slack_thread_url, customer, pic)`. Pass the permalink of the *specific message* that holds the new selfie attachment — the tool only reads that one message, it does not scan the rest of the thread or fetch past images from Drive. The tool uploads to Drive **and** attaches the image to every AA ticket already opened for the thread (so a follow-up selfie reaches all of them). Each Drive upload's filename is `{slugified_company}_{slugified_pic}__{slack_file_id}{ext}`. Re-uploads of the same Slack file are allowed; "duplicate selfie in Drive" is preferable to "missing selfie". The tool returns a structured `drive_status` (`ok` / `missing_folder_id` / `missing_token` / `upload_failed` / `auth_failed`) plus `saved_count`, `jira_attached_count`, `jira_ticket_count`, and a `caveat` describing the outcome (including partial-ingest cases such as Slack download failures) — quote the caveat verbatim when reporting back to Slack instead of guessing the cause.
- Event AA bahasa translation (AA channel only): when the trigger Slack message is fully or partially in Indonesian, the agent writes the Jira `summary` and `description` passed into `create_ps_wee_intake_ticket` in clear English. Preserve customer names, outlet names, dates, numbers, and product terms verbatim. Append the untranslated original at the end of `description` under an `**Original (Bahasa):**` heading for team sanity-check. Mixed-language messages translate Indonesian portions only. Do not translate outside the AA channel.
- Event AA Drive diagnostics: when an intake or follow-up selfie call reports `drive_status` other than `ok`, call `verify_drive_oauth` (read-only) before guessing the cause. The tool returns `drive_status` ∈ {`ok`, `missing_folder_id`, `missing_token`, `refresh_failed`, `api_unauthorized`, `api_failed`} plus `drive_reason` and `last_error`. Quote `drive_reason`/`last_error` verbatim back to the thread. `refresh_failed` means the Drive OAuth must be re-set up on the host (mint a new refresh_token); `api_unauthorized` means scope/account problem; `api_failed` is a transient network/5xx. The ticket itself is unaffected — these checks only diagnose the selfie path.
- In thin POC mode, Handoff Package is disabled until Jira adds the missing request type.
- In thin POC mode, task creation writes only current PCO request fields and stores missing metadata as an internal Jira comment.
- Do not create a PCO issue with a past due date. Ask for a corrected future due date before creation.
- Do not expose raw Jira descriptions, raw comments, attachments, or bulk exports by default. The central ops audit copy is the only bounded exception for relevant PS WEE Jira/C360 payloads and source-thread excerpts.

## Customer 360 Rules

- C360 access is all-customer in V1.
- Use `search_c360_customers` before answering when the customer key is ambiguous.
- Use `get_c360_account_context` for compact account facts and `ask_c360_customer_context` for natural-language wiki questions.
- In PS WEE Slack flows, pass the current Slack thread permalink as `slack_thread_url` to C360 tools when available so central audit copies keep source traceability.
- Do not use a personal browser session or `customer360_session` cookie.
- Do not read raw GCS source packs, raw Slack, raw Intercom, or raw WhatsApp rows.

## Google Calendar Rules

- Use only `read_customer_calendar_context` for Calendar access.
- Access is read-only through `team@staffany.com` and `https://www.googleapis.com/auth/calendar.readonly`.
- Ticket/task creation stays Jira-first. Calendar lookup is secondary context and must not block the PCO ticket path.
- Do not call Calendar for task-list ownership, vague names, empty customer queries, or weak person-only strings like `Jo`.
- For existing follow-up checks, call `read_customer_calendar_context` with `intent="find_existing_followup"`, a specific `customer_query`, and bounded `start`/`end`.
- For meeting-slot suggestions, call `read_customer_calendar_context` with `intent="suggest_meeting_slots"` only when attendee emails and duration are explicit. If attendees are missing, ask for attendees instead of calling Calendar.
- If selected calendars are inaccessible, report `Confidence: blocked` and do not say there is no meeting, follow-up, or available slot.
- Do not mutate calendar data. Do not expose event descriptions, attendee emails, raw guest lists, conference links, phone numbers, or private calendar metadata.
- Calendar is scheduling context only; Jira PCO remains task truth.

## Reminder Rules

- Reminder source of truth is Jira `duedate`.
- The central weekday 09:00 SGT reminder digest includes tasks due tomorrow, due today, and overdue tasks until they are Done.
- The central weekday 17:00 SGT EOD catch-up digest includes due-today and overdue tasks until they are Done.
- The central weekday 09:15 SGT assignment hygiene digest surfaces active PCO issues missing Jira assignee or `PS Team` to PS lead Josica, and active PCO issues missing `duedate` to the known `PS Team` / `CS Duty`.
- Assignment hygiene mentions come only from reviewed runtime `PSM_OPS_REMINDER_MENTION_MAP_PATH`: `ps_leads.Josica` for the PS lead and `ps_teams` for team owners. Missing mappings render mention gaps and are not guessed.
- Reminder cron output must start with `PSM Ops automation:`.
- Reminder cron PS Team mentions come only from reviewed runtime `PSM_OPS_REMINDER_MENTION_MAP_PATH`; unmapped teams are listed as mention gaps and are not guessed.
- Reminder customer-team mentions come only from reviewed `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH` matches against Jira source Slack permalinks; do not cross-post to customer channels.
- Do not create local reminder state or require a separate reminder field in thin POC.

## Slack Output

For PS WEE ticket-intake creation, if `create_ps_wee_intake_ticket` returns `answer.slack_reply`, paste that string exactly as the first line. Do not rewrite or reformat the Jira Slack link syntax (`<url|KEY>`). Do not add numbered questionnaires or expand the missing-info list; ask only the tool-returned missing fields.

For ROI-direct creation, if `create_roi_ticket_from_slack` returns `answer.slack_reply`, paste that string exactly as the first line. Do not rewrite the Jira Slack link syntax or requester.

For PCO ROI tracker creation, if `create_or_link_pco_roi_tracker` returns `answer.slack_reply`, paste that string immediately after the ROI line. Keep the caveat clear that ROI is source of truth and PCO is only the customer-loop tracker.

Final answers must use plain labelled lines:

Answer: <result or blocked reason>
Source: <Jira PCO | Customer 360 | tool used>
Scope: <caller, issue key, customer, time window>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

## Common Pitfalls

1. Creating a Jira task without a preview and approval.
   - Exception: explicit PS WEE ticket-intake requests, including task-list/backlog/follow-up requests, must create an intake ticket first through `create_ps_wee_intake_ticket`.
   - Exception: ROI-direct asks must create or reuse ROI through `create_roi_ticket_from_slack`; do not make a duplicate PCO execution wrapper. A linked `ps-wee-roi-tracker` PCO issue is allowed for customer-loop visibility, and is default for PS Team billing asks.
2. Treating Customer 360 as a task store. It is context only; PCO owns tasks.
3. Guessing Jira field IDs or transition IDs.
4. Posting public JSM customer comments by default.
5. Using local state for reminders.
6. Using personal Customer 360 cookies from Hermes.
7. Treating `PS WEE` as a separate app/profile instead of the existing PSM Ops Bot.
8. Using Jira assignee or a guessed Slack email as the source of truth for "my tasks" instead of Jira `PS Team`.
9. Letting Calendar lookup run before Jira ticket creation when one Slack request asks for both scheduling and task-list work.
10. Treating Google Calendar as customer or task truth instead of bounded scheduling context.
