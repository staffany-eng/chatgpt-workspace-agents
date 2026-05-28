# StaffAny Hermes App Overlap Map

Last updated: 2026-05-28

## Apps on this VM

| App dir | Profile name | Primary lane |
|---|---|---|
| `launchbot` | `launchbot` | Help article drafts, KER/IFI intake (customer-demand surface), weekly support watch |
| `product-ops-bot` | `productopsbot` | Internal ops/product KER intake, IFI creation, Jira grooming, PRD generation |
| `psm-ops-bot` | `productopsbot` (same profile) | PSM PCO Jira JSM tasks, Customer 360 context |
| `nurtureany-sales-bot` | `nurtureanysalesbot` | HubSpot target accounts, sales enrichment, nurture drafts |
| `hermes-data-bot` | `staffanydatabot` | BigQuery metrics, product-term lookups, release-feature usage tracking |
| `bq-mcp-proxy` | — | Infrastructure proxy only, no skills or SOUL |
| `hermes-shared` | — | Shared assets only, no skills or SOUL |

## Overlap Matrix

### ⚠️ Launchbot ↔ Product Ops Bot — KER + IFI (most significant overlap)

| Capability | Launchbot | Product Ops Bot |
|---|---|---|
| KER ticket lookup | ✅ read-only from Slack thread | ✅ KER backlog search + CSV snapshot |
| IFI ticket creation | ✅ APQ/BD-note surface, linked to HubSpot Company ID | ✅ Internal ops/product intake surface |
| KER idea creation | ✅ `create intake` from Slack thread | ✅ `New` decision → creates KER |
| HubSpot company resolution | ✅ required before IFI | ❌ not in scope |
| Code grounding | ✅ Pantheon (develop branch) | ✅ Kraken/Gryphon via GitHub |

**Key distinction:** Launchbot IFI = customer-facing feature demand (APQ, BD notes), must resolve HubSpot Company ID. Product Ops Bot IFI = internal team intake from ops/product requests. Same Jira project, different entry surfaces and audiences.

### PSM Ops Bot ↔ Product Ops Bot — Jira ticket creation (mild)

- Both create Jira tickets but in different projects: PSM Ops Bot → JSM PCO board; Product Ops Bot → KER + IFI
- Both have "find existing ticket before creating duplicate" guard
- No functional collision — different audiences (PSMs vs. PMs/ops teams)

### Hermes Data Bot ↔ Product Ops Bot — Release feature tracking (mild)

- Data Bot: answers "what was released" from `staffany-release-feature-registry.md` + BigQuery usage actuals
- Product Ops Bot: grooms/PRDs those same Jira tickets for execution
- Overlap zone: "what was released in Jira" — each bot handles a different job (reporting vs. execution)
- No collision in practice

### NurtureAny Sales Bot

No meaningful overlap with any other app. Entirely HubSpot/sales lane.

## Skills Per App

```
launchbot/
  skills/
    help-article-generator/
    weekly-support-watch/

product-ops-bot/
  skills/
    product-ops-bot/           # top-level router
    product-ops-intake-linking/ # KER search → IFI creation flow
    staffany-product-delivery-workflow/ # Jira grooming, PRD, handoffs

psm-ops-bot/
  skills/
    psm-ops-bot/               # PCO JSM + Customer 360

nurtureany-sales-bot/
  skills/
    apify-facebook-scraper/
    apify-instagram-scraper/
    apify-linkedin-scraper/
    company-enrichment/
    nurtureany-sales-bot/
    publish-analysis-to-sheets/
    target-account-news-scout/

hermes-data-bot/
  skills/
    staffany-data-bot/         # BigQuery + product-term + release-feature registry
```

## How To Read Another App's Skills From Launchbot

```bash
# 1. List app directories
ls /home/leekaiyi/chatgpt-workspace-agents/apps/

# 2. List skills for a specific app
ls /home/leekaiyi/chatgpt-workspace-agents/apps/<app-name>/skills/

# 3. Read a skill
# Use read_file on /home/leekaiyi/chatgpt-workspace-agents/apps/<app-name>/skills/<skill-name>/SKILL.md

# 4. Read live profile SOUL
# /home/leekaiyi/.hermes/profiles/<profilename>/SOUL.md
```
