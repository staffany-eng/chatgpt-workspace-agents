---
name: help-article-generator
description: Creates or updates StaffAny help articles with code-grounded accuracy, consistent formatting, and docx-ready output. Use when the user needs a new help article, an update suggestion across existing help center articles, or a review-ready draft with structured headings, lists, and FAQ.
---

# Help Article Generator

Use this skill to produce help articles in a repeatable format that is ready for internal review and Google Docs editing.

## Inputs

- Feature/topic name
- Mode intent:
  - `Create`
  - `Update`
- Optional:
  - Jira URL
  - PRD
  - Repo hint (`pantheon` / `manticore`)
  - Existing help center context

## Intake Workflow

1. Determine mode:
   - If unclear, ask: `Create` or `Update`.
2. If `Create`, ask source of truth:
   - `1. Jira ticket URL`
   - `2. PRD`
   - `3. Directly from pantheon codebase`
3. If source is Jira or PRD:
   - Remind user content must be updated before drafting.
4. If `Update`:
   - Do not ask for article URL first.
   - Scan English help center content under `https://help.staffany.com/en/`.
   - Propose which article(s)/section(s) should be edited.
5. Language rollout:
   - Default to English first.
   - Iterate Chinese and Bahasa Indonesia in later passes when requested.

## Repo + Evidence Workflow

1. Treat Pantheon as the StaffAny product behavior source of truth for help articles:
   - Cloud LaunchBot path: `~/.hermes/profiles/launchbot/source/pantheon`
   - Expected remote: `git@github.com:staffany-eng/pantheon.git`
   - Expected branch: `develop`
2. Before drafting product behavior, verify the Pantheon checkout is fresh and clean:
   - `~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh`
   - `git -C ~/.hermes/profiles/launchbot/source/pantheon status --short`
   - `git -C ~/.hermes/profiles/launchbot/source/pantheon rev-parse --abbrev-ref HEAD`
   - `git -C ~/.hermes/profiles/launchbot/source/pantheon rev-parse HEAD`
3. Jira tickets and PRDs can explain launch intent, customer positioning, and release context, but Pantheon code decides actual product behavior.
4. Locate behavior in Pantheon before writing:
   - feature entry points
   - user flow steps
   - access levels
   - flags/gating
   - API/data touchpoints
5. Trace backend/API behavior in `apps/kraken`, web/admin behavior in `apps/gryphon`, mobile behavior in `apps/pixie`, and product labels or permissions in the actual code paths.
6. Use only verified behavior in the article body.
7. If Pantheon is missing, stale, dirty, or conflicts with Jira/PRD, block or mark the draft `needs-check`; do not guess.
8. Keep assumptions explicit when evidence is incomplete.

## Launchbot Planning Rules

- Handoff-upgraded rules in this Launchbot skill override the older Grimoire help-article skill where they conflict.
- For ClubAny / Club Blue brand-and-perk management, default to one combined management article unless the user explicitly requests separate owner/staff articles.
- The combined ClubAny management article should use major sections:
  - `Managing Brands`
  - `Managing Perks`
  - `FAQ`
- Include the object model with this exact meaning when relevant:
  - A brand is the business profile.
  - A perk sits under a brand and contains redeemable perk details.
- Include the catalogue visibility rule when relevant: an active brand still does not appear in the mobile catalogue until it has at least one active perk.
- Add screenshot placeholders at key procedural steps when screenshots are not available yet.

## Article Format Contract

Follow this exact high-level order:

1. `Title`
2. Audience applicability block
3. Intro paragraph in marketable tone, with no `Introduction` header
4. Optional second intro paragraph
5. `This guide will cover how to:` as normal bold text (not a heading)
6. Outline list using numbered items
7. Main sections
8. FAQ

### Main body rules

- Do not repeat the title in the article body after the page title.
- Do not place any visible divider lines in source markdown. Never use standalone `---`, repeated underscores, repeated hyphens, or long text lines as separators.
- Do not use raw HTML in the markdown body. This includes `<div>`, `<br/>`, inline `style`, and `align` attributes.
- If an article needs a visual divider in Intercom, use Intercom's divider block during final Intercom editing. Do not simulate a divider with underscores, repeated dashes, or long text lines in the source article.
- Keep visible spacing before every heading and subheading. Add one blank line before each `##` and `###` section.
- Keep one blank line after the audience applicability block and before the opening paragraph.
- Keep one blank line between the opening paragraph and the `This guide will cover how to:` line.
- Main sections use concise context lines under each heading.
- Subheaders should not use `a.` prefix unless explicitly requested.
- Use real numbered/bullet lists (not plain text pretending to be lists).
- The outline under `This guide will cover how to:` must use numbered items, not dash bullets.
- Restart numbered steps from `1` for each subsection.
- Bold interactive UI terms in steps (buttons, tabs, pages, statuses).
- For generated Intercom/HTML output, add anchor links for subheaders where possible by using stable heading text. If writing HTML directly, add heading IDs derived from the subheader text.

### Audience block rules

- Keep this section center-aligned in `.docx`, Google Docs, and Intercom.
- The label `Contents of this article are applicable to the following users` must be bold and centered.
- The metadata lines below it must be centered, not bold by default.
- Include:
  - Tier, using one or more of: `Startup`, `Growth`, `Scale`
  - Product, using one or more of: `EngageAny`, `StaffAny`, `HRAny`, `HireAny`, `PayrollAny`
  - Platform
  - Access Level
- Platform values must be user-facing:
  - `Mobile`
  - `Web`
- Access Level values must be user-facing:
  - `Employee`
  - `Supervisor`
  - `Manager`
  - `Owner`
- Combine access levels where necessary, for example `Owner, Manager`.
- For ClubAny / Club Blue content, set Product to `StaffAny`.
- Never use internal app names (`pixie`, `gryphon`) in this field.

### Introduction rules

- Do not add an `Introduction` heading.
- Add a short marketable intro paragraph contextualized to the target audience.
- Bold the line `This guide will cover how to:`.
- If positioning copy is unclear, ask user for preferred wording.

### FAQ rules

- FAQ question line must start with `Q:` and the whole question line must be bold.
- FAQ answer line is not bold.
- Keep proper spacing after every Q&A pair.
- Keep FAQ concise and practical.
- Include human-process guidance when useful (for example in-person redemption interactions).

### Publishable body rules

- Do not include the internal appendix in the publishable help article body.
- Keep implementation evidence, source paths, assumptions, and last-verified commit in a separate internal notes file or response appendix only.
- Remove any internal-only section before sending content to Google Docs or Intercom.
- If a generated draft contains literal HTML text, repeated title text, internal appendix content, or text-based divider lines, fix it before promotion.

## Output Requirements

1. Show draft text in-chat first.
2. Generate `.docx` output for review.
3. Ensure `.docx` preserves:
   - title/heading hierarchy
   - bold text
   - centered audience block
   - correctly indented nested bullets
   - numbered lists that restart per subsection
4. Return only the requested article draft or structure. Do not add meta commentary such as "Structure complete" after the article body.

## Internal Notes Requirement

Always keep these details outside the publishable article body:

- Source of truth used
- Repository and branch/sha
- Pantheon checkout path and freshness status
- Key file paths/symbols
- API/data touchpoints
- Assumptions
- Last verified commit

## Quick QA Checklist

Before finalizing:

- Section order matches contract
- No visible divider lines are present
- Platform is `Mobile` or `Web`
- Intro exists (no intro header)
- No repeated title appears in the article body
- No raw HTML appears as visible text
- Audience block includes Tier, Product, Platform, and Access Level
- Outline uses real numbered lists with visible indentation
- Steps restart from `1` per subsection
- FAQ has bold `Q:` questions and normal answers
- Internal appendix is not in the publishable body
- Tone is natural, concise, and user-centered
