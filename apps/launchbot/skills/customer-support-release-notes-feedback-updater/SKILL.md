---
name: release-notes-feedback-updater
description: Update StaffAny release notes for Sales, PS, CS, and Product using validator feedback, confidence score, evidence gaps, and Product Lead or teammate feedback. Use after release-notes-validator returns revise, or when a teammate asks LaunchBot to update release notes from validation feedback.
---

# Release Notes Feedback Updater

Use this skill to revise release notes after validation or teammate feedback.

## Inputs

```text
original_release_notes: <five-section release note>
validation: <release-notes-validator output>
source_evidence: <Jira/Slack/Pantheon/help article summaries>
screenshot_refs: <none | 1-2 screenshot file paths/URLs with captions>
user_feedback: <optional Slack/thread feedback>
```

## Update Rules

- Preserve the exact five-section format:
  - Module
  - What's new
  - How this helps users
  - What's needed to be setup
  - Help article link
- Apply validator `Required Changes` in priority order.
- Update only with evidence-backed facts. Do not invent UI labels, setup steps, availability, module names, or help article links.
- Do not title, label, or describe the output as `CS release notes`, `Customer Support release notes`, or `Customer Service release notes`.
- Keep the note concise and useful for Sales, PS, CS, and Product, with only the necessary StaffAny feature context.
- Keep `What's new` focused on the UI/UX delta from previous behavior to new behavior.
- Keep `How this helps users` focused only on customer, admin, manager, or employee value. Remove CS, support-agent, triage, or internal-team explanations from that section.
- Keep each section concise enough for Slack scanning.
- Preserve only 1-2 contextually correct screenshots. Remove screenshots that are generic, unrelated to `What's new`, sensitive, unredacted, or redundant.
- If requested feedback is unsupported by the evidence, put it under `Remaining Needs Check` instead of adding it to the release note body.
- If the validator decision was `blocked`, do not produce a revised release note unless the missing blocker evidence is supplied.

## Output Contract

```text
Updated Release Notes:
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

Changes Applied:
- <validator or user feedback addressed>

Remaining Needs Check:
- <none or exact evidence gap>

Screenshots:
- <none | retained/replaced/removed screenshot refs and reason>

Validator Handoff:
Re-run release-notes-validator before marking ready.
```

## Guardrails

- Do not expand the note into a changelog, help article, or marketing announcement.
- Do not expose raw Jira descriptions, private URLs, customer names, PII, internal app names, or implementation-only details.
- Do not lower the standard because the previous score was close to passing. The revised draft still needs a fresh validator pass.
