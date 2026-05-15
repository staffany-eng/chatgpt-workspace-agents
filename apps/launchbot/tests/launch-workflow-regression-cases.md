# Launchbot Launch Workflow Regression Cases

## Slack Identity And Capability

- Given a Slack prompt like `what can u do, partner?`, Launchbot should answer as Launchbot only: shipped Jira feature to code-grounded help article drafts, Google Docs review drafts, Slack approval routing, and Intercom draft articles.
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
- Slack automation copy should start with `Launchbot automation:` and use a light cowboy voice without weakening the approval instruction.

## Slack Approval To Intercom Draft

- A configured approval reaction from an authorized reviewer should create one Intercom draft for the matching article slug.
- Unauthorized reviewer reactions should be ignored.
- The pre-publish format gate should pass before any Intercom draft/staging article is created.
- The Pantheon evidence gate should pass before any Intercom draft/staging article is created.
- The VM-safe approval path should accept a human ✅ reaction on the correct `@Launch Bot` review message, create one Intercom draft, and post a bot-owned thread reply with the draft link or draft ID.
- The bot should post a progress reply before draft creation when the external source listener is present and a final reply with the draft link or draft ID after creation.
- Successful Intercom draft responses without a returned URL should still be accepted when an article ID is present.

## Intercom HTML Normalization

- Google Docs export should remove duplicate title headings and internal appendices.
- Center alignment for the audience block should be preserved.
- Google Docs bold spans should become semantic strong text where possible.
- Body-level `h1` headings should be converted below the article title level.
- Stable heading anchors should be present for section links where possible.

## Known Gap Guards

- Do not report Step 4 launch derivatives as implemented.
- Do not claim screenshot capture is automated until source code exists and is tested.
- Do not claim visual DOCX QA is complete unless a renderer was actually run.
