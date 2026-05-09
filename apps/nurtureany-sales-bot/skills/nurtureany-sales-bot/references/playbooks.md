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
- Lost-deal re-nurture
- Missing direct contact
- High-value dormant account

## Drafting Rules

- Draft for manual AE review only.
- Keep WhatsApp drafts short and specific.
- Keep email drafts structured but not marketing-heavy.
- Keep LinkedIn drafts light and relationship-led.
- Use the contact persona and account trigger in the first sentence where possible.
- Do not invent facts, incentives, relationships, or prior conversations.
- Do not include raw phone numbers or unnecessary contact details in Slack output.

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

