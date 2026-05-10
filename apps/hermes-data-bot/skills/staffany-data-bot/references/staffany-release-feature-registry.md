# StaffAny Release Feature Registry

This reviewed registry is the only Jira release source Hermes Data Bot may use for release-feature usage tracking.

Jira is a release and priority source. BigQuery remains the usage source. Do not query Jira live from Slack answers or scheduled digests.

## Current State

- Registry status: synced from Jira on 2026-05-10T18:10:45Z and reviewed for launch-priority classification.
- Priority mapping status: `confirmed`.
- Known candidate Jira project: `KER` (Kaiyi's Excel Replacement).
- Confirmed launch-priority value: `P1 - High Reach Retention and Growth`.
- Trackable feature rows: Club Blue is tracked with the current `kraken_prod.engagement_reward_redemption` proxy source; Avatar standardization remains blocked after metric-source review.
- Weekly digest target: Slack `#kaiyi-bot-testing`, Mondays 9am SGT.

## Priority Mapping

The Jira sync workflow must fill this table from read-only Jira discovery, then a human must confirm the exact field and high-priority values before any row becomes trackable.

| mapping_key | jira_field_id | jira_field_name | candidate_values | included_high_priority_values | status | confirmed_by | confirmed_at | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| launch_priority | customfield_10561 | Launch Priority | P1 - High Reach Retention and Growth | P1 - High Reach Retention and Growth | confirmed | VK Slack guidance + Jira field discovery | 2026-05-11 | Candidate from Slack guidance in `#proj-first-agent` on 2026-04-15; Jira field discovery confirmed the custom field ID. Do not infer high priority from Jira's built-in engineering priority unless this row is explicitly reviewed. |

Allowed `status` values:

- `needs-confirmation`: field/value candidates are discovered but not approved.
- `confirmed`: field ID, field name, and included high-priority values are reviewed.
- `rejected`: candidate field/value mapping must not be used.

## Release Feature Rows

Required row schema:

| jira_issue_key | release_version | release_date | canonical_feature_name | product_area | launch_priority_field | launch_priority_value | priority_mapping_status | priority_class | usage_metric_key | source_table_hint | owner | sync_timestamp | tracking_status | caveat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KER-1884 |  |  | Standardise Avatar Sizes Across Gryphon | Gryphon Design System | Launch Priority | P1 - High Reach Retention and Growth | confirmed | high | gryphon_avatar_size_standardization_usage | no-safe-usage-source |  | 2026-05-10T18:10:45Z | blocked | Visual standardization has no dedicated usage/adoption event or warehouse source; do not proxy with generic Gryphon page views. |
| KER-1742 |  |  | Club Blue | ClubAny / Engagement | Launch Priority | P1 - High Reach Retention and Growth | confirmed | high | club_blue_redemption_usage | `staffany-warehouse.kraken_prod.engagement_reward_redemption` |  | 2026-05-10T18:10:45Z | track | Track using current Engagement Reward Redemption events as a Club Blue / ClubAny proxy. Confidence is `needs-check` until owner confirms this proxy or a dedicated Club Blue source exists. |

Allowed `priority_class` values:

- `high`: row matches the confirmed launch-priority mapping.
- `not-high`: row does not match the confirmed launch-priority mapping.
- `unknown`: priority cannot be classified because the mapping is not confirmed or the Jira value is missing.

Allowed `tracking_status` values:

- `track`: confirmed high-priority feature with a reviewed `usage_metric_key`.
- `needs-mapping`: confirmed high-priority feature without a safe usage metric mapping.
- `ignore`: not high priority or explicitly out of scope.
- `blocked`: release data exists, but source, priority, or usage mapping is unsafe to use.

## Selection Rules

For high-priority release-feature usage questions and digests:

1. Read this registry before BigQuery.
2. Include only rows where `priority_mapping_status = confirmed` and `priority_class = high`.
3. Query BigQuery only for rows where `tracking_status = track` and `usage_metric_key` maps to `staffany-data-bot-metric-registry.md`.
4. For high-priority rows marked `needs-mapping` or `blocked`, report the mapping/source gap and use `Confidence: blocked`; do not invent a query.
5. Exclude rows marked `ignore`.
6. If the priority mapping is `needs-confirmation`, return `Confidence: blocked` for launch-priority classification and explain that the Jira field/value mapping needs review.

## Digest Output Rules

The weekly digest must show only confirmed high-priority release features and blocked high-priority mapping gaps.

For each row, include:

- Feature.
- Release/version and release date.
- Usage or adoption summary, or the exact mapping blocker.
- Source table or registry source.
- Confidence: exactly `verified`, `needs-check`, or `blocked`.
- Caveat, only when material.

If no rows are trackable and no blocked high-priority rows exist, answer that no confirmed high-priority release features are ready for usage tracking yet, cite this registry, and use `Confidence: blocked`. If blocked high-priority rows exist, list them with their exact blocker.
