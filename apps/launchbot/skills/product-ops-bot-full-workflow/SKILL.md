---
name: product-ops-bot-full-workflow
description: Full embedded Product Ops Bot workflow bundle for Launchbot. Use this skill for product operations intake, KER/IFI routing+linking, Jira grooming, PRD grooming, and RICE assessment using the exact app workflow copied from apps/product-ops-bot.
---

# Product Ops Bot Full Workflow (Embedded In Launchbot)

This skill is a full embedded copy of `apps/product-ops-bot` so Launchbot can use the exact workflow consistently.

## Source Of Truth Inside This Skill

Use these embedded files directly:
- `workflow/profile/SOUL.md`
- `workflow/profile/config.template.yaml`
- `workflow/runtime/slack.md`
- `workflow/runtime/jira.md`
- `workflow/runtime/health-checks.md`
- `workflow/runtime/check-health.sh`
- `workflow/runtime/audit-live-profile.sh`
- `workflow/runtime/mcp/README.md`
- `workflow/skills/product-ops-intake-linking/SKILL.md`
- `workflow/skills/staffany-product-delivery-workflow/SKILL.md`
- `workflow/skills/staffany-product-delivery-workflow/references/*`
- `workflow/skills/staffany-product-delivery-workflow/scripts/*`
- `workflow/tests/regression-cases.md`
- `workflow/app.manifest.json`

## Routing Rule

For product-ops requests (triage, investigate, product gap, IFI/KER create/update/link, Jira grooming, PRD grooming, RICE), follow the embedded Product Ops workflow first.

## Non-Goals

Do not replace Launchbot runtime MCP contracts or non-product-ops lanes with this skill. This skill governs product-ops behavior only.
