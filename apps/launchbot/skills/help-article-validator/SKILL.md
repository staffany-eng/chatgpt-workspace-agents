---
name: help-article-validator
description: Validate StaffAny Help Center article drafts with confidence scoring, evidence-based reasoning, model-article format comparison, HTML display readiness, and Intercom readiness decisions. Use after help-article-generator creates or updates English or Indonesian help article drafts, before Google Docs review, Intercom draft staging, or Product Lead approval.
---

# Help Article Validator

Use this skill as the mandatory checkpoint after a help article draft or update patch is generated.

Read `references/model-help-articles.md` before scoring. Use the model articles as formatting, wording, structure, and completeness references, while treating Pantheon and approved source evidence as the authority for product behavior.

## Inputs

```text
mode: <create | update>
locale: <en | id>
article_title: <title>
target_article: <URL | Intercom article ID | none>
source_evidence: <Pantheon/Jira/PRD/screenshot/help article evidence>
draft_html: <publishable HTML article body or HTML update patch>
existing_article_notes: <optional preservation requirements>
screenshot_status: <captured | placeholders | not-needed | blocked>
```

## Validation Rules

- Evaluate English and Indonesian drafts independently. One locale passing does not approve the other.
- Compare format, wording, and structure against the StaffAny model article patterns.
- Verify every non-obvious behavior, UI label, permission, status, default, formula, threshold, eligibility rule, warning, and outcome against evidence.
- For updates, ensure unrelated valid content, FAQ, screenshots, and caveats are preserved unless the source evidence makes them wrong.
- Keep internal notes, source paths, Jira/Figma/private URLs, evidence appendices, TODOs, and assumptions out of the public article body.
- Screenshot placeholders are acceptable only when screenshot capture is explicitly blocked and the article is not being published immediately.
- The visible draft or patch must be HTML, not Markdown. Markdown syntax in the public article preview is a revision issue unless the teammate explicitly requested Markdown for debugging.
- HTML must be Intercom-ready semantic HTML and must not include scripts, event handlers, external CSS, source paths, or evidence notes.

## Scoring

Return a validation score from `0` to `100`.

- Model article format fit: `0-30`
- Information correctness and source grounding: `0-35`
- Information comprehensiveness: `0-25`
- Intercom publishing hygiene: `0-10`

Decision thresholds:

- `Ready to draft`: `90-100`, no blockers, no unresolved evidence gap.
- `Revise before drafting`: `75-89`, or fixable issues with enough evidence to revise.
- `Do not draft`: below `75`, unsupported behavior claims, unsafe guidance, or mandatory blockers.

Confidence bands:

- `High`: `90-100`
- `Medium`: `75-89`
- `Low`: `60-74`
- `Very low`: below `60`

Score caps:

- Cap at `89` when procedural screenshots are still placeholders for a workflow that should be screenshot-backed.
- Cap at `74` when product behavior evidence is incomplete.
- Cap at `69` when important workflow steps, prerequisites, or outcomes are missing.
- Cap at `59` when the public body contains invented behavior, unsafe payroll/payment/document guidance, internal notes, or private data.

## Mandatory Blockers

Set decision to `Do not draft` when the article:

- Claims product behavior without Pantheon, approved Jira/PRD, screenshot, or existing-article evidence.
- Contains raw internal notes, local source paths, private links, PII, customer data, salaries, bank details, IDs, or secrets.
- Shows the public article body mainly as Markdown instead of HTML.
- Omits the audience applicability block for a new article.
- Omits critical setup, permission, eligibility, state transition, irreversible action, or user-impact consequences.
- Rewrites an existing article in a way that drops unrelated valid sections, FAQs, screenshots, or caveats.
- Uses internal app names such as `gryphon`, `pixie`, `kraken`, or `manticore` in the publishable article body.

## Output Contract

```text
Help Article Validation:
Decision: <Ready to draft | Revise before drafting | Do not draft>
Validation Score: <0-100>
Confidence: <High | Medium | Low | Very low>
Locale: <en | id>

Blockers:
- <blocker or No blockers found>

Evidence-Based Reasoning:
- <claim checked> -> <supporting evidence or gap>

Category Scores:
- Model article format fit: <0-30> - <reason>
- Information correctness and source grounding: <0-35> - <reason>
- Information comprehensiveness: <0-25> - <reason>
- Intercom publishing hygiene: <0-10> - <reason>
- HTML display readiness: <pass | revise> - <reason>
- Cap applied: <yes | no> - <reason>

Required Changes:
- <change or none>

Ready for Review: <yes | no>
Next Skill: <none | help-article-feedback-updater>
```

## Handoff

- If decision is `Ready to draft`, the article can move to Google Docs review or Intercom draft/staging.
- If decision is `Revise before drafting`, run `help-article-feedback-updater` with this validation output, then validate again.
- If decision is `Do not draft`, gather missing evidence first. Do not revise by inventing product behavior.
