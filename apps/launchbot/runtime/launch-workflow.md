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
  - Name the proven lane: code-grounded English and Indonesian help article drafts shown as Intercom-ready HTML, Google Docs review drafts, Slack approval routing, Intercom draft articles after approval, and concise release-note drafts with validator confidence scoring.
  - State that the PMM workflow is scoped to help articles and concise release notes.
  - Do not list generic assistant categories such as web search, ML experiments, creative writing, smart-home control, social posting, broad email/calendar management, or generic coding-agent orchestration.

### Product Commitment Questions

- Input: Slack questions such as `check product commitment for this thread`, `is this committed on roadmap`, `any ETA`, or `can u check` in configured product-question channels.
- Output: read-only commitment status from Jira KER/JPD safe fields.
- Required behavior:
  - Use `check_product_commitment_from_slack_thread`.
  - Read bounded Slack thread context with the Launchbot bot token only.
  - Search Jira KER/JPD read-only.
  - Count only explicit Jira `fixVersions` or reviewed field IDs from `LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS` as commitment evidence.
  - If no reviewed commitment field exists, say `No committed Jira roadmap evidence found for <topic> yet` with `Confidence: needs-check`.
  - Do not infer ETA from Slack wording, Jira status, assignee, priority, or model reasoning.
  - Do not create intake, create/update Jira issues, comment, transition, assign, delete, bulk-update Jira, or post from the MCP tool.

### IFI Feature Request Tracking

- Input: APQ or Slack request such as `track IFI for <HubSpot company URL/name>: <feature gap>`.
- BD notes input: meeting-note text plus an optional confirmed HubSpot company URL/ID. Use `preview_ifi_feature_request_from_bd_note`; do not treat extracted company text as confirmed identity.
- Output before mutation: resolved HubSpot company, IFI dedupe result, exact Jira create/update payload, source Slack thread, optional KER link, and `willMutateJira: false`.
- Output after confirmation with `confirm IFI`: IFI issue key/URL and a bot-owned Slack reply draft starting with `Launchbot automation:`.
- Required behavior:
  - Use `preview_ifi_feature_request_tracking` before any APQ/Slack Jira write.
  - Use `preview_ifi_feature_request_from_bd_note` before any BD-notes-driven Jira write.
  - Use `create_or_update_ifi_feature_request_tracking` only after exact confirmation for APQ/Slack requests.
  - Use `create_or_update_ifi_feature_request_from_bd_note` only after exact confirmation for BD notes.
  - Resolve the company through HubSpot first. HubSpot Company ID is canonical for customer/prospect identity.
  - Return `needs-check` and ask for a HubSpot company link or numeric ID when company text is ambiguous, empty, or only an unconfirmed alias.
  - Dedupe IFI by `HubSpot Company ID` (`customfield_10881`) plus feature keyword.
  - Use IFI project `IFI` and Feature Request issue type ID `10151`.
  - Store requester, source Slack thread, original question, APQ classification, and KER key in the structured IFI description.
  - Link IFI to KER with a Jira issue link when a KER key is supplied.
  - Block without the exact approval marker `confirm IFI`.
  - Do not mutate HubSpot, do not use Jira Organizations as CRM truth, and do not post Slack messages from the MCP tool.

### Step 0: Article Planning, Pantheon Evidence, Intercom Format Profile, And Pre-Publish Gates

- Input: curated English Intercom help article families, 8-12 curated Intercom format article IDs, a Pantheon topic/app/path scope, or a generated help article draft.
- Output: a cached article planning profile, article plan, normalized Intercom format profile, Pantheon evidence pack, affected-article search results, a rendered Intercom HTML preview, and pre-publish gate results.
- Visible help article previews shown in Slack or chat must be Intercom-ready HTML, not Markdown. Markdown source may be used internally only for existing gate commands that require `--draft <draft.md>`.
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
- Output: one or more locale-aware article records with slug, locale, title, article markdown, internal notes, gate status, review routing metadata, and manifest metadata.
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
  - For normal create or text-update article work, create both English (`en`) and Indonesian (`id`) article records.
  - Generate English first as the source draft, then create Indonesian from the validated English structure and the same Pantheon evidence.
  - Keep product behavior, UI labels, limits, eligibility, and steps equivalent across both locales; localized wording must not introduce new product claims.
  - Run Pantheon evidence and Intercom format gates separately for `en` and `id`. A passing English draft does not approve the Indonesian draft.
  - If English changes after Indonesian has been drafted, mark Indonesian `needs-refresh` and regenerate it before review or staging.
  - If Indonesian needs local market or language review, mark only the Indonesian locale `needs-check` while leaving English governed by its own gates.
  - Screenshot capture is optional and runs after article planning/drafting as an asset enhancement. A failed, blocked, or unavailable screenshot runner must keep precise placeholders and a blocker note, but must not block Pantheon evidence checks, Google Docs review creation, Slack approval routing, or Intercom draft/staging for otherwise valid article text.
  - Real screenshots may be inserted only when captured from approved DEV/staging/local sources with demo-safe data and verified redaction.
  - When screenshot capture is blocked on staging, use `help-article-screenshot-troubleshooter` to verify Playwright, hydrate staging credentials from Secret Manager or the live profile, create runtime-only storage state, and rerun the plan. Do not store storage-state in this repo.

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
- Output: per-article, per-locale Google Docs, review routing metadata, and Slack review messages.
- Legacy single-article manifests must be upgraded into structured article records before promotion.
- Multiple article outputs must remain separately tracked by slug, locale, Google Doc URL, and Slack message timestamp.
- English and Indonesian review artifacts must be reviewed and approved independently. Do not use one locale's approval reaction to approve the other locale.
- Slack review messages require bot-owned posting credentials. Do not use a human user token for visible automation replies.
- Launchbot Slack tests must use the `@Launch Bot` app profile (`user_id=U0ASVD79UT1`, `bot_id=B0ATPPEGBCH`). Do not use `@codexlaunchbot` / Kea Reloaded for Launchbot tests.
- Launchbot tests default to Slack `#launch-bot-testing` (`C0B32M34J3W`). Use a different channel only when the user explicitly asks for it.
- When verifying a SOUL-changing deploy in an existing Slack thread, run the live-profile audit and reset any reported `sessions:stale-system-prompt` session before smoke testing. Hermes persists per-thread system prompts, so a healthy restarted gateway can still answer from stale instructions if the thread session is left active.
- Launchbot Slack Socket Mode event subscriptions must include bot events `app_mention` and `message.channels`. `message.channels` is required for channel thread/mention events to reach the Hermes gateway; without it, the service can be connected but never receive the smoke message.
- Launchbot must set `slack.allow_bots=mentions` and `slack.strict_mention=true` so Jira/app-authored messages with a direct Launchbot mention are admitted without enabling bot-to-bot thread loops.
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
  - For bilingual articles, create draft/staging output per locale only after that locale has its own approval, Pantheon evidence pass, and format pass.
  - Store each locale's Intercom draft/staging ID and URL separately. Do not overwrite or publish a different locale article from a shared approval.

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

### Weekly Support Watch

- Current status: no-agent weekly report beside the normal mention-gated Slack gateway.
- Input: recent BigQuery-backed Intercom conversations plus optional WhatsApp support logs from the previous report window.
- Output: one compact `Launchbot automation:` report in `#all-bugs-production` only when new, untracked production-bug signals exist.
- Schedule: UTC VM cron `0 1 * * 4`, which is Thursday 09:00 SGT.
- Required behavior:
  - Preview with `preview_weekly_support_watch_report`.
  - Scheduled runs use `runtime/monitor-support-watch.py` from no-agent cron `launchbot support watch`.
  - Query BigQuery source tables `intercom.conversations`, `intercom.conversation_parts`, and optionally the native `analytics.support_watch_whatsapp_ticket_logs` mirror; count the full report window, then fetch bounded candidate rows using problem-keyword scoring instead of sampling only the latest rows. Persist only support-source IDs, safe summaries, source URLs, state, available team/admin assignee IDs, timestamps, signatures, source row counts, and safe counters.
  - Keep the native WhatsApp mirror fresh through BigQuery scheduled query `Launchbot support watch WhatsApp native mirror refresh` on `every day 00:30` UTC. The weekly runtime path must not query the Drive-backed `gsheets` source directly.
  - Cluster likely production bugs by repeated topic, shared error phrase, or one high-severity blocker.
  - Trace likely product/code causes through the Pantheon checkout and recent Git evidence. Treat this as heuristic and require review before claiming root cause.
  - Dedupe against recent `#team-cs-eng-duty` posts through `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS`, EDT issues through `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL`, and prior state at `LAUNCHBOT_SUPPORT_WATCH_STATE_PATH`.
  - Post only to `#all-bugs-production`, configured as `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME=all-bugs-production` plus deploy-resolved `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID`.
  - No new findings means no Slack post.
  - Do not create Linear/Jira tickets, tag engineers, assign owners, transition issues, comment on issues, or persist raw support transcripts.
  - Dry-run with `--dry-run --max-tickets 20` after BigQuery/Jira/Slack env is present and before enabling the weekly cron.

### Step 4: Launch Derivatives

- Current status: skill-backed drafting workflow, still approval-gated and not public-publish automated.
- Target outputs for Phase 1: help article work items and concise release notes with evidence-based validation.
- Use `product-marketing-launch-workflow` to map KER Roadmap sprint rows to required materials from Launch Priority.
- Use `help-article-generator` for create/update help article work, including English and Indonesian locale flows.
- Every help article draft or update patch must pass through `help-article-validator` with evidence-based reasoning and a 0-100 confidence score.
- Every help article preview returned to a teammate must be HTML-labelled / fenced `html`, not `.md`.
- If help article validation returns `Revise before drafting`, use `help-article-feedback-updater`, then rerun the validator before Google Docs review, Slack approval, or Intercom staging.
- Use Create and Manage Disbursement and Managing Employee Document Types as model references for help article formatting, wording, structure, and high-score completeness.
- Use `release-notes-generator` for release notes.
- Every release note draft must pass through `release-notes-validator`.
- If validation returns `revise`, use `release-notes-feedback-updater`, then rerun the validator before review.
- For approved release-note posts, run `help-article-screenshot-capture` and include only 1-2 contextually correct screenshots that directly show the UI/UX delta.
- Mention the Jira Product Lead in the Slack review thread.
- After exact Product Lead approval, send the final release notes to `#all-product-new-updates` (`C03QQ2ERMT7`) or the configured release-note output channel.
- Changelog / What's New and WhatsApp Community messages are out of scope for this PMM workflow.
- Public publishing, newsletter sends, homepage updates, pricing updates, blog posts, PR, social, and sales-deck changes remain manual or separate Marketing/Rev handoffs until implementation and regression evidence exist.

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
- `LAUNCHBOT_SUPPORT_WATCH_SOURCE`
- `LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT`
- `LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET`
- `LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET`
- `LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS`
- `LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP`
- `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW`
- `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_SOURCE_VIEW`
- `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_REFRESH_TRANSFER_NAME`
- `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_REFRESH_SCHEDULE_UTC`
- `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_MAX_STALENESS_HOURS`
- `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME`
- `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID`
- `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS`
- `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL`
- `LAUNCHBOT_SUPPORT_WATCH_STATE_PATH`
- `LAUNCHBOT_SUPPORT_WATCH_LOOKBACK_DAYS`
- `LAUNCHBOT_SUPPORT_WATCH_MAX_TICKETS`

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
- Screenshot capture is runner-backed through `runtime/help-article-screenshot-runner.mjs`, but actual captures still require approved DEV/staging or local Gryphon access with demo data. Screenshot blockers must keep placeholders and must not fail the core help article draft, Google Docs review, Slack approval, or Intercom draft/staging path.
- Visual DOCX render QA needs a document renderer such as LibreOffice.
- PMM workflow launch derivatives are scoped to help article work items and concise release notes with validator checkpoints only; changelog and WhatsApp Community are out of scope.
