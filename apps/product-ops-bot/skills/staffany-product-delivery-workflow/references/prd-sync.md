# PRD Notion Sync Guide

Use this guide when PRD drafting/iteration uses Notion as the source of truth.

## Default Direction

- PRD source of truth is Notion (not Google Docs).
- Keep markdown output in `outputs/prd/...` as local artifact for versioned handoff.
- Sync markdown content into one Notion PRD page for collaboration and iteration.
- PRD title format standard: `YYYYMMDD - <Title> (PRD)`.
- PRD markdown filename format standard: `YYYYMMDD - <Title> (PRD).md`.

## Modes

- `direct-sync`: Notion page/database record exists; read current content first, then update relevant sections.
- `full-overwrite`: replace entire PRD page body only when user explicitly requests rewrite.
- `md-only`: no Notion target yet; produce markdown and return explicit steps to create/sync in Notion.

## PRD Lifecycle Rule (New vs Existing)

- If PRD does not exist yet:
  - Create PRD from Notion template inside PRD database.
  - Populate metadata fields via page properties (including Target Release only when explicitly provided, and DRI only when explicitly provided).
  - Build Requirements inline table view and requirement sub-pages from markdown.
- If PRD already exists:
  - Treat existing Notion page as source of truth.
  - Update the same page and re-sync requirements content unless explicit rewrite scope says otherwise.

## Required Inputs Before Direct Sync

- Notion workspace connected in Codex.
- Target page URL/ID, or PRD database URL/ID.
- Markdown source path (for example `outputs/prd/20260429 - Approval System (PRD).md`).
- Update mode: `add-missing-only` (default) or `full-replace` (explicit only).
- Script mode: `replace` (current runtime default) or `append`.

If any input is missing, proceed with `md-only` first.

## Content Mapping (Markdown -> Notion, Current Runtime)

Map markdown sections to Notion blocks/properties:

- `# Product Requirements Document - <Title>` -> normalized page title: `YYYYMMDD - <Title> (PRD)`
- `## Target Releases` and `## Overview` -> mapped into page properties where available:
  - `Target Release` (only if explicitly provided)
  - `Tags`
  - `DRI` (only if explicitly provided)
  - `Goals`
  - `Background and strategic fit`
  - `Scope`
  - `Out of Scope`
  - `Assumption`
- `## Requirements` -> inline linked database table on PRD page with columns:
  - `Code`, `Name`, `Priority`, `Notes`
- each requirement row -> requirement sub-page content blocks:
  - `User Story`
  - `Requirement`
  - `Acceptance Criteria`
  - `Meta`
- body append sections currently include:
  - `Acceptance Criteria Authoring Rules`
  - `Current UX Baseline (Mandatory When UX Scope Exists)`
  - `Affected Files (Predicted)`
  - `Risks`
  - `Open Questions`
  - `Reference Links Used for Benchmarking`

Acceptance Criteria rule:
- Acceptance Criteria source remains in PRD markdown Requirements table.
- In Notion, AC is written into each requirement sub-page under `Acceptance Criteria` (numbered list items).

## Practical Sync Flow in This Skill

1. Generate/refresh markdown PRD in `outputs/prd/...`.
2. Resolve target page/database/template via args or env.
3. Patch Notion page properties from markdown.
4. Build/refresh inline Requirements table view and requirement sub-pages.
5. Append remaining PRD narrative sections in body.
6. Return updated Notion page URL in final output.

## Decision Rules

- Current script supports `replace` and `append`.
- Use full rewrite behavior only with explicit user instruction.
- If markdown and Notion conflict, ask user which is source of truth before write.
- For iteration requests, update same page rather than creating new page.

## Step-by-Step Setup (Notion)

1. Create Notion integration:
- Notion -> `Settings & members` -> `Connections` -> `Develop or manage integrations`.
- Create internal integration (example name: `Codex PRD Sync`).
- Copy integration token.

2. Share PRD workspace/database with integration:
- Open PRD database (or PRD parent page).
- `Share` -> invite integration (`Codex PRD Sync`) with edit access.

3. Create PRD database schema:
- Required properties:
  - `Name` (title)
  - `Status` (select)
  - `Owner` (people/text)
  - `Release` (text/select)
  - `Updated At` (date)
  - `Jira` (url/text)

4. Prepare PRD page template in Notion:
- Add canonical headings matching markdown sections.
- Add an inline/child database named `Requirements` in the page body.
- Required DB properties: `Name`, `Priority`, `Notes` (plus optional `Status`, `Owner`, `Due Date`, `SR`, `User story`, `Eng-Unit`).
- Each requirement row will be created as a database item page, and Acceptance Criteria will be written inside the item page content.

5. Configure Codex app connector:
- In Codex Apps, connect Notion account/workspace.
- Verify Codex can list and open PRD database/page.

6. Save local env hints (optional but recommended):
- `NOTION_PRD_DATABASE_ID=<database_id>`
- `NOTION_PRD_TEMPLATE_PAGE_ID=<template_page_id>`
- `NOTION_PRD_DEFAULT_PAGE_URL=<page_url>`

7. First test run:
- Generate markdown PRD to `outputs/prd/...`.
- Ask skill to create PRD in Notion from template and sync sections.
- Verify Requirements table + AC rows are rendered correctly.

8. Iteration workflow:
- Keep using same Notion PRD page URL.
- Ask skill to update specific sections (or full PRD).
- Confirm changelog/review in Notion page history.

## Troubleshooting

- Notion page not found:
  - Check page/database is shared to integration.
- Permission denied:
  - Ensure integration has edit access on target page and parent database.
- Bad table formatting:
  - Ensure template has stable section headings and table placeholders.
- Duplicate PRDs:
  - Reuse existing page URL for iterations; avoid creating a new page each run.

## CLI Sync Script (Local)

Use local script for create/update:

```bash
# Create a new PRD page in Notion database, then fill content from markdown
SKILL_DIR="pantheon/apps/grimoire/catalog/shared/staffany-product-delivery-workflow"
node "$SKILL_DIR/scripts/sync-prd-notion.mjs" \
  --database <NOTION_DATABASE_ID_OR_URL> \
  --title "20260429 - Approval System (PRD)" \
  --file outputs/prd/2026-04-27-manual-overtime-feature-prd.md \
  --mode replace
```

```bash
# Update an existing Notion PRD page
SKILL_DIR="pantheon/apps/grimoire/catalog/shared/staffany-product-delivery-workflow"
node "$SKILL_DIR/scripts/sync-prd-notion.mjs" \
  --page <NOTION_PAGE_ID_OR_URL> \
  --file outputs/prd/2026-04-27-manual-overtime-feature-prd.md \
  --mode replace
```

Required env:
- `NOTION_API_TOKEN`

Optional env:
- `NOTION_PRD_DATABASE_ID`
- `NOTION_PRD_DEFAULT_PAGE_URL`
