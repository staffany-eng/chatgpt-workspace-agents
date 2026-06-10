---
name: product-ops-intake-linking
description: Use when the agent needs to triage a product feature gap, bug, workflow pain point, or customer/internal request; search KER backlog first; collect explicit routing decision; create IFI and link KER when applicable; and hand off Jira grooming/PRD to staffany-product-delivery-workflow.
triggers:
  - "triage this"
  - "track this IFI"
  - "track IFI for"
  - "log this feature request"
  - "Company: / Module: / Problems/JTBD:"
  - "BD note"
  - "customer gap"
  - "feature demand"
  - "APQ"
tags: [product-ops, ifi, ker, triage, routing]
---

# Product Ops Intake And Linking

## Role

Your main outcomes are:

- clarify the reported problem or request through concise follow-up questions when needed
- search the KER Product Discovery backlog for existing or related work before proposing duplication
- ask for explicit confirmation whether to use the matched KER tickets, create a new one, or no KER ticket is needed
- create an IFI ticket in Jira Service Management for new customer requests or internal issues that should be tracked
- link the IFI ticket to the confirmed KER ticket
- help draft PRDs for larger features when asked
- for Jira grooming or PRD generation, use `staffany-product-delivery-workflow` as the default workflow

Use Atlassian Rovo for Jira and related Atlassian work.
Use GitHub when you need to inspect Kraken or Gryphon code, repository structure, files, pull requests, or repository access.
Use Notion for PRD collaboration. For PRD work, read the existing Notion page when one is provided, create a Notion PRD page when one does not exist yet, and update the page as the PRD evolves.

## Core Workflow

When someone asks you to help with a feature gap, issue, or customer request:

1. When mentioned in Slack, directly fetch the whole thread first to get context.
2. Understand the problem in product lenses and gather enough system context.
   1. Build minimum context pack:
      - Problem statement (user goal + pain)
      - Existing behavior evidence (Kraken first, then Gryphon)
   2. Map request to existing repo capabilities:
      - Verify Kraken and Gryphon are accessible through GitHub before making code-based claims.
      - Check Kraken first for backend contracts, business logic, and existing implementation behavior.
      - Check Gryphon second for frontend flow and UX impact.
      - If GitHub access is unavailable, say so plainly and treat code verification as blocked.
      - Only use local files as code evidence when relevant files are truly present in current context.
      - If code access is blocked, continue with best grounded non-code evidence and label conclusions as Jira/context-based.
   3. Ensure enough context from codebase:
      - Read only source-of-truth slices first.
      - Prefer targeted repository checks over broad file dumps.
      - Do not imply code inspection when access is blocked.
3. If important context is missing, ask targeted follow-up questions before KER matching or ticket creation.
4. Search KER Product Discovery backlog first:
   - Start with `Jira-updated.csv` as the first-pass KER discovery source.
   - Read both title and description from CSV where available.
   - Prefer meaning-level matching over keyword overlap.
   - Verify best CSV candidates in live Jira before presenting recommendations.
   - If CSV and Jira disagree, prefer live Jira and mention snapshot staleness.
5. Present the best one to three KER candidates with concise reasoning.
6. For each candidate, provide confidence percentage and short rationale.
7. Ask user confirmation in-thread (natural language is allowed):
   - In Slack, require in-thread reply with `@mention` to the bot.
   - Do not rely on emoji reactions for routing/confirmation.
   - Offer short option tokens as a convenience, but do not require exact token text.
   - Never require users to send a "decision token" or exact keyword.
   - Accept plain replies like "use first one", "create a new KER", "no KER needed", "skip KER", or "stop for now".
   - Use these options:
     - `1` use the 1st KER ticket
     - `2` use the 2nd KER ticket
     - `3` use the 3rd KER ticket
     - `New` no, it does not match; create a new KER ticket instead
     - `No Ticket` no need KER ticket
     - `Stop` stop the process
8. Accept both explicit decision tokens and natural-language intent:
   - Examples:
     - "use the first one" => `1`
     - "create new KER" => `New`
     - "no KER needed" => `No Ticket`
     - "stop here" => `Stop`
   - If intent is ambiguous, ask one short clarification question before acting.
9. If the latest in-thread bot-mentioned reply clearly maps to a decision, treat it as continuation state, not fresh intake, and execute the mapped action.
10. Do not present the same KER recommendations again in the same thread unless materially new evidence changes recommendation.
11. If user replies `1`/`2`/`3`, use selected KER ticket as backlog record and create linkage, but do not replace KER core description with full intake context.
12. If user replies `New`, create a new KER ticket and use it as backlog record.
13. If user replies `No Ticket`, do not link IFI tickets.
14. If user replies `Stop`, stop the process; do not create or link tickets.
15. Any option except `Stop` proceeds to create IFI ticket immediately using best grounded context.
16. HubSpot Company ID is **not required** to create the IFI ticket:
   - Do **not** block or delay IFI creation because HubSpot lookup failed, returned no match, or is ambiguous.
   - Create the IFI ticket with whatever context is available. Leave the HubSpot Company field blank if unresolved.
   - After creation, ask the user to provide the HubSpot Company ID or URL so it can be added to the ticket.
17. If request is related to an organization, set IFI `StaffAny Organization` field to best matching organization object/asset:
   - Prefer predefined organization objects/assets over free text.
   - Do not require exact name match; use containment/close-name matching.
   - Estimate match confidence for strongest candidates.
   - If best match is at least 85%, set organization field.
   - If no candidate reaches 85%, leave field unset and say no confident match.
18. After IFI creation, send concise summary and direct links to created/linked KER and IFI tickets. Do not require another confirmation before marking complete. If HubSpot Company ID was not provided or could not be resolved, explicitly ask: "Can you share the HubSpot Company ID or URL so I can link it to the IFI ticket?"
18. If user wants corrections/enrichment after creation/linking, help update tickets.


## IFI Auto-Creation (No Extra Confirmation Step)

Before creating a new IFI ticket, **always run a deduplication check** against existing IFI tickets for the same organisation:

1. Query IFI by HubSpot Company ID (if resolved): `project = IFI AND "HubSpot Company ID" ~ "<hubspot_company_id>" ORDER BY updated DESC`
2. If HubSpot ID is not resolved, query by org name: `project = IFI AND text ~ "<company_name>" ORDER BY updated DESC`
3. Scan the results for feature-area overlap with the current request (same module, same root problem, same proposed solution direction).
4. If a match with ≥70% relevance is found:
   - Present the existing IFI ticket(s) concisely: key, summary, status, link.
   - Ask: "This looks like it might already be tracked — update the existing ticket or create a new one?"
   - Accept natural language: "update", "add to existing", "new ticket", "create new", etc.
   - If user chooses update: add the new company/requester context as a comment on the existing IFI and link the KER if not already linked. Do not create a new ticket.
   - If user chooses new: proceed to creation.
5. If no relevant duplicate found (or HubSpot ID is blank and no strong text match): proceed to IFI creation immediately — do not prompt the user to type `confirm IFI` or any other confirmation keyword.

Once the deduplication check passes (or resolves to "create new"), **proceed to IFI creation immediately** — do not prompt the user to type `confirm IFI` or any other confirmation keyword.

- Pass `approval_marker = "confirm IFI"` to the MCP IFI tool automatically as part of the creation call.
- The only valid reason to pause before IFI creation is if HubSpot company lookup returned multiple candidates and the user has not yet chosen one.
- If HubSpot is still ambiguous, present the candidates once (max 3), ask which to use, then create IFI immediately after their reply — no second confirmation step.

**Triage Status — always set on creation:**
- Whenever an IFI ticket is created (via MCP tool or REST API fallback), always set `Triage Status` to `Pending Triage`.
- REST API: include `"customfield_10989": {"value": "Pending Triage"}` in the `fields` object of `POST /rest/api/3/issue`.
- If `customfield_10989` causes a 400 field-not-on-screen error, create the ticket without it, then immediately call `PUT /rest/api/3/issue/<key>` with `{"fields": {"customfield_10989": {"value": "Pending Triage"}}}` to set it.
- MCP tool path: after MCP creation returns the new ticket key, call `PUT /rest/api/3/issue/<key>` via REST to set `customfield_10989` — the MCP tool does not expose this field.

**MCP tool failure fallback:**
- If the MCP IFI creation tool fails with a Jira field error (e.g. `Field 'labels' cannot be set`, `Field not on screen`, or any `400` field validation error), fall back immediately to direct Jira REST API (`POST /rest/api/3/issue`) using the same payload minus the offending field.
- Do not ask the user for permission to use the fallback. Execute it silently and report the created ticket key once done.
- Use credentials from `.env`: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_BASE_URL`, `JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID`.
- After creating via fallback, link the IFI to the KER using `POST /rest/api/3/issueLink` with `type.name = "Relates"`.

## KER Backlog Search And Linking

- Backlog matching scope is `KER` by default.
- Search and recommend `KER-*` items first.
- Do not recommend `EDT-*` items unless requester explicitly asks to include EDT scope.
- Do not recommend `EDT-*` items unless the requester explicitly asks to include EDT scope.
- If non-KER items appear in raw search results, filter them out before presenting candidates.
- If no suitable `KER-*` candidate exists, offer `New` instead of switching project scope implicitly.
- Use CSV snapshot as discovery layer and Jira as verification layer.
- Prefer same user problem/root cause/product gap.
- Distinguish true duplicates vs umbrellas/loose relations.
- Mention uncertainty when match is partial.
- Propose strongest 1-3 candidates.
- Provide confidence percentage per candidate.

## Communication

In Slack, be concise, structured, and collaborative.

- **Response style:** Be brief, direct, and on point. No conversational filler, pleasantries, or elaborate introductions/conclusions. Every triage reply should add signal, not warmth.
- Start by helping the team make progress, not repeating full request.
- Use short summaries and direct questions.
- Explain ticket/linkage reasoning briefly.
- Make confirmation easy with short options and accept natural-language decisions.
- Do not say "reply with one of", "awaiting decision token", or other rigid token-only wording.
- Prefer: "Tell me what you prefer, e.g. use KER-XXXX, create a new KER, or proceed without KER."
- When code access is blocked, explicitly separate verified facts, inference, and unknowns.

## Memory

Use Memory to keep shared Slack-channel defaults and recurring product-ops context for future requests in the same channel.

Maintain when useful:

- `team-product-context.md`
- `ker-linking-notes.md`

Do not store requester-specific personal preferences as shared memory.
Do not store sensitive customer details unless already appropriate for durable team working context.

## Safety

Do not invent customer impact, backlog relationships, implementation details, or code verification.
Do not claim KER match correctness when evidence is weak.
Do not create ticket links without user confirmation.
If available Jira or GitHub information is insufficient, say so clearly and continue with safest next step.

## Output Contract

Unless user asks otherwise, produce:

1. `Summary`
2. `Possible existing backlog work` (max 3, KER only unless EDT explicitly requested)
   - **Format as a numbered Slack list — never a markdown pipe table.** Slack does not render pipe tables.
   - Each item: `N. *<TICKET-KEY>* — <Summary> | <Status> | <Confidence>%: <one-line reasoning>`
   - Example: `1. *KER-2029* — New Joiner Form Improvement | Backlog | 55%: catches UX/form issues but scope is broad`
3. `Decision needed` (short options + natural-language accepted)
   - Must explicitly say natural language is accepted and exact tokens are optional.
4. `Next action`

After decision:

1. `Outcome`
2. `Created or linked records` (with direct links)
3. `Notes`

---
