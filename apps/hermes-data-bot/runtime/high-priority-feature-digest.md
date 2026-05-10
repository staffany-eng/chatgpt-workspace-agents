# High-Priority Feature Usage Digest

Hermes Data Bot sends a weekly digest for Jira-confirmed high-priority release features whose usage metrics are safe to query.

## Schedule

- Cadence: every Monday 9am SGT.
- Cron expression on the current SGT-local profile: `0 9 * * 1`.
- If the deployment host/profile runs Hermes in UTC, use `0 1 * * 1` instead.
- Delivery: Slack `#kaiyi-bot-testing`.
- Cron name: `staffanydatabot high-priority release feature usage digest`.

## Preconditions

- `staffany-release-feature-registry.md` has a confirmed launch-priority mapping.
- High-priority rows have reviewed `usage_metric_key` mappings, or are explicitly marked `needs-mapping`.
- `staffany_bigquery` MCP is healthy and still exposes only the read-only allowlist.
- Slack quiet-output settings remain enabled.

Do not enable the digest if the priority mapping is still `needs-confirmation`, unless the expected weekly output is an explicit blocked/no-trackable-row status.

## Manual Dry Run

From the repo root:

```bash
hermes -p staffanydatabot --skills staffany-data-bot \
  -z "$(cat apps/hermes-data-bot/runtime/prompts/high-priority-feature-usage-digest.md)"
```

Expected safe dry-run behavior:

- It reads `staffany-release-feature-registry.md`.
- It does not query Jira live.
- It queries only confirmed high-priority rows marked `track`.
- It reports Club Blue through `kraken_prod.engagement_reward_redemption` with `Confidence: needs-check` until the proxy source is owner-confirmed.
- It reports blocked high-priority mapping gaps, such as Avatar standardization, with `Confidence: blocked`.

## Cron Install

After the dry run is reviewed:

```bash
hermes -p staffanydatabot cron create "0 9 * * 1" \
  "$(cat apps/hermes-data-bot/runtime/prompts/high-priority-feature-usage-digest.md)" \
  --name "staffanydatabot high-priority release feature usage digest" \
  --skill staffany-data-bot \
  --deliver "slack:#kaiyi-bot-testing" \
  --workdir "$(pwd)/apps/hermes-data-bot"
hermes -p staffanydatabot cron list
```

If the installed Hermes version requires a Slack channel ID instead of `#kaiyi-bot-testing`, use the channel ID in the `--deliver` target and keep the digest name unchanged.

## Result Contract

The digest should be normal Slack text, not a code block. Use one compact block per feature:

```text
High-priority release feature usage digest
Scope: <release window or registry timestamp>

Feature: <canonical feature name>
Release: <version/date/Jira key>
Usage: <adoption summary or blocked mapping reason>
Source: <registry + BigQuery table or registry only>
Confidence: <verified | needs-check | blocked>
Caveat: <material caveat>
```

If no rows are trackable, send a single blocked summary with the registry as source.
