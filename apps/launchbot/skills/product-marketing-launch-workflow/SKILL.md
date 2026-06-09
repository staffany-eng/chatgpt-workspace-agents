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
Read `references/pantheon-evidence-patterns.md` for proven Pantheon search paths, Jira field patterns, and access-level feature evidence.

## First Response Shape

When a teammate triggers the workflow for a single KER ticket (e.g. `Start product marketing workflow for KER-xxx`), Launchbot must do all the work upfront and respond with this structure **before asking for approval or proceeding to gates**:

```
• [Create / Update] help article: <article title>
  ↳ If update: <link to existing Intercom article>

[Help article screenshot preview — rendered HTML image(s) posted via MEDIA:]

• Release notes draft

[Release notes screenshot preview — rendered HTML image(s) posted via MEDIA:]

Any feedback before I proceed?
```

Rules for this first response:
- **Do all drafting work first.** Run Pantheon evidence, draft both `en` and `id` help article, draft release notes, run validators — all before posting the summary.
- **State Create or Update** for the help article based on whether a matching Intercom article already exists. If updating, include the direct Intercom article link.
- **Show help article draft as browser-rendered screenshot(s)**, not pasted HTML. Follow the HTML preview delivery procedure in `help-article-generator`.
- **Show release notes draft as browser-rendered screenshot(s)** — save to `/tmp/release-notes-preview-<slug>.html`, open in browser tool, post screenshot via `MEDIA:`.
- **End with "Any feedback before I proceed?"** — do not advance to review/approval/staging until the teammate responds.
- If validators return `Revise before drafting`, apply feedback-updater and rerun before showing the preview. Show the passing version in the first response.
- If Pantheon evidence is missing or `needs-check`, show the draft with a `⚠️ needs-check` flag on the affected section; do not block the entire first response.
- If screenshots from the product UI are available, embed them in the HTML file so they appear in the rendered preview.

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
   - **Skill loading note:** `release-notes-generator` lives in the profile under the directory `customer-support-release-notes-generator/`. If `skill_view('release-notes-generator')` fails, read the file directly at `~/.hermes/profiles/launchbot/skills/customer-support-release-notes-generator/SKILL.md`. Same applies to `release-notes-validator` → `customer-support-release-notes-validator/` and `release-notes-feedback-updater` → `customer-support-release-notes-feedback-updater/`.
5. Evaluation checkpoint:
   - After every English or Indonesian help article HTML draft or update patch, run `help-article-validator`.
   - If the help-article validator returns `Revise before drafting`, run `help-article-feedback-updater`, then rerun `help-article-validator`.
   - Do not mark help articles `ready_for_review` unless both required locales return `Ready to draft`.
   - After every release note draft, run `release-notes-validator`.
   - If the release-note validator returns `revise`, run `release-notes-feedback-updater`, then rerun `release-notes-validator`.
   - Do not mark release notes `ready_for_review` unless the validator decision is `pass`.
6. Release-note screenshot step:
   - Run `help-article-screenshot-capture` for the release-note post when the change is UI/UX-visible.
   - Select only 1-2 screenshots that directly show the UI/UX delta in `What's new`.
   - Prefer 1 screenshot; use 2 only when a second image adds necessary context such as setup, permission, result, or confirmation state.
   - If screenshots are blocked, sensitive, unavailable, or not contextually useful, continue with `Screenshots: none` and the blocker reason.
7. Product Lead review and approval:
   - Post the release-note draft in the originating Slack thread or review thread and mention the Product Lead with `<@product_lead_slack_user_id>`.
   - Include Jira key, launch priority, validator score, evidence summary, help article link, 1-2 selected screenshots when available, and the exact approval instruction.
   - Accept feedback only when the Slack reply mentions `@Launch Bot`.
   - If feedback changes the release note, run `release-notes-feedback-updater`, then rerun `release-notes-validator`.
   - Only accept final approval from the Jira Product Lead or configured override reviewers.
   - Exact approval marker: `@Launch Bot approve release notes <KER-key>`.
8. Approved Slack distribution:
   - **Do not send release notes until the help article is published.** After Product Lead approval of the release notes, pause before distribution and confirm that the associated help article is live/published in Intercom.
   - Post a prompt to the Product Lead: confirm the help article is published before proceeding with release note distribution to `#all-product-new-updates`.
   - Only after the Product Lead explicitly confirms the help article is published, send the final release notes to `#all-product-new-updates`.
   - If the help article is not yet published, mark release notes status as `approved_pending_article_publish` and do not post.
   - After confirmed publication, proceed with distribution:
   - Include only the approved 1-2 screenshot refs/files from the review thread.
   - Default channel ID: `C03QQ2ERMT7`.
   - Config env vars: `LAUNCHBOT_RELEASE_NOTES_OUTPUT_CHANNEL_ID` and `LAUNCHBOT_RELEASE_NOTES_OUTPUT_CHANNEL_NAME`.
   - Use bot-owned posting and prefix automation wrapper copy with `Launchbot automation:`.
9. Output the launch tracker:
   - `not_needed`
   - `needed`
   - `drafted`
   - `needs_revision`
   - `ready_for_review`
   - `approved`
   - `approved_pending_article_publish`
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
Screenshots: <none | 1-2 contextually correct screenshot refs>
Next action: <specific owner action>
```

For generated help article drafts, include:

```text
Material: <help_article>
Locale: <en | id>
Draft or patch: <copy>
Display format: <Intercom-ready HTML>
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
- If Launch Priority is blank, do not invent it. Use SOP heuristics only as a `suggested_priority` and mark confidence `needs-check`. Heuristic guide: new Settings page or admin-action feature that changes user behavior → P3; pure label/copy tweak with no new admin action → P4; always confirm with Product Lead before distributing.
- When the Product Lead's Slack user ID is not resolvable from `.env` or the Slack message, output `blocked_missing_mapping` in the review field and ask Davin for the Slack user ID explicitly. Do not block the entire draft — produce the release note and flag the missing ID as the only remaining blocker.
- Changelog / What's New and WhatsApp Community messages are out of scope for this workflow. Do not draft, evaluate, or track them here.
