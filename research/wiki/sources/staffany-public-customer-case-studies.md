# StaffAny Public Customer Case Studies

## Source Metadata

- Type: public website and video case-study ingest
- Source class: StaffAny public customer case-study pages and public YouTube customer videos
- Source URL or path: https://www.staffany.com/ and https://www.staffany.my/ customer case-study pages; https://www.staffany.com/customers/ public video embeds; public YouTube video pages
- Date ingested: 2026-05-11
- Date refreshed: 2026-05-16
- Context: approved public customer proof for NurtureAny pre-demo case-study matching, sales name drops, and KNS Knowledge hooks
- Default weight: 4 for NurtureAny case-study name-drop and KNS Knowledge matching; 2 for broad product claims outside StaffAny sales context
- Privacy: public marketing pages and public videos; Slack candidate discovery summarized without raw Slack transcripts; no full MP4 or audio archived

## Context Caveat

These pages and videos are approved public sales-enablement evidence. They can support customer name
drops, case-study matching, KNS Knowledge hooks, and draftable sales context. They must not override
HubSpot for account ownership, target-account membership, customer/prospect status, current tools,
contacts, activities, follow-up state, or deal facts. Slack-only candidates are not approved source
context until a published page or approved internal asset exists.

## Evidence Used

- Raw record: [StaffAny Public Customer Case Study Catalog](../../raw/nurtureany-case-studies/public-case-study-catalog.md)

## What They Said

- StaffAny has 27 approved public customer stories: 26 page-based case studies plus Suwe Ora Jamu as a public video-only story linked from the Customers page.
- The video-evidence ingest covers 11 public StaffAny customer videos with per-case metadata, transcript notes, representative keyframe pointers, evidence bullets, and KNS Knowledge hooks.
- Nine videos have caption evidence; Belly & The Chef and Keisuke are marked blocked for transcript verification because YouTube reports transcripts disabled.
- Braud Group and Suwe Ora Jamu preserve Indonesian auto-captions with English translations for AE-facing use.
- The published catalog covers multiple matchable customer patterns, including F&B chains, coffee/beverage brands, retail, fitness/health services, entertainment, petrol retail, and automotive repair.
- Each approved case can be reduced to safe matching fields: country, industry, outlet or staff-size signal, pain, outcome, tags, video evidence when present, and KNS Knowledge hooks.
- Slack-discovered candidates such as Molly Tea, Tiong Hoe, Panchangkat, Bali Buda, and Seniman Coffee should not be used as approved case-study matches until a public page or approved internal asset exists.
- Public case studies and videos are enrichment context only; HubSpot stays canonical for the selected prospect or customer record.

## Evidence Trace

- Claim: StaffAny has 27 approved public customer stories. Evidence: The raw metadata and evidence extract record 27 approved stories. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:9`.
- Claim: The video-evidence ingest covers 11 public StaffAny customer videos. Evidence: The Public Video Evidence Inventory lists 11 case rows with KNS material IDs and evidence paths. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:48`.
- Claim: Two videos remain transcript-blocked while the others have caption evidence. Evidence: Belly & The Chef and Keisuke are marked blocked in the video inventory. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:56`.
- Claim: Indonesian-language videos preserve source captions with English translations. Evidence: Braud Group and Suwe Ora Jamu are marked `available_translated_en`. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:58`.
- Claim: The catalog spans several customer patterns and industries. Evidence: The raw evidence extract summarizes the covered verticals after the inventory. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:79`.
- Claim: Each case can support safe matching fields and KNS Knowledge hooks. Evidence: The raw evidence extract states that case cards include matching fields, video evidence where available, and KNS Knowledge hooks. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:80`.
- Claim: Slack-only candidates are not approved case-study matches yet. Evidence: The raw Slack Candidate Inventory records excluded candidates and handling. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:66`.
- Claim: Public case studies and videos do not override HubSpot account truth. Evidence: The raw evidence extract states that these assets are sales-enablement context only. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:82`.

## Learning Summary

- NurtureAny can stop returning three generic `case-study match needed` slots when a selected account has enough country, industry, or pain-signal context to match published StaffAny case studies.
- The matching layer should prefer public StaffAny case-study pages before Slack mentions because public pages are approved, linkable, and safe to cite externally.
- Video-derived KNS Knowledge hooks give AEs concise proof snippets without exposing raw transcript dumps in Slack tool output.
- Caption-disabled videos can stay in the catalog as public case-page proof, but their material row status should stay `needs-check` until captions, ASR, or approved subtitles are available.
- Slack is useful as a discovery backlog for marketing work-in-progress, but it should not become canonical case-study evidence without an approved artifact.
- Case-study matching should remain explainable and conservative: show customer name, matching reason, and URL; pad with `case-study match needed` if fewer than three approved matches are available.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed with explicit blocked video exceptions
- Focus source: StaffAny public customer case-study pages, public StaffAny YouTube customer videos, and Slack candidate discovery summary
- Evidence weight check: weight 4 for StaffAny sales-name-drop use because these are approved public StaffAny pages; lower confidence outside StaffAny sales workflows.
- Decision: make the public case-study and KNS video-hook catalog available as NurtureAny approved source context while keeping HubSpot as the source of truth for account-specific facts.

## Possible Agent Builder Relevance

- Agent-synthesized: Add this catalog to NurtureAny pre-demo planning so the bot can return three source-backed name drops and KNS Knowledge hooks when the selected account context supports them.
- Do-not-promote: Do not treat Slack-only case-study chatter, WIP shoots, or unpublished marketing tasks as approved customer proof.
- Do-not-promote: Do not treat blocked-transcript video hooks as transcript-verified proof until captions, ASR, or an approved transcript is available.
- Agent-synthesized: Keep the case-study catalog structured separately from HubSpot fields so sales proof enriches the pitch without corrupting CRM truth.

## Follow-Up Questions

- Should marketing provide approved private case-study assets for Molly Tea, Tiong Hoe, Panchangkat, Bali Buda, and Seniman Coffee, or should NurtureAny wait until those pages are public?
- Can marketing provide subtitles or transcript files for Belly & The Chef and Keisuke so their KNS video rows can move from `needs-check` to approved transcript-backed proof?
