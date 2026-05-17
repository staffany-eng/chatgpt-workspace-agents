---
name: publish-analysis-to-sheets
description: Publish sanitized, table-shaped NurtureAny analysis output to the shared Google Sheets workbook after Slack run approval.
---

# Publish Analysis To Sheets

Use this skill when a NurtureAny Slack request produces table-shaped team analysis that would be painful to consume only in Slack, especially event RSVP/client/prospect/inviter breakdowns, target-account classification rows, manager-safe review rows, or other bounded tabular outputs.

## Routing

1. In the Slack preflight, say the run will export sanitized rows to the shared workbook in addition to the Slack summary.
2. Treat the same `run` as approval for the internal Sheet write only when the preflight mentioned the export.
3. Use source tools first. Do not create sheet rows from guesses.
4. Call `preview_analysis_sheet_export` with the final columns, row count, stable `idempotency_key`, source permalink, and sanitized sample rows.
5. If preview is verified, call `apply_analysis_sheet_export`.
6. In the final Slack response, include short answer, key counts, Sheet link, source, scope, confidence, and caveat.

## Safe Row Contract

Allowed fields include account name, HubSpot company ID, country, owner, account status, RSVP status, invited-by label, match reason, match confidence, safe source permalink, and aggregate counts.

Never export raw Slack transcripts, phone numbers, full attendee emails, raw HubSpot bodies, raw guest exports, raw registration answers, secrets, or broad unmatched attendee lists.

## Idempotency

Use stable keys from the source thread/run, for example:

```text
slack:<channel_id>:<thread_ts>:<analysis_slug>
```

Reruns must update the same `Runs` row and run tab instead of creating duplicate tabs.
