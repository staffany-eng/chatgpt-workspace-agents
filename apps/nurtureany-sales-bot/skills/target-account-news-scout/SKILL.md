---
name: target-account-news-scout
description: Research a NurtureAny-scoped HubSpot target account, find timely public news and brand signals, rank the best outreach angle, and produce a send-ready review draft with source links. Use when an AE or manager asks for recent account news, timely public signals, or a news-based nurture opener.
version: 1.0.0
author: StaffAny
license: Internal
metadata:
  hermes:
    tags: [staffany, sales, hubspot, public-research, nurtureany]
    related_skills: [nurtureany-sales-bot]
---

# Target Account News Scout

## Overview

Use this skill when the input is a named NurtureAny target account or scoped HubSpot company and the goal is to turn recent public signals into outreach.

NurtureAny-specific rule: HubSpot scope comes first. On Slack, a first request that needs HubSpot, Tavily/public research, Slack lookup, or any other app-backed source must use the NurtureAny run gate before tools. After `run`, resolve the account from the caller's allowed HubSpot scope, then call the approved public-research path. Do not research arbitrary company-name-only inputs outside the caller's NurtureAny scope.

First Slack response format must be the standard NurtureAny five-line preflight only:

```text
Interpreted question: <target-account news request>
Plan: I will resolve <account> against your scoped HubSpot target accounts, then use target-account-news-scout and approved public research to find recent public signals and draft a manual-review <channel> opener.
Estimate: 2-3 min
Caveat: Public news is an outreach angle only; it does not override HubSpot account truth and no outreach will be sent.
Reply "run" to start, or tell me what to change.
```

Do not add checklists, prerequisites, or extra headings before `run`.

Preferred pattern:

1. Resolve the account through NurtureAny HubSpot scope.
2. Search recent public sources through approved public research.
3. Pick the most relevant signal.
4. Produce a short, send-ready draft for manual review with citations.

This skill inherits NurtureAny V1 guardrails:

- Prefer fresh, meaningful signals over generic mentions.
- Prefer official company sources, partner announcements, and reputable news outlets.
- Classify signals into `funding`, `leadership`, `hiring`, `product`, `brand-buzz`, or `news`.
- Keep the final message concise and human.
- Never auto-send WhatsApp, email, LinkedIn, Instagram, SMS, or sequence messages.
- Messaging output is a draft only unless an approved NurtureAny send workflow with explicit approval exists.

## Inputs

The ideal input bundle is:

- `slack_user_email`
- `hubspot_company_id` or an exact scoped account name
- `account_name`
- `domain`
- `industry`
- `country` or market
- `persona` such as `CEO`, `HR`, or `decision-maker`
- `channel` such as `whatsapp`, `email`, or `linkedin-message`

If only the account name is provided in Slack, first resolve it against the caller's scoped HubSpot target accounts after `run`. If multiple scoped companies match, stop and ask the user to pick a company ID. If no scoped HubSpot company matches, return `Confidence: blocked` instead of doing broad web research.

## Workflow

### 1. Resolve The Target Account

- Use NurtureAny account scope before public research.
- Confirm the official website/domain from HubSpot when available.
- Use industry, geography, and domain as tie-breakers.
- If the account cannot be resolved confidently inside caller scope, stop and say so.

### 2. Search Public Signals

- Search the last 30 to 60 days first.
- Prefer official press pages, newsroom posts, partner announcements, and reputable media.
- Only use Facebook or Instagram if the official handle is obvious, already provided, or linked from the company site.
- Do not rely on broad LinkedIn scraping or unverified profile data.
- Use `research_public_company_signals` when a scoped HubSpot company is available, with `research_mode="light"` by default unless the user asks for deeper research.

Read [references/search-playbook.md](references/search-playbook.md) for query patterns and source priorities.

### 3. Filter And Classify

- Deduplicate repeated coverage of the same event.
- Discard weak mentions like generic directory pages, job boards without context, and low-signal content farms.
- Classify each surviving signal as one of:
  - `funding`
  - `leadership`
  - `hiring`
  - `product`
  - `brand-buzz`
  - `news`

### 4. Pick The Best Outreach Angle

Rank signals using these priorities:

- Freshness: newer beats older.
- Business significance: launches, partnerships, expansions, executive changes, hiring, funding, and brand momentum beat generic mentions.
- Role fit: prefer signals that match the persona if one is provided.
- Reusability: prefer signals that support a natural opener for outreach.

If there is no strong recent signal, fall back to one official update from the company site and be explicit that the angle is lighter.

### 5. Draft The Message

- Pick one primary signal and up to two alternates.
- Write one concise message tailored to the requested channel.
- Keep it useful, not salesy.
- Include the article title and link in the draft when the channel supports links.
- Say `Manual-review draft only`; do not imply the message was sent.

### 6. Return The Result

Use the markdown output in [references/output-contract.md](references/output-contract.md). Include `Source`, `Scope`, `Confidence`, and `Caveat` in the final NurtureAny answer.

## Quality Bar

- Every factual claim needs a source link.
- Include concrete dates when summarizing news.
- Do not invent article titles, people, or business events.
- Prefer 1 strong signal over 5 weak ones.
- Keep the draft short enough to send without editing in most cases.
- Include `cost_report` and `will_mutate_hubspot=false` when public research ran.

## Failure Modes

- If no credible recent news is found, say that clearly and provide a softer fallback angle.
- If sources conflict, note the conflict and prefer the official source.
- If the company name is ambiguous inside caller scope, stop after identity resolution and ask for the scoped company ID.
- If public research credentials or tooling are unavailable, return `Confidence: blocked` with the failing prerequisite.
