# Launchbot Launch Workflow

## Source Status

This Launchbot skill/workflow captures the workflow contract from the 2026-05-11 handoff. The runtime source code under `vk-super-productivity/launch-superpower-bot` is not present in this repo, so code-level fixes must happen in that external checkout.

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

### Step 0: Article Planning, Pantheon Evidence, Intercom Format Profile, And Pre-Publish Gates

- Input: curated English Intercom help article families, 8-12 curated Intercom format article IDs, a Pantheon topic/app/path scope, or a generated help article draft.
- Output: a cached article planning profile, article plan, normalized Intercom format profile, Pantheon evidence pack, affected-article search results, a rendered Intercom HTML preview, and pre-publish gate results.
- Pantheon source strategy:
  - Use a configured local checkout from `LAUNCH_PANTHEON_REPO`, defaulting locally to `/Users/leekaiyi/workspace/pantheon`.
  - Read only by default. Do not auto-pull or mutate Pantheon during a scan.
  - Record repo path, branch, sha, dirty status, matched app(s), app-local `AGENTS.md` guidance, source files, routes/screens, access levels, flags/gating, API/data touchpoints, statuses, user-facing labels, edge cases, conflicts, and unverified claims.
  - Relevant app mapping: `gryphon` for Web/admin behavior, `pixie` for Mobile behavior, `kraken` for backend/API/data behavior, and `manticore` only for analytics/reporting behavior.
  - If Pantheon is missing, dirty, ambiguous, stale, or conflicts with Jira/PRD/Intercom, mark the evidence `needs-check` and block Intercom staging/draft creation.
- Intercom article-shape strategy:
  - Use a Midas/Karpathy-style ingest: live Intercom is pulled on explicit refresh, full JSON/HTML stays in ignored `.cache/`, and only normalized planning evidence is committed.
  - Store article planning rules at `skills/help-article-generator/references/article-planning-profile.json`.
  - Store all-article inventory metadata at `skills/help-article-generator/references/intercom-article-inventory.json`; it may include headings, word count, inferred family, and audience/platform/product signals, but not raw article bodies.
  - `intercom:inventory` pulls the Help Center map into ignored cache and commits only normalized inventory metadata.
  - `help-article:plan --topic "<topic>"` uses the cached profile first, then the cached inventory for affected article lookup, then live Intercom only when inventory is missing or insufficient.
  - `help-article:plan` runs an adaptive intake gate after cached profile/inventory inference and before live Intercom search, drafting, or staging. If the topic is too vague to infer article family, surface, audience, or desired outcome, it returns `needs-intake` with concise questions and does not search live Intercom.
  - Planning decides `update_existing`, `create_new`, or `mixed`, plus recommended articles by audience, platform, and workflow.
  - Live Intercom is used at four points only: inventory refresh, shape refresh, affected-article search, and pre-stage target-article stale check.
  - If a cached target article `updated_at` or structural fingerprint disagrees with the live target Intercom article, staged output must be `needs-check` / `needs-refresh`.
- Source strategy:
  - Pull live Intercom articles first when credentials are available for explicit format/profile refreshes.
  - Store only normalized article fingerprints in the repo profile at `skills/help-article-generator/references/intercom-format-profile.json`.
  - Keep full pulled Intercom JSON/HTML in `.cache/launch-superpower-bot/intercom-format-corpus/`, which is ignored by git.
  - If the live Intercom pull conflicts with the stored profile, live Intercom wins and the profile must be refreshed before approval.
- Safe write boundary:
  - Search and pull operations are read-only.
  - The format gate may write local preview files under `.cache/launch-superpower-bot/format-check-previews/`.
  - Intercom writes remain draft/staging only. Do not publish publicly or overwrite an existing published article from Launchbot.
  - Public publishing stays manual in Intercom.
- Commands:
  - `npm run help-article:shape-refresh` refreshes the cached article planning profile from curated article families.
  - `npm run help-article:shape-ingest` is an alias for the shape refresh flow.
  - `npm run intercom:inventory` refreshes the all-article inventory metadata map without committing raw bodies.
  - `npm run help-article:plan -- --topic "<topic>" [--surface <surface>] [--audience <audience>] [--outcome <outcome>]` plans whether to update existing articles, create a new article, or split into multiple articles before drafting; if needed, it returns `needs-intake` with only the missing high-impact questions.
  - `npm run intercom:format:pull -- --sample-ids <article_id,article_id>` refreshes the curated format profile from live Intercom.
  - `npm run intercom:format:profile -- --sample-ids <article_id,article_id>` rebuilds the profile from cached pulls.
  - `npm run help-article:pantheon-scan -- --topic "<topic>" [--app <app,app>] [--paths <paths>]` writes a read-only Pantheon evidence pack under `.cache/launch-superpower-bot/pantheon-evidence/`.
  - `npm run help-article:evidence-check -- --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"` blocks drafts that are not supported by Pantheon evidence.
  - `npm run help-article:format-check -- --draft <draft.md> --title "<article title>"` checks generated draft format before promotion.
  - `npm run intercom:affected -- --topic "<topic>"` searches published Intercom articles first and falls back to all states if no published articles match.
  - `npm run intercom:stage-update -- --article-id <article_id> --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"` writes a local staged-update JSON and preview without writing to Intercom.
- Staged output records should include source article ID, source URL, direct Intercom edit URL, proposed title/description/body, Pantheon evidence path/result, format-gate result, and approval status.
- Staged output records should include article-shape stale check status from the cached planning profile vs live target Intercom article.
- Gate failures block promotion when Pantheon evidence is missing, dirty, ambiguous, conflicts with source docs, lacks source files, lacks platform-specific app evidence, contains unsupported product behavior claims, or leaks internal app names such as `gryphon`, `pixie`, `kraken`, or `manticore`.
- Gate failures block promotion when the generated draft has missing audience metadata, repeated title body text, raw HTML or markdown leakage, text divider lines, internal appendix content, bad list numbering, missing FAQ, or missing numbered outline.

### Step 1: Help Article Trigger

- Input: shipped Jira feature, reason, and summary.
- Current proven test: `KER-1742`, Club Blue, ClubAny brands, perks, and redemptions, version `v005`.
- Output: one or more article records with slug, title, article markdown, internal notes, and manifest metadata.
- Required drafting behavior:
  - Run article planning before drafting. Do not skip the cached Intercom article planning profile unless explicitly doing a one-off manual draft outside Launchbot.
  - Use the VM-local Pantheon checkout as the StaffAny product behavior source of truth before writing.
  - Jira tickets and PRDs can explain launch intent, but Pantheon code decides actual labels, screens, buttons, access, APIs, flags, and edge cases.
  - Verify backend/API behavior in `apps/kraken`, web/admin behavior in `apps/gryphon`, mobile behavior in `apps/pixie`, and product labels or permissions in the actual code paths.
  - Use Pantheon-grounded product behavior evidence before writing.
  - Derive audience metadata from Pantheon evidence when possible.
  - Keep implementation evidence, assumptions, source paths, and commit details outside the publishable article body.
  - Never expose internal app names such as `gryphon`, `pixie`, `kraken`, or `manticore` in the publishable article body.
  - Do not emit visible raw HTML, repeated titles, text divider lines, or internal appendix content in publishable markdown.
  - For ClubAny / Club Blue content, use `Product: StaffAny`.
  - For ClubAny brand/perk management, prefer one combined management article unless the user explicitly requests separate owner/staff articles.

### Update Lane: Video-only Help Article Update

- Input: Slack request such as `@Launch Bot update the Timesheet how-it-works video with <loom link>`.
- Output before mutation: preview of article, registered slot, current video, new Loom embed URL, exact iframe patch summary, `will_publish: false`, and confidence.
- Output after user confirmation with `draft it`: Intercom draft URL or draft article ID, `article_state: "draft"`, slot ID, video source, and `will_publish: false`.
- Required behavior:
  - Treat this as a sub-mode of the existing `help-article-generator` `Update` lane.
  - Use `skills/help-article-generator/references/video-placement-registry.json` as the placement authority.
  - Accept Loom share/embed URLs only and normalize them to an Intercom-safe Loom embed URL.
  - Use `preview_help_article_video_update` before any mutation.
  - Use `create_help_article_video_update_draft` only after explicit confirmation with `draft it`.
  - Replace only the registered video block using `replace_next_video_after_anchor`.
  - Block if the article hint, slot, anchor text, provider, or current video block does not validate exactly.
  - Do not rewrite article text, generate Google Docs review drafts, publish, delete, tag, move collections, or mutate unregistered video blocks.
  - Intercom body updates use HTML because the Articles API stores article body as HTML and accepts article updates through `PUT /articles/{article_id}`.
  - Video embeds must use supported embed URLs; raw `.mp4`, Slack file URLs, unsupported hosts, missing video IDs, and ambiguous links are out of scope.

### Step 2: Google Docs Approval

- Input: Step 1 issue/version manifest.
- Output: per-article Google Docs, review routing metadata, and Slack review messages.
- Legacy single-article manifests must be upgraded into structured article records before promotion.
- Multiple article outputs must remain separately tracked by slug, Google Doc URL, and Slack message timestamp.
- Slack review messages require bot-owned posting credentials. Do not use a human user token for visible automation replies.
- Launchbot Slack tests must use the `@Launch Bot` app profile (`user_id=U0ASVD79UT1`, `bot_id=B0ATPPEGBCH`). Do not use `@codexlaunchbot` / Kea Reloaded for Launchbot tests.
- Launchbot tests default to Slack `#launch-bot-testing` (`C0B32M34J3W`). Use a different channel only when the user explicitly asks for it.
- Launchbot Slack Socket Mode event subscriptions must include bot events `app_mention` and `message.channels`. `message.channels` is required for channel thread/mention events to reach the Hermes gateway; without it, the service can be connected but never receive the smoke message.
- Launchbot Slack OAuth scopes must include `app_mentions:read`, `channels:history`, `channels:read`, and `chat:write`.
- Slack automation copy should keep the `Launchbot automation:` prefix and use a light cowboy voice, for example `Howdy, partner`, while keeping approval instructions factual.
- Read-only product-commitment / KER lookup may run in `#all-product-questions` (`C01RZ7SHC8K`); Google Docs approval routing still defaults to `#launch-bot-testing`.

### Step 3: Intercom Draft Creation

- Input: approved Slack reaction for a specific article review message.
- Output: Intercom draft articles, direct draft URLs when available, and bot-owned Slack progress/final replies.
- Approval behavior:
  - Use the Slack approval reaction configured by the runtime source.
  - Ignore unauthorized reviewers.
  - In the VM-safe runner, `--approval-only` reads the stored Step 2 Slack timestamp, verifies a non-bot approval reaction, optionally filters against `LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS`, creates the Intercom draft, and posts a bot-owned thread reply.
  - If Slack cannot replay an old reaction after webhook changes, remove and re-add the reaction.
- Intercom behavior:
  - Run the Pantheon evidence gate before creating an Intercom draft.
  - Run the pre-publish format gate before creating an Intercom draft.
  - Treat successful draft creation as success even if the API response has no URL.
  - Construct direct Intercom article URLs when IDs are available.
  - Create drafts only; public publishing remains outside this packet.
  - For video-only updates, update existing articles with `state: "draft"` only and do not touch tags or collection placement.
- Google Docs HTML export should normalize duplicate title headings, internal appendices, center alignment, bold spans, heading anchors, and body-level heading depth before Intercom insertion.

### Feature Intake Channel Monitor

- Current status: no-agent monitor beside the normal mention-gated Slack gateway.
- Input: top-level messages and thread replies in configured public channels, defaulting to `#input-features-ux` (`CF8PK6V4J`).
- Output: one compact `Launchbot automation: Potential KER intake detected.` preview in the source thread, or an existing KER link when the Slack permalink is already captured.
- Required behavior:
  - Keep `slack.require_mention=true` for normal Launchbot replies; do not route every channel message through the Hermes agent loop.
  - Poll with `runtime/monitor-feature-intake.py` from no-agent cron `launchbot feature intake monitor` on `* * * * *`.
  - Use `SLACK_BOT_TOKEN` only; do not use the Slack connector or a human user token for monitoring or posting.
  - Use `conversations.history` for channel messages and `conversations.replies` for thread approvals.
  - Skip bot messages, Launchbot automation messages, empty/deleted messages, and duplicate source permalinks.
  - Store only channel ID, thread/message timestamps, source permalink, safe summary, status, preview post timestamp, issue key, and timestamps in `feature-intake-monitor-state.json`. Do not store raw Slack transcripts.
  - Post previews with `chat.postMessage` as Launchbot only, with the `Launchbot automation:` prefix.
  - Create Jira only after exact in-thread `create intake` or `create KER intake`; `yes`, `ok`, `create`, `+1`, and similar replies are not approval.
  - If `LAUNCHBOT_FEATURE_INTAKE_APPROVER_USER_IDS` is set, only those Slack user IDs can approve; otherwise any non-bot teammate in the configured channel can approve.
  - Dry-run with `--dry-run --channel CF8PK6V4J --since-minutes 30` before enabling or after changing monitor logic.

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
- `LAUNCH_INTERCOM_HELP_CENTER_ID`
- `LAUNCH_INTERCOM_FORMAT_SAMPLE_IDS`
- `LAUNCH_INTERCOM_SHAPE_FAMILIES`
- `LAUNCH_PANTHEON_REPO`
- `LAUNCH_PANTHEON_APPS`
- `LAUNCH_GOOGLE_AUTH_JSON`
- `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`
- `LAUNCH_STEP2_SLACK_CHANNEL_ID`
- `LAUNCH_STEP3_SLACK_APPROVAL_REACTION`
- `LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS`

Launchbot also expects a local Pantheon source checkout for help article behavior verification:

- Default path: `~/.hermes/profiles/launchbot/source/pantheon`
- Remote: `git@github.com:staffany-eng/pantheon.git`
- Branch: `develop`
- Refresh script: `~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh`
- Freshness status: `~/.hermes/profiles/launchbot/runtime/pantheon-repo-status.json`

Secret values must come from the approved secret store or secure sharing path. Do not commit token values, service-account JSON, OAuth credentials, or `.env` files.

For local LaunchBot testing, use the Secret Manager wrapper instead of sourcing copied `.env` values:

```bash
node scripts/launchbot-with-secrets.mjs --check --only intercom
node scripts/launchbot-with-secrets.mjs --only intercom -- node apps/launchbot/runtime/intercom-format-gate.mjs intercom:affected --topic "<topic>"
```

The wrapper loads secrets from GCP Secret Manager into the child process only. The current Intercom secret source is `launchbot-step3-intercom-access-token` in project `staffany-warehouse`, mapped to `LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN` and `INTERCOM_ACCESS_TOKEN`.

Default test channel: `#launch-bot-testing` (`C0B32M34J3W`).
Default read-only KER lookup channels: `#launch-bot-testing` (`C0B32M34J3W`), `#proj-cs-seonggong-seorae` (`C0AJAUNCEL8`), and `#all-product-questions` (`C01RZ7SHC8K`).

## Help Article Format Target

Use the upgraded `help-article-generator` skill in this packet. The current ClubAny target is one combined management article with:

- `Managing Brands`
- `Managing Perks`
- `FAQ`

The content must explain that a brand is the business profile, a perk sits under a brand and contains redeemable perk details, and an active brand still does not appear in the mobile catalogue until it has at least one active perk.

## Video Placement Registry

V1 video-only updates support English Loom slots only. The registry seeds public StaffAny help article examples before touching real Intercom drafts:

- `web-app-timesheet`: Timesheet how-it-works video.
- `run-payroll`: Payroll how-it-works video.
- `general-settings`: Settings navigation video.

The registry fields are `article_key`, `locale`, `title`, `public_url`, `intercom_article_id`, and `slots[]`. Each slot stores `slot_id`, `purpose`, `anchor_text`, `provider: "loom"`, and `replace_policy: "replace_next_video_after_anchor"`.

## Known Gaps

- Stronger ClubAny-specific planning is still needed in Step 1 source code.
- DOCX output needs real Word numbering definitions for numbered and nested lists.
- Screenshot capture or screenshot placeholders are not automated.
- Visual DOCX render QA needs a document renderer such as LibreOffice.
- Step 4 launch derivatives are not implemented in the handoff source.
