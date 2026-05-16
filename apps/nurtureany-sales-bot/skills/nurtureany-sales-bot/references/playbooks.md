# Nurture Playbooks

## Enrichment Tiers

| Tier | Definition | Bot behavior |
| --- | --- | --- |
| Not enriched | Missing owner, renewal/contract timing, contact, decision maker, persona, or channel fit. | Return missing fields and recommend enrichment task. |
| Minimum enriched | Target account with owner, country, ICP/headcount, industry, renewal or contract timing, at least one contact, and at least one decision maker. | Can enter nurture scoring queue. |
| Nurture-ready enriched | Minimum enriched plus persona, channel fit, contact freshness, and enough context to draft a useful message. | Draft manual message and preview HubSpot task/note updates. |

## Priority Signals

Rank only accounts inside the caller's allowed scope.

Primary signals:

- Target account is true.
- Commercial value or MRR from C360.
- Contract end or renewal timing.
- Deal stage and post-demo status.
- Last sales activity age.
- Contact coverage and direct decision-maker availability.
- Event invite, RSVP, attendance, or missed-follow-up context.
- Lost-deal recency.
- Manual AE priority or prospecting-account signal.

Use `needs-check` confidence when any major scoring input is missing, inferred, stale, or from a candidate mapping.

## Suggested Segments

- Renewal / contract-end alert
- Pre-demo target account
- Post-demo ongoing deal
- Event invite / RSVP chase
- Post-event attended follow-up
- Event no-show follow-up
- Lost-deal re-nurture
- Missing direct contact
- High-value dormant account

## ICP And Persona Angles

Use these as framing guidance only. HubSpot and approved live tools still decide target-account scope, owner, country, contact coverage, current tools, and follow-up status.

| Segment | Useful angle |
| --- | --- |
| SG headcount >20 / MY or ID headcount >50 | Possible fit; check industry, outlet count, current tools, and timing before investing heavy effort. |
| SG headcount >50 / MY or ID headcount >100 | Good-fit ICP; prioritize persona-specific pain and value proof. |
| ICP 0 | Move fast, disqualify when needed, or route to freemium/light-touch rather than deep nurture. |
| ICP 1-2 | Farmable low-hanging fruit; use practical pain around scheduling, attendance, timesheets, and scaling process. |
| ICP 3 | Relationship-led nurture; map HR, Ops, Finance, and director stakeholders before pushing for a close. |
| Owner / founder | Cost control, visibility, scale, auditability, and reduced unnecessary labour hours. |
| HR manager / HR ops | Timesheet consolidation, payroll accuracy, compliance, leave reports, and fewer disputes. |
| Ops / outlet manager | Scheduling, last-minute changes, staffing visibility, cross-outlet coordination, and attendance issues. |
| Staff-facing concern | Timesheet transparency, mobile clock-in/out, fewer discrepancies, and trust. |

## Drafting Rules

- Draft for manual AE review only.
- Keep WhatsApp drafts short and specific.
- Keep email drafts structured but not marketing-heavy.
- Keep LinkedIn drafts light and relationship-led.
- Use the contact persona and account trigger in the first sentence where possible.
- Do not invent facts, incentives, relationships, or prior conversations.
- Do not include raw HubSpot phone fields or unnecessary contact details in draft/queue Slack output. Selected Lusha or Prospeo reveal is the only raw-number exception, and only after explicit approval with `approval_marker` plus `reveal_phones=true`.

## Daily Nurture Material Registry

Use one read-only Google Sheet as the material database. Tabs:

- `Materials`
- `Playbooks`
- `Peer Intros`
- `Speaker/Venue Opportunities`
- `Events`
- `Review Log`

Minimum fields: `material_id`, `category`, `title`, `url`, `status`, `country_scope`, `industry_tags`, `concept_tags`, `persona_tags`, `valid_from`, `valid_until`, `template_name`, `template_params_schema`, `message_hook`, `owner`.

Allowed material categories include podcast, case study, same-industry/same-concept proof, event invite, community matching, talent matching, collaboration opportunity, speaking opportunity, fireside speaker or podcast speaker ask, future-speaker sourcing, venue opportunity, salary benchmark, fireside chat learning, and warm peer intro. Approved public case studies can stay in the repo catalog; Sheet rows may reference case-study IDs for matching.

For Network KNS, use the registry and Luma only as source context. `Events`, `Peer Intros`, and collaboration rows can support AE-selected suggestions, but they do not prove attendance frequency, active supporter status, product adoption, intro willingness, or a "top 5 community members" match unless those fields exist in a real community-member source.

Jeremy daily nurture automation is disabled pending refinement and confirmation. Do not advertise a ready daily-pack workflow, 09:00 cron, noon reminder, or Eazybe-ready automated run until the workflow is approved again.

## HubSpot Action Planning

For each selected account, preview:

- Task owner.
- Associated company and contact.
- Due date.
- Suggested channel.
- Draft message.
- Rationale.
- Field updates.
- Note summary with source evidence and approval marker.

Do not execute any write until the AE or authorized manager approves the preview.
