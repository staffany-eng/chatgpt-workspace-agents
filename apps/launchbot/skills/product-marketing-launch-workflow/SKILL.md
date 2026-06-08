---
name: product-marketing-launch-workflow
description: Orchestrates StaffAny Launchbot product marketing launches from Jira KER release rows, sprint Roadmap values, launch-priority classification, help article work, concise release notes, release-note validation, Product Lead approval, and launch status tracking. Use when planning or running LaunchBot PMM workflow steps for shipped KER tickets in Slack.
---

# Product Marketing Launch Workflow

Use this skill to turn Jira KER release rows into a launch tracker and material work queue.

## Required Inputs

- Jira KER rows with:
  - `jira_key`
  - `summary`
  - Roadmap sprint from `customfield_10064`
  - status
  - Launch Priority from `customfield_10561`
- Sprint range, for example `25092` through `26052`.
- Launch scope from the PMM SOP:
  - Help articles
  - Release notes for Sales, PS, CS, and Product
- Product Lead Slack user ID or Jira Product Lead field that can map to Slack.

Read `references/launch-priority-materials.md` before classifying launch materials.

## Workflow

1. Build the source table:
   - Use KER Product Discovery `Roadmap` (`customfield_10064`) as the sprint/release bucket.
   - Use `Launch Priority` (`customfield_10561`) as the priority source.
   - Use Jira `status.name` as the ticket final/current status.
   - Do not infer launch priority from Jira engineering priority.
2. Filter launch candidates:
   - Include rows in the requested Roadmap range.
   - Treat `6 - Shipped & Launching` and `Done` as shipped candidates.
   - Keep non-shipped rows visible as blocked or not-ready when they have Launch Priority set.
3. Classify required materials:
   - P1: help article and release notes.
   - P2: help article and release notes.
   - P3: release notes or internal update by default; help article only when user behavior changes.
   - P4 or blank: no customer-facing launch material unless the change is customer-visible and likely to need guidance.
4. Create material work items:
   - `help_article`: route to `help-article-generator`.
   - `release_notes`: route to `release-notes-generator`.
5. Evaluation checkpoint:
   - After every English or Indonesian help article draft or update patch, run `help-article-validator`.
   - If the help-article validator returns `Revise before drafting`, run `help-article-feedback-updater`, then rerun `help-article-validator`.
   - Do not mark help articles `ready_for_review` unless both required locales return `Ready to draft`.
   - After every release note draft, run `release-notes-validator`.
   - If the release-note validator returns `revise`, run `release-notes-feedback-updater`, then rerun `release-notes-validator`.
   - Do not mark release notes `ready_for_review` unless the validator decision is `pass`.
6. Product Lead review and approval:
   - Post the release-note draft in the originating Slack thread or review thread and mention the Product Lead with `<@product_lead_slack_user_id>`.
   - Include Jira key, launch priority, validator score, evidence summary, help article link, and the exact approval instruction.
   - Accept feedback only when the Slack reply mentions `@Launch Bot`.
   - If feedback changes the release note, run `release-notes-feedback-updater`, then rerun `release-notes-validator`.
   - Only accept final approval from the Jira Product Lead or configured override reviewers.
   - Exact approval marker: `@Launch Bot approve release notes <KER-key>`.
7. Approved Slack distribution:
   - After Product Lead approval, send the final release notes to `#all-product-new-updates`.
   - Default channel ID: `C03QQ2ERMT7`.
   - Config env vars: `LAUNCHBOT_RELEASE_NOTES_OUTPUT_CHANNEL_ID` and `LAUNCHBOT_RELEASE_NOTES_OUTPUT_CHANNEL_NAME`.
   - Use bot-owned posting and prefix automation wrapper copy with `Launchbot automation:`.
8. Output the launch tracker:
   - `not_needed`
   - `needed`
   - `drafted`
   - `needs_revision`
   - `ready_for_review`
   - `approved`
   - `posted_to_product_updates`
   - `blocked`

## Output Contract

Return a compact table with:

```text
Roadmap | Jira | Status | Launch Priority | Help Article | Release Notes | Blocker / Next Action
```

For generated material drafts, include:

```text
Material: <release_notes>
Draft: <copy>
Evaluator decision: <pass | revise | blocked>
Evaluator confidence: <0-100>
Product Lead review: <@user_id | blocked_missing_mapping>
Distribution: <#all-product-new-updates | not_approved_yet | posted>
Next action: <specific owner action>
```

For generated help article drafts, include:

```text
Material: <help_article>
Locale: <en | id>
Draft or patch: <copy>
Evaluator decision: <Ready to draft | Revise before drafting | Do not draft>
Evaluator confidence: <0-100>
Evidence-based reasoning: <short bullets>
Next action: <specific owner action>
```

## Guardrails

- Customer-facing outputs are draft-first and approval-gated.
- Public Intercom publishing stays manual.
- Release notes are for Sales, PS, CS, and Product teammates. Do not title or label them as CS or Customer Service release notes in visible output.
- Keep each release-note section concise and grounded in existing StaffAny feature context.
- Do not expose raw Jira descriptions, comments, customer PII, internal app names, or private implementation details.
- If Launch Priority is blank, do not invent it. Use SOP heuristics only as a `suggested_priority` and mark confidence `needs-check`.
- Changelog / What's New and WhatsApp Community messages are out of scope for this workflow. Do not draft, evaluate, or track them here.
