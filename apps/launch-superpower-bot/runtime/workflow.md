# Launch Superpower Bot Workflow

## Source Status

This packet captures the workflow contract from the 2026-05-11 handoff. The runtime source code under `vk-super-productivity/launch-superpower-bot` is not present in this repo, so code-level fixes must happen in that external checkout.

When the external source checkout is absent, use `runtime/launchbot_e2e.py` as the minimal VM-safe runner for the handoff flow. It generates versioned Step 1 artifacts, creates a Google Doc review draft, posts a bot-owned Slack review message, processes an existing approved Slack reaction with `--approval-only`, and creates an Intercom draft article with a direct Intercom app URL when the API response omits a public URL.

## Step Contract

### Slack Capability Questions

- Input: Slack questions such as `what can u do`, `what are you`, or `what can you help with`.
- Output: a short Launchbot-specific answer only.
- Required behavior:
  - Say Launchbot turns shipped Jira features into launch assets.
  - Name the proven lane: code-grounded help article drafts, Google Docs review drafts, Slack approval routing, and Intercom draft articles after approval.
  - State that Step 4 launch derivatives are planned only when relevant.
  - Do not list generic assistant categories such as web search, ML experiments, creative writing, smart-home control, social posting, broad email/calendar management, or generic coding-agent orchestration.

### Step 1: Help Article Trigger

- Input: shipped Jira feature, reason, and summary.
- Current proven test: `KER-1742`, Club Blue, ClubAny brands, perks, and redemptions, version `v005`.
- Output: one or more article records with slug, title, article markdown, internal notes, and manifest metadata.
- Required drafting behavior:
  - Use the VM-local Pantheon checkout as the StaffAny product behavior source of truth before writing.
  - Jira tickets and PRDs can explain launch intent, but Pantheon code decides actual labels, screens, buttons, access, APIs, flags, and edge cases.
  - Verify backend/API behavior in `apps/kraken`, web/admin behavior in `apps/gryphon`, mobile behavior in `apps/pixie`, and product labels or permissions in the actual code paths.
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
- Launchbot Slack tests must use the `@Launch Bot` app profile (`user_id=U0ASVD79UT1`, `bot_id=B0ATPPEGBCH`). Do not use `@codexlaunchbot` / Kea Reloaded for Launchbot tests.
- Launchbot tests default to Slack `#launch-bot-testing` (`C0B32M34J3W`). Use a different channel only when the user explicitly asks for it.
- Slack automation copy should keep the `Launchbot automation:` prefix and use a light cowboy voice, for example `Howdy, partner`, while keeping approval instructions factual.

### Step 3: Intercom Draft Creation

- Input: approved Slack reaction for a specific article review message.
- Output: Intercom draft articles, direct draft URLs when available, and bot-owned Slack progress/final replies.
- Approval behavior:
  - Use the Slack approval reaction configured by the runtime source.
  - Ignore unauthorized reviewers.
  - In the VM-safe runner, `--approval-only` reads the stored Step 2 Slack timestamp, verifies a non-bot approval reaction, optionally filters against `LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS`, creates the Intercom draft, and posts a bot-owned thread reply.
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
- `LAUNCH_STEP3_INTERCOM_APP_ID`
- `LAUNCH_GOOGLE_AUTH_JSON`
- `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`
- `LAUNCH_STEP2_SLACK_CHANNEL_ID`
- `LAUNCH_STEP3_SLACK_APPROVAL_REACTION`
- `LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS`

LaunchBot also expects a local Pantheon source checkout for help article behavior verification:

- Default path: `~/.hermes/profiles/launchbot/source/pantheon`
- Remote: `git@github.com:staffany-eng/pantheon.git`
- Branch: `develop`
- Refresh script: `~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh`
- Freshness status: `~/.hermes/profiles/launchbot/runtime/pantheon-repo-status.json`

Secret values must come from the approved secret store or secure sharing path. Do not commit token values, service-account JSON, OAuth credentials, or `.env` files.

Default test channel: `#launch-bot-testing` (`C0B32M34J3W`).

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
