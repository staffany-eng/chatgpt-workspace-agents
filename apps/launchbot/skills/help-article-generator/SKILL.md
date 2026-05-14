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
  - `Update -> Video-only update`
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
   - Search live Intercom articles first using `npm run intercom:affected -- --topic "<topic>"`.
   - Scan English help center content under `https://help.staffany.com/en/` only as public fallback context.
   - Propose which article(s)/section(s) should be edited.
5. If `Update -> Video-only update`:
   - Treat this as a sub-mode of `Update`, not as a separate skill.
   - Accept only Loom share/embed URLs.
   - Use the placement registry at `references/video-placement-registry.json` to resolve the target article and slot.
   - Preview the exact registered video-block patch before mutation.
   - Create an Intercom draft only after the user confirms with `draft it`.
   - Do not rewrite article text, create review docs, publish, delete, tag, move collections, or change unregistered video blocks.
   - If no registry slot matches, block instead of guessing.
6. Language rollout:
   - Default to English first.
   - Iterate Chinese and Bahasa Indonesia in later passes when requested.

## Repo + Evidence Workflow

1. Treat Pantheon as the StaffAny product behavior source of truth for help articles:
   - Cloud LaunchBot path: `~/.hermes/profiles/launchbot/source/pantheon`
   - Default local checkout: `/Users/leekaiyi/workspace/pantheon`
   - Configured runtime checkout: `LAUNCH_PANTHEON_REPO`
   - Expected remote: `git@github.com:staffany-eng/pantheon.git`
   - Expected branch: `develop`
   - Do not auto-pull by default.
2. Before drafting product behavior, verify the Pantheon checkout is fresh and clean:
   - `~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh`
   - `npm run help-article:pantheon-scan -- --topic "<topic>" [--app <app,app>] [--paths <paths>]`
   - `git -C ~/.hermes/profiles/launchbot/source/pantheon status --short`
   - `git -C ~/.hermes/profiles/launchbot/source/pantheon rev-parse --abbrev-ref HEAD`
   - `git -C ~/.hermes/profiles/launchbot/source/pantheon rev-parse HEAD`
3. Scope Pantheon app evidence correctly:
   - `gryphon` for Web/admin behavior
   - `pixie` for Mobile behavior
   - `kraken` for backend/API/data behavior
   - `manticore` only for analytics/reporting behavior
4. Jira tickets and PRDs can explain launch intent, customer positioning, and release context, but Pantheon code decides actual product behavior.
5. Locate behavior in Pantheon before writing:
   - feature entry points
   - user flow steps
   - access levels
   - flags/gating
   - API/data touchpoints
6. Trace backend/API behavior in `apps/kraken`, web/admin behavior in `apps/gryphon`, mobile behavior in `apps/pixie`, and product labels or permissions in the actual code paths.
7. Use only verified Pantheon behavior in the article body.
8. If Pantheon is missing, dirty, ambiguous, stale, or conflicts with Jira/PRD/Intercom, mark the draft `needs-check` and do not stage it for Intercom.
9. Keep assumptions explicit outside the publishable article body when evidence is incomplete.

## Launchbot Planning Rules

- Handoff-upgraded rules in this Launchbot skill override the older Grimoire help-article skill where they conflict.
- Video-only help article updates are registry-only and draft-only. The registry is the authority for placement; model inference can suggest a slot but cannot mutate without a registry match.
- Before drafting, run article planning from the cached Intercom article-shape profile:
  - `npm run help-article:plan -- --topic "<topic>"`
- `help-article:plan` includes an adaptive intake gate. It should infer article family, surface, audience, and desired outcome from explicit flags, topic text, cached family models, and cached inventory before asking anything.
- If `help-article:plan` returns `needs-intake`, ask only the missing high-impact questions from `intake.questions`. Do not run a long interview or ask for every optional field.
- Refresh the cached article-shape profile only when needed:
  - `npm run help-article:shape-refresh`
- Refresh the all-article inventory metadata map when article coverage changes:
  - `npm run intercom:inventory`
- Do not pull all live Intercom articles for every draft. Use live Intercom only for shape refreshes, affected-article search, and final stale checks before staging.
- Use the article planning profile at `references/article-planning-profile.json` as the repeatable source for article families, audience/platform split rules, workflow tags, and create-vs-update recommendations.
- Use the all-article inventory at `references/intercom-article-inventory.json` as the Help Center map. It must stay metadata plus derived content signals only; do not commit raw article bodies.
- Use the hybrid Intercom format profile as the format source of truth: live Intercom pull first, then the normalized profile at `references/intercom-format-profile.json` for repeatable checks.
- For local live Intercom tests, use `node scripts/launchbot-with-secrets.mjs --only intercom -- <command>` instead of copying tokens into a worktree. It reads `launchbot-step3-intercom-access-token` from GCP Secret Manager and maps it to `LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN` / `INTERCOM_ACCESS_TOKEN` only for the child process.
- Use Pantheon evidence as the product-behavior source of truth before drafting or staging.
- Before sending content to Google Docs or Intercom, run `npm run help-article:evidence-check -- --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"`.
- Before sending content to Google Docs or Intercom, run `npm run help-article:format-check -- --draft <draft.md> --title "<article title>"`.
- If the Pantheon evidence gate fails, fix the source scope or draft before promotion. Do not bypass failures for missing Pantheon evidence, dirty repo state, ambiguous app scope, source conflicts, platform-specific evidence gaps, unsupported product behavior claims, or internal app-name leakage.
- If the format gate fails, fix the draft before promotion. Do not bypass failures for missing audience metadata, repeated title text, raw HTML or markdown leakage, text divider lines, internal appendix content, bad list numbering, missing FAQ, or missing numbered outline.
- For topic updates, use `npm run intercom:affected -- --topic "<topic>"` to find affected Intercom articles, then stage proposed diffs/previews for approval instead of overwriting published articles.
- For an existing article update, use `npm run intercom:stage-update -- --article-id <article_id> --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"` to create the local staged-update record.
- `intercom:stage-update` must use the cached article planning profile plus a live target-article pull to run the pre-stage stale check. If the cached target article fingerprint or `updated_at` disagrees with live Intercom, mark the staged update `needs-check` / `needs-refresh`.
- Public publishing stays manual in Intercom; Launchbot writes only draft/staging output after approval.

## Article Planning Rules

- Start from `help-article:plan`, not the user's intake form.
- Treat `needs-intake` as a normal planning stop: answer the concise questions, then rerun `help-article:plan` with the supplied `--surface`, `--audience`, `--outcome`, `--change`, `--jira`, `--prd`, `--release-state`, `--feature-flag`, `--reviewer`, or `--screenshot-owner` flags as relevant.
- Prefer updating an existing article when live Intercom already has the same audience, platform, and workflow.
- Split articles when audiences perform different jobs, such as admin setup vs employee action.
- Split articles when platform flows differ materially, such as Web owner setup vs Mobile staff redemption.
- Split marketplace or multi-sided workflows by actor view.
- Keep one article when one audience completes one connected lifecycle.
- Keep overview articles only when they coordinate related subflows.
- If the planner returns `needs-check`, refresh or expand the article-shape profile before drafting.
- Keep Slack, Jira, and PRD as intent/context. Pantheon remains behavior truth, and cached Intercom planning synthesis remains article-shape truth.
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
  - Product, using one or more of: `EngageAny`, `StaffAny`, `HRAny`, `HireAny`, `PayrollAny`
  - Platform
  - Access Level
- Tier is optional for now. Include it only when the source article or product owner explicitly supplies it.
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
- Never use internal app names (`gryphon`, `pixie`, `kraken`, `manticore`) anywhere in the publishable article body.

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

For `Update -> Video-only update`, replace the normal article drafting output with:

1. Preview output with:
   - article
   - slot
   - current_video
   - new_video
   - patch_summary
   - `will_publish: false`
   - confidence
2. Draft output only after confirmation with `draft it`:
   - intercom_article_id
   - draft_url
   - `article_state: "draft"`
   - slot_id
   - video_src
   - `will_publish: false`
3. A blocked answer when the Loom URL, article hint, anchor, or current video block does not validate against the registry.

## Internal Notes Requirement

Always keep these details outside the publishable article body:

- Source of truth used
- Repository and branch/sha
- Pantheon checkout path and freshness status
- Pantheon evidence pack path
- Key file paths/symbols
- API/data touchpoints
- Assumptions
- Last verified commit

## Quick QA Checklist

Before finalizing:

- Section order matches contract
- Pantheon evidence gate passes
- No visible divider lines are present
- Platform is `Mobile` or `Web`
- Intro exists (no intro header)
- No repeated title appears in the article body
- No raw HTML appears as visible text
- Audience block includes Product, Platform, and Access Level
- Outline uses real numbered lists with visible indentation
- Steps restart from `1` per subsection
- FAQ has bold `Q:` questions and normal answers
- Internal appendix is not in the publishable body
- Tone is natural, concise, and user-centered
- For video-only updates, the patch touches exactly one registered Loom iframe and the Intercom payload uses `state: "draft"` only
