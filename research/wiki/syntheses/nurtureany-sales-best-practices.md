# NurtureAny Sales Best Practices

## Scope

This synthesis combines the Leadership Tactical Pause folder and Sales Training folder into durable NurtureAny operating guidance. It should feed the NurtureAny skill reference, not replace HubSpot or live tool outputs.

## Source Base

- Leadership Tactical Pause: [source note](../sources/nurtureany-leadership-tactical-pause.md), [raw record](../../raw/nurtureany-sales-best-practices/leadership-tactical-pause.md).
- Sales Training Materials: [source note](../sources/nurtureany-sales-training-materials.md), [raw record](../../raw/nurtureany-sales-best-practices/sales-training-materials.md).
- Sales Onboarding Master Template: [source note](../sources/nurtureany-sales-onboarding-master-template.md), [raw record](../../raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md).

## Source Hierarchy

1. HubSpot and live MCP/tool outputs remain source of truth for target account, owner, country, contract end date, current tools, follow-up status, calls, meetings, tasks, and deals.
2. Current/final Tactical Pause materials are the source of truth for operating rhythm, account coverage, QO quality, warm activity, event discipline, and Friday correction.
3. Current instructor-copy training materials and current rubric sheets are the source of truth for outreach, pre-demo, demo, post-demo, and coaching quality standards.
4. Current onboarding plans, master templates, and assessment sheets are supporting evidence for ramp, certification, and scoring.
5. Archive, old, copy, outdated, and trainee files are lower-authority context. Surface conflicts when material.

## Operating Rhythm

- Each AE should have a protected 150-account pool. Changes should be deliberate and manager-approved.
- Weekly coverage target is 120 of 150 priority accounts.
- Daily rhythm includes 30 WhatsApp nurturing touches, double taps, and connected-call discipline where the channel fits.
- 40 connected calls is a useful weekly discipline from the current account pool where calling is a strong channel.
- Friday review is not passive reporting. It should trigger correction for missed coverage, weak activity quality, poor QO quality, or stale follow-up.
- Clean data comes before AI: capture calls, meetings, notes, trackable channels, and CRM updates before asking automation to optimize the system.

## QO And QO Met Quality

- Clean lead requirements: correct industry, headcount, current solution or current tools, contract end date, and a champion or decision maker.
- QO must be a real new opportunity. Follow-up meetings do not count as new QOs.
- QO quality requires decision-maker or buying-relevant owner, HR, or operations participation.
- The operating target is greater than 75% QO-to-QO-Met. Weak QO quality should show up quickly in the QO Met gap.
- QO Met should be confirmed from actual meeting evidence and HubSpot records, not inferred from training docs.

## Demo Discipline

- Pre-demo planning must include static facts, why-now context, stakeholder map, current tools, contract end date, and hypothesis.
- For opportunities above 10k ACV, primary research is expected before the demo. If the bot cannot verify it through allowed sources, mark it as a manual-check item.
- I-C-BANT should run before product demo: Introduction, Connect, Budget, Authority, Need, and Timeline.
- A demo is a value conversation, not a product walkthrough. It should be consultative, contextual, benefit-led, and structured around before/after value.
- Reps should not show everything. Recommend workflows, tie them to the prospect context, use relevant case studies only when known, and control next steps.
- Negotiation guidance should quantify value, trade value for concessions, and work backward from onboarding, signing, and decision dates.

## Rubric And Ramp Evidence

- Current 2026 rubrics use a 0/1/2 scoring scale and require evidence notes when scoring weak behavior.
- Coaching should use the rubric layer for CCC, CBANT, pre-demo nurturing, combined demo, and post-demo follow-up.
- The master template supports onboarding and ramp coaching: 8-week validation, structured tests, month-four ramp expectations, and first-deal gates.
- Older 450 cap-point mechanics remain ramp context only. They yield to the current Tactical Pause account-coverage and activity-hygiene rhythm.

## Event And Warm Activity

- Warm activity proof should include a photo or selfie, follow-up WhatsApp, and a HubSpot meeting log.
- WhatsApp may autolog through Eazybe where configured, but HubSpot remains the durable record for reporting.
- Events should be measured as outbound demand generation. Track registrations, attendance, QO, QO Met, deals, and follow-up.
- Event volume should be constrained when QO output or manager capacity is weak.
- Do not paste raw images, phone exports, private event attendee lists, or unnecessary form responses into wiki notes or bot outputs.

## Coaching Cadence

- Managers should coach activity quality, account focus, QO quality, and demo/follow-up discipline daily when gaps are active.
- Friday reviews should identify misses, assign correction, and protect time for cleanup instead of adding external meetings.
- Use training rubrics for coaching: CCC, CBANT, I-C-BANT, value-driven demo, and post-demo follow-up.
- Onboarding plans are useful for ramp expectations and testing, but older activity-point mechanics yield to current activity hygiene.

## Objection Handling

- For AI or custom-build objections, do not attack AI or say the prospect cannot build.
- Reframe the issue around risk after launch: compliance ownership, payroll/attendance access control, daily maintenance, and operational troubleshooting.
- Use the principle "build around the core, not instead of the core" when discussing StaffAny APIs and custom workflows.

## Inbound Routing

- SG diagnosis points to pipeline quality, meeting efficiency, and inbound routing/execution gaps.
- Inbound should be routed to reps with proven qualification and meeting discipline when quality is the bottleneck.
- The bot should avoid treating every inbound as equal; lead source, ICP fit, buying role, and current tools matter.

## AI And Data Readiness

- AI workflow ideas are downstream of data capture. Missing CRM fields, notes, calls, or meetings should be flagged as readiness gaps.
- Higher-leverage HQ work should be made explicit manually before automation.
- Bot outputs should separate verified facts, inferred hypotheses, and manual-check items.

## Market Guidance

- SG: prioritize QO quality, QO-to-QO-Met improvement, inbound routing, meeting discipline, and closing quality.
- MY: apply the same CCC/CBANT/I-C-BANT and demo standards, with onboarding materials as current ramp context.
- ID: prioritize activity-to-QO efficiency. Bahasa Indonesia case material supports localization; do not force SG call assumptions when WhatsApp, events, or referral activity is stronger evidence.
- Cross-market: use ICP, industry, headcount, current tools, contract end date, and buying role before choosing playbooks or examples.

## NurtureAny Implementation Implications

- Sales drafts, Friday reviews, pre-demo plans, event follow-ups, coaching summaries, and operating-rhythm advice should consult the best-practices reference first.
- Tool calls still matter: Friday sales reviews should call `build_friday_sales_review`, and pre-demo plans should call `build_pre_demo_game_plans` for selected scoped accounts.
- Drafts remain manual-review only. The bot should not send external messages.
- The bot should surface lower-authority old/archive guidance when it conflicts with current/final/instructor material.
