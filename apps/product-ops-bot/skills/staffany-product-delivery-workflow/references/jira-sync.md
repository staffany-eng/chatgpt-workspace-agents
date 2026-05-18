# Jira Sync Guide

Use this guide when grooming Jira tickets with read/update integration.

For first-time environment bootstrap, run setup in `references/jira-setup.md` first.

## Modes

- `direct-sync`: issue key/link provided; read current ticket context first, then sync final markdown back.
- `md-only`: no issue key/link yet; produce markdown only and provide a sync command.

## Required Fields To Connect Jira

Collect these before direct sync:
- `issue`: Jira issue key or browse URL (for example `KER-304` or full Jira URL)
- `mode`: `description` | `comment` | `both`
- `file`: markdown path to sync (for example `outputs/jira/2026-04-16-ker-304-....md`)
- Jira credentials availability in local environment:
  - `JIRA_BASE_URL`
  - `JIRA_EMAIL`
  - `JIRA_API_TOKEN`

If Jira is not accessible in-session (no connector/tool exposure or auth-gated browser session), ask for the fields above explicitly and continue with `md-only` until they are provided.

## Read Existing Ticket Context

```bash
SKILL_DIR="pantheon/apps/grimoire/catalog/shared/staffany-product-delivery-workflow"
node "$SKILL_DIR/scripts/read-jira-ticket.mjs" \
  --issue <ISSUE_KEY_OR_URL> \
  --include-links \
  --include-comments \
  --max-comments 10
```

## Sync Final Markdown Back To Jira

Default behavior is updating the issue description:

```bash
SKILL_DIR="pantheon/apps/grimoire/catalog/shared/staffany-product-delivery-workflow"
node "$SKILL_DIR/scripts/sync-jira-ticket.mjs" \
  --issue <ISSUE_KEY_OR_URL> \
  --file outputs/jira/YYYY-MM-DD-short-kebab-title.md \
  --mode description \
  --set-need-product-review 1
```

By default, sync enforces mandatory RICE validation and will fail if the markdown does not contain:
- `## RICE Assessment`
- factor rows for `Reach`, `Impact`, `Confidence`, `Effort`, and `RICE Score`

Optional mode variants:
- `--mode comment` to post as a comment
- `--mode both` to update description and post comment
- `--set-need-product-review 1` to check `Need Product Review` (`customfield_10843`)
- `--set-need-product-review 0` to uncheck it after manual product acceptance
- `--skip-rice-check` to bypass RICE validation intentionally (use sparingly)

Optional field sync behavior:
- If configured, script also writes RICE components into Jira fields from markdown:
  - `JIRA_FIELD_REACH`
  - `JIRA_FIELD_IMPACT`
  - `JIRA_FIELD_CONFIDENCE`
  - `JIRA_FIELD_EFFORT`
  - `JIRA_FIELD_RICE_RATIONALE`

## Required Environment Variables

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

These are loaded from local `.env` via repo scripts when available.
