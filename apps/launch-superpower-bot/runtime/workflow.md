# Launch Superpower Bot Workflow

## Source Status

This packet captures the workflow contract from the 2026-05-11 handoff. The runtime source code under `vk-super-productivity/launch-superpower-bot` is not present in this repo, so code-level fixes must happen in that external checkout.

## Step Contract

### Step 1: Help Article Trigger

- Input: shipped Jira feature, reason, and summary.
- Current proven test: `KER-1742`, Club Blue, ClubAny brands, perks, and redemptions, version `v005`.
- Output: one or more article records with slug, title, article markdown, internal notes, and manifest metadata.
- Required drafting behavior:
  - Use code-grounded evidence before writing.
  - Keep implementation evidence, assumptions, source paths, and commit details outside the publishable article body.
  - Do not emit visible raw HTML, repeated titles, text divider lines, or internal appendix content in publishable markdown.
  - For ClubAny / Club Blue content, use `Product: StaffAny`.
  - For ClubAny brand/perk management, prefer one combined management article unless the user explicitly requests separate owner/staff articles.

### Step 2: Google Docs Approval

- Input: Step 1 issue/version manifest.
- Output: per-article Google Docs, review routing metadata, and Slack review messages.
- Legacy single-article manifests must be upgraded into structured article records before promotion.
- Multiple article outputs must remain separately tracked by slug, Google Doc URL, and Slack message timestamp.
- Slack review messages require bot-owned posting credentials. Do not use a human user token for visible automation replies.

### Step 3: Intercom Draft Creation

- Input: approved Slack reaction for a specific article review message.
- Output: Intercom draft articles, direct draft URLs when available, and bot-owned Slack progress/final replies.
- Approval behavior:
  - Use the Slack approval reaction configured by the runtime source.
  - Ignore unauthorized reviewers.
  - If Slack cannot replay an old reaction after webhook changes, remove and re-add the reaction.
- Intercom behavior:
  - Treat successful draft creation as success even if the API response has no URL.
  - Construct direct Intercom article URLs when IDs are available.
  - Create drafts only; public publishing remains outside this packet.
- Google Docs HTML export should normalize duplicate title headings, internal appendices, center alignment, bold spans, heading anchors, and body-level heading depth before Intercom insertion.

### Step 4: Launch Derivatives

- Current status: planned stub.
- Target outputs: Released posts, WhatsApp drafts, and newsletter drafts.
- Do not imply Step 4 is production-ready until source code and regression evidence exist.

## Configuration Names

Required runtime environment names:

- `LAUNCH_STEP2_SLACK_BOT_TOKEN`
- `LAUNCH_STEP3_SLACK_SIGNING_SECRET`
- `LAUNCH_STEP3_SLACK_BOT_TOKEN`
- `LAUNCH_STEP3_GOOGLE_SERVICE_ACCOUNT_JSON`
- `LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN`
- `LAUNCH_STEP3_INTERCOM_STAGING_COLLECTION_ID`

Optional runtime environment name:

- `LAUNCH_STEP3_INTERCOM_AUTHOR_ID`

Secret values must come from the approved secret store or secure sharing path. Do not commit token values, service-account JSON, OAuth credentials, or `.env` files.

## Help Article Format Target

Use the upgraded `help-article-generator` skill in this packet. The current ClubAny target is one combined management article with:

- `Managing Brands`
- `Managing Perks`
- `FAQ`

The content must explain that a brand is the business profile, a perk sits under a brand and contains redeemable perk details, and an active brand still does not appear in the mobile catalogue until it has at least one active perk.

## Known Gaps

- Stronger ClubAny-specific planning is still needed in Step 1 source code.
- DOCX output needs real Word numbering definitions for numbered and nested lists.
- Screenshot capture or screenshot placeholders are not automated.
- Visual DOCX render QA needs a document renderer such as LibreOffice.
- Step 4 launch derivatives are not implemented in the handoff source.
