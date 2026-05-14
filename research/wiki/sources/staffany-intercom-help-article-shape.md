# StaffAny Intercom Help Article Shape

## Source Metadata

- Type: live Intercom API curated article-shape refresh
- Source class: private StaffAny Intercom workspace evidence
- Source path: `apps/launch-superpower-bot/skills/help-article-generator/references/article-planning-profile.json`
- Date ingested: 2026-05-14
- Context: LaunchBot help-article planning, article split/merge rules, and pre-stage stale checks
- Default weight: 4 for article-shape planning; live target Intercom article remains higher authority at staging time
- Privacy: private internal API-derived metadata; no token values, raw HTML, or full article bodies copied

## Context Caveat

This source is a curated Intercom shape profile, not a full Help Center mirror. Use it to plan article shape and split/merge behavior. For a specific target article, pull that article live before staging because live Intercom is the current article truth.

## Evidence Used

- Raw record: [StaffAny Intercom Help Article Shape Source Record](../../raw/staffany-intercom-help-article-shape/source-record.md)

## What They Said

- The shape ingest uses a curated Intercom sample by family and stores only normalized evidence in the committed profile.
- The profile covers 37 published reference articles across 10 article families.
- The inventory ingest maps all 328 Intercom articles while committing only metadata and derived content signals.
- Live Intercom is still used for inventory refresh, shape refresh, affected-article search, and pre-stage stale checks.
- The planning hierarchy is live target Intercom article, Pantheon product behavior, cached Intercom planning synthesis, then Slack/Jira/PRD context.
- The cached profile encodes family-specific split/merge rules for workflows such as ClubAny, Company Documents, Claims, Leave, Payroll, Scheduling, and Permissions.
- A live ClubAny planning smoke returned two target articles: Web management and Mobile redemption.

## Evidence Trace

- Claim: The shape ingest uses a curated Intercom sample by family and stores only normalized evidence in the committed profile. Evidence: The raw policy says full JSON/HTML stays in ignored cache and committed evidence is normalized. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:16`.
- Claim: The profile covers 37 published reference articles across 10 article families. Evidence: The raw inventory records the generated profile count and family count. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:23`.
- Claim: The inventory ingest maps all 328 Intercom articles while committing only metadata and derived content signals. Evidence: The raw inventory records article count, cache policy, and committed inventory boundary. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:25`.
- Claim: Live Intercom is still used for inventory refresh, shape refresh, affected-article search, and pre-stage stale checks. Evidence: The raw extracts list those live Intercom uses. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:42`.
- Claim: The planning hierarchy is live target Intercom article, Pantheon product behavior, cached Intercom planning synthesis, then Slack/Jira/PRD context. Evidence: The raw extracts record that exact source hierarchy. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:38`.
- Claim: Cached profile has family split rules. Evidence: Raw extracts list maintained family split rules. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:41`.
- Claim: A live ClubAny planning smoke returned two target articles: Web management and Mobile redemption. Evidence: The raw extracts record the selected family, mode, and two recommended target articles. Source: `research/raw/staffany-intercom-help-article-shape/source-record.md:51`.

## Learning Summary

- LaunchBot should plan from the cached article-shape profile first, then use live Intercom only for targeted search and stale checks.
- LaunchBot should use the all-article inventory as a Help Center map before live search, without treating inventory as article-body truth.
- Article count should follow audience, platform, and workflow boundaries rather than a one-feature-one-article default.
- Pantheon remains the behavior source; this Intercom profile only teaches article shape, format patterns, and split/merge expectations.
- The pre-stage path must compare live target article timestamps and structural fingerprints against the cached profile before staging.
- If the target article has drifted, LaunchBot should return `needs-refresh` instead of drafting against stale shape evidence.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `apps/launch-superpower-bot/skills/help-article-generator/references/article-planning-profile.json`, `docs/product-compass.md`, `research/wiki/weights.md`
- Evidence weight check: default weight 4 because it is API-derived current Intercom evidence, but live target article checks outrank the cached profile.
- Decision: promote as LaunchBot article-planning truth for shape and split/merge behavior, gated by live stale checks.

## Possible Agent Builder Relevance

- Agent-synthesized: Add `help-article:shape-refresh` as the reusable refresh path for article-shape learning.
- Agent-synthesized: Keep raw Intercom bodies out of git and commit only normalized planning evidence.
- Agent-synthesized: Require `help-article:plan` before drafting so LaunchBot can decide whether to update one article or split work across several articles.
- Do-not-promote: Do not use this cached profile as behavior truth; product behavior still needs Pantheon evidence.
- Do-not-promote: Do not publish or overwrite existing Intercom articles from LaunchBot.

## Follow-Up Questions

- Which Intercom article families should be added next after the first 10 maintained families?
- Should source-note refreshes record a before/after diff when an article family changes shape materially?
