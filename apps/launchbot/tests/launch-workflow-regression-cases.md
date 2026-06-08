# Launchbot Launch Workflow Regression Cases

## Slack Identity And Capability

- Given a Slack prompt like `what can u do, partner?`, Launchbot should answer as Launchbot only: shipped Jira feature to code-grounded help article drafts shown as Intercom-ready HTML, Google Docs review drafts, Slack approval routing, and Intercom draft articles.
- Capability answers must not list generic assistant categories such as web search, ML experiments, creative writing, smart-home control, social posting, broad email/calendar management, or generic coding-agent orchestration.

## Help Article Drafting

- Given any StaffAny product behavior claim, LaunchBot should verify the VM-local Pantheon checkout before drafting; Jira and PRD content can explain intent but must not override code behavior.
- If Pantheon is missing, stale, dirty, or conflicts with Jira/PRD, LaunchBot should return `needs-check` or blocked source status rather than inventing article steps.
- Internal notes must include Pantheon branch/sha, checkout freshness, and key `apps/kraken`, `apps/gryphon`, or `apps/pixie` paths used as evidence when relevant.
- Given any help-article topic, Launchbot should run `help-article:plan` from the cached Intercom article planning profile before drafting.
- Given a clear topic such as `ClubAny brands and perks`, `help-article:plan` should infer article family, surface, audience, and desired outcome from the cached profile/inventory and proceed without a separate interview.
- Given a vague topic such as `new thing`, `help-article:plan` should return `needs-intake` with concise `intake.questions` for only the missing high-impact fields and should not run live Intercom search.
- Given explicit `--surface`, `--audience`, and `--outcome` flags, `help-article:plan` should use them before topic/profile/inventory inference.
- Given an ambiguous topic that matches multiple article families, `help-article:plan` should return `needs-intake` with a family clarification question before split/update decisions.
- Given a topic that matches an existing same-audience same-platform Intercom article, the planner should recommend `update_existing` instead of a duplicate new article.
- Given New Joiner scope, the planner should recommend separate articles for New Joiner Form setup, Onboarding New Hires, and Submitting New Joiner Form.
- Given Company Documents scope, the planner should separate Web owner/admin document management from Mobile employee acknowledgement/viewing.
- Given ClubAny scope, the planner should keep brand/perk management together and keep Mobile perk redemption separate.
- Given Claims scope, the planner should split setup, submission, approval management, payroll processing, and cutoff behavior.
- Given Leave Calendar scope, the planner should prefer one combined manager-facing Web/Mobile article unless Pantheon shows different workflows.
- Given `KER-1742` / ClubAny brand and perk management, Step 1 should prefer one combined management article with `Managing Brands`, `Managing Perks`, and `FAQ`.
- Help article product-behavior claims must be grounded in a Pantheon evidence pack from `help-article:pantheon-scan` before Google Docs or Intercom promotion.
- Draft markdown must not include raw HTML tags, text divider lines, repeated title text in the body, or internal appendix content.
- Audience block must include Product, Platform, and Access Level; Tier is optional for now. ClubAny / Club Blue content must use `Product: StaffAny`.
- Audience metadata should be derived from Pantheon evidence where possible, while internal app names such as `gryphon`, `pixie`, `kraken`, and `manticore` must not appear in the publishable article body.
- The guide outline must be a numbered list, and numbered steps must restart at `1` for each subsection.
- Internal notes must include source of truth, Pantheon evidence path, repo and branch or sha, key paths or symbols, API/data touchpoints, assumptions, and last verified commit outside the publishable body.
- Created or updated help article previews shown to teammates must be Intercom-ready HTML, not Markdown.

## Video-only Help Article Updates

- Given `@Launch Bot update the Timesheet how-it-works video with https://www.loom.com/share/...`, Launchbot should resolve `web-app-timesheet` and `how-timesheet-works-video` from the registry before any mutation.
- Preview must return article, slot, current video, new video, exact patch summary, `will_publish: false`, and confidence.
- Given a non-Loom URL, raw `.mp4`, Slack file URL, missing Loom ID, unsupported host, or ambiguous article hint, Launchbot should block before calling Intercom.
- Given no registered slot match, Launchbot should block instead of using model inference to choose placement.
- Given a missing or duplicated anchor/video block in the current Intercom HTML, Launchbot should block as drift.
- Given user confirmation `draft it`, Launchbot should call `create_help_article_video_update_draft`, update only the registered Loom iframe, and send Intercom `state: "draft"` only.
- Video-only updates must not rewrite article text, create Google Docs review docs, publish, delete, tag, move collections, or mutate unregistered videos.

## Feature Intake Channel Monitor

- A feature-like message in `#input-features-ux` causes at most one `Launchbot automation: Potential KER intake detected.` preview in the source thread.
- A duplicate Slack source permalink returns the existing KER link instead of another create prompt.
- Exact `create intake` or `create KER intake` in the previewed thread creates one KER Idea.
- Replies such as `yes`, `ok`, `create`, and `+1` do not create Jira issues.
- Bot messages, Launchbot automation messages, deleted/empty messages, and repeated source permalinks are ignored.
- The monitor state stores safe summaries and source pointers only; raw Slack transcripts are not persisted.

## Weekly Support Watch

- A repeated Intercom conversation or WhatsApp support-log topic should produce a single clustered finding, not one finding per source row.
- A high-severity single support blocker should produce a `needs-check` finding with source IDs and safe summaries only.
- Email addresses, phone numbers, raw conversation bodies, and raw support-log bodies must be redacted or omitted from support-watch output and state.
- Findings already present in recent `#team-cs-eng-duty` posts must be deduped and must not post to `#all-bugs-production`.
- Findings already present in EDT Jira results from `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL` must be deduped and must not post to `#all-bugs-production`.
- Findings already present in `support-watch-state.json` must be deduped and must not post again.
- No new findings means no Slack post.
- New untracked findings post one compact `Launchbot automation:` report to `#all-bugs-production`.
- Support watch must not create Linear/Jira tickets, tag engineers, assign owners, comment on issues, transition issues, or persist raw support transcripts.

## Product Commitment Checks

- Given `@Launch Bot check product commitment for this thread` in `#all-product-questions`, Launchbot should call only `check_product_commitment_from_slack_thread`.
- Product commitment checks should be allowed by `LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS` and should not widen the feature-intake channel allowlist.
- The MCP should read bounded Slack context with the bot token, sanitize thread summaries, and never persist raw Slack transcripts.
- The MCP should search Jira KER/JPD read-only and must not post Slack messages, create intake, create/update Jira issues, comment, transition, assign, delete, or bulk-update Jira.
- Given no matching Jira issue, Launchbot should return `No matching KER/JPD issue found` with `Confidence: needs-check`.
- Given a matching Jira issue without `fixVersions` or configured reviewed commitment fields, Launchbot should return `No committed Jira roadmap evidence found for <topic> yet` with `Confidence: needs-check`.
- Given a matching Jira issue with `fixVersions`, Launchbot should return the issue key, summary, status, Jira link, and fixVersion commitment evidence with `Confidence: verified`.
- Given a matching Jira issue with a non-empty field configured in `LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS`, Launchbot should treat that configured reviewed field as commitment evidence.
- Launchbot must never infer an ETA from Slack wording, Jira status, assignee, priority, or model reasoning.

## IFI Feature Request Tracking

- Given `track IFI for <HubSpot company URL>: Citibank bank file export`, Launchbot should call `preview_ifi_feature_request_tracking` first and should not mutate Jira.
- Preview must resolve the HubSpot company, build a dedupe JQL using `HubSpot Company ID`, include the source Slack thread, original question, APQ classification, and return `willMutateJira: false`.
- Given multiple or zero HubSpot matches, Launchbot should return `needs-check`, ask for a HubSpot company link or numeric ID, and must not create an IFI issue.
- Given `neon group`, Launchbot may return candidate companies such as `Victory Hill Exhibitions Pte Ltd` but must not auto-map the alias without human confirmation.
- Given a BD note such as `Neon Group asked whether StaffAny can generate a native Citibank payroll bank file.`, Launchbot should call `preview_ifi_feature_request_from_bd_note`, extract the company hint and feature gap, and return `needs-check` until a confirmed HubSpot Company ID is supplied.
- Given the same BD note with confirmed HubSpot Company ID `25638156628`, Launchbot should dedupe by `HubSpot Company ID` plus `citibank` and update an existing IFI instead of creating a duplicate.
- Given no exact `confirm IFI` approval marker, `create_or_update_ifi_feature_request_tracking` should block and return the preview.
- Given no exact `confirm IFI` approval marker for a BD note, `create_or_update_ifi_feature_request_from_bd_note` should block and return the preview.
- Given `confirm IFI`, Launchbot should create or update an IFI issue with `customfield_10881`, write the structured description, link a supplied KER key, and return a `Launchbot automation:` Slack reply draft without posting from the MCP.
- IFI tracking must not mutate HubSpot and must not use Jira Organizations or StaffAny Organization as CRM truth.

## Pantheon Evidence Gate

- Given a topic and explicit app scope, `help-article:pantheon-scan` should use `LAUNCH_PANTHEON_REPO` or the local default `/Users/leekaiyi/workspace/pantheon`, record branch/sha/dirty state, read app-local `AGENTS.md`, and output source files plus routes/screens, access levels, flags/gating, API/data touchpoints, statuses, labels, and edge cases.
- Given a missing or dirty Pantheon checkout, the scanner should return `needs-check` and block Intercom staging/draft creation.
- Given a broad topic that matches multiple Pantheon apps without explicit `--app` or `--paths`, the scanner should return `needs-check` with ambiguous app scope.
- Given a Web article without Gryphon evidence or a Mobile article without Pixie evidence, `help-article:evidence-check` should return `needs-check`.
- Given unsupported product behavior claims or internal Pantheon app names in the publishable body, `help-article:evidence-check` should return `needs-check`.

## Intercom Format Profile And Gate

- Given 8-12 curated English Intercom article IDs, `intercom:format:pull` should fetch live article JSON, cache full HTML only under `.cache/launch-superpower-bot/intercom-format-corpus/`, and write normalized fingerprints to `intercom-format-profile.json`.
- Given a generated draft, `help-article:format-check` should produce `pass` or `fail`, blocking errors, warnings, closest reference article, and a rendered Intercom HTML preview path.
- The format gate should fail drafts with missing audience metadata, repeated title body text, raw HTML or markdown leakage, text divider lines, internal appendix content, bad list numbering, missing FAQ, or missing numbered outline.
- If the live Intercom pull and stored format profile disagree, live Intercom wins and the profile should be refreshed before approval.

## Intercom Affected Article Search

- `help-article:shape-refresh` should pull curated article families only, cache full JSON/HTML under `.cache/launch-superpower-bot/intercom-article-shape-corpus/`, and commit only normalized article-shape evidence to `article-planning-profile.json`.
- `intercom:inventory` should pull all article metadata, cache full JSON/HTML under `.cache/launch-superpower-bot/intercom-article-inventory/`, and commit only normalized inventory metadata plus derived content signals to `intercom-article-inventory.json`.
- `help-article:plan` should use the cached planning profile first, use the cached inventory for affected-article lookup, and use live Intercom only when inventory is missing or confidence is insufficient.
- Given a topic, `intercom:affected` should search live Intercom published articles first and fall back to `state=all` only when no published articles match.
- Results should include article ID, title, public URL, state, updated timestamp, direct Intercom edit URL, highlight, confidence, and `approval_status: not_requested`.
- Given an affected article and proposed draft, `intercom:stage-update` should write a local staged-update JSON with source article ID, source URL, direct Intercom edit URL, proposed title, proposed description, proposed HTML body, format-gate result, and `approval_status: not_requested`.
- `intercom:stage-update` must require a Pantheon evidence path and include `pantheon_evidence_path` plus `pantheon_evidence_result` in the staged-update JSON.
- `intercom:stage-update` must pull the exact target article live and compare it against the cached planning profile when that article is present. If `updated_at` or structural fingerprint differs, staged output should include `article_shape_stale_check.status: needs-refresh` and block promotion.
- Search and pull operations must not write to Intercom.
- Public publishing stays manual in Intercom; Launchbot may only create draft/staging output after explicit approval.

## Google Docs Promotion

- A single-article legacy manifest should be upgraded into a structured article record without losing article slug, title, markdown, or internal notes.
- Multiple articles should create and track separate Google Docs and Slack review messages.
- Slack review messages must be posted by the bot identity when posting is enabled.
- Slack review messages must use the `@Launch Bot` profile (`user_id=U0ASVD79UT1`, `bot_id=B0ATPPEGBCH`), not `@codexlaunchbot` / Kea Reloaded.
- Launchbot test runs should post to `#launch-bot-testing` (`C0B32M34J3W`) unless the user explicitly names another channel.
- Slack Socket Mode subscriptions must include bot events `app_mention` and `message.channels`; if the gateway is connected but receives no inbound smoke event, debug Slack event subscription drift first.
- Jira/app-authored messages containing `<@U0ASVD79UT1>` must be admitted with `slack.allow_bots=mentions`; app-authored messages without that direct mention must remain ignored, and `slack.strict_mention=true` must prevent follow-up bot loops.
- Slack automation copy should start with `Launchbot automation:` and use a light cowboy voice without weakening the approval instruction.

## Read-only KER Lookup

- `#all-product-questions` (`C01RZ7SHC8K`) is an allowed Launchbot channel only for read-only product-commitment / KER lookup.
- KER lookup in `#all-product-questions` must read bounded Slack context with the Launchbot bot token, call Jira KER read-only, and never create feature intake, post from the MCP, or mutate Jira.

## Indonesia Payroll Tax Answers

- Given `@Launch Bot does StaffAny have A1 form?`, Launchbot should route to `skills/staffany-indonesia-payroll-tax-grimoire/SKILL.md`, separate regulatory basis from StaffAny system behavior, inspect Pantheon before claiming product support, and call out gaps such as `Report 1721-A1 - Coming Soon` versus `Bukti Pemotongan A1 (BPA1)` export if that remains true in code.
- Given `@Launch Bot what is the latest BPJS JP and JHT rate?`, Launchbot should state that BPJS-only questions are outside the core tax skill unless they affect payroll-tax/reporting, verify current rates/caps against official BPJS/government sources, and avoid answering from stale local tax notes alone.
- Given a question about current or changed Indonesia payroll-tax law, rates, forms, deadlines, filing channels, or regulator platform behavior, Launchbot should use `skills/indonesia-tax-knowledge-updater/SKILL.md` inside the grimoire before final answer and run the grimoire knowledge-bank validator when reference files are updated.
- Indonesia tax answers must include `Answer`, `Regulatory basis`, `StaffAny system behavior`, `Gap / risk / not validated`, `Sources checked`, and `Confidence`.
- Indonesia tax answers must not expose full NPWP, NIK, bank account, credentials, unrelated employee details, raw Slack transcripts, or unverified consultant guidance as official regulation.

## Slack Approval To Intercom Draft

- A configured approval reaction from an authorized reviewer should create one Intercom draft for the matching article slug.
- Unauthorized reviewer reactions should be ignored.
- Bilingual article creation should create separate `en` and `id` review records, and each locale should require its own approval before Intercom draft/staging.
- The pre-publish format gate should pass before any Intercom draft/staging article is created.
- The Pantheon evidence gate should pass before any Intercom draft/staging article is created.
- The pre-publish format and Pantheon evidence gates should run separately for English and Indonesian. One locale passing should not promote the other locale.
- The VM-safe approval path should accept a human ✅ reaction on the correct `@Launch Bot` review message, create one Intercom draft, and post a bot-owned thread reply with the draft link or draft ID.
- The bot should post a progress reply before draft creation when the external source listener is present and a final reply with the draft link or draft ID after creation.
- Successful Intercom draft responses without a returned URL should still be accepted when an article ID is present.

## Jira Shipped Windmill Help Article Flow

- A Jira Automation webhook for `KER-*` transitioning to `6 - Shipped & Launching` should create `run_id = issue_key + ':' + transitioned_at` and fetch the latest Jira issue snapshot before any draft work.
- A duplicate webhook for the same `run_id` should return the existing run state and must not regenerate Intercom drafts.
- A webhook for a non-`KER-*` issue or any destination status other than `6 - Shipped & Launching` should be ignored.
- If the fresh Jira issue is no longer in `6 - Shipped & Launching`, the run should block as `stale_transition`.
- If `customfield_10561` Launch Priority is blank, the run should block before drafting and post one `Launchbot automation:` blocker to `#launch-bot-testing`.
- If `JIRA_FIELD_PRODUCT_LEAD` is blank, missing, or cannot map by Slack `users.lookupByEmail` or `LAUNCHBOT_JIRA_ACCOUNT_TO_SLACK_USER_MAP`, the run should block before drafting.
- Help article planning must use cached Intercom planning first, then live affected-article stale check before any Intercom write.
- Pantheon evidence scan must pass before English or Indonesian drafting; missing, dirty, stale, ambiguous, or conflicting Pantheon evidence blocks the run.
- English must be drafted before Indonesian; if English changes after Indonesian exists, Indonesian must be marked `needs-refresh` until regenerated.
- Both English and Indonesian drafts must pass independent evidence and Intercom format gates before review or publishing.
- The Slack review request must mention the Jira Product Lead, include Jira key, launch priority, create/update decision, English draft URL, Indonesian draft URL, and exact feedback/publish instructions.
- Slack feedback is processed only from the stored review thread and only when the message mentions `@Launch Bot`.
- Non-Product Lead publish confirmation should be rejected unless the Slack user is in the configured override reviewer list.
- Publish confirmation must match exactly `@Launch Bot publish help articles KER-123`.
- Before publishing, Launchbot must re-check Jira status, both locale gates, draft article IDs, and unresolved `needs-check` / `needs-refresh` gates.
- Exact Product Lead confirmation publishes both `en` and `id` Intercom articles and posts public URLs plus audit metadata in the Slack thread.
- Intercom update mode must block unless `LAUNCHBOT_INTERCOM_UPDATE_DRAFT_SUPPORTED=true` has verified that published content remains unchanged while the draft is pending.

## Intercom HTML Normalization

- Google Docs export should remove duplicate title headings and internal appendices.
- Center alignment for the audience block should be preserved.
- Google Docs bold spans should become semantic strong text where possible.
- Body-level `h1` headings should be converted below the article title level.
- Stable heading anchors should be present for section links where possible.

## Known Gap Guards

- Do not report PMM workflow materials as public-publish automated.
- Do report PMM workflow materials as scoped to help articles and concise release notes with release-note validator gates.
- Release-note review requests must mention the Jira Product Lead in Slack.
- Product Lead approval should post approved release notes to `#all-product-new-updates` (`C03QQ2ERMT7`).
- Approved release-note posts should include only 1-2 contextually correct screenshots from `help-article-screenshot-capture`; unrelated, sensitive, unredacted, or redundant screenshots must be omitted.
- Do not claim screenshot capture is automated until source code exists and is tested.
- Do not claim visual DOCX QA is complete unless a renderer was actually run.
