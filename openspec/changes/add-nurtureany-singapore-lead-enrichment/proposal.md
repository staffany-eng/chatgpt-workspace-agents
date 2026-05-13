# OpenSpec: NurtureAny Singapore Lead Enrichment Skill

## Summary

Create one main NurtureAny workflow, `build_singapore_lead_enrichment_plan`, that works for any scoped Singapore HubSpot company and defaults to SG target accounts.

V1 helps SG sales close three gaps before WhatsApp nurturing:

- associated contact coverage
- verified decision-maker coverage
- callable / verified-phone coverage

The cost target is capped effectiveness, not cheapest possible enrichment: minimize cost per usable AE handoff, and spend only when the next provider materially improves verified decision-maker, champion/influencer, or callable-phone coverage.

The fixed-AE-account pilot adds one more operating layer: start with 20-30 priority accounts, keep account ownership unchanged, have Khai research/classify/handoff contacts, and have the AE validate through outreach within 3 working days.

## Evidence Used

- Pasted Granola transcript about SG/MY target-account requirements, decision-maker discovery, phone verification, WhatsApp nurturing, Lusha/Prospeo/Truecaller, and HubSpot rollup mismatch.
- Repo/wiki/app packet and existing NurtureAny HubSpot source-of-truth rules.
- Read-only Slack review of `#team-rev-bd-sgmy-proj12`: Kerren lead-cleaning process, screenshot-count reports, and Siti HubSpot decision-maker mismatch thread.
- Read-only Slack review of Eugene's fixed AE account contact enrichment pilot: 20-30 priority accounts, 1 DM + 1 champion/influencer + at least 3 usable contacts where possible, source/confidence/handoff notes, and AE validation SLA.
- Current NurtureAny packet/runtime contracts for Tavily public research, Exa people search, and Lusha selected reveal.
- Prospeo API docs and Clay waterfall/conditional-run docs as provider-method inspiration only.

## Problem

SG reps are cleaning fixed account lists manually across LinkedIn, Lusha, Apollo, Prospeo, job boards, Google, and call/WhatsApp history. Coverage reporting is inconsistent:

- Some accounts have target-account truth but weak associated contacts.
- Some accounts have contacts but no verified decision maker.
- Some accounts have contacts and titles but no callable or verified phone status.
- HubSpot rollups can say a decision maker exists while associated contacts do not show `hs_buying_role=DECISION_MAKER`.
- WhatsApp batches need cleaner pre-work, not a send automation.

## Goals

- Give SG sales one repeatable review-first enrichment plan per owner or selected companies.
- Default to Singapore HubSpot target accounts while allowing explicit scoped SG HubSpot companies.
- Return account-level gaps, stakeholder slots, phone-verification status, next source, handoff note, and WhatsApp readiness.
- Add phone-verification field support and exact HubSpot mismatch diagnostics.
- Separate provider jobs clearly: Tavily for public company/job-board signals, Exa for people candidates, Lusha/Prospeo for controlled paid contact-data comparison, Truecaller for manual callability evidence.
- Add Clay-style waterfall rules: run providers only when a real gap exists, stop when minimum readiness is met, track successful provider/source/confidence, and measure cost per useful handoff.
- Keep Truecaller manual in V1: no automated reverse lookup, scraping, or bulk enrichment.

## Non-Goals

- No automatic WhatsApp/Eazybe sends.
- No raw phone numbers in Slack-facing output.
- No paid Lusha or Prospeo reveal without explicit approval.
- No automatic Truecaller API integration unless StaffAny has an approved API contract for this exact use case.
- No arbitrary company-name prospecting outside HubSpot scope.
- No account-owner reassignment.
- No Prospeo automation in this change; Prospeo is a V1.1 paid-provider candidate for a measured pilot beside Lusha.
- No Clay automation in V1; Clay remains a future/manual batch-provider option only if the workflow and budget are approved.
- No Unbrowse usage in this workflow; automated gated/social/shadow-API access stays outside the current safety model.
