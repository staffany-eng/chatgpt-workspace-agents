# Gong Coaching Public Docs

## Source Metadata

- Type: public vendor documentation ingest
- Source class: Gong coaching and conversation-intelligence product docs
- Source URL or path: https://help.gong.io/docs/
- Date ingested: 2026-05-15
- Context: product-pattern evidence for call coaching, scorecards, call pages, search, trackers, topics, and interaction stats
- Default weight: 3
- Privacy: public docs, no private Gong data or StaffAny data copied

## Context Caveat

These docs describe Gong's public product patterns. They are useful for designing NurtureAny's call-coaching output, but they are not StaffAny source truth, not a Gong integration contract, and not a parity claim. HubSpot, StaffAny sales materials, Aircall, and OpenAI remain the actual NurtureAny source stack.

## Evidence Used

- Raw record: [research/raw/gong-coaching/source-extract.md](../../raw/gong-coaching/source-extract.md)

## What They Said

- Gong frames coaching as a loop around recorded calls, scorecards, coachable moments, progress tracking, and business outcomes.
- Gong's AI Call Reviewer uses scorecards for structured feedback and can either suggest answers or score whole calls against predefined criteria.
- AI Call Reviewer searches call transcripts to answer scorecard questions, so the documented AI review pattern is transcript-grounded.
- Gong scorecards break call quality into explicit questions, including discovery, role understanding, pain, business impact, concerns, next steps, value-led demo, tailoring, and firm future commit.
- Gong recommends rolling out scorecards with a small starting set, aligned scoring definitions, scoring KPIs, and follow-on search/team insight review.
- Gong's call page combines the recording player, speaker timing, highlights, outline, comments, stats, topics, and jump-to-moment navigation.
- Gong search supports call filters for participants, accounts, words, trackers, deal stage, dates, platforms, topics, scorecard name, score, comments, and more.
- Gong exposes interaction-style filters such as talk ratio, interactivity, patience, longest monologue, customer story length, and question counts/rates.
- Gong trackers identify words, phrases, or concepts and are meant to follow business priorities such as pricing, new methodology, objections, competitors, pain points, and recording consent.
- Gong topics are automatically detected subjects shown in call pages, filters, team stats, and coaching surfaces.

## Evidence Trace

- Claim: Gong frames coaching as a recorded-call and scorecard loop. Evidence: The raw extract summarizes recorded calls, coachable moments, progress tracking, scorecard answers, and automatic scoring. Source: `research/raw/gong-coaching/source-extract.md:31`.
- Claim: AI Call Reviewer can suggest or automatically score scorecard answers. Evidence: The raw extract describes both individual scorecard suggestions and entire-call scoring. Source: `research/raw/gong-coaching/source-extract.md:33`.
- Claim: Gong's AI review is transcript-grounded. Evidence: The raw extract says AI Call Reviewer searches call transcripts for scorecard answers. Source: `research/raw/gong-coaching/source-extract.md:34`.
- Claim: Gong scorecards encode concrete sales-call dimensions. Evidence: The raw extract lists discovery, pain, business impact, concerns, next steps, demo tailoring, and firm future commit. Source: `research/raw/gong-coaching/source-extract.md:36`.
- Claim: Gong recommends an adoption loop around scorecards. Evidence: The raw extract notes one or two scorecards, score definitions, KPIs, search, and team insights. Source: `research/raw/gong-coaching/source-extract.md:37`.
- Claim: Gong call pages put call review evidence into one surface. Evidence: The raw extract lists player, speaker soundtrack, stats, comments, topics, AI answers, highlights, outline, and jump-to-moment navigation. Source: `research/raw/gong-coaching/source-extract.md:38`.
- Claim: Gong search makes call review reusable across filters. Evidence: The raw extract lists participant, account, phrase, tracker, title, deal-stage, date, platform, outcome, topics, scorecard, score, and comment filters. Source: `research/raw/gong-coaching/source-extract.md:40`.
- Claim: Gong treats interaction stats as coaching/search signals. Evidence: The raw extract lists talk ratio, interactivity, patience, monologue length, customer story length, and question-rate metrics. Source: `research/raw/gong-coaching/source-extract.md:39`.
- Claim: Gong trackers should follow business priorities. Evidence: The raw extract names pricing rollout, new methodology, objection handling, competitor differentiation, pain points, promotions, and consent as tracker examples. Source: `research/raw/gong-coaching/source-extract.md:41`.
- Claim: Gong topics are automatically detected and appear across call review surfaces. Evidence: The raw extract says topics appear on call pages, filters, team stats, and Whisper. Source: `research/raw/gong-coaching/source-extract.md:42`.

## Learning Summary

- NurtureAny should imitate the coaching workflow shape: selected call, short summary, scorecard, timestamped coachable moments, manager note, rep next action, and trend/review follow-up.
- The StaffAny rubric should stay 0/1/2 because current internal sales rubrics already use that scale; Gong's contribution is the structured scorecard workflow and evidence-first review loop.
- Selected-call review should include interaction dimensions when evidence exists: talk ratio, interactivity, patience, monologue length, question balance, objection handling, and next-step control.
- If only transcript is available, NurtureAny should say tone/audio cues were not checked. If later audio-native analysis is added, it should describe observable vocal cues only.
- Gong docs should not introduce any Gong credentials, Gong MCP, Gong API dependency, webhook, data storage, or claim that NurtureAny has Gong parity.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: Gong public coaching docs and NurtureAny selected-call coaching behavior.
- Evidence weight check: default weight 3; public vendor docs are useful product-pattern evidence but lower authority than StaffAny sales materials and HubSpot/runtime evidence.
- Output: synthesize as design inspiration for NurtureAny call coaching, not as product truth or integration proof.

## Possible Agent Builder Relevance

- Agent-synthesized: Add a Gong-inspired selected-call rubric to NurtureAny sales best practices and Slack output guidance.
- Agent-synthesized: Keep the executable path source-agnostic: HubSpot account truth plus Aircall/OpenAI call artifact enrichment, with no Gong runtime dependency.
- Agent-synthesized: Add regression cases that block Gong-integration claims, raw transcript/audio exposure, phone-number exposure, and unsupported tone/emotion claims.
- Do-not-promote: Do not treat Gong topics, trackers, or scorecards as existing StaffAny data unless StaffAny implements equivalent Aircall/OpenAI/HubSpot evidence capture.

## Follow-Up Questions

- Should NurtureAny later compute interaction stats from diarized segments, or keep them as manual transcript-derived coaching notes until an explicit audio-analysis tool is approved?
