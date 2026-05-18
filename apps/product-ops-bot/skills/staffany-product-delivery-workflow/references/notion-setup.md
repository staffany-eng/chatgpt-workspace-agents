# Notion Setup for PRD Workflow

Use this checklist once per workspace.

## 1) Create Integration
- Notion -> `Settings & members` -> `Connections` -> `Develop or manage integrations`.
- Create internal integration (example: `Codex PRD Sync`).
- Keep token in password manager.

## 2) Share Database/Page to Integration
- Open PRD database or parent PRD page.
- `Share` -> invite integration -> grant edit permission.

## 3) Standardize PRD Database Properties
- `Name` (title)
- `Status` (select)
- `Owner` (people/text)
- `Release` (text/select)
- `Updated At` (date)
- `Jira` (url/text)

## 4) Build PRD Template Page
- Add fixed section headings:
  - Requirements
  - Acceptance Criteria Authoring Rules
  - Current UX Baseline (Mandatory When UX Scope Exists)
  - Affected Files (Predicted)
  - Risks
  - Open Questions
  - Reference Links Used for Benchmarking
- Keep page properties available for:
  - `Target Release`, `Tags`, `DRI`, `Goals`, `Background and strategic fit`, `Scope`, `Out of Scope`, `Assumption`
- The sync script will create and maintain the inline linked `Requirements` database view automatically.

## 5) Connect Notion in Codex
- Open Codex Apps/Connectors.
- Connect Notion workspace account.
- Verify Codex can open PRD database and one page.

## 6) Optional Local Env Aliases
- `NOTION_PRD_DATABASE_ID=<database_id>`
- `NOTION_PRD_TEMPLATE_PAGE_ID=<template_page_id>`
- `NOTION_PRD_DEFAULT_PAGE_URL=<page_url>`

## 7) Validation Test
- Generate one PRD markdown in `outputs/prd/...`.
- Sync/create corresponding Notion PRD page.
- Confirm Requirements inline table shows columns: `Code`, `Name`, `Priority`, `Notes`.
- Confirm each requirement has sub-page content including `User Story` and `Acceptance Criteria`.

## 8) Skill-Local Script Path
- Use the script under this skill directory:
  - `pantheon/apps/grimoire/catalog/shared/staffany-product-delivery-workflow/scripts/sync-prd-notion.mjs`
