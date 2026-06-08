---
name: release-notes-generator
description: Generate concise StaffAny release notes for Sales, PS, CS, and Product from a shipped Jira KER ticket, Launch Priority, verified UI/UX behavior, existing StaffAny feature context, and optional help article link. Use after launch-priority-identifier or when a Jira-to-Slack command asks LaunchBot for release notes.
---

# Release Notes Generator

Generate short release notes for Sales, PS, CS, and Product from a shipped Jira KER ticket.

## Required Inputs

- Jira key and summary.
- Ticket status, preferably `6 - Shipped & Launching` or Done.
- Launch Priority from `launch-priority-identifier`.
- Verified product behavior from Pantheon evidence, screenshots, approved help article draft, or trusted Jira acceptance criteria.
- Help article link, Intercom draft link, or `TBD`.

## Drafting Rules

- Be concise. Write for Sales, PS, CS, and Product teammates who need to recognize, explain, and support the change quickly.
- Do not title, label, or describe the output as `CS release notes`, `Customer Support release notes`, or `Customer Service release notes`.
- Include just enough existing StaffAny feature context for the audience to understand where the change fits.
- Focus `What's new` on UI/UX changes from the previous version to the newer one:
  - changed screens, buttons, labels, fields, menus, filters, empty states, errors, flows, permissions, setup surfaces, or user-visible behavior.
  - avoid backend-only details unless they explain a visible support outcome.
- Use plain enablement language, not marketing copy.
- Keep `How this helps users` focused only on end-user, manager, admin, or customer value. Do not explain how the change helps CS, support agents, triage, or internal teams in that section.
- Mention setup only when the customer/admin must configure something, enable a setting, update permissions, migrate data, or use a new help article.
- If no setup is needed, write `None`.
- If the help article is not ready, write `TBD` and include the Intercom draft link if available.
- Keep each section to one short line or 1-2 bullets unless the ticket has multiple user-facing changes.

## Required Format

Return exactly these sections:

```text
- Module
- What's new
- How this helps users
- What's needed to be setup
- Help article link
```

Use this shape:

```text
- Module
  <Product area or feature module>

- What's new
  <1-2 concise bullets focused on UI/UX delta from old to new>

- How this helps users
  <1-2 concise bullets on customer, admin, manager, or employee value only>

- What's needed to be setup
  <None | concise setup steps or prerequisites>

- Help article link
  <URL | Intercom draft URL | TBD>
```

## Quality Gate

Before returning, check:

- The ticket is shipped or clearly labeled draft preview.
- UI/UX deltas are verified or explicitly marked `needs-check`.
- No internal app names, source paths, implementation-only details, private URLs, PII, or customer-specific names appear.
- The note is useful for CS triage: what changed, what customers see, what setup is needed, where to send them.
- The note is useful for Sales, PS, CS, and Product: product context, visible change, customer value, setup, and help link.
- `How this helps users` contains no CS/support-agent/internal-team explanation.

## Required Validation Checkpoint

After drafting, immediately run `release-notes-validator` with:

```text
jira_key: <KER-key>
jira_status: <status>
launch_priority: <Launch Priority>
source_evidence: <Jira/Pantheon/help article/source summary>
draft: <release note>
help_article_link: <URL | Intercom draft URL | TBD>
```

If the validator returns `revise`, run `release-notes-feedback-updater`, then validate again. If the validator returns `blocked`, stop and name the missing evidence instead of revising from inference.

## Product Lead Review Handoff

After validation returns `pass`, ask the Product Lead for review in Slack:

```text
Launchbot automation: <@product_lead_slack_user_id> please review these release notes for <KER-key>.
Reply in this thread with `@Launch Bot <feedback>` for edits, or `@Launch Bot approve release notes <KER-key>` to send it to #all-product-new-updates.
```

Do not post to `#all-product-new-updates` until Product Lead approval is explicit.

## Output Contract

```text
Jira: <KER-key>
Launch Priority: <P1 | P2 | P3 | P4 | blank>
Confidence: <verified | needs-check | blocked>

Release Notes:
- Module
  ...

- What's new
  ...

- How this helps users
  ...

- What's needed to be setup
  ...

- Help article link
  ...

Evidence Checked:
- <Jira/Pantheon/help article/source summary>

Needs Check:
- <none or exact missing evidence>

Validator:
Decision: <pass | revise | blocked>
Confidence Score: <0-100>
Top reasons: <short bullets>
Required changes: <short bullets or none>

Slack Review:
Product Lead: <@user_id | blocked_missing_mapping>
Approval instruction: @Launch Bot approve release notes <KER-key>
Approved destination: #all-product-new-updates
```

## Blockers

Return `blocked` instead of release notes when:

- The ticket is not shipped and the user did not ask for a preview.
- There is no verified customer-visible behavior.
- The only known change is sensitive, negative, or operationally risky to broadcast.
- The draft would require inventing UI labels, setup steps, availability, or help article links.
