# NurtureAny Mobile Number Rollout

## Source Metadata

- Type: private Google Docs ingest
- Source class: NurtureAny sales execution hygiene and operations rollout memo
- Source URL or path: https://docs.google.com/document/d/1ROis86zqsgfrobL20n14pxmhv2lvHGQgaqqQu4rBcSc
- Date ingested: 2026-05-12
- Context: company-controlled mobile numbers, WhatsApp Business, Eazybe, HubSpot logging, conversation repository, onboarding, and offboarding
- Default weight: 4
- Privacy: private internal operations memo; no phone numbers, credentials, raw message bodies, Drive ACLs, or private comments copied

## Context Caveat

This memo is rollout-planning evidence. It should guide NurtureAny readiness checks and sales hygiene advice, but it does not prove the mobile-number rollout is live. Until verified by live systems, NurtureAny should mark rollout state as `needs-check`.

## Evidence Used

- Raw record: [research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md](../../raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md)

## What They Said

- Sales conversations should move from personal rep numbers to company-controlled mobile numbers.
- WhatsApp messages and calls should become a company-owned conversation layer that can be logged, stored, reviewed, reassigned, and used for coaching or future AI.
- The rollout exists because personal-number dependency causes lost history, weak leader visibility, and poor conversation repositories for coaching or QA.
- The planned setup is company mobile number plus WhatsApp Business plus Eazybe, with WhatsApp auto-logging into HubSpot.
- Conversation history, searchable central storage, onboarding setup, offboarding reassignment, and a tracker are must-have operating requirements.
- Sales-call logging into HubSpot is a nice-to-have, with Aircall feasibility to be checked.
- The rollout target is all active sales reps live by 1 June 2026 after feasibility, vendor, activation, and logging tests.

## Evidence Trace

- Claim: Sales conversations should move from personal rep numbers to company-controlled mobile numbers. Evidence: The raw extract states the desired outcome and must-have requirement. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:28`.
- Claim: WhatsApp and calls should become a company-owned conversation layer for logging, review, reassignment, coaching, and future AI. Evidence: The raw extract describes the desired conversation layer. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:29`.
- Claim: Current pain is lost history, weak visibility, and no clean repository. Evidence: The raw extract lists personal-number dependency, lost history, leader visibility, and repository gaps. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:30`.
- Claim: Planned setup is mobile number, WhatsApp Business, Eazybe, and HubSpot auto-logging. Evidence: The raw extract lists rollout setup steps and logging requirements. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:35`.
- Claim: Central storage, onboarding/offboarding, tracker, and history preservation are must-have requirements. Evidence: The raw extract lists storage, search, access, tracker, onboarding, and offboarding. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:51`.
- Claim: Sales-call logging is nice-to-have and Aircall feasibility is open. Evidence: The raw extract labels call logging as nice-to-have and mentions checking Aircall linkage. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:57`.
- Claim: Target rollout date is 1 June 2026 with earlier feasibility, vendor, activation, and test gates. Evidence: The raw extract records the target date and timeline milestones. Source: `research/raw/google-drive/2026-05-12-mobile-number-memo/source-extract.md:61`.

## Learning Summary

- NurtureAny should treat company-controlled WhatsApp numbers as a sales hygiene and continuity prerequisite, not only a telephony admin task.
- HubSpot remains the durable follow-up source, but the memo raises a readiness gap: WhatsApp logging quality depends on company-number, Eazybe, and reassignment setup.
- Follow-up quality and coaching should distinguish between verified HubSpot activity and missing/blocked conversation capture infrastructure.
- Onboarding and offboarding checks should include number assignment, WhatsApp Business setup, Eazybe linkage, HubSpot logging test, central access, and reassignment.
- Call evidence remains weaker until HubSpot call logging or Aircall-style integration is verified.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: company-controlled mobile-number rollout memo
- Evidence weight check: default weight 4 as private current operations memo; rollout status still needs live verification
- Decision: promote sales hygiene implications into NurtureAny references while keeping actual rollout status `needs-check`.

## Possible Agent Builder Relevance

- Agent-synthesized: Add company-controlled number and WhatsApp/Eazybe logging readiness to sales best-practices guidance.
- Agent-synthesized: Add conversation-capture gaps as a caveat in coaching, Friday review, and follow-up quality answers.
- Do-not-promote: Do not claim all reps are on company numbers or that call logging is live without system verification.

## Follow-Up Questions

- Should NurtureAny get a read-only roster/readiness tool for company-number, WhatsApp Business, Eazybe, and HubSpot logging setup status?
- Should the rollout tracker become the approved source for mobile-number readiness once it exists?
