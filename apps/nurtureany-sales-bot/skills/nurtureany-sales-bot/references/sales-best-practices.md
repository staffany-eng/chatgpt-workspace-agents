# Sales Best Practices

Use this reference before answering NurtureAny sales workflow requests involving drafting, Friday reviews, pre-demo plans, event follow-ups, coaching summaries, QO/QO Met quality, account coverage, or operating-rhythm advice.

## Source Order

1. HubSpot and live tool outputs are the source of truth for target-account membership, owner, country, contract end date, current tools, follow-up status, calls, meetings, tasks, and deals.
2. Current/final Leadership Tactical Pause material is the source of truth for operating rhythm, account coverage, QO quality, warm activity, event discipline, and Friday correction.
3. Current instructor-copy training material and current sales rubrics are the source of truth for outreach, pre-demo, demo, post-demo, and coaching standards.
4. Current onboarding plans, master templates, and assessment materials are supporting evidence for ramp, testing, certification, and coaching.
5. Old, copy, archived, outdated, or trainee files are lower-authority context. If they conflict with current/final/instructor material, surface the conflict and use the higher-authority source.

Do not build a new MCP for this guidance. In Hermes, configured MCP servers are discovered from `mcp_servers` and registered as first-class tools. This document is a Hermes skill reference, not a native MCP server.

## HubSpot Override Rule

Training and Tactical Pause docs never override live HubSpot fields or tool outputs for:

- target account: `hs_is_target_account`
- owner: `hubspot_owner_id` resolved through HubSpot owners API
- country: `company_country`
- contract end date: `contract_end_date`
- current tools: `current_tools`
- follow-up status: HubSpot communications, notes, tasks, and meetings
- calls: HubSpot calls
- meetings: HubSpot meetings
- deals: HubSpot deals and configured QO/QO Met/closed-won stages

When facts are missing, write `needs-check` instead of inventing them.

## Operating Rhythm

- Each AE works from a protected 150-account pool. Account swaps should be deliberate and manager-approved.
- Weekly coverage target is 120 of 150 priority accounts.
- `120/150` means weekly coverage of 120 accounts out of the protected 150-account pool. It is not a different SG/MY ownership cap, and it should not be restated as "120 owned accounts."
- Daily rhythm includes 30 WhatsApp nurturing touches, usually around the morning nurture block.
- Use double taps where the account is active and the next step is worth pursuing.
- Use 40 connected calls as weekly discipline where calling is an appropriate channel.
- Friday review is a correction mechanism. It should call out missed coverage, weak QO quality, stale follow-up, dirty accounts, and next-week correction.
- Clean data comes before AI: capture calls, meetings, notes, trackable channels, and CRM updates before automation advice.

## Market Guidance

- SG: prioritize pipeline quality, inbound routing, meeting efficiency, QO-to-QO-Met, and closing quality.
- MY: apply the same CCC, CBANT, I-C-BANT, demo, and follow-up standards; use onboarding materials for ramp context.
- ID: prioritize activity-to-QO efficiency. Bahasa Indonesia case material can support localized coaching. Do not force SG call-heavy assumptions where WhatsApp, events, or referrals are stronger local evidence.
- Cross-market: choose playbooks from ICP, industry, headcount, current tools, contract end date, lead source, buying role, and why-now signal.

## ICP And Value Framing

- Use ICP stage, country headcount, industry, outlet count, maturity, persona, and JTBD before choosing the angle.
- Training threshold guide: SG below 20 headcount is no-fit, above 20 is possible fit, and above 50 is good fit; MY/ID below 50 is no-fit, above 50 is possible fit, and above 100 is good fit.
- ICP 0 should be disqualified or moved fast; ICP 1 and ICP 2 are farmable; ICP 3 requires relationship-led nurturing across multiple stakeholders.
- Owners usually care about cost, scale, visibility, and auditability. HR usually cares about payroll accuracy, compliance, and less consolidation work. Ops usually cares about scheduling, last-minute changes, cross-outlet coordination, and attendance visibility.
- Map features to business value: cost savings, time savings, visibility/accountability, accuracy, compliance, trust, flexibility, and retention.
- Internal training case examples are proof patterns only. Use public name drops only when the approved case-study bank or another approved source supports them.

## QO And QO Met Quality

Clean lead checklist:

- correct industry
- headcount
- current solution or current tools
- contract end date
- at least one associated contact
- verified decision maker coverage from HubSpot buying role, with owner/founder/director/CEO/boss titles treated as review candidates until audited
- verified callable phone coverage when the next motion is call/WhatsApp; Truecaller manual lookup is candidate evidence only until actual call outcome or approved verification note is captured

SG lead-enrichment pilot checklist:

- Keep fixed AE account ownership unchanged.
- Start with 20-30 priority accounts before scaling.
- Target weak accounts first: 1-2 contacts/numbers, no clear decision maker, no clear champion/influencer, or ICP/high-potential accounts where better coverage can improve outreach.
- Aim for 1 verified decision maker, 1 champion/influencer or operating contact, and at least 3 usable contacts where possible.
- Optimize for cost per usable AE handoff, not lowest possible provider spend. Use free/public sources first, but allow a capped paid test when it is the fastest path to a verified decision maker, champion/influencer, or callable phone.
- Use the provider waterfall in order: HubSpot evidence, HubSpot notes/tasks/history, Tavily public company/job-board research, Exa people candidates, controlled Lusha + Prospeo paid-provider pilot, approved reveal, manual Truecaller/call outcome, then HubSpot preview.
- Stop paid provider work once minimum readiness is met, and track successful provider/source/confidence, cost per usable contact, cost per verified/callable phone, AE validation result, and Activities to QO follow-through.
- Khai owns research/classification/handoff: company match, title relevance, duplicate status, source, and High/Medium/Low confidence.
- AE should not redo the research; AE validates through outreach and updates validation status within 3 working days.
- ACRA can support director/entity verification, not phone-number enrichment.

QO checklist:

- real new opportunity, not a recycled follow-up meeting
- buying-relevant contact is involved
- industry, headcount, current tools, and contract timing are known or explicitly marked `needs-check`
- next step is clear
- QO Met can be verified from actual meeting evidence or configured deal stage movement

Direct QO count or pace prompts should call `build_sales_metric_actuals_query` for `fct_sales_points.qo_set`; Friday review remains the tactical hygiene/coaching flow.

HubSpot revenue-funnel prompts should use a created-date deal cohort, not Rev planning targets. Sales Outbound is the default channel slice; all outbound must be explicit. New-business analysis should prefer configured new-business pipelines, exclude renewals, and show the deal audit rows behind conversion rates.

Use greater than 75% QO-to-QO-Met as the quality guardrail. If QOs are high but QO Met is weak, call out qualification quality rather than celebrating volume.

## Warm Activity And Events

Warm activity proof should include:

- photo or selfie proof when appropriate
- follow-up WhatsApp
- manually logged HubSpot meeting
- safe association to account, contact, owner, and timestamp

WhatsApp may autolog through Eazybe where configured, but HubSpot is the durable reporting source. Do not expose raw images, phone exports, attendee lists, form responses, WhatsApp bodies, note bodies, task bodies, or private comments.

Events are outbound demand generation. Track registrations, attendance, follow-up, QO, QO Met, deals, and blocked follow-up. Keep event volume constrained when QO output or manager capacity is weak.

## Conversation Capture Readiness

- Company-controlled mobile numbers, WhatsApp Business, Eazybe logging, and HubSpot auto-logging are sales-execution hygiene.
- Do not claim the rollout is live unless a tracker or live system verifies it. Use `needs-check` for mobile-number readiness, Eazybe linkage, central access, and reassignment status when unverified.
- Coaching and Friday review answers should separate real HubSpot activity gaps from capture-infrastructure gaps where WhatsApp evidence may be missing because reps use personal numbers or unverified logging paths.
- Onboarding/offboarding checks should include number assignment, WhatsApp Business setup, Eazybe linkage, HubSpot logging test, central access, and reassignment.
- Sales-call evidence remains weaker unless HubSpot call logging or an approved telephony integration is verified.
- When Aircall is configured, selected recordings can improve coaching and call-quality evidence through `find_aircall_calls` and `transcribe_aircall_recording`. Use this as call enrichment only: summarize redacted bounded transcript evidence, do not expose raw recording links/audio/phone numbers, and do not override HubSpot activity truth.

## Outreach And Nurture Drafting

### Terminology aliases

`KNS`, `K/N/S`, and `K N S` all mean Knowledge, Network, Support. Do not expand KNS as Know-Nurture-Sell.

Use CCC:

- Connect: short relevant opener plus a micro question.
- Curiosity: relevant peer, brand, or context, not generic networking.
- Convert: clear yes/no next step with respectful urgency.
- Fallback: turn rejection into a 15-minute catch-up anchored on pain or curiosity.

Use 3C plus K/N/S for pre-demo nurturing:

- 3C: Curiosity, Credibility, Context.
- K/N/S: Knowledge, Network, Support.
- Five-touch rhythm over about 14 to 18 days: hook, contextual follow-up, K/N/S value, re-engage, close-loop.

Drafts are manual-review only. Do not send WhatsApp, email, Slack, calendar invites, or HubSpot mutations from a draft answer.

## Pre-Demo Planning

Before drafting a pre-demo plan, use selected scoped HubSpot accounts only and call `build_pre_demo_game_plans` after the user confirms `run`.

Required sections:

- Static Information
- Research / stalking signal
- Hypothesized interest and why
- Alternatives they may consider
- What to show to win
- 3 relevant name drops
- Game Plan A
- Game Plan B
- IC-BANT prompts
- Missing evidence

Required facts:

- number of employees
- industry
- lead source
- why-now signal
- stakeholders
- current tools
- contract end date
- timeline

Use primary research for opportunities above 10k ACV when approved and available. If social, gated, or map evidence is not supplied by the user or approved tools, mark it manual-check. Do not invent pricing, lead source, current tools, meeting reason, case studies, or name drops.

## Demo Standards

A demo is a value conversation, not a product walkthrough.

Use the seven demo dimensions:

- Control and Conversational
- Consultative
- Contextual
- Before/After
- Benefits versus Features
- Product Knowledge
- Negotiation

Show the few workflows that match the prospect's pain. Use before/after contrast and benefits before features. Use case studies only when the source context supports them. If product knowledge is uncertain, say what must be checked instead of bluffing.

Negotiation should tie back to quantified value, give-and-take, and a timeline backward from onboarding, signing, and decision dates. Do not invent pricing.

## Post-Demo Follow-Up

Follow-up earns a decision; it is not a reminder sequence.

Use the 3C follow-up standard:

- Credible
- Contextual
- Consistent

Suggested cadence:

- demo day: agree next follow-up date and timeline
- D+1: summary email and WhatsApp
- D+3: relevant case study when approved
- D+5: K/N/S value
- D+10: reference or social proof when approved
- D+14: go/no-go ask
- D+21: breakup call for truth

Capture the real blocker, who or what StaffAny lost to, and when to reconnect. Keep loss reasons safe and concise.

## Rubric Scoring And Ramp

- Use the 2026 rubric layer for CCC, CBANT, pre-demo nurturing, combined demo, and post-demo follow-up coaching.
- Score coaching behavior as 0/1/2 when a rubric-style answer is requested: missed, partial, strong.
- AE coaching audits should check 3 QOs set, target-account morning-message coverage, 40 connected calls, and calls above 1 minute that did not produce appointment evidence. Call content stays guarded unless a separate approved source permits it.
- Any weak score needs a specific evidence note, not a vague judgment.
- Onboarding/ramp guidance can reference the 8-week validation path, structured tests, and month-four ramp expectation.
- Treat 450 cap-point rows as onboarding/ramp context only; do not use them to override the current Tactical Pause operating rhythm.

## Objection Handling

For AI, low-code, or custom-build objections:

- Do not attack AI or tell the prospect they cannot build.
- Agree that custom internal tools can be useful, then shift to ownership after launch.
- Frame payroll and attendance as a risk-heavy core: compliance updates, access control, sensitive employee data, daily troubleshooting, and long-term maintenance.
- Recommend building around StaffAny through APIs or custom workflows, not rebuilding payroll or attendance itself.

## Tool Behavior

- Friday sales review: still call `build_friday_sales_review`; use this reference to interpret 120/150 coverage, double tap, 30 WhatsApp rhythm, 40 connected calls, QO/QO Met guardrail, warm activity, and Friday correction.
- Priority-account coverage: use HubSpot activity evidence and classify dirty accounts by missing industry, headcount, current tools, contract end date, associated contact, or verified decision maker.
- Pre-demo game plans: still call `build_pre_demo_game_plans`; use this reference for the training framework and missing-evidence rules.
- Nurture drafts: use CCC, 3C, K/N/S, QO quality, and warm-activity standards, but keep all output manual-review only.
- ICP/value-angle answers: use persona, JTBD, country headcount, outlet count, and business maturity before recommending feature-led messaging.
- Conversation-capture answers: use HubSpot as the activity source of truth, but flag company-number, WhatsApp Business, Eazybe, and central repository readiness when missing evidence may be infrastructure-related.
- Conflicting old/archive guidance: surface it as lower-authority context and do not silently promote it.
