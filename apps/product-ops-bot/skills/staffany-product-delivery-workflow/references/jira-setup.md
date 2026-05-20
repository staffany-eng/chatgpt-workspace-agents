# Jira Connection Setup

Use this guide to bootstrap Jira connectivity before running `direct-sync`.

## Available Local Scripts

- `scripts/read-jira-ticket.mjs` - reads ticket summary/description/comments
- `scripts/sync-jira-ticket.mjs` - writes markdown to Jira (`description`/`comment`/`both`)
- `scripts/load-env.mjs` - auto-loads local `.env` from current working directory or the skill directory

Set:

```bash
SKILL_DIR="pantheon/apps/grimoire/catalog/shared/staffany-product-delivery-workflow"
```

## Required Fields

- Jira issue key or browse URL (for example `KER-304` or full Jira URL)
- Sync mode: `description` | `comment` | `both`
- Output markdown file path (for example `outputs/jira/YYYY-MM-DD-...md`)
- Local credentials in `.env`:
 - `JIRA_BASE_URL` (for example `https://staffany.atlassian.net`)
 - `JIRA_EMAIL`
 - `JIRA_API_TOKEN`
 - Optional custom-field ids for RICE + review checkbox sync:
   - `JIRA_FIELD_NEED_PRODUCT_REVIEW` (default script fallback: `customfield_10843`)
   - `JIRA_FIELD_REACH`
   - `JIRA_FIELD_IMPACT`
   - `JIRA_FIELD_CONFIDENCE`
   - `JIRA_FIELD_EFFORT`
   - `JIRA_FIELD_RICE_SCORE`
   - `JIRA_FIELD_RICE_RATIONALE`

## Setup Steps

1. Ensure `.env` exists in the skill directory (or repo root/current working directory).
2. Add Jira credentials:

```bash
JIRA_BASE_URL="https://staffany.atlassian.net"
JIRA_EMAIL="your-email@company.com"
JIRA_API_TOKEN="your-atlassian-api-token"
```

3. Verify read access:

```bash
node "$SKILL_DIR/scripts/read-jira-ticket.mjs" --issue <ISSUE_KEY_OR_URL> --dry-run
node "$SKILL_DIR/scripts/read-jira-ticket.mjs" --issue <ISSUE_KEY_OR_URL> --include-links --include-comments --max-comments 10
```

4. Verify sync payload:

```bash
node "$SKILL_DIR/scripts/sync-jira-ticket.mjs" \
  --issue <ISSUE_KEY_OR_URL> \
  --file outputs/jira/YYYY-MM-DD-short-kebab-title.md \
  --mode description \
  --set-need-product-review 1 \
  --dry-run
```

5. Execute actual sync after dry-run looks correct:

```bash
node "$SKILL_DIR/scripts/sync-jira-ticket.mjs" \
  --issue <ISSUE_KEY_OR_URL> \
  --file outputs/jira/YYYY-MM-DD-short-kebab-title.md \
  --mode description \
  --set-need-product-review 1
```

## Fallback

If setup fields are unavailable, proceed with `md-only` and return the explicit sync command for later.
