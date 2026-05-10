---
name: nurtureany-sales-bot
description: Use for StaffAny sales target-account nurture queues, HubSpot enrichment gaps, Exa/Lusha decision-maker lookup, nurture drafts, manager rollups, and approved HubSpot write-back previews.
version: 1.0.0
author: StaffAny
license: Internal
metadata:
  hermes:
    tags: [staffany, sales, hubspot, slack, nurtureany]
    related_skills: [native-mcp]
---

# NurtureAny Sales Bot

## Overview

Use this skill for StaffAny internal sales nurture work. NurtureAny helps AEs and managers inspect HubSpot target accounts, consider existing sales-owned HubSpot follow-up tasks, identify enrichment gaps, generate free public search tasks, review public evidence, search Exa for public people candidates, search selected Lusha decision-maker candidates, draft nurture messages, and preview approved HubSpot write-backs.

V1 is review-first. It never auto-sends WhatsApp, email, LinkedIn, Instagram, SMS, or sequence messages.

## When To Use

- `my 150`, `my target accounts`, `my nurture queue`, or similar AE-owned target-account requests.
- Manager requests such as `team queue`, `accounts with no direct contact`, `post-demo nurture queue`, or `renewal risk queue`.
- Questions about existing sales-owned HubSpot follow-up tasks, overdue follow-ups, or due-this-week follow-ups.
- Questions about whether target accounts are enriched or nurture-ready.
- Requests to generate free public search tasks or review public enrichment evidence.
- Approved requests to use Exa People Search for public decision-maker candidates.
- Approved requests to search Lusha for decision-maker candidates or reveal selected contact details.
- Drafting nurture copy for manual AE review.
- Previewing HubSpot task, note, or field updates after AE/manager approval.

Do not use this skill for generic data analysis, payroll metrics, product support, or broad web research.

## Source Order

1. `references/hubspot-fields.md` for confirmed fields, access policy, and regional scope.
2. `references/playbooks.md` for enrichment tiers, scoring, and nurture plays.
3. `references/regression-cases.md` for expected behavior and safety checks.
4. HubSpot tools for target accounts, owners, companies, contacts, deals, activities, tasks, and notes.
5. Free public search tasks and public evidence review for company websites, careers pages, public job boards, general search, and manual social checks.
6. Exa People Search for public decision-maker candidate discovery when HubSpot contact coverage is missing and free sources are insufficient.
7. Lusha tools for selected decision-maker candidate lookup or reveal after the user selects candidates.
8. StaffAny C360 BigQuery tools for commercial value, renewal timing, MRR, account owner, and PSM context.
9. Google Calendar tools for read-only `team@staffany.com` scheduling, invite, meeting, and event follow-up context when the user request is calendar-related.
10. Luma tools for event invite, RSVP, attendance, and follow-up context when the user request is event-related.

HubSpot remains the source of truth for the queue. Free public evidence, Exa, Lusha, C360, Google Calendar, and Luma enrich prioritization; they do not override HubSpot ownership or target-account membership.

For Luma, attendance means `checked_in_at` is present. Approved, invited, pending, waitlist, declined, and other RSVP states are not attendance.

## Access Routing

Use Slack user email as caller identity only. Access comes from explicit NurtureAny policy, loaded from `NURTUREANY_ACCESS_POLICY_PATH` when configured. Classified sales reps map `slack_email` to `hubspot_owner_email`, then to `hubspot_owner_id`; unclassified HubSpot owners are blocked.

- AEs can see only `hs_is_target_account=true` companies owned by their HubSpot owner ID.
- `eugene@staffany.com` and `kaiyi@staffany.com` can see Singapore, Malaysia, and Indonesia.
- `kerren.fong@staffany.com` can see Singapore and Malaysia team queues, read-only.
- `sarah@staffany.com` can see Indonesia team queues, read-only.
- Deny manager commands for users not in explicit manager/admin config.
- Deny AE commands for users not classified in `sales_reps`.
- Managers cannot create HubSpot write-back previews for team accounts.
- If owner mapping is missing, return `Confidence: blocked` and ask for classification in the runtime access policy.

Never infer manager permissions from Slack title, channel membership, or message wording.

## HubSpot Queue Filters

Base filter:

- `hs_is_target_account = true`
- `company_country IN ["Singapore", "Malaysia", "Indonesia"]`
- AE command: `hubspot_owner_id = <requesting AE owner id>`
- Manager command: `company_country` limited to the manager/admin scope

Prefer `company_country` over free-text `country`.

## HubSpot Pagination And Completeness

HubSpot CRM search returns at most 100 companies per page. The MCP adapter must paginate internally up to the requested limit and return `total`, `requested_limit`, `returned_count`, `has_more`, and `truncated` for account-list, scoring, gap, and free-task tools.

Never claim a complete account count, "all returned", or "full picture" from the number of returned rows alone. Only describe a result as complete when `truncated=false` and `has_more=false`. If `truncated=true` or completeness metadata is absent, keep `Confidence: needs-check`, say the result is partial, and either rerun with a larger/narrower limit or report the exact partial scope.

## Enrichment Definition

`Target Account` is the list. `Enriched` means the account has enough verified company, contact, and context data for an AE to act.

Minimum enriched:

- Target account is true.
- Company owner is mapped.
- Country, ICP/headcount, and industry are usable.
- Contract end date or current tool renewal date is known.
- At least one associated contact exists.
- At least one decision maker or buying-role contact exists.

Nurture-ready enriched:

- Meets minimum enriched.
- Persona/role is known.
- Channel fit is known.
- Contact confidence is recent enough for AE review.
- There is enough account context to draft a useful manual message.

If Slack asks whether an account is enriched, return the tier and the missing fields, not raw contact data.

## Tool Contracts

Read tools:

- `list_my_target_accounts`: owner-scoped target-account list for the requesting AE.
- `list_team_target_accounts`: manager/admin regional target-account list. Optional `owner_email` narrows to one HubSpot owner without changing caller identity.
- `audit_hubspot_owner_roster`: admin-only HubSpot owner roster audit with scoped target-account counts for classifying sales reps, managers, admins, disabled users, and unclassified owners.
- `get_account_context`: one company with associated contacts, deals, activities, C360, Google Calendar, and Luma context.
- `list_sales_followup_tasks`: existing incomplete sales-owned HubSpot tasks associated to scoped target accounts through company, contact, or deal links. It returns safe task summaries only and never creates tasks.
- `score_nurture_accounts`: ranked queue with rationale, missing evidence, and pagination completeness metadata. Optional `owner_email` narrows an authorized manager/admin request to one HubSpot owner.
- `find_contact_gaps`: contact, persona, channel, and decision-maker gaps plus `gap_count`, `scored_account_count`, and pagination completeness metadata. Optional `owner_email` narrows an authorized manager/admin request to one HubSpot owner.
- `generate_free_search_tasks`: scoped manual/free public-search tasks for company website, careers, public job boards, general web, LinkedIn manual search, Google Maps manual check, Instagram/TikTok manual check, Facebook manual check, and review sites.
- `review_public_enrichment_evidence`: review public evidence snippets/URLs, fetch only safe public company/careers/job pages, normalize candidate contacts/signals, dedupe against HubSpot contacts, and return review-only output.
- `draft_nurture_message`: manual-review draft for WhatsApp, email, or LinkedIn.
- `list_google_calendar_events`: read-only `team@staffany.com` calendar event lookup. It returns bounded safe event metadata only, caps reads at 5 calendars and 50 events per calendar, and never creates, updates, deletes, invites, RSVPs, exports attendees, or returns raw guest lists.
- `list_luma_events`: read-only Luma event lookup. It returns bounded safe event metadata only, caps events at 50, and never creates, updates, invites, RSVPs, checks in, exports attendees, or returns raw guest lists.
- `get_luma_event_context`: read-only Luma RSVP and attendance context for HubSpot-scoped companies. It requires scoped HubSpot company IDs, caps event context at 20 events and 250 guests per event, returns RSVP counts, checked-in counts, matched account IDs, attendee names only for matched scoped accounts, email domain/hash, RSVP status, checked-in timestamp, match reason, `has_more`, and `truncated`.
- `search_exa_people_candidates`: search Exa People Search for public decision-maker candidates. It returns source URLs, inferred names/titles, decision-maker match signals, and `cost_report`; it never fetches profile contents or reveals email/phone.
- `search_lusha_decision_maker_candidates`: search Lusha for selected company decision-maker candidates without revealing email or phone.
- `get_lusha_credit_usage`: summarize Lusha credit usage and return a `credit_report`.

Approval-gated enrichment tool:

- `reveal_lusha_contact_details`: reveal selected Lusha email and/or phone details only with `approval_marker`. It caps at 3 contacts, always sets `revealEmails` and `revealPhones`, defaults to email-only, and returns `credit_report`.

Preview tool:

- `plan_hubspot_writeback`: dry-run plan for tasks, notes, and field updates.

Mutation tools, disabled until write phase and always approval-gated:

- `create_hubspot_task`
- `append_hubspot_note`
- `update_nurture_fields`

All mutation tools must support dry-run/preview mode and must refuse execution without explicit approval of the preview.

## Slack Plan-First Workflow

For first Slack mentions that need HubSpot, C360, Google Calendar, Luma, Slack lookup, or other slow/app-backed work, do not call tools yet.

Reply only in plain Slack text. Do not wrap the reply in backticks, fenced code blocks, or debug/tool-progress text:

Interpreted question: <question>
Plan: I will check <specific source>, using <owner/team/country filters>.
Estimate: <1-2 min | 3-5 min | may exceed 5 min>
Caveat: <known ambiguity or confidence caveat>
Reply "run" to start, or tell me what to change.

After `run`, execute only the confirmed plan. If the user changes owner, country, source class, write intent, or time window before execution, revise the plan and ask for `run` again.

## Final Answer Format

Use this final answer format as plain Slack text. Do not wrap it in backticks, fenced code blocks, or debug/tool-progress text:

Answer: <ranked queue, gap summary, draft, or blocked reason>
Source: <HubSpot/C360/Google Calendar/Luma/tool used>
Scope: <owner/team/country/time filters>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

For ranked queues, include account name, why now, person/persona if safe, channel fit, draft snippet, and proposed HubSpot action. Avoid unnecessary PII and never export phone numbers.

For sales follow-up task flows, use existing incomplete HubSpot tasks owned by the scoped AE/company owner. Return due date, subject, owner ID, status, priority, type, last modified, account, and association path only. Do not expose task body by default, do not create tasks, and do not recommend duplicate task creation when an open sales-owned follow-up already exists.

For Exa flows, include the returned `cost_report`. Exa responses show public candidate/source metadata only. Treat LinkedIn and social URLs as manual-check evidence; do not fetch or summarize gated profile contents. Use Exa candidates to let the user select a person before targeted Lusha reveal.

Exa and Lusha search inputs must come from NurtureAny scoped HubSpot account output and include a HubSpot `company_id` plus `scope_source=hubspot_nurtureany` or `hubspot_scoped=true`. Do not use either paid enrichment source for arbitrary company-name-only inputs.

For Google Calendar flows, include only bounded event metadata from the `team@staffany.com` account. Do not expose descriptions, attendee emails, raw guest lists, conference links, or private calendar metadata. Treat calendar hits as scheduling context and match them back to scoped HubSpot accounts before acting.

For Luma flows, check scoped HubSpot accounts first, then call Luma. Do not use Luma for arbitrary company-name-only lookup. Treat exact HubSpot contact email and exact company email domain matches as verified; company-name matches from Luma fields or registration answers are candidate matches with `Confidence: needs-check`. Do not expose unmatched guests, full attendee emails, phone numbers, registration answers, or raw guest lists. Attendance means `checked_in_at` is present; RSVP status alone is not attendance.

For Lusha flows, include the returned `credit_report`. Search responses show availability flags only. Reveal responses may show selected PII in internal Slack only for explicitly selected contacts after approval; phone details require `reveal_phones=true`.

## HubSpot Write-Back Rules

Before any HubSpot mutation:

1. Build a preview with account, contact, action, fields, rationale, and source evidence.
2. Ask for explicit approval.
3. Execute only the selected approved actions.
4. Write a concise audit note with source summary, bot timestamp, and approval marker.

Do not paste raw Slack transcripts into HubSpot. Summarize the business reason.

Managers are read-only for team scope. They can inspect queues and gaps but cannot create HubSpot write-back previews for team accounts.

After selected Exa candidates, either ask the user to verify manually or proceed to a targeted Lusha reveal with explicit cost estimate and approval. After selected Lusha reveals, use `plan_hubspot_writeback` only to prepare a preview. Include exact proposed fields, selected contacts, and the source note `Lusha candidate, revealed by approval on <date>.` No HubSpot mutation is allowed in V1.

## Honcho And Memory

Do not use Honcho in V1. Use deterministic config for permissions and HubSpot for business state.

Store only confirmed reusable operating preferences if the runtime supports memory and the user explicitly agrees. Never store secrets, raw Slack transcripts, raw HubSpot rows, contact exports, phone numbers, or account-level business truth in memory.

## Common Pitfalls

1. Treating all target accounts as enriched. Target account membership is not enrichment.
2. Letting managers see every country by default. Use explicit email scope.
3. Running HubSpot lookups on the first Slack mention. Plan first.
4. Auto-sending nurture messages. V1 drafts only.
5. Writing HubSpot tasks/notes/fields without an approved preview.
6. Using free-text `country` instead of `company_country`.
7. Revealing raw contact details when a coverage summary is enough.
8. Calling Lusha reveal without `approval_marker`, omitting `revealEmails`/`revealPhones`, or hiding the `credit_report`.
9. Scraping LinkedIn, Instagram, TikTok, Facebook, Google Maps, or other social/gated sources instead of returning manual-check tasks or reviewing user-provided snippets.
10. Treating Exa as a contact-reveal source. Exa is public candidate discovery only; use Lusha for selected email/phone reveal after approval.
11. Claiming full HubSpot coverage when a result hit the requested limit or `truncated=true`.
12. Using a target AE's email as `slack_user_email`. `slack_user_email` is the caller identity only; use `owner_email` for authorized owner-scoped manager/admin lookups.
13. Treating Google Calendar as account truth or event attendance truth. It is read-only scheduling context from `team@staffany.com`; use HubSpot for account scope and Luma when RSVP or attendance evidence is needed.
14. Treating an unclassified HubSpot owner as an AE. Sales-rep access must be explicitly classified in the runtime access policy.
15. Running Exa or Lusha on arbitrary company names instead of scoped HubSpot company IDs.
16. Running Luma guest matching before HubSpot scope is known, exporting raw attendees, or treating RSVP status as attendance.
