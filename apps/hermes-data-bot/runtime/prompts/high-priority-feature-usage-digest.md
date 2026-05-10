Produce the weekly high-priority release feature usage digest for StaffAny.

Use the staffany-data-bot skill and follow these rules:

1. Read skills/staffany-data-bot/references/staffany-release-feature-registry.md first.
2. Do not query Jira live. Jira release and launch-priority facts must come only from the reviewed registry.
3. Include only rows with priority_mapping_status = confirmed and priority_class = high.
4. For rows with tracking_status = track, use usage_metric_key to find the matching definition in skills/staffany-data-bot/references/staffany-data-bot-metric-registry.md, then query BigQuery only through the read-only staffany_bigquery MCP.
5. For rows with tracking_status = needs-mapping or blocked, do not query BigQuery. Report the mapping blocker with Confidence: blocked.
6. Exclude rows with tracking_status = ignore.
7. Hide SQL unless explicitly asked.

Output normal Slack text, not a code block:

High-priority release feature usage digest
Scope: registry sync timestamp and release window checked

Feature: <canonical feature name>
Release: <release version/date/Jira key>
Usage: <adoption summary or exact blocker>
Source: <registry + BigQuery table, or registry only>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

If there are no confirmed high-priority release features ready for tracking and no blocked high-priority rows to explain, return:

Answer: No confirmed high-priority release features are ready for usage tracking yet.
Source: staffany-release-feature-registry.md
Scope: current reviewed registry
Confidence: blocked
Caveat: Jira launch-priority mapping or usage metric mapping still needs review.
