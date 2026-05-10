# NurtureAny Sales Onboarding Master Template

## Source Metadata

- Type: private Google Sheets master template plus linked-file ingest
- Source class: NurtureAny sales onboarding, rubric, and training-link graph
- Source URL or path: https://docs.google.com/spreadsheets/d/1rGagl2iqty0d-ypJHGhjpH-2MKjCjWB4IRk-GV-JWB8/edit?gid=2004877958#gid=2004877958
- Date ingested: 2026-05-10
- Context: focused second-pass ingest of the sales onboarding master template and Drive-linked files
- Default weight: 4
- Privacy: private internal evidence, no raw PII, form responses, customer lists, or raw pricing rows copied

## Context Caveat

This source is current and useful for onboarding, certification, rubric scoring, and linked
training context. It also links older 2020/2022 materials, secret tests, response sheets,
pricing sheets, and archived artifacts. Use current 2026 rubrics and decks for training
quality, but keep Tactical Pause as the stronger source for current operating rhythm and
HubSpot as the stronger source for account-specific truth.

## Evidence Used

- Raw record: [research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md](../../raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md)

## What They Said

- The focused crawl parsed the master template and checked both first-level Drive links and
  second-order Drive links discovered inside linked files.
- The master material list treats conversation/qualification, demo, nurturing, and overall
  CBANT/CBV/negotiation as assessed sales skill sets.
- The onboarding plan is an 8-week validation and ramp program, with older 450 cap-point
  mechanics, QO gates, deal gates, and a month-four ramp expectation.
- The process checklist requires tool linking, HubSpot hygiene, source tagging, activity
  logging, meeting logging, next-step discipline, and follow-up timing.
- The 2026 rubric sheet defines CCC, CBANT, trainer marking order, 0/1/2 scoring, and
  evidence notes for weak scores.
- The 2026 training decks reinforce 3C plus K/N/S nurturing, pre-demo static/hypothesis
  planning, primary research for 10k ACV deals, and value-driven demo dimensions.
- Post-demo and objection-handling materials push reps to get decision truth, lost reasons,
  next reconnect timing, gatekeeper context, and a risk-based answer to AI-build objections.
- Secret forms, response sheets, historic pricing sheets, and account-list style sheets were
  inventoried but not copied as raw operating guidance.

## Evidence Trace

- Claim: The crawl checked first-level and second-order linked Drive files. Evidence: It records 47 first-level files, 25 folder-child links, and 18 second-order links. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:26`.
- Claim: The material list assesses conversation/qualification, demo, nurturing, and overall CBANT/CBV/negotiation. Evidence: The material-list extract names those rows. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:149`.
- Claim: The onboarding plan is an 8-week ramp program with QO and deal gates. Evidence: The extract states the 8-week objective, Phase 1b 8 QO gate, Phase 1c deal gate, and month-four ramp. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:156`.
- Claim: The process checklist requires tool setup and HubSpot process hygiene. Evidence: It names tool links, company/contact/deal creation, source tagging, logging, next steps, and 24-hour follow-up. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:187`.
- Claim: The 2026 rubric sheet defines CCC/CBANT and evidence-backed scoring. Evidence: The trainer guide defines CCC, CBANT, marking order, 0/1/2 scoring, and evidence notes. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:238`.
- Claim: The 2026 decks reinforce nurturing, pre-demo, and demo standards. Evidence: The extracts show 3C, K/N/S, five touches over 18 days, 10k ACV research, and demo dimensions. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:263`.
- Claim: Post-demo and objection materials add decision-truth and risk-framing standards. Evidence: The extracts include lost reasons, D+14/D+21 truth, gatekeeper context, and AI-build framing. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:322`.
- Claim: Secret, response, pricing, and account-list artifacts were not promoted as raw guidance. Evidence: The raw policy and blocked/inventory section state those handling limits. Source: `research/raw/nurtureany-sales-best-practices/sales-onboarding-master-template-linked-files.md:16`.

## Learning Summary

- This second-pass ingest closes the master-template link graph: direct Drive links, linked
  folders, uploaded PPTX decks, Forms metadata, and one level of Drive links found inside
  linked files are now inventoried or extracted.
- The master template is strongest for onboarding/ramp, training certification, and rubric
  scoring. It should not override the newer Tactical Pause operating rhythm.
- Current 2026 rubrics should guide NurtureAny scoring and coaching for CCC, CBANT,
  pre-demo nurturing, I-C-BANT, value-driven demo, and post-demo follow-up.
- Older 450 cap-point mechanics are ramp evidence only. When they conflict with current
  activity hygiene, the Tactical Pause 150-account and 120/150 coverage rhythm wins.
- The bot should keep raw pricing, secret tests, form responses, customer lists, and old
  meeting sheets out of generated guidance unless a user provides explicit scoped context.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: NurtureAny sales onboarding master template and linked files
- Evidence weight check: default weight 4 for current 2026 onboarding/rubric material; older
  2020/2022, archived, response, pricing, and missing files are lower-authority context.
- Promotion action: update the NurtureAny synthesis and skill reference only where the
  focused crawl strengthens onboarding, rubric, pre-demo, post-demo, and objection standards.

## Possible Agent Builder Relevance

- Agent-synthesized: NurtureAny should treat this source as the detailed onboarding and
  rubric layer beneath the sales-best-practices reference.
- Agent-synthesized: Coaching outputs should cite evidence-backed scoring behavior, especially
  when giving a weak CCC, CBANT, pre-demo, demo, or post-demo score.
- Do-not-promote: Do not turn old 450 cap-point rows, raw pricing sheets, secret tests, or
  response sheets into current operating rules.

## Follow-Up Questions

- Should the 2026 Forms bodies become separate training-test notes, or should they remain
  inventory-only because the rubrics and decks already cover the reusable standards?
