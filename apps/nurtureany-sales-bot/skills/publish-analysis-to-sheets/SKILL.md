---
name: publish-analysis-to-sheets
description: Preview sanitized, table-shaped NurtureAny analysis output for the shared Google Sheets workbook, then write only after explicit Sheet approval.
---

# Publish Analysis To Sheets

Use this skill when a NurtureAny Slack request produces table-shaped team analysis that would be painful to consume only in Slack, especially event RSVP/client/prospect/inviter breakdowns, target-account classification rows, manager-safe review rows, or other bounded tabular outputs.

## Routing

1. In the Slack preflight, say the run will prepare a sanitized Sheet preview in addition to the Slack summary.
2. Treat the same `run` as approval to build and preview the Sheet rows only. Do not write until the user explicitly approves the Sheet write.
3. Use source tools first. Do not create sheet rows from guesses.
4. Call `preview_analysis_sheet_export` with the final columns, row count, stable `idempotency_key`, source permalink, and sanitized sample rows.
5. If preview is verified, show the planned row count/tab and ask for exact approval such as `apply Sheet` or `confirm Sheet`.
6. Call `apply_analysis_sheet_export` only after that explicit Sheet approval in the same thread.
7. In the final Slack response, include short answer, key counts, preview/write status, Sheet link when written, source, scope, confidence, and caveat.

## Safe Row Contract

Allowed fields include account name, HubSpot company ID, country, owner, account status, RSVP status, invited-by label, match reason, match confidence, safe source permalink, and aggregate counts.

Never export raw Slack transcripts, phone numbers, full attendee emails, raw HubSpot bodies, raw guest exports, raw registration answers, secrets, or broad unmatched attendee lists.

For event match action queues, use one tab named `Event Match Action Queue` and the safe columns: `event_id`, `event_name`, `rsvp_status`, `account_name`, `hubspot_company_link`, `hubspot_contact_link_if_exact_match`, `owner`, `customer_or_prospect`, `match_level`, `confidence`, `root_cause`, `next_action`, `action_owner`, `due_by`, `status`, and `source_run_link`.

## Idempotency

Use stable keys from the source thread/run, for example:

```text
slack:<channel_id>:<thread_ts>:<analysis_slug>
```

Reruns must update the same `Runs` row and run tab instead of creating duplicate tabs.
