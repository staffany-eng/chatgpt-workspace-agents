# Launch Superpower Bot Handoff

Last updated: 2026-05-11

This handoff captures the current state of the Launch Superpower workflow so another teammate can continue from here without replaying the whole Codex thread.

## Project Goal

The workflow turns a shipped Jira feature into reviewable and publishable launch assets:

1. Step 1 drafts help article content from code-grounded evidence.
2. Step 2 uploads the draft articles to Google Docs, routes them to the right Drive folder, and posts Slack review messages.
3. Step 3 listens for Slack approval reactions and creates Intercom draft articles.
4. Step 4 is still a stub for launch derivatives such as Released posts and WhatsApp/newsletter drafts.

## Current Test Feature

- Jira issue: `KER-1742`
- Ticket name: `Club Blue`
- Feature: `ClubAny brands, perks, and redemptions`
- Latest clean test version: `v005`

## Latest Test Outputs

Step 1 generated two articles for `KER-1742/v005`:

- `owner-setup`: `Creating and managing ClubAny brands and perks`
- `staff-redemption`: `Discovering and redeeming ClubAny perks`

Step 2 uploaded Google Docs and posted Slack review messages:

- Owner setup Google Doc: https://docs.google.com/document/d/1AfJAobm9BKbWzbnL_u04miVcHcZ0sjuRbizMp91bg8E/edit?usp=drivesdk
- Staff redemption Google Doc: https://docs.google.com/document/d/1q9-VmxJQ5fdHFEPDGmZeTq1G55xC2e_0z7YUE_BfhD0/edit?usp=drivesdk
- Slack channel: `C01D9TLLLAJ`
- Owner setup Slack message timestamp: `1778490588.626099`
- Staff redemption Slack message timestamp: `1778490588.948169`

Step 3 created Intercom draft articles:

- Owner setup Intercom draft: https://app.intercom.com/a/apps/y12ertqm/articles/articles/15053607/show
- Staff redemption Intercom draft: https://app.intercom.com/a/apps/y12ertqm/articles/articles/15053608/show

Note: Vanessa replaced one Google Doc manually during review. For judging the desired final article format, use the DOCX she exported:

- `/Users/vanessakwa/Downloads/KER-1742 - Discovering and redeeming ClubAny perks.docx`

## Important Local Paths

Workspace:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace "
```

Workflow root:

```bash
vk-super-productivity/launch-superpower-bot
```

Latest artifacts:

```bash
vk-super-productivity/launch-superpower-bot/step-1-help-article-trigger/issues/KER-1742/versions/v005
vk-super-productivity/launch-superpower-bot/step-2-google-docs-approval/issues/KER-1742/versions/v005
vk-super-productivity/launch-superpower-bot/step-3-intercom-publish/issues/KER-1742/versions/v005
```

Local Codex skill files that were updated outside this repo:

```bash
/Users/vanessakwa/.codex/skills/help-article-generator/SKILL.md
/Users/vanessakwa/.codex/skills/help-article-generator/references/help-article-skeleton.md
```

Repo template that was updated:

```bash
vk-super-productivity/templates/help-article-template.md
```

## Code Areas Changed

Step 1:

- `step-1-help-article-trigger/launch_step1.py`
  - Tightened the drafting prompt to avoid raw HTML, repeated titles, visible divider lines, and internal appendix content in publishable articles.
  - Added ClubAny-specific guidance: use `Product: StaffAny`.
- `step-1-help-article-trigger/markdown_to_docx.py`
  - Improved DOCX rendering of centered audience blocks.
  - Added support for one-line legacy centered HTML blocks so older drafts do not show literal `<div>` text.

Step 2:

- `step-2-google-docs-approval/src/launch_step2.ts`
  - Fixed Step 1 to Step 2 article contract handling.
  - Legacy single-article manifests are upgraded into structured article records.
  - Multiple article Google Docs are uploaded and tracked separately.
  - Slack review messages now post per article when `LAUNCH_STEP2_SLACK_BOT_TOKEN` is present.

Step 3:

- `step-3-intercom-publish/src/launch_step3.ts`
  - Slack `white_check_mark` reactions trigger Intercom draft creation.
  - Unauthorized reviewers are ignored.
  - Bot posts a “creating draft” thread reply before publishing and a final draft link after publishing.
  - Intercom API draft creation accepts successful draft responses even when Intercom returns `url: null`.
  - Draft links now use direct Intercom article URLs.
  - Google Docs HTML export is normalized for Intercom:
    - removes duplicate title heading
    - removes internal appendix
    - preserves center alignment for the audience block
    - converts Google Docs bold spans to `<strong>`
    - adds heading IDs for anchors
    - converts body-level `h1` to `h2`

## Environment Variables Needed

Do not put secret values in this file. The colleague should get secrets through the proper password manager or secure sharing path.

Required for Step 2 Slack review posting:

```bash
LAUNCH_STEP2_SLACK_BOT_TOKEN
```

Required for Step 3 Slack reaction listener:

```bash
LAUNCH_STEP3_SLACK_SIGNING_SECRET
LAUNCH_STEP3_SLACK_BOT_TOKEN
```

Required for Step 3 Google Doc export:

```bash
LAUNCH_STEP3_GOOGLE_SERVICE_ACCOUNT_JSON
```

or a working local Google auth setup.

Required for Intercom draft creation:

```bash
LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN
LAUNCH_STEP3_INTERCOM_STAGING_COLLECTION_ID
```

Optional:

```bash
LAUNCH_STEP3_INTERCOM_AUTHOR_ID
```

The local test used `launchctl setenv` for Slack bot tokens so Terminal-launched processes could inherit them:

```bash
launchctl setenv LAUNCH_STEP2_SLACK_BOT_TOKEN "xoxb-..."
launchctl setenv LAUNCH_STEP3_SLACK_BOT_TOKEN "xoxb-..."
```

## How To Re-run The End-to-End Test

From the workspace root:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace "
./vk-super-productivity/launch-superpower-bot/step-1-help-article-trigger/redraft_help_article.sh \
  KER-1742 \
  --reason "handoff verification run" \
  --summary "ClubAny brands, perks, and redemptions"
```

This creates the next Step 1 version, such as `v006`.

Promote that version to Google Docs and Slack:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-2-google-docs-approval"
LAUNCH_STEP2_SLACK_BOT_TOKEN="$(launchctl getenv LAUNCH_STEP2_SLACK_BOT_TOKEN)" \
  npm exec -- tsx src/launch_step2.ts promote --issue KER-1742 --version v006
```

Manually create Intercom drafts for both article slugs:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-3-intercom-publish"
./publish_draft.sh KER-1742 v006 owner-setup
./publish_draft.sh KER-1742 v006 staff-redemption
```

If the generated slug changes, read the Step 1 or Step 2 manifest first:

```bash
cat "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-1-help-article-trigger/issues/KER-1742/versions/v006/manifest.json"
```

## How To Start The Slack Reaction Listener

Start Step 3 locally:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-3-intercom-publish"
export LAUNCH_STEP2_SLACK_BOT_TOKEN="$(launchctl getenv LAUNCH_STEP2_SLACK_BOT_TOKEN)"
export LAUNCH_STEP3_SLACK_BOT_TOKEN="$(launchctl getenv LAUNCH_STEP3_SLACK_BOT_TOKEN)"
export LAUNCH_STEP3_SLACK_SIGNING_SECRET="$(launchctl getenv LAUNCH_STEP3_SLACK_SIGNING_SECRET)"
./start_webhook_server.sh --host 127.0.0.1 --port 8790
```

Health check:

```bash
curl http://127.0.0.1:8790/
```

Expected response for `GET`:

```json
{"status":"method_not_allowed"}
```

Slack cannot call `127.0.0.1` directly. For local testing, expose the listener through a public HTTPS tunnel and set that URL in the Slack app Event Subscriptions Request URL. The local test used `localhost.run`:

```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:8790 nokey@localhost.run
```

Then configure the Slack app:

- Event Subscriptions: On
- Request URL: the `https://...lhr.life` tunnel URL
- Bot event: `reaction_added`

After changing the request URL, remove and re-add the checkmark reaction because Slack does not replay old reactions.

## Formatting Target From Vanessa

Use the edited DOCX as the target style. Key differences from the generated `v005` drafts:

- Prefer one combined ClubAny management article when the feature is about brands and perks.
- Use major sections:
  - `Managing Brands`
  - `Managing Perks`
  - `FAQ`
- Use nested outline entries:
  - `Managing Brands`
    - `Adding Brands`
    - `Editing Brands`
    - `Archiving / Unarchiving Brands`
  - `Managing Perks`
    - `Adding Perks`
    - `Editing Perks`
    - `Archiving / Unarchiving Perks`
  - `FAQ`
- Intro should be more marketable and user-facing, not only procedural.
- Include the object model explanation:
  - a brand is the business profile
  - a perk sits under a brand and contains redeemable perk details
- Include the catalogue visibility note:
  - an active brand still does not appear in the mobile catalogue until it has at least one active perk.
- Add screenshots or screenshot placeholders at key steps. Vanessa’s edited DOCX has six embedded screenshots.
- Generated DOCX should use real Word numbering, not fake text paragraphs that start with `1.`.

## Current Known Gaps

- The generator still needs a stronger ClubAny-specific content planner so it chooses the combined `Managing Brands` / `Managing Perks` article instead of splitting into staff usage and owner setup by default.
- `markdown_to_docx.py` still has limited list rendering. It should create real Word numbering definitions for numbered and nested outline lists.
- Screenshot capture/insertion is not automated yet.
- Visual DOCX render QA could not be run here because `soffice` is not installed.
- Step 4 launch derivative generation is still a stub.

## Verification Commands

Step 1:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-1-help-article-trigger"
python3 -m unittest tests/test_launch_step1.py
```

Step 2:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-2-google-docs-approval"
npm test
npm run typecheck
```

Step 3:

```bash
cd "/Users/vanessakwa/Documents/Codex/VK New Workspace /vk-super-productivity/launch-superpower-bot/step-3-intercom-publish"
npm test
npm run typecheck
```

## Suggested Next Work

1. Update Step 1 planning rules so ClubAny creates the combined management article by default.
2. Update the help-article generator skill with Vanessa’s target structure from the edited DOCX.
3. Make `markdown_to_docx.py` produce real numbered lists.
4. Decide how screenshot placeholders or real screenshot capture should work.
5. Re-run `KER-1742` as `v006` and compare to Vanessa’s edited DOCX.
6. Once the output is accepted, package the skill changes so teammates can install the same `help-article-generator` behavior.
