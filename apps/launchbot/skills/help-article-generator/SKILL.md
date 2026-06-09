---
name: help-article-generator
description: Creates or updates StaffAny help articles with Pantheon-grounded feature evidence, StaffAny Help Center structure, Intercom-ready HTML output, Google Docs-ready exports, and Launchbot Intercom staging gates. Use when the user needs a new help article, an update suggestion across existing help center articles, or a review-ready HTML draft with structured headings, lists, and FAQ.
---

# Help Article Generator

Use this skill to produce help articles in a repeatable format that is ready for internal review, Google Docs editing, and Launchbot's existing Intercom staging workflow. Whenever you show a created or updated help article to a teammate, show it as Intercom-ready HTML, not Markdown.

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
  - Audience, country, plan/tier, platform, tone, or terminology preferences

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
   - Treat the existing article as the base content. Do not generate a replacement article from scratch unless the user explicitly asks for a rewrite.
   - Preserve all existing sections, steps, FAQs, screenshots, videos, notes, and wording that are not contradicted by the new feature evidence.
   - Apply the smallest complete update: insert new sections, update the guide outline, add or adjust only directly affected steps/FAQ, and leave unrelated valid content intact.
   - If the full existing article body is unavailable, fetch it before showing a "whole article" draft. If it cannot be fetched, return a patch-style update with insertion points instead of reconstructing the full article.
5. If `Update -> Video-only update`:
   - Treat this as a sub-mode of `Update`, not as a separate skill.
   - Accept only Loom share/embed URLs.
   - Use the placement registry at `references/video-placement-registry.json` to resolve the target article and slot.
   - Preview the exact registered video-block patch before mutation.
   - Create an Intercom draft only after the user confirms with `draft it`.
   - Do not rewrite article text, create review docs, publish, delete, tag, move collections, or change unregistered video blocks.
   - If no registry slot matches, block instead of guessing.
6. Language rollout:
   - Default normal help article creation and text updates to two article records: English (`en`) and Indonesian (`id`).
   - Generate English first as the source draft, then create the Indonesian version from the validated English structure and the same Pantheon evidence.
   - Do not create a translated article that introduces product behavior, eligibility, UI labels, limits, or steps not present in the English source draft and Pantheon evidence.
   - Chinese remains a later pass only when requested.

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
   - **Pitfall (VM):** `help-article:pantheon-scan` resolves Pantheon to the Mac-local path `/Users/leekaiyi/workspace/pantheon` on the VM and returns `missing_pantheon_repo` errors. Run `launchbot-update-pantheon-repo.sh` first, then grep directly from `/home/leekaiyi/.hermes/profiles/launchbot/source/pantheon/` as the primary evidence method on the VM.
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

## Article Generation Assets

- Use `templates/help-article-template.md` as the base article shape for new drafts.
- Read `references/staffany-help-center-style.md` before drafting. Treat it as style guidance only; Pantheon code and explicit user requirements remain the authority for product behavior.
- Use `scripts/feature_context.sh` to build a local code context pack when the Launchbot npm evidence scanner is unavailable or when a focused feature scan is useful:

```bash
bash apps/launchbot/skills/help-article-generator/scripts/feature_context.sh \
  --feature "<feature>" \
  --repo "$LAUNCH_PANTHEON_REPO" \
  --max 80
```

- Optional deep scan:

```bash
ENABLE_BACKEND_SCAN=1 ENABLE_HELP_REF_SCAN=1 \
bash apps/launchbot/skills/help-article-generator/scripts/feature_context.sh \
  --feature "<feature>" \
  --repo "$LAUNCH_PANTHEON_REPO" \
  --max 80
```

- Use `scripts/export_help_article.sh` only after internal evidence notes are removed from the publishable body. It can create Google Docs copy formats and optional `.docx` output.
- Use `scripts/publish_help_article_gdocs.sh` only when the user explicitly wants a Google Doc and valid Google credentials are available. Never commit OAuth credentials or token caches.
- Internal source files may remain Markdown when an existing evidence or format CLI requires `--draft <draft.md>`, but visible LaunchBot output must show the help article as HTML.

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
- For locale draft API details, token extraction, and known article IDs, see `references/intercom-locale-draft-api.md`.
- For local live Intercom tests, use `node scripts/launchbot-with-secrets.mjs --only intercom -- <command>` instead of copying tokens into a worktree. It reads `launchbot-step3-intercom-access-token` from GCP Secret Manager and maps it to `LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN` / `INTERCOM_ACCESS_TOKEN` only for the child process.
- Use Pantheon evidence as the product-behavior source of truth before drafting or staging.
- Before sending content to Google Docs or Intercom, run `npm run help-article:evidence-check -- --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"`.
- Before sending content to Google Docs or Intercom, run `npm run help-article:format-check -- --draft <draft.md> --title "<article title>"`.
- When showing a draft or update patch in Slack or chat, use the HTML preview delivery procedure: save to a temp HTML file, render via browser tool, post the screenshot. Do not paste raw HTML or `.md` source in the thread unless a teammate explicitly asks for source for debugging.
- Review messages and approval threads should link any Google Doc or Intercom draft as usual, but the inline article preview must be HTML.
- For bilingual article creation or text updates, run evidence and format checks separately for both `en` and `id` drafts. One locale passing does not approve the other locale.
- After each English or Indonesian help article draft or update patch, run `help-article-validator` with the draft, locale, source evidence, target article, and screenshot status.
- If `help-article-validator` returns `Revise before drafting`, run `help-article-feedback-updater`, then rerun `help-article-validator`.
- Do not send a help article to Google Docs, Slack review, or Intercom draft/staging unless `help-article-validator` returns `Ready to draft`.
- If the Pantheon evidence gate fails, fix the source scope or draft before promotion. Do not bypass failures for missing Pantheon evidence, dirty repo state, ambiguous app scope, source conflicts, platform-specific evidence gaps, unsupported product behavior claims, or internal app-name leakage.
- If the format gate fails, fix the draft before promotion. Do not bypass failures for missing audience metadata, repeated title text, raw HTML or markdown leakage, text divider lines, internal appendix content, bad list numbering, missing FAQ, or missing numbered outline.
- For topic updates, use `npm run intercom:affected -- --topic "<topic>"` to find affected Intercom articles, then stage proposed diffs/previews for approval instead of overwriting published articles.
- For an existing article update, use `npm run intercom:stage-update -- --article-id <article_id> --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"` to create the local staged-update record.
- `intercom:stage-update` must use the cached article planning profile plus a live target-article pull to run the pre-stage stale check. If the cached target article fingerprint or `updated_at` disagrees with live Intercom, mark the staged update `needs-check` / `needs-refresh`.
- Public publishing stays manual in Intercom; Launchbot writes only draft/staging output after approval.

## Intercom Locale Draft API — Creating an `id` Article

When creating an Indonesian (`id`) locale version of an existing English article, **PUT to the existing EN article ID** with `locale=id`. Both the English and Indonesian versions share the **same article ID**. Do NOT POST a new article — that creates a separate unlinked record.

```python
payload = {
    "title": "<Indonesian title>",
    "description": "<Indonesian subtitle>",
    "body": id_body_html,
    "author_id": 3374597,          # Launchbot author — required, API rejects without it
    "state": "draft",
    "locale": "id"
}
# PUT to https://api.intercom.io/articles/<EN_ARTICLE_ID>?locale=id
# e.g. PUT https://api.intercom.io/articles/15419519?locale=id
```

- The EN article ID is shared between locales. Record the same article ID for both `en` and `id`.
- Fetch the EN article first to confirm article ID and current state: `GET /articles/<en_article_id>`
- Translate all user-facing prose; preserve all HTML structure, element IDs (`id="h_..."`), image URLs, anchor `href` values, and product/UI labels verbatim.

**Pitfall:** Do NOT POST a new article for the `id` locale — this creates a separate unlinked Intercom article with a different ID, which is wrong. Always PUT to the EN article ID with `?locale=id`.

### Token extraction on VM (pitfall)

Do **not** use `source ~/.hermes/profiles/launchbot/.env` in a subshell — the path may fail due to sandbox `$HOME` remapping. Instead extract the token explicitly:

```bash
TOKEN=$(grep '^INTERCOM_ACCESS_TOKEN=' /home/leekaiyi/.hermes/profiles/launchbot/.env \
  | sed 's/^INTERCOM_ACCESS_TOKEN=//' | tr -d '"' | tr -d "'")
```

Then call Intercom with `--data @/tmp/payload.json` (write JSON to a temp file first; do not use heredoc in curl).

## Article Planning Rules

- Start from `help-article:plan`, not the user's intake form.
- Treat `needs-intake` as a normal planning stop: answer the concise questions, then rerun `help-article:plan` with the supplied `--surface`, `--audience`, `--outcome`, `--change`, `--jira`, `--prd`, `--release-state`, `--feature-flag`, `--reviewer`, or `--screenshot-owner` flags as relevant.
- Prefer updating an existing article when live Intercom already has the same audience, platform, and workflow.
- For existing article updates, preserve-by-default. Existing article content remains valid unless the new feature evidence directly makes it wrong, duplicate, or misleading.
- Never shrink, summarize, or omit original article sections merely because they are not touched by the new change.
- When asked to "generate the whole article" for an update, first load the full current article, merge the approved changes into it, and show the merged result. If only a proposed update draft is available, say so and show only the update patch.
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
- Treat screenshot capture as optional. If `help-article-screenshot-capture` or its browser runner is blocked, keep placeholders and blocker notes; do not block article drafting, Google Docs review, Slack approval, or Intercom draft/staging for otherwise valid article text.

## Article Format Contract

Follow this exact high-level order:

1. `Title`
2. Subtitle
3. Audience applicability block
4. Quick explanation paragraph, with no `Introduction` header
5. `This guide will cover how to:` as normal bold text (not a heading)
6. Outline list using numbered items
7. Main sections
8. FAQ

### Main body rules

- Do not repeat the title in the article body after the page title.
- Do not place any visible divider lines in source markdown. Never use standalone `---`, repeated underscores, repeated hyphens, or long text lines as separators.
- Do not use raw HTML in the internal markdown body. This includes `<div>`, `<br/>`, inline `style`, and `align` attributes in Markdown source.
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

### HTML display rules

- **Do not paste the full HTML inline in the Slack thread.** Always save the article HTML to a file and deliver a rendered visual preview instead.
- HTML preview delivery procedure:
  1. Write the full article HTML to a temp file: `/tmp/help-article-preview-<slug>-<locale>.html`. Wrap the body in a minimal `<html><head><meta charset="utf-8"><style>body{font-family:sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem}hr{border:none;border-top:1px solid #ddd;margin:2rem 0}img{max-width:100%}</style></head><body>...</body></html>` shell so it renders correctly.
  2. Open the file with the browser tool (`browser_navigate` to `file:///tmp/help-article-preview-<slug>-<locale>.html`) and take a full-page screenshot.
  3. Post the screenshot image(s) to Slack using `MEDIA:/path/to/screenshot.png`. For long articles, take 2–3 paginated screenshots covering the full content.
  4. Include real screenshot assets (`<img src="...">`) in the HTML file when they are available, so they appear in the rendered preview.
  5. Do not post the raw HTML source in the thread unless a teammate explicitly asks for the source for debugging.
- Use Intercom-ready semantic HTML for the article body: `<h1>`, `<h2>`, `<h3>`, `<p>`, `<strong>`, `<ol>`, `<ul>`, `<li>`, `<a>`, `<img>`, `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, and `<td>` as needed.
- Do not show Markdown syntax such as `##`, `**bold**`, `1.`, `-`, or `[text](url)` in the visible article body.
- Do not include `<script>`, event handlers, external CSS, private source paths, evidence notes, or implementation details in the HTML file.
- Keep screenshot placeholders as visible `[Screenshot: <description>]` text blocks in the HTML when real screenshots are unavailable. Replace placeholders with real `<img>` tags once screenshots are captured.
- HTML output must preserve the same article structure, wording, numbering, FAQ, and audience metadata as the validated source.

### Section divider rules

- Add a visual divider (`<hr>` or Intercom divider block) **after each major section** in the published Intercom article. This means after every `<h2>` section body, before the next `<h2>` or the FAQ, insert a divider.
- In HTML output, represent dividers as `<hr>` tags between sections.
- Do not place a divider before the first section or after the FAQ.

### Audience block rules

- Keep this section center-aligned in `.docx`, Google Docs, and Intercom.
- The label `Contents of this article are applicable to the following users up to access level` must be **bold and center-aligned**. Use `<p style="text-align: center;"><strong>Contents of this article are applicable to the following users up to access level</strong></p>` in HTML output.
- The metadata lines below it (Product, Platform, Access Level) must also be centered.
- In Intercom, set the paragraph alignment to center for this entire block.
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

### New article ground rules

- Title must be a simple present-tense verb + feature noun, contextual to StaffAny. Example: `Create Disbursement`, `Manage Leave Types`, `View Wallet Balance`.
- Subtitle must start with `Learn how to` followed by the contextual verb + feature noun. Example: `Learn how to create disbursement in PayrollAny`.
- For new articles, start the audience applicability block with these default values:
  - `Tier: NA`
  - `Product: PayrollAny`
  - `Platform: Web`
  - `Access Level: Owner`
- Continue with draft generation, review artifacts, and staging without pausing only to validate these default applicability values, unless the user flags them as uncertain or asks to review them.
- Add a quick explanation of the feature before the guide outline.
- The outline under `This guide will cover how to:` must list every section header in article order.
- Section headers must start with a simple present-tense verb + noun. Order sections from setting up or explaining the feature first, then using or managing it.
- Each section must use numbered user steps. Start with where the user goes in StaffAny, for example `Go to Settings > Payroll > ...`.
- Keep step text simple present tense, verb + noun where practical. Use feature conditions inside the relevant section steps instead of separating them into unrelated notes.
- Use the StaffAny help center references for structure: `Create and Manage Disbursement` for the new PayrollAny article pattern, and `Create and Manage Leave Types` for setup, edit, delete, recalculation, and condition examples.
- Use `Managing Employee Document Types` as an additional model for concise HRAny setup, edit, archive/unarchive, and reuse workflows.
- Use `references/staffany-help-center-style.md` for current StaffAny Help Center conventions. The style reference must not override code evidence or explicit user requirements.
- Insert screenshots, videos, or tables immediately after the step they support when assets are available. When screenshots are not available, use screenshot placeholders only where a reviewer can realistically supply the asset.

## Output Requirements

1. Deliver the article draft as a rendered visual preview (browser screenshot of the HTML file), not as pasted HTML in the thread. Group locales as separate screenshots (`en` then `id`). Follow the HTML preview delivery procedure in the HTML display rules section above.
2. Include "Evidence Used" notes and "Gaps/Assumptions" notes outside the public article body.
3. Generate separate Google Docs copy artifacts or `.docx` output per locale when the user or Launchbot flow asks for review artifacts.
4. Ensure generated review artifacts preserve:
   - title/heading hierarchy
   - bold text
   - centered audience block
   - correctly indented nested bullets
   - numbered lists that restart per subsection
5. Return only the requested article draft or structure. Do not add meta commentary such as "Structure complete" after the article body.
6. Do not show Markdown as the main article preview. Markdown is allowed only as an internal temporary source or when explicitly requested for debugging.

For normal `Update` mode, output one of these explicit shapes:

1. Patch-style update when the full existing article has not been loaded:
   - target article
   - HTML sections to add
   - HTML sections to modify
   - HTML FAQ additions
   - unchanged sections that should be preserved
2. Full merged article only after reading the current full article body:
   - preserve unchanged original content verbatim where practical
   - mark only the inserted or changed sections in the review notes, not inside the publishable body
   - do not remove original content unless listing a specific reason in "Gaps/Assumptions" or review notes

For bilingual `Create` or text `Update` mode, output and track both locale records:

- `en`: English source article
- `id`: Indonesian article
- Each locale record must include title, subtitle, publishable HTML body, internal notes, evidence-check result, format-check result, Google Doc URL or review artifact path, Slack review message timestamp, Intercom draft/staging status, and final status.
- Both locales must move through the same gates independently: Pantheon evidence check, format check, Google Docs review, Slack approval, Intercom draft/staging.
- Do not promote either locale to Intercom draft/staging if its own evidence or format gate fails.
- If English changes after Indonesian has been drafted, mark Indonesian `needs-refresh` and regenerate it before review.
- If Indonesian wording needs product-owner or country-market review, mark only `id` as `needs-check`; English can continue only if its own gates pass.
- Keep screenshots and video-slot references locale-aware. Reuse the same screenshot asset only when the UI is identical and the caption/nearby instructional text is localized.

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
- Title uses simple verb + feature noun
- Subtitle starts with `Learn how to`
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
- Article preview is delivered as a browser-rendered screenshot (not pasted HTML or Markdown in the thread)
- Tone is natural, concise, and user-centered
- For existing article updates, full-article output was merged from the current article body rather than reconstructed from partial notes
- For video-only updates, the patch touches exactly one registered Loom iframe and the Intercom payload uses `state: "draft"` only
