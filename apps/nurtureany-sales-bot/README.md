# NurtureAny Sales Bot

Canonical Hermes app packet for StaffAny's sales nurture bot.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `nurtureanysalesbot`
- Surface: Slack mentions in sales pilot channels
- Model: Anthropic Claude Sonnet provider configured in the live profile
- Primary data source: HubSpot CRM
- Enrichment sources: existing sales-owned HubSpot follow-up tasks, free public evidence tasks/review, StaffAny C360 through read-only BigQuery, Luma event context when configured, Exa People Search public candidate discovery when configured, and approval-gated Lusha decision-maker lookup when configured
- V1 regions: Singapore, Malaysia, Indonesia
- V1 safety mode: review-first, no external message auto-send
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/nurtureanysalesbot/`

## Relationship To Da Ta Hermz

NurtureAny is a separate Hermes profile from Da Ta Hermz.

| Bot | Hermes profile | Responsibility |
| --- | --- | --- |
| Da Ta Hermz | `staffanydatabot` | General StaffAny data bot and BigQuery/C360 analysis workflows. |
| NurtureAny | `nurtureanysalesbot` | Sales nurture workflow for HubSpot target accounts, AE queues, manager queues, and approved HubSpot write-back previews. |

The two profiles may share model authentication credentials during the pilot. They must not share Slack app tokens, HubSpot tool policy, SOUL prompts, skills, runtime safety rules, or business state.

For production, prefer a dedicated service credential for NurtureAny model auth instead of copied pilot auth from Da Ta Hermz.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `profile/SOUL.md` | Source-controlled copy of the profile soul prompt. |
| `profile/config.template.yaml` | Non-secret profile config template and access policy. |
| `skills/nurtureany-sales-bot/` | Hermes skill and progressive-disclosure references. |
| `runtime/slack.md` | Slack gateway behavior, commands, and run gate. |
| `runtime/hubspot.md` | HubSpot API contract, fields, and write approval rules. |
| `runtime/bigquery.md` | C360 read-only enrichment contract. |
| `runtime/luma.md` | Luma event-context contract. |
| `runtime/exa.md` | Exa People Search public candidate-discovery and cost-reporting contract. |
| `runtime/lusha.md` | Cost-controlled Lusha lookup, selected-PII, and credit-reporting contract. |
| `runtime/health-checks.md` | Operational checks and expected silence. |
| `tests/regression-cases.md` | Manual/eval regression cases for app behavior. |

## Product Scope

NurtureAny helps AEs and sales managers work the HubSpot target-account list:

- AEs ask for their own target accounts and nurture queue.
- Managers ask for team queues, missing direct contacts, renewal risk, post-demo nurture, overdue nurture work, and existing sales follow-up tasks.
- The bot ranks accounts, identifies enrichment gaps, generates free public search tasks, reviews public evidence, searches Exa for public people candidates when approved, searches Lusha for selected decision-maker candidates when approved, drafts nurture messages, and previews HubSpot write-backs.
- Existing HubSpot sales follow-up tasks are read-only prioritization signals. New HubSpot tasks, notes, and field updates happen only after explicit approval.

V1 does not send WhatsApp, email, LinkedIn, or sequence messages.

## Access Model

Slack user email maps to HubSpot owner email, then to `hubspot_owner_id`.

| Role | Slack email | Scope |
| --- | --- | --- |
| Overall admin | `eugene@staffany.com` | Singapore, Malaysia, Indonesia |
| Overall admin | `kaiyi@staffany.com` | Singapore, Malaysia, Indonesia |
| SG/MY manager | `kerren.fong@staffany.com` | Singapore, Malaysia |
| Indonesia manager | `sarah@staffany.com` | Indonesia |
| AE | Any mapped HubSpot owner email | Own target accounts only |

Permissions are explicit config, not inferred from Slack titles.

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `nurtureanysalesbot` profile.
3. Copy `profile/SOUL.md` into the profile's `SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Copy `skills/nurtureany-sales-bot/` into the profile skills directory.
6. Set profile `.env` from Secret Manager values only; do not commit or inline model-provider or Lusha credentials.
7. Configure Slack gateway, HubSpot MCP/API adapter, StaffAny BigQuery MCP, optional Luma adapter, optional Exa MCP with `EXA_API_KEY`, and optional Lusha MCP with `LUSHA_API_KEY`.
8. Run health checks and regression cases before adding sales channels.

## Canonical Source Rule

The live Hermes profile may accumulate local state and runtime learning. Treat that as unreviewed drift until the specific useful change is copied back here and committed.
