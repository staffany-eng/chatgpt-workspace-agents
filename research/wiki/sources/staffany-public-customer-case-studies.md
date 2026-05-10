# StaffAny Public Customer Case Studies

## Source Metadata

- Type: public website case-study ingest
- Source class: StaffAny public customer case-study pages
- Source URL or path: https://www.staffany.com/ and https://www.staffany.my/ customer case-study pages
- Date ingested: 2026-05-11
- Context: approved public customer proof for NurtureAny pre-demo case-study matching and sales name drops
- Default weight: 4 for NurtureAny case-study name-drop matching; 2 for broad product claims outside StaffAny sales context
- Privacy: public marketing pages; Slack candidate discovery summarized without raw Slack transcripts

## Context Caveat

These pages are approved public sales-enablement evidence. They can support customer name drops,
case-study matching, and draftable sales context. They must not override HubSpot for account ownership,
target-account membership, customer/prospect status, current tools, contacts, activities, follow-up state,
or deal facts. Slack-only candidates are not approved source context until a published page or approved
internal asset exists.

## Evidence Used

- Raw record: [StaffAny Public Customer Case Study Catalog](../../raw/nurtureany-case-studies/public-case-study-catalog.md)

## What They Said

- StaffAny has 26 unique published customer case studies available as approved public sales proof across the Singapore and Malaysia public sites.
- The published catalog covers multiple matchable customer patterns, including F&B chains, coffee/beverage brands, retail, fitness/health services, entertainment, petrol retail, and automotive repair.
- Each approved case can be reduced to safe matching fields: country, industry, outlet or staff-size signal, pain, outcome, and tags.
- Slack-discovered candidates such as Molly Tea, Tiong Hoe, Panchangkat, Bali Buda, and Seniman Coffee should not be used as approved case-study matches until a public page or approved internal asset exists.
- Public case studies are enrichment context only; HubSpot stays canonical for the selected prospect or customer record.

## Evidence Trace

- Claim: StaffAny has 26 unique published customer case studies. Evidence: The raw inventory lists every approved case-study row. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:18`.
- Claim: The catalog spans several customer patterns and industries. Evidence: The raw evidence extract summarizes the covered verticals after the inventory. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:58`.
- Claim: Each case can support safe matching fields. Evidence: The raw evidence extract states that case cards include country, industry, size, pain, outcome, and tags. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:59`.
- Claim: Slack-only candidates are not approved case-study matches yet. Evidence: The raw Slack Candidate Inventory records excluded candidates and handling. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:48`.
- Claim: Public case studies do not override HubSpot account truth. Evidence: The raw evidence extract states that these case studies are sales-enablement context only. Source: `research/raw/nurtureany-case-studies/public-case-study-catalog.md:61`.

## Learning Summary

- NurtureAny can stop returning three generic `case-study match needed` slots when a selected account has enough country, industry, or pain-signal context to match published StaffAny case studies.
- The matching layer should prefer public StaffAny case-study pages before Slack mentions because public pages are approved, linkable, and safe to cite externally.
- Slack is useful as a discovery backlog for marketing work-in-progress, but it should not become canonical case-study evidence without an approved artifact.
- Case-study matching should remain explainable and conservative: show customer name, matching reason, and URL; pad with `case-study match needed` if fewer than three approved matches are available.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: StaffAny public customer case-study pages plus Slack candidate discovery summary
- Evidence weight check: weight 4 for StaffAny sales-name-drop use because these are approved public StaffAny pages; lower confidence outside StaffAny sales workflows.
- Decision: make the public case-study catalog available as NurtureAny approved source context while keeping HubSpot as the source of truth for account-specific facts.

## Possible Agent Builder Relevance

- Agent-synthesized: Add this catalog to NurtureAny pre-demo planning so the bot can return three source-backed name drops when the selected account context supports them.
- Do-not-promote: Do not treat Slack-only case-study chatter, WIP shoots, or unpublished marketing tasks as approved customer proof.
- Agent-synthesized: Keep the case-study catalog structured separately from HubSpot fields so sales proof enriches the pitch without corrupting CRM truth.

## Follow-Up Questions

- Should marketing provide approved private case-study assets for Molly Tea, Tiong Hoe, Panchangkat, Bali Buda, and Seniman Coffee, or should NurtureAny wait until those pages are public?
