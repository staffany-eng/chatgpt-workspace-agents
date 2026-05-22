---
name: staffany-product-delivery-workflow
description: StaffAny PM workflow orchestration for Jira grooming, PRD/docs drafting, and frontend/backend implementation handoffs. Use when tasks require triage routing, model-tier enforcement (Triage=Low, PM/Designer=Medium, FE/BE=High), backend-first context checks (Kraken then Gryphon), and direct Jira updates when write preconditions are satisfied.
---

# StaffAny Product Delivery Workflow

Follow this skill when handling requests in the StaffAny monorepo that need structured routing, consistent documentation outputs, and auditable handoffs.

## Self-Contained Assets

All required workflow assets for this skill are local to this directory:
- `references/` for templates, checklists, and sync/setup guides
- `scripts/` for Jira and Notion sync tooling

## Quick Start

1. Read root `AGENTS.md`, then any nested `AGENTS.md` in target subdirectories.
2. Fill preflight checks mentally and only ask follow-up questions when missing context would risk a wrong Jira write.
4. Run triage routing and record handoff entries with required fields.
5. Use backend-first source of truth (`pantheon/apps/kraken`), then quick frontend check (`pantheon/apps/gryphon`).
6. For Jira grooming, update the Jira ticket directly after context + RICE are complete.
7. Use local markdown output only when Jira write is blocked or user explicitly asks for file output.

For required field-level details, read:
- `references/workflow-checklist.md`
- `references/output-rules.md`
- `references/jira-grooming-template.md`
- `references/prd-template.md`
- `references/prd-sync.md`
- `references/notion-setup.md`
- `references/rice-assessment.md`
- `references/jira-sync.md`
- `references/jira-setup.md`

## Triage Routing Rules

Apply these route rules:
- Use `Triage -> User` for simple questions that can be answered directly.
- Use `PM` first for Jira grooming, PRD/docs drafting, requirement shaping, and net-new features.
- Use `Frontend` directly for clear UI-only implementation tasks.
- Use `Backend` directly for clear backend-only fixes.
- Use `PM -> Designer -> Frontend -> Backend` for ambiguous feature-level work.
- Use `PM -> Designer -> Frontend` for prototype-first requests (mock data only), then pause for review before backend.

When triage resolves directly:
- Record `triage_resolved_directly = true` in the plan.
- Record `selected_reasoning_tier = Low`.
- Add short `resolution_note` and `why_no_handoff_needed`.

## Model Tier Policy

Default reasoning tiers by agent:
- Triage Agent: `Low`
- PM Agent: `Medium`
- Designer Agent: `Medium`
- Frontend Agent: `High`
- Backend Agent: `High`

Override only when needed. Log reason in the plan.

## Output Mapping

Map requests to templates and destinations:
- Jira grooming -> template `references/jira-grooming-template.md` -> direct Jira description/comment sync by default
- PRD writing -> template `references/prd-template.md` -> `outputs/prd/YYYYMMDD - <Title> (PRD).md`
- Other docs -> `outputs/docs/YYYY-MM-DD-short-kebab-title.md`

For multiple tickets/documents, create one file per ticket/document.

## PRD Notion Connection (Read + Update)

For PRD requests, Notion is the default collaboration/source-of-truth destination.

For PRD requests with Notion target, support:
- `direct-sync`: Notion page/database target provided. Read current page first, then apply scoped updates.
- `full-overwrite`: replace full PRD page content only when user explicitly requests rewrite/overwrite.
- `md-only`: no Notion target yet. Produce markdown and return explicit Notion setup/sync steps.

PRD authoring lifecycle (mandatory):
- If PRD is not yet generated:
  - create PRD page from Notion PRD template in the target PRD database
  - read template styling/guideline blocks first
  - draft PRD content in markdown + sync to Notion
- If PRD already exists:
  - update the existing Notion PRD page with relevant new context only

Notion sync preflight rule (mandatory):
- Before update, verify target Notion page/database is reachable and editable.
- Verify Requirements model exists/works:
  - inline linked `Requirements` table view on page (`Code`, `Name`, `Priority`, `Notes`)
  - requirement sub-pages containing `Acceptance Criteria`
- Iterate Requirements/Acceptance Criteria through requirement rows/sub-pages.
- If preflight fails, stop immediately with one actionable error.

Required fields before direct sync:
- Notion page URL/ID or PRD database URL/ID.
- Output markdown file path under `outputs/prd/...`.
- Update mode: `add-missing-only` (default) or `full-replace` (explicit only).

If required fields are missing:
- proceed with `md-only` output first,
- then return explicit sync command for later.

When the latest reviewed source is already the Notion page, default to `add-missing-only` and preserve reviewed wording.

## Jira Ticket Connection (Read + Update)

For Jira grooming requests, support both modes:
- `direct-sync` (default): Jira issue key/link is provided and credentials are available. Read ticket context first, then sync directly to Jira in the same run.
- `md-only` (fallback): use only when Jira access is blocked, issue key is missing, or user explicitly asks for markdown output.

When Jira cannot be accessed directly in-session (for example no Jira connector/tool, auth-gated URL, or missing credentials), explicitly ask for the required fields below before attempting sync:
- Jira issue key or browse URL (for example `KER-304`).
- Desired sync mode: `description` | `comment` | `both`.
- Confirmation that Jira credentials are available in local `.env`:
  - `JIRA_BASE_URL`
  - `JIRA_EMAIL`
  - `JIRA_API_TOKEN`

If any required field is missing:
- do not pretend the write happened,
- continue with best safe read-only guidance,
- use `md-only` only as fallback.

Use local scripts inside this skill directory:
- Read ticket context:
  - `node <skill-dir>/scripts/read-jira-ticket.mjs --issue <ISSUE_KEY_OR_URL> --include-comments --max-comments 10`
  - Add `--include-links` to inspect linked items (`IFI-*` evidence extraction).
- Sync grooming content to Jira description:
  - `node <skill-dir>/scripts/sync-jira-ticket.mjs --issue <ISSUE_KEY_OR_URL> --file <TEMP_MARKDOWN_PATH> --mode description --set-need-product-review 1`
  - This sync script enforces mandatory RICE presence by default and fails fast if missing.
  - Use `--set-need-product-review 0` after manual product acceptance.
  - Override only when intentionally syncing non-grooming content: add `--skip-rice-check`.

Before first direct sync, run Jira bootstrap steps from `references/jira-setup.md` to verify credentials and dry-run connectivity.

Environment variables required (auto-loaded from local `.env` when present):
- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

## Jira Writing Rules

- Keep one `Acceptance Criteria` section.
- Include both frontend and backend requirements.
- Order criteria: frontend-impact first, then backend/logic.
- Do not prefix criteria with `Frontend:` or `Backend:`.
- Include `Affected Files (Predicted)` with concrete paths (or `TBD` + reason).
- Include a full RICE assessment for every Jira grooming output using `references/rice-assessment.md`.
- Default flow: after drafting grooming content, compute and append the RICE section before finalizing/syncing.

## Required Handoff Logging

For each transition, include all required fields:
- `destination_agent`
- `task_summary`
- `request_type`
- `selected_reasoning_tier`
- `source_of_truth_checked`
- `constraints`
- `acceptance_criteria_or_fix_target`
- `affected_files`
- `jira_target_ticket`
- `notion_target_document`
- `open_questions`
- `done_signal`

Use `references/workflow-checklist.md` as the canonical checklist.

## Quality Gates

Before execution:
- Complete preflight checks in plan.

During execution:
- Do not move to next stage when handoff fields are incomplete.

At completion:
- Report what was updated in Jira (fields/sections), source-of-truth used, validation status, and open questions.

## Competitor Benchmark Rule

For net-new feature requests, benchmark at least 3 relevant competitors from:
- Talenox, Talenta, 7Shift, Gusto, Homebase, Infotech, BrioHR, Kakitangan, Swingvy.

Record findings succinctly in output docs.
