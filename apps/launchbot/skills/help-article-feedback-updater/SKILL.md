---
name: help-article-feedback-updater
description: Update StaffAny Help Center article drafts using help-article-validator feedback, confidence scoring rationale, evidence gaps, model-article format issues, and Product Lead feedback. Use after help-article-validator returns Revise before drafting, or when a teammate asks LaunchBot to revise a help article draft from validation feedback.
---

# Help Article Feedback Updater

Use this skill to revise a help article draft or update patch after validation.

## Inputs

```text
original_article_html: <HTML draft or HTML update patch>
validation: <help-article-validator output>
source_evidence: <Pantheon/Jira/PRD/screenshot/help article evidence>
user_feedback: <optional Slack/thread feedback>
locale: <en | id>
mode: <create | update>
```

## Update Rules

- Apply validator `Required Changes` in priority order.
- Preserve the help article format from `help-article-generator`.
- Return the revised public article or update patch as Intercom-ready HTML, not Markdown.
- Preserve existing article sections, FAQ, screenshots, videos, caveats, and valid wording unless the evidence directly requires a change.
- Update only with evidence-backed facts. Do not invent UI labels, permissions, statuses, setup steps, limits, formulas, defaults, eligibility rules, or help links.
- Improve model fit by aligning title, `Learn how to` subtitle, audience applicability, guide outline, action-oriented headings, numbered steps, screenshot placement notes, and FAQ with the model article references.
- Keep public body clean: remove evidence notes, source paths, private URLs, TODOs, assumptions, and internal names.
- If validator feedback asks for unsupported product behavior, put it under `Remaining Needs Check` instead of adding it to the article.
- If validation was `Do not draft`, do not produce a revised article unless the missing blocker evidence is supplied.
- For Indonesian drafts, preserve the validated English structure and product meaning. Do not add behavior absent from English source evidence.

## Output Contract

```text
Updated Help Article:
<revised publishable HTML article body or HTML update patch>

Changes Applied:
- <validator or user feedback addressed>

Remaining Needs Check:
- <none or exact evidence gap>

Validator Handoff:
Re-run help-article-validator before marking ready.
```

## Guardrails

- Do not publish, stage, or send to Intercom as part of the update unless the user explicitly asks.
- Do not expand a focused update into a full rewrite unless explicitly requested.
- Do not reduce the validation standard because a previous score was close to passing.
