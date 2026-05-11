# Pre-Demo Game Plans

Use this reference when the user asks for `game plan`, `pre-demo prep`, `demo plan`, or `hypothesis plan` for selected target accounts.

## Scope

- Run only on demand for selected HubSpot company IDs, HubSpot company links, or exact company names.
- Cap each run at 5 accounts.
- Resolve names only inside the caller's scoped HubSpot target accounts. If one exact scoped match is found, proceed. If multiple scoped matches are found, return candidate company IDs and ask the user to pick. If no match is found, ask for the HubSpot company ID or link.
- Do not generate game plans for all target accounts by default.
- Preserve the originating Slack pre-meeting thread permalink as `Source thread` when the request supplies one. Store/link provenance only; do not copy raw Slack transcripts into HubSpot.

## Framework

Each account output must include:

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
- Source thread, when supplied

## Game Plan Rules

- Game Plan A is the primary route to win. Tie it to the strongest likely pain, the relevant StaffAny flow, and a commercial outcome.
- Game Plan B is the fallback route. Use a lighter package, pilot, buyback, proof-of-value, phased migration, or value-vs-price path only when the evidence supports it.
- Include rough pricing or package only when supplied by the user or present in approved source context. Otherwise write `pricing needed`.
- Include case studies only when supplied by approved source context or `case-studies.md`. Otherwise write `case-study match needed`.
- Keep the output punchy enough for a rep to use before a call. Avoid long ChatGPT-looking paragraphs.

## Evidence Rules

- HubSpot remains the source of truth for account scope, owner, target-account status, contacts, deals, tasks, and stored fields. Use company `current_tools` for current tools and company `contract_end_date` for renewal timing.
- Show HubSpot owner as name/email, not raw owner ID only. Resolve from HubSpot owners API.
- Explain decision-maker coverage using the actual HubSpot fields: `hs_num_decision_makers` counts associated contacts with buying role `DECISION_MAKER`; `hs_num_contacts_with_buying_roles` counts associated contacts with any buying role. Do not describe these as Eazybe signals unless evidence shows Eazybe changed the underlying HubSpot contact roles.
- For Calendar follow-up checks, scan the HubSpot company owner's email calendar through the `team@staffany.com` OAuth account. If that AE calendar is inaccessible, mark calendar coverage blocked/needs-check.
- Use customer/prospect status from HubSpot `type`, `lifecyclestage`, `prospecting_account`, and C360 when explicitly used. Say `renewal call` only for verified customers; for prospects use incumbent-tool contract timing, migration/procurement timing, or current-tool confirmation.
- Social/gated sources such as LinkedIn, Instagram, Facebook, TikTok, and Google Maps are manual-check only unless the user provides snippets.
- Public StaffAny case-study pages in `case-studies.md` are approved for name drops; Slack-only or WIP case-study mentions are not approved until a published page or approved internal asset exists.
- Do not scrape social/gated sources, reveal unnecessary PII, fetch raw task bodies, mutate HubSpot, or send external messages.
- If current tools, lead source, meeting reason, stakeholders, pricing, or case studies are missing, mark `Confidence: needs-check`.

## Slack Behavior

First Slack request is plan-first:

Interpreted question: <question>
Plan: I will build pre-demo game plans for the selected HubSpot accounts using scoped HubSpot account context only.
Estimate: 1-2 min
Caveat: I will not invent pricing, current tools, lead source, meeting reason, or case studies; missing items will be marked.
Reply "run" to start, or tell me what to change.

Do not add public/news/LinkedIn/social research to this preflight unless the user explicitly supplied snippets or separately approved a public-evidence workflow.

After `run`, call `build_pre_demo_game_plans` directly with the selected company IDs, HubSpot links, or raw exact names and return a Slack-first answer. If the request includes a useful pre-meeting Slack thread permalink, pass it as `source_slack_thread_url`; if the current request merely links to the true pre-meeting notes thread, use the linked thread as the source. Do not pre-resolve game-plan names with `list_team_target_accounts`, `score_nurture_accounts`, or `find_contact_gaps`; the game-plan tool owns scoped resolution and compact-name matching such as `Tung Lok` to `Tunglok`. If the tool returns ambiguous company-name candidates, ask the user to reply with the intended HubSpot company ID before building the plan. HubSpot write-back is a separate `plan_hubspot_writeback` preview after review and approval; when previewing a note, pass the same Slack permalink as `source_url` / `source_evidence` and do not paste the raw Slack text.
