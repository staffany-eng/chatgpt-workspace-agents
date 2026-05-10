# Jira Release Sync Workflow

This workflow creates a reviewed release-feature registry from Jira. Hermes Data Bot must use the synced registry, not live Jira, when answering Slack questions or producing the weekly high-priority feature usage digest.

## Source Boundary

- Jira supplies release facts, issue keys, release versions, release dates, product area hints, owners, and launch-priority values.
- BigQuery supplies usage actuals.
- The reviewed registry lives at `skills/staffany-data-bot/references/staffany-release-feature-registry.md`.
- Do not copy Jira descriptions, comments, attachments, private customer content, or secrets into the registry.

## Required Inputs

The sync script reads these environment variables:

- `JIRA_BASE_URL`: StaffAny Jira base URL.
- `JIRA_EMAIL`: Jira API user email.
- `JIRA_API_TOKEN`: Jira API token from the operator's secret store.
- `JIRA_JQL`: optional release issue query. Default: `project = KER AND "Launch Priority" = "P1 - High Reach Retention and Growth" ORDER BY updated DESC`.
- `JIRA_LAUNCH_PRIORITY_FIELD_ID`: confirmed custom launch-priority field ID, for example `customfield_12345`.
- `JIRA_LAUNCH_PRIORITY_FIELD_NAME`: confirmed field label, for example `Launch Priority`.
- `JIRA_HIGH_PRIORITY_VALUES`: comma-separated values that count as high priority. For StaffAny launch tracking, use `P1 - High Reach Retention and Growth` unless Product changes the Jira value.

The script uses Jira Cloud REST API v3 field discovery and JQL issue search at `/rest/api/3/search/jql`.

## Discovery Gate

Run discovery first without `JIRA_LAUNCH_PRIORITY_FIELD_ID` or `JIRA_HIGH_PRIORITY_VALUES`:

```bash
apps/hermes-data-bot/runtime/sync-jira-release-registry.sh
```

Expected result:

- The script prints candidate custom fields and exits with `sync:priority-mapping-needs-confirmation`.
- A human reviews the candidates, confirms the field ID/name and included high-priority values, then updates the Priority Mapping table in the registry.
- Only after that confirmation should the sync be rerun with `JIRA_LAUNCH_PRIORITY_FIELD_ID`, `JIRA_LAUNCH_PRIORITY_FIELD_NAME`, and `JIRA_HIGH_PRIORITY_VALUES`.

## Reviewed Sync

After confirmation, generate a draft registry table:

```bash
JIRA_LAUNCH_PRIORITY_FIELD_ID=customfield_12345 \
JIRA_LAUNCH_PRIORITY_FIELD_NAME="Launch Priority" \
JIRA_HIGH_PRIORITY_VALUES="P1 - High Reach Retention and Growth" \
apps/hermes-data-bot/runtime/sync-jira-release-registry.sh > /tmp/staffany-release-feature-registry.draft.md
```

Review the draft before copying safe rows into `staffany-release-feature-registry.md`.

For each high-priority row, set:

- `usage_metric_key` to an existing metric registry key only after the metric source is safe.
- `tracking_status` to `track` only when `usage_metric_key` is reviewed.
- `tracking_status` to `needs-mapping` when Jira confirms high priority but no safe usage metric exists yet.

## Verification

After updating the registry:

```bash
npm run hermes-data-bot:verify
```

Before enabling or changing the digest cron, run the digest prompt manually as described in `runtime/high-priority-feature-digest.md`.
